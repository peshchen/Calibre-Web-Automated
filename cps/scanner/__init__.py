"""
扫描器模块
==========

提供图书目录扫描功能，支持：
- 全量扫描和增量扫描
- 多种电子书格式
- 进度报告和错误处理
- 数据库读写
- 路径验证
"""

from .library_scanner import (
    LibraryScanner,
    ScanConfig,
    ScanResult,
    BookFile,
    ScanWarning,
    ScanError,
    create_scanner,
    DEFAULT_SUPPORTED_FORMATS
)

from .book_repository import (
    BookRepository,
    BookRecord,
    SCAN_MODE_IMPORT,
    SCAN_MODE_SCANNER,
    create_repository
)

from .path_validator import (
    PathValidator,
    PathValidationResult,
    PathWarning,
    validate_book_path,
    get_missing_books_report
)

from .scan_logger import (
    ScanLogger,
    get_scan_logger,
    reset_scan_logger
)

from .book_file_helper import (
    ScannerBookFile,
    get_book_file_path,
    check_book_file_exists,
    SCAN_MODE_IMPORT,
    SCAN_MODE_SCANNER
)

__all__ = [
    # 扫描器
    'LibraryScanner',
    'ScanConfig', 
    'ScanResult',
    'BookFile',
    'ScanWarning',
    'ScanError',
    'create_scanner',
    'DEFAULT_SUPPORTED_FORMATS',
    
    # 仓储
    'BookRepository',
    'BookRecord',
    'SCAN_MODE_IMPORT',
    'SCAN_MODE_SCANNER',
    'create_repository',
    
    # 路径验证
    'PathValidator',
    'PathValidationResult',
    'PathWarning',
    'validate_book_path',
    'get_missing_books_report',
    
    # 日志
    'ScanLogger',
    'get_scan_logger',
    'reset_scan_logger',
    
    # 文件访问
    'ScannerBookFile',
    'get_book_file_path',
    'check_book_file_exists',
]