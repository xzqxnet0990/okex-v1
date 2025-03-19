from abc import ABC, abstractmethod
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

from utils.logger import Log


@dataclass
class OrderBook:
    """深度数据结构"""
    Asks: List[Tuple[float, float]]  # price, amount
    Bids: List[Tuple[float, float]]  # price, amount

@dataclass
class Account:
    """账户信息结构"""
    Balance: float = 0.0       # USDT余额
    Stocks: float = 0.0        # 币种数量
    FrozenBalance: float = 0.0 # 冻结的USDT
    FrozenStocks: float = 0.0  # 冻结的币种数量

class BaseExchange(ABC):
    """交易所基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.passphrase = config.get('passphrase', '')
        self.maker_fee = config.get('maker_fee', 0.002)
        self.taker_fee = config.get('taker_fee', 0.002)
        self.name = "BaseExchange"
        self.label = "Base"
        self.fee_config = config.get('fees', {})
    
    @abstractmethod
    async def GetAccount(self) -> Account:
        """获取账户信息"""
        pass
    
    @abstractmethod
    async def GetDepth(self, symbol: str) -> OrderBook:
        """获取市场深度"""
        pass
    
    @abstractmethod
    async def Buy(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """买入订单"""
        pass
    
    @abstractmethod
    async def Sell(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """卖出订单"""
        pass
    
    def GetName(self) -> str:
        """获取交易所名称"""
        return self.name
    
    def GetLabel(self) -> str:
        """获取交易所标签"""
        return self.label
    
    @abstractmethod
    async def CancelOrder(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        pass
    
    @abstractmethod
    async def GetOrder(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """获取订单信息"""
        pass
    
    @abstractmethod
    async def GetOrders(self, symbol: str) -> List[Dict[str, Any]]:
        """获取所有未完成订单"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭连接"""
        pass

    async def _execute_request(self, request_func, *args, **kwargs):
        """执行请求的通用方法
        
        Args:
            request_func: 要执行的请求函数
            *args: 传递给请求函数的位置参数
            **kwargs: 传递给请求函数的关键字参数
            
        Returns:
            Any: 请求函数的返回值
        """
        try:
            return await request_func(*args, **kwargs)
        except Exception as e:
            Log(f"执行请求失败: {str(e)}")
            raise

    async def GetFee(self, symbol: str = None, is_maker: bool = False) -> float:
        """
        获取交易所费率
        
        Args:
            symbol: 交易对，如果为None则返回默认费率
            is_maker: 是否是maker单，True为maker，False为taker
            
        Returns:
            float: 费率，例如0.002表示0.2%
        """
        try:
            # 1. 检查是否有币种特定费率
            if symbol and symbol in self.fee_config.get('symbol_fees', {}):
                symbol_fees = self.fee_config['symbol_fees'][symbol]
                return symbol_fees['maker'] if is_maker else symbol_fees['taker']
            
            # 2. 检查是否有默认费率配置
            if 'default_fees' in self.fee_config:
                default_fees = self.fee_config['default_fees']
                return default_fees['maker'] if is_maker else default_fees['taker']
            
            # 3. 使用初始化时设置的费率
            return self.maker_fee if is_maker else self.taker_fee
            
        except Exception as e:
            # 如果发生任何错误，返回保守的taker费率
            return 0.002  # 0.2% as fallback 