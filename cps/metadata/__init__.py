"""
元数据模块
==========

提供图书元数据提取和管理功能

模块：
- filename_parser: 文件名解析器
- local_metadata: 本地元数据读取
- cover_saver: 封面和元数据保存

使用示例：
    from cps.metadata import parse_filename, read_local_metadata, save_book_extras
    
    # 解析文件名
    parsed = parse_filename('/path/to/book.txt')
    print(f"标题: {parsed.title}, 作者: {parsed.author}")
    
    # 读取本地元数据
    metadata = read_local_metadata('/path/to/book.txt')
    
    # 保存额外元数据（对应 M006 需求）
    save_book_extras('/path/to/book.txt', cover_data=cover, metadata=metadata)
"""

from .filename_parser import (
    FilenameParser,
    ParsedFilename,
    parse_filename,
    parse_author_from_filename,
    parse_title_from_filename
)

from .local_metadata import (
    LocalMetadataReader,
    get_local_metadata_reader,
    read_local_metadata,
    read_local_cover
)

from .cover_saver import (
    CoverSaver,
    get_cover_saver,
    save_book_cover,
    save_book_metadata,
    save_book_extras
)

__all__ = [
    # 文件名解析
    'FilenameParser',
    'ParsedFilename',
    'parse_filename',
    'parse_author_from_filename',
    'parse_title_from_filename',
    
    # 本地元数据
    'LocalMetadataReader',
    'get_local_metadata_reader',
    'read_local_metadata',
    'read_local_cover',
    
    # 封面保存
    'CoverSaver',
    'get_cover_saver',
    'save_book_cover',
    'save_book_metadata',
    'save_book_extras',
]