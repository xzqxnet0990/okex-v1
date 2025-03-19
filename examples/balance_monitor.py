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

async def get_exchange_balances(exchange_type: str, config: Dict[str, Any]) -> Dict[str, float]:
    """Get balances from a specific exchange"""
    try:
        exchange = ExchangeFactory.create_exchange(exchange_type, config)
        if not exchange:
            Log(f"Failed to initialize {exchange_type} exchange")
            return {}
            
        account = await exchange.GetAccount()
        return {
            'USDT': account.Balance,
            'BTC': account.Stocks,
            'Frozen USDT': account.FrozenBalance,
            'Frozen BTC': account.FrozenStocks
        }
        
    except Exception as e:
        Log(f"Error getting {exchange_type} balances: {str(e)}")
        return {}
    finally:
        if exchange:
            await exchange.close()

def format_balance(balance: float) -> str:
    """Format balance with appropriate precision"""
    if balance == 0:
        return "0.00"
    elif balance < 0.0001:
        return f"{balance:.8f}"
    elif balance < 0.01:
        return f"{balance:.6f}"
    else:
        return f"{balance:.2f}"

async def Log_balances(balances: Dict[str, Dict[str, float]]) -> None:
    """Log formatted balance information"""
    # Calculate totals
    total_usdt = sum(b.get('USDT', 0) + b.get('Frozen USDT', 0) for b in balances.values())
    total_btc = sum(b.get('BTC', 0) + b.get('Frozen BTC', 0) for b in balances.values())
    
    # Log header
    Log("\nExchange Balance Summary")
    Log("=" * 80)
    Log(f"{'Exchange':<15} {'USDT':<15} {'Frozen USDT':<15} {'BTC':<15} {'Frozen BTC':<15}")
    Log("-" * 80)
    
    # Log each exchange's balances
    for exchange in sorted(balances.keys()):
        b = balances[exchange]
        Log(
            f"{exchange.upper():<15} "
            f"{format_balance(b.get('USDT', 0)):<15} "
            f"{format_balance(b.get('Frozen USDT', 0)):<15} "
            f"{format_balance(b.get('BTC', 0)):<15} "
            f"{format_balance(b.get('Frozen BTC', 0)):<15}"
        )
    
    # Log totals
    Log("-" * 80)
    Log(
        f"{'TOTAL':<15} "
        f"{format_balance(total_usdt):<15} "
        f"{'':<15} "
        f"{format_balance(total_btc):<15}"
    )
    Log("=" * 80)

async def monitor_balances(update_interval: int = 60) -> None:
    """Monitor balances across all exchanges"""
    while True:
        try:
            # Load configuration
            config = await load_config()
            if not config:
                Log("No configuration found. Please create config/config.json")
                return

            # Get balances from all exchanges
            balances = {}
            for exchange_type, exchange_config in config.items():
                balances[exchange_type] = await get_exchange_balances(exchange_type, exchange_config)
            
            # Clear screen and Log balances
            Log("\033[2J\033[H")  # Clear screen and move cursor to top
            await Log_balances(balances)
            
            # Wait for next update
            Log(f"\nUpdating every {update_interval} seconds. Press Ctrl+C to exit.")
            await asyncio.sleep(update_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            Log(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(5)

async def main():
    """Main function"""
    try:
        await monitor_balances()
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 