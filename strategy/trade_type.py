class TradeType:
    """交易类型定义

    交易类型分为以下几大类：
    1. 直接套利 (ARBITRAGE)
       - 仅限现货市场内部进行
       - 利用不同现货交易所间的价格差进行套利

    2. 对冲操作 (HEDGE)
       - 仅限现货市场内部进行
       - HEDGE_SELL: 现货卖出操作，用于平衡仓位
       - HEDGE_BUY: 现货买入操作，用于平衡仓位

    3. 均衡操作 (BALANCE)
       - 仅限现货账户之间
       - 用于调整多个现货账户间的资产分布

    4. 挂单套利 (PENDING)
       - 仅限现货账户之间
       - PENDING_TRADE: 先挂买单后挂卖单的套利
       - REVERSE_PENDING: 先挂卖单后挂买单的套利
    """

    # 1. 直接套利 - 仅限现货账户
    ARBITRAGE = "套利(原)"

    # 2. 对冲操作 - 现货账户间对冲
    HEDGE_SELL = "对冲卖出(吃)"
    HEDGE_BUY = "对冲买入(吃)"

    # 3. 均衡操作 - 现货账户间均衡
    BALANCE_OPERATION = "均衡"

    # 4. 挂单套利 - 现货账户间挂单操作
    PENDING_TRADE = "正向挂单"
    REVERSE_PENDING = "反向挂单"

    NO_TRADE = "no_trade"

    @staticmethod
    def is_spot_only(trade_type: str) -> bool:
        """
        判断交易类型是否仅限现货账户
        
        Args:
            trade_type: 交易类型
            
        Returns:
            bool: 是否仅限现货账户
        """
        spot_only_types = [
            TradeType.ARBITRAGE,
            TradeType.HEDGE_BUY,
            TradeType.HEDGE_SELL,
            TradeType.BALANCE_OPERATION,
            TradeType.PENDING_TRADE,
            TradeType.REVERSE_PENDING
        ]
        return trade_type in spot_only_types

    @staticmethod
    def requires_futures(trade_type: str) -> bool:
        """判断交易类型是否需要期货账户"""
        return False  # 当前所有交易类型都不需要期货账户

    @staticmethod
    def is_pending_order(trade_type: str) -> bool:
        """判断交易类型是否为挂单交易"""
        pending_types = [
            TradeType.PENDING_TRADE,
            TradeType.REVERSE_PENDING
        ]
        return trade_type in pending_types 