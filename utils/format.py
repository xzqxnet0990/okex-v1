"""
格式化工具函数
"""

__all__ = ['_N']

def _N(value: float, precision: int = 4) -> str:
    """
    格式化数字为指定精度的字符串

    Args:
        value: 要格式化的数字
        precision: 小数点后的位数

    Returns:
        格式化后的字符串
    """
    try:
        if isinstance(value, str):
            value = float(value)
        if value == float('inf') or value == float('-inf'):
            return str(value)
        return f"{value:.{precision}f}"
    except (ValueError, TypeError):
        return str(value) 