from datetime import datetime
from typing import List, Tuple, Dict, Any, Union

from strategy.trade_type import TradeType
from strategy.trade_status import TradeStatus
from strategy.trade_record import TradeRecord
from strategy.trade_utils import _validate_params
from utils.calculations import _N
from utils.logger import Log
from utils.simulated_account import SimulatedAccount
from utils.config import get_exchange_fee


class ArbitrageOpportunity:
    def __init__(self, min_amount: float = 0.001, min_profit_rate: float = 0.1):
        self.min_amount = min_amount
        self.min_profit_rate = min_profit_rate

    async def _check_arbitrage_opportunity(
            self,
            coin: str,
            depths: Dict[str, Dict[str, Any]],
            account: SimulatedAccount,
            spot_exchanges: List[str],
            min_amount: float,
            min_basis: float,
            config: Dict[str, Any]
    ) -> Union[Tuple[str, str, float, float, float], None]:
        """检查套利机会"""
        try:
            # 参数验证
            if not _validate_params(coin, depths, account, spot_exchanges):
                Log("参数验证失败")
                return None

            coin = coin.upper()
            Log(f"===== 套利机会检查 - 币种: {coin} =====")

            # 获取所有交易所的买卖价格
            exchange_prices = []
            Log(f"各交易所价格信息:")
            for exchange in spot_exchanges:
                if exchange not in depths:
                    Log(f"  {exchange}: 不在深度数据中")
                    continue
                depth = depths[exchange]
                if not depth or not depth.get('asks') or not depth.get('bids'):
                    Log(f"  {exchange}: 深度数据不完整")
                    continue
                if not depth['asks'] or not depth['bids']:
                    Log(f"  {exchange}: 深度数据为空")
                    continue

                ask_price = depth['asks'][0][0]  # 最低卖价
                bid_price = depth['bids'][0][0]  # 最高买价
                ask_volume = depth['asks'][0][1]  # 卖单量
                bid_volume = depth['bids'][0][1]  # 买单量

                # 验证价格和数量的有效性
                if ask_price <= 0 or bid_price <= 0 or ask_volume < min_amount or bid_volume < min_amount:
                    Log(f"  {exchange}: 价格或数量无效 (卖价: {_N(ask_price, 6)}, 买价: {_N(bid_price, 6)}, 卖量: {_N(ask_volume, 6)}, 买量: {_N(bid_volume, 6)})")
                    continue

                exchange_prices.append((exchange, ask_price, bid_price, ask_volume, bid_volume))
                Log(f"  {exchange}: 卖价={_N(ask_price, 6)}, 买价={_N(bid_price, 6)}, 卖量={_N(ask_volume, 6)}, 买量={_N(bid_volume, 6)}")

            if len(exchange_prices) < 2:
                Log("有效交易所数量不足，无法进行套利")
                return None

            # 寻找最佳套利机会
            best_opportunity = None
            max_profit_rate = -float('inf')

            Log("\n开始检查交易所对之间的套利机会...")
            
            # 优化：预先计算手续费率，避免重复获取
            fee_rates = {}
            for ex, _, _, _, _ in exchange_prices:
                fee_rates[ex] = get_exchange_fee(ex, coin, False)  # taker费率

            for i, (ex1, ask1, bid1, _, _) in enumerate(exchange_prices):
                for j, (ex2, ask2, bid2, _, _) in enumerate(exchange_prices):
                    if i == j:
                        continue

                    # 检查账户余额
                    usdt_balance = account.get_balance('usdt', ex1)

                    if usdt_balance < min_amount * ask1:
                        Log(f"  {ex1} -> {ex2}: USDT余额不足 (需要: {_N(min_amount * ask1, 2)}, 实际: {_N(usdt_balance, 2)})")
                        continue

                    # 计算利润率
                    fee1 = fee_rates[ex1]
                    fee2 = fee_rates[ex2]

                    # 买入成本 = 买入价格 * (1 + 手续费率)
                    buy_cost = ask1 * (1 + fee1)
                    # 卖出收益 = 卖出价格 * (1 - 手续费率)
                    sell_revenue = bid2 * (1 - fee2)
                    # 利润率 = (卖出收益 - 买入成本) / 买入成本
                    profit_rate = (sell_revenue - buy_cost) / buy_cost

                    # 只记录有利可图的交易对
                    if profit_rate > 0:
                        Log(f"  {ex1} -> {ex2}: 利润率 = {_N(profit_rate * 100, 4)}% (最小要求: {_N(min_basis * 100, 4)}%)")
                        
                        if profit_rate > min_basis:
                            Log(f"  ✓ 符合条件: {ex1}买入@{_N(ask1, 6)} -> {ex2}卖出@{_N(bid2, 6)}")
                            Log(f"    买入成本: {_N(buy_cost, 6)}, 卖出收益: {_N(sell_revenue, 6)}")
                            Log(f"    USDT余额: {_N(usdt_balance, 2)}")
                            
                            if profit_rate > max_profit_rate:
                                max_profit_rate = profit_rate
                                best_opportunity = (ex1, ex2, ask1, bid2, min_amount)
                        else:
                            Log(f"  ✗ 利润率不足: {_N(profit_rate * 100, 4)}% < {_N(min_basis * 100, 4)}%")

            if best_opportunity:
                ex1, ex2, ask1, bid2, amount = best_opportunity
                Log(f"\n===== 发现最佳套利机会 =====")
                Log(f"买入交易所: {ex1} @ {_N(ask1, 6)}")
                Log(f"卖出交易所: {ex2} @ {_N(bid2, 6)}")
                Log(f"数量: {_N(amount, 6)}")
                Log(f"预期收益率: {_N(max_profit_rate * 100, 4)}%")
                Log(f"最小收益率要求: {_N(min_basis * 100, 4)}%")
                Log(f"===========================")
                return best_opportunity
            else:
                Log("\n未发现符合条件的套利机会")
                return None

        except Exception as e:
            Log(f"检查套利机会时发生错误: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return None


    async def execute_arbitrage_trade(
            self,
            coin: str,
            buy_exchange: str,
            sell_exchange: str,
            buy_price: float,
            sell_price: float,
            amount: float,
            account: SimulatedAccount,
            all_depths: Dict[str, Dict[str, Any]],
            config: Dict[str, Any],
            current_time: datetime
    ) -> None:
        try:
            Log(f"\n===== 执行套利交易 - {coin.upper()} =====")
            Log(f"买入: {buy_exchange} @ {_N(buy_price, 6)}")
            Log(f"卖出: {sell_exchange} @ {_N(sell_price, 6)}")
            Log(f"数量: {_N(amount, 6)}")
            
            # 获取交易所对象
            buy_ex = account.exchanges.get(buy_exchange)
            sell_ex = account.exchanges.get(sell_exchange)

            if not buy_ex or not sell_ex:
                Log(f"❌ 无法获取交易所对象: {buy_exchange} 或 {sell_exchange}")
                return

            # 检查交易所是否在深度数据中
            if buy_exchange not in all_depths or sell_exchange not in all_depths:
                Log(f"❌ 深度数据中没有{buy_exchange}或{sell_exchange}的信息，放弃交易")
                return

            # 获取最新深度数据
            buy_depth = all_depths[buy_exchange]
            sell_depth = all_depths[sell_exchange]

            # 获取最新价格
            current_buy_price = buy_depth['asks'][0][0]  # 买入使用卖一价
            current_sell_price = sell_depth['bids'][0][0]  # 卖出使用买一价

            # 放宽价格变动检查限制
            max_price_change = config.get('strategy', {}).get('MAX_PRICE_CHANGE', 0.008)  # 默认0.8%
            
            # 添加检查，防止除以零错误
            if buy_price > 0:
                buy_price_change = abs(current_buy_price - buy_price) / buy_price
            else:
                buy_price_change = 1.0  # 如果原始买入价格为0，设置变动为100%，确保不会执行交易

            if sell_price > 0:
                sell_price_change = abs(current_sell_price - sell_price) / sell_price
            else:
                sell_price_change = 1.0  # 如果原始卖出价格为0，设置变动为100%，确保不会执行交易

            if buy_price_change > max_price_change or sell_price_change > max_price_change:
                Log(f"❌ 价格变动过大，放弃交易")
                Log(f"  买入价格: {_N(buy_price, 6)} -> {_N(current_buy_price, 6)} (变动: {_N(buy_price_change * 100, 2)}%)")
                Log(f"  卖出价格: {_N(sell_price, 6)} -> {_N(current_sell_price, 6)} (变动: {_N(sell_price_change * 100, 2)}%)")
                Log(f"  最大允许变动: {_N(max_price_change * 100, 2)}%")

                # 创建失败的交易记录
                trade_record = TradeRecord.create_arbitrage_record(
                    coin=coin.upper(),
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    amount=amount,
                    buy_price=current_buy_price,
                    sell_price=current_sell_price,
                    buy_fee=0,
                    sell_fee=0,
                    profit=0,
                    status=TradeStatus.FAILED
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
                return

            # 检查是否仍有利润
            cost = amount * current_buy_price
            revenue = amount * current_sell_price

            # 获取手续费率
            buy_fee_rate = account.get_fee(buy_exchange, 'taker')
            sell_fee_rate = account.get_fee(sell_exchange, 'taker')

            buy_fee = cost * buy_fee_rate
            sell_fee = revenue * sell_fee_rate
            total_fees = buy_fee + sell_fee

            profit = revenue - cost - buy_fee - sell_fee
            # 添加检查，防止除以零错误
            if cost > 0:
                profit_rate = profit / cost
            else:
                profit_rate = 0  # 如果成本为0，设置利润率为0

            # 放宽利润检查限制
            min_profit_amount = config.get('strategy', {}).get('MIN_PROFIT_AMOUNT', 0.001)

            Log(f"交易计算:")
            Log(f"  买入成本: {_N(cost, 6)} USDT")
            Log(f"  卖出收益: {_N(revenue, 6)} USDT")
            Log(f"  买入手续费: {_N(buy_fee, 6)} USDT ({_N(buy_fee_rate * 100, 4)}%)")
            Log(f"  卖出手续费: {_N(sell_fee, 6)} USDT ({_N(sell_fee_rate * 100, 4)}%)")
            Log(f"  总手续费: {_N(total_fees, 6)} USDT")
            Log(f"  预期利润: {_N(profit, 6)} USDT ({_N(profit_rate * 100, 4)}%)")
            Log(f"  最小利润要求: {min_profit_amount} USDT")

            if profit <= min_profit_amount:
                Log(f"❌ 价格变动导致利润过低，放弃交易")

                # 创建失败的交易记录
                trade_record = TradeRecord.create_arbitrage_record(
                    coin=coin.upper(),
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    amount=amount,
                    buy_price=current_buy_price,
                    sell_price=current_sell_price,
                    buy_fee=buy_fee,
                    sell_fee=sell_fee,
                    profit=profit,
                    status=TradeStatus.FAILED
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
                return

            # 检查买入交易所USDT余额是否足够
            usdt_balance = account.get_balance('usdt', buy_exchange)

            if usdt_balance < cost + buy_fee:
                Log(f"❌ 买入交易所USDT余额不足，放弃交易")
                Log(f"  需要: {_N(cost + buy_fee, 6)} USDT")
                Log(f"  可用: {_N(usdt_balance, 6)} USDT")

                # 创建失败的交易记录
                trade_record = TradeRecord.create_arbitrage_record(
                    coin=coin.upper(),
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    amount=amount,
                    buy_price=current_buy_price,
                    sell_price=current_sell_price,
                    buy_fee=buy_fee,
                    sell_fee=sell_fee,
                    profit=profit,
                    status=TradeStatus.FAILED
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
                return

            # 执行交易
            Log(f"\n开始执行交易...")
            
            # 买入操作
            Log(f"1. 买入 {_N(amount, 6)} {coin.upper()} @ {buy_exchange}")
            buy_success = await account.spot_buy(
                buy_exchange, coin.lower(), amount,
                current_buy_price
            )

            if not buy_success:
                Log(f"❌ 买入操作失败，放弃整个交易")

                # 创建失败的交易记录
                trade_record = TradeRecord.create_arbitrage_record(
                    coin=coin.upper(),
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    amount=amount,
                    buy_price=current_buy_price,
                    sell_price=current_sell_price,
                    buy_fee=0,
                    sell_fee=0,
                    profit=0,
                    status=TradeStatus.FAILED
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
                return

            # 卖出操作
            Log(f"2. 卖出 {_N(amount, 6)} {coin.upper()} @ {sell_exchange}")
            sell_success = await account.spot_sell(
                sell_exchange, coin.lower(), amount,
                current_sell_price
            )

            if not sell_success:
                Log(f"❌ 卖出操作失败，但买入已完成，请手动处理")

                # 创建部分失败的交易记录
                trade_record = TradeRecord.create_arbitrage_record(
                    coin=coin.upper(),
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    amount=amount,
                    buy_price=current_buy_price,
                    sell_price=current_sell_price,
                    buy_fee=buy_fee,
                    sell_fee=0,
                    profit=-buy_fee,
                    status=TradeStatus.FAILED
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
                return

            Log(f"✅ 套利交易执行完成")
            Log(f"  买入: {buy_exchange} {_N(amount, 6)} {coin.upper()} @ {_N(current_buy_price, 6)}")
            Log(f"  卖出: {sell_exchange} {_N(amount, 6)} {coin.upper()} @ {_N(current_sell_price, 6)}")
            Log(f"  利润: {_N(profit, 6)} USDT ({_N(profit_rate * 100, 4)}%)")

            # 更新交易统计
            account.update_trade_stats(
                TradeType.ARBITRAGE,
                amount,
                profit,
                total_fees,
                TradeStatus.SUCCESS
            )

            # 创建成功的交易记录
            trade_record = TradeRecord.create_arbitrage_record(
                coin=coin.upper(),
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                amount=amount,
                buy_price=current_buy_price,
                sell_price=current_sell_price,
                buy_fee=buy_fee,
                sell_fee=sell_fee,
                profit=profit,
                status=TradeStatus.SUCCESS
            )
            
            # 记录交易记录到日志
            TradeRecord.log_trade_record(trade_record)
            
            # 将交易记录添加到账户
            account.add_trade_record(trade_record)
            Log(f"===========================")

        except Exception as e:
            Log(f"❌ 执行套利交易时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())

            # 记录异常情况
            try:
                trade_record = TradeRecord.create_arbitrage_record(
                    coin=coin.upper(),
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    amount=amount,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    buy_fee=0,
                    sell_fee=0,
                    profit=0,
                    status=TradeStatus.ERROR
                )
                
                # 记录交易记录到日志
                TradeRecord.log_trade_record(trade_record)
                
                # 将交易记录添加到账户
                account.add_trade_record(trade_record)
            except Exception as record_error:
                Log(f"记录交易异常时出错: {str(record_error)}")
