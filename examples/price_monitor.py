import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from typing import Dict, Any
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

async def get_market_prices(exchange_type: str, exchange: Any, symbol: str) -> Dict[str, float]:
    """Get market prices from an exchange"""
    try:
        depth = await exchange.GetDepth(symbol)
        
        # Calculate mid price and spread
        best_ask = depth.Asks[0][0] if depth.Asks else 0
        best_bid = depth.Bids[0][0] if depth.Bids else 0
        mid_price = (best_ask + best_bid) / 2 if best_ask and best_bid else 0
        spread = ((best_ask - best_bid) / mid_price * 100) if mid_price else 0
        
        return {
            'best_ask': best_ask,
            'best_bid': best_bid,
            'mid_price': mid_price,
            'spread': spread,
            'ask_volume': depth.Asks[0][1] if depth.Asks else 0,
            'bid_volume': depth.Bids[0][1] if depth.Bids else 0
        }
    except Exception as e:
        Log(f"Error getting {exchange_type} prices: {str(e)}")
        return {}

def format_price(value: float) -> str:
    """Format price with appropriate precision"""
    if value == 0:
        return "N/A"
    elif value < 0.0001:
        return f"{value:.8f}"
    elif value < 0.01:
        return f"{value:.6f}"
    elif value < 1:
        return f"{value:.4f}"
    else:
        return f"{value:.2f}"

async def Log_price_summary(
    prices: Dict[str, Dict[str, float]],
    symbol: str,
    show_volumes: bool = True
) -> None:
    """Log formatted price summary"""
    # Calculate average price across exchanges
    valid_prices = [p['mid_price'] for p in prices.values() if p.get('mid_price', 0) > 0]
    avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0
    
    # Log header
    Log(f"\n{symbol}/USDT Price Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    Log("=" * 100)
    header = f"{'Exchange':<12} {'Best Bid':<12} {'Best Ask':<12} {'Mid Price':<12} {'Spread %':<10}"
    if show_volumes:
        header += f" {'Bid Vol':<12} {'Ask Vol':<12}"
    Log(header)
    Log("-" * 100)
    
    # Log each exchange's prices
    for exchange in sorted(prices.keys()):
        p = prices[exchange]
        if not p:
            continue
            
        # Calculate price deviation from average
        deviation = ((p['mid_price'] - avg_price) / avg_price * 100) if avg_price and p['mid_price'] else 0
        
        # Format line
        line = (
            f"{exchange.upper():<12} "
            f"{format_price(p.get('best_bid', 0)):<12} "
            f"{format_price(p.get('best_ask', 0)):<12} "
            f"{format_price(p.get('mid_price', 0)):<12} "
            f"{format_price(p.get('spread', 0)):<10}"
        )
        if show_volumes:
            line += f" {format_price(p.get('bid_volume', 0)):<12} {format_price(p.get('ask_volume', 0)):<12}"
        
        # Add deviation indicator
        if abs(deviation) >= 0.1:  # Show if deviation is >= 0.1%
            line += f" {'↑' if deviation > 0 else '↓'}{abs(deviation):.2f}%"
            
        Log(line)
    
    # Log average
    Log("-" * 100)
    Log(f"{'AVERAGE':<12} {'':<12} {'':<12} {format_price(avg_price):<12}")
    Log("=" * 100)

async def monitor_prices(
    symbol: str = "BTC",
    update_interval: int = 1,
    show_volumes: bool = True
) -> None:
    """Monitor prices across all exchanges"""
    while True:
        try:
            # Load configuration
            config = await load_config()
            if not config:
                Log("No configuration found. Please create config/config.json")
                return

            # Get prices from all exchanges
            prices = {}
            for exchange_type, exchange_config in config.items():
                try:
                    exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
                    if exchange:
                        prices[exchange_type] = await get_market_prices(exchange_type, exchange, symbol)
                        await exchange.close()
                except Exception as e:
                    Log(f"Error getting {exchange_type} prices: {str(e)}")
            
            # Clear screen and Log summary
            Log("\033[2J\033[H")  # Clear screen and move cursor to top
            await Log_price_summary(prices, symbol, show_volumes)
            
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
        update_interval = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        
        Log(f"Starting price monitor for {symbol}/USDT")
        Log(f"Update interval: {update_interval} second(s)")
        
        await monitor_prices(symbol, update_interval)
        
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 