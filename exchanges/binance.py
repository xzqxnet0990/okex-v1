import ccxt.async_support as ccxt
from typing import Dict, List, Any
from .base import BaseExchange, Account, OrderBook
from utils.logger import Log
from utils.decorators import retry

class BinanceExchange(BaseExchange):
    """币安交易所实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "Binance"
        self.label = "币安"
        
        # 初始化ccxt交易所实例
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            }
        })
        
        # Binance特定的费率配置
        self.fee_config.update({
            'default_fees': {
                'maker': 0.001,  # 0.1% maker费率
                'taker': 0.001   # 0.1% taker费率
            }
        })
    
    @retry(retries=3, delay=1.0)
    async def GetAccount(self) -> Account:
        """获取账户信息"""
        try:
            balance = await self.exchange.fetch_balance()
            return Account(
                Balance=float(balance.get('USDT', {}).get('free', 0)),
                Stocks=float(balance.get('BTC', {}).get('free', 0)),
                FrozenBalance=float(balance.get('USDT', {}).get('used', 0)),
                FrozenStocks=float(balance.get('BTC', {}).get('used', 0))
            )
        except Exception as e:
            Log(f"获取{self.name}账户信息失败: {str(e)}")
            raise
    
    @retry(retries=3, delay=1.0)
    async def GetDepth(self, symbol: str) -> OrderBook:
        """获取市场深度"""
        try:
            orderbook = await self.exchange.fetch_order_book(f"{symbol}/USDT")
            return OrderBook(
                Asks=[(float(price), float(amount)) for price, amount in orderbook['asks']],
                Bids=[(float(price), float(amount)) for price, amount in orderbook['bids']]
            )
        except Exception as e:
            Log(f"获取{self.name}深度数据失败: {str(e)}")
            raise
    
    @retry(retries=3, delay=1.0)
    async def Buy(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """买入订单"""
        try:
            order = await self.exchange.create_limit_buy_order(
                f"{symbol}/USDT",
                amount,
                price
            )
            return {
                'id': order['id'],
                'price': float(order['price']),
                'amount': float(order['amount']),
                'filled': float(order['filled']),
                'status': order['status']
            }
        except Exception as e:
            Log(f"下买单失败 {self.name} {symbol} {price} {amount}: {str(e)}")
            raise
    
    @retry(retries=3, delay=1.0)
    async def Sell(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """卖出订单"""
        try:
            order = await self.exchange.create_limit_sell_order(
                f"{symbol}/USDT",
                amount,
                price
            )
            return {
                'id': order['id'],
                'price': float(order['price']),
                'amount': float(order['amount']),
                'filled': float(order['filled']),
                'status': order['status']
            }
        except Exception as e:
            Log(f"下卖单失败 {self.name} {symbol} {price} {amount}: {str(e)}")
            raise
    
    @retry(retries=3, delay=1.0)
    async def CancelOrder(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        try:
            await self.exchange.cancel_order(order_id, f"{symbol}/USDT")
            return True
        except Exception as e:
            Log(f"取消订单失败 {self.name} {symbol} {order_id}: {str(e)}")
            return False
    
    @retry(retries=3, delay=1.0)
    async def GetOrder(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """获取订单信息"""
        try:
            order = await self.exchange.fetch_order(order_id, f"{symbol}/USDT")
            return {
                'id': order['id'],
                'price': float(order['price']),
                'amount': float(order['amount']),
                'filled': float(order['filled']),
                'status': order['status']
            }
        except Exception as e:
            Log(f"获取订单信息失败 {self.name} {symbol} {order_id}: {str(e)}")
            raise
    
    @retry(retries=3, delay=1.0)
    async def GetOrders(self, symbol: str) -> List[Dict[str, Any]]:
        """获取所有未完成订单"""
        try:
            orders = await self.exchange.fetch_open_orders(f"{symbol}/USDT")
            return [{
                'id': order['id'],
                'price': float(order['price']),
                'amount': float(order['amount']),
                'filled': float(order['filled']),
                'status': order['status']
            } for order in orders]
        except Exception as e:
            Log(f"获取未完成订单失败 {self.name} {symbol}: {str(e)}")
            raise
    
    @retry(retries=2, delay=1.0)
    async def GetFee(self, symbol: str = None, is_maker: bool = False) -> float:
        """
        获取币安交易所费率
        
        Args:
            symbol: 交易对，如果为None则返回默认费率
            is_maker: 是否是maker单，True为maker，False为taker
            
        Returns:
            float: 费率，例如0.001表示0.1%
        """
        try:
            # 1. 如果提供了symbol，尝试从CCXT获取交易对特定费率
            if symbol:
                try:
                    # 获取交易对的市场信息
                    market = await self._execute_request(
                        self.exchange.fetch_markets,
                        f"{symbol}/USDT"
                    )
                    if market and 'maker' in market and 'taker' in market:
                        return market['maker'] if is_maker else market['taker']
                except Exception as e:
                    Log(f"获取{self.name} {symbol}费率失败: {str(e)}")
            
            # 2. 如果无法获取特定费率，使用基类的费率查询逻辑
            return await super().GetFee(symbol, is_maker)
            
        except Exception as e:
            Log(f"获取{self.name}费率失败: {str(e)}")
            # 如果发生任何错误，返回保守的taker费率
            return 0.001  # 0.1% as fallback
    
    async def close(self) -> None:
        """关闭连接"""
        try:
            await self.exchange.close()
        except Exception as e:
            Log(f"关闭{self.name}连接失败: {str(e)}") 