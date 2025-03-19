import pytest
import pytest_asyncio
from typing import Dict
from datetime import datetime

from utils.logger import Log
from utils.simulated_account import SimulatedAccount
from exchanges.base import OrderBook

# 测试配置数据
TEST_CONFIG = {
    'strategy': {
        'COINS': ['BTC', 'ETH'],  # 测试两个币种
        'MIN_AMOUNT': 0.001,
        'SAFE_PRICE': 100,
        'MAX_TRADE_PRICE': 500,
        'FUTURES_MARGIN_RATE': 0.1
    },
        'exchanges': {
        'MEXC': {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        },
        'HTX': {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        },
        'Futures_MEXC': {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        },
        'OKX': {
            'api_key': '',
            'api_secret': '',
            'passphrase': '',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        },
        'CoinEx': {
            'api_key': '',
            'api_secret': '',
            'default_fees': {
                'maker': 0.002,
                'taker': 0.002
            }
        },
        'Bybit': {
            'api_key': '',
            'api_secret': '',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        },
        'Gate': {
            'api_key': '',
            'api_secret': '',
            'default_fees': {
                'maker': 0.002,
                'taker': 0.002
            }
        },
        'Bitget': {
            'api_key': '',
            'api_secret': '',
            'passphrase': '',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        },
        'BINANCE': {
            'api_key': '',
            'api_secret': '',
            'default_fees': {
                'maker': 0.001,
                'taker': 0.001
            }
        }
    },
    'supported_exchanges': {
        'BTC': ['MEXC', 'HTX'],
        'ETH': ['MEXC', 'HTX']
    }
}

class MockAccount:
    def __init__(self, initial_balance: float = 10000):
        self.initial_balance = initial_balance
        self.balances = {
            'usdt': {'Exchange1': initial_balance/2, 'Exchange2': initial_balance/2},
            'stocks': {
                'Exchange1': {'btc': 0.0, 'eth': 0.0},
                'Exchange2': {'btc': 0.0, 'eth': 0.0}
            }
        }
        self.frozen_balances = {
            'usdt': {'Exchange1': 0, 'Exchange2': 0},
            'stocks': {
                'Exchange1': {'btc': 0.0, 'eth': 0.0},
                'Exchange2': {'btc': 0.0, 'eth': 0.0}
            }
        }
        self.trade_records = []
        self.exchanges = {}

    async def _initialize_coin_balances(self):
        """模拟初始化币种余额"""
        # 为每个交易所分配一些币种
        for exchange in ['Exchange1', 'Exchange2']:
            # 获取该交易所的USDT余额
            usdt_balance = self.balances['usdt'][exchange]
            
            # 将USDT平均分配给BTC和ETH
            btc_usdt = usdt_balance * 0.4  # 40% 用于购买BTC
            eth_usdt = usdt_balance * 0.4  # 40% 用于购买ETH
            # 保留20%作为USDT
            
            # 模拟购买BTC
            btc_price = 50000
            btc_amount = btc_usdt / btc_price
            btc_fee = btc_usdt * 0.001  # 0.1% 手续费
            
            # 模拟购买ETH
            eth_price = 3000
            eth_amount = eth_usdt / eth_price
            eth_fee = eth_usdt * 0.001  # 0.1% 手续费
            
            # 更新余额
            self.balances['stocks'][exchange]['btc'] = btc_amount
            self.balances['stocks'][exchange]['eth'] = eth_amount
            self.balances['usdt'][exchange] = usdt_balance - btc_usdt - eth_usdt - btc_fee - eth_fee

class MockExchange:
    """模拟交易所类"""
    def __init__(self, name: str, prices: Dict[str, float]):
        self.name = name
        self.prices = prices

    async def GetDepth(self, coin: str) -> OrderBook:
        """模拟获取深度数据"""
        price = self.prices.get(coin, 1000)  # 默认价格1000
        return OrderBook(
            Asks=[(price, 1.0)],
            Bids=[(price * 0.999, 1.0)]
        )

    async def GetFee(self, coin: str, is_maker: bool = False) -> float:
        """模拟获取费率"""
        return 0.001 if is_maker else 0.002

