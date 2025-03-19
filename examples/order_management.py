import asyncio
import json
from typing import Dict, Any, List
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

async def place_test_orders(exchange: Any, symbol: str) -> List[str]:
    """Place test orders and return their IDs"""
    order_ids = []
    try:
        # Get current market price
        depth = await exchange.GetDepth(symbol)
        current_price = depth.Bids[0][0]  # Use best bid price
        
        # Place a buy order 2% below current price
        buy_price = current_price * 0.98
        buy_amount = 0.001  # Small test amount
        buy_order = await exchange.Buy(symbol, buy_price, buy_amount)
        order_ids.append(buy_order['id'])
        Log(f"Placed buy order: Price={buy_price}, Amount={buy_amount}")
        
        # Place a sell order 2% above current price
        sell_price = current_price * 1.02
        sell_amount = 0.001  # Small test amount
        sell_order = await exchange.Sell(symbol, sell_price, sell_amount)
        order_ids.append(sell_order['id'])
        Log(f"Placed sell order: Price={sell_price}, Amount={sell_amount}")
        
        return order_ids
        
    except Exception as e:
        Log(f"Error placing test orders: {str(e)}")
        return order_ids

async def monitor_orders(exchange: Any, symbol: str, order_ids: List[str]) -> None:
    """Monitor the status of orders"""
    try:
        while order_ids:
            # Get all open orders
            open_orders = await exchange.GetOrders(symbol)
            open_order_ids = {order['id'] for order in open_orders}
            
            # Check each order
            for order_id in order_ids[:]:  # Use slice to modify list while iterating
                try:
                    # Get specific order details
                    order = await exchange.GetOrder(symbol, order_id)
                    
                    if order['status'] in ['closed', 'filled']:
                        Log(f"Order {order_id} has been filled")
                        order_ids.remove(order_id)
                    elif order['status'] == 'canceled':
                        Log(f"Order {order_id} has been canceled")
                        order_ids.remove(order_id)
                    elif order_id not in open_order_ids:
                        Log(f"Order {order_id} not found in open orders")
                        order_ids.remove(order_id)
                    else:
                        Log(f"Order {order_id} is still open. Filled amount: {order['filled']}")
                
                except Exception as e:
                    Log(f"Error checking order {order_id}: {str(e)}")
            
            # Wait before next check
            await asyncio.sleep(5)
            
    except Exception as e:
        Log(f"Error in order monitoring: {str(e)}")

async def main():
    """Main order management function"""
    # Load configuration
    config = await load_config()
    if not config:
        Log("No configuration found. Please create config/config.json")
        return

    try:
        # Initialize first exchange from config
        exchange_type = next(iter(config))
        exchange = ExchangeFactory.create_exchange(exchange_type, config[exchange_type])
        
        if not exchange:
            Log("Failed to initialize exchange")
            return
            
        Log(f"Using exchange: {exchange_type}")
        
        # Place test orders
        order_ids = await place_test_orders(exchange, "BTC")
        
        if not order_ids:
            Log("No orders were placed")
            return
            
        # Monitor orders for 1 minute
        try:
            monitoring_task = asyncio.create_task(monitor_orders(exchange, "BTC", order_ids))
            await asyncio.sleep(60)  # Monitor for 1 minute
            
            # Cancel remaining orders
            for order_id in order_ids[:]:
                try:
                    if await exchange.CancelOrder("BTC", order_id):
                        Log(f"Cancelled order {order_id}")
                        order_ids.remove(order_id)
                except Exception as e:
                    Log(f"Error cancelling order {order_id}: {str(e)}")
            
            # Wait for monitoring task to complete
            await monitoring_task
            
        except Exception as e:
            Log(f"Error in main monitoring loop: {str(e)}")
    
    except Exception as e:
        Log(f"Error in main: {str(e)}")
    
    finally:
        # Close all exchange connections
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    try:
        # Run the order management example
        asyncio.run(main())
    except KeyboardInterrupt:
        Log("Program terminated by user") 