import sys
import os
import json
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any
from utils.utils import Log
from exchanges import ExchangeFactory

def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'config.json')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return {
                'exchanges': config.get('exchanges', {}),
                'coins': config.get('strategy', {}).get('COINS', []),
                'exchange_list': config.get('strategy', {}).get('EXCHANGES', [])
            }
    except Exception as e:
        Log(f"加载配置文件失败: {str(e)}")
        return {'exchanges': {}, 'coins': [], 'exchange_list': []}

def load_supported_exchanges() -> Dict[str, list]:
    """加载已有的支持交易所配置"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'supported_exchanges.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        Log(f"加载supported_exchanges.json失败: {str(e)}")
    return {}

async def check_trading_pair(exchange_type: str, exchange: Any, coin: str) -> bool:
    """检查交易对是否支持"""
    try:
        # 对期货交易所特殊处理
        if exchange_type == 'Futures_MEXC':
            # 如果已经是 XXX_USDT 格式，直接使用
            if '_USDT' in coin.upper():
                symbol = coin.upper()
            else:
                symbol = f"{coin}_USDT"
        else:
            symbol = coin
        Log(f"检查{exchange_type}交易对{symbol}是否支持 type{type(exchange)}")
        depth = await exchange.GetDepth(symbol)
        # 验证深度数据是否有效
        if depth and hasattr(depth, 'Asks') and hasattr(depth, 'Bids'):
            if len(depth.Asks) > 0 and len(depth.Bids) > 0:
                return True
    except Exception as e:
        error_msg = str(e).lower()
        if any(msg in error_msg for msg in ["does not have market symbol", "market not found", "symbol not found", "invalid symbol"]):
            return False
        Log(f"检查{exchange_type}交易对{coin}时出错: {str(e)}")
    return False

async def generate_supported_exchanges() -> Dict[str, list]:
    """生成支持的交易所配置"""
    supported_exchanges = {}
    
    # 加载配置
    config = load_config()
    if not config['coins'] or not config['exchange_list']:
        Log("错误: 未在配置文件中找到币种列表或交易所列表")
        return {}

    # 检查每个币种在每个交易所的支持情况
    for coin in config['coins']:
        # 获取支持该币种的交易所列表
        supported_exchanges[coin] = []
        exchanges_to_check = config['exchange_list']
        
        for exchange_type in exchanges_to_check:
            try:
                # 初始化交易所
                exchange = ExchangeFactory.create_exchange(
                    exchange_type, 
                    config['exchanges'].get(exchange_type.upper(), {})
                )
                if not exchange:
                    Log(f"初始化交易所失败: {exchange_type}")
                    continue

                # 检查交易对是否支持
                if await check_trading_pair(exchange_type, exchange, coin):
                    supported_exchanges[coin].append(exchange_type)
                    Log(f"交易所 {exchange_type} 支持 {coin}/USDT 交易对")
                else:
                    Log(f"交易所 {exchange_type} 不支持 {coin}/USDT 交易对")

                # 关闭交易所连接
                await exchange.close()
                
            except Exception as e:
                Log(f"检查交易所 {exchange_type} 的 {coin}/USDT 交易对时出错: {str(e)}")
        
        # 为每个币种添加 Futures_MEXC 对冲
        # try:
        #     # 初始化 Futures_MEXC 交易所
        #     futures_mexc = ExchangeFactory.create_exchange(
        #         'Futures_MEXC',
        #         config['exchanges'].get('Futures_MEXC', {})
        #     )
        #     Log(f"初始化 Futures_MEXC 交易所: {type(futures_mexc)}")
        #     if futures_mexc:
        #         # 检查期货交易对是否支持
        #         Log(f"检查 Futures_MEXC 的 type {type(futures_mexc)}/USDT 交易对")
        #         if await check_trading_pair('Futures_MEXC', futures_mexc, coin):
        #             supported_exchanges[coin].append('Futures_MEXC')
        #             Log(f"交易所 Futures_MEXC 支持 {coin}/USDT 交易对")
        #         else:
        #             Log(f"交易所 Futures_MEXC 不支持 {coin}/USDT 交易对")
        #         await futures_mexc.close()
        #     else:
        #         Log("初始化 Futures_MEXC 交易所失败")
        # except Exception as e:
        #     Log(f"检查 Futures_MEXC 的 {coin}/USDT 交易对时出错: {str(e)}")

    return supported_exchanges

def save_config(supported_exchanges: Dict[str, list], output_file: str = "supported_exchanges.json"):
    """保存配置到文件"""
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(project_root, "config")
        
        # 确保config目录存在
        os.makedirs(config_dir, exist_ok=True)
        
        # 保存配置文件
        output_path = os.path.join(config_dir, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(supported_exchanges, f, indent=4)
        
        Log(f"配置已保存到: {output_path}")
        
    except Exception as e:
        Log(f"保存配置文件失败: {str(e)}")

def Log_supported_exchanges(supported_exchanges: Dict[str, list]):
    """打印支持的交易所配置"""
    Log("\n支持的交易所配置:")
    Log("=" * 80)
    
    for coin, exchanges in supported_exchanges.items():
        Log(f"\n{coin}:")
        Log("-" * 40)
        for exchange in exchanges:
            Log(f"- {exchange}")

async def main():
    """主函数"""
    try:
        # 生成配置
        supported_exchanges = await generate_supported_exchanges()
        
        # 打印配置
        Log_supported_exchanges(supported_exchanges)
        
        # 保存配置
        save_config(supported_exchanges)
        
        # 输出Python格式的配置（可以直接复制到代码中使用）
        Log("\nPython格式的配置:")
        Log("=" * 80)
        Log("SUPPORTED_EXCHANGES = {")
        for coin, exchanges in supported_exchanges.items():
            Log(f"    \"{coin}\": {exchanges},")
        Log("}")
        
    except Exception as e:
        Log(f"执行失败: {str(e)}")
    finally:
        # 确保关闭所有交易所连接
        await ExchangeFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main()) 