@pytest_asyncio.fixture
async def account():
    """创建测试账户实例"""
    acc = SimulatedAccount(initial_balance=10000, config=TEST_CONFIG)
    
    # 获取所有交易所
    all_exchanges = set()
    for exchanges in TEST_CONFIG['supported_exchanges'].values():
        all_exchanges.update(exchanges)
    
    # 分类现货和期货交易所
    spot_exchanges = [ex for ex in all_exchanges if 'futures' not in ex.lower()]
    futures_exchanges = [ex for ex in all_exchanges if 'futures' in ex.lower()]
    
    # 计算每个现货和期货交易所的初始余额
    total_spot_balance = acc.initial_balance * 0.7  # 70%给现货
    total_futures_balance = acc.initial_balance * 0.3  # 30%给期货
    
    # 计算每个交易所的初始余额
    spot_balance_per_exchange = total_spot_balance / len(spot_exchanges) if spot_exchanges else 0
    futures_balance_per_exchange = total_futures_balance / len(futures_exchanges) if futures_exchanges else 0
    
    # 初始化USDT余额
    acc.balances['usdt'] = {}
    for exchange in all_exchanges:
        # 初始化交易所
        acc.initialize_exchange(exchange)
        # 设置初始余额
        if 'futures' in exchange.lower():
            acc.balances['usdt'][exchange] = futures_balance_per_exchange
        else:
            acc.balances['usdt'][exchange] = spot_balance_per_exchange
    
    # 初始化币种余额字典
    acc.balances['stocks'] = {exchange: {} for exchange in all_exchanges}
    
    # 初始化冻结余额字典
    acc.frozen_balances = {
        'usdt': {exchange: 0 for exchange in all_exchanges},
        'stocks': {exchange: {} for exchange in all_exchanges}
    }
    
    print(f"\n初始资金分配:")
    print(f"总初始资金: {acc.initial_balance:.2f} USDT")
    print(f"现货总资金: {total_spot_balance:.2f} USDT ({len(spot_exchanges)}个交易所，每个{spot_balance_per_exchange:.2f} USDT)")
    print(f"期货总资金: {total_futures_balance:.2f} USDT ({len(futures_exchanges)}个交易所，每个{futures_balance_per_exchange:.2f} USDT)")
    for exchange in all_exchanges:
        print(f"{exchange}: {acc.balances['usdt'][exchange]:.2f} USDT")
    
    yield acc

