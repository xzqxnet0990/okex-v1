class TradeStatus:
    """交易状态定义
    
    交易状态分为以下几类：
    1. SUCCESS - 交易成功完成
    2. FAILED - 交易失败
    3. ERROR - 交易过程中出现错误
    4. PENDING - 交易挂单中，等待成交
    5. EXECUTED - 交易已执行（通常用于部分成交的情况）
    6. CANCELLED - 交易已取消
    """
    
    # 交易成功
    SUCCESS = "SUCCESS"
    
    # 交易失败
    FAILED = "FAILED"
    
    # 交易出错
    ERROR = "ERROR"
    
    # 交易挂单中
    PENDING = "PENDING"
    
    # 交易已执行
    EXECUTED = "EXECUTED"
    
    # 交易已取消
    CANCELLED = "CANCELLED"
    
    @staticmethod
    def is_successful(status: str) -> bool:
        """
        判断交易状态是否为成功
        
        Args:
            status: 交易状态
            
        Returns:
            bool: 是否为成功状态
        """
        return status in [TradeStatus.SUCCESS, TradeStatus.EXECUTED]
    
    @staticmethod
    def is_failed(status: str) -> bool:
        """
        判断交易状态是否为失败
        
        Args:
            status: 交易状态
            
        Returns:
            bool: 是否为失败状态
        """
        return status in [TradeStatus.FAILED, TradeStatus.ERROR, TradeStatus.CANCELLED]
    
    @staticmethod
    def is_pending(status: str) -> bool:
        """
        判断交易状态是否为挂单中
        
        Args:
            status: 交易状态
            
        Returns:
            bool: 是否为挂单状态
        """
        return status == TradeStatus.PENDING 