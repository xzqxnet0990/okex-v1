import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.utils import Log, _N

# 静态深度数据
STATIC_DEPTHS = {
    "MAGA": {
        "CoinEx": {
            "asks": [
                (0.1205, 1000),  # price, amount
                (0.1206, 2000),
                (0.1207, 3000),
            ],
            "bids": [
                (0.1204, 1500),
                (0.1203, 2500),
                (0.1202, 3500),
            ]
        },
        "Gate": {
            "asks": [
                (0.1208, 800),
                (0.1209, 1800),
                (0.1210, 2800),
            ],
            "bids": [
                (0.1207, 1200),
                (0.1206, 2200),
                (0.1205, 3200),
            ]
        },
        "HTX": {
            "asks": [
                (0.1206, 1200),
                (0.1207, 2200),
                (0.1208, 3200),
            ],
            "bids": [
                (0.1205, 1700),
                (0.1204, 2700),
                (0.1203, 3700),
            ]
        },
        "MEXC": {
            "asks": [
                (0.1204, 900),
                (0.1205, 1900),
                (0.1206, 2900),
            ],
            "bids": [
                (0.1203, 1300),
                (0.1202, 2300),
                (0.1201, 3300),
            ]
        }
    }
}

def Log_market_depths():
    """打印市场深度数据"""
    for coin, exchanges in STATIC_DEPTHS.items():
        Log(f"\n{coin} Market Depths:")
        Log("=" * 80)
        
        for exchange, depth in exchanges.items():
            Log(f"\n{exchange}:")
            Log("-" * 40)
            
            Log("Asks (Sell Orders):")
            for price, amount in depth["asks"]:
                Log(f"Price: {_N(price, 4)}, Amount: {_N(amount, 2)}")
            
            Log("\nBids (Buy Orders):")
            for price, amount in depth["bids"]:
                Log(f"Price: {_N(price, 4)}, Amount: {_N(amount, 2)}")

def find_arbitrage_opportunities():
    """查找套利机会"""
    opportunities = []
    
    for coin, exchanges in STATIC_DEPTHS.items():
        exchange_names = list(exchanges.keys())
        
        for i, buy_exchange in enumerate(exchange_names):
            buy_price = exchanges[buy_exchange]["asks"][0][0]  # 最低卖价
            
            for sell_exchange in exchange_names[i+1:]:
                sell_price = exchanges[sell_exchange]["bids"][0][0]  # 最高买价
                
                if sell_price > buy_price:
                    profit_rate = (sell_price - buy_price) / buy_price * 100
                    
                    # 计算可交易数量
                    buy_amount = exchanges[buy_exchange]["asks"][0][1]
                    sell_amount = exchanges[sell_exchange]["bids"][0][1]
                    trade_amount = min(buy_amount, sell_amount)
                    
                    opportunities.append({
                        "coin": coin,
                        "buy_exchange": buy_exchange,
                        "sell_exchange": sell_exchange,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "profit_rate": profit_rate,
                        "trade_amount": trade_amount
                    })
    
    return opportunities

def Log_arbitrage_opportunities(opportunities):
    """打印套利机会"""
    if not opportunities:
        Log("\nNo arbitrage opportunities found.")
        return
        
    Log("\nArbitrage Opportunities Found:")
    Log("=" * 100)
    
    for opp in opportunities:
        Log(f"\nCoin: {opp['coin']}")
        Log(f"Buy from {opp['buy_exchange']} at {_N(opp['buy_price'], 4)}")
        Log(f"Sell on {opp['sell_exchange']} at {_N(opp['sell_price'], 4)}")
        Log(f"Profit Rate: {_N(opp['profit_rate'], 2)}%")
        Log(f"Maximum Trade Amount: {_N(opp['trade_amount'], 2)}")
        Log("-" * 80)

def main():
    """主函数"""
    Log("Static Market Depth Test")
    Log("=" * 80)
    
    # 打印市场深度数据
    Log_market_depths()
    
    # 查找并打印套利机会
    opportunities = find_arbitrage_opportunities()
    Log_arbitrage_opportunities(opportunities)

if __name__ == "__main__":
    main() 