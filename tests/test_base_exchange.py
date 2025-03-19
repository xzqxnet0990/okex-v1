import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from exchanges.base import BaseExchange, Account, OrderBook

class MockExchange(BaseExchange):
    """Mock implementation of BaseExchange for testing"""
    
    def __init__(self, config=None):
        super().__init__(config or {})
        self.name = "MockExchange"
        self.label = "Mock"
    
    async def GetAccount(self):
        return Account(Balance=1000.0, Stocks=1.0, FrozenBalance=100.0, FrozenStocks=0.1)
    
    async def GetDepth(self, symbol):
        return OrderBook(
            Asks=[(50000, 1.0), (50100, 2.0)],
            Bids=[(49900, 1.0), (49800, 2.0)]
        )
    
    async def Buy(self, symbol, price, amount):
        return {
            'id': 'test_order_id',
            'price': price,
            'amount': amount,
            'filled': amount,
            'status': 'closed'
        }
    
    async def Sell(self, symbol, price, amount):
        return {
            'id': 'test_order_id',
            'price': price,
            'amount': amount,
            'filled': amount,
            'status': 'closed'
        }
    
    async def CancelOrder(self, symbol, order_id):
        return True
    
    async def GetOrder(self, symbol, order_id):
        return {
            'id': order_id,
            'price': 50000,
            'amount': 1.0,
            'filled': 1.0,
            'status': 'closed'
        }
    
    async def GetOrders(self, symbol):
        return [{
            'id': 'test_order_id',
            'price': 50000,
            'amount': 1.0,
            'filled': 1.0,
            'status': 'closed'
        }]
    
    async def close(self):
        pass

@pytest.fixture
def exchange():
    """Fixture to create a mock exchange instance"""
    config = {
        'api_key': 'test_key',
        'api_secret': 'test_secret',
        'passphrase': 'test_pass',
        'maker_fee': 0.001,
        'taker_fee': 0.002,
        'fees': {
            'default_fees': {
                'maker': 0.001,
                'taker': 0.002
            },
            'symbol_fees': {
                'BTC': {
                    'maker': 0.0005,
                    'taker': 0.001
                }
            }
        }
    }
    return MockExchange(config)

def test_base_exchange_initialization():
    """Test BaseExchange initialization"""
    # Test with minimal config
    config = {
        'api_key': 'test_key',
        'api_secret': 'test_secret'
    }
    exchange = MockExchange(config)
    
    assert exchange.api_key == 'test_key'
    assert exchange.api_secret == 'test_secret'
    assert exchange.passphrase == ''
    assert exchange.maker_fee == 0.002  # Default value
    assert exchange.taker_fee == 0.002  # Default value
    assert exchange.name == 'MockExchange'
    assert exchange.label == 'Mock'
    
    # Test with full config
    config = {
        'api_key': 'test_key',
        'api_secret': 'test_secret',
        'passphrase': 'test_pass',
        'maker_fee': 0.001,
        'taker_fee': 0.002
    }
    exchange = MockExchange(config)
    
    assert exchange.api_key == 'test_key'
    assert exchange.api_secret == 'test_secret'
    assert exchange.passphrase == 'test_pass'
    assert exchange.maker_fee == 0.001
    assert exchange.taker_fee == 0.002

def test_get_name_and_label(exchange):
    """Test GetName and GetLabel methods"""
    assert exchange.GetName() == 'MockExchange'
    assert exchange.GetLabel() == 'Mock'

@pytest.mark.asyncio
async def test_execute_request(exchange):
    """Test _execute_request method"""
    # Create a mock request function
    mock_func = AsyncMock(return_value="success")
    
    # Test successful request
    result = await exchange._execute_request(mock_func, "arg1", "arg2", kwarg1="value1")
    
    assert result == "success"
    mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")
    
    # Test failed request
    mock_func.reset_mock()
    mock_func.side_effect = Exception("Test error")
    
    with pytest.raises(Exception) as excinfo:
        await exchange._execute_request(mock_func, "arg1")
    
    assert "Test error" in str(excinfo.value)
    mock_func.assert_called_once_with("arg1")

@pytest.mark.asyncio
async def test_get_fee_with_symbol_fees(exchange):
    """Test GetFee method with symbol-specific fees"""
    # Test with symbol-specific maker fee
    fee = await exchange.GetFee("BTC", True)
    assert fee == 0.0005
    
    # Test with symbol-specific taker fee
    fee = await exchange.GetFee("BTC", False)
    assert fee == 0.001

@pytest.mark.asyncio
async def test_get_fee_with_default_fees(exchange):
    """Test GetFee method with default fees"""
    # Test with default maker fee
    fee = await exchange.GetFee("ETH", True)
    assert fee == 0.001
    
    # Test with default taker fee
    fee = await exchange.GetFee("ETH", False)
    assert fee == 0.002

@pytest.mark.asyncio
async def test_get_fee_fallback(exchange):
    """Test GetFee method fallback to instance variables"""
    # Remove fee config to test fallback
    exchange.fee_config = {}
    
    # Test fallback to instance maker_fee
    fee = await exchange.GetFee("BTC", True)
    assert fee == 0.001
    
    # Test fallback to instance taker_fee
    fee = await exchange.GetFee("BTC", False)
    assert fee == 0.002

@pytest.mark.asyncio
@patch('utils.logger.Log')
async def test_get_fee_with_error(mock_log):
    """Test GetFee method with error handling"""
    # Create exchange with no fee config
    exchange = MockExchange({})
    
    # Create a mock GetFee method that raises an exception
    original_get_fee = exchange.GetFee
    
    async def mock_get_fee(*args, **kwargs):
        raise Exception("Test error")
    
    # Replace the method
    exchange.GetFee = mock_get_fee
    
    try:
        # Call the method directly to test error handling
        fee = await BaseExchange.GetFee(exchange, "BTC", True)
        assert fee == 0.002  # Should return default conservative value
        
        # Test taker fee with error
        fee = await BaseExchange.GetFee(exchange, "BTC", False)
        assert fee == 0.002  # Should return default conservative value
    finally:
        # Restore original method
        exchange.GetFee = original_get_fee

def test_account_dataclass():
    """Test Account dataclass"""
    # Test initialization with default values
    account = Account()
    assert account.Balance == 0.0
    assert account.Stocks == 0.0
    assert account.FrozenBalance == 0.0
    assert account.FrozenStocks == 0.0
    
    # Test initialization with custom values
    account = Account(Balance=1000.0, Stocks=1.0, FrozenBalance=100.0, FrozenStocks=0.1)
    assert account.Balance == 1000.0
    assert account.Stocks == 1.0
    assert account.FrozenBalance == 100.0
    assert account.FrozenStocks == 0.1

def test_orderbook_dataclass():
    """Test OrderBook dataclass"""
    # Test initialization with empty lists
    orderbook = OrderBook(Asks=[], Bids=[])
    assert orderbook.Asks == []
    assert orderbook.Bids == []
    
    # Test initialization with data
    asks = [(50000, 1.0), (50100, 2.0)]
    bids = [(49900, 1.0), (49800, 2.0)]
    orderbook = OrderBook(Asks=asks, Bids=bids)
    assert orderbook.Asks == asks
    assert orderbook.Bids == bids 