import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime
from exchanges import ExchangeFactory
from utils.utils import Log

async def load_config() -> Dict[str, Any]:
    """Load exchange configuration"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'config.json')
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('exchanges', {})
    except Exception as e:
        Log(f"Failed to load config: {str(e)}")
        return {}

async def get_open_orders(exchange_type: str, exchange: Any, symbol: str) -> List[Dict[str, Any]]:
    """Get open orders from an exchange"""
    try:
        orders = await exchange.GetOrders(symbol)
        return orders
    except Exception as e:
        Log(f"Error getting {exchange_type} orders: {str(e)}")
        return []

def format_number(value: float) -> str:
    """Format number with appropriate precision"""
    if value == 0:
        return "0.00"
    elif value < 0.0001:
        return f"{value:.8f}"
    elif value < 0.01:
        return f"{value:.6f}"
    else:
        return f"{value:.2f}"

async def Log_orders_summary(orders_by_exchange: Dict[str, List[Dict[str, Any]]], symbol: str) -> None:
    """Log formatted orders summary"""
    total_orders = sum(len(orders) for orders in orders_by_exchange.values())
    
    # Log header
    Log(f"\n{symbol}/USDT Open Orders Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    Log("=" * 120)
    Log(f"{'Exchange':<12} {'Order ID':<24} {'Type':<6} {'Price':<12} {'Amount':<12} {'Filled':<12} {'Status':<12}")
    Log("-" * 120)
    
    # Log orders for each exchange
    for exchange in sorted(orders_by_exchange.keys()):
        orders = orders_by_exchange[exchange]
        if not orders:
            Log(f"{exchange.upper():<12} No open orders")
            continue
            
        for i, order in enumerate(orders):
            # Log exchange name only for first order
            exchange_name = exchange.upper() if i == 0 else ""
            
            Log(
                f"{exchange_name:<12} "
                f"{order['id']:<24} "
                f"{'SELL' if order.get('side') == 'sell' else 'BUY':<6} "
                f"{format_number(order.get('price', 0)):<12} "
                f"{format_number(order.get('amount', 0)):<12} "
                f"{format_number(order.get('filled', 0)):<12} "
                f"{order.get('status', 'unknown'):<12}"
            )
    
    # Log summary
    Log("-" * 120)
    Log(f"Total open orders: {total_orders}")
    Log("=" * 120)

async def monitor_orders(symbol: str = "BTC", update_interval: int = 5) -> None:
    """Monitor open orders across all exchanges"""
    while True:
        try:
            # Load configuration
            config = await load_config()
            if not config:
                Log("No configuration found. Please create config/config.json")
                return

            # Get orders from all exchanges
            orders = {}
            for exchange_type, exchange_config in config.items():
                try:
                    exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
                    if exchange:
                        orders[exchange_type] = await get_open_orders(exchange_type, exchange, symbol)
                        await exchange.close()
                except Exception as e:
                    Log(f"Error getting {exchange_type} orders: {str(e)}")
            
            # Clear screen and Log summary
            Log("\033[2J\033[H")  # Clear screen and move cursor to top
            await Log_orders_summary(orders, symbol)
            
            # Wait for next update
            Log(f"\nUpdating every {update_interval} second(s). Press Ctrl+C to exit.")
            await asyncio.sleep(update_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            Log(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(5)

async def main():
    """Main function"""
    try:
        # Get symbol from command line argument or use default
        symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC"
        
        # Get update interval from command line argument or use default
        update_interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        
        Log(f"Starting order monitor for {symbol}/USDT")
        Log(f"Update interval: {update_interval} second(s)")
        
        await monitor_orders(symbol, update_interval)
        
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 