@pytest.mark.asyncio
async def test_initialize_coin_balances_basic(monkeypatch):
    """测试基本功能，验证资金流向和总资产平衡"""
    # 准备测试数据
    initial_balance = 10000  # 初始资金10000 USDT
    account = MockAccount(initial_balance=initial_balance)
    
    # 设置固定的币种价格，便于计算
    depths = {
        'BTC': {
            'Exchange1': {'asks': [(50000, 1.0)], 'bids': [(49900, 1.0)]},
            'Exchange2': {'asks': [(50100, 1.0)], 'bids': [(50000, 1.0)]}
        },
        'ETH': {
            'Exchange1': {'asks': [(3000, 1.0)], 'bids': [(2990, 1.0)]},
            'Exchange2': {'asks': [(3010, 1.0)], 'bids': [(3000, 1.0)]}
        }
    }
    timestamp = datetime.now()
    config = {
        'strategy': {
            'COINS': ['BTC', 'ETH'],
            'FUTURES_MARGIN_RATE': 0.1
        },
        'supported_exchanges': {
            'BTC': ['Exchange1', 'Exchange2'],
            'ETH': ['Exchange1', 'Exchange2']
        }
    }

    # 记录初始状态
    print(f"\n初始资金: {initial_balance} USDT")
    
    # 执行初始化
    await account._initialize_coin_balances()
    
    # 验证每个交易所的资金分配
    total_remaining_usdt = 0
    total_coin_value = 0
    total_fees = 0
    
    for exchange in ['Exchange1', 'Exchange2']:
        # 获取剩余USDT
        remaining_usdt = account.balances['usdt'][exchange]
        total_remaining_usdt += remaining_usdt
        print(f"\n{exchange} 剩余USDT: {remaining_usdt:.4f}")
        
        # 计算币种价值和手续费
        for coin, price_data in depths.items():
            coin_amount = account.balances['stocks'][exchange].get(coin.lower(), 0)
            coin_price = price_data[exchange]['asks'][0][0]  # 使用卖一价作为当前价格
            coin_value = coin_amount * coin_price
            
            # 计算购买这些币所花费的手续费（假设费率0.1%）
            fee = coin_value * 0.001
            total_fees += fee
            total_coin_value += coin_value
            
            print(f"{exchange} {coin}:")
            print(f"  数量: {coin_amount:.8f}")
            print(f"  价格: {coin_price:.2f}")
            print(f"  价值: {coin_value:.4f}")
            print(f"  手续费: {fee:.4f}")
    
    # 计算总资产价值
    total_asset_value = total_remaining_usdt + total_coin_value
    
    print(f"\n资产统计:")
    print(f"总剩余USDT: {total_remaining_usdt:.4f}")
    print(f"总币种价值: {total_coin_value:.4f}")
    print(f"总手续费: {total_fees:.4f}")
    print(f"总资产价值: {total_asset_value:.4f}")
    print(f"初始资金: {initial_balance:.4f}")
    print(f"资产差值: {(total_asset_value - initial_balance):.4f}")
    
    # 验证总资产是否与初始资金相近（考虑手续费的影响）
    asset_difference = abs(total_asset_value - initial_balance)
    max_allowed_difference = initial_balance * 0.002  # 允许0.2%的误差
    
    assert asset_difference <= max_allowed_difference, \
        f"资产差值 ({asset_difference:.4f}) 超过允许范围 ({max_allowed_difference:.4f})"
    
    # 验证手续费是否在合理范围内
    expected_max_fee_rate = 0.002  # 假设每个交易的手续费率是0.1%，考虑买入和卖出
    max_expected_fees = initial_balance * expected_max_fee_rate
    
    assert total_fees <= max_expected_fees, \
        f"总手续费 ({total_fees:.4f}) 超过预期最大值 ({max_expected_fees:.4f})"
    
    # 验证每个交易所的余额分配是否合理
    for exchange in ['Exchange1', 'Exchange2']:
        # 验证USDT余额非负
        assert account.balances['usdt'][exchange] >= 0, \
            f"{exchange} USDT余额为负: {account.balances['usdt'][exchange]:.4f}"
        
        # 验证币种余额非负
        for coin in ['btc', 'eth']:
            assert account.balances['stocks'][exchange].get(coin, 0) >= 0, \
                f"{exchange} {coin}余额为负: {account.balances['stocks'][exchange].get(coin, 0):.8f}"
        
        # 验证该交易所的总资产价值在合理范围内
        exchange_usdt = account.balances['usdt'][exchange]
        exchange_coin_value = sum(
            account.balances['stocks'][exchange].get(coin.lower(), 0) * 
            depths[coin.upper()][exchange]['asks'][0][0]
            for coin in ['BTC', 'ETH']
        )
        exchange_total_value = exchange_usdt + exchange_coin_value
        
        # 每个交易所的资产应该接近初始资金的一半（允许5%的误差）
        expected_exchange_value = initial_balance / 2
        exchange_value_difference = abs(exchange_total_value - expected_exchange_value)
        max_exchange_difference = expected_exchange_value * 0.05
        
        assert exchange_value_difference <= max_exchange_difference, \
            f"{exchange}资产价值 ({exchange_total_value:.4f}) 与预期值 ({expected_exchange_value:.4f}) 相差过大"

@pytest.mark.asyncio
async def test_initialize_coin_balances_with_different_prices(account):
    """测试不同价格下的币种余额初始化"""
    # 设置不同交易所不同价格，使用更接近的价格比率
    account.exchanges = {
        'MEXC': MockExchange('MEXC', {'BTC': 50000, 'ETH': 2500}),  # 20:1 ratio
        'HTX': MockExchange('HTX', {'BTC': 50100, 'ETH': 2510})     # 20:1 ratio
    }

    # 执行初始化
    await account._initialize_coin_balances()

    # 验证余额分配是否合理
    for exchange in ['MEXC', 'HTX']:
        btc_balance = account.balances['stocks'][exchange].get('btc', 0)
        eth_balance = account.balances['stocks'][exchange].get('eth', 0)
        
        # 计算每个币种的价值
        btc_value = btc_balance * 50000  # 使用基准价格
        eth_value = eth_balance * 2500   # 使用基准价格
        
        # 计算总价值
        total_value = btc_value + eth_value
        
        # 验证每个币种的价值占比是否接近50%（允许20%的误差）
        if total_value > 0:
            btc_ratio = btc_value / total_value
            eth_ratio = eth_value / total_value
            assert abs(btc_ratio - 0.5) < 0.2, f"{exchange} BTC ratio: {btc_ratio}"
            assert abs(eth_ratio - 0.5) < 0.2, f"{exchange} ETH ratio: {eth_ratio}"

