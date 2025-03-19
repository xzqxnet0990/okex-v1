import pytest
import pytest_asyncio
from datetime import datetime
from typing import Dict, Any
from utils.logger import log_simulation_status
from utils.cache_manager import depth_cache
import time

class MockAccount:
    def __init__(self, initial_balance: float = 10000):
        self.initial_balance = initial_balance
        self.balances = {
            'usdt': {'Exchange1': 5000, 'Exchange2': 5000},
            'stocks': {
                'Exchange1': {'btc': 0.1, 'eth': 1.0},
                'Exchange2': {'btc': 0.2, 'eth': 2.0}
            }
        }
        self.frozen_balances = {
            'usdt': {'Exchange1': 100, 'Exchange2': 200},
            'stocks': {
                'Exchange1': {'btc': 0.01, 'eth': 0.1},
                'Exchange2': {'btc': 0.02, 'eth': 0.2}
            }
        }
        self.trade_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'total_trades': 0,
            'success_trades': 0,
            'failed_trades': 0,
            'total_volume': 0.0,
            'total_profit': 0.0,
            'total_fees': 0.0,
            'max_profit': float('-inf'),
            'max_loss': 0,
            'trade_types': {}
        }
        self.trade_records = []
        self.exchanges = {'Exchange1': {}, 'Exchange2': {}}
        self.fee_cache = {'Exchange1': {'btc': 0.001, 'eth': 0.001}, 'Exchange2': {'btc': 0.002, 'eth': 0.002}}

    def get_balance(self, coin: str, exchange: str = None) -> float:
        if coin == 'usdt':
            if exchange:
                return self.balances.get('usdt', {}).get(exchange, 0)
            return sum(self.balances.get('usdt', {}).values())
        else:
            if exchange:
                return self.balances.get('stocks', {}).get(exchange, {}).get(coin, 0)
            return sum(self.balances.get('stocks', {}).get(ex, {}).get(coin, 0) for ex in self.balances.get('stocks', {}))

    def get_freeze_balance(self, coin: str, exchange: str) -> float:
        if coin == 'usdt':
            return self.frozen_balances.get('usdt', {}).get(exchange, 0)
        else:
            return self.frozen_balances.get('stocks', {}).get(exchange, {}).get(coin, 0)

    def get_unhedged_position(self, coin: str, exchange: str) -> float:
        if 'futures' in exchange.lower():
            return -0.1  # 模拟空单
        return 0.1  # 模拟多单
        
    def get_pending_orders(self):
        return []
        
    async def _get_estimated_price(self, coin: str) -> float:
        # 模拟获取价格
        if coin == 'BTC':
            return 50000.0
        elif coin == 'ETH':
            return 3000.0
        return 1.0

    def update_trade_stats(self, trade_type: str, amount: float, profit: float, fees: float, status: str = 'SUCCESS', count: int = 1):
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
            if profit < 0:
                self.trade_stats['max_loss'] = min(self.trade_stats['max_loss'], profit)

        # 更新按类型统计
        if trade_type not in self.trade_stats['trade_types']:
            self.trade_stats['trade_types'][trade_type] = {
                'count': 0,
                'success': 0,
                'failed': 0,
                'total_trades': 0,
                'success_trades': 0,
                'failed_trades': 0,
                'total_volume': 0.0,
                'total_profit': 0.0,
                'total_fees': 0.0,
                'max_profit': float('-inf'),
                'max_loss': float('inf'),
                'avg_profit_per_trade': 0.0
            }

        stats = self.trade_stats['trade_types'][trade_type]
        stats['count'] += count
        stats['total_trades'] += count
        stats['total_volume'] += abs(amount)
        stats['total_fees'] += fees
        stats['total_profit'] += profit

        if status in ['SUCCESS', 'EXECUTED']:
            stats['success'] += count
            stats['success_trades'] += count
            if profit > 0:
                stats['max_profit'] = max(stats['max_profit'], profit)
            elif profit < 0:
                stats['max_loss'] = min(stats['max_loss'], profit)
        elif status in ['FAILED', 'CANCELLED']:
            stats['failed'] += count
            stats['failed_trades'] += count
            if profit < 0:
                stats['max_loss'] = min(stats['max_loss'], profit)

        if stats['count'] > 0:
            stats['avg_profit_per_trade'] = stats['total_profit'] / stats['count']

class MockDepth:
    def __init__(self, price: float = 50000):
        self.asks = [(price, 1.0)]
        self.bids = [(price * 0.999, 1.0)]

@pytest_asyncio.fixture
async def mock_web_server():
    class MockWebServer:
        async def broadcast(self, data):
            print("Broadcasting data:", data)
            return True
    return MockWebServer()

