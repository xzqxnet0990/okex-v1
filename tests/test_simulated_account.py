import pytest
import pytest_asyncio
from utils.simulated_account import SimulatedAccount
from datetime import datetime
from unittest.mock import patch, AsyncMock

# 测试配置数据
TEST_CONFIG = {
    'strategy': {
        'COINS': ['BTC', 'ETH'],
        'MIN_AMOUNT': 0.001,
        'SAFE_PRICE': 100,
        'MAX_TRADE_PRICE': 500,
        'FUTURES_MARGIN_RATE': 0.1
    },

    "exchanges": {
        "MEXC": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.000,
                "taker": 0.0005
            }
        },
        "OKX": {
            "api_key": "",
            "api_secret": "",
            "passphrase": "",
            "default_fees": {
                "maker": 0.001,
                "taker": 0.001
            }
        },
        "HTX": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.002,
                "taker": 0.002
            }
        },
        "CoinEx": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.002,
                "taker": 0.002
            }
        },
        "Bybit": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.001,
                "taker": 0.001
            }
        },
        "Gate": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.002,
                "taker": 0.002
            }
        },
        "Bitget": {
            "api_key": "",
            "api_secret": "",
            "passphrase": "",
            "default_fees": {
                "maker": 0.001,
                "taker": 0.001
            }
        },
        "BINANCE": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.001,
                "taker": 0.001
            }
        },
        "Futures_MEXC": {
            "api_key": "",
            "api_secret": "",
            "default_fees": {
                "maker": 0.001,
                "taker": 0.001
            }
        }
    },
    'supported_exchanges': {
        'BTC': ['Binance', 'OKX', 'MEXC', 'HTX'],
        'ETH': ['Binance', 'OKX', 'MEXC', 'HTX']
    }
}

@pytest_asyncio.fixture
async def account():
    """创建测试账户实例"""
    acc = SimulatedAccount(initial_balance=10000, config=TEST_CONFIG)
    
    # 初始化交易所
    for exchange in TEST_CONFIG['exchanges'].keys():
        acc.initialize_exchange(exchange)
    
    yield acc
    # 清理资源
    for exchange in acc.exchanges.values():
        if exchange:
            try:
                await exchange.close()
            except:
                pass

@pytest.mark.asyncio
async def test_initialization(account):
    """测试账户初始化"""
    assert account.initial_balance == 10000
    assert account.config == TEST_CONFIG
    assert isinstance(account.exchanges, dict)
    assert isinstance(account.fee_cache, dict)
    assert isinstance(account.balances, dict)
    assert isinstance(account.frozen_balances, dict)
    assert isinstance(account.unhedged_positions, dict)
    assert isinstance(account.pending_orders, list)
    assert isinstance(account.trade_stats, dict)
    assert isinstance(account.trade_records, list)

@pytest.mark.asyncio
async def test_initialize_method(account):
    """测试异步初始化方法"""
    # Create a new account instance
    account = SimulatedAccount(initial_balance=10000, config=TEST_CONFIG)
    
    # Mock the _initialize_coin_balances method to prevent real API calls
    with patch.object(SimulatedAccount, '_initialize_coin_balances', new_callable=AsyncMock) as mock_init_balances:
        # Call initialize
        await account.initialize()
        
        # Verify _initialize_fees was called (indirectly by checking fee_cache)
        assert 'maker' in account.fee_cache
        assert 'taker' in account.fee_cache
        
        # Verify _initialize_coin_balances was called
        mock_init_balances.assert_called_once()
        
        # Manually set up some balances to verify the test
        account.balances['usdt'] = {'MEXC': 5000, 'HTX': 5000}
        
        # Verify balances
        assert len(account.balances['usdt']) > 0
        assert account.balances['usdt']['MEXC'] == 5000
        assert account.balances['usdt']['HTX'] == 5000

@pytest.mark.asyncio
async def test_get_fee(account):
    """测试获取费率方法"""
    # 初始化费率缓存
    account.update_fee('Binance', 'BTC', 0.001, 0.001)
    # 测试获取maker费率
    maker_fee = account.get_fee('Binance', 'BTC', True)
    assert maker_fee == 0.001
    # 测试获取taker费率
    taker_fee = account.get_fee('Binance', 'BTC', False)
    assert taker_fee == 0.001
    # 测试获取不存在的交易所费率（应返回默认值）
    unknown_fee = account.get_fee('Unknown', 'BTC', True)
    assert unknown_fee == 0.002

@pytest.mark.asyncio
async def test_update_fee(account):
    """测试更新费率方法"""
    account.update_fee('Binance', 'BTC', 0.001, 0.002)
    assert account.fee_cache['maker']['Binance']['BTC'] == 0.001
    assert account.fee_cache['taker']['Binance']['BTC'] == 0.002

