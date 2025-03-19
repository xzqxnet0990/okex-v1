import asyncio
import json
from typing import Dict, Any, Tuple
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

async def get_current_prices(exchange_type: str, exchange: Any, symbol: str) -> Tuple[float, float]:
    """Get current market prices from an exchange"""
    try:
        depth = await exchange.GetDepth(symbol)
        mid_price = (depth.Asks[0][0] + depth.Bids[0][0]) / 2 if depth.Asks and depth.Bids else 0
        return mid_price, True
    except Exception as e:
        Log(f"Error getting {exchange_type} prices: {str(e)}")
        return 0, False

async def get_account_balances(exchange_type: str, exchange: Any) -> Dict[str, float]:
    """Get account balances from an exchange"""
    try:
        account = await exchange.GetAccount()
        return {
            'USDT': account.Balance + account.FrozenBalance,
            'BTC': account.Stocks + account.FrozenStocks
        }
    except Exception as e:
        Log(f"Error getting {exchange_type} balances: {str(e)}")
        return {'USDT': 0, 'BTC': 0}

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

async def calculate_pnl(initial_investment: float = 0) -> None:
    """Calculate profit/loss across all exchanges"""
    # Load configuration
    config = await load_config()
    if not config:
        Log("No configuration found. Please create config/config.json")
        return

    total_usdt = 0
    total_btc = 0
    valid_price = False
    btc_price = 0
    
    Log("\nGathering data from exchanges...")
    Log("=" * 80)
    
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
                    # Get balances
                    balances = await get_account_balances(exchange_type, exchange)
                    total_usdt += balances['USDT']
                    total_btc += balances['BTC']
                    
                    # Get current BTC price
                    if not valid_price:
                        price, success = await get_current_prices(exchange_type, exchange, "BTC")
                        if success:
                            btc_price = price
                            valid_price = True
                    
                    # Log exchange summary
                    Log(f"\n{exchange_type.upper()}:")
                    Log(f"USDT Balance: {format_number(balances['USDT'])}")
                    Log(f"BTC Balance: {format_number(balances['BTC'])}")
                    
                finally:
                    # Close exchange connection
                    await exchange.close()
                    
            except Exception as e:
                Log(f"Error processing {exchange_type}: {str(e)}")
    
        # Calculate total value in USDT
        total_value_usdt = total_usdt
        if valid_price and total_btc > 0:
            total_value_usdt += total_btc * btc_price
        
        # Calculate profit/loss
        pnl = total_value_usdt - initial_investment if initial_investment > 0 else 0
        pnl_percentage = (pnl / initial_investment * 100) if initial_investment > 0 else 0
        
        # Log summary
        Log("\nPortfolio Summary")
        Log("=" * 80)
        Log(f"Total USDT: {format_number(total_usdt)}")
        Log(f"Total BTC: {format_number(total_btc)}")
        if valid_price:
            Log(f"Current BTC Price: {format_number(btc_price)} USDT")
            Log(f"Total Portfolio Value: {format_number(total_value_usdt)} USDT")
        else:
            Log("Warning: Could not get current BTC price")
            Log(f"Total Portfolio Value (excluding BTC): {format_number(total_value_usdt)} USDT")
        
        if initial_investment > 0:
            Log(f"\nInitial Investment: {format_number(initial_investment)} USDT")
            Log(f"Total Profit/Loss: {format_number(pnl)} USDT ({format_number(pnl_percentage)}%)")
        
        Log("=" * 80)
    
    except Exception as e:
        Log(f"Error in main process: {str(e)}")

async def main():
    """Main function"""
    try:
        # Get initial investment amount
        Log("Enter your initial investment in USDT (or press Enter to skip):")
        response = input().strip()
        
        initial_investment = float(response) if response else 0
        await calculate_pnl(initial_investment)
        
    except ValueError:
        Log("Invalid input. Please enter a valid number.")
    except KeyboardInterrupt:
        Log("Program terminated by user")
    finally:
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 