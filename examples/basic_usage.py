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

async def Log_account_info(exchange_name: str, exchange: Any) -> None:
    """Log account balance information"""
    try:
        account = await exchange.GetAccount()
        Log(f"\n{exchange_name} Account Info:")
        Log(f"USDT Balance: {account.Balance}")
        Log(f"BTC Balance: {account.Stocks}")
        Log(f"Frozen USDT: {account.FrozenBalance}")
        Log(f"Frozen BTC: {account.FrozenStocks}")
    except Exception as e:
        Log(f"Failed to get {exchange_name} account info: {str(e)}")

async def Log_market_depth(exchange_name: str, exchange: Any, symbol: str) -> None:
    """Log market depth information"""
    try:
        depth = await exchange.GetDepth(symbol)
        Log(f"\n{exchange_name} Market Depth for {symbol}:")
        Log("Top 5 Asks:")
        for price, amount in depth.Asks[:5]:
            Log(f"Price: {price}, Amount: {amount}")
        Log("\nTop 5 Bids:")
        for price, amount in depth.Bids[:5]:
            Log(f"Price: {price}, Amount: {amount}")
    except Exception as e:
        Log(f"Failed to get {exchange_name} market depth: {str(e)}")

async def main():
    """Main example function"""
    # Load configuration
    config = await load_config()
    if not config:
        Log("No configuration found. Please create config/config.json")
        return

    try:
        # Initialize exchanges
        for exchange_type, exchange_config in config.items():
            exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
            if exchange:
                # Log account information
                await Log_account_info(exchange_type, exchange)
                
                # Log market depth for BTC/USDT
                await Log_market_depth(exchange_type, exchange, "BTC")
                
                # Small delay between exchanges
                await asyncio.sleep(1)
    
    except Exception as e:
        Log(f"Error in main: {str(e)}")
    
    finally:
        # Close all exchange connections
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    # Run the example
    asyncio.run(main()) 