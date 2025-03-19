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

async def get_market_prices(exchange_type: str, exchange: Any, symbol: str) -> Dict[str, Tuple[float, float]]:
    """Get best bid and ask prices from a specific exchange"""
    try:
        depth = await exchange.GetDepth(symbol)
        return {
            'ask': (depth.Asks[0][0], depth.Asks[0][1]) if depth.Asks else (0, 0),
            'bid': (depth.Bids[0][0], depth.Bids[0][1]) if depth.Bids else (0, 0)
        }
    except Exception as e:
        Log(f"Error getting {exchange_type} prices: {str(e)}")
        return {}

def calculate_spreads(prices: Dict[str, Dict[str, Tuple[float, float]]]) -> List[Dict[str, Any]]:
    """Calculate spreads between exchanges"""
    spreads = []
    
    for ex1 in prices:
        for ex2 in prices:
            if ex1 >= ex2:  # Skip duplicate pairs and ensure consistent ordering
                continue
                
            p1 = prices[ex1]
            p2 = prices[ex2]
            
            if not p1 or not p2:
                continue
                
            # Calculate cross-exchange spreads
            ex1_bid, ex1_bid_size = p1['bid']
            ex2_ask, ex2_ask_size = p2['ask']
            if ex1_bid > 0 and ex2_ask > 0:
                spread1 = (ex1_bid - ex2_ask) / ex2_ask * 100
                max_amount1 = min(ex1_bid_size, ex2_ask_size)
                
                spreads.append({
                    'buy_exchange': ex2,
                    'sell_exchange': ex1,
                    'buy_price': ex2_ask,
                    'sell_price': ex1_bid,
                    'spread': spread1,
                    'max_amount': max_amount1
                })
            
            # Calculate reverse spread
            ex2_bid, ex2_bid_size = p2['bid']
            ex1_ask, ex1_ask_size = p1['ask']
            if ex2_bid > 0 and ex1_ask > 0:
                spread2 = (ex2_bid - ex1_ask) / ex1_ask * 100
                max_amount2 = min(ex2_bid_size, ex1_ask_size)
                
                spreads.append({
                    'buy_exchange': ex1,
                    'sell_exchange': ex2,
                    'buy_price': ex1_ask,
                    'sell_price': ex2_bid,
                    'spread': spread2,
                    'max_amount': max_amount2
                })
    
    return sorted(spreads, key=lambda x: x['spread'], reverse=True)

def format_number(value: float) -> str:
    """Format number with appropriate precision"""
    if value == 0:
        return "0.00"
    elif abs(value) < 0.0001:
        return f"{value:.8f}"
    elif abs(value) < 0.01:
        return f"{value:.6f}"
    else:
        return f"{value:.2f}"

async def Log_market_summary(
    prices: Dict[str, Dict[str, Tuple[float, float]]],
    spreads: List[Dict[str, Any]]
) -> None:
    """Log formatted market summary"""
    # Log exchange prices
    Log("\nExchange Prices")
    Log("=" * 80)
    Log(f"{'Exchange':<15} {'Ask Price':<15} {'Ask Size':<15} {'Bid Price':<15} {'Bid Size':<15}")
    Log("-" * 80)
    
    for exchange in sorted(prices.keys()):
        p = prices[exchange]
        ask_price, ask_size = p.get('ask', (0, 0))
        bid_price, bid_size = p.get('bid', (0, 0))
        Log(
            f"{exchange.upper():<15} "
            f"{format_number(ask_price):<15} "
            f"{format_number(ask_size):<15} "
            f"{format_number(bid_price):<15} "
            f"{format_number(bid_size):<15}"
        )
    
    # Log spreads
    if spreads:
        Log("\nCross-Exchange Spreads")
        Log("=" * 100)
        Log(f"{'Buy Exchange':<15} {'Sell Exchange':<15} {'Buy Price':<15} {'Sell Price':<15} {'Spread %':<10} {'Max Amount':<15}")
        Log("-" * 100)
        
        for spread in spreads:
            if spread['spread'] > 0:  # Only show positive spreads
                Log(
                    f"{spread['buy_exchange'].upper():<15} "
                    f"{spread['sell_exchange'].upper():<15} "
                    f"{format_number(spread['buy_price']):<15} "
                    f"{format_number(spread['sell_price']):<15} "
                    f"{format_number(spread['spread']):<10} "
                    f"{format_number(spread['max_amount']):<15}"
                )
    
    Log("=" * 100)

async def monitor_spreads(symbol: str = "BTC", min_spread: float = 0.1, update_interval: int = 1) -> None:
    """Monitor price spreads across all exchanges"""
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
            
            # Calculate spreads
            spreads = calculate_spreads(prices)
            
            # Filter spreads
            spreads = [s for s in spreads if s['spread'] >= min_spread]
            
            # Clear screen and Log summary
            Log("\033[2J\033[H")  # Clear screen and move cursor to top
            await Log_market_summary(prices, spreads)
            
            # Wait for next update
            Log(f"\nMonitoring {symbol}/USDT spreads >= {min_spread}%. Updating every {update_interval} second(s). Press Ctrl+C to exit.")
            await asyncio.sleep(update_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            Log(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(5)

async def main():
    """Main function"""
    try:
        # Get minimum spread threshold
        Log("Enter minimum spread percentage to display (default: 0.1):")
        response = input().strip()
        
        min_spread = float(response) if response else 0.1
        await monitor_spreads(min_spread=min_spread)
        
    except ValueError:
        Log("Invalid input. Please enter a valid number.")
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 