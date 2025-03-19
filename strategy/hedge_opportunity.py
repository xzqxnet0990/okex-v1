from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
import time

from strategy.trade_record import TradeRecord
from strategy.trade_status import TradeStatus
from strategy.trade_type import TradeType
from utils.calculations import _N
from utils.logger import Log
from utils.simulated_account import SimulatedAccount


# 辅助函数，用于验证参数
def _validate_params(coin, depths, account, spot_exchanges):
    """验证参数是否有效"""
    if not coin or not isinstance(coin, str):
        return False
    if not depths or not isinstance(depths, dict):
        return False
    if not account:
        return False
    if not spot_exchanges or not isinstance(spot_exchanges, list) or len(spot_exchanges) < 2:
        return False
    return True

class HedgeOpportunity:
    def __init__(self, min_value: float = 0.001):
        self.min_value = min_value
        self.max_deviation = 0.15  # 最大偏差阈值 15%
        # 缓存交易所费率
        self.fee_cache = {}

    async def check_cancelled_orders_for_hedge(self, coin: str, account: SimulatedAccount, 
                                              spot_exchanges: List[str], config: Dict[str, Any]) -> Optional[Tuple[str, str, float, float]]:
        """
        检查取消订单统计，对未成交挂单进行对冲操作
        
        Args:
            coin: 币种
            account: 账户对象
            spot_exchanges: 现货交易所列表
            config: 配置信息
            
        Returns:
            Optional[Tuple[str, str, float, float]]: 对冲操作信息，格式为 (操作类型, 交易所, 价格, 数量)
        """
        try:
            # 获取币种的取消订单统计
            cancelled_stats = account.get_cancelled_order_stats(coin)
            if not cancelled_stats or not cancelled_stats.get('total_count', 0):
                return None
                
            Log(f"===== 对冲操作检查 - 币种: {coin.upper()} =====")
            Log(f"取消订单总数: {cancelled_stats.get('total_count', 0)}")
            Log(f"取消订单总量: {_N(cancelled_stats.get('total_amount', 0), 6)}")
            
            # 检查是否需要对冲
            # 设置阈值：当取消订单币种数量超过一定值时才考虑对冲
            min_cancel_amount = config.get('strategy', {}).get('HEDGE', {}).get('MIN_CANCEL_AMOUNT', 0.001)
            if cancelled_stats.get('total_amount', 0) < min_cancel_amount:
                Log(f"✗ 取消订单币种数量 {_N(cancelled_stats.get('total_amount', 0), 6)} 小于阈值 {_N(min_cancel_amount, 6)}，不进行对冲")
                return None
                
            # 分析交易所对数据，找出最频繁取消的交易所对
            exchanges_stats = cancelled_stats.get('exchanges', {})
            if not exchanges_stats:
                Log(f"✗ 没有交易所对数据，无法进行对冲")
                return None
                
            # 找出取消数量最多的交易所对
            max_cancel_pair = None
            max_cancel_amount = 0
            
            Log(f"\n交易所对取消统计:")
            for pair, stats in exchanges_stats.items():
                cancel_amount = stats.get('amount', 0)
                cancel_count = stats.get('count', 0)
                Log(f"  {pair}: {cancel_count} 次, {_N(cancel_amount, 6)} {coin.upper()}")
                if cancel_amount > max_cancel_amount:
                    max_cancel_amount = cancel_amount
                    max_cancel_pair = pair
                    
            if not max_cancel_pair:
                Log(f"✗ 未找到最多取消数量的交易所对")
                return None
                
            # 解析交易所对
            buy_ex, sell_ex = max_cancel_pair.split("->")
            
            Log(f"\n最多取消数量的交易所对: {max_cancel_pair}, 取消数量: {_N(max_cancel_amount, 6)} {coin.upper()}")
            
            # 检查这些交易所的持仓情况
            buy_position = account.get_unhedged_position(coin, buy_ex)
            sell_position = account.get_unhedged_position(coin, sell_ex)
            
            Log(f"持仓情况:")
            Log(f"  {buy_ex}: {_N(buy_position, 6)} {coin.upper()}")
            Log(f"  {sell_ex}: {_N(sell_position, 6)} {coin.upper()}")
            
            # 计算持仓差异
            position_diff = abs(buy_position - sell_position)
            avg_position = (buy_position + sell_position) / 2
            
            if avg_position <= 0:
                Log(f"✗ 平均持仓为零或负值，无法计算偏差")
                return None
                
            position_diff_percent = position_diff / avg_position * 100
            Log(f"持仓差异: {_N(position_diff, 6)} {coin.upper()} ({_N(position_diff_percent, 2)}%)")
            
            # 如果持仓差异超过阈值，进行对冲
            hedge_threshold = config.get('strategy', {}).get('HEDGE', {}).get('POSITION_DIFF_THRESHOLD', 0.1)
            hedge_threshold_percent = hedge_threshold * 100
            
            if position_diff / avg_position > hedge_threshold:
                Log(f"✓ 持仓差异 {_N(position_diff_percent, 2)}% 超过阈值 {_N(hedge_threshold_percent, 2)}%，需要对冲")
                
                # 获取当前市场价格估计值
                # 使用第一个交易所获取价格估计
                first_exchange = spot_exchanges[0] if spot_exchanges else None
                if first_exchange:
                    estimated_price = await account._get_estimated_price(coin, first_exchange)
                    Log(f"估计的 {coin.upper()} 价格 (来自 {first_exchange}): {_N(estimated_price, 6)} USDT")
                else:
                    Log(f"无法获取价格估计，没有可用的交易所")
                    return None
                
                # 确定对冲方向
                if buy_position > sell_position:
                    # 买入交易所持仓多，需要在买入交易所卖出或在卖出交易所买入
                    return self._determine_hedge_direction(
                        coin, account, buy_ex, sell_ex, buy_position, sell_position, 
                        position_diff, estimated_price, config
                    )
                else:
                    # 卖出交易所持仓多，需要在卖出交易所卖出或在买入交易所买入
                    return self._determine_hedge_direction(
                        coin, account, sell_ex, buy_ex, sell_position, buy_position, 
                        position_diff, estimated_price, config
                    )
            else:
                Log(f"✗ 持仓差异 {_N(position_diff_percent, 2)}% 在阈值 {_N(hedge_threshold_percent, 2)}% 范围内，无需对冲")
                return None
                
        except Exception as e:
            Log(f"❌ 检查取消订单统计进行对冲操作时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return None
    
    def _determine_hedge_direction(self, coin: str, account: SimulatedAccount, 
                                  high_ex: str, low_ex: str, high_position: float, low_position: float,
                                  position_diff: float, estimated_price: float, config: Dict[str, Any]) -> Optional[Tuple[str, str, float, float]]:
        """确定对冲方向"""
        # 高持仓交易所卖出或低持仓交易所买入
        # 根据交易所余额情况决定对冲方向
        usdt_balance_low_ex = account.get_balance('usdt', low_ex)
        min_usdt_required = position_diff * estimated_price * 1.05  # 预估所需USDT，加5%作为缓冲
        
        Log(f"\n对冲方向分析:")
        Log(f"  {low_ex} USDT余额: {_N(usdt_balance_low_ex, 2)}")
        Log(f"  所需USDT估计: {_N(min_usdt_required, 2)}")
        
        if usdt_balance_low_ex >= min_usdt_required:
            # 低持仓交易所有足够的USDT，可以在低持仓交易所买入
            hedge_amount = min(position_diff, high_position * 0.5)  # 最多对冲一半持仓
            Log(f"✓ 选择在 {low_ex} 买入 {_N(hedge_amount, 6)} {coin.upper()} 进行对冲")
            return (TradeType.HEDGE_BUY, low_ex, estimated_price, hedge_amount)
        else:
            # 低持仓交易所USDT不足，在高持仓交易所卖出
            hedge_amount = min(position_diff, high_position * 0.5)  # 最多对冲一半持仓
            Log(f"✓ 选择在 {high_ex} 卖出 {_N(hedge_amount, 6)} {coin.upper()} 进行对冲")
            return (TradeType.HEDGE_SELL, high_ex, estimated_price, hedge_amount)
            
    async def hedge_cancelled_orders(self, 
                                    account: SimulatedAccount,
                                    coin: str,
                                    spot_exchanges: List[str],
                                    all_depths: Dict[str, Dict[str, Dict[str, Any]]],
                                    current_time: datetime,
                                    config: Dict[str, Any]) -> bool:
        """
        对取消订单进行对冲操作
        
        Args:
            account: 账户对象
            coin: 币种
            spot_exchanges: 现货交易所列表
            all_depths: 所有深度数据
            current_time: 当前时间
            config: 配置信息
            
        Returns:
            bool: 是否成功执行对冲操作
        """
        try:
            # 检查是否需要对冲
            hedge_info = await self.check_cancelled_orders_for_hedge(coin, account, spot_exchanges, config)
            if not hedge_info:
                return False
                
            trade_type, exchange, price, amount = hedge_info
            
            # 执行对冲交易
            is_buy = trade_type == TradeType.HEDGE_BUY
            
            Log(f"\n===== 执行对冲交易 - {coin.upper()} =====")
            Log(f"交易所: {exchange}")
            Log(f"操作: {'买入' if is_buy else '卖出'}")
            Log(f"数量: {_N(amount, 6)}")
            Log(f"估计价格: {_N(price, 6)}")
            
            # 记录对冲前的持仓情况
            before_position = account.get_unhedged_position(coin, exchange)
            Log(f"对冲前持仓: {_N(before_position, 6)} {coin.upper()}")
            
            # 记录对冲前的USDT余额
            before_usdt = account.get_balance('usdt', exchange)
            Log(f"对冲前USDT余额: {_N(before_usdt, 2)}")
            
            # 执行对冲交易
            await self.execute_hedge_trade(account, coin, exchange, amount, is_buy, all_depths, current_time)
            
            # 检查对冲后的持仓情况，确认交易是否成功
            after_position = account.get_unhedged_position(coin, exchange)
            Log(f"对冲后持仓: {_N(after_position, 6)} {coin.upper()}")
            
            # 记录对冲后的USDT余额
            after_usdt = account.get_balance('usdt', exchange)
            Log(f"对冲后USDT余额: {_N(after_usdt, 2)}")
            
            # 如果持仓变化，说明对冲成功，重置该币种的取消订单统计
            hedge_success = False
            
            if is_buy:
                # 买入操作，持仓应该增加，USDT应该减少
                position_change = after_position - before_position
                usdt_change = after_usdt - before_usdt
                
                if position_change > 0 and usdt_change < 0:
                    hedge_success = True
                    Log(f"✅ 对冲买入成功:")
                    Log(f"  {coin.upper()} 持仓增加: {_N(position_change, 6)}")
                    Log(f"  USDT减少: {_N(abs(usdt_change), 2)}")
                    
                    # 创建成功的对冲买入记录
                    trade_record = TradeRecord.create_hedge_buy_record(
                        coin=coin,
                        exchange=exchange,
                        amount=amount,
                        price=price,
                        fee=abs(usdt_change) - (amount * price),  # 估算手续费
                        balance_before=before_position,
                        balance_after=after_position,
                        usdt_before=before_usdt,
                        usdt_after=after_usdt,
                        status=TradeStatus.SUCCESS
                    )
                    
                    # 记录交易记录到日志
                    TradeRecord.log_trade_record(trade_record)
                    
                    # 将交易记录添加到账户
                    account.add_trade_record(trade_record)
            else:
                # 卖出操作，持仓应该减少，USDT应该增加
                position_change = before_position - after_position
                usdt_change = after_usdt - before_usdt
                
                if position_change > 0 and usdt_change > 0:
                    hedge_success = True
                    Log(f"✅ 对冲卖出成功:")
                    Log(f"  {coin.upper()} 持仓减少: {_N(position_change, 6)}")
                    Log(f"  USDT增加: {_N(usdt_change, 2)}")
                    
                    # 创建成功的对冲卖出记录
                    trade_record = TradeRecord.create_hedge_sell_record(
                        coin=coin,
                        exchange=exchange,
                        amount=amount,
                        price=price,
                        fee=amount * price - usdt_change,  # 估算手续费
                        balance_before=before_position,
                        balance_after=after_position,
                        usdt_before=before_usdt,
                        usdt_after=after_usdt,
                        status=TradeStatus.SUCCESS
                    )
                    
                    # 记录交易记录到日志
                    TradeRecord.log_trade_record(trade_record)
                    
                    # 将交易记录添加到账户
                    account.add_trade_record(trade_record)
            
            if hedge_success:
                Log(f"对冲操作成功，重置 {coin.upper()} 的取消订单统计")
                account.reset_cancelled_order_stats(coin)
                return True
            else:
                Log(f"❌ 对冲操作可能未成功，持仓或USDT余额变化不符合预期")
                return False
            
        except Exception as e:
            Log(f"❌ 对取消订单进行对冲操作时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return False

    async def execute_hedge_trade(
            self,
            account: SimulatedAccount,
            coin: str,
            spot_ex: str,
            trade_amount: float,
            is_buy: bool,
            all_depths: Dict[str, Dict[str, Dict[str, Any]]],
            current_time: datetime
    ) -> None:
        """执行对冲交易"""
        try:
            if trade_amount <= 0:
                Log(f"❌ 交易数量必须大于0: {trade_amount}")
                return

            # 获取深度数据
            if coin not in all_depths or spot_ex not in all_depths[coin]:
                Log(f"❌ 无法获取 {spot_ex} 的 {coin} 深度数据")
                return

            depth = all_depths[coin][spot_ex]
            if not depth or 'bids' not in depth or 'asks' not in depth or not depth['bids'] or not depth['asks']:
                Log(f"❌ {spot_ex} 的 {coin} 深度数据不完整")
                return

            # 获取价格
            if is_buy:
                # 买入使用卖一价
                price = depth['asks'][0][0]
                
                # 记录交易前的余额
                balance_before = account.get_balance(coin.lower(), spot_ex)
                usdt_before = account.get_balance('usdt', spot_ex)
                
                # 获取手续费率
                if spot_ex not in self.fee_cache:
                    self.fee_cache[spot_ex] = account.get_fee(spot_ex, coin)
                fee_rate = self.fee_cache[spot_ex]
                
                # 计算所需的USDT
                cost = trade_amount * price
                fee = cost * fee_rate
                total_cost = cost + fee

                # 检查USDT余额是否足够
                if account.get_balance('usdt', spot_ex) >= total_cost:
                    Log(f"\n执行买入交易:")
                    Log(f"买入 {_N(trade_amount, 6)} {coin.upper()} @ {_N(price, 6)} on {spot_ex}")
                    Log(f"预计成本: {_N(cost, 2)} USDT")
                    Log(f"预计手续费: {_N(fee, 2)} USDT ({_N(fee_rate * 100, 4)}%)")
                    Log(f"总成本: {_N(total_cost, 2)} USDT")
                    
                    # 执行买入
                    result = await account.spot_buy(spot_ex, coin.lower(), trade_amount, price)
                    
                    # 记录交易后的余额
                    balance_after = account.get_balance(coin.lower(), spot_ex)
                    usdt_after = account.get_balance('usdt', spot_ex)
                    
                    if result:
                        # 创建交易记录
                        trade_record = TradeRecord.create_hedge_buy_record(
                            coin=coin,
                            exchange=spot_ex,
                            amount=trade_amount,
                            price=price,
                            fee=fee,
                            balance_before=balance_before,
                            balance_after=balance_after,
                            usdt_before=usdt_before,
                            usdt_after=usdt_after,
                            status=TradeStatus.SUCCESS
                        )
                        
                        # 记录交易记录到日志
                        TradeRecord.log_trade_record(trade_record)
                        
                        # 将交易记录添加到账户
                        account.add_trade_record(trade_record)

                        Log(f"✅ 对冲买入成功")
                        Log(f"更新后的持仓: {_N(account.get_unhedged_position(coin, spot_ex), 6)} {coin.upper()}")
                        Log(f"更新后的USDT余额: {_N(account.get_balance('usdt', spot_ex), 2)}")
                    else:
                        Log(f"❌ 对冲买入失败: {coin} @ {spot_ex}")

                        # 创建失败的交易记录
                        trade_record = TradeRecord.create_hedge_buy_record(
                            coin=coin,
                            exchange=spot_ex,
                            amount=trade_amount,
                            price=price,
                            fee=0,
                            balance_before=balance_before,
                            balance_after=balance_after,
                            usdt_before=usdt_before,
                            usdt_after=usdt_after,
                            status=TradeStatus.FAILED,
                            reason="买入操作执行失败"
                        )
                        
                        # 记录交易记录到日志
                        TradeRecord.log_trade_record(trade_record)
                        
                        # 将交易记录添加到账户
                        account.add_trade_record(trade_record)
                else:
                    Log(f"❌ USDT余额不足，无法执行对冲买入:")
                    Log(f"  需要: {_N(total_cost, 2)} USDT")
                    Log(f"  可用: {_N(account.get_balance('usdt', spot_ex), 2)} USDT")
                    
                    # 创建失败的交易记录（USDT余额不足）
                    trade_record = TradeRecord.create_hedge_buy_record(
                        coin=coin,
                        exchange=spot_ex,
                        amount=trade_amount,
                        price=price,
                        fee=0,
                        balance_before=balance_before,
                        balance_after=balance_before,  # 余额未变
                        usdt_before=usdt_before,
                        usdt_after=usdt_before,  # USDT未变
                        status=TradeStatus.FAILED,
                        reason=f"USDT余额不足，需要 {_N(total_cost, 2)} USDT，但只有 {_N(usdt_before, 2)} USDT"
                    )
                    
                    # 记录交易记录到日志
                    TradeRecord.log_trade_record(trade_record)
                    
                    # 将交易记录添加到账户
                    account.add_trade_record(trade_record)
            else:
                # 卖出使用买一价
                price = depth['bids'][0][0]
                
                # 记录交易前的余额
                balance_before = account.get_balance(coin.lower(), spot_ex)
                usdt_before = account.get_balance('usdt', spot_ex)
                
                # 获取手续费率
                if spot_ex not in self.fee_cache:
                    self.fee_cache[spot_ex] = account.get_fee(spot_ex, coin)
                fee_rate = self.fee_cache[spot_ex]
                
                # 计算预期收益
                value = trade_amount * price
                fee = value * fee_rate
                net_value = value - fee
                
                # 检查币种余额是否足够
                if account.get_balance(coin.lower(), spot_ex) >= trade_amount:
                    Log(f"\n执行卖出交易:")
                    Log(f"卖出 {_N(trade_amount, 6)} {coin.upper()} @ {_N(price, 6)} on {spot_ex}")
                    Log(f"预计收益: {_N(value, 2)} USDT")
                    Log(f"预计手续费: {_N(fee, 2)} USDT ({_N(fee_rate * 100, 4)}%)")
                    Log(f"净收益: {_N(net_value, 2)} USDT")
                    
                    # 执行卖出
                    result = await account.spot_sell(spot_ex, coin.lower(), trade_amount, price)
                    
                    # 记录交易后的余额
                    balance_after = account.get_balance(coin.lower(), spot_ex)
                    usdt_after = account.get_balance('usdt', spot_ex)
                    
                    if result:
                        # 创建交易记录
                        trade_record = TradeRecord.create_hedge_sell_record(
                            coin=coin,
                            exchange=spot_ex,
                            amount=trade_amount,
                            price=price,
                            fee=fee,
                            balance_before=balance_before,
                            balance_after=balance_after,
                            usdt_before=usdt_before,
                            usdt_after=usdt_after,
                            status=TradeStatus.SUCCESS
                        )
                        
                        # 记录交易记录到日志
                        TradeRecord.log_trade_record(trade_record)
                        
                        # 将交易记录添加到账户
                        account.add_trade_record(trade_record)

                        Log(f"✅ 对冲卖出成功")
                        Log(f"更新后的持仓: {_N(account.get_unhedged_position(coin, spot_ex), 6)} {coin.upper()}")
                        Log(f"更新后的USDT余额: {_N(account.get_balance('usdt', spot_ex), 2)}")
                    else:
                        Log(f"❌ 对冲卖出失败: {coin} @ {spot_ex}")

                        # 创建失败的交易记录
                        trade_record = TradeRecord.create_hedge_sell_record(
                            coin=coin,
                            exchange=spot_ex,
                            amount=trade_amount,
                            price=price,
                            fee=0,
                            balance_before=balance_before,
                            balance_after=balance_after,
                            usdt_before=usdt_before,
                            usdt_after=usdt_after,
                            status=TradeStatus.FAILED,
                            reason="卖出操作执行失败"
                        )
                        
                        # 记录交易记录到日志
                        TradeRecord.log_trade_record(trade_record)
                        
                        # 将交易记录添加到账户
                        account.add_trade_record(trade_record)
                else:
                    Log(f"❌ 币种余额不足，无法执行对冲卖出:")
                    Log(f"  需要: {_N(trade_amount, 6)} {coin.upper()}")
                    Log(f"  可用: {_N(account.get_balance(coin.lower(), spot_ex), 6)} {coin.upper()}")
                    
                    # 创建失败的交易记录（币种余额不足）
                    trade_record = TradeRecord.create_hedge_sell_record(
                        coin=coin,
                        exchange=spot_ex,
                        amount=trade_amount,
                        price=price,
                        fee=0,
                        balance_before=balance_before,
                        balance_after=balance_before,  # 余额未变
                        usdt_before=usdt_before,
                        usdt_after=usdt_before,  # USDT未变
                        status=TradeStatus.FAILED,
                        reason=f"币种余额不足，需要 {_N(trade_amount, 6)} {coin}，但只有 {_N(balance_before, 6)} {coin}"
                    )
                    
                    # 记录交易记录到日志
                    TradeRecord.log_trade_record(trade_record)
                    
                    # 将交易记录添加到账户
                    account.add_trade_record(trade_record)

        except Exception as e:
            Log(f"❌ 执行对冲交易时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
