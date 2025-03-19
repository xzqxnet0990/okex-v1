from datetime import datetime
from typing import List, Tuple, Dict, Any, Union

from strategy.trade_record import TradeRecord
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


class BalanceOpportunity:
    """余额调整机会类"""
    
    def __init__(self):
        """初始化"""
        # 设置默认的最大偏差
        self.max_deviation = 0.2  # 默认20%
        # 设置默认的最小偏差阈值
        self.min_deviation = 0.05  # 默认5%
        # 设置默认的利润阈值
        self.profit_threshold = 0.0001  # 默认0.01%
        # 记录上次余额调整的时间
        self.last_balance_time = None
        # 缓存交易所费率
        self.fee_cache = {}

    async def _check_balance_opportunity(
            self,
            coin: str,
            depths: Dict[str, Dict[str, Any]],
            account: SimulatedAccount,
            spot_exchanges: List[str],
            min_amount: float,
            max_deviation: float,
            config: Dict[str, Any]
    ) -> Union[Tuple[str, float, float, str, str], None]:
        """检查余额调整机会"""

        if not _validate_params(coin, depths, account, spot_exchanges):
            Log("参数验证失败")
            return None

        if len(spot_exchanges) < 2:
            Log("交易所数量不足")
            return None

        coin = coin.upper()
        Log(f"===== 均衡操作检查 - 币种: {coin} =====")

        # 从配置中获取不平衡性阈值和利润阈值
        min_deviation = config.get('strategy', {}).get('BALANCE', {}).get('MIN_DEVIATION', self.min_deviation)
        profit_threshold = config.get('strategy', {}).get('BALANCE', {}).get('PROFIT_THRESHOLD', self.profit_threshold)
        
        Log(f"不平衡性阈值: {_N(min_deviation * 100, 2)}%, 利润阈值: {_N(profit_threshold * 100, 4)}%")

        # 计算平均持仓
        total_balance = 0
        valid_exchanges = []
        exchange_balances = {}
        exchange_prices = {}  # 存储每个交易所的买卖价格

        # 预先获取所有交易所的费率
        for exchange in spot_exchanges:
            if exchange not in self.fee_cache:
                self.fee_cache[exchange] = account.get_fee(exchange, coin)

        Log(f"\n各交易所持仓情况:")
        for exchange in spot_exchanges:
            if exchange not in depths:
                Log(f"  {exchange}: 不在深度数据中")
                continue
                
            # 获取交易所深度数据
            depth = depths[exchange]
            if not depth or 'bids' not in depth or 'asks' not in depth or not depth['bids'] or not depth['asks']:
                Log(f"  {exchange}: 深度数据不完整")
                continue
                
            # 存储交易所的买卖价格
            bid_price = depth['bids'][0][0]  # 买一价
            ask_price = depth['asks'][0][0]  # 卖一价
            exchange_prices[exchange] = {'bid': bid_price, 'ask': ask_price}
            
            balance = account.get_balance(coin.lower(), exchange)
            Log(f"  {exchange}: {_N(balance, 6)} {coin}, 买价: {_N(bid_price, 6)}, 卖价: {_N(ask_price, 6)}")
            
            if balance > 0:
                total_balance += balance
                valid_exchanges.append(exchange)
                exchange_balances[exchange] = balance

        if len(valid_exchanges) < 2:
            Log("有效交易所数量不足，至少需要两个交易所有持仓")
            return None

        avg_balance = total_balance / len(valid_exchanges)
        Log(f"\n平均持仓: {_N(avg_balance, 6)} {coin}")

        # 寻找最大偏差的交易所
        max_positive_dev = -float('inf')
        max_negative_dev = float('inf')
        source_ex = None
        target_ex = None

        Log(f"\n各交易所偏差情况:")
        for ex in valid_exchanges:
            deviation = (exchange_balances[ex] - avg_balance) / avg_balance
            deviation_percent = deviation * 100
            
            # 使用符号标记偏差方向
            direction = "↑" if deviation > 0 else "↓"
            Log(f"  {ex}: {direction} {_N(abs(deviation_percent), 4)}%")

            if deviation > 0 and deviation > max_positive_dev:
                max_positive_dev = deviation
                source_ex = ex
            elif deviation < 0 and deviation < max_negative_dev:
                max_negative_dev = deviation
                target_ex = ex

        if not source_ex or not target_ex:
            Log("\n未找到合适的源交易所或目标交易所")
            
            # 如果所有交易所偏差都是同一方向，选择偏差最大和最小的
            if not source_ex and not target_ex:
                # 重新遍历，找出偏差最大和最小的交易所
                max_dev = -float('inf')
                min_dev = float('inf')
                max_dev_ex = None
                min_dev_ex = None

                for ex in valid_exchanges:
                    deviation = (exchange_balances[ex] - avg_balance) / avg_balance
                    if deviation > max_dev:
                        max_dev = deviation
                        max_dev_ex = ex
                    if deviation < min_dev:
                        min_dev = deviation
                        min_dev_ex = ex

                if max_dev_ex and min_dev_ex and max_dev_ex != min_dev_ex:
                    source_ex = max_dev_ex
                    target_ex = min_dev_ex
                    Log(f"所有偏差同向，选择偏差最大的 {source_ex} 和最小的 {target_ex}")

            if not source_ex or not target_ex:
                Log("无法确定源交易所和目标交易所，放弃均衡操作")
                return None

        Log(f"\n最大偏差交易所: {source_ex} (偏高 ↑), {target_ex} (偏低 ↓)")
        max_dev = max(abs(max_positive_dev), abs(max_negative_dev))
        Log(f"最大偏差: {_N(abs(max_dev) * 100, 4)}%, 阈值: {_N(max_deviation * 100, 4)}%")

        # 检查不平衡性是否达到最小阈值
        if abs(max_dev) < min_deviation:
            Log(f"✗ 不平衡性 {_N(abs(max_dev) * 100, 4)}% 低于最小阈值 {_N(min_deviation * 100, 4)}%，不进行均衡操作")
            return None
            
        # 检查不平衡性是否超过最大阈值
        if abs(max_dev) > max_deviation:
            Log(f"✓ 不平衡性 {_N(abs(max_dev) * 100, 4)}% 超过最大阈值 {_N(max_deviation * 100, 4)}%，需要进行均衡操作")
        else:
            # 如果不平衡性在最小和最大阈值之间，检查是否有盈利机会
            if source_ex not in exchange_prices or target_ex not in exchange_prices:
                Log(f"✗ 无法获取交易所价格信息，放弃均衡操作")
                return None
                
            source_bid = exchange_prices[source_ex]['bid']  # 源交易所买一价
            target_ask = exchange_prices[target_ex]['ask']  # 目标交易所卖一价
            
            # 计算价差比例
            price_diff_ratio = (source_bid - target_ask) / target_ask
            Log(f"价差比例: {_N(price_diff_ratio * 100, 4)}%")
            
            # 获取手续费率
            source_fee_rate = self.fee_cache.get(source_ex, account.get_fee(source_ex, coin))
            target_fee_rate = self.fee_cache.get(target_ex, account.get_fee(target_ex, coin))
            total_fee_rate = source_fee_rate + target_fee_rate
            Log(f"总手续费率: {_N(total_fee_rate * 100, 4)}%")
            
            # 计算净利润比例 = 价差比例 - 总手续费率
            net_profit_ratio = price_diff_ratio - total_fee_rate
            Log(f"净利润比例: {_N(net_profit_ratio * 100, 4)}%")
            
            # 检查净利润是否达到阈值
            if net_profit_ratio < profit_threshold:
                Log(f"✗ 净利润比例 {_N(net_profit_ratio * 100, 4)}% 低于阈值 {_N(profit_threshold * 100, 4)}%，不进行均衡操作")
                return None
            else:
                Log(f"✓ 净利润比例 {_N(net_profit_ratio * 100, 4)}% 达到阈值，可以进行均衡操作")

        # 计算转移数量
        # 根据不平衡程度动态调整转移数量，不平衡越大，转移数量越大
        imbalance_factor = min(1.0, abs(max_dev) / max_deviation)  # 不平衡因子，范围 [0, 1]
        max_transfer_amount = config.get('strategy', {}).get('BALANCE', {}).get('MAX_TRANSFER_AMOUNT', min_amount * 10)
        transfer_amount = min_amount + (max_transfer_amount - min_amount) * imbalance_factor
        
        # 确保转移数量不超过源交易所的余额
        source_balance = exchange_balances[source_ex]
        transfer_amount = min(transfer_amount, source_balance * 0.5)  # 最多转移源交易所余额的50%
        
        # 获取价格
        try:
            source_price = exchange_prices[source_ex]['bid']
            target_price = exchange_prices[target_ex]['ask']
        except (KeyError, IndexError):
            Log("✗ 获取价格失败")
            return None

        # 如果不平衡性超过最大阈值，则不需要检查利润，直接进行均衡操作
        # 确保 net_profit_ratio 变量在所有情况下都有定义
        if not locals().get('net_profit_ratio'):
            # 计算净利润比例
            source_bid = exchange_prices[source_ex]['bid']  # 源交易所买一价
            target_ask = exchange_prices[target_ex]['ask']  # 目标交易所卖一价
            price_diff_ratio = (source_bid - target_ask) / target_ask
            source_fee_rate = self.fee_cache.get(source_ex, account.get_fee(source_ex, coin))
            target_fee_rate = self.fee_cache.get(target_ex, account.get_fee(target_ex, coin))
            total_fee_rate = source_fee_rate + target_fee_rate
            net_profit_ratio = price_diff_ratio - total_fee_rate

        Log(f"\n===== 发现均衡操作机会 =====")
        Log(f"币种: {coin}")
        Log(f"源交易所: {source_ex} @ {_N(source_price, 6)}")
        Log(f"目标交易所: {target_ex} @ {_N(target_price, 6)}")
        Log(f"调整数量: {_N(transfer_amount, 6)}")
        Log(f"不平衡性: {_N(max_dev * 100, 4)}%")
        Log(f"预计利润: {_N(net_profit_ratio * 100, 4)}%")
        Log(f"=============================")

        # 修改返回值，确保返回的元组包含正确的元素顺序：operation_type, price, amount, source_exchange, target_exchange
        return TradeType.BALANCE_OPERATION, source_price, transfer_amount, source_ex, target_ex

    async def execute_balance_trade(
            self,
            coin: str,
            amount: float,
            source_exchange: str = None,
            target_exchange: str = None,
            account: SimulatedAccount = None,
            depths: Dict[str, Dict[str, Any]] = None,
            supported_exchanges: List[str] = None,
            current_time: datetime = None,
            config: Dict[str, Any] = None
    ) -> bool:
        """执行余额调整交易"""
        try:
            coin = coin.upper()
            Log(f"\n===== 执行均衡交易 - {coin} =====")
            Log(f"源交易所: {source_exchange}")
            Log(f"目标交易所: {target_exchange}")
            Log(f"数量: {_N(amount, 6)}")

            # 记录交易前的余额
            source_balance_before = account.get_balance(coin.lower(), source_exchange)
            target_balance_before = account.get_balance(coin.lower(), target_exchange)
            Log(f"交易前余额 - 源交易所: {_N(source_balance_before, 6)}, 目标交易所: {_N(target_balance_before, 6)}")

            # 获取手续费率
            source_fee_rate = self.fee_cache.get(source_exchange, account.get_fee(source_exchange, coin))
            target_fee_rate = self.fee_cache.get(target_exchange, account.get_fee(target_exchange, coin))
            self.fee_cache[source_exchange] = source_fee_rate
            self.fee_cache[target_exchange] = target_fee_rate
            
            Log(f"手续费率 - 源交易所: {_N(source_fee_rate * 100, 4)}%, 目标交易所: {_N(target_fee_rate * 100, 4)}%")

            # 如果没有提供价格，尝试从深度数据获取
            if depths:
                try:
                    source_depth = depths.get(source_exchange, {})
                    if source_depth and 'bids' in source_depth and source_depth['bids']:
                        price = source_depth['bids'][0][0]  # 使用源交易所的买一价
                        Log(f"从深度数据获取价格: {_N(price, 6)}")
                except Exception as e:
                    Log(f"从深度数据获取价格失败: {str(e)}")
                    # 尝试获取市场价格
                    try:
                        price = await account._get_estimated_price(coin, source_exchange)
                        Log(f"使用市场价格: {_N(price, 6)}")
                    except Exception as e2:
                        Log(f"获取市场价格失败: {str(e2)}")
                        return False

            # 计算成本和收益
            sell_amount = amount
            sell_value = sell_amount * price
            sell_fee = sell_value * source_fee_rate
            sell_net = sell_value - sell_fee

            buy_value = sell_net
            buy_fee = buy_value * target_fee_rate
            buy_amount = (buy_value - buy_fee) / price

            # 获取当前市场价格
            expected_profit_ratio = None
            expected_profit = None
            try:
                current_source_price = await account._get_estimated_price(coin, source_exchange)
                current_target_price = await account._get_estimated_price(coin, target_exchange)
                
                # 确保在使用价格前已经正确地等待协程完成
                Log(f"当前市场价格 - 源交易所: {_N(current_source_price, 6)}, 目标交易所: {_N(current_target_price, 6)}")
                
                # 计算预期利润
                price_diff = current_source_price - current_target_price
                price_diff_ratio = price_diff / current_target_price
                total_fee_rate = source_fee_rate + target_fee_rate
                expected_profit_ratio = price_diff_ratio - total_fee_rate
                expected_profit = sell_value * expected_profit_ratio
                
                Log(f"预期利润率: {_N(expected_profit_ratio * 100, 4)}%, 预期利润: {_N(expected_profit, 6)} USDT")
                
                # 如果预期利润为负，可以考虑放弃交易
                min_profit_threshold = config.get('strategy', {}).get('BALANCE', {}).get('MIN_PROFIT', 0)
                if expected_profit < min_profit_threshold:
                    Log(f"❌ 预期利润 {_N(expected_profit, 6)} USDT 低于最小阈值 {_N(min_profit_threshold, 6)} USDT，放弃交易")
                    return False
            except Exception as e:
                Log(f"获取市场价格失败: {str(e)}")
                # 继续执行，因为这只是额外的检查

            # 执行交易
            Log(f"\n开始执行交易...")
            Log(f"1. 在 {source_exchange} 卖出 {_N(sell_amount, 6)} {coin} @ {_N(price, 6)}")
            sell_result = await account.spot_sell(source_exchange, coin.lower(), sell_amount, price)
            if not sell_result:
                Log(f"❌ 在 {source_exchange} 卖出失败")
                return False

            Log(f"2. 在 {target_exchange} 买入 {_N(buy_amount, 6)} {coin} @ {_N(price, 6)}")
            buy_result = await account.spot_buy(target_exchange, coin.lower(), buy_amount, price)
            if not buy_result:
                Log(f"❌ 在 {target_exchange} 买入失败")
                # 尝试回滚卖出操作
                Log(f"尝试回滚卖出操作...")
                rollback_result = await account.spot_buy(source_exchange, coin.lower(), sell_amount, price)
                if not rollback_result:
                    Log(f"❌ 回滚卖出操作失败")
                return False

            # 记录交易后的余额
            source_balance_after = account.get_balance(coin.lower(), source_exchange)
            target_balance_after = account.get_balance(coin.lower(), target_exchange)
            Log(f"\n交易后余额 - 源交易所: {_N(source_balance_after, 6)}, 目标交易所: {_N(target_balance_after, 6)}")

            # 计算实际变化
            source_change = source_balance_after - source_balance_before
            target_change = target_balance_after - target_balance_before
            Log(f"余额变化 - 源交易所: {_N(source_change, 6)}, 目标交易所: {_N(target_change, 6)}")

            # 计算实际利润
            total_change = source_change + target_change
            Log(f"总余额变化: {_N(total_change, 6)} {coin}")

            # 创建交易记录
            trade_record = TradeRecord.create_balance_record(
                coin=coin,
                source_exchange=source_exchange,
                target_exchange=target_exchange,
                amount=amount,
                price=price,
                source_balance_before=source_balance_before,
                source_balance_after=source_balance_after,
                target_balance_before=target_balance_before,
                target_balance_after=target_balance_after,
                source_change=source_change,
                target_change=target_change,
                total_change=total_change,
                expected_profit_ratio=expected_profit_ratio,
                expected_profit=expected_profit
            )
            
            # 记录交易记录到日志
            TradeRecord.log_trade_record(trade_record)
            
            # 将交易记录添加到账户
            account.add_trade_record(trade_record)
            
            Log(f"✅ 均衡交易执行成功")
            return True
        except Exception as e:
            Log(f"❌ 执行均衡交易时发生错误: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return False