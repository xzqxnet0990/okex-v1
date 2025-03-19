from strategy.spot_arbitrage import SpotArbitrage
from strategy.trade_type import TradeType
from strategy.hedge_opportunity import _check_hedge_opportunity
import asyncio

# Create a mock account and depths for testing
class MockAccount:
    def __init__(self):
        self.exchanges = {'exchange1': None, 'exchange2': None}
        
    def get_pending_orders(self):
        return []
    
    def get_unhedged_position(self, coin):
        # Significant difference in positions to trigger hedge
        positions = {'exchange1': 2.0, 'exchange2': 0.5}
        return positions
    
    def get_balance(self, coin, exchange):
        return 1000.0
    
    def get_fee(self, exchange, fee_type):
        return 0.001

# Create a simple test
async def test():
    # Create a SpotArbitrage instance with minimal config
    config = {
        'strategy': {
            'MIN_AMOUNT': 0.001,
            'MIN_PROFIT_THRESHOLD': 0.002,
            'MIN_BASIS': 0.001,
            'SPOT_EXCHANGES': ['exchange1', 'exchange2']
        }
    }
    
    spot_arb = SpotArbitrage(config)
    spot_arb.spot_exchanges = ['exchange1', 'exchange2']  # Ensure spot_exchanges is set
    
    # Create mock depths with significant price difference
    all_depths = {
        'btc': {
            'exchange1': {
                'bids': [[40000, 1.0]],
                'asks': [[40100, 1.0]]
            },
            'exchange2': {
                'bids': [[40200, 1.0]],
                'asks': [[40300, 1.0]]
            }
        }
    }
    
    # Test determine_trade_type
    account = MockAccount()
    result = await spot_arb.determine_trade_type('btc', account, all_depths)
    
    print("\nDetermine Trade Type Test Results:")
    print(f'Trade type: {result[0]}')
    print(f'Buy price: {result[1]}')
    print(f'Sell price: {result[2]}')
    print(f'Amount: {result[3]}')
    print(f'Buy exchange: {result[4]}')
    print(f'Sell exchange: {result[5]}')
    
    # Verify the result is as expected
    assert result[0] == TradeType.HEDGE_SELL, f"Expected {TradeType.HEDGE_SELL}, got {result[0]}"
    assert result[1] == 40000, f"Expected buy price 40000, got {result[1]}"
    assert result[2] == 40000, f"Expected sell price 40000, got {result[2]}"
    assert result[3] == 0.75, f"Expected amount 0.75, got {result[3]}"
    assert result[4] == "", f"Expected buy exchange '', got {result[4]}"
    assert result[5] == "exchange1", f"Expected sell exchange 'exchange1', got {result[5]}"
    
    print("\nAll tests passed successfully!")

# Run the test
if __name__ == "__main__":
    asyncio.run(test()) 