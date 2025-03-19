import pytest
from unittest.mock import patch, MagicMock
from exchanges import ExchangeFactory
from exchanges.base import BaseExchange
from exchanges.mexc import MEXCExchange
from exchanges.htx import HTXExchange
from exchanges.okx import OKXExchange
from exchanges.binance import BinanceExchange
from exchanges.futures_mexc import FuturesMEXCExchange

# Reset the ExchangeFactory._exchanges dictionary before each test
@pytest.fixture(autouse=True)
def reset_exchange_factory():
    """Reset the ExchangeFactory._exchanges dictionary before each test"""
    original_exchanges = ExchangeFactory._exchanges.copy()
    ExchangeFactory._exchanges = {}
    yield
    ExchangeFactory._exchanges = original_exchanges

# Patch the Log function for all tests to avoid asyncio errors
@pytest.fixture(autouse=True)
def mock_log():
    """Mock the Log function to avoid asyncio errors"""
    with patch('exchanges.factory.Log') as mock:
        yield mock

def test_exchange_factory_create_exchange():
    """Test creating exchanges with ExchangeFactory"""
    # Test configuration
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "passphrase": "test_pass"
    }
    
    # Test creating different exchange types
    exchanges_to_test = [
        ("MEXC", MEXCExchange),
        ("HTX", HTXExchange),
        ("OKX", OKXExchange),
        ("Binance", BinanceExchange),
        ("Futures_MEXC", FuturesMEXCExchange)
    ]
    
    for exchange_name, exchange_class in exchanges_to_test:
        # Create exchange
        exchange = ExchangeFactory.create_exchange(exchange_name, config)
        
        # Verify exchange type
        assert isinstance(exchange, exchange_class)
        assert isinstance(exchange, BaseExchange)  # All exchanges should inherit from BaseExchange
        
        # Verify config was passed correctly
        assert exchange.api_key == "test_key"
        assert exchange.api_secret == "test_secret"

def test_exchange_factory_case_insensitive():
    """Test that exchange names are case-insensitive"""
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret"
    }
    
    # Test with different case variations
    variations = [
        ("MEXC", MEXCExchange),
        ("mexc", MEXCExchange),
        ("Mexc", MEXCExchange),
        ("MeXc", MEXCExchange)
    ]
    
    for exchange_name, expected_class in variations:
        exchange = ExchangeFactory.create_exchange(exchange_name, config)
        assert isinstance(exchange, expected_class)

def test_exchange_factory_get_exchange():
    """Test getting an existing exchange"""
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret"
    }
    
    # Create an exchange
    exchange1 = ExchangeFactory.create_exchange("MEXC", config)
    
    # Get the same exchange
    exchange2 = ExchangeFactory.get_exchange("MEXC")
    
    # Should return the same instance
    assert exchange1 is exchange2

def test_exchange_factory_unknown_exchange(mock_log):
    """Test creating an unknown exchange type"""
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret"
    }
    
    # Try to create an unknown exchange
    exchange = ExchangeFactory.create_exchange("UNKNOWN_EXCHANGE", config)
    
    # Should return None for unknown exchange
    assert exchange is None
    
    # Verify log was called
    assert mock_log.call_count > 0

def test_exchange_factory_with_empty_config():
    """Test creating an exchange with empty config"""
    # Empty config
    config = {}
    
    # Create exchange with empty config
    exchange = ExchangeFactory.create_exchange("MEXC", config)
    
    # Should still create the exchange
    assert isinstance(exchange, MEXCExchange)
    
    # Default values should be used for empty config
    assert exchange.api_key == ""
    assert exchange.api_secret == ""

def test_exchange_factory_exception_handling(mock_log):
    """Test exception handling when creating exchanges"""
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret"
    }
    
    # Create a side effect that raises an exception
    def raise_exception(*args, **kwargs):
        raise Exception("Test exception")
    
    # Patch the MEXCExchange constructor to raise an exception
    with patch.object(MEXCExchange, '__init__', side_effect=raise_exception):
        # Try to create the exchange
        exchange = ExchangeFactory.create_exchange("MEXC", config)
        
        # Should return None when an exception occurs
        assert exchange is None
        
        # Verify log was called
        assert mock_log.call_count > 0

def test_exchange_factory_all_supported_exchanges():
    """Test that all supported exchanges can be created"""
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "passphrase": "test_pass"
    }
    
    # Get all supported exchange types from the factory
    supported_exchanges = [
        "MEXC", "HTX", "OKX", "Binance", "Bybit", 
        "Gate", "Bitget", "CoinEx", "Futures_MEXC"
    ]
    
    # Try to create each exchange type
    for exchange_name in supported_exchanges:
        exchange = ExchangeFactory.create_exchange(exchange_name, config)
        assert exchange is not None
        assert isinstance(exchange, BaseExchange) 