@pytest_asyncio.fixture
async def account():
    """创建测试账户实例"""
    return MockAccount()

@pytest.mark.asyncio
async def test_log_simulation_status_basic(monkeypatch):
    """测试基本功能"""
    # 准备测试数据
    account = MockAccount()
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
            'BTC': ['Exchange1', 'Exchange2', 'Futures_Exchange1'],
            'ETH': ['Exchange1', 'Exchange2', 'Futures_Exchange1']
        }
    }

    # 模拟 web_server
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 执行测试
    await log_simulation_status(account, depths, timestamp, config)

@pytest.mark.asyncio
async def test_log_simulation_status_empty_data():
    """测试空数据处理"""
    account = MockAccount(initial_balance=0)
    depths = {}
    timestamp = datetime.now()
    config = {
        'strategy': {
            'COINS': [],
            'FUTURES_MARGIN_RATE': 0.1
        },
        'supported_exchanges': {}
    }

    await log_simulation_status(account, depths, timestamp, config)

@pytest.mark.asyncio
async def test_log_simulation_status_error_handling():
    """测试错误处理"""
    account = MockAccount()
    depths = {
        'BTC': {
            'Exchange1': {'asks': [], 'bids': []},  # 空深度数据
            'Exchange2': None  # 无效深度数据
        }
    }
    timestamp = datetime.now()
    config = {
        'strategy': {
            'COINS': ['BTC'],
            'FUTURES_MARGIN_RATE': 0.1
        },
        'supported_exchanges': {
            'BTC': ['Exchange1', 'Exchange2']
        }
    }

    await log_simulation_status(account, depths, timestamp, config)

@pytest.mark.asyncio
async def test_log_simulation_status_data_format():
    """测试数据格式化"""
    account = MockAccount()
    depths = {
        'BTC': {
            'Exchange1': {'asks': [(50000, 1.0)], 'bids': [(49900, 1.0)]}
        }
    }
    timestamp = datetime.now()
    config = {
        'strategy': {
            'COINS': ['BTC'],
            'FUTURES_MARGIN_RATE': 0.1
        },
        'supported_exchanges': {
            'BTC': ['Exchange1']
        }
    }

    await log_simulation_status(account, depths, timestamp, config)

@pytest.mark.asyncio
async def test_log_simulation_status_cache():
    """测试缓存功能"""
    account = MockAccount()
    depths = {
        'BTC': {
            'Exchange1': {'asks': [(50000, 1.0)], 'bids': [(49900, 1.0)]}
        }
    }
    
    # 设置缓存数据
    depth_cache.set('Exchange1', 'BTC', {
        'asks': [(49000, 1.0)],
        'bids': [(48900, 1.0)]
    })
    
    timestamp = datetime.now()
    config = {
        'strategy': {
            'COINS': ['BTC'],
            'FUTURES_MARGIN_RATE': 0.1
        },
        'supported_exchanges': {
            'BTC': ['Exchange1']
        }
    }

    await log_simulation_status(account, depths, timestamp, config)

@pytest.mark.asyncio
async def test_trade_stats_basic(account):
    """测试基本的交易统计功能"""
    # 更新交易统计
    account.update_trade_stats('arbitrage', 1.0, 100, 1)
    
    # 验证统计数据
    assert account.trade_stats['total_trades'] == 1
    assert account.trade_stats['success_trades'] == 1
    assert account.trade_stats['total_profit'] == 100
    assert account.trade_stats['total_fees'] == 1

@pytest.mark.asyncio
async def test_trade_stats_multiple_types(account):
    """测试多种交易类型的统计"""
    # 测试不同类型的交易
    trade_types = ['套利(原)', '对冲卖出(吃)', '对冲买入(吃)', '均衡(原)']
    
    for trade_type in trade_types:
        # 添加成功交易
        account.update_trade_stats(trade_type, 1.0, 100, 1, status='SUCCESS')
        # 添加失败交易
        account.update_trade_stats(trade_type, 0.5, -50, 0.5, status='FAILED')
        
        # 验证每种类型的统计数据
        stats = account.trade_stats['trade_types'][trade_type]
        assert stats['total_trades'] == 2
        assert stats['success_trades'] == 1
        assert stats['failed_trades'] == 1
        assert stats['total_volume'] == 1.5  # 1.0 + 0.5
        assert stats['total_fees'] == 1.5  # 1 + 0.5
        assert stats['max_profit'] == 100
        assert stats['max_loss'] == -50
        assert stats['avg_profit_per_trade'] == 25  # (100 - 50) / 2

