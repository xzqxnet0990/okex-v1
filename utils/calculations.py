from typing import Dict, Any
from utils.logger import Log

def _N(value: float, decimals: int = 6) -> float:
    """
    Format a number to a specified number of decimal places.
    
    Args:
        value: The number to format
        decimals: Number of decimal places to keep (default: 2)
        
    Returns:
        float: The formatted number with specified decimal places
    """
    if not isinstance(value, (int, float)):
        return value
    
    multiplier = 10 ** decimals
    return float(int(value * multiplier)) / multiplier

def calculate_real_price(price: float, fee_rate: float, is_ask: bool) -> float:
    """
    计算考虑手续费后的实际价格
    
    Args:
        price: 原始价格
        fee_rate: 手续费率
        is_ask: 是否是卖单
        
    Returns:
        float: 考虑手续费后的实际价格
    """
    return price * (1 + fee_rate) if is_ask else price * (1 - fee_rate)

def calculate_trade_amount(buy_price: float, sell_price: float, balance: float, config: Dict[str, Any]) -> float:
    """
    计算交易数量

    Args:
        buy_price: 买入价格
        sell_price: 卖出价格
        balance: 账户余额
        config: 配置信息

    Returns:
        交易数量
    """
    try:
        # 价格有效性检查
        if buy_price <= 0 or sell_price <= 0:
            Log(f"无效价格: 买入价={buy_price}, 卖出价={sell_price}")
            return 0

        # 获取配置参数
        min_amount = config.get('strategy', {}).get('MIN_AMOUNT', 0.001)  # 最小交易量
        safe_price = config.get('strategy', {}).get('SAFE_PRICE', 100)  # 单笔买入限额
        max_trade_price = config.get('strategy', {}).get('MAX_TRADE_PRICE', 500)  # 单笔交易限额
        max_amount = config.get('strategy', {}).get('MAX_AMOUNT', 1000000)  # 最大交易量

        # 根据买入价格和安全限额计算最大可买入量
        safe_price_amount = safe_price / buy_price if buy_price > 0 else 0
        max_trade_amount = max_trade_price / buy_price if buy_price > 0 else 0

        # 根据账户余额计算可买入量
        balance_amount = balance / buy_price if buy_price > 0 else 0

        # 计算目标交易量
        target_amount = min(
            balance_amount,  # 不超过账户余额
            safe_price_amount,  # 不超过单笔买入限额
            max_trade_amount,  # 不超过单笔交易限额
            max_amount  # 不超过最大交易量
        )

        # 确保不小于最小交易量
        if target_amount < min_amount:
            return 0

        return _N(target_amount)

    except Exception as e:
        Log(f"计算交易数量失败: {str(e)}")
        return 0 