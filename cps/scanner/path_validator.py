"""
T009: 路径有效性校验
=====================

功能：扫描时检查文件是否存在，标记警告

主要功能：
- 文件存在性检查
- 路径可访问性验证
- 警告日志记录
- 批量路径校验
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class PathWarning:
    """路径警告"""
    file_path: str
    warning_type: str  # 'not_found', 'permission_denied', 'inaccessible', 'symbolic_link'
    message: str
    severity: str = "warning"  # 'warning', 'error'


@dataclass
class PathValidationResult:
    """路径校验结果"""
    total_checked: int = 0
    valid_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    warnings: List[PathWarning] = field(default_factory=list)
    
    @property
    def summary(self) -> str:
        return f"校验完成: {self.total_checked} 文件, {self.valid_count} 有效, {self.warning_count} 警告, {self.error_count} 错误"


class PathValidator:
    """
    路径验证器
    
    功能：
    - 检查文件是否存在
    - 检查文件是否可读
    - 检查路径是否为符号链接
    - 处理网络存储路径
    """
    
    def __init__(self):
        """初始化验证器"""
        self._cache = {}  # 缓存验证结果
    
    def validate_path(self, file_path: str, check_exists: bool = True) -> Tuple[bool, Optional[PathWarning]]:
        """
        验证单个路径
        
        Args:
            file_path: 文件路径
            check_exists: 是否检查文件存在
            
        Returns:
            tuple: (是否有效, 警告信息)
        """
        if not file_path:
            return False, PathWarning(
                file_path="",
                warning_type="empty_path",
                message="路径为空",
                severity="error"
            )
        
        # 路径规范化
        try:
            file_path = os.path.abspath(file_path)
        except Exception as e:
            return False, PathWarning(
                file_path=file_path,
                warning_type="invalid_path",
                message=f"无效路径: {e}",
                severity="error"
            )
        
        # 检查是否存在
        if check_exists:
            if not os.path.exists(file_path):
                return False, PathWarning(
                    file_path=file_path,
                    warning_type="not_found",
                    message="文件不存在",
                    severity="warning"
                )
            
            # 检查是否为目录
            if os.path.isdir(file_path):
                return False, PathWarning(
                    file_path=file_path,
                    warning_type="is_directory",
                    message="路径是目录而非文件",
                    severity="error"
                )
        
        # 检查可读性
        if os.path.exists(file_path):
            if not os.access(file_path, os.R_OK):
                return False, PathWarning(
                    file_path=file_path,
                    warning_type="permission_denied",
                    message="文件不可读",
                    severity="error"
                )
        
        # 检查符号链接
        if os.path.islink(file_path):
            target = os.readlink(file_path)
            # 检查链接目标是否存在
            if not os.path.exists(target):
                return False, PathWarning(
                    file_path=file_path,
                    warning_type="broken_link",
                    message=f"符号链接目标不存在: {target}",
                    severity="warning"
                )
            
            logger.debug(f"文件是符号链接: {file_path} -> {target}")
        
        # 路径穿越检查（安全）
        real_path = os.path.realpath(file_path)
        if not real_path.startswith(os.path.commonpath([real_path, file_path])):
            return False, PathWarning(
                file_path=file_path,
                warning_type="path_traversal",
                message="检测到可能的路径穿越",
                severity="error"
            )
        
        return True, None
    
    def validate_paths(self, file_paths: List[str]) -> PathValidationResult:
        """
        批量验证路径
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            PathValidationResult: 验证结果
        """
        result = PathValidationResult()
        result.total_checked = len(file_paths)
        
        for file_path in file_paths:
            is_valid, warning = self.validate_path(file_path)
            
            if is_valid:
                result.valid_count += 1
            else:
                result.warning_count += 1
                result.warnings.append(warning)
                
                if warning.severity == "error":
                    result.error_count += 1
        
        return result
    
    def validate_book(self, book_id: int) -> Tuple[bool, List[PathWarning]]:
        """
        验证图书的源文件路径
        
        Args:
            book_id: 图书 ID
            
        Returns:
            tuple: (是否有效, 警告列表)
        """
        warnings = []
        
        try:
            from cps import calibre_db
            
            book = calibre_db.get_book(book_id)
            if not book:
                return False, [PathWarning(
                    file_path="",
                    warning_type="book_not_found",
                    message=f"图书不存在: ID={book_id}",
                    severity="error"
                )]
            
            # 检查扫描模式
            scan_mode = getattr(book, 'scan_mode', 0)
            if scan_mode != 1:  # 非扫描模式
                return True, []
            
            # 获取源文件路径
            source_path = getattr(book, 'source_path', '')
            if not source_path:
                return False, [PathWarning(
                    file_path="",
                    warning_type="no_source_path",
                    message="图书没有源文件路径",
                    severity="error"
                )]
            
            # 验证路径
            is_valid, warning = self.validate_path(source_path)
            if not is_valid:
                warnings.append(warning)
            
            return is_valid, warnings
            
        except Exception as e:
            logger.error(f"验证图书路径失败: {e}")
            return False, [PathWarning(
                file_path="",
                warning_type="validation_error",
                message=str(e),
                severity="error"
            )]
    
    def validate_all_scanner_books(self, limit: int = 1000) -> PathValidationResult:
        """
        验证所有扫描模式图书的路径
        
        Args:
            limit: 最大验证数量
            
        Returns:
            PathValidationResult: 验证结果
        """
        result = PathValidationResult()
        
        try:
            from cps import calibre_db, db
            
            # 获取所有扫描模式图书
            books = calibre_db.session.query(db.Books).filter(
                db.Books.scan_mode == 1  # 扫描模式
            ).limit(limit).all()
            
            result.total_checked = len(books)
            
            for book in books:
                source_path = getattr(book, 'source_path', '')
                if source_path:
                    is_valid, warning = self.validate_path(source_path)
                    
                    if is_valid:
                        result.valid_count += 1
                    else:
                        result.warning_count += 1
                        if warning:
                            # 添加图书 ID 到警告信息
                            warning.message = f"[Book ID: {book.id}] {warning.message}"
                            result.warnings.append(warning)
                            
                            if warning.severity == "error":
                                result.error_count += 1
            
            logger.info(f"路径校验完成: {result.summary}")
            
        except Exception as e:
            logger.error(f"批量验证失败: {e}")
        
        return result
    
    def get_missing_files_report(self) -> List[dict]:
        """
        获取缺失文件报告
        
        Returns:
            list: 缺失文件列表（包含图书信息）
        """
        missing = []
        
        try:
            from cps import calibre_db, db
            
            # 获取所有扫描模式图书
            books = calibre_db.session.query(db.Books).filter(
                db.Books.scan_mode == 1
            ).all()
            
            for book in books:
                source_path = getattr(book, 'source_path', '')
                if source_path and not os.path.exists(source_path):
                    missing.append({
                        'book_id': book.id,
                        'title': book.title,
                        'source_path': source_path,
                        'missing_since': self._get_file_missing_time(source_path)
                    })
            
        except Exception as e:
            logger.error(f"获取缺失文件报告失败: {e}")
        
        return missing
    
    def _get_file_missing_time(self, file_path: str) -> Optional[str]:
        """获取文件丢失时间（如果可以确定）"""
        # 这需要数据库记录文件状态历史，目前返回 None
        return None


def validate_book_path(book_id: int) -> Tuple[bool, List[PathWarning]]:
    """
    验证图书路径的便捷函数
    
    Args:
        book_id: 图书 ID
        
    Returns:
        tuple: (是否有效, 警告列表)
    """
    validator = PathValidator()
    return validator.validate_book(book_id)


def get_missing_books_report() -> List[dict]:
    """
    获取缺失文件的图书报告
    
    Returns:
        list: 缺失文件列表
    """
    validator = PathValidator()
    return validator.get_missing_files_report()


# 扫描日志记录器
class ScanLogger:
    """
    扫描日志记录器
    
    记录扫描过程中的警告和错误
    """
    
    def __init__(self):
        """初始化日志记录器"""
        self._logs = []
    
    def add_warning(self, warning: PathWarning):
        """添加警告"""
        self._logs.append({
            'type': 'warning',
            'data': warning
        })
        logger.warning(f"扫描警告: {warning.file_path} - {warning.message}")
    
    def add_error(self, error: PathWarning):
        """添加错误"""
        self._logs.append({
            'type': 'error',
            'data': error
        })
        logger.error(f"扫描错误: {error.file_path} - {error.message}")
    
    def get_logs(self) -> List[dict]:
        """获取所有日志"""
        return self._logs
    
    def clear(self):
        """清空日志"""
        self._logs.clear()


# 全局日志记录器
_scan_logger: Optional[ScanLogger] = None


def get_scan_logger() -> ScanLogger:
    """获取扫描日志记录器"""
    global _scan_logger
    if _scan_logger is None:
        _scan_logger = ScanLogger()
    return _scan_logger