from typing import Dict, Any, Optional

from utils.logger import Log
from .base import BaseExchange
from .okx import OKXExchange
from .mexc import MEXCExchange
from .htx import HTXExchange
from .coinex import CoinExExchange
from .kucoin import KuCoinExchange
from .gateio import GateIOExchange
from .bitget import BitgetExchange
from .binance import BinanceExchange
from .futures_mexc import FuturesMEXCExchange

class ExchangeFactory:
    """交易所工厂类，用于创建和管理交易所实例"""
    
    _exchanges: Dict[str, BaseExchange] = {}
    
    @classmethod
    def create_exchange(cls, exchange_type: str, config: Dict[str, Any]) -> Optional[BaseExchange]:
        """
        创建交易所实例
        
        Args:
            exchange_type: 交易所类型
            config: 交易所配置
            
        Returns:
            交易所实例或None（如果创建失败）
        """
        try:
            if exchange_type in cls._exchanges:
                return cls._exchanges[exchange_type]
            
            exchange: Optional[BaseExchange] = None
            
            if exchange_type.lower() == "okx":
                exchange = OKXExchange(config)
            elif exchange_type.lower() == "mexc":
                exchange = MEXCExchange(config)
            elif exchange_type.lower() == "htx":
                exchange = HTXExchange(config)
            elif exchange_type.lower() == "coinex":
                exchange = CoinExExchange(config)
            elif exchange_type.lower() == "kucoin":
                exchange = KuCoinExchange(config)
            elif exchange_type.lower() in ["gate", "gate.io", "gateio"]:
                exchange = GateIOExchange(config)
            elif exchange_type.lower() in ["bybit", "bybit.com"]:
                exchange = BitgetExchange(config)
            elif exchange_type.lower() == "bitget":
                exchange = BitgetExchange(config)
            elif exchange_type.lower() == "binance":
                exchange = BinanceExchange(config)
            elif exchange_type.lower() == "futures_mexc":
                exchange = FuturesMEXCExchange(config)
            else:
                Log(f"不支持的交易所类型: {exchange_type}")
                return None
                
            cls._exchanges[exchange_type] = exchange
            return exchange
            
        except Exception as e:
            Log(f"创建交易所实例失败 {exchange_type}: {str(e)}")
            return None
    
    @classmethod
    def get_exchange(cls, exchange_type: str) -> Optional[BaseExchange]:
        """
        获取已创建的交易所实例
        
        Args:
            exchange_type: 交易所类型
            
        Returns:
            交易所实例或None（如果不存在）
        """
        return cls._exchanges.get(exchange_type)
    
    @classmethod
    async def close_all(cls) -> None:
        """关闭所有交易所连接"""
        for exchange in cls._exchanges.values():
            try:
                await exchange.close()
            except Exception as e:
                Log(f"关闭交易所连接失败 {exchange.name}: {str(e)}")
        cls._exchanges.clear() 