@pytest.mark.asyncio
async def test_trade_stats_edge_cases(account):
    """测试边界情况"""
    # 测试零值交易
    account.update_trade_stats('zero_trade', 0, 0, 0)
    assert account.trade_stats['trade_types']['zero_trade']['total_trades'] == 1
    assert account.trade_stats['trade_types']['zero_trade']['total_volume'] == 0
    assert account.trade_stats['trade_types']['zero_trade']['total_fees'] == 0
    
    # 测试负值交易量
    account.update_trade_stats('negative_volume', -1.0, 100, 1)
    assert account.trade_stats['trade_types']['negative_volume']['total_volume'] == 1.0  # 应该取绝对值
    
    # 测试极大值
    large_number = 1e9
    account.update_trade_stats('large_trade', large_number, large_number, large_number)
    assert account.trade_stats['trade_types']['large_trade']['total_volume'] == large_number
    assert account.trade_stats['trade_types']['large_trade']['total_profit'] == large_number
    assert account.trade_stats['trade_types']['large_trade']['max_profit'] == large_number

@pytest.mark.asyncio
async def test_trade_stats_profit_tracking(account):
    """测试利润追踪功能"""
    trade_type = '套利测试'
    
    # 添加一系列交易，测试最大利润和最大亏损的追踪
    profits = [100, 200, -50, -150, 300]
    for profit in profits:
        account.update_trade_stats(trade_type, 1.0, profit, 1)
    
    stats = account.trade_stats['trade_types'][trade_type]
    assert stats['max_profit'] == 300
    assert stats['max_loss'] == -150
    assert stats['total_profit'] == sum(profits)
    assert stats['avg_profit_per_trade'] == sum(profits) / len(profits)

@pytest.mark.asyncio
async def test_trade_stats_status_tracking(account):
    """测试交易状态统计"""
    trade_type = '状态测试'
    
    # 测试不同状态的交易
    statuses = ['SUCCESS', 'FAILED', 'PENDING', 'EXECUTED', 'CANCELLED']
    expected_success = 0
    expected_failed = 0
    
    for status in statuses:
        account.update_trade_stats(trade_type, 1.0, 100, 1, status=status)
        if status in ['SUCCESS', 'EXECUTED']:
            expected_success += 1
        elif status in ['FAILED', 'CANCELLED']:
            expected_failed += 1
    
    stats = account.trade_stats['trade_types'][trade_type]
    assert stats['success_trades'] == expected_success
    assert stats['failed_trades'] == expected_failed
    assert stats['total_trades'] == len(statuses)

@pytest.mark.asyncio
async def test_trade_stats_volume_calculation(account):
    """测试交易量计算"""
    trade_type = '交易量测试'
    
    # 测试不同大小的交易量
    volumes = [0.1, 0.5, 1.0, 2.0, 5.0]
    for volume in volumes:
        account.update_trade_stats(trade_type, volume, 100, volume * 0.001)
    
    stats = account.trade_stats['trade_types'][trade_type]
    assert stats['total_volume'] == sum(volumes)
    assert abs(stats['total_fees'] - sum(v * 0.001 for v in volumes)) < 1e-10

