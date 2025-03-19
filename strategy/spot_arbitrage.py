import time
from datetime import datetime
from typing import Dict, Any, Tuple
import asyncio

from strategy.arbitrage_opportunity import ArbitrageOpportunity
from strategy.hedge_opportunity import HedgeOpportunity
from strategy.balance_opportunity import BalanceOpportunity
from strategy.pending_opportunity import PendingOpportunity
from strategy.trade_type import TradeType
from strategy.trade_utils import calculate_dynamic_min_amount
from utils.simulated_account import SimulatedAccount
from utils.logger import Log, _N


class SpotArbitrage:
    """现货套利策略"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strategy_config = config.get('strategy', {})
        self.coins = self.strategy_config.get('COINS', [])
        self.spot_exchanges = self.strategy_config.get('MAIN_EXCHANGES', [])
        self.min_amount = self.strategy_config.get('MIN_AMOUNT', 0.001)
        self.min_profit_threshold = self.strategy_config.get('MIN_PROFIT_THRESHOLD', 0.001)
        self.min_basis = self.strategy_config.get('MIN_BASIS', 0.001)
        self.max_position_deviation = self.strategy_config.get('MAX_POSITION_DEVIATION', 0.2)
        self.order_timeout = self.strategy_config.get('ORDER_TIMEOUT', 300)  # 5分钟超时
        
        # 初始化各种策略处理器
        self.pending_handler = PendingOpportunity()
        self.arbitrage_handler = ArbitrageOpportunity()
        self.hedge_handler = HedgeOpportunity()
        self.balance_handler = BalanceOpportunity()
        
        # 初始化时间戳记录
        self._last_balance_check = 0
        self._last_report_time = 0

        # 移除所有与期货相关的配置
        Log(f"===== 初始化现货套利策略 =====")
        Log(f"支持的币种: {', '.join(self.coins)}")
        Log(f"支持的现货交易所: {', '.join(self.spot_exchanges)}")
        Log(f"最小交易数量: {self.min_amount}")
        Log(f"最小利润阈值: {_N(self.min_profit_threshold * 100, 4)}%")
        Log(f"最小价差: {_N(self.min_basis * 100, 4)}%")
        Log(f"最大仓位偏差: {_N(self.max_position_deviation * 100, 4)}%")
        Log(f"订单超时时间: {self.order_timeout}秒")
        Log(f"===============================")

    async def determine_trade_type(self, coin: str, account: SimulatedAccount,
                                   all_depths: Dict[str, Dict[str, Dict[str, Any]]]) -> Tuple[
        str, float, float, float, str, str]:
        """
        确定交易类型
        
        Args:
            coin: 币种
            account: 账户对象
            all_depths: 所有深度数据
            
        Returns:
            Tuple[str, float, float, float, str, str]: 
                (交易类型, 买入价格, 卖出价格, 交易数量, 买入交易所, 卖出交易所)
        """
        # 检查币种是否在深度数据中
        if coin not in all_depths:
            Log(f"币种 {coin} 不在深度数据中")
            return TradeType.NO_TRADE, 0, 0, 0, "", ""

        # 获取支持的交易所列表
        supported_exchanges = []
        for ex in self.spot_exchanges:
            if ex in all_depths[coin]:
                supported_exchanges.append(ex)

        if len(supported_exchanges) < 2:
            Log(f"币种 {coin} 的支持交易所数量不足 (需要至少2个)")
            return TradeType.NO_TRADE, 0, 0, 0, "", ""

        # 动态计算最小交易数量
        dynamic_min_amount = calculate_dynamic_min_amount(coin, all_depths[coin], self.config, account)
        Log(f"币种 {coin} 动态计算的最小交易数量: {_N(dynamic_min_amount, 6)}")

        # 检查是否有未处理的挂单
        pending_orders = account.get_pending_orders()
        if pending_orders:
            # 检查挂单是否需要处理
            for order in pending_orders:
                if order.get('coin') == coin:  # 只处理当前币种的挂单
                    Log(f"存在未处理的 {coin} 挂单，跳过新交易检查")
                    return TradeType.PENDING_TRADE, 0, 0, 0, "", ""

        # 检查是否有套利机会
        Log(f"\n检查 {coin} 的套利机会...")
        arbitrage_info = await self.arbitrage_handler._check_arbitrage_opportunity(
            coin, depths=all_depths[coin], account=account, spot_exchanges=supported_exchanges,
            min_amount=dynamic_min_amount, min_basis=self.min_basis, config=self.config)

        if arbitrage_info:
            # 解包套利信息：(buy_ex, sell_ex, buy_price, sell_price, amount)
            buy_ex, sell_ex, buy_price, sell_price, amount = arbitrage_info
            # 验证套利机会是否有效
            if amount > 0 and buy_price > 0 and sell_price > 0:
                Log(f"发现有效套利机会: {buy_ex}->{sell_ex}, 数量: {_N(amount, 6)}")
                return TradeType.ARBITRAGE, buy_price, sell_price, amount, buy_ex, sell_ex
        
        # 检查是否需要余额操作
        Log(f"\n检查 {coin} 的余额操作机会...")
        balance_info = await self.balance_handler._check_balance_opportunity(
            coin, all_depths[coin], account, supported_exchanges,
            min_amount=dynamic_min_amount, max_deviation=self.max_position_deviation, config=self.config
        )
        if balance_info:
            operation_type, price, amount, source_exchange, target_exchange = balance_info
            # 验证余额操作是否有效
            if amount > 0 and price > 0:
                Log(f"发现有效均衡操作: {operation_type}")
                if operation_type == 'buy':
                    return TradeType.BALANCE_OPERATION, price, 0, amount, source_exchange, target_exchange
                else:  # sell
                    return TradeType.BALANCE_OPERATION, 0, price, amount, source_exchange, target_exchange
        
        # 检查是否有挂单套利机会
        Log(f"\n检查 {coin} 的挂单套利机会...")
        try:
            pending_info = await self.pending_handler._check_pending_opportunity(
                coin, all_depths[coin], account, supported_exchanges,
                min_amount=dynamic_min_amount, min_basis=self.min_profit_threshold, config=self.config
            )
            if pending_info:
                trade_type, buy_price, sell_price, amount, buy_ex, sell_ex = pending_info
                # 验证挂单机会是否有效
                if amount > 0 and (buy_price > 0 or sell_price > 0):
                    if trade_type == TradeType.PENDING_TRADE:
                        return TradeType.PENDING_TRADE, buy_price, sell_price, amount, buy_ex, sell_ex
                    elif trade_type == TradeType.REVERSE_PENDING:
                        return TradeType.REVERSE_PENDING, buy_price, sell_price, amount, buy_ex, sell_ex
        except TypeError:
            # 兼容旧版本接口
            Log(f"使用兼容模式检查挂单机会")
            pending_info = await self.pending_handler._check_pending_opportunity(
                coin, all_depths[coin], account, supported_exchanges,
                min_amount=dynamic_min_amount, min_basis=self.min_profit_threshold, config=self.config
            )
            if pending_info:
                trade_type, buy_price, sell_price, amount, buy_ex, sell_ex = pending_info
                # 验证挂单机会是否有效
                if amount > 0 and buy_price > 0 and sell_price > 0:
                    return TradeType.PENDING_TRADE, buy_price, sell_price, amount, buy_ex, sell_ex

        Log(f"未发现 {coin} 的任何有效交易机会")
        return TradeType.NO_TRADE, 0, 0, 0, "", ""

    async def process_arbitrage_opportunities(self,
                                              coin,
                                              account: SimulatedAccount,
                                              all_depths: Dict[str, Dict[str, Dict[str, Any]]],
                                              current_time: datetime,
                                              config: Dict[str, Any]
                                              ) -> None:
        """处理套利机会"""
        try:
            Log(f"\n===== 处理套利机会: {coin.upper()} @ {current_time.strftime('%Y-%m-%d %H:%M:%S')} =====")

            # 处理已有的挂单 (无论当前交易类型如何，都需要检查和处理已有的挂单)
            await self.process_pending_orders(account=account, current_time=current_time, config=config)
            
            # 处理取消订单的对冲操作
            await self.hedge_handler.hedge_cancelled_orders(
                account=account,
                coin=coin,
                spot_exchanges=self.spot_exchanges,
                all_depths=all_depths,
                current_time=current_time,
                config=config
            )

            # 检查币种是否在深度数据中
            if coin not in all_depths:
                Log(f"深度数据中没有 {coin} 的信息，跳过处理")
                return

            # 检查是否有未处理的挂单，并且验证挂单是否有效
            pending_orders = account.get_pending_orders()
            if pending_orders:
                # 检查挂单是否需要处理
                for order in pending_orders:
                    if order.get('coin') == coin:  # 只处理当前币种的挂单
                        Log(f"存在未处理的 {coin} 挂单，跳过新交易检查")
                        return

            # 获取支持的交易所列表
            supported_exchanges = []
            for ex in self.spot_exchanges:
                if ex in all_depths[coin]:
                    supported_exchanges.append(ex)

            # 首先确定交易类型
            trade_type, buy_price, sell_price, amount, buy_ex, sell_ex = await self.determine_trade_type(
                coin, account, all_depths
            )

            # 检查是否有套利机会
            if trade_type == TradeType.ARBITRAGE:
                # 验证套利机会是否有效
                if amount > 0 and buy_price > 0 and sell_price > 0:
                    Log(f"\n执行套利交易:")
                    Log(f"币种: {coin.upper()}")
                    Log(f"买入交易所: {buy_ex} @ {_N(buy_price, 6)}")
                    Log(f"卖出交易所: {sell_ex} @ {_N(sell_price, 6)}")
                    Log(f"交易数量: {_N(amount, 6)}")
                    Log(f"价差: {_N((sell_price - buy_price) / buy_price * 100, 4)}%")

                    # 检查是否启用交易
                    trading_enabled = config.get('strategy', {}).get('ENABLE_TRADING', True)

                    if trading_enabled:
                        await self.arbitrage_handler.execute_arbitrage_trade(
                            coin=coin, buy_exchange=buy_ex, sell_exchange=sell_ex, buy_price=buy_price, sell_price=sell_price,
                            amount=amount, account=account, all_depths=all_depths[coin], config=config, current_time=current_time
                        )
                    else:
                        Log("交易已禁用，跳过执行")

            elif trade_type == TradeType.BALANCE_OPERATION:
                # 执行余额操作
                operation_type = 'buy' if buy_price > 0 else 'sell'
                price = buy_price if buy_price > 0 else sell_price

                Log(f"\n执行余额操作:")
                Log(f"币种: {coin.upper()}")
                Log(f"源交易所: {buy_ex}")
                Log(f"目标交易所: {sell_ex}")
                Log(f"操作: {operation_type}")
                Log(f"价格: {_N(price, 6)}")
                Log(f"数量: {_N(amount, 6)}")

                await self.balance_handler.execute_balance_trade(
                    coin=coin,
                    amount=amount,
                    target_exchange=buy_ex,
                    source_exchange=sell_ex,
                    account=account,
                    depths=all_depths[coin],
                    supported_exchanges=supported_exchanges,
                    current_time=current_time
                )

            elif trade_type == TradeType.PENDING_TRADE:
                # 执行挂单套利
                Log(f"\n执行挂单套利:")
                Log(f"币种: {coin.upper()}")
                Log(f"买入交易所: {buy_ex} @ {_N(buy_price, 6)}")
                Log(f"卖出交易所: {sell_ex} @ {_N(sell_price, 6)}")
                Log(f"数量: {_N(amount, 6)}")
                Log(f"价差: {_N((sell_price - buy_price) / buy_price * 100, 4)}%")

                # 获取最新深度数据
                if buy_ex not in all_depths[coin] or sell_ex not in all_depths[coin]:
                    Log(f"无法获取最新深度数据，跳过执行")
                    return

                buy_depth = all_depths[coin][buy_ex]
                sell_depth = all_depths[coin][sell_ex]
                
                if buy_depth and sell_depth:
                    await self.pending_handler.execute_pending_trade(
                        account=account,
                        coin=coin,
                        buy_ex=buy_ex,
                        sell_ex=sell_ex,
                        buy_depth=buy_depth,
                        sell_depth=sell_depth,
                        trade_type=trade_type,
                        current_time=current_time,
                        amount=amount,
                        config=config
                    )
                else:
                    Log(f"无法获取深度数据，取消挂单套利")

            elif trade_type == TradeType.REVERSE_PENDING:
                # 执行反向挂单套利
                Log(f"\n执行反向挂单套利:")
                Log(f"币种: {coin.upper()}")
                Log(f"卖出交易所: {sell_ex} @ {_N(sell_price, 6)}")
                Log(f"买入交易所: {buy_ex} @ {_N(buy_price, 6)}")
                Log(f"数量: {_N(amount, 6)}")
                Log(f"价差: {_N((sell_price - buy_price) / buy_price * 100, 4)}%")

                # 获取最新深度数据
                if buy_ex not in all_depths[coin] or sell_ex not in all_depths[coin]:
                    Log(f"无法获取最新深度数据，跳过执行")
                    return

                buy_depth = all_depths[coin][buy_ex]
                sell_depth = all_depths[coin][sell_ex]

                if buy_depth and sell_depth:
                    await self.pending_handler.execute_pending_trade(
                        account=account,
                        coin=coin,
                        buy_ex=buy_ex,
                        sell_ex=sell_ex,
                        buy_depth=buy_depth,
                        sell_depth=sell_depth,
                        trade_type=trade_type,
                        current_time=current_time,
                        amount=amount,
                        config=config
                    )
                else:
                    Log(f"无法获取深度数据，取消反向挂单套利")

            # 检查并平衡现货持仓
            # 根据配置决定是否执行平衡操作
            current_timestamp = int(time.time())

            # 定期生成现货持仓报告（频率低于平衡检查）
            # report_interval = config.get('strategy', {}).get('POSITION_REPORT_INTERVAL', 300)  # 默认每5分钟生成一次报告
            #
            # if current_timestamp - self._last_report_time >= report_interval:
            #     await self.generate_position_report(account, all_depths, current_time, config)
            #     self._last_report_time = current_timestamp

            Log(f"===== 处理完成 =====")

        except Exception as e:
            Log(f"❌ 处理套利机会时发生错误: {str(e)}")
            import traceback
            Log(traceback.format_exc())

    async def process_pending_orders(self,
                                     account: SimulatedAccount,
                                     current_time: datetime,
                                     config: Dict[str, Any]
                                     ) -> None:
        """处理挂单"""
        # 使用PendingOpportunity类的方法处理挂单
        await self.pending_handler.process_pending_orders(account, current_time, config)

    async def generate_position_report(self,
                                       account: SimulatedAccount,
                                       all_depths: Dict[str, Dict[str, Dict[str, Any]]],
                                       current_time: datetime,
                                       config: Dict[str, Any]) -> None:
        """
        定期生成现货持仓报告
        
        此方法用于定期生成和记录现货持仓的详细报告，
        但不执行任何平衡操作。
        
        Args:
            account: 账户对象
            all_depths: 所有深度数据
            current_time: 当前时间
            config: 配置信息
        """
        # 分析结果
        analysis = await self.analyze_spot_positions(account)

        # 记录报告
        Log(f"\n===== 定期现货持仓报告 ({current_time.strftime('%Y-%m-%d %H:%M:%S')}) =====")
        Log(f"总持仓价值: {_N(analysis['total_positions'], 4)} USDT")
        Log(f"风险评级: {analysis['risk_level']}")
        
        # 如果有高风险币种，详细记录
        high_risk_coins = [coin for coin, data in analysis.get('coins_analysis', {}).items() 
                          if data.get('risk_level') == 'HIGH']
        
        if high_risk_coins:
            Log(f"\n⚠️ 高风险币种: {', '.join(high_risk_coins)}")
            for coin in high_risk_coins:
                coin_data = analysis['coins_analysis'][coin]
                Log(f"  {coin.upper()}:")
                Log(f"    总持仓: {_N(coin_data['total_position'], 6)}")
                Log(f"    平均持仓: {_N(coin_data['avg_position'], 6)}")
                Log(f"    最大偏差: {_N(coin_data['max_deviation'], 6)} @ {coin_data['max_deviation_exchange']}")
                Log(f"    偏差比例: {_N(coin_data['deviation_ratio'] * 100, 2)}%")
        
        # 如果风险级别高，发出警告
        if analysis['risk_level'] == 'HIGH':
            Log(f"\n⚠️ 警告: 现货持仓风险级别高，建议执行平衡操作!")
            for recommendation in analysis['recommendations']:
                Log(f"建议: {recommendation}")
        
        Log(f"===========================================")

    async def analyze_spot_positions(self, account: SimulatedAccount) -> Dict[str, Any]:
        """
        分析现货持仓情况
        
        Args:
            account: 账户对象
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        # 获取所有交易所的持仓
        positions = {}
        for exchange in self.spot_exchanges:
            positions[exchange] = {}
            for coin in self.coins:
                balance = account.get_balance(coin.lower(), exchange)
                if balance > 0:
                    positions[exchange][coin] = balance
        
        # 计算每个币种在各交易所的总持仓
        total_positions = {}
        for coin in self.coins:
            total_positions[coin] = 0
            for exchange in self.spot_exchanges:
                total_positions[coin] += positions.get(exchange, {}).get(coin, 0)
        
        # 计算每个币种在各交易所的持仓比例
        position_ratios = {}
        for exchange in self.spot_exchanges:
            position_ratios[exchange] = {}
            for coin in self.coins:
                if total_positions[coin] > 0:
                    position_ratios[exchange][coin] = positions.get(exchange, {}).get(coin, 0) / total_positions[coin]
                else:
                    position_ratios[exchange][coin] = 0
        
        # 计算每个币种在各交易所的持仓偏差
        position_deviations = {}
        for exchange in self.spot_exchanges:
            position_deviations[exchange] = {}
            for coin in self.coins:
                # 理想比例是平均分配
                ideal_ratio = 1.0 / len(self.spot_exchanges)
                actual_ratio = position_ratios[exchange][coin]
                deviation = actual_ratio - ideal_ratio
                position_deviations[exchange][coin] = deviation
        
        # 找出偏差最大的币种和交易所
        max_deviation = 0
        max_deviation_coin = None
        max_deviation_exchange = None
        
        for exchange in self.spot_exchanges:
            for coin in self.coins:
                deviation = abs(position_deviations[exchange][coin])
                if deviation > max_deviation:
                    max_deviation = deviation
                    max_deviation_coin = coin
                    max_deviation_exchange = exchange
        
        # 获取各币种的价格
        coin_prices = {}
        for coin in self.coins:
            # 简化处理，使用第一个交易所的价格
            for exchange in self.spot_exchanges:
                if hasattr(account, '_get_estimated_price'):
                    price = await account._get_estimated_price(coin, exchange)
                    if price > 0:
                        coin_prices[coin] = price
                        break

        # 最大偏差比例阈值
        high_risk_threshold = self.max_position_deviation * 2  # 高风险阈值
        
        # 计算各交易所的总资产价值
        exchange_values = {}
        total_value = 0
        
        for exchange in self.spot_exchanges:
            exchange_values[exchange] = account.get_balance('usdt', exchange)  # USDT余额
            for coin, balance in positions.get(exchange, {}).items():
                if coin in coin_prices:
                    coin_value = balance * coin_prices[coin]
                    exchange_values[exchange] += coin_value
            total_value += exchange_values[exchange]
        
        # 计算各交易所资产占比
        exchange_ratios = {}
        for exchange in self.spot_exchanges:
            if total_value > 0:
                exchange_ratios[exchange] = exchange_values[exchange] / total_value
            else:
                exchange_ratios[exchange] = 0
        
        # 计算各交易所资产偏差
        exchange_deviations = {}
        for exchange in self.spot_exchanges:
            ideal_ratio = 1.0 / len(self.spot_exchanges)
            actual_ratio = exchange_ratios[exchange]
            deviation = actual_ratio - ideal_ratio
            exchange_deviations[exchange] = deviation
        
        # 找出资产偏差最大的交易所
        max_asset_deviation = 0
        max_asset_deviation_exchange = None
        
        for exchange in self.spot_exchanges:
            deviation = abs(exchange_deviations[exchange])
            if deviation > max_asset_deviation:
                max_asset_deviation = deviation
                max_asset_deviation_exchange = exchange
        
        # 构建分析结果
        result = {
            'positions': positions,
            'total_positions': total_positions,
            'position_ratios': position_ratios,
            'position_deviations': position_deviations,
            'max_deviation': max_deviation,
            'max_deviation_coin': max_deviation_coin,
            'max_deviation_exchange': max_deviation_exchange,
            'coin_prices': coin_prices,
            'exchange_values': exchange_values,
            'total_value': total_value,
            'exchange_ratios': exchange_ratios,
            'exchange_deviations': exchange_deviations,
            'max_asset_deviation': max_asset_deviation,
            'max_asset_deviation_exchange': max_asset_deviation_exchange,
            'high_risk': max_deviation > high_risk_threshold,
            'risk_level': 'HIGH' if max_deviation > high_risk_threshold else 'MEDIUM' if max_deviation > self.max_position_deviation else 'LOW'
        }
        
        return result

    # 以下是为保持向后兼容性的别名方法
    async def analyze_position_report(self, account: SimulatedAccount) -> Dict[str, Any]:
        """分析持仓分布情况（别名方法，为保持向后兼容性）"""
        return await self.analyze_spot_positions(account)
        
    async def generate_spot_positions_report(self, account: SimulatedAccount) -> str:
        """生成详细的现货持仓报告（已弃用，使用generate_position_report代替）"""
        Log("警告: generate_spot_positions_report方法已弃用，请使用generate_position_report")
        analysis = await self.analyze_spot_positions(account)
        return f"总持仓价值: {_N(analysis['total_positions'], 4)} USDT, 风险评级: {analysis['risk_level']}"
        
    async def generate_unhedged_positions_report(self, account: SimulatedAccount) -> str:
        """生成未对冲持仓的详细报告（已弃用，使用generate_position_report代替）"""
        Log("警告: generate_unhedged_positions_report方法已弃用，请使用generate_position_report")
        return await self.generate_spot_positions_report(account)
        
    def calculate_optimal_hedge_amount(self,
                                       basis: float,
                                       min_basis: float,
                                       min_amount: float,
                                       max_amount: float,
                                       basis_scale_factor: float = 5.0) -> float:
        """
        根据基差计算最优交易量（已弃用）
        """
        Log("警告: calculate_optimal_hedge_amount方法已弃用")
        # 计算基差比例
        basis_ratio = basis / min_basis

        # 计算动态交易量
        dynamic_amount = min_amount + (max_amount - min_amount) * (basis_ratio - 1) * basis_scale_factor

        # 确保不超过最大交易量
        return min(dynamic_amount, max_amount)
