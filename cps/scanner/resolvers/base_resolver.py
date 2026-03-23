"""
T003: 解析器基类
=================

定义图书解析器的接口和通用功能

所有具体解析器都应继承此基类
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class BookMetadata:
    """图书元数据"""
    title: str = ""
    author: str = ""
    author_sort: str = ""
    description: str = ""
    publisher: str = ""
    pubdate: str = ""
    isbn: str = ""
    language: str = ""
    series: str = ""
    series_index: str = "1.0"
    tags: list[str] = None
    
    # 封面
    cover_image: Optional[bytes] = None
    cover_image_ext: str = "jpg"
    
    # 文件信息
    file_path: str = ""
    file_format: str = ""
    file_size: int = 0
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class BaseResolver(ABC):
    """
    解析器基类
    
    所有文件格式解析器都应继承此类
    """
    
    # 支持的文件扩展名（子类需要覆盖）
    SUPPORTED_EXTENSIONS: list[str] = []
    
    def __init__(self):
        """初始化解析器"""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_resolve(self, file_path: str) -> bool:
        """
        检查此解析器是否能处理给定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否能处理
        """
        pass
    
    @abstractmethod
    def resolve(self, file_path: str) -> Optional[BookMetadata]:
        """
        解析文件并提取元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            BookMetadata: 提取的元数据，解析失败返回 None
        """
        pass
    
    def get_file_extension(self, file_path: str) -> str:
        """获取文件扩展名（小写，不含点）"""
        return Path(file_path).suffix.lower().strip('.')
    
    def is_supported(self, file_path: str) -> bool:
        """检查文件是否被此解析器支持"""
        ext = self.get_file_extension(file_path)
        return ext in [e.lower() for e in self.SUPPORTED_EXTENSIONS]
    
    def _extract_cover_from_archive(self, file_path: str, archive_extensions: list[str]) -> Optional[bytes]:
        """
        从压缩包中提取封面
        
        Args:
            file_path: 文件路径
            archive_extensions: 支持的压缩包格式
            
        Returns:
            bytes: 封面图片数据，或 None
        """
        import zipfile
        
        ext = self.get_file_extension(file_path)
        if ext not in archive_extensions:
            return None
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # 查找常见封面文件名
                cover_names = [
                    'cover.jpg', 'cover.jpeg', 'cover.png',
                    'Cover.jpg', 'Cover.jpeg', 'Cover.png',
                    'cover.jpg', 'OEBPS/Images/cover.jpg',
                    'Images/cover.jpg', 'images/cover.jpg',
                ]
                
                for name in zf.namelist():
                    name_lower = name.lower()
                    if any(name_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                        if 'cover' in name_lower:
                            # 找到封面
                            with zf.open(name) as img:
                                return img.read()
                
                # 如果没找到封面，尝试第一张图片
                for name in zf.namelist():
                    if any(name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                        # 检查是否是图片文件（非目录）
                        if not name.endswith('/'):
                            with zf.open(name) as img:
                                return img.read()
                            
        except Exception as e:
            self.logger.warning(f"从压缩包提取封面失败: {file_path}, 错误: {e}")
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        解析日期字符串为标准格式
        
        Args:
            date_str: 日期字符串
            
        Returns:
            str: 标准化后的日期字符串，或 None
        """
        from datetime import datetime
        
        if not date_str:
            return None
        
        # 尝试多种日期格式
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y-%m',
            '%Y',
            '%B %d, %Y',
            '%b %d, %Y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None


class ResolverRegistry:
    """
    解析器注册表
    
    管理所有可用的解析器，提供文件到解析器的映射
    """
    
    def __init__(self):
        """初始化注册表"""
        self._resolvers: list[BaseResolver] = []
    
    def register(self, resolver: BaseResolver) -> None:
        """注册解析器"""
        if resolver not in self._resolvers:
            self._resolvers.append(resolver)
            logger.info(f"注册解析器: {resolver.__class__.__name__}")
    
    def unregister(self, resolver: BaseResolver) -> None:
        """注销解析器"""
        if resolver in self._resolvers:
            self._resolvers.remove(resolver)
    
    def get_resolver(self, file_path: str) -> Optional[BaseResolver]:
        """
        获取适合处理文件的解析器
        
        Args:
            file_path: 文件路径
            
        Returns:
            BaseResolver: 解析器实例，或 None
        """
        for resolver in self._resolvers:
            if resolver.can_resolve(file_path):
                return resolver
        return None
    
    def resolve_file(self, file_path: str) -> Optional[BookMetadata]:
        """
        解析文件（自动选择合适的解析器）
        
        Args:
            file_path: 文件路径
            
        Returns:
            BookMetadata: 元数据，或 None
        """
        resolver = self.get_resolver(file_path)
        if resolver:
            return resolver.resolve(file_path)
        
        logger.warning(f"没有找到合适的解析器: {file_path}")
        return None
    
    def get_all_resolvers(self) -> list[BaseResolver]:
        """获取所有已注册的解析器"""
        return self._resolvers.copy()
    
    def get_supported_extensions(self) -> set[str]:
        """获取所有支持的文件扩展名"""
        extensions = set()
        for resolver in self._resolvers:
            extensions.update(resolver.SUPPORTED_EXTENSIONS)
        return extensions


# 全局解析器注册表
_default_registry: Optional[ResolverRegistry] = None


def get_resolver_registry() -> ResolverRegistry:
    """获取默认的解析器注册表"""
    global _default_registry
    
    if _default_registry is None:
        _default_registry = ResolverRegistry()
        
        # 注册所有内置解析器
        from cps.scanner.resolvers import (
            BookResolver,
            PdfResolver,
            TxtResolver,
        )
        
        _default_registry.register(BookResolver())
        _default_registry.register(PdfResolver())
        _default_registry.register(TxtResolver())
    
    return _default_registry


def resolve_file(file_path: str) -> Optional[BookMetadata]:
    """
    便捷函数：使用默认注册表解析文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        BookMetadata: 元数据，或 None
    """
    registry = get_resolver_registry()
    return registry.resolve_file(file_path)