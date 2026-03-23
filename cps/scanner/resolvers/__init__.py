"""
扫描器解析器模块
=================

提供各种电子书格式的解析器

已支持的格式：
- BookResolver: epub, mobi, azw3, fb2 等通用格式
- PdfResolver: PDF 格式
- TxtResolver: TXT 纯文本格式

使用示例：
    from cps.scanner.resolvers import resolve_file
    
    metadata = resolve_file('/path/to/book.epub')
"""

from .base_resolver import (
    BaseResolver,
    BookMetadata,
    ResolverRegistry,
    get_resolver_registry,
    resolve_file
)

from .book_resolver import BookResolver
from .pdf_resolver import PdfResolver
from .txt_resolver import TxtResolver


__all__ = [
    'BaseResolver',
    'BookMetadata',
    'ResolverRegistry',
    'get_resolver_registry',
    'resolve_file',
    'BookResolver',
    'PdfResolver',
    'TxtResolver',
]