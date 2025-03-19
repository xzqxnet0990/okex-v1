import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from typing import Dict, Any
from exchanges import ExchangeFactory
from utils.utils import Log

async def load_config() -> Dict[str, Any]:
    """Load exchange configuration"""
    try:
        # Get the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'config.json')
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('exchanges', {})
    except Exception as e:
        Log(f"Failed to load config: {str(e)}")
        return {}

async def test_exchange_connection(exchange_type: str, config: Dict[str, Any]) -> bool:
    """Test exchange connection and basic functionality"""
    try:
        # Initialize exchange
        exchange = ExchangeFactory.create_exchange(exchange_type, config)
        if not exchange:
            Log(f"Failed to initialize {exchange_type} exchange")
            return False
            
        Log(f"\nTesting {exchange_type} exchange:")
        
        # Test account info
        try:
            account = await exchange.GetAccount()
            Log("✓ Account info retrieved successfully")
            Log(f"  USDT Balance: {account.Balance}")
            Log(f"  BTC Balance: {account.Stocks}")
        except Exception as e:
            Log(f"✗ Failed to get account info: {str(e)}")
            return False
            
        # Test market depth
        try:
            depth = await exchange.GetDepth("BTC")
            Log("✓ Market depth retrieved successfully")
            Log(f"  Best ask: {depth.Asks[0][0] if depth.Asks else 'N/A'}")
            Log(f"  Best bid: {depth.Bids[0][0] if depth.Bids else 'N/A'}")
        except Exception as e:
            Log(f"✗ Failed to get market depth: {str(e)}")
            return False
            
        # Test open orders
        try:
            orders = await exchange.GetOrders("BTC")
            Log("✓ Open orders retrieved successfully")
            Log(f"  Number of open orders: {len(orders)}")
        except Exception as e:
            Log(f"✗ Failed to get open orders: {str(e)}")
            return False
            
        return True
        
    except Exception as e:
        Log(f"Error testing {exchange_type} exchange: {str(e)}")
        return False
    finally:
        if exchange:
            await exchange.close()

async def main():
    """Main test function"""
    # Load configuration
    config = await load_config()
    if not config:
        Log("No configuration found. Please create config/config.json")
        return

    results = []
    try:
        # Test each exchange
        for exchange_type, exchange_config in config.items():
            success = await test_exchange_connection(exchange_type, exchange_config)
            results.append((exchange_type, success))
        
        # Log summary
        Log("\nTest Results Summary:")
        Log("=" * 40)
        for exchange_type, success in results:
            status = "PASS" if success else "FAIL"
            Log(f"{exchange_type}: {status}")
    
    except Exception as e:
        Log(f"Error in main: {str(e)}")
    
    finally:
        # Close all exchange connections
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    try:
        # Run the configuration test
        asyncio.run(main())
    except KeyboardInterrupt:
        Log("Program terminated by user") 