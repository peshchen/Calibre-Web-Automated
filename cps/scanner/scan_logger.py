"""
T009: 扫描日志记录器
====================

功能：记录扫描过程中的详细信息
"""

import logging
import json
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass, field, asdict


logger = logging.getLogger(__name__)


@dataclass
class ScanLogEntry:
    """扫描日志条目"""
    timestamp: str
    level: str  # INFO, WARNING, ERROR
    category: str  # scanner, resolver, repository, etc.
    message: str
    details: Optional[dict] = None


class ScanLogger:
    """
    扫描日志记录器
    
    用于详细记录扫描过程
    """
    
    def __init__(self, task_id: str = ""):
        """
        初始化日志记录器
        
        Args:
            task_id: 任务 ID
        """
        self.task_id = task_id
        self._entries: List[ScanLogEntry] = []
        self._stats = {
            'files_scanned': 0,
            'files_added': 0,
            'files_updated': 0,
            'warnings': 0,
            'errors': 0
        }
    
    def info(self, category: str, message: str, details: dict = None):
        """记录信息"""
        self._add_entry('INFO', category, message, details)
    
    def warning(self, category: str, message: str, details: dict = None):
        """记录警告"""
        self._stats['warnings'] += 1
        self._add_entry('WARNING', category, message, details)
        logger.warning(f"[{category}] {message}")
    
    def error(self, category: str, message: str, details: dict = None):
        """记录错误"""
        self._stats['errors'] += 1
        self._add_entry('ERROR', category, message, details)
        logger.error(f"[{category}] {message}")
    
    def debug(self, category: str, message: str, details: dict = None):
        """记录调试信息"""
        self._add_entry('DEBUG', category, message, details)
        logger.debug(f"[{category}] {message}")
    
    def _add_entry(self, level: str, category: str, message: str, details: dict = None):
        """添加日志条目"""
        entry = ScanLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            category=category,
            message=message,
            details=details
        )
        self._entries.append(entry)
    
    def get_entries(self, level: str = None, category: str = None) -> List[ScanLogEntry]:
        """
        获取日志条目
        
        Args:
            level: 过滤级别
            category: 过滤分类
            
        Returns:
            list: 日志条目列表
        """
        entries = self._entries
        
        if level:
            entries = [e for e in entries if e.level == level]
        
        if category:
            entries = [e for e in entries if e.category == category]
        
        return entries
    
    def get_warnings(self) -> List[ScanLogEntry]:
        """获取所有警告"""
        return self.get_entries(level='WARNING')
    
    def get_errors(self) -> List[ScanLogEntry]:
        """获取所有错误"""
        return self.get_entries(level='ERROR')
    
    def update_stats(self, key: str, value: int = 1):
        """更新统计"""
        if key in self._stats:
            self._stats[key] += value
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self._stats.copy()
    
    def to_json(self) -> str:
        """导出为 JSON"""
        return json.dumps({
            'task_id': self.task_id,
            'stats': self._stats,
            'entries': [asdict(e) for e in self._entries]
        }, indent=2, ensure_ascii=False)
    
    def clear(self):
        """清空日志"""
        self._entries.clear()
        self._stats = {
            'files_scanned': 0,
            'files_added': 0,
            'files_updated': 0,
            'warnings': 0,
            'errors': 0
        }


# 全局日志记录器
_scan_logger: Optional[ScanLogger] = None


def get_scan_logger(task_id: str = "") -> ScanLogger:
    """获取扫描日志记录器"""
    global _scan_logger
    
    if _scan_logger is None or (task_id and _scan_logger.task_id != task_id):
        _scan_logger = ScanLogger(task_id)
    
    return _scan_logger


def reset_scan_logger():
    """重置扫描日志记录器"""
    global _scan_logger
    if _scan_logger:
        _scan_logger.clear()