@pytest.mark.asyncio
async def test_initialize_coin_balances_with_fees(account):
    """测试考虑手续费的币种余额初始化"""
    # 设置模拟交易所，使用实际执行价格
    prices = {'BTC': 49975.0, 'ETH': 2998.5}
    account.exchanges = {
        'MEXC': MockExchange('MEXC', prices),
        'HTX': MockExchange('HTX', prices)
    }

    # 设置初始USDT余额
    initial_usdt = account.initial_balance

    # 执行初始化
    await account._initialize_coin_balances()

    # 计算所有花费的USDT（包括手续费）
    total_spent_usdt = initial_usdt - sum(account.balances['usdt'].values())
    
    # 计算每个交易所中币种的总价值
    total_coin_value = 0
    total_fees = 0
    for exchange in ['MEXC', 'HTX']:
        exchange_value = 0
        for coin, price in prices.items():
            coin_amount = account.balances['stocks'][exchange].get(coin.lower(), 0)
            coin_value = coin_amount * price
            total_coin_value += coin_value
            exchange_value += coin_value
            # 计算手续费（0.1%的交易费率）
            if coin_amount > 0:
                fee = coin_value * 0.001
                total_fees += fee
            print(f"{exchange} {coin} 数量: {coin_amount:.8f}, 价值: {coin_value:.2f} USDT")
        print(f"{exchange} 总价值: {exchange_value:.2f} USDT")
    
    # 计算当前总资产价值（USDT + 币种价值）
    current_usdt = sum(account.balances['usdt'].values())
    total_asset_value = current_usdt + total_coin_value
    
    print(f"\n资产统计:")
    print(f"初始USDT: {initial_usdt:.2f}")
    print(f"当前USDT: {current_usdt:.2f}")
    print(f"花费的USDT: {total_spent_usdt:.2f}")
    print(f"币种总价值: {total_coin_value:.2f}")
    print(f"当前总资产: {total_asset_value:.2f}")
    print(f"实际手续费: {total_fees:.2f}")
    
    # 验证总资产价值与初始资金的差异不超过预期的手续费范围
    # 由于每个交易的手续费率是0.1%，总共4笔交易
    expected_max_fee_rate = 0.004  # 0.1% * 4
    max_expected_fees = initial_usdt * expected_max_fee_rate
    assert total_fees > 0  # 手续费应该是正数
    assert total_fees <= max_expected_fees  # 手续费不应超过预期最大值
    
    # 验证花费的USDT不超过初始余额
    assert total_spent_usdt <= initial_usdt
    
    # 验证每个交易所的余额分配是否考虑了手续费
    for exchange in ['MEXC', 'HTX']:
        remaining_usdt = account.balances['usdt'][exchange]
        assert remaining_usdt >= 0  # 确保没有透支

