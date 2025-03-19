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

async def get_all_depths(exchanges: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """Get market depth from all exchanges"""
    depths = {}
    
    async def fetch_depth(ex_name, exchange):
        try:
            return ex_name, await exchange.GetDepth(symbol)
        except Exception as e:
            Log(f"Failed to get {ex_name} market depth: {str(e)}")
            return ex_name, None
    
    # 并发获取所有交易所的深度数据
    tasks = [fetch_depth(ex_name, exchange) for ex_name, exchange in exchanges.items()]
    results = await asyncio.gather(*tasks)
    
    # 处理结果
    for ex_name, depth in results:
        if depth:
            depths[ex_name] = depth
            
    return depths

def find_arbitrage_opportunities(
    depths: Dict[str, Any],
    min_profit_rate: float = 0.001
) -> List[Tuple[str, str, float, float, float, float]]:
    """
    Find arbitrage opportunities between exchanges
    Returns list of (buy_ex, sell_ex, buy_price, sell_price, amount, profit_rate)
    """
    opportunities = []
    
    for buy_ex, buy_depth in depths.items():
        if not buy_depth or not buy_depth.Asks:
            continue
            
        buy_price = buy_depth.Asks[0][0]  # Best ask price
        
        for sell_ex, sell_depth in depths.items():
            if buy_ex == sell_ex or not sell_depth or not sell_depth.Bids:
                continue
                
            sell_price = sell_depth.Bids[0][0]  # Best bid price
            
            if sell_price > buy_price:
                profit_rate = (sell_price - buy_price) / buy_price
                if profit_rate >= min_profit_rate:
                    # Calculate maximum possible trade amount
                    amount = min(buy_depth.Asks[0][1], sell_depth.Bids[0][1])
                    opportunities.append((
                        buy_ex,
                        sell_ex,
                        buy_price,
                        sell_price,
                        amount,
                        profit_rate
                    ))
    
    return opportunities

async def main():
    """Main arbitrage monitoring function"""
    # Load configuration
    config = await load_config()
    if not config:
        Log("No configuration found. Please create config/config.json")
        return

    exchanges = {}
    try:
        # Initialize exchanges
        for exchange_type, exchange_config in config.items():
            exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
            if exchange:
                exchanges[exchange_type] = exchange
                Log(f"Initialized {exchange_type} exchange")
        
        # Monitor for arbitrage opportunities
        while True:
            try:
                # Get market depth from all exchanges
                depths = await get_all_depths(exchanges, "BTC")
                
                # Find arbitrage opportunities
                opportunities = find_arbitrage_opportunities(depths)
                
                # Log opportunities
                for buy_ex, sell_ex, buy_price, sell_price, amount, profit_rate in opportunities:
                    Log(f"\nArbitrage Opportunity Found!")
                    Log(f"Buy from {buy_ex} at {buy_price}")
                    Log(f"Sell on {sell_ex} at {sell_price}")
                    Log(f"Maximum amount: {amount} BTC")
                    Log(f"Profit rate: {profit_rate*100:.2f}%")
                
                # Wait before next check
                await asyncio.sleep(1)
                
            except Exception as e:
                Log(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(1)
    
    except Exception as e:
        Log(f"Error in main: {str(e)}")
    
    finally:
        # Close all exchange connections
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    try:
        # Run the arbitrage monitor
        asyncio.run(main())
    except KeyboardInterrupt:
        Log("Program terminated by user") 