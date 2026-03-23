"""
T008: 扫描模式图书文件访问辅助模块
====================================

功能：支持扫描模式图书的读取和下载

主要功能：
- 获取扫描模式图书的源文件路径
- 验证源文件是否存在
- 提供文件读取接口
"""

import os
import logging
from typing import Optional, Tuple
from flask import send_file, abort


logger = logging.getLogger(__name__)


# 扫描模式常量
SCAN_MODE_IMPORT = 0  # 导入模式
SCAN_MODE_SCANNER = 1  # 扫描模式


class ScannerBookFile:
    """
    扫描模式图书文件访问器
    
    用于处理扫描模式图书的源文件访问
    """
    
    @staticmethod
    def get_source_path(book_id: int) -> Optional[str]:
        """
        获取图书的源文件路径
        
        Args:
            book_id: 图书 ID
            
        Returns:
            str: 源文件绝对路径，或 None
        """
        try:
            from cps import calibre_db, db
            
            book = calibre_db.get_book(book_id)
            if not book:
                return None
            
            # 检查是否是扫描模式
            if getattr(book, 'scan_mode', 0) != SCAN_MODE_SCANNER:
                return None
            
            # 获取源文件路径
            source_path = getattr(book, 'source_path', '')
            
            if not source_path:
                logger.warning(f"图书 {book_id} 没有源文件路径")
                return None
            
            return source_path
            
        except Exception as e:
            logger.error(f"获取源文件路径失败: {e}")
            return None
    
    @staticmethod
    def is_source_exists(book_id: int) -> Tuple[bool, str]:
        """
        检查源文件是否存在
        
        Args:
            book_id: 图书 ID
            
        Returns:
            tuple: (是否存在, 错误信息)
        """
        source_path = ScannerBookFile.get_source_path(book_id)
        
        if not source_path:
            return False, "图书不是扫描模式或没有源文件路径"
        
        if not os.path.exists(source_path):
            logger.warning(f"源文件不存在: {source_path}")
            return False, f"源文件不存在: {source_path}"
        
        return True, ""
    
    @staticmethod
    def get_file_info(book_id: int) -> Optional[dict]:
        """
        获取图书文件信息
        
        Args:
            book_id: 图书 ID
            
        Returns:
            dict: 文件信息，或 None
        """
        source_path = ScannerBookFile.get_source_path(book_id)
        
        if not source_path or not os.path.exists(source_path):
            return None
        
        stat = os.stat(source_path)
        
        return {
            'path': source_path,
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'format': os.path.splitext(source_path)[1].lstrip('.').lower()
        }
    
    @staticmethod
    def read_file(book_id: int, chunk_size: int = 8192):
        """
        读取图书文件（用于流式传输）
        
        Args:
            book_id: 图书 ID
            chunk_size: 分块大小
            
        Returns:
            Flask response 对象
        """
        # 检查文件是否存在
        exists, error = ScannerBookFile.is_source_exists(book_id)
        if not exists:
            logger.error(f"读取失败: {error}")
            abort(404)
        
        source_path = ScannerBookFile.get_source_path(book_id)
        
        try:
            # 获取文件信息
            file_info = ScannerBookFile.get_file_info(book_id)
            
            # 获取文件名
            filename = os.path.basename(source_path)
            
            return send_file(
                source_path,
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            abort(500)
    
    @staticmethod
    def validate_before_read(book_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        读取前的验证
        
        Args:
            book_id: 图书 ID
            
        Returns:
            tuple: (是否有效, 错误信息, 文件信息)
        """
        try:
            from cps import calibre_db
            
            book = calibre_db.get_book(book_id)
            if not book:
                return False, "图书不存在", None
            
            # 检查扫描模式
            if getattr(book, 'scan_mode', 0) != SCAN_MODE_SCANNER:
                return False, "图书不是扫描模式", None
            
            # 获取文件信息
            file_info = ScannerBookFile.get_file_info(book_id)
            if not file_info:
                return False, "源文件不存在或无法访问", None
            
            return True, "", file_info
            
        except Exception as e:
            logger.error(f"验证失败: {e}")
            return False, str(e), None


def get_book_file_path(book_id: int, book_format: str = "") -> Optional[str]:
    """
    获取图书文件路径（统一接口）
    
    优先返回扫描模式源文件路径，否则返回导入模式路径
    
    Args:
        book_id: 图书 ID
        book_format: 图书格式（可选）
        
    Returns:
        str: 文件路径，或 None
    """
    try:
        from cps import calibre_db, config
        
        book = calibre_db.get_book(book_id)
        if not book:
            return None
        
        # 检查是否是扫描模式
        if getattr(book, 'scan_mode', 0) == SCAN_MODE_SCANNER:
            # 扫描模式：返回源文件路径
            source_path = getattr(book, 'source_path', '')
            if source_path and os.path.exists(source_path):
                return source_path
        
        # 导入模式：返回 Calibre 库路径
        if book_format:
            # 获取对应格式的文件
            for data in book.data:
                if data.format.lower() == book_format.lower():
                    return os.path.join(
                        config.get_book_path(),
                        book.path,
                        data.name + "." + book_format.lower()
                    )
        
        # 返回第一个可用格式
        if book.data:
            data = book.data[0]
            return os.path.join(
                config.get_book_path(),
                book.path,
                data.name + "." + data.format.lower()
            )
        
        return None
        
    except Exception as e:
        logger.error(f"获取图书文件路径失败: {e}")
        return None


def check_book_file_exists(book_id: int) -> Tuple[bool, str]:
    """
    检查图书文件是否存在
    
    Args:
        book_id: 图书 ID
        
    Returns:
        tuple: (是否存在, 错误信息)
    """
    try:
        from cps import calibre_db
        
        book = calibre_db.get_book(book_id)
        if not book:
            return False, "图书不存在"
        
        # 扫描模式
        if getattr(book, 'scan_mode', 0) == SCAN_MODE_SCANNER:
            source_path = getattr(book, 'source_path', '')
            if not source_path:
                return False, "图书没有源文件路径"
            if not os.path.exists(source_path):
                return False, f"源文件不存在: {source_path}"
            return True, ""
        
        # 导入模式：检查 Calibre 库
        from cps import config
        for data in book.data:
            file_path = os.path.join(
                config.get_book_path(),
                book.path,
                data.name + "." + data.format.lower()
            )
            if os.path.exists(file_path):
                return True, ""
        
        return False, "图书文件不存在"
        
    except Exception as e:
        logger.error(f"检查图书文件存在失败: {e}")
        return False, str(e)


# 用于 Web.py 的补丁函数
def patched_get_book_path(book, book_format, config):
    """
    修补后的获取图书路径函数
    
    支持扫描模式图书的源文件路径
    """
    # 检查是否是扫描模式
    if getattr(book, 'scan_mode', 0) == SCAN_MODE_SCANNER:
        source_path = getattr(book, 'source_path', '')
        if source_path and os.path.exists(source_path):
            return source_path
    
    # 原有逻辑：Calibre 库路径
    for data in book.data:
        if not book_format or data.format.lower() == book_format.lower():
            return os.path.join(
                config.get_book_path(),
                book.path,
                data.name + "." + data.format.lower()
            )
    
    return None