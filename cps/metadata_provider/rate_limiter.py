"""
T010: API 限流器
================

功能：控制外部 API 调用频率
"""

import time
import threading
from collections import deque
from typing import Optional


class RateLimiter:
    """
    速率限制器
    
    使用滑动窗口算法限制 API 调用频率
    """
    
    def __init__(self, max_calls: float, time_window: float):
        """
        初始化限流器
        
        Args:
            max_calls: 时间窗口内最大调用次数
            time_window: 时间窗口（秒）
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self._calls = deque()
        self._lock = threading.Lock()
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        获取调用许可
        
        Args:
            blocking: 是否阻塞等待
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否获得许可
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                now = time.time()
                
                # 清理过期的调用记录
                while self._calls and self._calls[0] < now - self.time_window:
                    self._calls.popleft()
                
                # 检查是否还有额度
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return True
                
                if not blocking:
                    return False
                
                # 计算等待时间
                if self._calls:
                    oldest = self._calls[0]
                    wait_time = self.time_window - (now - oldest) + 0.01
                else:
                    wait_time = 0.01
                
                # 检查超时
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return False
                    wait_time = min(wait_time, timeout - elapsed)
            
            # 等待
            if wait_time > 0:
                time.sleep(wait_time)
    
    def reset(self):
        """重置限流器"""
        with self._lock:
            self._calls.clear()
    
    @property
    def remaining(self) -> int:
        """剩余调用次数"""
        with self._lock:
            now = time.time()
            while self._calls and self._calls[0] < now - self.time_window:
                self._calls.popleft()
            return int(self.max_calls - len(self._calls))


class MultiRateLimiter:
    """
    多提供者限流器
    
    为不同的 API 提供者分别限制速率
    """
    
    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()
    
    def add_provider(self, name: str, max_calls: float, time_window: float):
        """添加提供者限流配置"""
        with self._lock:
            self._limiters[name] = RateLimiter(max_calls, time_window)
    
    def acquire(self, provider_name: str, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """获取调用许可"""
        with self._lock:
            limiter = self._limiters.get(provider_name)
        
        if limiter:
            return limiter.acquire(blocking, timeout)
        
        # 没有限流配置的提供者直接放行
        return True
    
    def get_limiter(self, name: str) -> Optional[RateLimiter]:
        """获取指定提供者的限流器"""
        with self._lock:
            return self._limiters.get(name)


# 全局限流器
_rate_limiter: Optional[MultiRateLimiter] = None


def get_rate_limiter() -> MultiRateLimiter:
    """获取全局限流器"""
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = MultiRateLimiter()
        
        # 配置各提供者限流
        # OpenLibrary: 5次/秒
        _rate_limiter.add_provider('OpenLibrary', 5, 1.0)
        
        # Google Books: 5次/秒（未认证）
        _rate_limiter.add_provider('GoogleBooks', 5, 1.0)
    
    return _rate_limiter