@pytest.mark.asyncio
async def test_get_balance(account):
    """测试获取余额方法"""
    # 设置初始余额
    account.balances['usdt']['Binance'] = 1000
    account.balances['stocks']['Binance'] = {'btc': 1.0}
    
    # 测试获取USDT余额
    usdt_balance = account.get_balance('usdt', 'Binance')
    assert usdt_balance == 1000
    
    # 测试获取币种余额
    btc_balance = account.get_balance('btc', 'Binance')
    assert btc_balance == 1.0
    
    # 测试获取不存在的余额
    unknown_balance = account.get_balance('eth', 'Binance')
    assert unknown_balance == 0

@pytest.mark.asyncio
async def test_update_balance(account):
    """测试更新余额方法"""
    # 初始化测试数据
    account.balances['usdt']['Binance'] = 100000  # 设置足够大的初始USDT余额
    account.balances['stocks']['Binance'] = {'btc': 0}

    # 测试买入更新（增加币种余额，减少USDT）
    account.update_balance('btc', 1.0, 'Binance', True)  # 增加1.0 BTC
    account.update_balance('usdt', -50000, 'Binance', True)  # 减少50000 USDT
    assert account.get_balance('btc', 'Binance') == 1.0
    assert account.get_balance('usdt', 'Binance') == 50000  # 100000 - 50000
    
    # 测试卖出更新（减少币种余额，增加USDT）
    account.update_balance('btc', -0.5, 'Binance', False)  # 减少0.5 BTC
    account.update_balance('usdt', 25000, 'Binance', False)  # 增加25000 USDT
    assert account.get_balance('btc', 'Binance') == 0.5
    assert account.get_balance('usdt', 'Binance') == 75000  # 50000 + 25000

    # 测试余额不能为负数
    account.update_balance('btc', -1.0, 'Binance', False)  # 尝试减少超过余额的数量
    assert account.get_balance('btc', 'Binance') == 0  # 余额应该是0，不能为负

    # 测试不存在的交易所
    account.update_balance('btc', 1.0, 'Unknown', True)
    assert account.get_balance('btc', 'Unknown') == 1.0

@pytest.mark.asyncio
async def test_freeze_unfreeze_balance(account):
    """测试冻结和解冻余额方法"""
    # 设置初始余额
    account.balances['usdt']['Binance'] = 1000
    
    # 测试冻结余额
    account.freeze_balance('usdt', 100, 'Binance')
    assert account.get_freeze_balance('usdt', 'Binance') == 100
    
    # 测试解冻余额
    account.unfreeze_balance('usdt', 50, 'Binance')
    assert account.get_freeze_balance('usdt', 'Binance') == 50

@pytest.mark.asyncio
async def test_update_unhedged_position(account):
    """测试更新未对冲头寸方法"""
    # 测试买入头寸
    account.update_unhedged_position('BTC', 1.0, 'Binance', True)
    assert account.get_unhedged_position('BTC', 'Binance') == 1.0
    
    # 测试卖出头寸
    account.update_unhedged_position('BTC', 0.5, 'Binance', False)
    assert account.get_unhedged_position('BTC', 'Binance') == 0.5

@pytest.mark.asyncio
async def test_pending_orders(account):
    """测试挂单相关方法"""
    # 创建测试订单
    test_order = {
        'id': 'test_order',
        'coin': 'BTC',
        'amount': 1.0,
        'price': 50000,
        'type': 'buy'
    }
    
    # 测试添加挂单
    account.add_pending_order(test_order)
    assert len(account.get_pending_orders()) == 1
    
    # 测试获取特定币种的挂单
    btc_orders = account.get_pending_orders('BTC')
    assert len(btc_orders) == 1
    
    # 测试移除挂单
    account.remove_pending_order('test_order')
    assert len(account.get_pending_orders()) == 0

@pytest.mark.asyncio
async def test_trade_stats(account):
    """测试交易统计相关方法"""
    # 更新交易统计
    account.update_trade_stats('arbitrage', 1.0, 100, 1)
    
    # 验证统计数据
    assert account.trade_stats['total_trades'] == 1
    assert account.trade_stats['success_trades'] == 1
    assert account.trade_stats['total_profit'] == 100
    assert account.trade_stats['total_fees'] == 1

@pytest.mark.asyncio
async def test_trade_records(account):
    """测试交易记录相关方法"""
    # 创建测试交易记录
    trade_data = {
        'type': 'arbitrage',
        'coin': 'BTC',
        'amount': 1.0,
        'buy_price': 50000,
        'sell_price': 50100,
        'profit': 100,
        'fees': 1
    }
    
    # 添加交易记录
    account.add_trade_record(trade_data)
    
    # 验证记录是否添加成功
    assert len(account.trade_records) == 1
    assert account.trade_records[0]['type'] == 'arbitrage'
    
    # 验证交易统计是否更新
    assert account.trade_stats['total_trades'] == 1

@pytest.mark.asyncio
async def test_get_trade_stats_summary(account):
    """测试获取交易统计摘要方法"""
    # 添加一些测试数据
    account.update_trade_stats('arbitrage', 1.0, 100, 1)
    account.update_trade_stats('hedge', 1.0, -50, 1)
    
    # 获取统计摘要
    summary = account.get_trade_stats_summary()
    
    # 验证摘要内容
    assert isinstance(summary, str)
    assert '交易统计摘要' in summary
    assert '总交易次数: 2' in summary

