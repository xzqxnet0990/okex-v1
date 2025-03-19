import sys
import os
import json
import asyncio
import ccxt.async_support as ccxt
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List
from utils.utils import Log, retry


async def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'config.json')
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            return {
                'exchanges': config.get('exchanges', {}),
                'coins': config.get('strategy', {}).get('COINS', [])
            }
    except Exception as e:
        Log(f"加载配置文件失败: {str(e)}")
        return {'exchanges': {}, 'coins': []}

@retry(retries=3, delay=1.0)
async def get_exchange_symbol_fees(exchange: ccxt.Exchange, symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取指定交易所的指定交易对费率"""
    fees = {}
    
    try:
        # 获取交易所基础费率
        trading_fees = await exchange.fetch_trading_fees()
        base_maker = trading_fees.get('maker', 0.002)
        base_taker = trading_fees.get('taker', 0.002)
        
        # 获取每个交易对的具体费率
        for symbol in symbols:
            try:
                # 构造交易对格式
                market_symbol = f"{symbol}/USDT"
                
                # 获取具体交易对的费率
                market = await exchange.load_market(market_symbol)
                
                # 使用交易对特定费率，如果没有则使用基础费率
                maker = market.get('maker', base_maker)
                taker = market.get('taker', base_taker)
                
                fees[symbol] = {
                    'maker': maker,
                    'taker': taker
                }
                
                Log(f"  {symbol}: Maker {maker*100}%, Taker {taker*100}%")
                
            except Exception as e:
                Log(f"获取{symbol}费率失败: {str(e)}")
                # 使用基础费率作为默认值
                fees[symbol] = {
                    'maker': base_maker,
                    'taker': base_taker
                }
                
    except Exception as e:
        Log(f"获取交易所费率失败: {str(e)}")
    
    return fees

@retry(retries=3, delay=1.0)
async def get_okx_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取OKX费率"""
    try:
        exchange = ccxt.okx({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'password': config.get('passphrase'),
            'enableRateLimit': True
        })
        
        Log("\nOKX费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取OKX费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_gate_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取Gate.io费率"""
    try:
        exchange = ccxt.gateio({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'enableRateLimit': True
        })
        
        Log("\nGate.io费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取Gate.io费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_mexc_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取MEXC费率"""
    try:
        exchange = ccxt.mexc({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'enableRateLimit': True
        })
        
        Log("\nMEXC费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取MEXC费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_htx_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取HTX费率"""
    try:
        exchange = ccxt.huobi({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'enableRateLimit': True
        })
        
        Log("\nHTX费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取HTX费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_kucoin_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取KuCoin费率"""
    try:
        exchange = ccxt.kucoin({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'password': config.get('passphrase'),
            'enableRateLimit': True
        })
        
        Log("\nKuCoin费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取KuCoin费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_bitget_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取Bitget费率"""
    try:
        exchange = ccxt.bitget({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'password': config.get('passphrase'),
            'enableRateLimit': True
        })
        
        Log("\nBitget费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取Bitget费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_bybit_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取Bybit费率"""
    try:
        exchange = ccxt.bybit({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        
        Log("\nBybit费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取Bybit费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_coinex_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取CoinEx费率"""
    try:
        exchange = ccxt.coinex({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'enableRateLimit': True
        })
        
        Log("\nCoinEx费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取CoinEx费率失败: {str(e)}")
        return {}

@retry(retries=3, delay=1.0)
async def get_bitmart_fees(config: Dict[str, Any], symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """获取Bitmart费率"""
    try:
        exchange = ccxt.bitmart({
            'apiKey': config.get('api_key'),
            'secret': config.get('api_secret'),
            'password': config.get('memo', ''),  # Bitmart uses 'memo' as passphrase
            'enableRateLimit': True
        })
        
        Log("\nBitmart费率:")
        fees = await get_exchange_symbol_fees(exchange, symbols)
        await exchange.close()
        return fees
        
    except Exception as e:
        Log(f"获取Bitmart费率失败: {str(e)}")
        return {}

async def get_exchange_fees() -> Dict[str, Dict[str, Dict[str, float]]]:
    """获取所有交易所的费率"""
    all_fees = {}
    config = await load_config()
    
    # 获取需要查询的币种列表
    symbols = config['coins']
    if not symbols:
        Log("警告: 未在配置文件中找到币种列表")
        return {}
    
    # 定义交易所和对应的费率获取函数
    fee_functions = {
        'okx': get_okx_fees,
        'gate': get_gate_fees,
        'mexc': get_mexc_fees,
        'htx': get_htx_fees,
        'kucoin': get_kucoin_fees,
        'bitget': get_bitget_fees,
        'bybit': get_bybit_fees,
        'coinex': get_coinex_fees,
        'bitmart': get_bitmart_fees,
    }
    
    # 并发获取所有交易所的费率
    tasks = []
    for exchange_type, exchange_config in config['exchanges'].items():
        if exchange_type.lower() in fee_functions:
            tasks.append(asyncio.create_task(
                fee_functions[exchange_type.lower()](exchange_config, symbols)
            ))
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果
    for exchange_type, result in zip(fee_functions.keys(), results):
        if isinstance(result, dict):
            all_fees[exchange_type.upper()] = result
        else:
            Log(f"获取{exchange_type.upper()}费率失败: {str(result)}")
    
    return all_fees

def save_fees(fees: Dict[str, Dict[str, Dict[str, float]]]):
    """保存费率到文件"""
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 保存到JSON文件
        json_path = os.path.join(project_root, 'config', 'exchange_fees.json')
        with open(json_path, 'w') as f:
            json.dump(fees, f, indent=4)
        Log(f"\n费率信息已保存到: {json_path}")
        
        # 生成Python代码格式
        py_path = os.path.join(project_root, 'config', 'exchange_fees.py')
        with open(py_path, 'w') as f:
            f.write("# 交易所费率配置\n\n")
            f.write("EXCHANGE_FEES = {\n")
            for exchange, symbols in fees.items():
                f.write(f"    '{exchange}': {{\n")
                for symbol, rates in symbols.items():
                    f.write(f"        '{symbol}': {{\n")
                    f.write(f"            'maker': {rates['maker']},  # {rates['maker']*100}%\n")
                    f.write(f"            'taker': {rates['taker']},  # {rates['taker']*100}%\n")
                    f.write("        },\n")
                f.write("    },\n")
            f.write("}\n")
        Log(f"费率配置已保存到: {py_path}")
        
    except Exception as e:
        Log(f"保存费率信息失败: {str(e)}")

async def main():
    """主函数"""
    try:
        Log("开始获取交易所费率信息...")
        fees = await get_exchange_fees()
        
        if fees:
            # 保存费率信息
            save_fees(fees)
            
            # 打印汇总信息
            Log("\n费率信息汇总:")
            Log("=" * 60)
            for exchange, symbols in fees.items():
                Log(f"\n{exchange}:")
                for symbol, rates in symbols.items():
                    Log(f"  {symbol}:")
                    Log(f"    Maker fee: {rates['maker']*100}%")
                    Log(f"    Taker fee: {rates['taker']*100}%")
        else:
            Log("未获取到任何费率信息")
            
    except Exception as e:
        Log(f"执行失败: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 