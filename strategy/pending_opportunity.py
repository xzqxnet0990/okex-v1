import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

from strategy.trade_type import TradeType
from strategy.trade_status import TradeStatus
from strategy.trade_record import TradeRecord
from strategy.trade_utils import _validate_params
from utils.simulated_account import SimulatedAccount
from utils.logger import Log, _N

class PendingOpportunity:

    def __init__(self, min_amount: float = 0.001):
        self.min_amount = min_amount
        self.order_timeout = 300  # 默认5分钟超时

    async def _check_pending_opportunity(
            self,
            coin: str,
            depths: Dict[str, Dict[str, Any]],
            account: SimulatedAccount,
            spot_exchanges: List[str],
            min_amount: float,
            min_basis: float,
            config: Dict[str, Any]
    ) -> Tuple[str, float, float, float, str, str]:
        """检查挂单套利机会"""
        try:
            # 参数验证
            if not _validate_params(coin, depths, account, spot_exchanges):
                Log("参数验证失败")
                return TradeType.NO_TRADE, 0, 0, 0, "", ""

            if not coin or not depths or not account or not spot_exchanges:
                Log("参数无效")
                return TradeType.NO_TRADE, 0, 0, 0, "", ""

            if len(spot_exchanges) < 2:
                Log("交易所数量不足")
                return TradeType.NO_TRADE, 0, 0, 0, "", ""

            coin = coin.upper()
            # 注意：depths 已经是当前币种的深度数据，不需要检查 coin 是否在 depths 中

            # 获取配置参数
            pending_config = config.get('strategy', {}).get('pending', {})
            # 降低挂单阈值，因为挂单有等待时间，可以接受更小的利润
            threshold_multiplier = pending_config.get('THRESHOLD_MULTIPLIER', 0.2)  # 默认为最小利润的20%，降低阈值
            min_pending_basis = min_basis * threshold_multiplier

            Log(f"===== 挂单套利检查 - 币种: {coin} =====")
            Log(f"最小利润率: {_N(min_basis * 100, 4)}%, 挂单阈值倍数: {threshold_multiplier}, 挂单最小利润率: {_N(min_pending_basis * 100, 4)}%")

            # 获取所有交易所的买卖价格
            exchange_prices = []
            Log(f"各交易所价格信息:")
            for exchange in spot_exchanges:
                if exchange not in depths:
                    continue
                depth = depths[exchange]
                if not depth or not depth.get('asks') or not depth.get('bids'):
                    continue
                if not depth['asks'] or not depth['bids']:
                    continue

                ask_price = depth['asks'][0][0]  # 最低卖价
                bid_price = depth['bids'][0][0]  # 最高买价
                ask_volume = depth['asks'][0][1]  # 卖单量
                bid_volume = depth['bids'][0][1]  # 买单量

                # 验证价格和数量的有效性
                if ask_price <= 0 or bid_price <= 0 or ask_volume < min_amount or bid_volume < min_amount:
                    Log(f"  {exchange}: 价格或数量无效")
                    continue

                exchange_prices.append((exchange, ask_price, bid_price))
                Log(f"  {exchange}: 卖价={_N(ask_price, 6)}, 买价={_N(bid_price, 6)}, 卖量={_N(ask_volume, 6)}, 买量={_N(bid_volume, 6)}")

            if len(exchange_prices) < 2:
                Log("有效交易所数量不足")
                return TradeType.NO_TRADE, 0, 0, 0, "", ""

            # 寻找最佳挂单机会
            best_opportunity = None
            max_profit_rate = -float('inf')

            Log("\n开始检查交易所对之间的挂单机会...")

            # 首先找到最低卖价和最高买价的交易所
            min_ask = float('inf')
            max_bid = -float('inf')
            min_ask_ex = None
            max_bid_ex = None

            for ex, ask, bid in exchange_prices:
                if ask < min_ask:
                    min_ask = ask
                    min_ask_ex = ex
                if bid > max_bid:
                    max_bid = bid
                    max_bid_ex = ex

            Log(f"最低卖价交易所: {min_ask_ex} @ {_N(min_ask, 6)}")
            Log(f"最高买价交易所: {max_bid_ex} @ {_N(max_bid, 6)}")

            # 检查每个交易所对
            for i, (ex1, ask1, bid1) in enumerate(exchange_prices):
                # 检查同一交易所内的挂单机会
                usdt_balance1 = account.get_balance('usdt', ex1)
                fee1 = account.get_fee(ex1, 'maker')

                # 同一交易所内的买卖利润率
                same_ex_profit_rate = (bid1 * (1 - fee1) - ask1 * (1 + fee1)) / ask1

                Log(f"\n交易所 {ex1} 内部挂单检查:")
                Log(f"  利润率 = {_N(same_ex_profit_rate * 100, 4)}%, 最小要求 = {_N(min_pending_basis * 100, 4)}%")
                Log(f"  余额检查: USDT = {_N(usdt_balance1, 2)}")

                if same_ex_profit_rate > min_pending_basis:
                    if usdt_balance1 >= min_amount * ask1:
                        Log(f"  ✓ 内部挂单符合条件: 利润率 {_N(same_ex_profit_rate * 100, 4)}% > 最小要求 {_N(min_pending_basis * 100, 4)}%")
                        if same_ex_profit_rate > max_profit_rate:
                            max_profit_rate = same_ex_profit_rate
                            best_opportunity = (TradeType.PENDING_TRADE, ask1, bid1, min_amount, ex1, ex1)
                    else:
                        Log(f"  ✗ 内部挂单余额不足: 需要 {_N(min_amount * ask1, 2)} USDT, 实际 {_N(usdt_balance1, 2)} USDT")

                # 检查不同交易所之间的挂单机会
                for j, (ex2, ask2, bid2) in enumerate(exchange_prices):
                    if i == j:
                        continue

                    # 检查账户余额
                    usdt_balance2 = account.get_balance('usdt', ex2)
                    coin_balance1 = account.get_balance(coin.lower(), ex1)
                    coin_balance2 = account.get_balance(coin.lower(), ex2)

                    Log(f"\n交易所对 {ex1} <-> {ex2} 检查:")
                    Log(f"  余额: {ex1} USDT={_N(usdt_balance1, 2)}, {coin}={_N(coin_balance1, 6)}; {ex2} USDT={_N(usdt_balance2, 2)}, {coin}={_N(coin_balance2, 6)}")

                    # 策略1: ex1买入->ex2卖出 (正向挂单)
                    profit_rate1 = (bid2 * (1 - fee1) - ask1 * (1 + fee1)) / ask1
                    Log(f"  正向策略1 ({ex1}买入->{ex2}卖出): 利润率 = {_N(profit_rate1 * 100, 4)}%, 最小要求 = {_N(min_pending_basis * 100, 4)}%")
                    
                    if profit_rate1 > min_pending_basis:
                        if usdt_balance1 >= min_amount * ask1:
                            Log(f"  ✓ 正向策略1符合条件: 利润率 {_N(profit_rate1 * 100, 4)}% > 最小要求 {_N(min_pending_basis * 100, 4)}%")
                            if profit_rate1 > max_profit_rate:
                                max_profit_rate = profit_rate1
                                best_opportunity = (TradeType.PENDING_TRADE, ask1, bid2, min_amount, ex1, ex2)
                        else:
                            Log(f"  ✗ 正向策略1余额不足: 需要 {_N(min_amount * ask1, 2)} USDT @ {ex1}, 实际 {_N(usdt_balance1, 2)} USDT")

                    # 策略2: ex2买入->ex1卖出 (正向挂单)
                    profit_rate2 = (bid1 * (1 - fee1) - ask2 * (1 + fee1)) / ask2
                    Log(f"  正向策略2 ({ex2}买入->{ex1}卖出): 利润率 = {_N(profit_rate2 * 100, 4)}%, 最小要求 = {_N(min_pending_basis * 100, 4)}%")
                    
                    if profit_rate2 > min_pending_basis:
                        if usdt_balance2 >= min_amount * ask2:
                            Log(f"  ✓ 正向策略2符合条件: 利润率 {_N(profit_rate2 * 100, 4)}% > 最小要求 {_N(min_pending_basis * 100, 4)}%")
                            if profit_rate2 > max_profit_rate:
                                max_profit_rate = profit_rate2
                                best_opportunity = (TradeType.PENDING_TRADE, ask2, bid1, min_amount, ex2, ex1)
                        else:
                            Log(f"  ✗ 正向策略2余额不足: 需要 {_N(min_amount * ask2, 2)} USDT @ {ex2}, 实际 {_N(usdt_balance2, 2)} USDT")

                    # 策略3: ex1卖出->ex2买入 (反向挂单)
                    # 检查是否有足够的币种余额用于反向挂单
                    if coin_balance1 >= min_amount:
                        # 修正反向挂单利润率计算公式
                        # 反向挂单应该是先卖出再买入，所以利润应该是卖出收入减去买入成本
                        # 卖出收入: bid1 * (1 - fee1)，买入成本: ask2 * (1 + fee1)
                        reverse_profit_rate1 = (bid1 * (1 - fee1) - ask2 * (1 + fee1)) / ask2
                        Log(f"  反向策略1 ({ex1}卖出->{ex2}买入): 利润率 = {_N(reverse_profit_rate1 * 100, 4)}%, 最小要求 = {_N(min_pending_basis * 100, 4)}%")

                        if reverse_profit_rate1 > min_pending_basis:
                            Log(f"  ✓ 反向策略1符合条件: 利润率 {_N(reverse_profit_rate1 * 100, 4)}% > 最小要求 {_N(min_pending_basis * 100, 4)}%")
                            if reverse_profit_rate1 > max_profit_rate:
                                max_profit_rate = reverse_profit_rate1
                                best_opportunity = (TradeType.REVERSE_PENDING, ask2, bid1, min_amount, ex2, ex1)
                        else:
                            Log(f"  ✗ 反向策略1利润率不足: {_N(reverse_profit_rate1 * 100, 4)}% < {_N(min_pending_basis * 100, 4)}%")
                    else:
                        Log(f"  ✗ 反向策略1余额不足: 需要 {_N(min_amount, 6)} {coin} @ {ex1}, 实际 {_N(coin_balance1, 6)} {coin}")

                    # 策略4: ex2卖出->ex1买入 (反向挂单)
                    if coin_balance2 >= min_amount:
                        # 修正反向挂单利润率计算公式
                        # 反向挂单应该是先卖出再买入，所以利润应该是卖出收入减去买入成本
                        # 卖出收入: bid2 * (1 - fee1)，买入成本: ask1 * (1 + fee1)
                        reverse_profit_rate2 = (bid2 * (1 - fee1) - ask1 * (1 + fee1)) / ask1
                        Log(f"  反向策略2 ({ex2}卖出->{ex1}买入): 利润率 = {_N(reverse_profit_rate2 * 100, 4)}%, 最小要求 = {_N(min_pending_basis * 100, 4)}%")

                        if reverse_profit_rate2 > min_pending_basis:
                            Log(f"  ✓ 反向策略2符合条件: 利润率 {_N(reverse_profit_rate2 * 100, 4)}% > 最小要求 {_N(min_pending_basis * 100, 4)}%")
                            if reverse_profit_rate2 > max_profit_rate:
                                max_profit_rate = reverse_profit_rate2
                                best_opportunity = (TradeType.REVERSE_PENDING, ask1, bid2, min_amount, ex1, ex2)
                        else:
                            Log(f"  ✗ 反向策略2利润率不足: {_N(reverse_profit_rate2 * 100, 4)}% < {_N(min_pending_basis * 100, 4)}%")
                    else:
                        Log(f"  ✗ 反向策略2余额不足: 需要 {_N(min_amount, 6)} {coin} @ {ex2}, 实际 {_N(coin_balance2, 6)} {coin}")

            if best_opportunity:
                trade_type, buy_price, sell_price, amount, buy_ex, sell_ex = best_opportunity
                Log(f"\n===== 发现最佳挂单机会 =====")
                if trade_type == TradeType.PENDING_TRADE:
                    Log(f"类型: 正向挂单")
                    Log(f"买入交易所: {buy_ex} @ {_N(buy_price, 6)}")
                    Log(f"卖出交易所: {sell_ex} @ {_N(sell_price, 6)}")
                else:  # TradeType.REVERSE_PENDING
                    Log(f"类型: 反向挂单")
                    Log(f"卖出交易所: {sell_ex} @ {_N(sell_price, 6)}")
                    Log(f"买入交易所: {buy_ex} @ {_N(buy_price, 6)}")
                Log(f"数量: {_N(amount, 6)}")
                Log(f"预期收益率: {_N(max_profit_rate * 100, 4)}%")
                Log(f"最小收益率要求: {_N(min_pending_basis * 100, 4)}%")
                Log(f"===========================")
                return best_opportunity

            Log("\n未发现符合条件的挂单机会")
            return TradeType.NO_TRADE, 0, 0, 0, "", ""

        except Exception as e:
            Log(f"检查挂单机会时发生错误: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return TradeType.NO_TRADE, 0, 0, 0, "", ""

    def _check_pending_order_executable(self, order: Dict[str, Any], buy_depth: Dict[str, Any],
                                        sell_depth: Dict[str, Any]) -> bool:
        """检查挂单是否可以执行
        
        当市场价格达到或超过挂单价格时，挂单可以执行。
        买入挂单：当市场卖价低于或等于挂单买价时可执行
        卖出挂单：当市场买价高于或等于挂单卖价时可执行
        
        对于反向挂单，条件相反：
        买入挂单：当市场卖价高于或等于挂单买价时可执行
        卖出挂单：当市场买价低于或等于挂单卖价时可执行
        """
        try:
            # 获取市场价格
            market_buy_price = buy_depth['asks'][0][0]  # 市场最低卖价
            market_sell_price = sell_depth['bids'][0][0]  # 市场最高买价

            # 获取挂单价格
            order_buy_price = order['buy_price']
            order_sell_price = order['sell_price']
            
            # 获取挂单类型
            order_type = order.get('type', TradeType.PENDING_TRADE)
            is_reverse = order_type == TradeType.REVERSE_PENDING
            
            if is_reverse:
                # 反向挂单条件
                # 检查买入条件：市场卖价高于或等于挂单买价
                buy_executable = market_buy_price >= order_buy_price

                # 检查卖出条件：市场买价低于或等于挂单卖价
                sell_executable = market_sell_price <= order_sell_price
            else:
                # 正向挂单条件
                # 检查买入条件：市场卖价低于或等于挂单买价
                buy_executable = market_buy_price <= order_buy_price

                # 检查卖出条件：市场买价高于或等于挂单卖价
                sell_executable = market_sell_price >= order_sell_price

            # 同时满足买入和卖出条件时，挂单可执行
            executable = buy_executable and sell_executable

            if executable:
                Log(f"挂单可执行 (类型: {order_type}):")
                if is_reverse:
                    Log(f"  买入条件: 市场卖价 {_N(market_buy_price, 6)} >= 挂单买价 {_N(order_buy_price, 6)}: {buy_executable}")
                    Log(f"  卖出条件: 市场买价 {_N(market_sell_price, 6)} <= 挂单卖价 {_N(order_sell_price, 6)}: {sell_executable}")
                else:
                    Log(f"  买入条件: 市场卖价 {_N(market_buy_price, 6)} <= 挂单买价 {_N(order_buy_price, 6)}: {buy_executable}")
                    Log(f"  卖出条件: 市场买价 {_N(market_sell_price, 6)} >= 挂单卖价 {_N(order_sell_price, 6)}: {sell_executable}")

            return executable

        except Exception as e:
            Log(f"检查挂单是否可执行时出错: {str(e)}")
            return False

    # 提取共同逻辑：检查价格变动
    def _check_price_change(self, original_price: float, current_price: float, max_change_rate: float = 0.005) -> Tuple[bool, float]:
        """
        检查价格变动是否超过阈值
        
        Args:
            original_price: 原始价格
            current_price: 当前价格
            max_change_rate: 最大允许变动比例，默认0.5%
            
        Returns:
            Tuple[bool, float]: (是否变动过大, 变动比例)
        """
        if original_price <= 0:
            return True, 1.0  # 如果原始价格为0或负数，视为变动过大
            
        change_rate = abs(current_price - original_price) / original_price
        return change_rate > max_change_rate, change_rate

    # 提取共同逻辑：计算交易利润
    def _calculate_trade_profit(self, 
                               amount: float, 
                               buy_price: float, 
                               sell_price: float, 
                               buy_fee_rate: float, 
                               sell_fee_rate: float,
                               is_reverse: bool = False) -> Dict[str, float]:
        """
        计算交易利润和相关数据
        
        Args:
            amount: 交易数量
            buy_price: 买入价格
            sell_price: 卖出价格
            buy_fee_rate: 买入手续费率
            sell_fee_rate: 卖出手续费率
            is_reverse: 是否为反向挂单
            
        Returns:
            Dict[str, float]: 包含成本、收益、手续费、利润等信息的字典
        """
        cost = amount * buy_price
        revenue = amount * sell_price
        buy_fee = cost * buy_fee_rate
        sell_fee = revenue * sell_fee_rate
        
        if is_reverse:
            # 修正反向挂单的利润计算
            # 反向挂单是先卖出再买入，所以利润是卖出收入减去买入成本
            profit = revenue - cost - buy_fee - sell_fee
            profit_rate = profit / cost if cost > 0 else 0
        else:
            profit = revenue - cost - buy_fee - sell_fee
            profit_rate = profit / cost if cost > 0 else 0
            
        return {
            'cost': cost,
            'revenue': revenue,
            'buy_fee': buy_fee,
            'sell_fee': sell_fee,
            'total_fee': buy_fee + sell_fee,
            'profit': profit,
            'profit_rate': profit_rate
        }

    # 提取共同逻辑：记录交易
    def _record_trade(self, 
                     account: SimulatedAccount, 
                     trade_type: str, 
                     coin: str,
                     buy_exchange: str, 
                     sell_exchange: str, 
                     amount: float, 
                     buy_price: float, 
                     sell_price: float, 
                     profit: float, 
                     profit_rate: float, 
                     fee: float,
                     current_time: datetime) -> None:
        """
        记录交易统计和交易记录
        
        Args:
            account: 账户对象
            trade_type: 交易类型
            coin: 币种
            buy_exchange: 买入交易所
            sell_exchange: 卖出交易所
            amount: 交易数量
            buy_price: 买入价格
            sell_price: 卖出价格
            profit: 利润
            profit_rate: 利润率
            fee: 手续费
            current_time: 当前时间
        """
        # 更新交易统计
        account.update_trade_stats(
            trade_type,
            amount,
            profit,
            fee,
            TradeStatus.SUCCESS
        )

        # 添加交易记录
        if trade_type == TradeType.PENDING_TRADE:
            # 创建正向挂单交易记录
            buy_fee = fee / 2  # 假设手续费平均分配
            sell_fee = fee / 2
            
            trade_record = TradeRecord.create_arbitrage_record(
                coin=coin.upper(),
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                amount=amount,
                buy_price=buy_price,
                sell_price=sell_price,
                buy_fee=buy_fee,
                sell_fee=sell_fee,
                profit=profit,
                status=TradeStatus.SUCCESS
            )
            
            # 记录交易记录到日志
            TradeRecord.log_trade_record(trade_record)
            
            # 将交易记录添加到账户
            account.add_trade_record(trade_record)
            
        elif trade_type == TradeType.REVERSE_PENDING:
            # 创建反向挂单交易记录
            buy_fee = fee / 2  # 假设手续费平均分配
            sell_fee = fee / 2
            
            trade_record = TradeRecord.create_arbitrage_record(
                coin=coin.upper(),
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                amount=amount,
                buy_price=buy_price,
                sell_price=sell_price,
                buy_fee=buy_fee,
                sell_fee=sell_fee,
                profit=profit,
                status=TradeStatus.SUCCESS
            )
            
            # 记录交易记录到日志
            TradeRecord.log_trade_record(trade_record)
            
            # 将交易记录添加到账户
            account.add_trade_record(trade_record)
        else:
            # 对于其他类型的交易，使用通用的记录方法
            Log(f"未知的交易类型: {trade_type}，使用通用记录方法")
            
            trade_record = TradeRecord.create_arbitrage_record(
                coin=coin.upper(),
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                amount=amount,
                buy_price=buy_price,
                sell_price=sell_price,
                buy_fee=fee/2,
                sell_fee=fee/2,
                profit=profit,
                status=TradeStatus.SUCCESS
            )
            
            # 记录交易记录到日志
            TradeRecord.log_trade_record(trade_record)
            
            # 将交易记录添加到账户
            account.add_trade_record(trade_record)

    async def _execute_pending_order(self,
                                     account: SimulatedAccount,
                                     order: Dict[str, Any],
                                     buy_depth: Dict[str, Any],
                                     sell_depth: Dict[str, Any],
                                     current_time: datetime,
                                     config: Dict[str, Any]) -> None:
        """执行挂单交易"""
        try:
            coin = order['coin']
            buy_exchange = order['buy_exchange']
            sell_exchange = order['sell_exchange']
            amount = order['amount']
            buy_price = order['buy_price']
            sell_price = order['sell_price']
            order_id = order['id']
            order_type = order.get('type', TradeType.PENDING_TRADE)
            is_reverse = order_type == TradeType.REVERSE_PENDING

            # 获取交易所对象
            buy_ex = account.exchanges.get(buy_exchange)
            sell_ex = account.exchanges.get(sell_exchange)

            if not buy_ex or not sell_ex:
                Log(f"无法获取交易所对象: {buy_exchange} 或 {sell_exchange}")
                return

            # 获取最新价格
            current_buy_price = buy_depth['asks'][0][0]  # 买入使用卖一价
            current_sell_price = sell_depth['bids'][0][0]  # 卖出使用买一价

            # 检查价格是否变动过大
            buy_changed, buy_change_rate = self._check_price_change(buy_price, current_buy_price)
            sell_changed, sell_change_rate = self._check_price_change(sell_price, current_sell_price)
            
            if buy_changed or sell_changed:
                Log(f"价格变动过大，放弃执行挂单")
                Log(f"买入价格: {_N(buy_price, 6)} -> {_N(current_buy_price, 6)} (变动: {_N(buy_change_rate * 100, 2)}%)")
                Log(f"卖出价格: {_N(sell_price, 6)} -> {_N(current_sell_price, 6)} (变动: {_N(sell_change_rate * 100, 2)}%)")
                return

            # 获取手续费率
            buy_fee_rate = account.get_fee(buy_exchange, 'taker')
            sell_fee_rate = account.get_fee(sell_exchange, 'taker')

            # 计算利润
            profit_data = self._calculate_trade_profit(
                amount, current_buy_price, current_sell_price, 
                buy_fee_rate, sell_fee_rate, is_reverse
            )
            
            if profit_data['profit'] <= 0:
                Log(f"价格变动导致无利润，放弃执行{'反向' if is_reverse else ''}挂单")
                Log(f"买入成本: {_N(profit_data['cost'], 6)} USDT")
                Log(f"卖出收益: {_N(profit_data['revenue'], 6)} USDT")
                Log(f"手续费: {_N(profit_data['total_fee'], 6)} USDT")
                Log(f"利润: {_N(profit_data['profit'], 6)} USDT ({_N(profit_data['profit_rate'] * 100, 4)}%)")
                return

            if is_reverse:
                # 对于反向挂单，先执行卖出操作，再执行买入操作
                # 记录卖出前的余额
                before_coin_balance_sell = account.get_balance(coin.lower(), sell_exchange)
                before_usdt_balance_sell = account.get_balance('usdt', sell_exchange)
                
                # 执行卖出操作
                sell_order_id = f"sell_{coin}_{int(time.time() * 1000)}"
                sell_result = await account.CreateOrder(sell_ex, coin.upper(), current_sell_price, amount, is_buy=False)

                if not sell_result:
                    Log(f"卖出订单创建失败，取消挂单")
                    self._cancel_pending_order(account, order)
                    return

                Log(f"卖出订单创建成功: {sell_result.get('id', sell_order_id)}")
                Log(f"卖出{coin.upper()}: {_N(amount, 6)} @ {_N(current_sell_price, 6)} = {_N(profit_data['revenue'], 6)} USDT")
                Log(f"卖出手续费: {_N(profit_data['sell_fee'], 6)} USDT")

                # 解冻原有资金（之前冻结的是买入资金）
                account.unfreeze_balance(coin.lower(), amount, sell_exchange)

                # 更新卖出交易所余额
                account.update_balance(coin.lower(), -amount, sell_exchange)
                account.update_balance('usdt', profit_data['revenue'] - profit_data['sell_fee'], sell_exchange)
                
                # 记录卖出后的余额
                after_coin_balance_sell = account.get_balance(coin.lower(), sell_exchange)
                after_usdt_balance_sell = account.get_balance('usdt', sell_exchange)
                
                # 创建卖出交易记录
                sell_record = TradeRecord.create_hedge_sell_record(
                    coin=coin.upper(),
                    exchange=sell_exchange,
                    amount=amount,
                    price=current_sell_price,
                    fee=profit_data['sell_fee'],
                    balance_before=before_coin_balance_sell,
                    balance_after=after_coin_balance_sell,
                    usdt_before=before_usdt_balance_sell,
                    usdt_after=after_usdt_balance_sell,
                    status=TradeStatus.SUCCESS
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(sell_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(sell_record)
                
                # 记录买入前的余额
                before_coin_balance_buy = account.get_balance(coin.lower(), buy_exchange)
                before_usdt_balance_buy = account.get_balance('usdt', buy_exchange)

                # 执行买入操作
                buy_order_id = f"buy_{coin}_{int(time.time() * 1000)}"
                buy_result = await account.CreateOrder(buy_ex, coin.upper(), current_buy_price, amount, is_buy=True)

                if not buy_result:
                    Log(f"买入订单创建失败，需要手动处理卖出的USDT")
                    # 从挂单列表中移除
                    account.remove_pending_order(order_id)
                    return

                Log(f"买入订单创建成功: {buy_result.get('id', buy_order_id)}")
                Log(f"买入{coin.upper()}: {_N(amount, 6)} @ {_N(current_buy_price, 6)} = {_N(profit_data['cost'], 6)} USDT")
                Log(f"买入手续费: {_N(profit_data['buy_fee'], 6)} USDT")

                # 更新买入交易所余额
                account.update_balance('usdt', -(profit_data['cost'] + profit_data['buy_fee']), buy_exchange)
                account.update_balance(coin.lower(), amount, buy_exchange)
                
                # 记录买入后的余额
                after_coin_balance_buy = account.get_balance(coin.lower(), buy_exchange)
                after_usdt_balance_buy = account.get_balance('usdt', buy_exchange)
                
                # 创建买入交易记录
                buy_record = TradeRecord.create_hedge_buy_record(
                    coin=coin.upper(),
                    exchange=buy_exchange,
                    amount=amount,
                    price=current_buy_price,
                    fee=profit_data['buy_fee'],
                    balance_before=before_coin_balance_buy,
                    balance_after=after_coin_balance_buy,
                    usdt_before=before_usdt_balance_buy,
                    usdt_after=after_usdt_balance_buy,
                    status=TradeStatus.SUCCESS
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(buy_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(buy_record)
                
                # 记录交易
                self._record_trade(
                    account, TradeType.REVERSE_PENDING, coin, 
                    buy_exchange, sell_exchange, amount, 
                    buy_price, sell_price, 
                    profit_data['profit'], profit_data['profit_rate'], 
                    profit_data['total_fee'], current_time
                )

                # 从挂单列表中移除
                account.remove_pending_order(order_id)

                Log(f"\n反向挂单交易执行成功:")
                Log(f"卖出交易所: {sell_exchange}")
                Log(f"买入交易所: {buy_exchange}")
                Log(f"币种: {coin.upper()}")
                Log(f"数量: {_N(amount, 6)}")
                Log(f"卖出价格: {_N(sell_price, 6)}")
                Log(f"买入价格: {_N(buy_price, 6)}")
                Log(f"利润: {_N(profit_data['profit'], 6)} USDT ({_N(profit_data['profit_rate'] * 100, 4)}%)")
                
            else:
                # 正向挂单处理逻辑
                # 记录买入前的余额
                before_coin_balance_buy = account.get_balance(coin.lower(), buy_exchange)
                before_usdt_balance_buy = account.get_balance('usdt', buy_exchange)
                
                # 执行买入操作
                buy_order_id = f"buy_{coin}_{int(time.time() * 1000)}"
                # 使用CreateOrder方法替代直接调用Buy
                buy_result = await account.CreateOrder(buy_ex, coin.upper(), current_buy_price, amount, is_buy=True)

                if not buy_result:
                    Log(f"买入订单创建失败，取消挂单")
                    self._cancel_pending_order(account, order)
                    return

                Log(f"买入订单创建成功: {buy_result.get('id', buy_order_id)}")
                Log(f"买入{coin.upper()}: {_N(amount, 6)} @ {_N(current_buy_price, 6)} = {_N(profit_data['cost'], 6)} USDT")
                Log(f"买入手续费: {_N(profit_data['buy_fee'], 6)} USDT")

                # 解冻原有资金（之前冻结的是买入资金）
                account.unfreeze_balance('usdt', profit_data['cost'] + profit_data['buy_fee'], buy_exchange)

                # 更新买入交易所余额
                account.update_balance('usdt', -(profit_data['cost'] + profit_data['buy_fee']), buy_exchange)
                account.update_balance(coin.lower(), amount, buy_exchange)
                
                # 记录买入后的余额
                after_coin_balance_buy = account.get_balance(coin.lower(), buy_exchange)
                after_usdt_balance_buy = account.get_balance('usdt', buy_exchange)
                
                # 创建买入交易记录
                buy_record = TradeRecord.create_hedge_buy_record(
                    coin=coin.upper(),
                    exchange=buy_exchange,
                    amount=amount,
                    price=current_buy_price,
                    fee=profit_data['buy_fee'],
                    balance_before=before_coin_balance_buy,
                    balance_after=after_coin_balance_buy,
                    usdt_before=before_usdt_balance_buy,
                    usdt_after=after_usdt_balance_buy,
                    status=TradeStatus.SUCCESS
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(buy_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(buy_record)
                
                # 记录卖出前的余额
                before_coin_balance_sell = account.get_balance(coin.lower(), sell_exchange)
                before_usdt_balance_sell = account.get_balance('usdt', sell_exchange)

                # 执行卖出操作
                sell_order_id = f"sell_{coin}_{int(time.time() * 1000)}"
                # 使用CreateOrder方法替代直接调用Sell
                sell_result = await account.CreateOrder(sell_ex, coin.upper(), current_sell_price, amount, is_buy=False)

                if not sell_result:
                    Log(f"卖出订单创建失败，需要手动处理买入的币种")
                    # 从挂单列表中移除
                    account.remove_pending_order(order_id)
                    return

                Log(f"卖出订单创建成功: {sell_result.get('id', sell_order_id)}")
                Log(f"卖出{coin.upper()}: {_N(amount, 6)} @ {_N(current_sell_price, 6)} = {_N(profit_data['revenue'], 6)} USDT")
                Log(f"卖出手续费: {_N(profit_data['sell_fee'], 6)} USDT")

                # 更新卖出交易所余额
                account.update_balance(coin.lower(), -amount, sell_exchange)
                account.update_balance('usdt', profit_data['revenue'] - profit_data['sell_fee'], sell_exchange)
                
                # 记录卖出后的余额
                after_coin_balance_sell = account.get_balance(coin.lower(), sell_exchange)
                after_usdt_balance_sell = account.get_balance('usdt', sell_exchange)
                
                # 创建卖出交易记录
                sell_record = TradeRecord.create_hedge_sell_record(
                    coin=coin.upper(),
                    exchange=sell_exchange,
                    amount=amount,
                    price=current_sell_price,
                    fee=profit_data['sell_fee'],
                    balance_before=before_coin_balance_sell,
                    balance_after=after_coin_balance_sell,
                    usdt_before=before_usdt_balance_sell,
                    usdt_after=after_usdt_balance_sell,
                    status=TradeStatus.SUCCESS
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(sell_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(sell_record)

                # 记录交易
                self._record_trade(
                    account, TradeType.PENDING_TRADE, coin, 
                    buy_exchange, sell_exchange, amount, 
                    buy_price, sell_price, 
                    profit_data['profit'], profit_data['profit_rate'], 
                    profit_data['total_fee'], current_time
                )

                # 从挂单列表中移除
                account.remove_pending_order(order_id)

                Log(f"\n挂单交易执行成功:")
                Log(f"买入交易所: {buy_exchange}")
                Log(f"卖出交易所: {sell_exchange}")
                Log(f"币种: {coin.upper()}")
                Log(f"数量: {_N(amount, 6)}")
                Log(f"买入价格: {_N(buy_price, 6)}")
                Log(f"卖出价格: {_N(sell_price, 6)}")
                Log(f"利润: {_N(profit_data['profit'], 6)} USDT ({_N(profit_data['profit_rate'] * 100, 4)}%)")

        except Exception as e:
            Log(f"执行挂单交易时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())

    def _cancel_pending_order(self, account: SimulatedAccount, order: Dict[str, Any]) -> None:
        """取消挂单并解冻资金"""
        try:
            order_id = order['id']
            buy_exchange = order['buy_exchange']
            sell_exchange = order['sell_exchange']
            coin = order['coin']
            order_type = order.get('type', TradeType.PENDING_TRADE)
            is_reverse = order_type == TradeType.REVERSE_PENDING

            # 计算需要解冻的资金
            amount = order['amount']
            buy_price = order['buy_price']
            sell_price = order['sell_price']
            buy_fee_rate = order['buy_fee_rate']
            cost = amount * buy_price
            buy_fee = cost * buy_fee_rate

            if is_reverse:
                # 反向挂单解冻币种余额
                account.unfreeze_balance(coin.lower(), amount, sell_exchange)
                Log(f"解冻{coin.upper()}: {_N(amount, 6)} @ {sell_exchange}")
                
                # 创建撤销挂单记录
                trade_record = TradeRecord.create_reverse_pending_record(
                    coin=coin.upper(),
                    exchange=sell_exchange,
                    original_order_type="sell",
                    original_amount=amount,
                    original_price=sell_price,
                    original_order_id=order_id,
                    reverse_amount=amount,
                    reverse_price=sell_price,
                    balance_before=account.get_balance(coin.lower(), sell_exchange),
                    usdt_before=account.get_balance('usdt', sell_exchange),
                    status=TradeStatus.CANCELLED,
                    reason="挂单超时或手动取消"
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
            else:
                # 正向挂单解冻USDT
                account.unfreeze_balance('usdt', cost + buy_fee, buy_exchange)
                Log(f"解冻USDT: {_N(cost + buy_fee, 2)} @ {buy_exchange}")
                
                # 创建撤销挂单记录
                trade_record = TradeRecord.create_pending_trade_record(
                    coin=coin.upper(),
                    exchange=buy_exchange,
                    order_type="buy",
                    amount=amount,
                    price=buy_price,
                    estimated_fee=buy_fee,
                    balance_before=account.get_balance(coin.lower(), buy_exchange),
                    usdt_before=account.get_balance('usdt', buy_exchange),
                    order_id=order_id,
                    status=TradeStatus.CANCELLED,
                    reason="挂单超时或手动取消"
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)

            # 从挂单列表中移除
            account.remove_pending_order(order_id)
            Log(f"挂单已取消并从列表中移除: {order_id}")

            # 记录取消订单的统计
            trade_type = TradeType.REVERSE_PENDING if is_reverse else TradeType.PENDING_TRADE
            account.update_trade_stats(
                trade_type,
                amount,
                0,  # 没有盈亏
                0,  # 没有手续费
                TradeStatus.CANCELLED
            )
            
            # 添加对未成交挂单币种的统计
            account.update_cancelled_order_stats(coin, amount, buy_exchange, sell_exchange, is_reverse)
            
        except Exception as e:
            Log(f"取消挂单时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())

    async def process_pending_orders(self,
                                     account: SimulatedAccount,
                                     current_time: datetime,
                                     config: Dict[str, Any]
                                     ) -> None:
        """处理挂单"""
        try:
            pending_orders = account.get_pending_orders()
            if not pending_orders:
                return

            Log(f"处理挂单，共 {len(pending_orders)} 个")
            for order in pending_orders:
                coin = order.get('coin')
                if not coin:
                    Log(f"挂单缺少币种信息")
                    continue

                # 获取买入和卖出交易所的深度数据
                buy_exchange = order.get('buy_exchange')
                sell_exchange = order.get('sell_exchange')

                if not buy_exchange or not sell_exchange:
                    Log(f"挂单缺少交易所信息")
                    continue

                # 使用 fetch_all_depths_compat 获取最新深度数据
                from utils.depth_data import fetch_all_depths_compat
                from exchanges import ExchangeFactory
                
                # 获取交易所实例
                exchanges = {}
                for ex in [buy_exchange, sell_exchange]:
                    exchange_instance = ExchangeFactory.get_exchange(ex)
                    if exchange_instance:
                        exchanges[ex] = exchange_instance
                
                # 获取支持的交易所配置
                supported_exchanges = {coin: [buy_exchange, sell_exchange]}
                
                # 获取最新深度数据
                updated_depths = await fetch_all_depths_compat(coin, exchanges, supported_exchanges, config)
                
                # 检查是否成功获取深度数据
                if coin not in updated_depths or not updated_depths[coin]:
                    Log(f"无法获取{coin}的最新深度数据")
                    continue
                
                if buy_exchange not in updated_depths[coin] or sell_exchange not in updated_depths[coin]:
                    Log(f"无法获取{buy_exchange}或{sell_exchange}的最新深度数据")
                    continue
                
                buy_depth = updated_depths[coin][buy_exchange]
                sell_depth = updated_depths[coin][sell_exchange]

                # 检查挂单是否可执行
                if self._check_pending_order_executable(order, buy_depth, sell_depth):
                    # 执行挂单
                    await self._execute_pending_order(account, order, buy_depth, sell_depth, current_time, config)
                else:
                    # 检查挂单是否超时
                    create_time = order.get('time')
                    if create_time:
                        create_time = datetime.fromisoformat(create_time)
                        elapsed_seconds = (current_time - create_time).total_seconds()
                        if elapsed_seconds > self.order_timeout:
                            Log(f"挂单超时，取消挂单")
                            self._cancel_pending_order(account, order)
                        else:
                            Log(f"挂单未超时，继续等待")
                    else:
                        Log(f"挂单缺少创建时间信息")
        except Exception as e:
            Log(f"处理挂单时发生错误: {str(e)}")
            import traceback
            Log(traceback.format_exc())

    async def execute_pending_trade(
            self,
            account: SimulatedAccount,
            coin: str,
            buy_ex: str,
            sell_ex: str,
            buy_depth: Dict[str, Any],
            sell_depth: Dict[str, Any],
            trade_type: str,
            current_time: datetime,
            amount:float,
            config: Dict[str, Any]
    ) -> None:
        """执行挂单套利"""
        try:
            # 创建PendingOpportunity实例以使用其辅助方法
            is_reverse = trade_type == TradeType.REVERSE_PENDING
            trade_type_display = "反向挂单套利" if is_reverse else "挂单套利"

            Log(f"开始执行{trade_type_display} - 币种: {coin}")
            if is_reverse:
                Log(f"卖出交易所: {sell_ex}, 买入交易所: {buy_ex}")
            else:
                Log(f"买入交易所: {buy_ex}, 卖出交易所: {sell_ex}")

            # 获取买卖价格
            buy_price = buy_depth['asks'][0][0]
            sell_price = sell_depth['bids'][0][0]

            Log(f"当前市场价格 - 买入: {_N(buy_price, 6)}, 卖出: {_N(sell_price, 6)}")

            # 计算挂单价格（更大幅度的价格调整）
            price_adjust_rate = config.get('strategy', {}).get('PRICE_ADJUST_RATE', 0.003)  # 默认0.3%的价格调整
            pending_buy_price = buy_price * (1 - price_adjust_rate)  # 比最优买价低0.3%
            pending_sell_price = sell_price * (1 + price_adjust_rate)  # 比最优卖价高0.3%

            Log(f"价格调整率: {_N(price_adjust_rate * 100, 4)}%")
            Log(f"调整后价格 - 买入: {_N(pending_buy_price, 6)}, 卖出: {_N(pending_sell_price, 6)}")

            # 获取可交易数量
            buy_amount = buy_depth['asks'][0][1]
            sell_amount = sell_depth['bids'][0][1]
            min_amount = config.get('strategy', {}).get('MIN_AMOUNT', 0.001)

            Log(f"市场深度 - 买入: {_N(buy_amount, 6)}, 卖出: {_N(sell_amount, 6)}")

            trade_amount = min(buy_amount, sell_amount, amount)
            Log(f"计算的交易数量: {_N(trade_amount, 6)}")

            if trade_amount >= min_amount:
                # 获取费率
                buy_fee_rate = account.get_fee(buy_ex, 'maker')
                sell_fee_rate = account.get_fee(sell_ex, 'maker')

                Log(f"手续费率 - 买入: {_N(buy_fee_rate * 100, 4)}%, 卖出: {_N(sell_fee_rate * 100, 4)}%")

                # 使用辅助方法计算利润
                profit_data = self._calculate_trade_profit(
                    trade_amount, pending_buy_price, pending_sell_price,
                    buy_fee_rate, sell_fee_rate, is_reverse
                )

                # 计算潜在利润（不计入实际统计）
                potential_profit = profit_data['profit']
                min_profit_amount = config.get('strategy', {}).get('MIN_PROFIT_AMOUNT', 0.05)  # 降低最小利润金额（USDT）

                Log(f"交易计算:")
                Log(f"  买入成本: {_N(profit_data['cost'], 4)} USDT")
                Log(f"  卖出收入: {_N(profit_data['revenue'], 4)} USDT")
                Log(f"  买入手续费: {_N(profit_data['buy_fee'], 4)} USDT")
                Log(f"  卖出手续费: {_N(profit_data['sell_fee'], 4)} USDT")
                Log(f"  总手续费: {_N(profit_data['total_fee'], 4)} USDT")
                Log(f"  潜在利润: {_N(potential_profit, 4)} USDT")
                Log(f"  最小利润要求: {min_profit_amount} USDT")

                # 只有在预期利润大于最小利润金额时才创建挂单
                if potential_profit < min_profit_amount:
                    Log(f"预期利润 {_N(potential_profit, 6)} USDT 小于最小要求 {min_profit_amount} USDT，跳过挂单")
                    return

                # 检查USDT余额是否足够
                usdt_balance = account.get_balance('usdt', buy_ex)
                if usdt_balance < profit_data['cost'] + profit_data['buy_fee']:
                    Log(f"买入交易所USDT余额不足，放弃交易")
                    Log(f"需要: {_N(profit_data['cost'] + profit_data['buy_fee'], 6)} USDT")
                    Log(f"可用: {_N(usdt_balance, 6)} USDT")
                    return

                # 检查是否已经有相同交易所的挂单
                existing_orders = account.get_pending_orders()
                if existing_orders:
                    Log(f"当前已有 {len(existing_orders)} 个挂单")

                    # 检查是否已有相同交易所对的挂单
                    for order in existing_orders:
                        if order.get('buy_exchange') == buy_ex and order.get('sell_exchange') == sell_ex and order.get(
                                'coin') == coin:
                            Log(f"已存在相同交易所对的{coin}挂单，跳过")
                            return

                    # 检查挂单总数限制
                    max_pending_orders = config.get('strategy', {}).get('MAX_PENDING_ORDERS', 3)
                    if len(existing_orders) >= max_pending_orders:
                        Log(f"挂单数量已达上限 {max_pending_orders}，跳过")
                        return

                    # 检查挂单总价值限制
                    max_total_pending_value = config.get('strategy', {}).get('MAX_TOTAL_PENDING_VALUE', 10000)
                    total_pending_value = sum(
                        order.get('amount', 0) * order.get('buy_price', 0) for order in existing_orders)
                    if total_pending_value + profit_data['cost'] > max_total_pending_value:
                        Log(f"挂单总价值已达上限 {max_total_pending_value} USDT，跳过")
                        Log(f"当前挂单总价值: {_N(total_pending_value, 2)} USDT, 新挂单价值: {_N(profit_data['cost'], 2)} USDT")
                        return

                # 获取订单超时时间，用于日志显示
                order_timeout = config.get('strategy', {}).get('ORDER_TIMEOUT', 300)  # 5分钟超时
                timeout_time = (current_time + timedelta(seconds=order_timeout)).strftime('%Y-%m-%d %H:%M:%S')

                Log(f"\n创建{trade_type_display}订单:")
                Log(f"类型: {trade_type} 币种: {coin} @ {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                if is_reverse:
                    Log(f"卖出交易所: {sell_ex} @ {_N(pending_sell_price, 6)}")
                    Log(f"买入交易所: {buy_ex} @ {_N(pending_buy_price, 6)}")
                else:
                    Log(f"买入交易所: {buy_ex} @ {_N(pending_buy_price, 6)}")
                    Log(f"卖出交易所: {sell_ex} @ {_N(pending_sell_price, 6)}")
                Log(f"数量: {_N(trade_amount, 6)}")
                Log(f"潜在利润: {_N(potential_profit, 6)} USDT ({_N(potential_profit / profit_data['cost'] * 100, 4)}%)")
                Log(f"超时时间: {timeout_time} ({order_timeout}秒后)")

                # 创建挂单，使用毫秒级时间戳
                order_id = f"pending_{coin}_{int(time.time() * 1000)}"
                pending_order = {
                    'id': order_id,
                    'time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': trade_type,
                    'coin': coin,
                    'buy_exchange': buy_ex,
                    'sell_exchange': sell_ex,
                    'amount': trade_amount,
                    'buy_price': pending_buy_price,
                    'sell_price': pending_sell_price,
                    'buy_fee_rate': buy_fee_rate,
                    'sell_fee_rate': sell_fee_rate,
                    'potential_profit': potential_profit,
                    'price_updates': 0,  # 价格调整次数
                    'status': 'PENDING',
                    'created_at': int(time.time())  # 添加创建时间戳，用于超时计算
                }

                # 添加到挂单列表
                account.add_pending_order(pending_order)
                Log(f"挂单已添加，订单ID: {order_id}")

                # 冻结资金
                if is_reverse:
                    # 反向挂单冻结币种
                    account.freeze_balance(coin.lower(), trade_amount, sell_ex)
                    Log(f"冻结{coin.upper()}: {_N(trade_amount, 6)} @ {sell_ex}")
                    
                    # 创建反向挂单记录
                    trade_record = TradeRecord.create_reverse_pending_record(
                        coin=coin.upper(),
                        exchange=sell_ex,
                        original_order_type="sell",
                        original_amount=trade_amount,
                        original_price=pending_sell_price,
                        original_order_id=order_id,
                        reverse_amount=0,  # 尚未撤销
                        reverse_price=pending_sell_price,
                        balance_before=account.get_balance(coin.lower(), sell_ex) + trade_amount,  # 加上已冻结的金额
                        usdt_before=account.get_balance('usdt', sell_ex),
                        status=TradeStatus.PENDING,
                        reason=""
                    )
                else:
                    # 正向挂单冻结USDT
                    account.freeze_balance('usdt', profit_data['cost'] + profit_data['buy_fee'], buy_ex)
                    Log(f"冻结资金: {_N(profit_data['cost'] + profit_data['buy_fee'], 6)} USDT @ {buy_ex}")
                    
                    # 创建正向挂单记录
                    trade_record = TradeRecord.create_pending_trade_record(
                        coin=coin.upper(),
                        exchange=buy_ex,
                        order_type="buy",
                        amount=trade_amount,
                        price=pending_buy_price,
                        estimated_fee=profit_data['buy_fee'],
                        balance_before=account.get_balance(coin.lower(), buy_ex),
                        usdt_before=account.get_balance('usdt', buy_ex) + profit_data['cost'] + profit_data['buy_fee'],  # 加上已冻结的金额
                        order_id=order_id,
                        status=TradeStatus.PENDING,
                        reason=""
                    )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)

                # 更新交易统计
                trade_type_for_stats = TradeType.REVERSE_PENDING if is_reverse else TradeType.PENDING_TRADE
                account.update_trade_stats(
                    trade_type_for_stats,
                    trade_amount,
                    0,  # 暂无盈亏
                    0,  # 暂无手续费
                    TradeStatus.PENDING
                )

        except Exception as e:
            Log(f"执行挂单套利时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
