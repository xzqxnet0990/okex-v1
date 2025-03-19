import asyncio
import functools
import time
from utils.logger import Log

def retry(retries: int = 3, delay: float = 1.0):
    """
    重试装饰器，用于处理可能失败的操作
    
    Args:
        retries: 最大重试次数
        delay: 重试间隔时间（秒）
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < retries - 1:  # 如果不是最后一次尝试
                        Log(f"操作失败 ({func.__name__}): {str(e)}")
                        Log(f"等待 {delay} 秒后重试 ({attempt + 1}/{retries})")
                        await asyncio.sleep(delay)
                    else:
                        Log(f"操作失败 ({func.__name__}): {str(e)}")
                        Log(f"已达到最大重试次数 ({retries})")
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < retries - 1:  # 如果不是最后一次尝试
                        Log(f"操作失败 ({func.__name__}): {str(e)}")
                        Log(f"等待 {delay} 秒后重试 ({attempt + 1}/{retries})")
                        time.sleep(delay)
                    else:
                        Log(f"操作失败 ({func.__name__}): {str(e)}")
                        Log(f"已达到最大重试次数 ({retries})")
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator 