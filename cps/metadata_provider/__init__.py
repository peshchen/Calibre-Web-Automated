"""
元数据提供者模块
================

提供外部元数据获取功能

支持的提供者：
- OpenLibrary: https://openlibrary.org/
- Google Books: https://books.google.com/

使用示例：
    from cps.metadata_provider import search_metadata, get_metadata_by_isbn
    
    # 搜索图书
    results = search_metadata("Harry Potter", author="Rowling")
    for r in results:
        print(f"标题: {r.title}, 作者: {r.author}")
    
    # ISBN 查询
    metadata = get_metadata_by_isbn("9780747532743")
    if metadata:
        print(f"找到: {metadata.title}")
"""

from .base_provider import (
    BaseMetadataProvider,
    ExternalMetadata,
    MetadataProviderRegistry,
    get_provider_registry,
    search_metadata,
    get_metadata_by_isbn
)

from .openlibrary import OpenLibraryProvider, get_openlibrary_provider

from .google_books import GoogleBooksProvider, get_google_books_provider


__all__ = [
    # 基类
    'BaseMetadataProvider',
    'ExternalMetadata',
    'MetadataProviderRegistry',
    
    # 便捷函数
    'get_provider_registry',
    'search_metadata',
    'get_metadata_by_isbn',
    
    # 提供者
    'OpenLibraryProvider',
    'get_openlibrary_provider',
    'GoogleBooksProvider',
    'get_google_books_provider',
]