@pytest.mark.asyncio
async def test_initialize_coin_balances_error_handling(account):
    """测试错误处理情况"""
    class ErrorExchange(MockExchange):
        def __init__(self, name: str, prices: Dict[str, float]):
            super().__init__(name, prices)
            self.depth_calls = 0
            self.max_failures = 2  # 前两次调用失败

        async def GetDepth(self, coin: str) -> OrderBook:
            self.depth_calls += 1
            if self.depth_calls <= self.max_failures:
                # 记录错误但继续执行
                Log(f"获取{coin}深度数据失败")
                # 返回空的深度数据而不是抛出异常
                return OrderBook([], [])
            return await super().GetDepth(coin)

    # 设置一个正常交易所和一个异常交易所
    mexc_exchange = MockExchange('MEXC', {'BTC': 50000, 'ETH': 2500})
    htx_exchange = ErrorExchange('HTX', {'BTC': 50100, 'ETH': 2510})
    
    account.exchanges = {
        'MEXC': mexc_exchange,
        'HTX': htx_exchange
    }

    # 记录初始余额
    initial_mexc_balance = account.balances['usdt']['MEXC']
    initial_htx_balance = account.balances['usdt']['HTX']

    # 执行初始化
    await account._initialize_coin_balances()

    # 验证正常交易所的余额是否正确初始化
    assert account.balances['usdt']['MEXC'] < initial_mexc_balance  # MEXC应该有余额变化
    assert 'btc' in account.balances['stocks']['MEXC']
    assert 'eth' in account.balances['stocks']['MEXC']
    assert account.balances['stocks']['MEXC']['btc'] > 0
    assert account.balances['stocks']['MEXC']['eth'] > 0

    # 验证异常交易所的处理
    # 由于返回空深度数据，HTX可能会尝试使用其他交易所的价格进行初始化
    assert account.balances['usdt']['HTX'] <= initial_htx_balance  # HTX余额不应超过初始值
    
    # 再次执行初始化（这次HTX的GetDepth应该成功）
    await account._initialize_coin_balances()

    # 验证HTX是否成功处理了新的深度数据
    assert account.balances['usdt']['HTX'] < initial_htx_balance  # HTX应该有余额变化
    assert account.balances['stocks']['HTX'].get('btc', 0) > 0  # 应该有BTC余额
    assert account.balances['stocks']['HTX'].get('eth', 0) > 0  # 应该有ETH余额

    # 验证最终的余额分布是否合理
    final_mexc_btc_value = account.balances['stocks']['MEXC']['btc'] * 50000
    final_htx_btc_value = account.balances['stocks']['HTX']['btc'] * 50100
    assert abs(final_mexc_btc_value - final_htx_btc_value) / final_mexc_btc_value < 0.2  # 允许20%的差异

@pytest.mark.asyncio
async def test_initialize_coin_balances_concurrent_execution(account):
    """测试并发执行性能"""
    import time

    # 添加更多的币种和交易所来测试并发性能
    large_config = TEST_CONFIG.copy()
    large_config['strategy']['COINS'] = ['BTC', 'ETH', 'XRP', 'DOGE', 'LTC']
    large_config['supported_exchanges']['XRP'] = ['MEXC', 'HTX']
    large_config['supported_exchanges']['DOGE'] = ['MEXC', 'HTX']
    large_config['supported_exchanges']['LTC'] = ['MEXC', 'HTX']

    account.config = large_config
    prices = {
        'BTC': 50000, 'ETH': 3000, 'XRP': 1,
        'DOGE': 0.1, 'LTC': 100
    }
    account.exchanges = {
        'MEXC': MockExchange('MEXC', prices),
        'HTX': MockExchange('HTX', prices)
    }

    # 记录开始时间
    start_time = time.time()

    # 执行初始化
    await account._initialize_coin_balances()

    # 记录结束时间
    end_time = time.time()
    execution_time = end_time - start_time

    # 验证执行时间是否在合理范围内（例如小于2秒）
    assert execution_time < 2.0

    # 验证所有币种是否都被正确初始化
    for coin in large_config['strategy']['COINS']:
        for exchange in ['MEXC', 'HTX']:
            assert coin.lower() in account.balances['stocks'][exchange]

@pytest.mark.asyncio
async def test_initialize_coin_balances_balance_distribution(account):
    """测试余额分配的均衡性"""
    # 设置模拟交易所
    prices = {'BTC': 50000, 'ETH': 3000}
    account.exchanges = {
        'MEXC': MockExchange('MEXC', prices),
        'HTX': MockExchange('HTX', prices)
    }

    # 执行初始化
    await account._initialize_coin_balances()

    # 计算每个交易所的总资产价值
    exchange_values = {}
    for exchange in ['MEXC', 'HTX']:
        usdt_value = account.balances['usdt'][exchange]
        btc_value = account.balances['stocks'][exchange]['btc'] * prices['BTC']
        eth_value = account.balances['stocks'][exchange]['eth'] * prices['ETH']
        exchange_values[exchange] = usdt_value + btc_value + eth_value

    # 验证交易所之间的资产分配是否均衡
    mexc_value = exchange_values['MEXC']
    htx_value = exchange_values['HTX']
    # 允许10%的差异
    assert abs(mexc_value - htx_value) / mexc_value < 0.1

if __name__ == '__main__':
    pytest.main(['-v', 'test_initialize_coin_balances.py']) 