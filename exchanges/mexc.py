import ccxt.async_support as ccxt
from typing import Dict, List, Any
from .base import BaseExchange, Account, OrderBook
from utils.logger import Log
from utils.decorators import retry
import asyncio
import time

class MEXCExchange(BaseExchange):
    """MEXC交易所实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "MEXC"
        self.label = "MEXC"
        
        # 初始化ccxt交易所实例
        self.exchange = ccxt.mexc({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'rateLimit': 100,  # 降低到100ms
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,  # 自动调整服务器时间
            }
        })
        
        # 请求限制相关
        self._last_request_time = time.time()
        self._request_interval = 0.3  # 请求最小间隔(秒)
        self._request_window = 1.0  # 时间窗口(秒)
        self._max_requests_per_window = 5  # 每个时间窗口内的最大请求数
        self._request_timestamps = []  # 记录请求时间戳
        self._request_lock = asyncio.Lock()  # 请求锁
        
        # MEXC特定的费率配置
        self.fee_config.update({
            'default_fees': {
                'maker': 0.002,  # 0.2% maker费率
                'taker': 0.002   # 0.2% taker费率
            }
        })

    async def _wait_for_rate_limit(self):
        """等待请求限制"""
        async with self._request_lock:
            current_time = time.time()
            
            # 清理过期的请求记录
            self._request_timestamps = [ts for ts in self._request_timestamps 
                                     if current_time - ts <= self._request_window]
            
            # 检查是否超过窗口请求限制
            if len(self._request_timestamps) >= self._max_requests_per_window:
                # 计算需要等待的时间
                wait_time = self._request_timestamps[0] + self._request_window - current_time
                if wait_time > 0:
                    await asyncio.sleep(wait_time + 0.1)  # 额外等待0.1秒以确保安全
            
            # 检查距离上次请求的时间间隔
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._request_interval:
                await asyncio.sleep(self._request_interval - time_since_last_request + 0.1)
            
            # 更新请求记录
            self._last_request_time = time.time()
            self._request_timestamps.append(self._last_request_time)

    async def _execute_request(self, request_func, *args, **kwargs):
        """执行请求的通用方法"""
        await self._wait_for_rate_limit()
        try:
            return await request_func(*args, **kwargs)
        except ccxt.ExchangeError as e:
            if "Request frequently" in str(e):
                Log(f"MEXC请求频率限制，等待后重试: {str(e)}")
                await asyncio.sleep(2)  # 遇到频率限制时多等待2秒
                raise
            raise
    
    @retry(retries=2, delay=1.0)  # 减少重试次数和延迟
    async def GetAccount(self) -> Account:
        """获取账户信息"""
        try:
            balance = await self._execute_request(self.exchange.fetch_balance)
            return Account(
                Balance=float(balance.get('USDT', {}).get('free', 0)),
                Stocks=float(balance.get('BTC', {}).get('free', 0)),
                FrozenBalance=float(balance.get('USDT', {}).get('used', 0)),
                FrozenStocks=float(balance.get('BTC', {}).get('used', 0))
            )
        except Exception as e:
            Log(f"获取{self.name}账户信息失败: {str(e)}")
            raise
    
    @retry(retries=2, delay=1.0)  # 减少重试次数和延迟
    async def GetDepth(self, symbol: str) -> OrderBook:
        """获取市场深度"""
        try:
            orderbook = await self._execute_request(
                self.exchange.fetch_order_book,
                f"{symbol}/USDT",
                20  # 限制深度大小
            )
            return OrderBook(
                Asks=[(float(price), float(amount)) for price, amount in orderbook['asks']],
                Bids=[(float(price), float(amount)) for price, amount in orderbook['bids']]
            )
        except Exception as e:
            Log(f"获取{self.name}深度数据失败: {str(e)}")
            raise
    
    @retry(retries=2, delay=1.0)  # 减少重试次数和延迟
    async def Buy(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """买入订单"""
        try:
            order = await self._execute_request(
                self.exchange.create_limit_buy_order,
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
    
    @retry(retries=2, delay=1.0)  # 减少重试次数和延迟
    async def Sell(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """卖出订单"""
        try:
            order = await self._execute_request(
                self.exchange.create_limit_sell_order,
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
    
    @retry(retries=2, delay=1.0)
    async def CancelOrder(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        try:
            await self._execute_request(self.exchange.cancel_order, order_id, f"{symbol}/USDT")
            return True
        except Exception as e:
            Log(f"取消订单失败 {self.name} {symbol} {order_id}: {str(e)}")
            return False
    
    @retry(retries=2, delay=1.0)
    async def GetOrder(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """获取订单信息"""
        try:
            order = await self._execute_request(self.exchange.fetch_order, order_id, f"{symbol}/USDT")
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
    
    @retry(retries=2, delay=1.0)
    async def GetOrders(self, symbol: str) -> List[Dict[str, Any]]:
        """获取所有未完成订单"""
        try:
            orders = await self._execute_request(self.exchange.fetch_open_orders, f"{symbol}/USDT")
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
        获取MEXC交易所费率
        
        Args:
            symbol: 交易对，如果为None则返回默认费率
            is_maker: 是否是maker单，True为maker，False为taker
            
        Returns:
            float: 费率，例如0.002表示0.2%
        """
        try:
            # 1. 如果提供了symbol，尝试从CCXT获取交易对特定费率
            if symbol:
                try:
                    # 获取所有市场信息
                    markets = await self._execute_request(self.exchange.fetch_markets)
                    # 构建交易对
                    market_symbol = f"{symbol.upper()}/USDT"
                    
                    # 查找匹配的市场信息
                    market_info = None
                    for m in markets:
                        if m['symbol'] == market_symbol:
                            market_info = m
                            break
                    
                    if market_info and 'maker' in market_info and 'taker' in market_info:
                        return market_info['maker'] if is_maker else market_info['taker']
                except Exception as e:
                    Log(f"获取{self.name} {symbol}市场信息失败: {str(e)}")
            
            # 2. 如果无法获取特定费率，使用基类的费率查询逻辑
            return await super().GetFee(symbol, is_maker)
            
        except Exception as e:
            Log(f"获取{self.name}费率失败: {str(e)}")
            # 如果发生任何错误，返回保守的taker费率
            return 0.002  # 0.2% as fallback
    
    async def close(self) -> None:
        """关闭连接"""
        try:
            await self.exchange.close()
        except Exception as e:
            Log(f"关闭{self.name}连接失败: {str(e)}") 