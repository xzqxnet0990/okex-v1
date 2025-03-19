from typing import Dict, Any, List

from utils.logger import Log, _N
from utils.simulated_account import SimulatedAccount


def _validate_params(coin: str, depths: Dict[str, Dict[str, Any]], account: SimulatedAccount,
                     spot_exchanges: List[str]) -> bool:
    """验证参数是否有效"""
    if not coin or not depths or not account or not spot_exchanges:
        Log("参数为空")
        return False
    if len(spot_exchanges) < 2:
        Log("交易所数量不足")
        return False

    coin = coin.upper()
    Log(f"验证参数 - 币种: {coin}")
    Log(f"深度数据键: {list(depths.keys())}")

    # 注意：depths 已经是当前币种的深度数据，不需要检查 coin 是否在 depths 中

    Log(f"深度数据中的交易所: {list(depths.keys())}")

    for ex in spot_exchanges:
        if ex not in depths:
            Log(f"深度数据中没有{ex}的信息")
            return False
        if not depths[ex].get('asks') or not depths[ex].get('bids'):
            Log(f"{ex}的深度数据不完整")
            return False
        if not depths[ex]['asks'] or not depths[ex]['bids']:
            Log(f"{ex}的深度数据为空")
            return False
    return True


def calculate_dynamic_min_amount(coin: str, depths: Dict[str, Dict[str, Any]], config: Dict[str, Any], account=None) -> float:
    """
    根据配置中的 SAFE_AMOUNT、币价、深度数据和账户余额动态计算最小交易数量
    
    Args:
        coin: 币种
        depths: 深度数据
        config: 配置信息
        account: 账户对象，用于检查余额
        
    Returns:
        float: 动态计算的最小交易数量
    """
    # 获取配置中的安全交易金额（以USDT计）
    safe_amount = config.get('strategy', {}).get('SAFE_AMOUNT', 10.0)  # 默认10 USDT
    
    # 获取当前币价（使用第一个可用交易所的卖一价格）
    coin_price = 0.0
    for exchange, depth in depths.items():
        if depth and depth.get('asks') and len(depth['asks']) > 0:
            # 卖一价格
            coin_price = depth['asks'][0][0]
            break
    
    if coin_price <= 0:
        Log(f"无法获取{coin}的价格，使用默认最小交易数量")
        return config.get('strategy', {}).get('MIN_AMOUNT', 0.001)
    
    # 计算最小交易数量 = 安全交易金额 / 币价
    min_amount = safe_amount / coin_price
    
    # 获取配置中的最小交易数量作为下限
    min_amount_floor = config.get('strategy', {}).get('MIN_AMOUNT', 0.001)
    
    # 确保计算的最小交易数量不小于配置的最小值
    min_amount = max(min_amount, min_amount_floor)
    
    # 考虑深度数据中的可用交易量
    # 计算每个交易所前3档深度的平均可用量
    depth_based_amounts = []
    for exchange, depth in depths.items():
        if not depth or not depth.get('asks') or not depth.get('bids'):
            continue
            
        # 计算卖单(asks)前3档的总量
        ask_volume = 0.0
        for i, (price, volume) in enumerate(depth['asks']):
            if i >= 3:  # 只考虑前3档
                break
            ask_volume += volume
            
        # 计算买单(bids)前3档的总量
        bid_volume = 0.0
        for i, (price, volume) in enumerate(depth['bids']):
            if i >= 3:  # 只考虑前3档
                break
            bid_volume += volume
            
        # 取买卖单中较小的量作为该交易所的深度限制
        exchange_depth_limit = min(ask_volume, bid_volume)
        
        # 考虑市场影响，使用深度限制的一定比例（例如20%）
        market_impact_factor = config.get('strategy', {}).get('MARKET_IMPACT_FACTOR', 0.2)
        depth_based_amount = exchange_depth_limit * market_impact_factor
        
        if depth_based_amount > 0:
            depth_based_amounts.append(depth_based_amount)
            Log(f"交易所: {exchange}, 卖单量: {_N(ask_volume, 6)}, 买单量: {_N(bid_volume, 6)}, 深度限制: {_N(exchange_depth_limit, 6)}, 基于深度的交易量: {_N(depth_based_amount, 6)}")
    
    # 如果有基于深度的交易量限制，取其最小值
    if depth_based_amounts:
        depth_min_amount = min(depth_based_amounts)
        Log(f"基于深度的最小交易数量: {_N(depth_min_amount, 6)} (原计算值: {_N(min_amount, 6)})")
        
        # 如果基于深度的最小交易量小于之前计算的最小交易量，则使用基于深度的值
        if depth_min_amount < min_amount:
            min_amount = max(depth_min_amount, min_amount_floor)  # 确保不小于配置的最小值
    
    # 如果提供了账户对象，检查各交易所的余额
    if account:
        # 检查各交易所的余额，找出最小可用余额
        min_available_balance = float('inf')
        for exchange in depths.keys():
            # 检查币种余额
            coin_balance = account.get_balance(coin.lower(), exchange)
            # 检查USDT余额（用于买入）
            usdt_balance = account.get_balance('usdt', exchange)
            # 可买入的币数量
            can_buy_amount = usdt_balance / coin_price if coin_price > 0 else 0
            
            # 取币种余额和可买入数量的较小值作为该交易所的可用余额
            available_balance = min(coin_balance, can_buy_amount)
            
            # 更新最小可用余额
            if available_balance < min_available_balance:
                min_available_balance = available_balance
            
            Log(f"交易所: {exchange}, {coin}余额: {_N(coin_balance, 6)}, USDT余额: {_N(usdt_balance, 2)}, 可用余额: {_N(available_balance, 6)}")
        
        # 如果最小可用余额小于计算的最小交易数量，则使用最小可用余额的一定比例
        if min_available_balance < min_amount and min_available_balance > 0:
            # 使用最小可用余额的80%作为最小交易数量
            balance_based_min_amount = min_available_balance * 0.8
            Log(f"基于余额的最小交易数量: {_N(balance_based_min_amount, 6)} (原计算值: {_N(min_amount, 6)})")
            
            # 确保不小于配置的最小值
            min_amount = max(balance_based_min_amount, min_amount_floor)
    
    Log(f"币种: {coin}, 币价: {_N(coin_price, 6)}, 安全金额: {safe_amount} USDT, 最终计算的最小交易数量: {_N(min_amount, 6)}")
    
    return min_amount