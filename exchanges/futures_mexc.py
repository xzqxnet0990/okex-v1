import ccxt.async_support as ccxt
from typing import Dict, List, Any
from .base import BaseExchange, Account, OrderBook
from utils.logger import Log
from utils.decorators import retry
import asyncio
import time

class FuturesMEXCExchange(BaseExchange):
    """MEXC期货交易所实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "Futures_MEXC"
        self.label = "MEXC期货"
        
        # 初始化ccxt交易所实例
        self.exchange = ccxt.mexc({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'rateLimit': 100,  # 设置更保守的请求间隔(毫秒)
            'options': {
                'defaultType': 'swap',  # 设置为永续合约
                'defaultContractType': 'linear',  # 设置为U本位合约
                'adjustForTimeDifference': True,  # 自动调整服务器时间
            }
        })
        
        # 请求限制相关
        self._last_request_time = time.time()
        self._request_interval = 0.2  # 请求最小间隔(秒)
        self._request_window = 1.0  # 时间窗口(秒)
        self._max_requests_per_window = 5  # 每个时间窗口内的最大请求数
        self._request_timestamps = []  # 记录请求时间戳
        self._request_lock = asyncio.Lock()  # 请求锁

        # MEXC期货特定的费率配置
        self.fee_config.update({
            'default_fees': {
                'maker': 0.0002,  # 0.02% maker费率
                'taker': 0.0004   # 0.04% taker费率
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
                    await asyncio.sleep(wait_time)
            
            # 检查距离上次请求的时间间隔
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._request_interval:
                await asyncio.sleep(self._request_interval - time_since_last_request)
            
            # 更新请求记录
            self._last_request_time = time.time()
            self._request_timestamps.append(self._last_request_time)

    @retry(retries=3, delay=1.0)
    async def GetDepth(self, symbol: str) -> OrderBook:
        """获取市场深度"""
        try:
            # 等待请求限制
            await self._wait_for_rate_limit()
            
            # 验证交易对格式
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"无效的交易对格式: {symbol}")
                
            # 处理交易对格式
            # 如果已经是 XXX_USDT 格式，直接使用
            if '_USDT' in symbol.upper():
                contract_symbol = symbol.upper()
            else:
                # 否则添加 _USDT 后缀
                contract_symbol = f"{symbol.upper()}_USDT"
            
            # 设置获取深度的限制
            limit = 20  # 限制深度大小，避免获取过多数据
            orderbook = await self.exchange.fetch_order_book(contract_symbol, limit)
            
            # 验证orderbook数据完整性
            if not orderbook or 'asks' not in orderbook or 'bids' not in orderbook:
                raise ValueError(f"获取到的深度数据不完整: {orderbook}")
                
            # 确保asks和bids数据格式正确
            asks = []
            bids = []
            
            # 处理卖单(asks)，并添加数据验证
            for ask in orderbook['asks'][:limit]:
                if not isinstance(ask, list) or len(ask) < 2:
                    continue
                try:
                    price = float(ask[0])
                    amount = float(ask[1])
                    if price <= 0 or amount <= 0:
                        continue
                    asks.append((price, amount))
                except (ValueError, TypeError):
                    continue
                    
            # 处理买单(bids)，并添加数据验证
            for bid in orderbook['bids'][:limit]:
                if not isinstance(bid, list) or len(bid) < 2:
                    continue
                try:
                    price = float(bid[0])
                    amount = float(bid[1])
                    if price <= 0 or amount <= 0:
                        continue
                    bids.append((price, amount))
                except (ValueError, TypeError):
                    continue
            
            # 验证处理后的深度数据
            if not asks or not bids:
                raise ValueError(f"处理后的深度数据为空: asks={len(asks)}, bids={len(bids)}")
            
            return OrderBook(
                Asks=asks,
                Bids=bids
            )
            
        except ccxt.ExchangeError as e:
            if "Request frequently" in str(e):
                Log(f"MEXC请求频率限制，等待后重试: {str(e)}")
                await asyncio.sleep(1)  # 遇到频率限制时多等待一会
            raise
        except Exception as e:
            Log(f"获取{self.name}深度数据失败: {str(e)}")
            raise

    async def _execute_request(self, request_func, *args, **kwargs):
        """执行请求的通用方法"""
        await self._wait_for_rate_limit()
        return await request_func(*args, **kwargs)

    @retry(retries=3, delay=1.0)
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

    @retry(retries=3, delay=1.0)
    async def Buy(self, symbol: str, price: float, amount: float) -> Dict[str, Any]:
        """买入订单"""
        try:
            contract_symbol = f"{symbol}_USDT"
            order = await self._execute_request(
                self.exchange.create_limit_buy_order,
                contract_symbol,
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
            contract_symbol = f"{symbol}_USDT"
            order = await self._execute_request(
                self.exchange.create_limit_sell_order,
                contract_symbol,
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
            contract_symbol = f"{symbol}_USDT"
            await self.exchange.cancel_order(order_id, contract_symbol)
            return True
        except Exception as e:
            Log(f"取消订单失败 {self.name} {symbol} {order_id}: {str(e)}")
            return False
    
    @retry(retries=3, delay=1.0)
    async def GetOrder(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """获取订单信息"""
        try:
            contract_symbol = f"{symbol}_USDT"
            order = await self.exchange.fetch_order(order_id, contract_symbol)
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
            contract_symbol = f"{symbol}_USDT"
            orders = await self.exchange.fetch_open_orders(contract_symbol)
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
        获取MEXC期货交易所费率
        
        Args:
            symbol: 交易对，如果为None则返回默认费率
            is_maker: 是否是maker单，True为maker，False为taker
            
        Returns:
            float: 费率，例如0.0002表示0.02%
        """
        try:
            # 1. 如果提供了symbol，尝试从CCXT获取交易对特定费率
            if symbol:
                try:
                    # 获取所有市场信息
                    markets = await self._execute_request(self.exchange.fetch_markets)
                    # 构建交易对 (期货格式)
                    market_symbol = f"{symbol.upper()}/USDT:USDT"
                    
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
            return 0.0004  # 0.04% as fallback

    async def close(self) -> None:
        """关闭连接"""
        try:
            await self.exchange.close()
        except Exception as e:
            Log(f"关闭{self.name}连接失败: {str(e)}") 