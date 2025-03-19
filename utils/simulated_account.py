import os
import json
from datetime import datetime
from typing import Dict, Any, List, Union
import asyncio
import time
from utils.cache_manager import depth_cache

from exchanges import ExchangeFactory
from utils.logger import Log
from utils.config import load_supported_exchanges, get_exchange_fee

class SimulatedAccount:
    """模拟账户"""
    
    def __init__(self, initial_balance: float = 10000, config: Dict[str, Any] = None):
        """初始化模拟账户

        Args:
            initial_balance: 初始余额
            config: 配置信息
        """
        self.initial_balance = initial_balance
        self.config = config or {}

        # 初始化交易所字典
        self.exchanges = {}

        # 初始化费率缓存
        self.fee_cache = {
            'maker': {},
            'taker': {}
        }

        # 初始化余额字典
        self.balances = {
            'usdt': {},
            'stocks': {}
        }

        # 初始化冻结余额字典
        self.frozen_balances = {
            'usdt': {},
            'stocks': {}
        }

        # 初始化未对冲头寸字典
        self.unhedged_positions = {}

        # 初始化挂单列表
        self.pending_orders = []

        # 初始化交易统计
        self.trade_stats = {
            'total_trades': 0,
            'success_trades': 0,
            'failed_trades': 0,
            'total_volume': 0.0,
            'total_profit': 0.0,
            'total_fees': 0.0,
            'max_profit': float('-inf'),
            'max_loss': float('inf')  # 初始化为正无穷，因为我们要找最小值
        }

        # 初始化交易记录
        self.trade_records = []

        # 设置最大保留的最近交易记录数量
        self.max_recent_trades = 10000

        # 初始化取消订单统计
        self._cancelled_order_stats = {}

        self.main_currency = 'usdt'
        self.main_balance = 0.0

    async def initialize(self):
        """异步初始化方法"""
        await self._initialize_fees()
        await self._initialize_coin_balances()

    async def _initialize_fees(self):
        """初始化交易所费率"""
        try:
            # 1. 尝试从 exchange_fees.json 加载费率信息
            try:
                config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
                fee_file_path = os.path.join(config_dir, 'exchange_fees.json')
                with open(fee_file_path, 'r') as f:
                    fee_info = json.load(f)
            except Exception as e:
                Log(f"读取exchange_fees.json失败: {str(e)}")
                fee_info = {}

            # 2. 遍历所有支持的交易所和币种
            supported_exchanges = load_supported_exchanges()

            for coin, exchanges in supported_exchanges.items():
                for exchange in exchanges:
                    # 检查是否已经有这个交易所的费率信息
                    if coin not in self.fee_cache:
                        self.fee_cache[coin] = {}

                    # 从JSON文件中获取费率
                    if coin in fee_info and exchange in fee_info[coin]:
                        maker_fee = fee_info[coin][exchange]['maker']
                        taker_fee = fee_info[coin][exchange]['taker']
                        Log(f"从配置文件加载{exchange} {coin}费率: maker={maker_fee}, taker={taker_fee}")
                        self.update_fee(exchange, coin, maker_fee, taker_fee)
                        Log(f"从配置文件加载{exchange} {coin}费率: maker={maker_fee}, taker={taker_fee}")
                        continue

                    # 如果JSON中没有费率信息，尝试从交易所获取
                    try:
                        # 创建交易所实例（如果还没有）
                        # if exchange not in self.exchanges:
                        #     self.initialize_exchange(exchange)
                        if exchange in self.exchanges and self.exchanges[exchange]:
                            maker_fee = await self.exchanges[exchange].GetFee(coin, True)
                            taker_fee = await self.exchanges[exchange].GetFee(coin, False)
                            self.update_fee(exchange, coin, maker_fee, taker_fee)
                            Log(f"从API获取{exchange} {coin}费率: maker={maker_fee}, taker={taker_fee}")
                    except Exception as e:
                        Log(f"获取{exchange} {coin}费率失败: {str(e)}")
                        # 使用默认费率
                        self.update_fee(exchange, coin, 0.002, 0.002)  # 默认0.2%
                        Log(f"使用默认费率 {exchange} {coin}: maker=0.2%, taker=0.2%")

        except Exception as e:
            Log(f"初始化交易所费率失败: {str(e)}")
            raise

    def get_fee(self, exchange: str, coin: str = 'usdt', is_maker: bool = False) -> float:
        """
        获取指定交易所和币种的费率

        Args:
            exchange: 交易所名称
            coin: 币种
            is_maker: 是否是maker单

        Returns:
            float: 费率
        """
        try:
            fee_type = 'maker' if is_maker else 'taker'
            
            # 从缓存中获取费率
            if exchange in self.fee_cache[fee_type] and coin in self.fee_cache[fee_type][exchange]:
                fee = self.fee_cache[fee_type][exchange][coin]
                # 确保费率是有效的正值
                if fee >= 0:
                    return fee
            
            # 如果缓存中没有或费率无效，使用 get_exchange_fee 函数获取费率
            fee = get_exchange_fee(exchange, coin.upper(), is_maker)
            
            # 对于未知交易所，确保返回 0.002
            if exchange.lower() == 'unknown':
                fee = 0.002
            
            # 更新缓存
            if exchange not in self.fee_cache[fee_type]:
                self.fee_cache[fee_type][exchange] = {}
            self.fee_cache[fee_type][exchange][coin] = fee
            
            return fee
        except Exception as e:
            Log(f"获取{exchange} {coin}费率失败: {str(e)}")
            return 0.002  # 出错时返回默认费率

    def update_fee(self, exchange: str, coin: str, maker_fee: float, taker_fee: float):
        """
        更新指定交易所和币种的费率

        Args:
            exchange: 交易所名称
            coin: 币种
            maker_fee: maker费率
            taker_fee: taker费率
        """
        if exchange not in self.fee_cache['maker']:
            self.fee_cache['maker'][exchange] = {}
        if exchange not in self.fee_cache['taker']:
            self.fee_cache['taker'][exchange] = {}

        self.fee_cache['maker'][exchange][coin] = maker_fee
        self.fee_cache['taker'][exchange][coin] = taker_fee

    async def _initialize_coin_balances(self):
        """初始化每个交易所的币种余额"""
        try:
            coins = self.config.get('strategy', {}).get('COINS', [])
            supported_exchanges = self.config.get('supported_exchanges', {})
            Log(f"初始化币种: {coins}")

            # 1. 收集所有需要初始化的交易所
            all_exchanges = set()
            for exchanges in supported_exchanges.values():
                all_exchanges.update(exchanges)

            # 2. 过滤掉期货交易所，只保留现货交易所
            spot_exchanges = [ex for ex in all_exchanges if 'futures' not in ex.lower()]
            
            Log(f"现货交易所: {spot_exchanges}")

            # 3. 初始化所有现货交易所
            for exchange in spot_exchanges:
                if exchange not in self.exchanges:
                    self.initialize_exchange(exchange)

            # 4. 计算资金分配
            # 所有资金都分配给现货账户，其中50%用于购买币种
            total_spot_balance = self.initial_balance  # 100%给现货
            total_spot_coin_value = total_spot_balance * 0.5  # 现货资金的50%用于购买币种
            
            Log(f"现货账户总资金: {total_spot_balance} USDT，其中 {total_spot_coin_value} USDT 用于购买币种")

            # 5. 计算每个币种应分配的资金
            coin_count = len(coins)
            if coin_count == 0:
                Log("没有需要初始化的币种")
                return
                
            # 每个币种平均分配资金
            value_per_coin = total_spot_coin_value / coin_count
            Log(f"每个币种平均分配 {value_per_coin} USDT")

            # 6. 为每个现货交易所分配币种
            for coin in coins:
                # 获取该币种支持的现货交易所
                coin_spot_exchanges = [ex for ex in supported_exchanges.get(coin, []) if 'futures' not in ex.lower()]
                if not coin_spot_exchanges:
                    Log(f"{coin} 没有支持的现货交易所，跳过")
                    continue

                # 获取该币种的估计价格
                # 尝试获取该币种支持的交易所
                if coin_spot_exchanges:
                    # 使用第一个支持的交易所
                    exchange = coin_spot_exchanges[0]
                    coin_price = await self._get_estimated_price(coin, exchange)
                    Log(f"从交易所 {exchange} 获取 {coin} 的价格: {coin_price}")
                else:
                    # 如果没有支持的交易所，则不指定交易所
                    coin_price = await self._get_estimated_price(coin)
                    Log(f"获取 {coin} 的价格(未指定交易所): {coin_price}")
                
                if coin_price <= 0:
                    Log(f"无法获取 {coin} 的价格，跳过初始化")
                    continue

                # 计算需要购买的币种数量
                total_coin_amount = value_per_coin / coin_price
                
                # 不再平均分配，而是引入一些随机差异，但保证均衡率不超过20%
                import random
                
                # 设置最大偏差率为20%
                max_deviation = 0.20
                
                # 生成随机偏差系数，范围在[1-max_deviation, 1+max_deviation]之间
                deviation_factors = []
                for _ in range(len(coin_spot_exchanges)):
                    # 生成[-max_deviation, max_deviation]范围内的随机数
                    deviation = random.uniform(-max_deviation, max_deviation)
                    # 转换为[1-max_deviation, 1+max_deviation]范围
                    factor = 1 + deviation
                    deviation_factors.append(factor)
                
                # 归一化偏差系数，确保总和为交易所数量
                total_factors = sum(deviation_factors)
                normalized_factors = [factor * len(coin_spot_exchanges) / total_factors for factor in deviation_factors]
                
                # 计算每个交易所的分配量
                exchange_amounts = {}
                for i, exchange in enumerate(coin_spot_exchanges):
                    # 基础平均分配量
                    base_amount = total_coin_amount / len(coin_spot_exchanges)
                    # 应用偏差系数
                    adjusted_amount = base_amount * normalized_factors[i]
                    exchange_amounts[exchange] = adjusted_amount
                
                # 验证最大偏差是否在允许范围内
                avg_amount = total_coin_amount / len(coin_spot_exchanges)
                max_actual_deviation = max([abs(amount - avg_amount) / avg_amount for amount in exchange_amounts.values()])
                
                Log(f"为 {coin} 生成的分配方案:")
                for exchange, amount in exchange_amounts.items():
                    deviation_pct = (amount - avg_amount) / avg_amount * 100
                    Log(f"  {exchange}: {amount:.6f} {coin} (偏差: {deviation_pct:.2f}%)")
                Log(f"最大实际偏差率: {max_actual_deviation * 100:.2f}%")
                
                # 更新每个交易所的币种余额和USDT余额
                for exchange, amount in exchange_amounts.items():
                    # 更新币种余额
                    if exchange not in self.balances['stocks']:
                        self.balances['stocks'][exchange] = {}
                    self.balances['stocks'][exchange][coin.lower()] = amount
                    
                    # 扣除相应的USDT
                    usdt_cost = amount * coin_price
                    if exchange in self.balances['usdt']:
                        self.balances['usdt'][exchange] -= usdt_cost
                        Log(f"{exchange} 购买 {amount:.6f} {coin}，"
                            f"花费 {usdt_cost:.6f} USDT，"
                            f"剩余 {self.balances['usdt'][exchange]:.6f} USDT")
                    
                    # 更新未对冲头寸
                    if exchange not in self.unhedged_positions:
                        self.unhedged_positions[exchange] = {}
                    self.unhedged_positions[exchange][coin.lower()] = amount
            
            # # 7. 打印初始化后的账户状态
            # Log("\n初始化后的账户状态:")
            # for exchange in spot_exchanges:
            #     Log(f"{exchange}:")
            #     Log(f"  USDT: {self.balances['usdt'].get(exchange, 0)}")
            #     Log(f"  冻结USDT: {self.frozen_balances['usdt'].get(exchange, 0)}")
            #     for coin in coins:
            #         coin_balance = self.balances['stocks'].get(exchange, {}).get(coin.lower(), 0)
            #         if coin_balance != 0:  # 只显示非零余额
            #             Log(f"  {coin}: {coin_balance}")
            #
            # Log("\n总资产价值:")
            # total_value = sum(self.balances['usdt'].values())
            # for exchange, coins_balance in self.balances['stocks'].items():
            #     for coin, amount in coins_balance.items():
            #         # 使用特定交易所获取价格
            #         coin_price = await self._get_estimated_price(coin.upper(), exchange)
            #         if coin_price > 0:
            #             value = amount * coin_price
            #             total_value += value
            #             Log(f"  {exchange} {coin.upper()}: {amount} 个，价值: {value} USDT")
            #
            # Log(f"总资产价值: {total_value} USDT")
            
        except Exception as e:
            Log(f"初始化币种余额时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())

    async def _get_estimated_price(self, coin: str, specific_exchange: str = None) -> float:
        """
        获取币种的估计价格

        Args:
            coin: 币种
            specific_exchange: 指定的交易所，如果提供则返回该交易所的价格

        Returns:
            float: 估计价格
        """
        try:
            # 首先尝试从缓存中获取所有币种价格
            coin_prices = depth_cache.get_coin_prices()
            
            # 如果指定了交易所，尝试获取该交易所的价格
            if specific_exchange:
                # 确保交易所名称一致性
                exchange_key = specific_exchange
                # 特殊处理Gate交易所
                if specific_exchange.lower() in ['gate', 'gate.io', 'gateio']:
                    exchange_key = 'Gate'
                
                # 从缓存获取深度数据
                cached_depth = depth_cache.get(exchange_key, coin.upper())
                
                if cached_depth and cached_depth.get('asks') and cached_depth.get('bids'):
                    # 使用缓存的深度数据计算中间价
                    exchange_price = (cached_depth['asks'][0][0] + cached_depth['bids'][0][0]) / 2
                    Log(f"从缓存获取 {exchange_key} {coin} 价格: {exchange_price}")
                    return exchange_price
                
                # 如果缓存中没有数据，则从交易所获取
                exchange_instance = None
                
                # 尝试使用标准化的交易所名称
                if exchange_key in self.exchanges:
                    exchange_instance = self.exchanges[exchange_key]
                # 尝试使用原始交易所名称
                elif specific_exchange in self.exchanges:
                    exchange_instance = self.exchanges[specific_exchange]
                
                if exchange_instance:
                    depth = await exchange_instance.GetDepth(coin.upper())
                    if depth and depth.Asks and depth.Bids:
                        # 使用买一卖一的中间价
                        exchange_price = (depth.Asks[0][0] + depth.Bids[0][0]) / 2
                        Log(f"从交易所获取 {exchange_key} {coin} 价格: {exchange_price}")
                        
                        # 更新缓存
                        depth_data = {
                            'asks': [(ask[0], ask[1]) for ask in depth.Asks],
                            'bids': [(bid[0], bid[1]) for bid in depth.Bids]
                        }
                        depth_cache.set(exchange_key, coin.upper(), depth_data)
                        
                        return exchange_price
                
                # 如果无法获取指定交易所的价格，记录警告并继续使用通用方法
                Log(f"无法获取指定交易所 {specific_exchange} 的 {coin} 价格，尝试使用其他交易所")
            
            # 如果没有指定交易所或无法获取指定交易所的价格，使用通用方法
            if coin in coin_prices and coin_prices[coin] > 0:
                Log(f"从缓存获取 {coin} 价格: {coin_prices[coin]}")
                return coin_prices[coin]
                
            # 从所有支持的交易所获取深度数据
            supported_exchanges = self.config.get('supported_exchanges', {}).get(coin.upper(), [])
            
            if not supported_exchanges:
                Log(f"币种 {coin} 在supported_exchanges中没有配置交易所，尝试使用配置中的所有交易所")
                # 如果在supported_exchanges中找不到，尝试使用配置中的所有交易所
                supported_exchanges = self.config.get('strategy', {}).get('EXCHANGES', [])
                if not supported_exchanges:
                    Log(f"配置中也没有定义交易所列表，无法获取深度数据")
                    return 0
            
            # 过滤出现货交易所
            spot_exchanges = [ex for ex in supported_exchanges if 'futures' not in ex.lower()]
            
            Log(f"币种 {coin} 支持的现货交易所: {spot_exchanges}")
            
            # 从配置中获取主要交易所列表，而不是硬编码
            main_exchanges = self.config.get('strategy', {}).get('MAIN_EXCHANGES', [])
            if not main_exchanges:
                # 如果配置中没有定义主要交易所，则使用默认列表
                main_exchanges = ['binance', 'okx', 'htx', 'mexc']
            
            # 将交易所按照主要交易所列表的顺序排序
            def get_exchange_priority(exchange):
                # 转换为小写进行比较
                ex_lower = exchange.lower()
                # 如果在主要交易所列表中，返回其索引，否则返回一个较大的数
                # 使用更安全的方式检查是否在列表中
                main_exchanges_lower = [x.lower() for x in main_exchanges]
                try:
                    return main_exchanges_lower.index(ex_lower)
                except ValueError:
                    # 如果不在列表中，返回一个较大的数
                    return len(main_exchanges)
            
            # 按优先级排序交易所
            sorted_exchanges = sorted(spot_exchanges, key=get_exchange_priority)
            
            # 限制查询的交易所数量，避免过多API调用
            max_exchanges = 6
            exchanges_to_query = sorted_exchanges[:max_exchanges]
            
            Log(f"获取 {coin} 价格，查询交易所: {exchanges_to_query}")
            
            # 如果查询交易所列表为空，尝试使用所有支持的交易所
            if not exchanges_to_query and spot_exchanges:
                Log(f"查询交易所列表为空，尝试使用所有支持的交易所: {spot_exchanges}")
                exchanges_to_query = spot_exchanges[:max_exchanges]
            
            # 如果仍然为空，尝试使用主要交易所列表
            if not exchanges_to_query and main_exchanges:
                Log(f"尝试使用主要交易所列表: {main_exchanges}")
                exchanges_to_query = main_exchanges[:max_exchanges]
            
            # 定义获取单个交易所价格的异步函数
            async def fetch_price(exchange):
                try:
                    # 确保交易所名称一致性
                    exchange_key = exchange
                    # 特殊处理Gate交易所
                    if exchange.lower() in ['gate', 'gate.io', 'gateio']:
                        exchange_key = 'Gate'
                    
                    # 首先尝试从缓存获取深度数据
                    cached_depth = depth_cache.get(exchange_key, coin.upper())
                    
                    if cached_depth and cached_depth.get('asks') and cached_depth.get('bids'):
                        # 使用缓存的深度数据计算中间价
                        mid_price = (cached_depth['asks'][0][0] + cached_depth['bids'][0][0]) / 2
                        Log(f"从缓存获取 {exchange_key} {coin} 价格: {mid_price}")
                        return mid_price
                    
                    # 如果缓存中没有数据，则从交易所获取
                    exchange_instance = None
                    
                    # 尝试使用标准化的交易所名称
                    if exchange_key in self.exchanges:
                        exchange_instance = self.exchanges[exchange_key]
                    # 尝试使用原始交易所名称
                    elif exchange in self.exchanges:
                        exchange_instance = self.exchanges[exchange]
                    
                    if exchange_instance:
                        depth = await exchange_instance.GetDepth(coin.upper())
                        if depth and depth.Asks and depth.Bids:
                            # 使用买一卖一的中间价
                            mid_price = (depth.Asks[0][0] + depth.Bids[0][0]) / 2
                            Log(f"从交易所获取 {exchange_key} {coin} 价格: {mid_price}")
                            
                            # 更新缓存
                            depth_data = {
                                'asks': [(ask[0], ask[1]) for ask in depth.Asks],
                                'bids': [(bid[0], bid[1]) for bid in depth.Bids]
                            }
                            depth_cache.set(exchange_key, coin.upper(), depth_data)
                            
                            return mid_price
                except Exception as e:
                    Log(f"获取 {exchange} {coin} 价格时出错: {str(e)}")
                return None
            
            # 并发获取所有交易所的价格
            tasks = [fetch_price(exchange) for exchange in exchanges_to_query]
            results = await asyncio.gather(*tasks)
            
            # 过滤掉None值
            prices = [price for price in results if price is not None]

            if not prices:
                # 如果没有获取到任何价格，尝试使用硬编码的默认价格
                default_prices = {
                    'BTC': 50000,
                    'ETH': 3000,
                    'USDT': 1.0,
                    'USDC': 1.0,
                    'ELON': 0.00002,
                    'DOGE': 0.1
                }
                if coin.upper() in default_prices:
                    default_price = default_prices[coin.upper()]
                    Log(f"使用默认价格 {coin}: {default_price}")
                    return default_price
                Log(f"无法获取 {coin} 价格，返回 0")
                return 0

            # 使用第一个有效价格作为估计价格，而不是中位数
            first_price = prices[0]
            Log(f"{coin} 最终估计价格: {first_price} (使用第一个交易所的价格，共 {len(prices)} 个交易所)")
            return first_price

        except Exception as e:
            Log(f"获取估计价格时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return 0

    def initialize_exchange(self, exchange: str):
        """
        初始化交易所

        Args:
            exchange: 交易所名称
        """
        try:
            # 1. 检查是否已经初始化
            if exchange in self.exchanges and self.exchanges[exchange]:
                return

            # 2. 获取交易所配置
            exchange_config = self.config.get('exchanges', {}).get(exchange, {})
            if not exchange_config:
                Log(f"找不到{exchange}的配置信息")
                return

            # 3. 创建交易所实例
            # 确保交易所名称一致性
            exchange_key = exchange
            # 特殊处理Gate交易所
            if exchange.lower() in ['gate', 'gate.io', 'gateio']:
                exchange_key = 'Gate'
                
            self.exchanges[exchange] = ExchangeFactory.create_exchange(exchange_key, exchange_config)

            # 4. 获取所有现货交易所
            all_exchanges = set()
            for exchanges in self.config.get('supported_exchanges', {}).values():
                all_exchanges.update([ex for ex in exchanges if 'futures' not in ex.lower()])

            # 5. 计算每个交易所应该分配的资金
            # 所有资金平分给现货交易所
            balance_per_exchange = self.initial_balance / max(len(all_exchanges), 1)
            Log(f"为现货交易所{exchange}分配 {balance_per_exchange:.2f} USDT")

            # 6. 初始化余额
            self.balances['usdt'][exchange] = balance_per_exchange
            if exchange not in self.balances['stocks']:
                self.balances['stocks'][exchange] = {}
            if exchange not in self.frozen_balances['usdt']:
                self.frozen_balances['usdt'][exchange] = 0
            if exchange not in self.frozen_balances['stocks']:
                self.frozen_balances['stocks'][exchange] = {}
            
            # 7. 初始化未对冲头寸字典
            if exchange not in self.unhedged_positions:
                self.unhedged_positions[exchange] = {}

            Log(f"成功初始化{exchange}交易所，初始余额: {balance_per_exchange:.2f} USDT")

        except Exception as e:
            Log(f"初始化{exchange}交易所失败: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            self.exchanges[exchange] = None

    def get_balance(self, currency: str = 'usdt', exchange: str = None) -> float:
        """
        获取指定币种和交易所的余额

        Args:
            currency: 币种名称
            exchange: 交易所名称，如果为None则返回所有交易所的总余额

        Returns:
            float: 余额
        """
        try:
            currency = currency.lower()
            balance_type = 'usdt' if currency == 'usdt' else 'stocks'
            
            if exchange:
                if currency == 'usdt':
                    return max(0, self.balances[balance_type].get(exchange, 0))
                else:
                    return max(0, self.balances[balance_type].get(exchange, {}).get(currency, 0))
            else:
                if currency == 'usdt':
                    return max(0, sum(self.balances[balance_type].values()))
                else:
                    return max(0, sum(balances.get(currency, 0) for balances in self.balances[balance_type].values()))

        except Exception as e:
            Log(f"获取{exchange} {currency}余额失败: {str(e)}")
            return 0

    def update_balance(self, currency: str, amount: float, exchange: str, is_buy: bool = True):
        """
        更新余额

        Args:
            currency: 币种名称
            amount: 数量（正数表示增加，负数表示减少）
            exchange: 交易所名称
            is_buy: 是否是买入（仅用于日志记录，不影响实际操作）
        """
        try:
            currency = currency.lower()
            if currency == 'usdt':
                if exchange not in self.balances['usdt']:
                    self.balances['usdt'][exchange] = 0
                self.balances['usdt'][exchange] = self.balances['usdt'].get(exchange, 0) + amount
            else:
                if exchange not in self.balances['stocks']:
                    self.balances['stocks'][exchange] = {}
                if currency not in self.balances['stocks'][exchange]:
                    self.balances['stocks'][exchange][currency] = 0
                self.balances['stocks'][exchange][currency] = self.balances['stocks'][exchange].get(currency, 0) + amount

            return True

        except Exception as e:
            Log(f"更新{exchange} {currency}余额失败: {str(e)}")
            return False

    def freeze_balance(self, currency: str, amount: float, exchange: str):
        """
        冻结余额

        Args:
            currency: 币种名称
            amount: 数量
            exchange: 交易所名称
        """
        try:
            # 确保金额为正数
            if amount < 0:
                return

            currency = currency.lower()
            if currency == 'usdt':
                if exchange not in self.frozen_balances['usdt']:
                    self.frozen_balances['usdt'][exchange] = 0
                self.frozen_balances['usdt'][exchange] = self.frozen_balances['usdt'].get(exchange, 0) + amount
            else:
                if exchange not in self.frozen_balances['stocks']:
                    self.frozen_balances['stocks'][exchange] = {}
                if currency not in self.frozen_balances['stocks'][exchange]:
                    self.frozen_balances['stocks'][exchange][currency] = 0
                self.frozen_balances['stocks'][exchange][currency] = self.frozen_balances['stocks'][exchange].get(currency, 0) + amount

        except Exception as e:
            Log(f"冻结{exchange} {currency}余额失败: {str(e)}")

    def get_freeze_balance(self, currency: str, exchange: str) -> float:
        """
        获取冻结余额

        Args:
            currency: 币种名称
            exchange: 交易所名称

        Returns:
            float: 冻结余额
        """
        try:
            currency = currency.lower()
            if currency == 'usdt':
                return max(0, self.frozen_balances['usdt'].get(exchange, 0))
            else:
                return max(0, self.frozen_balances['stocks'].get(exchange, {}).get(currency, 0))

        except Exception as e:
            Log(f"获取{exchange} {currency}冻结余额失败: {str(e)}")
            return 0

    def unfreeze_balance(self, currency: str, amount: float, exchange: str):
        """
        解冻余额

        Args:
            currency: 币种名称
            amount: 数量
            exchange: 交易所名称
        """
        try:
            # 确保金额为正数
            if amount < 0:
                return

            currency = currency.lower()
            if currency == 'usdt':
                if exchange not in self.frozen_balances['usdt']:
                    self.frozen_balances['usdt'][exchange] = 0
                self.frozen_balances['usdt'][exchange] = max(0, self.frozen_balances['usdt'].get(exchange, 0) - amount)
            else:
                if exchange in self.frozen_balances['stocks']:
                    if currency not in self.frozen_balances['stocks'][exchange]:
                        self.frozen_balances['stocks'][exchange][currency] = 0
                    self.frozen_balances['stocks'][exchange][currency] = max(0, self.frozen_balances['stocks'][exchange].get(currency, 0) - amount)

        except Exception as e:
            Log(f"解冻{exchange} {currency}余额失败: {str(e)}")

    def update_unhedged_position(self, coin: str, amount: float, exchange: str, is_buy: bool = True):
        """
        更新现货持仓
        
        在纯现货交易场景中，此方法用于跟踪各交易所的币种持仓情况，
        用于平衡不同交易所间的持仓或处理挂单。
        
        Args:
            coin: 币种名称
            amount: 数量
            exchange: 交易所名称
            is_buy: 是否是买入（True为买入增加持仓，False为卖出减少持仓）
        """
        coin = coin.lower()
        
        # 确保交易所存在于未对冲头寸字典中
        if exchange not in self.unhedged_positions:
            self.unhedged_positions[exchange] = {}
            
        # 确保币种存在于该交易所的未对冲头寸字典中
        if coin not in self.unhedged_positions[exchange]:
            self.unhedged_positions[exchange][coin] = 0
            
        # 更新持仓
        if is_buy:
            self.unhedged_positions[exchange][coin] += amount
            Log(f"增加 {exchange} 交易所 {coin.upper()} 持仓 {amount}，当前持仓: {self.unhedged_positions[exchange][coin]}")
        else:
            # 确保不会出现负数持仓
            if self.unhedged_positions[exchange][coin] < amount:
                Log(f"警告: {exchange} 交易所 {coin.upper()} 持仓不足，当前持仓: {self.unhedged_positions[exchange][coin]}，尝试减少: {amount}")
                amount = self.unhedged_positions[exchange][coin]
                
            self.unhedged_positions[exchange][coin] -= amount
            Log(f"减少 {exchange} 交易所 {coin.upper()} 持仓 {amount}，当前持仓: {self.unhedged_positions[exchange][coin]}")
            
        # 同步更新stocks余额
        if exchange not in self.balances['stocks']:
            self.balances['stocks'][exchange] = {}
        self.balances['stocks'][exchange][coin] = self.unhedged_positions[exchange][coin]

    async def CreateOrder(self, exchange: str, coin: str, price: float, amount: float, is_buy: bool = True) -> Dict[str, Any]:
        """
        创建订单（统一接口，用于替代直接调用Buy/Sell方法）
        
        Args:
            exchange: 交易所名称
            coin: 币种名称
            price: 价格
            amount: 数量
            is_buy: 是否是买入（True为买入，False为卖出）
            
        Returns:
            Dict[str, Any]: 订单信息，包含orderId等
        """
        try:
            # 获取交易所对象
            ex = self.exchanges.get(exchange)
            if not ex:
                Log(f"无法获取交易所对象: {exchange}")
                return None
                
            # 生成唯一订单ID
            order_id = f"simulated_{exchange}_{coin.lower()}_{int(time.time()*1000)}"
            
            # 模拟订单创建
            if is_buy:
                # 计算成本和手续费
                cost = price * amount
                fee = self.get_fee(exchange, coin, False) * cost  # 假设是taker费率
                
                Log(f"模拟买入订单: {exchange} 买入 {amount} {coin.upper()} @ {price} = {cost} USDT")
                Log(f"预估手续费: {fee} USDT")
                
                # 创建订单响应
                result = {
                    "orderId": order_id,
                    "symbol": f"{coin.upper()}/USDT",
                    "price": price,
                    "amount": amount,
                    "cost": cost,
                    "fee": fee,
                    "side": "buy",
                    "status": "open",
                    "timestamp": int(time.time()*1000)
                }
                
                Log(f"买入订单创建成功: {order_id}")
                return result
            else:
                # 计算收入和手续费
                revenue = price * amount
                fee = self.get_fee(exchange, coin, False) * revenue  # 假设是taker费率
                
                Log(f"模拟卖出订单: {exchange} 卖出 {amount} {coin.upper()} @ {price} = {revenue} USDT")
                Log(f"预估手续费: {fee} USDT")
                
                # 创建订单响应
                result = {
                    "orderId": order_id,
                    "symbol": f"{coin.upper()}/USDT",
                    "price": price,
                    "amount": amount,
                    "cost": revenue,
                    "fee": fee,
                    "side": "sell",
                    "status": "open",
                    "timestamp": int(time.time()*1000)
                }
                
                Log(f"卖出订单创建成功: {order_id}")
                return result
                    
        except Exception as e:
            Log(f"创建订单时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            return None
            
    def add_pending_order(self, order: Dict[str, Any]):
        """添加挂单"""
        self.pending_orders.append(order)

    def remove_pending_order(self, order_id: str):
        """移除挂单"""
        self.pending_orders = [order for order in self.pending_orders if order['id'] != order_id]

    def get_pending_orders(self, coin: str = None) -> List[Dict[str, Any]]:
        """获取挂单"""
        if coin:
            return [order for order in self.pending_orders if order['coin'] == coin]
        return self.pending_orders

    def update_trade_stats(self, trade_type: str, amount: float, profit: float, fees: float, status: str = 'SUCCESS', count: int = 1):
        """
        更新交易统计

        Args:
            trade_type: 交易类型
            amount: 交易量
            profit: 盈利
            fees: 手续费
            status: 交易状态 ('SUCCESS', 'FAILED', 'PENDING', 'EXECUTED', 'CANCELLED')
            count: 交易次数
        """
        # 调试输出
        Log(f"DEBUG: 更新交易统计 - 类型: {trade_type}, 数量: {amount}, 利润: {profit}, 手续费: {fees}, 状态: {status}")
        
        # 更新总体统计
        self.trade_stats['total_trades'] += count
        self.trade_stats['total_volume'] += abs(amount)
        self.trade_stats['total_fees'] += fees
        self.trade_stats['total_profit'] += profit

        if status in ['SUCCESS', 'EXECUTED']:
            self.trade_stats['success_trades'] += count
            if profit > 0:
                self.trade_stats['max_profit'] = max(self.trade_stats['max_profit'], profit)
            elif profit < 0:
                self.trade_stats['max_loss'] = min(self.trade_stats['max_loss'], profit)
        elif status in ['FAILED', 'CANCELLED']:
            self.trade_stats['failed_trades'] += count

        # 更新按类型统计
        if trade_type not in self.trade_stats:
            self.trade_stats[trade_type] = {
                'count': 0,
                'success': 0,
                'failed': 0,
                'total_volume': 0.0,
                'total_profit': 0.0,
                'total_fees': 0.0,
                'max_profit': float('-inf'),
                'max_loss': float('inf'),
                'avg_profit_per_trade': 0.0
            }

        stats = self.trade_stats[trade_type]
        stats['count'] += count
        stats['total_volume'] += abs(amount)
        stats['total_fees'] += fees
        stats['total_profit'] += profit

        if status in ['SUCCESS', 'EXECUTED']:
            stats['success'] += count
            if profit > 0:
                stats['max_profit'] = max(stats['max_profit'], profit)
            elif profit < 0:
                stats['max_loss'] = min(stats['max_loss'], profit)
        elif status in ['FAILED', 'CANCELLED']:
            stats['failed'] += count

        if stats['count'] > 0:
            stats['avg_profit_per_trade'] = stats['total_profit'] / stats['count']
            
        # 调试输出更新后的统计信息
        Log(f"DEBUG: 更新后的总手续费: {self.trade_stats['total_fees']}")
        Log(f"DEBUG: 更新后的{trade_type}手续费: {stats['total_fees']}")

    def _get_trade_type_name(self, trade_type: str) -> str:
        """获取交易类型的中文名称"""
        # 如果是枚举类型，转换为字符串
        if hasattr(trade_type, 'value'):
            trade_type = trade_type.value
            
        type_names = {
            'HEDGE': '对冲',
            'HEDGE_BUY': '对冲买入',
            'HEDGE_SELL': '对冲卖出',
            'ARBITRAGE': '套利',
            'PENDING': '挂单',
            'PENDING_TRADE': '挂单',
            'BALANCE': '平衡',
            'MIGRATE': '迁移',
            'hedge': '对冲',
            'hedge_buy': '对冲买入',
            'hedge_sell': '对冲卖出',
            'arbitrage': '套利',
            'pending': '挂单',
            'pending_trade': '挂单',
            'balance': '平衡',
            'migrate': '迁移'
        }
        return type_names.get(str(trade_type).lower(), str(trade_type))

    def add_trade_record(self, trade_data: Dict[str, Any]):
        """
        添加交易记录

        Args:
            trade_data: 交易数据
        """
        # 添加时间戳
        if 'timestamp' not in trade_data:
            trade_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        Log(f"DEBUG: Adding trade record to account: {trade_data}")
        
        # 添加到交易记录列表
        self.trade_records.append(trade_data)
        
        Log(f"DEBUG: Trade records count after adding: {len(self.trade_records)}")

        # 如果超过最大记录数，移除最早的记录
        if len(self.trade_records) > self.max_recent_trades:
            self.trade_records = self.trade_records[-self.max_recent_trades:]

        # 确保交易数据包含所需字段
        volume = trade_data.get('trade_value', 0)
        if volume == 0 and 'amount' in trade_data and 'buy_price' in trade_data:
            volume = trade_data['amount'] * trade_data['buy_price']
            
        profit = trade_data.get('net_profit', trade_data.get('profit', 0))
        fees = trade_data.get('total_fees', trade_data.get('fees', 0))
        
        # 更新交易统计
        self.update_trade_stats(
            trade_data['type'],
            volume,
            profit,
            fees,
            trade_data.get('status', 'SUCCESS'),
            trade_data.get('count', 1)
        )

    def get_trade_stats_summary(self) -> str:
        """获取交易统计摘要"""
        summary = ["交易统计摘要:"]
        summary.append(f"总交易次数: {self.trade_stats['total_trades']}")
        if self.trade_stats['total_trades'] > 0:
            success_rate = self.trade_stats['success_trades'] / self.trade_stats['total_trades'] * 100
            summary.append(f"总成功率: {success_rate:.2f}%")
        summary.append(f"总成交量: {self.trade_stats['total_volume']:.4f}")
        summary.append(f"总盈亏: {self.trade_stats['total_profit']:.4f}")
        summary.append(f"总手续费: {self.trade_stats['total_fees']:.4f}")
        summary.append(f"最大单笔盈利: {max(self.trade_stats['max_profit'], 0.0):.4f}")
        summary.append(f"最大单笔亏损: {self.trade_stats['max_loss'] if self.trade_stats['max_loss'] != float('inf') else 0.0:.4f}")

        for trade_type, stats in self.trade_stats.items():
            if isinstance(stats, dict) and 'count' in stats:  # 只处理交易类型统计
                type_name = self._get_trade_type_name(trade_type)
                summary.append(f"\n{type_name}:")
                summary.append(f"  交易次数: {stats['count']}")
                if stats['count'] > 0:
                    success_rate = stats['success'] / stats['count'] * 100
                    summary.append(f"  成功率: {success_rate:.2f}%")
                summary.append(f"  总成交量: {stats['total_volume']:.4f}")
                summary.append(f"  总盈亏: {stats['total_profit']:.4f}")
                summary.append(f"  总手续费: {stats['total_fees']:.4f}")
                summary.append(f"  最大单笔盈利: {max(stats['max_profit'], 0.0):.4f}")
                summary.append(f"  最大单笔亏损: {stats['max_loss'] if stats['max_loss'] != float('inf') else 0.0:.4f}")
                summary.append(f"  平均每笔盈亏: {stats['avg_profit_per_trade']:.4f}")
                
        # 添加取消订单统计摘要
        if hasattr(self, '_cancelled_order_stats') and self._cancelled_order_stats:
            from utils.logger import _N
            
            # 计算总取消次数和数量
            total_cancelled = 0
            total_amount = 0
            normal_count = 0
            reverse_count = 0
            
            for coin, stats in self._cancelled_order_stats.items():
                total_cancelled += stats['total_count']
                total_amount += stats['total_amount']
                normal_count += stats['normal_count']
                reverse_count += stats['reverse_count']
            
            summary.append("\n取消订单统计:")
            summary.append(f"  总取消次数: {total_cancelled}")
            summary.append(f"  总取消数量: {_N(total_amount, 6)}")
            summary.append(f"  正向挂单取消: {normal_count}次")
            summary.append(f"  反向挂单取消: {reverse_count}次")
            
            # 计算总取消率
            from strategy.trade_type import TradeType
            pending_executed = self.trade_stats.get(TradeType.PENDING_TRADE, {}).get('SUCCESS', 0) or 0
            pending_cancelled = self.trade_stats.get(TradeType.PENDING_TRADE, {}).get('CANCELLED', 0) or 0
            reverse_executed = self.trade_stats.get(TradeType.REVERSE_PENDING, {}).get('SUCCESS', 0) or 0
            reverse_cancelled = self.trade_stats.get(TradeType.REVERSE_PENDING, {}).get('CANCELLED', 0) or 0
            
            total_executed = pending_executed + reverse_executed
            total_cancelled_orders = pending_cancelled + reverse_cancelled
            
            if total_executed + total_cancelled_orders > 0:
                cancel_rate = total_cancelled_orders / (total_executed + total_cancelled_orders) * 100
                summary.append(f"  挂单总取消率: {_N(cancel_rate, 2)}%")
                summary.append(f"  挂单总执行次数: {total_executed}")
                summary.append(f"  挂单总取消次数: {total_cancelled_orders}")

        return "\n".join(summary)

    def get_cancelled_order_stats(self, coin: str = None) -> Dict[str, Any]:
        """
        获取取消订单的统计信息
        
        Args:
            coin: 币种名称，如果为None则返回所有币种的统计
            
        Returns:
            Dict[str, Any]: 取消订单统计信息
        """
        if not hasattr(self, '_cancelled_order_stats'):
            self._cancelled_order_stats = {}
            
        if coin:
            # 返回特定币种的统计
            coin = coin.lower()
            return self._cancelled_order_stats.get(coin, {})
        else:
            # 返回所有币种的统计
            return self._cancelled_order_stats
            
    def update_cancelled_order_stats(self, coin: str, amount: float, 
                                    buy_exchange: str, sell_exchange: str, 
                                    is_reverse: bool = False) -> None:
        """
        更新取消订单的统计信息
        
        Args:
            coin: 币种名称
            amount: 数量
            buy_exchange: 买入交易所
            sell_exchange: 卖出交易所
            is_reverse: 是否为反向挂单
        """
        try:
            # 确保统计字典已初始化
            if not hasattr(self, '_cancelled_order_stats'):
                self._cancelled_order_stats = {}
                
            coin = coin.lower()
            
            # 初始化币种统计
            if coin not in self._cancelled_order_stats:
                self._cancelled_order_stats[coin] = {
                    'total_count': 0,
                    'total_amount': 0,
                    'exchanges': {},
                    'reverse_count': 0,
                    'normal_count': 0,
                    'last_cancelled_time': None
                }
            
            # 更新币种总计数据
            self._cancelled_order_stats[coin]['total_count'] += 1
            self._cancelled_order_stats[coin]['total_amount'] += amount
            self._cancelled_order_stats[coin]['last_cancelled_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 更新交易所对数据
            exchange_pair = f"{buy_exchange}->{sell_exchange}"
            if exchange_pair not in self._cancelled_order_stats[coin]['exchanges']:
                self._cancelled_order_stats[coin]['exchanges'][exchange_pair] = {
                    'count': 0,
                    'amount': 0
                }
            
            self._cancelled_order_stats[coin]['exchanges'][exchange_pair]['count'] += 1
            self._cancelled_order_stats[coin]['exchanges'][exchange_pair]['amount'] += amount
            
            # 更新挂单类型计数
            if is_reverse:
                self._cancelled_order_stats[coin]['reverse_count'] += 1
            else:
                self._cancelled_order_stats[coin]['normal_count'] += 1
                
            from utils.logger import Log, _N
            
            # 输出统计信息
            Log(f"未成交挂单统计 - {coin.upper()}:")
            Log(f"总取消次数: {self._cancelled_order_stats[coin]['total_count']}")
            Log(f"总取消数量: {_N(self._cancelled_order_stats[coin]['total_amount'], 6)}")
            Log(f"正向挂单取消: {self._cancelled_order_stats[coin]['normal_count']}次")
            Log(f"反向挂单取消: {self._cancelled_order_stats[coin]['reverse_count']}次")
            
        except Exception as e:
            from utils.logger import Log
            Log(f"更新取消订单统计时出错: {str(e)}")
            import traceback
            Log(traceback.format_exc())
            
    def get_cancelled_order_summary(self, coin: str = None) -> str:
        """
        获取取消订单统计摘要
        
        Args:
            coin: 币种名称，如果为None则返回所有币种的统计摘要
            
        Returns:
            str: 取消订单统计摘要
        """
        from utils.logger import _N
        
        if not hasattr(self, '_cancelled_order_stats'):
            return "无取消订单统计数据"
            
        summary = ["取消订单统计摘要:"]
        
        # 如果指定了币种，只返回该币种的统计
        if coin:
            coin = coin.lower()
            if coin not in self._cancelled_order_stats:
                return f"币种 {coin.upper()} 无取消订单统计数据"
                
            stats = self._cancelled_order_stats[coin]
            summary.append(f"\n币种: {coin.upper()}")
            summary.append(f"总取消次数: {stats['total_count']}")
            summary.append(f"总取消数量: {_N(stats['total_amount'], 6)}")
            summary.append(f"正向挂单取消: {stats['normal_count']}次")
            summary.append(f"反向挂单取消: {stats['reverse_count']}次")
            summary.append(f"最后取消时间: {stats['last_cancelled_time']}")
            
            summary.append("\n交易所对统计:")
            for pair, pair_stats in stats['exchanges'].items():
                summary.append(f"  {pair}: {pair_stats['count']}次, 总量: {_N(pair_stats['amount'], 6)}")
                
            # 计算取消率
            if self.trade_stats:
                from strategy.trade_type import TradeType
                pending_executed = self.trade_stats.get(TradeType.PENDING_TRADE, {}).get('SUCCESS', 0) or 0
                pending_cancelled = self.trade_stats.get(TradeType.PENDING_TRADE, {}).get('CANCELLED', 0) or 0
                reverse_executed = self.trade_stats.get(TradeType.REVERSE_PENDING, {}).get('SUCCESS', 0) or 0
                reverse_cancelled = self.trade_stats.get(TradeType.REVERSE_PENDING, {}).get('CANCELLED', 0) or 0
                
                total_executed = pending_executed + reverse_executed
                total_cancelled_orders = pending_cancelled + reverse_cancelled
                
                if total_executed + total_cancelled_orders > 0:
                    cancel_rate = total_cancelled_orders / (total_executed + total_cancelled_orders) * 100
                    summary.append(f"\n挂单总取消率: {_N(cancel_rate, 2)}%")
                    summary.append(f"挂单总执行次数: {total_executed}")
                    summary.append(f"挂单总取消次数: {total_cancelled_orders}")
        else:
            # 返回所有币种的统计
            total_cancelled = 0
            total_amount = 0
            normal_count = 0
            reverse_count = 0
            
            for coin, stats in self._cancelled_order_stats.items():
                total_cancelled += stats['total_count']
                total_amount += stats['total_amount']
                normal_count += stats['normal_count']
                reverse_count += stats['reverse_count']
                
                summary.append(f"\n币种: {coin.upper()}")
                summary.append(f"  总取消次数: {stats['total_count']}")
                summary.append(f"  总取消数量: {_N(stats['total_amount'], 6)}")
                summary.append(f"  正向挂单取消: {stats['normal_count']}次")
                summary.append(f"  反向挂单取消: {stats['reverse_count']}次")
                summary.append(f"  最后取消时间: {stats['last_cancelled_time']}")
            
            summary.insert(1, f"所有币种总取消次数: {total_cancelled}")
            summary.insert(2, f"所有币种总取消数量: {_N(total_amount, 6)}")
            summary.insert(3, f"所有币种正向挂单取消: {normal_count}次")
            summary.insert(4, f"所有币种反向挂单取消: {reverse_count}次")
            
            # 计算总取消率
            if self.trade_stats:
                from strategy.trade_type import TradeType
                pending_executed = self.trade_stats.get(TradeType.PENDING_TRADE, {}).get('SUCCESS', 0) or 0
                pending_cancelled = self.trade_stats.get(TradeType.PENDING_TRADE, {}).get('CANCELLED', 0) or 0
                reverse_executed = self.trade_stats.get(TradeType.REVERSE_PENDING, {}).get('SUCCESS', 0) or 0
                reverse_cancelled = self.trade_stats.get(TradeType.REVERSE_PENDING, {}).get('CANCELLED', 0) or 0
                
                total_executed = pending_executed + reverse_executed
                total_cancelled_orders = pending_cancelled + reverse_cancelled
                
                if total_executed + total_cancelled_orders > 0:
                    cancel_rate = total_cancelled_orders / (total_executed + total_cancelled_orders) * 100
                    summary.append(f"\n挂单总取消率: {_N(cancel_rate, 2)}%")
                    summary.append(f"挂单总执行次数: {total_executed}")
                    summary.append(f"挂单总取消次数: {total_cancelled_orders}")
                
        return "\n".join(summary)

    def reset_cancelled_order_stats(self, coin: str = None) -> None:
        """
        重置取消订单统计
        
        Args:
            coin: 币种名称，如果为None则重置所有币种的统计
        """
        if not hasattr(self, '_cancelled_order_stats'):
            return
            
        from utils.logger import Log
        
        if coin:
            # 重置特定币种的统计
            coin = coin.lower()
            if coin in self._cancelled_order_stats:
                Log(f"重置 {coin.upper()} 的取消订单统计")
                self._cancelled_order_stats.pop(coin)
        else:
            # 重置所有币种的统计
            Log(f"重置所有币种的取消订单统计")
            self._cancelled_order_stats = {}

    def get_unhedged_position(self, coin: str = None, exchange: str = None) -> Union[
        Dict[str, Dict[str, float]], Dict[str, float], float]:
        """
        获取现货持仓
        
        Args:
            coin: 币种名称，如果为None则返回所有币种
            exchange: 交易所名称，如果为None则返回所有交易所

        Returns:
            Union[Dict[str, Dict[str, float]], Dict[str, float], float]: 现货持仓
        """
        if coin and exchange:
            # 获取特定交易所特定币种的持仓
            coin = coin.lower()
            if exchange not in self.unhedged_positions:
                return 0
            return self.unhedged_positions[exchange].get(coin, 0)
        elif exchange and not coin:
            # 获取特定交易所的所有币种持仓
            if exchange not in self.unhedged_positions:
                return {}
            return self.unhedged_positions[exchange]
        elif coin and not exchange:
            # 获取所有交易所特定币种的持仓
            coin = coin.lower()
            result = {}
            for ex, positions in self.unhedged_positions.items():
                if coin in positions:
                    result[ex] = positions[coin]
            return result
        else:
            # 获取所有交易所所有币种的持仓
            return self.unhedged_positions
            
    async def get_ticker_price(self, coin: str, exchange: str) -> float:
        """
        获取指定币种在指定交易所的当前价格
        
        Args:
            coin: 币种
            exchange: 交易所
            
        Returns:
            float: 当前价格
        """
        try:
            # 标准化币种名称
            coin = coin.upper()
            
            # 导入 fetch_all_depths_compat 函数
            from utils.depth_data import fetch_all_depths_compat
            
            # 获取交易所实例
            exchange_instance = self.get_exchange_instance(exchange)
            if not exchange_instance:
                from utils.logger import Log
                Log(f"❌ 无法获取交易所 {exchange} 实例")
                return 0.0
            
            # 创建交易所字典
            exchanges_dict = {exchange: exchange_instance}
            
            # 创建支持的交易所字典
            supported_exchanges_dict = {coin: [exchange]}
            
            # 使用 fetch_all_depths_compat 获取深度数据
            depths = await fetch_all_depths_compat(
                coin=coin,
                exchanges=exchanges_dict,
                supported_exchanges=supported_exchanges_dict,
                config=self.config
            )
            
            # 检查是否成功获取深度数据
            if coin in depths and exchange in depths[coin]:
                depth_data = depths[coin][exchange]
                if 'asks' in depth_data and 'bids' in depth_data and depth_data['asks'] and depth_data['bids']:
                    # 计算中间价格
                    ask_price = depth_data['asks'][0][0]
                    bid_price = depth_data['bids'][0][0]
                    mid_price = (ask_price + bid_price) / 2
                    
                    from utils.logger import Log
                    Log(f"从深度数据获取 {exchange} 的 {coin} 价格: {mid_price}")
                    return mid_price
            
            # 如果无法通过 fetch_all_depths_compat 获取价格，尝试使用缓存
            from utils.logger import Log
            Log(f"无法通过 fetch_all_depths_compat 获取价格，尝试使用缓存")
            
            # 从缓存中获取深度数据
            from utils.cache_manager import depth_cache
            cached_depth = depth_cache.get(exchange, coin)
            
            if cached_depth and cached_depth.get('asks') and cached_depth.get('bids'):
                # 使用缓存的深度数据计算中间价
                mid_price = (cached_depth['asks'][0][0] + cached_depth['bids'][0][0]) / 2
                Log(f"从缓存获取 {exchange} {coin} 价格: {mid_price}")
                return mid_price
            
            # 如果缓存中没有数据，再次尝试使用 fetch_all_depths_compat 但使用不同的参数
            Log(f"缓存中没有数据，再次尝试使用 fetch_all_depths_compat")
            
            # 尝试使用更宽松的参数
            try:
                # 获取所有支持的交易所
                all_supported_exchanges = self.config.get('supported_exchanges', {}).get(coin, [])
                if exchange in all_supported_exchanges:
                    # 创建新的支持的交易所字典，包含更多交易所
                    wider_supported_exchanges_dict = {coin: all_supported_exchanges}
                    
                    # 再次调用 fetch_all_depths_compat
                    wider_depths = await fetch_all_depths_compat(
                        coin=coin,
                        exchanges=exchanges_dict,
                        supported_exchanges=wider_supported_exchanges_dict,
                        config=self.config
                    )
                    
                    # 检查是否成功获取深度数据
                    if coin in wider_depths and exchange in wider_depths[coin]:
                        depth_data = wider_depths[coin][exchange]
                        if 'asks' in depth_data and 'bids' in depth_data and depth_data['asks'] and depth_data['bids']:
                            # 计算中间价格
                            ask_price = depth_data['asks'][0][0]
                            bid_price = depth_data['bids'][0][0]
                            mid_price = (ask_price + bid_price) / 2
                            
                            Log(f"从更宽松的深度数据获取 {exchange} 的 {coin} 价格: {mid_price}")
                            return mid_price
            except Exception as e:
                Log(f"使用更宽松参数获取深度数据失败: {str(e)}")
            
            # 如果所有方法都失败，使用交易所API直接获取
            Log(f"所有方法都失败，尝试使用交易所API直接获取")
            try:
                depth = await exchange_instance.GetDepth(coin)
                if depth and hasattr(depth, 'Asks') and hasattr(depth, 'Bids') and depth.Asks and depth.Bids:
                    # 使用买一卖一的中间价
                    mid_price = (depth.Asks[0][0] + depth.Bids[0][0]) / 2
                    Log(f"从交易所API获取 {exchange} {coin} 价格: {mid_price}")
                    
                    # 更新缓存
                    depth_data = {
                        'asks': [(ask[0], ask[1]) for ask in depth.Asks],
                        'bids': [(bid[0], bid[1]) for bid in depth.Bids]
                    }
                    depth_cache.set(exchange, coin, depth_data)
                    
                    # 同时更新 fetch_all_depths_compat 的缓存
                    if coin not in depths:
                        depths[coin] = {}
                    depths[coin][exchange] = depth_data
                    
                    return mid_price
            except Exception as e:
                Log(f"使用交易所API获取价格失败: {str(e)}")
            
            # 如果所有方法都失败，返回0
            Log(f"❌ 无法获取 {exchange} 的 {coin} 价格")
            return 0.0
        except Exception as e:
            from utils.logger import Log
            import traceback
            Log(f"❌ 获取 {exchange} 的 {coin} 价格时出错: {str(e)}")
            Log(traceback.format_exc())
            return 0.0
            
    def get_exchange_instance(self, exchange: str):
        """
        获取交易所实例
        
        Args:
            exchange: 交易所名称
            
        Returns:
            交易所实例
        """
        try:
            # 检查交易所是否已初始化
            if not hasattr(self, '_exchange_instances'):
                self._exchange_instances = {}
                
            # 如果交易所实例已存在，直接返回
            if exchange in self._exchange_instances:
                return self._exchange_instances[exchange]
                
            # 否则创建新的交易所实例
            from exchanges import ExchangeFactory
            exchange_instance = ExchangeFactory.get_exchange(exchange)
            
            if exchange_instance:
                # 缓存交易所实例
                self._exchange_instances[exchange] = exchange_instance
                return exchange_instance
            else:
                from utils.logger import Log
                Log(f"❌ 无法创建交易所 {exchange} 实例")
                return None
        except Exception as e:
            from utils.logger import Log
            import traceback
            Log(f"❌ 获取交易所 {exchange} 实例时出错: {str(e)}")
            Log(traceback.format_exc())
            return None

    async def spot_buy(self, exchange: str, coin: str, amount: float, price: float) -> bool:
        """
        在现货交易所买入
        
        Args:
            exchange: 交易所名称
            coin: 币种
            amount: 数量
            price: 价格
            
        Returns:
            bool: 是否成功
        """
        try:
            # 获取手续费率
            fee_rate = self.get_fee(exchange, 'taker')
            cost = amount * price
            fee = cost * fee_rate
            total_cost = cost + fee
            
            # 检查USDT余额是否足够（包含手续费）
            usdt_balance = self.get_balance('usdt', exchange)
            if usdt_balance < total_cost:
                Log(f"{exchange} USDT余额不足: 需要 {total_cost}(含手续费{fee}), 实际 {usdt_balance}")
                return False
            
            # 扣除USDT余额（包含手续费）
            self.update_balance('usdt', -total_cost, exchange)
            
            # 增加币种余额
            self.update_balance(coin, amount, exchange)
            
            # 更新未对冲持仓
            self.update_unhedged_position(coin, amount, exchange, True)
            
            Log(f"{exchange} 买入 {amount} {coin} @ {price}, 花费 {cost} USDT, 手续费 {fee} USDT")
            return True
        except Exception as e:
            Log(f"{exchange} 买入失败: {str(e)}")
            return False
        
    async def spot_sell(self, exchange: str, coin: str, amount: float, price: float) -> bool:
        """
        在现货交易所卖出
        
        Args:
            exchange: 交易所名称
            coin: 币种
            amount: 数量
            price: 价格
            
        Returns:
            bool: 是否成功
        """
        try:
            # 获取手续费率
            fee_rate = self.get_fee(exchange, 'taker')
            revenue = amount * price
            fee = revenue * fee_rate
            net_revenue = revenue - fee
            
            # 检查币种余额是否足够
            coin_balance = self.get_balance(coin, exchange)
            if coin_balance < amount:
                Log(f"{exchange} {coin}余额不足: 需要 {amount}, 实际 {coin_balance}")
                return False
            
            # 扣除币种余额
            self.update_balance(coin, -amount, exchange)
            
            # 更新未对冲持仓
            self.update_unhedged_position(coin, amount, exchange, False)
            
            # 增加USDT余额（扣除手续费）
            self.update_balance('usdt', net_revenue, exchange)
            
            Log(f"{exchange} 卖出 {amount} {coin} @ {price}, 获得 {net_revenue} USDT, 手续费 {fee} USDT")
            return True
        except Exception as e:
            Log(f"{exchange} 卖出失败: {str(e)}")
            return False

    def get_total_asset_value(self, prices: Dict[str, float]) -> float:
        """
        计算总资产价值（USDT）
        
        Args:
            prices: 各币种当前价格，格式: {'btc': 50000.0, 'eth': 3000.0}
            
        Returns:
            float: 总资产价值（USDT）
        """
        total_value = 0.0
        
        # 计算所有USDT余额
        usdt_balance = sum(self.balances['usdt'].values())
        total_value += usdt_balance
        Log(f"DEBUG: USDT总余额: {usdt_balance}")
        
        # 计算所有币种价值
        for exchange, balances in self.balances['stocks'].items():
            exchange_value = 0.0
            for coin, amount in balances.items():
                if amount > 0 and coin.upper() in prices:
                    price = prices[coin.upper()]
                    coin_value = amount * price
                    exchange_value += coin_value
                    Log(f"DEBUG: {exchange} {coin.upper()} 持仓价值: {coin_value} USDT (数量: {amount}, 价格: {price})")
            total_value += exchange_value
            Log(f"DEBUG: {exchange} 交易所总持仓价值: {exchange_value} USDT")
        
        Log(f"DEBUG: 总资产价值: {total_value} USDT")
        return total_value

    def get_trade_stats(self) -> Dict[str, Any]:
        """获取交易统计"""
        return self.trade_stats
        
    def get_trade_stats_with_cancelled(self) -> Dict[str, Any]:
        """获取包含取消订单统计的交易统计"""
        stats = self.get_trade_stats()
        
        # 添加取消订单统计
        if hasattr(self, '_cancelled_order_stats'):
            stats['cancelled_orders'] = self._cancelled_order_stats
            
        return stats