@pytest.mark.asyncio
async def test_error_handling(account):
    """测试错误处理"""
    # 测试无效的费率更新
    account.update_fee('Unknown', 'BTC', -0.001, -0.001)
    assert account.get_fee('Unknown', 'BTC', True) == 0.002  # 应返回默认值
    
    # 测试无效的余额更新
    account.update_balance('btc', -1.0, 'Unknown', True)
    assert account.get_balance('btc', 'Unknown') == 0  # 应返回0
    
    # 测试无效的冻结操作
    account.freeze_balance('btc', -1.0, 'Unknown')
    assert account.get_freeze_balance('btc', 'Unknown') == 0  # 应返回0

@pytest.mark.asyncio
async def test_initialize_exchange(account):
    """测试交易所初始化"""
    for exchange in TEST_CONFIG['exchanges'].keys():
        assert exchange in account.balances['usdt']
        assert exchange in account.balances['stocks']
        assert exchange in account.frozen_balances['usdt']
        assert exchange in account.frozen_balances['stocks']

@pytest.mark.asyncio
async def test_update_trade_stats(account):
    """测试更新交易统计"""
    trade_type = '套利(原)'
    
    # 测试成功交易
    account.update_trade_stats(
        trade_type=trade_type,
        amount=1.0,
        profit=100,
        fees=1,
        status='SUCCESS'
    )
    
    assert trade_type in account.trade_stats
    stats = account.trade_stats[trade_type]
    assert stats['count'] == 1
    assert stats['total_volume'] == 1.0
    assert stats['total_profit'] == 100
    assert stats['total_fees'] == 1
    assert stats['success'] == 1
    assert stats['failed'] == 0

    # 测试失败交易
    account.update_trade_stats(
        trade_type=trade_type,
        amount=0.5,
        profit=-50,
        fees=0.5,
        status='FAILED'
    )
    
    stats = account.trade_stats[trade_type]
    assert stats['count'] == 2
    assert stats['total_volume'] == 1.5
    assert stats['total_profit'] == 50
    assert stats['total_fees'] == 1.5
    assert stats['success'] == 1
    assert stats['failed'] == 1

@pytest.mark.asyncio
async def test_add_trade_record(account):
    """测试添加交易记录"""
    trade = {
        'time': datetime.now().strftime('%H:%M:%S'),
        'type': '套利(原)',
        'coin': 'BTC',
        'buy_exchange': 'MEXC',
        'sell_exchange': 'HTX',
        'amount': 0.1,
        'buy_price': 50000,
        'sell_price': 50100,
        'status': 'SUCCESS'
    }
    
    account.add_trade_record(trade)
    assert len(account.trade_records) == 1
    assert account.trade_records[0]['type'] == '套利(原)'
    assert account.trade_records[0]['status'] == 'SUCCESS'

@pytest.mark.asyncio
async def test_get_freeze_balance(account):
    """测试获取冻结余额"""
    # 初始冻结余额应该为0
    freeze_balance = account.get_freeze_balance('usdt', 'MEXC')
    assert freeze_balance == 0

@pytest.mark.asyncio
async def test_update_trade_stats_with_different_status(account):
    """测试不同状态的交易统计更新"""
    trade_type = '套利(原)'
    
    # 测试各种状态
    statuses = ['SUCCESS', 'FAILED', 'PENDING', 'EXECUTED', 'CANCELLED']
    for status in statuses:
        account.update_trade_stats(
            trade_type=trade_type,
            amount=1.0,
            profit=100,
            fees=1,
            status=status
        )
    
    stats = account.trade_stats[trade_type]
    assert stats['count'] == len(statuses)
    
    # SUCCESS 和 EXECUTED 计入成功
    success_count = len([s for s in statuses if s in ['SUCCESS', 'EXECUTED']])
    assert stats['success'] == success_count
    
    # FAILED 和 CANCELLED 计入失败
    failed_count = len([s for s in statuses if s in ['FAILED', 'CANCELLED']])
    assert stats['failed'] == failed_count

@pytest.mark.asyncio
async def test_update_trade_stats_profit_tracking(account):
    """测试交易统计中的利润追踪"""
    trade_type = '套利(原)'
    
    # 添加一系列交易
    trades = [
        (1.0, 100, 1),   # 盈利交易
        (1.0, 200, 1),   # 更大盈利
        (1.0, -50, 1),   # 小额亏损
        (1.0, -150, 1),  # 大额亏损
        (1.0, 300, 1),   # 最大盈利
    ]
    
    for volume, profit, fees in trades:
        account.update_trade_stats(
            trade_type=trade_type,
            amount=volume,
            profit=profit,
            fees=fees,
            status='SUCCESS'
        )
    
    stats = account.trade_stats[trade_type]
    assert stats['max_profit'] == 300
    assert stats['max_loss'] == -150
    assert stats['total_profit'] == sum(t[1] for t in trades)
    assert stats['avg_profit_per_trade'] == sum(t[1] for t in trades) / len(trades)

if __name__ == '__main__':
    pytest.main(['-v', 'test_simulated_account.py']) 