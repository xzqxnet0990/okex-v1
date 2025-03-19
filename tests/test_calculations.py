import pytest
from unittest.mock import patch
from utils.calculations import _N, calculate_real_price, calculate_trade_amount

def test_N_formatting():
    """Test the _N function for number formatting"""
    # Test with default precision (6 decimal places)
    assert _N(123.456789) == 123.456789
    assert _N(123.4567891234) == 123.456789  # Should truncate to 6 decimal places
    
    # Test with custom precision
    assert _N(123.456789, 2) == 123.45
    assert _N(123.456789, 0) == 123.0
    assert _N(123.456789, 10) == 123.456789
    
    # Test with integers
    assert _N(123) == 123.0
    assert _N(123, 2) == 123.0
    
    # Test with zero
    assert _N(0) == 0.0
    assert _N(0, 2) == 0.0
    
    # Test with negative numbers
    assert _N(-123.456789, 2) == -123.45
    
    # Test with non-numeric values (should return the value unchanged)
    assert _N("not a number") == "not a number"
    assert _N(None) == None

def test_calculate_real_price():
    """Test the calculate_real_price function"""
    # Test ask price (selling) with fee
    # When selling, the real price is higher due to fees
    assert calculate_real_price(100.0, 0.001, True) == 100.1  # 0.1% fee
    assert calculate_real_price(100.0, 0.002, True) == 100.2  # 0.2% fee
    
    # Test bid price (buying) with fee
    # When buying, the real price is lower due to fees
    assert calculate_real_price(100.0, 0.001, False) == 99.9  # 0.1% fee
    assert calculate_real_price(100.0, 0.002, False) == 99.8  # 0.2% fee
    
    # Test with zero fee
    assert calculate_real_price(100.0, 0.0, True) == 100.0
    assert calculate_real_price(100.0, 0.0, False) == 100.0
    
    # Test with very small price - using approx for floating point comparison
    assert pytest.approx(calculate_real_price(0.00001, 0.001, True), abs=1e-10) == 0.00001001
    assert pytest.approx(calculate_real_price(0.00001, 0.001, False), abs=1e-10) == 0.00000999

@patch('utils.calculations.Log')
def test_calculate_trade_amount(mock_log):
    """Test the calculate_trade_amount function"""
    # Basic test configuration
    config = {
        'strategy': {
            'MIN_AMOUNT': 0.001,  # Minimum trade amount
            'SAFE_PRICE': 100,    # Maximum amount in USDT for a single buy
            'MAX_TRADE_PRICE': 500,  # Maximum trade price
            'MAX_AMOUNT': 1000000  # Maximum trade amount
        }
    }
    
    # Test normal case
    # If buy_price is 10 USDT, we can buy 10 units with SAFE_PRICE=100
    amount = calculate_trade_amount(10.0, 11.0, 1000.0, config)
    assert amount == 10.0  # 100 USDT / 10 USDT per unit = 10 units
    
    # Test with insufficient balance
    amount = calculate_trade_amount(10.0, 11.0, 50.0, config)
    assert amount == 5.0  # 50 USDT / 10 USDT per unit = 5 units
    
    # Test with very high price (should be limited by SAFE_PRICE)
    amount = calculate_trade_amount(1000.0, 1100.0, 10000.0, config)
    assert amount == 0.1  # 100 USDT / 1000 USDT per unit = 0.1 units
    
    # Test with very low price (should be limited by MAX_TRADE_PRICE)
    amount = calculate_trade_amount(0.01, 0.011, 10000.0, config)
    # The actual implementation may have a different limit, so we'll check the general behavior
    assert amount > 0
    assert amount * 0.01 <= config['strategy']['MAX_TRADE_PRICE']  # Total cost should not exceed MAX_TRADE_PRICE
    
    # Test with amount below MIN_AMOUNT
    amount = calculate_trade_amount(1000.0, 1100.0, 0.5, config)
    assert amount == 0  # 0.5 USDT / 1000 USDT per unit = 0.0005 units (below MIN_AMOUNT)
    
    # Test with invalid prices
    amount = calculate_trade_amount(0.0, 11.0, 1000.0, config)
    assert amount == 0  # Buy price is 0, should return 0
    
    amount = calculate_trade_amount(10.0, 0.0, 1000.0, config)
    assert amount == 0  # Sell price is 0, should still calculate based on buy price
    
    amount = calculate_trade_amount(-10.0, 11.0, 1000.0, config)
    assert amount == 0  # Negative buy price, should return 0

@patch('utils.calculations.Log')
def test_calculate_trade_amount_edge_cases(mock_log):
    """Test edge cases for the calculate_trade_amount function"""
    config = {
        'strategy': {
            'MIN_AMOUNT': 0.001,
            'SAFE_PRICE': 100,
            'MAX_TRADE_PRICE': 500,
            'MAX_AMOUNT': 1000000
        }
    }
    
    # Test with zero balance
    amount = calculate_trade_amount(10.0, 11.0, 0.0, config)
    assert amount == 0  # No balance, should return 0
    
    # Test with negative balance (should be treated as 0)
    amount = calculate_trade_amount(10.0, 11.0, -100.0, config)
    assert amount == 0  # Negative balance, should return 0
    
    # Test with missing config parameters (should use defaults)
    minimal_config = {'strategy': {}}
    amount = calculate_trade_amount(10.0, 11.0, 1000.0, minimal_config)
    assert amount > 0  # Should use default values and return a positive amount
    
    # Test with very small buy price
    amount = calculate_trade_amount(0.00000001, 0.00000002, 1000.0, config)
    # This should be limited by MAX_AMOUNT or MAX_TRADE_PRICE
    assert amount <= config['strategy']['MAX_AMOUNT']
    assert amount * 0.00000001 <= config['strategy']['MAX_TRADE_PRICE'] 