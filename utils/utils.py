def _N(v: float, precision: int = 8) -> float:
    """格式化数字，保留指定位数的小数"""
    try:
        if not isinstance(v, (int, float)):
            return v
        return round(float(v), precision)
    except:
        return v 