import asyncio
import json
from typing import Dict, Any, List, Tuple
from exchanges import ExchangeFactory
from utils.utils import Log

async def load_config() -> Dict[str, Any]:
    """Load exchange configuration"""
    try:
        with open('../config/config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        Log(f"Failed to load config: {str(e)}")
        return {}

async def get_open_orders(exchange_type: str, exchange: Any, symbol: str) -> List[Dict[str, Any]]:
    """Get open orders from a specific exchange"""
    try:
        orders = await exchange.GetOrders(symbol)
        return orders
    except Exception as e:
        Log(f"Error getting {exchange_type} orders: {str(e)}")
        return []

async def cancel_orders(
    exchange_type: str,
    exchange: Any,
    symbol: str,
    orders: List[Dict[str, Any]]
) -> Tuple[int, int]:
    """Cancel orders on a specific exchange"""
    success_count = 0
    fail_count = 0
    
    for order in orders:
        try:
            if await exchange.CancelOrder(symbol, order['id']):
                success_count += 1
                Log(f"Successfully cancelled order {order['id']} on {exchange_type}")
            else:
                fail_count += 1
                Log(f"Failed to cancel order {order['id']} on {exchange_type}")
        except Exception as e:
            fail_count += 1
            Log(f"Error cancelling order {order['id']} on {exchange_type}: {str(e)}")
    
    return success_count, fail_count

async def cancel_all_orders(symbol: str = "BTC") -> None:
    """Cancel all open orders across all exchanges"""
    # Load configuration
    config = await load_config()
    if not config:
        Log("No configuration found. Please create config/config.json")
        return

    total_success = 0
    total_fail = 0
    exchanges_processed = 0
    
    try:
        # Process each exchange
        for exchange_type, exchange_config in config.items():
            try:
                # Initialize exchange
                exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
                if not exchange:
                    Log(f"Failed to initialize {exchange_type} exchange")
                    continue
                
                try:
                    # Get open orders
                    Log(f"\nProcessing {exchange_type}...")
                    orders = await get_open_orders(exchange_type, exchange, symbol)
                    
                    if not orders:
                        Log(f"No open orders found on {exchange_type}")
                        continue
                    
                    # Cancel orders
                    Log(f"Found {len(orders)} open orders on {exchange_type}")
                    success, fail = await cancel_orders(exchange_type, exchange, symbol, orders)
                    
                    total_success += success
                    total_fail += fail
                    exchanges_processed += 1
                    
                finally:
                    # Close exchange connection
                    await exchange.close()
                    
            except Exception as e:
                Log(f"Error processing {exchange_type}: {str(e)}")
    
    except Exception as e:
        Log(f"Error in main process: {str(e)}")
    
    finally:
        # Log summary
        Log("\nOperation Complete")
        Log("=" * 40)
        Log(f"Exchanges processed: {exchanges_processed}")
        Log(f"Orders cancelled successfully: {total_success}")
        Log(f"Orders failed to cancel: {total_fail}")
        Log("=" * 40)

async def main():
    """Main function"""
    try:
        Log("WARNING: This will cancel ALL open orders across ALL configured exchanges.")
        Log("Are you sure you want to continue? (yes/no)")
        
        response = input().strip().lower()
        if response != 'yes':
            Log("Operation cancelled by user")
            return
            
        await cancel_all_orders()
        
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 