@pytest.mark.asyncio
async def test_trade_stats_calculation_accuracy():
    """测试交易统计计算的准确性"""
    # 创建一个测试账户，使用预定义的交易记录
    account = MockAccount()
    
    # 清空原有的交易记录和统计数据
    account.trade_records = []
    account.trade_stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'total_trades': 0,
        'success_trades': 0,
        'failed_trades': 0,
        'total_volume': 0.0,
        'total_profit': 0.0,
        'total_fees': 0.0,
        'max_profit': float('-inf'),
        'max_loss': 0,
        'trade_types': {}
    }
    
    # 添加测试用的交易记录
    test_trades = [
        {
            'time': '10:00:00',
            'type': '套利(原)',
            'coin': 'BTC',
            'buy_exchange': 'Exchange1',
            'sell_exchange': 'Exchange2',
            'amount': 1.0,
            'buy_price': 50000,
            'sell_price': 50500,
            'actual_buy_price': 50000,
            'actual_sell_price': 50500,
            'actual_buy_cost': 50000,
            'actual_sell_revenue': 50500,
            'total_fees': 50,
            'net_profit': 450,
            'status': 'SUCCESS'
        },
        {
            'time': '10:01:00',
            'type': '套利(原)',
            'coin': 'BTC',
            'buy_exchange': 'Exchange1',
            'sell_exchange': 'Exchange2',
            'amount': 0.5,
            'buy_price': 51000,
            'sell_price': 50800,
            'actual_buy_price': 51000,
            'actual_sell_revenue': 50800,
            'actual_buy_cost': 25500,
            'total_fees': 30,
            'net_profit': -130,
            'status': 'FAILED'
        },
        {
            'time': '10:02:00',
            'type': '对冲(吃)',
            'coin': 'ETH',
            'buy_exchange': 'Exchange1',
            'sell_exchange': 'Exchange2',
            'amount': 2.0,
            'buy_price': 3000,
            'sell_price': 3050,
            'actual_buy_price': 3000,
            'actual_sell_price': 3050,
            'actual_buy_cost': 6000,
            'actual_sell_revenue': 6100,
            'total_fees': 20,
            'net_profit': 80,
            'status': 'SUCCESS'
        }
    ]
    
    account.trade_records.extend(test_trades)
    
    # 更新交易统计数据
    for trade in test_trades:
        account.update_trade_stats(
            trade_type=trade['type'],
            amount=trade['amount'],
            profit=trade['net_profit'],
            fees=trade['total_fees'],
            status=trade['status']
        )
    
    # 准备测试数据
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
    
    # 执行日志记录并获取返回的统计数据
    status_data = await log_simulation_status(account, depths, timestamp, config)
    assert status_data is not None, "log_simulation_status 应该返回统计数据"
    
    # 验证总体统计
    assert len(account.trade_records) == 3, "总交易数量应该是3"
    
    # 打印调试信息
    print("\n交易统计数据:")
    print(f"account.trade_stats['trade_types']: {account.trade_stats['trade_types']}")
    print(f"status_data['trade_types']: {status_data['trade_types']}")
    print(f"status_data['trade_types'].keys(): {status_data['trade_types'].keys()}")
    
    # 从 trade_records 直接计算预期值
    expected_stats = {
        '套利(原)': {
            'count': 2,
            'success': 1,
            'failed': 1,
            'total_volume': 1.5,
            'total_profit': 320,
            'total_fees': 80,
            'max_profit': 450,
            'max_loss': -130,
            'avg_profit_per_trade': 160
        },
        '对冲(吃)': {
            'count': 1,
            'success': 1,
            'failed': 0,
            'total_volume': 2.0,
            'total_profit': 80,
            'total_fees': 20,
            'max_profit': 80,
            'max_loss': 0,
            'avg_profit_per_trade': 80
        }
    }
    
    # 验证每种交易类型的统计
    trade_types = status_data['trade_types']
    for trade_type, expected in expected_stats.items():
        stats = trade_types[trade_type]
        assert stats['count'] == expected['count'], \
            f"{trade_type} 交易数量应该是 {expected['count']}, 实际是 {stats['count']}"
        assert stats['success'] == expected['success'], \
            f"{trade_type} 成功交易数量应该是 {expected['success']}, 实际是 {stats['success']}"
        assert stats['failed'] == expected['failed'], \
            f"{trade_type} 失败交易数量应该是 {expected['failed']}, 实际是 {stats['failed']}"
        assert abs(float(stats['total_volume']) - expected['total_volume']) < 0.0001, \
            f"{trade_type} 总交易量应该是 {expected['total_volume']}, 实际是 {stats['total_volume']}"
        assert abs(float(stats['total_profit']) - expected['total_profit']) < 0.0001, \
            f"{trade_type} 总收益应该是 {expected['total_profit']}, 实际是 {stats['total_profit']}"
        assert abs(float(stats['total_fees']) - expected['total_fees']) < 0.0001, \
            f"{trade_type} 总手续费应该是 {expected['total_fees']}, 实际是 {stats['total_fees']}"
        assert abs(float(stats['max_profit']) - expected['max_profit']) < 0.0001, \
            f"{trade_type} 最大盈利应该是 {expected['max_profit']}, 实际是 {stats['max_profit']}"
        assert abs(float(stats['max_loss']) - expected['max_loss']) < 0.0001, \
            f"{trade_type} 最大亏损应该是 {expected['max_loss']}, 实际是 {stats['max_loss']}"
        assert abs(float(stats['avg_profit_per_trade']) - expected['avg_profit_per_trade']) < 0.0001, \
            f"{trade_type} 平均收益应该是 {expected['avg_profit_per_trade']}, 实际是 {stats['avg_profit_per_trade']}"
    
    # 验证总体胜率
    total_success = sum(1 for trade in account.trade_records if trade['status'] == 'SUCCESS')
    expected_win_rate = (total_success / len(account.trade_records)) * 100
    assert abs(status_data['win_rate'] - expected_win_rate) < 0.01, \
        f"总体胜率应该是 {expected_win_rate}%, 实际是 {status_data['win_rate']}%"

if __name__ == '__main__':
    pytest.main(['-v', 'test_log_simulation_status.py']) 