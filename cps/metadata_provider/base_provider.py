"""
T010: 外部元数据提供者基类
==========================

功能：外部元数据提供者的抽象基类和注册表
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


logger = logging.getLogger(__name__)


@dataclass
class ExternalMetadata:
    """外部元数据"""
    title: str = ""
    author: str = ""
    description: str = ""
    publisher: str = ""
    pubdate: str = ""
    isbn: str = ""
    language: str = ""
    series: str = ""
    series_index: str = "1.0"
    tags: List[str] = None
    cover_url: str = ""
    
    # 来源信息
    source: str = ""
    source_id: str = ""
    confidence: float = 0.0  # 匹配置信度 0-1
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'title': self.title,
            'author': self.author,
            'description': self.description,
            'publisher': self.publisher,
            'pubdate': self.pubdate,
            'isbn': self.isbn,
            'language': self.language,
            'series': self.series,
            'series_index': self.series_index,
            'tags': self.tags,
            'cover_url': self.cover_url,
            'source': self.source,
            'source_id': self.source_id,
            'confidence': self.confidence
        }


class BaseMetadataProvider(ABC):
    """
    元数据提供者基类
    
    所有外部元数据提供者都应继承此类
    """
    
    # 提供者名称（子类需要覆盖）
    PROVIDER_NAME: str = ""
    
    # 支持的 ISBN 国家/地区（可选）
    SUPPORTED_COUNTRIES: List[str] = []
    
    def __init__(self, rate_limit: float = 5.0):
        """
        初始化提供者
        
        Args:
            rate_limit: 每秒请求数限制
        """
        self.rate_limit = rate_limit
        self.logger = logging.getLogger(f"{__name__}.{self.PROVIDER_NAME}")
        self._last_request_time = 0
    
    @abstractmethod
    def search(self, query: str, author: str = "", isbn: str = "") -> List[ExternalMetadata]:
        """
        搜索元数据
        
        Args:
            query: 搜索关键词（书名）
            author: 作者名（可选）
            isbn: ISBN（可选）
            
        Returns:
            list: 匹配的元数据列表
        """
        pass
    
    @abstractmethod
    def get_by_isbn(self, isbn: str) -> Optional[ExternalMetadata]:
        """
        根据 ISBN 获取元数据
        
        Args:
            isbn: ISBN
            
        Returns:
            ExternalMetadata: 元数据，或 None
        """
        pass
    
    def _rate_limit_wait(self):
        """速率限制等待"""
        import time
        import threading
        
        min_interval = 1.0 / self.rate_limit
        
        with threading.Lock():
            elapsed = time.time() - self._last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()
    
    def _http_get(self, url: str, params: dict = None, headers: dict = None) -> dict:
        """
        发送 HTTP GET 请求
        
        Args:
            url: 请求 URL
            params: 查询参数
            headers: 请求头
            
        Returns:
            dict: JSON 响应
        """
        import requests
        import time
        
        self._rate_limit_wait()
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"HTTP 请求失败: {url}, 错误: {e}")
            return {}


class MetadataProviderRegistry:
    """
    元数据提供者注册表
    """
    
    def __init__(self):
        self._providers: List[BaseMetadataProvider] = []
    
    def register(self, provider: BaseMetadataProvider):
        if provider not in self._providers:
            self._providers.append(provider)
            logger.info(f"注册元数据提供者: {provider.PROVIDER_NAME}")
    
    def unregister(self, provider: BaseMetadataProvider):
        if provider in self._providers:
            self._providers.remove(provider)
    
    def get_provider(self, name: str) -> Optional[BaseMetadataProvider]:
        for provider in self._providers:
            if provider.PROVIDER_NAME == name:
                return provider
        return None
    
    def search_all(self, query: str, author: str = "", isbn: str = "") -> List[ExternalMetadata]:
        """在所有提供者中搜索"""
        results = []
        for provider in self._providers:
            try:
                results.extend(provider.search(query, author, isbn))
            except Exception as e:
                self.logger.warning(f"{provider.PROVIDER_NAME} 搜索失败: {e}")
        return results
    
    def get_all_providers(self) -> List[BaseMetadataProvider]:
        return self._providers.copy()


# 全局注册表
_registry: Optional[MetadataProviderRegistry] = None


def get_provider_registry() -> MetadataProviderRegistry:
    global _registry
    if _registry is None:
        _registry = MetadataProviderRegistry()
        
        # 注册内置提供者
        try:
            from cps.metadata_provider.openlibrary import OpenLibraryProvider
            _registry.register(OpenLibraryProvider())
        except ImportError:
            pass
        
        try:
            from cps.metadata_provider.google_books import GoogleBooksProvider
            _registry.register(GoogleBooksProvider())
        except ImportError:
            pass
    
    return _registry


def search_metadata(query: str, author: str = "", isbn: str = "") -> List[ExternalMetadata]:
    """在所有提供者中搜索元数据"""
    registry = get_provider_registry()
    return registry.search_all(query, author, isbn)


def get_metadata_by_isbn(isbn: str, provider_name: str = "") -> Optional[ExternalMetadata]:
    """根据 ISBN 获取元数据"""
    registry = get_provider_registry()
    
    if provider_name:
        provider = registry.get_provider(provider_name)
        if provider:
            return provider.get_by_isbn(isbn)
    
    # 遍历所有提供者
    for provider in registry.get_all_providers():
        result = provider.get_by_isbn(isbn)
        if result:
            return result
    
    return None