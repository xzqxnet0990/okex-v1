import asyncio
import json
from typing import Dict, Any
from exchanges.mexc import MEXCExchange
from exchanges.htx import HTXExchange
from exchanges.coinex import CoinExExchange
from exchanges.kucoin import KuCoinExchange
from exchanges.gateio import GateIOExchange
from exchanges.bitget import BitgetExchange
from exchanges.futures_mexc import FuturesMEXCExchange
from exchanges.bybit import BybitExchange
async def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    with open('config/config.json', 'r') as f:
        return json.load(f)

async def load_supported_exchanges() -> Dict[str, Any]:
    """加载支持的交易所信息"""
    with open('config/supported_exchanges.json', 'r') as f:
        return json.load(f)

def create_exchange(exchange_name: str, config: Dict[str, Any]) -> Any:
    """创建交易所实例"""
    exchange_map = {
        'MEXC': MEXCExchange,
        'HTX': HTXExchange,
        'CoinEx': CoinExExchange,
        'KuCoin': KuCoinExchange,
        'Gate': GateIOExchange,
        'Bitget': BitgetExchange,
        'Futures_MEXC': FuturesMEXCExchange,
        'Bybit': BybitExchange
    }
    
    if exchange_name not in exchange_map:
        return None
        
    exchange_config = config['exchanges'].get(exchange_name)
    if not exchange_config:
        return None
        
    return exchange_map[exchange_name](exchange_config)

async def get_fees(exchange, symbol: str) -> Dict[str, float]:
    """获取交易对的maker和taker费率"""
    try:
        # 1. 首先尝试从配置中获取费率
        if hasattr(exchange, 'fee_config'):
            # 检查是否有币种特定费率
            symbol_fees = exchange.fee_config.get('symbol_fees', {}).get(symbol)
            if symbol_fees:
                return {
                    'maker': symbol_fees['maker'],
                    'taker': symbol_fees['taker']
                }
            
            # 使用默认费率
            default_fees = exchange.fee_config.get('default_fees', {})
            if default_fees:
                return {
                    'maker': default_fees['maker'],
                    'taker': default_fees['taker']
                }
        
        # 2. 如果配置中没有费率，尝试从交易所API获取
        try:
            market = await exchange.exchange.fetch_market(f"{symbol}/USDT")
            if market and 'maker' in market and 'taker' in market:
                return {
                    'maker': market['maker'],
                    'taker': market['taker']
                }
        except Exception as e:
            pass
        
        # 3. 如果以上方法都失败，使用交易所默认费率
        return {
            'maker': exchange.maker_fee,
            'taker': exchange.taker_fee
        }
        
    except Exception as e:
        print(f"获取{exchange.name} {symbol}费率失败: {str(e)}")
        return {
            'maker': None,
            'taker': None
        }

async def main():
    """主函数"""
    # 加载配置和支持的交易所信息
    config = await load_config()
    supported_exchanges = await load_supported_exchanges()
    
    # 创建交易所实例缓存，避免重复创建
    exchange_instances = {}
    
    try:
        # 遍历每个币种和其支持的交易所
        for symbol, exchanges in supported_exchanges.items():
            print(f"\n=== {symbol} 交易对费率 ===")
            
            for exchange_name in exchanges:
                # 从缓存获取或创建交易所实例
                if exchange_name not in exchange_instances:
                    exchange = create_exchange(exchange_name, config)
                    if not exchange:
                        print(f"{exchange_name}: 不支持或配置缺失")
                        continue
                    exchange_instances[exchange_name] = exchange
                else:
                    exchange = exchange_instances[exchange_name]
                
                # 获取费率
                fees = await get_fees(exchange, symbol)
                
                # 打印费率信息
                if fees['maker'] is not None and fees['taker'] is not None:
                    print(f"{exchange_name}:")
                    print(f"  Maker费率: {fees['maker']*100}%")
                    print(f"  Taker费率: {fees['taker']*100}%")
                else:
                    print(f"{exchange_name}: 获取费率失败")
    
    finally:
        # 关闭所有交易所连接
        for exchange in exchange_instances.values():
            await exchange.close()

if __name__ == "__main__":
    asyncio.run(main()) 