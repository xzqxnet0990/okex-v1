import pytest
import os
import json
from unittest.mock import patch, mock_open
from utils.config import load_config, load_supported_exchanges, get_exchange_fee

# Mock data for testing
MOCK_CONFIG = {
    "strategy": {
        "COINS": ["BTC", "ETH"],
        "MIN_AMOUNT": 0.001,
        "SAFE_PRICE": 100,
        "MAX_TRADE_PRICE": 500,
    },
    "exchanges": {
        "MEXC": {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "default_fees": {
                "maker": 0.001,
                "taker": 0.002
            },
            "symbol_fees": {
                "BTC": {
                    "maker": 0.0005,
                    "taker": 0.001
                }
            }
        },
        "HTX": {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "default_fees": {
                "maker": 0.002,
                "taker": 0.002
            }
        }
    },
    "risk_control": {
        "SINGLE_TRADE_LOSS_LIMIT": -50,
        "TOTAL_LOSS_LIMIT": -1000
    },
    "web_server": {
        "host": "localhost",
        "port": 8080
    },
    "logging": {
        "level": "INFO",
        "file_path": "logs/trading.log"
    }
}

MOCK_SUPPORTED_EXCHANGES = {
    "BTC": ["MEXC", "HTX", "Binance"],
    "ETH": ["MEXC", "HTX", "Binance"],
    "DOGE": ["MEXC", "HTX"]
}

@pytest.fixture
def mock_config_file():
    """Fixture to mock the config.json file"""
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CONFIG))):
        with patch("os.path.exists", return_value=True):
            yield

@pytest.fixture
def mock_supported_exchanges_file():
    """Fixture to mock the supported_exchanges.json file"""
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_SUPPORTED_EXCHANGES))):
        with patch("os.path.exists", return_value=True):
            yield

def test_load_config_success(mock_config_file):
    """Test loading config successfully"""
    config = load_config()
    
    assert config is not None
    assert "strategy" in config
    assert "exchanges" in config
    assert "risk_control" in config
    assert "web_server" in config
    assert "logging" in config
    
    # Check specific values
    assert config["strategy"]["COINS"] == ["BTC", "ETH"]
    assert config["strategy"]["MIN_AMOUNT"] == 0.001
    assert config["exchanges"]["MEXC"]["api_key"] == "test_key"
    assert config["exchanges"]["MEXC"]["default_fees"]["maker"] == 0.001

@patch('utils.config.Log')
def test_load_config_file_not_exists(mock_log):
    """Test loading config when file doesn't exist"""
    with patch("os.path.exists", return_value=False):
        config = load_config()
        
        assert config == {}
        assert mock_log.call_count > 0

def test_load_config_with_defaults():
    """Test loading config with default values for missing fields"""
    # Create a config with missing fields
    incomplete_config = {
        "strategy": {
            "COINS": ["BTC", "ETH"]
            # Missing other strategy fields
        },
        "exchanges": {
            "MEXC": {
                "api_key": "test_key",
                "api_secret": "test_secret"
                # Missing fee information
            }
        },
        "risk_control": {},
        "web_server": {},
        "logging": {}
    }
    
    with patch("builtins.open", mock_open(read_data=json.dumps(incomplete_config))):
        with patch("os.path.exists", return_value=True):
            config = load_config()
            
            # Check that default values were added
            assert "MIN_AMOUNT" in config["strategy"]
            assert "SAFE_PRICE" in config["strategy"]
            assert "MAX_TRADE_PRICE" in config["strategy"]
            assert "SINGLE_TRADE_LOSS_LIMIT" in config["risk_control"]

@patch('utils.config.Log')
def test_load_config_invalid_json(mock_log):
    """Test loading config with invalid JSON"""
    with patch("builtins.open", mock_open(read_data="invalid json")):
        with patch("os.path.exists", return_value=True):
            config = load_config()
            
            assert config == {}
            assert mock_log.call_count > 0

def test_load_supported_exchanges_success(mock_supported_exchanges_file):
    """Test loading supported exchanges successfully"""
    exchanges = load_supported_exchanges()
    
    assert exchanges is not None
    assert "BTC" in exchanges
    assert "ETH" in exchanges
    assert "DOGE" in exchanges
    
    assert exchanges["BTC"] == ["MEXC", "HTX", "Binance"]
    assert exchanges["ETH"] == ["MEXC", "HTX", "Binance"]
    assert exchanges["DOGE"] == ["MEXC", "HTX"]

def test_load_supported_exchanges_file_not_exists():
    """Test loading supported exchanges when file doesn't exist"""
    with patch("os.path.exists", return_value=False):
        exchanges = load_supported_exchanges()
        
        assert exchanges == {}

@patch('utils.config.Log')
def test_load_supported_exchanges_invalid_json(mock_log):
    """Test loading supported exchanges with invalid JSON"""
    with patch("builtins.open", mock_open(read_data="invalid json")):
        with patch("os.path.exists", return_value=True):
            exchanges = load_supported_exchanges()
            
            assert exchanges == {}
            assert mock_log.call_count > 0

def test_get_exchange_fee_with_symbol_specific_fee(mock_config_file):
    """Test getting exchange fee with symbol-specific fee"""
    # MEXC has a symbol-specific fee for BTC
    fee = get_exchange_fee("MEXC", "BTC", False)  # taker fee
    
    assert fee == 0.001  # BTC-specific taker fee
    
    fee = get_exchange_fee("MEXC", "BTC", True)  # maker fee
    
    assert fee == 0.0005  # BTC-specific maker fee

def test_get_exchange_fee_with_default_fee(mock_config_file):
    """Test getting exchange fee with default fee"""
    # MEXC doesn't have a symbol-specific fee for ETH, so should use default
    fee = get_exchange_fee("MEXC", "ETH", False)  # taker fee
    
    assert fee == 0.002  # Default taker fee
    
    fee = get_exchange_fee("MEXC", "ETH", True)  # maker fee
    
    assert fee == 0.001  # Default maker fee

def test_get_exchange_fee_unknown_exchange(mock_config_file):
    """Test getting exchange fee for unknown exchange"""
    fee = get_exchange_fee("UNKNOWN", "BTC", False)
    
    assert fee == 0.0015  # Should return default conservative taker fee

def test_get_exchange_fee_unknown_symbol(mock_config_file):
    """Test getting exchange fee for unknown symbol"""
    fee = get_exchange_fee("MEXC", "UNKNOWN", False)
    
    assert fee == 0.002  # Should return default taker fee for the exchange

@patch('utils.config.Log')
@patch('utils.config.load_config', side_effect=Exception("Test error"))
def test_get_exchange_fee_with_error(mock_load_config, mock_log):
    """Test getting exchange fee with an error during processing"""
    fee = get_exchange_fee("MEXC", "BTC", False)
    
    assert fee == 0.0015  # Should return default conservative taker fee
    assert mock_log.call_count > 0 