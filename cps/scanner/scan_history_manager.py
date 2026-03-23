"""
T012: 扫描历史管理
==================

功能：管理扫描历史记录

注意：scan_history 表在 T001 中创建
扫描记录功能在 T006 中实现
这里提供额外的统计和分析功能
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ScanStatistics:
    """扫描统计"""
    total_scans: int = 0
    total_books_added: int = 0
    total_books_updated: int = 0
    total_warnings: int = 0
    total_errors: int = 0
    avg_duration: float = 0.0
    last_scan_time: Optional[datetime] = None


class ScanHistoryManager:
    """
    扫描历史管理器
    
    功能：
    - 查询扫描历史
    - 统计扫描数据
    - 生成报告
    """
    
    def __init__(self, db_session=None):
        self.db = db_session
    
    def get_recent_scans(self, limit: int = 20) -> List[Dict]:
        """获取最近的扫描记录"""
        try:
            from sqlalchemy import text
            
            if self.db is None:
                from cps import db as calibre_db
                self.db = calibre_db.session
            
            result = self.db.execute(
                text("""
                    SELECT id, scan_time, scan_type, scan_directory,
                           total_files, books_added, books_updated,
                           books_warning, books_error, duration_seconds,
                           status, error_message, created_by
                    FROM scan_history
                    ORDER BY scan_time DESC
                    LIMIT :limit
                """),
                {'limit': limit}
            )
            
            return [
                {
                    'id': row[0],
                    'scan_time': row[1],
                    'scan_type': row[2],
                    'scan_directory': row[3],
                    'total_files': row[4],
                    'books_added': row[5],
                    'books_updated': row[6],
                    'books_warning': row[7],
                    'books_error': row[8],
                    'duration_seconds': row[9],
                    'status': row[10],
                    'error_message': row[11],
                    'created_by': row[12]
                }
                for row in result
            ]
            
        except Exception as e:
            logger.error(f"获取扫描历史失败: {e}")
            return []
    
    def get_statistics(self, days: int = 30) -> ScanStatistics:
        """
        获取扫描统计
        
        Args:
            days: 统计天数
            
        Returns:
            ScanStatistics: 统计信息
        """
        stats = ScanStatistics()
        
        try:
            from sqlalchemy import text
            
            if self.db is None:
                from cps import db as calibre_db
                self.db = calibre_db.session
            
            # 计算时间范围
            start_time = datetime.now(timezone.utc) - timedelta(days=days)
            
            result = self.db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_scans,
                        COALESCE(SUM(books_added), 0) as total_added,
                        COALESCE(SUM(books_updated), 0) as total_updated,
                        COALESCE(SUM(books_warning), 0) as total_warnings,
                        COALESCE(SUM(books_error), 0) as total_errors,
                        COALESCE(AVG(duration_seconds), 0) as avg_duration,
                        MAX(scan_time) as last_scan
                    FROM scan_history
                    WHERE scan_time >= :start_time
                """),
                {'start_time': start_time}
            )
            
            row = result.fetchone()
            if row:
                stats.total_scans = row[0] or 0
                stats.total_books_added = row[1] or 0
                stats.total_books_updated = row[2] or 0
                stats.total_warnings = row[3] or 0
                stats.total_errors = row[4] or 0
                stats.avg_duration = float(row[5] or 0)
                stats.last_scan_time = row[6]
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
        
        return stats
    
    def get_daily_trend(self, days: int = 7) -> List[Dict]:
        """
        获取每日趋势
        
        Args:
            days: 天数
            
        Returns:
            list: 每日统计数据
        """
        try:
            from sqlalchemy import text
            
            if self.db is None:
                from cps import db as calibre_db
                self.db = calibre_db.session
            
            start_time = datetime.now(timezone.utc) - timedelta(days=days)
            
            result = self.db.execute(
                text("""
                    SELECT 
                        DATE(scan_time) as scan_date,
                        COUNT(*) as scan_count,
                        SUM(books_added) as books_added,
                        SUM(books_updated) as books_updated
                    FROM scan_history
                    WHERE scan_time >= :start_time
                    GROUP BY DATE(scan_time)
                    ORDER BY scan_date DESC
                """),
                {'start_time': start_time}
            )
            
            return [
                {
                    'date': row[0],
                    'scan_count': row[1],
                    'books_added': row[2] or 0,
                    'books_updated': row[3] or 0
                }
                for row in result
            ]
            
        except Exception as e:
            logger.error(f"获取趋势数据失败: {e}")
            return []
    
    def clear_old_records(self, keep_days: int = 90) -> int:
        """
        清理旧记录
        
        Args:
            keep_days: 保留天数
            
        Returns:
            int: 删除的记录数
        """
        try:
            from sqlalchemy import text
            
            if self.db is None:
                from cps import db as calibre_db
                self.db = calibre_db.session
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=keep_days)
            
            result = self.db.execute(
                text("""
                    DELETE FROM scan_history
                    WHERE scan_time < :cutoff_time
                """),
                {'cutoff_time': cutoff_time}
            )
            
            self.db.commit()
            
            deleted = result.rowcount
            if deleted > 0:
                logger.info(f"已清理 {deleted} 条旧扫描记录")
            
            return deleted
            
        except Exception as e:
            logger.error(f"清理旧记录失败: {e}")
            return 0


def get_scan_history(limit: int = 20) -> List[Dict]:
    """获取扫描历史"""
    manager = ScanHistoryManager()
    return manager.get_recent_scans(limit)


def get_scan_stats(days: int = 30) -> ScanStatistics:
    """获取扫描统计"""
    manager = ScanHistoryManager()
    return manager.get_statistics(days)


def get_scan_trend(days: int = 7) -> List[Dict]:
    """获取扫描趋势"""
    manager = ScanHistoryManager()
    return manager.get_daily_trend(days)