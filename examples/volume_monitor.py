import asyncio
import json
from typing import Dict, Any
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

async def get_market_depth(exchange_type: str, exchange: Any, symbol: str) -> Dict[str, float]:
    """Get market depth and calculate total volume"""
    try:
        depth = await exchange.GetDepth(symbol)
        
        # Calculate total volume on ask side
        ask_volume = sum(amount for _, amount in depth.Asks)
        ask_value = sum(price * amount for price, amount in depth.Asks)
        
        # Calculate total volume on bid side
        bid_volume = sum(amount for _, amount in depth.Bids)
        bid_value = sum(price * amount for price, amount in depth.Bids)
        
        # Calculate mid price
        mid_price = (depth.Asks[0][0] + depth.Bids[0][0]) / 2 if depth.Asks and depth.Bids else 0
        
        return {
            'ask_volume': ask_volume,
            'ask_value': ask_value,
            'bid_volume': bid_volume,
            'bid_value': bid_value,
            'mid_price': mid_price,
            'best_ask': depth.Asks[0][0] if depth.Asks else 0,
            'best_bid': depth.Bids[0][0] if depth.Bids else 0
        }
    except Exception as e:
        Log(f"Error getting {exchange_type} market depth: {str(e)}")
        return {}

def format_number(value: float) -> str:
    """Format number with appropriate precision"""
    if value == 0:
        return "0.00"
    elif value >= 1000000:
        return f"{value/1000000:.2f}M"
    elif value >= 1000:
        return f"{value/1000:.2f}K"
    elif abs(value) < 0.0001:
        return f"{value:.8f}"
    elif abs(value) < 0.01:
        return f"{value:.6f}"
    else:
        return f"{value:.2f}"

async def Log_volume_summary(volumes: Dict[str, Dict[str, float]]) -> None:
    """Log formatted volume summary"""
    # Calculate totals
    total_ask_volume = sum(v.get('ask_volume', 0) for v in volumes.values())
    total_ask_value = sum(v.get('ask_value', 0) for v in volumes.values())
    total_bid_volume = sum(v.get('bid_volume', 0) for v in volumes.values())
    total_bid_value = sum(v.get('bid_value', 0) for v in volumes.values())
    
    # Log header
    Log("\nMarket Volume Summary")
    Log("=" * 120)
    Log(f"{'Exchange':<12} {'Mid Price':<12} {'Best Ask':<12} {'Best Bid':<12} "
          f"{'Ask Vol':<12} {'Ask Val':<12} {'Bid Vol':<12} {'Bid Val':<12} {'Share %':<10}")
    Log("-" * 120)
    
    # Log each exchange's volumes
    total_value = (total_ask_value + total_bid_value) / 2
    for exchange in sorted(volumes.keys()):
        v = volumes[exchange]
        if not v:
            continue
            
        exchange_value = (v.get('ask_value', 0) + v.get('bid_value', 0)) / 2
        market_share = (exchange_value / total_value * 100) if total_value > 0 else 0
        
        Log(
            f"{exchange.upper():<12} "
            f"{format_number(v.get('mid_price', 0)):<12} "
            f"{format_number(v.get('best_ask', 0)):<12} "
            f"{format_number(v.get('best_bid', 0)):<12} "
            f"{format_number(v.get('ask_volume', 0)):<12} "
            f"{format_number(v.get('ask_value', 0)):<12} "
            f"{format_number(v.get('bid_volume', 0)):<12} "
            f"{format_number(v.get('bid_value', 0)):<12} "
            f"{format_number(market_share):<10}"
        )
    
    # Log totals
    Log("-" * 120)
    Log(
        f"{'TOTAL':<12} "
        f"{'':<12} "
        f"{'':<12} "
        f"{'':<12} "
        f"{format_number(total_ask_volume):<12} "
        f"{format_number(total_ask_value):<12} "
        f"{format_number(total_bid_volume):<12} "
        f"{format_number(total_bid_value):<12} "
        f"100.00"
    )
    Log("=" * 120)

async def monitor_volumes(symbol: str = "BTC", update_interval: int = 5) -> None:
    """Monitor trading volumes across all exchanges"""
    while True:
        try:
            # Load configuration
            config = await load_config()
            if not config:
                Log("No configuration found. Please create config/config.json")
                return

            # Get volumes from all exchanges
            volumes = {}
            for exchange_type, exchange_config in config.items():
                try:
                    exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
                    if exchange:
                        volumes[exchange_type] = await get_market_depth(exchange_type, exchange, symbol)
                        await exchange.close()
                except Exception as e:
                    Log(f"Error getting {exchange_type} volumes: {str(e)}")
            
            # Clear screen and Log summary
            Log("\033[2J\033[H")  # Clear screen and move cursor to top
            await Log_volume_summary(volumes)
            
            # Wait for next update
            Log(f"\nMonitoring {symbol}/USDT volumes. Updating every {update_interval} seconds. Press Ctrl+C to exit.")
            await asyncio.sleep(update_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            Log(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(5)

async def main():
    """Main function"""
    try:
        await monitor_volumes()
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main())