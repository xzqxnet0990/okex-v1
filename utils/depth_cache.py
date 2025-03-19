import time
from typing import Optional, Dict, Any


class DepthCache:
    """深度数据缓存管理器"""

    def __init__(self, cache_time: float = 100.0):
        """
        初始化缓存管理器

        Args:
            cache_time: 缓存有效时间（秒）
        """
        self.cache = {}  # {(exchange, coin): (timestamp, depth_data)}
        self.cache_time = cache_time

    def get(self, exchange: str, coin: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的深度数据

        Args:
            exchange: 交易所名称
            coin: 币种

        Returns:
            Optional[Dict[str, Any]]: 如果缓存有效则返回深度数据，否则返回None
        """
        key = (exchange, coin)
        if key not in self.cache:
            return None

        timestamp, data = self.cache[key]
        if time.time() - timestamp > self.cache_time:
            # 缓存过期
            del self.cache[key]
            return None

        return data

    def set(self, exchange: str, coin: str, data: Dict[str, Any]):
        """
        设置深度数据缓存

        Args:
            exchange: 交易所名称
            coin: 币种
            data: 深度数据
        """
        self.cache[(exchange, coin)] = (time.time(), data)

    def clear(self):
        """清除所有缓存"""
        self.cache.clear()
        
    def get_all_valid_data(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        获取所有有效的缓存数据
        
        Returns:
            Dict[str, Dict[str, Dict[str, Any]]]: 格式为 {coin: {exchange: depth_data}}
        """
        current_time = time.time()
        result = {}
        
        # 遍历所有缓存数据
        for (exchange, coin), (timestamp, data) in list(self.cache.items()):
            # 检查缓存是否有效
            if current_time - timestamp <= self.cache_time:
                # 确保数据有效
                if data and 'asks' in data and 'bids' in data and data['asks'] and data['bids']:
                    # 初始化币种字典
                    if coin not in result:
                        result[coin] = {}
                    # 添加交易所数据
                    result[coin][exchange] = data
            else:
                # 移除过期缓存
                del self.cache[(exchange, coin)]
                
        return result
        
    def get_coin_prices(self) -> Dict[str, float]:
        """
        从缓存中获取所有币种的中间价格
        
        Returns:
            Dict[str, float]: 格式为 {coin: price}
        """
        all_data = self.get_all_valid_data()
        prices = {}
        
        for coin, exchanges_data in all_data.items():
            coin_prices = []
            
            for exchange, depth_data in exchanges_data.items():
                if depth_data and depth_data.get('asks') and depth_data.get('bids'):
                    # 计算中间价
                    mid_price = (depth_data['asks'][0][0] + depth_data['bids'][0][0]) / 2
                    coin_prices.append(mid_price)
            
            if coin_prices:
                # 使用中位数作为最终价格
                coin_prices.sort()
                if len(coin_prices) % 2 == 0:
                    median_price = (coin_prices[len(coin_prices)//2 - 1] + coin_prices[len(coin_prices)//2]) / 2
                else:
                    median_price = coin_prices[len(coin_prices)//2]
                    
                prices[coin] = median_price
                
        return prices