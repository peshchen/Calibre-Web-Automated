"""
T011: 数据备份和恢复
====================

功能：
- 扫描前自动备份数据库
- 异常时支持恢复
- 备份历史管理
"""

import os
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    """备份信息"""
    backup_id: str
    backup_path: str
    created_at: datetime
    size: int
    type: str  # 'auto', 'manual'
    status: str  # 'completed', 'failed'
    description: str = ""


class DatabaseBackup:
    """
    数据库备份管理器
    
    功能：
    - 创建数据库备份
    - 恢复数据库
    - 管理备份历史
    - 自动清理过期备份
    """
    
    def __init__(self, db_path: str, backup_dir: Optional[str] = None):
        """
        初始化备份管理器
        
        Args:
            db_path: 数据库文件路径
            backup_dir: 备份目录（默认 db_path.backups）
        """
        self.db_path = db_path
        self.backup_dir = backup_dir or f"{db_path}.backups"
        
        # 确保备份目录存在
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, backup_type: str = 'auto', description: str = "") -> Optional[BackupInfo]:
        """
        创建数据库备份
        
        Args:
            backup_type: 备份类型 ('auto' 或 'manual')
            description: 描述
            
        Returns:
            BackupInfo: 备份信息，或 None
        """
        import uuid
        
        if not os.path.exists(self.db_path):
            logger.error(f"数据库文件不存在: {self.db_path}")
            return None
        
        try:
            # 生成备份文件名
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            backup_id = str(uuid.uuid4())[:8]
            backup_filename = f"backup_{backup_type}_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # 复制数据库文件
            shutil.copy2(self.db_path, backup_path)
            
            # 获取文件大小
            size = os.path.getsize(backup_path)
            
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_path=backup_path,
                created_at=datetime.now(timezone.utc),
                size=size,
                type=backup_type,
                status='completed',
                description=description
            )
            
            # 保存备份元信息
            self._save_backup_meta(backup_info)
            
            logger.info(f"数据库备份成功: {backup_path}, 大小: {size} bytes")
            return backup_info
            
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        恢复数据库
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 是否恢复成功
        """
        if not os.path.exists(backup_path):
            logger.error(f"备份文件不存在: {backup_path}")
            return False
        
        try:
            # 备份当前数据库（如果存在）
            if os.path.exists(self.db_path):
                current_backup = f"{self.db_path}.pre_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.db_path, current_backup)
                logger.info(f"当前数据库已备份到: {current_backup}")
            
            # 恢复备份
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"数据库恢复成功: {self.db_path}")
            return True
            
        except Exception as e:
            logger.error(f"数据库恢复失败: {e}")
            return False
    
    def list_backups(self, limit: int = 10) -> List[BackupInfo]:
        """
        获取备份列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            list: 备份信息列表
        """
        backups = []
        
        try:
            # 查找所有备份文件
            for filename in sorted(os.listdir(self.backup_dir), reverse=True):
                if filename.startswith('backup_') and filename.endswith('.db'):
                    backup_path = os.path.join(self.backup_dir, filename)
                    
                    # 获取文件信息
                    stat = os.stat(backup_path)
                    
                    # 解析备份类型
                    parts = filename.split('_')
                    backup_type = parts[1] if len(parts) > 1 else 'unknown'
                    
                    # 从文件名提取时间
                    timestamp_str = '_'.join(parts[2:]).replace('.db', '')
                    try:
                        created_at = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    except ValueError:
                        created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    
                    backups.append(BackupInfo(
                        backup_id=parts[-1].replace('.db', ''),
                        backup_path=backup_path,
                        created_at=created_at,
                        size=stat.st_size,
                        type=backup_type,
                        status='completed'
                    ))
                    
                    if len(backups) >= limit:
                        break
            
        except Exception as e:
            logger.error(f"获取备份列表失败: {e}")
        
        return backups
    
    def delete_backup(self, backup_path: str) -> bool:
        """
        删除备份
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 是否删除成功
        """
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
                logger.info(f"备份已删除: {backup_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"删除���份失败: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        清理旧备份
        
        Args:
            keep_count: 保留的备份数量
            
        Returns:
            int: 删除的备份数量
        """
        backups = self.list_backups(limit=100)
        
        # 只保留 auto 类型的备份
        auto_backups = [b for b in backups if b.type == 'auto']
        
        # 删除多余的备份
        deleted = 0
        for backup in auto_backups[keep_count:]:
            if self.delete_backup(backup.backup_path):
                deleted += 1
        
        if deleted > 0:
            logger.info(f"已清理 {deleted} 个旧备份")
        
        return deleted
    
    def _save_backup_meta(self, backup_info: BackupInfo):
        """保存备份元信息"""
        # 可以扩展为保存到 JSON 文件
        pass


def create_backup(db_path: str, backup_dir: str = None, backup_type: str = 'auto') -> Optional[BackupInfo]:
    """
    创建数据库备份的便捷函数
    
    Args:
        db_path: 数据库路径
        backup_dir: 备份目录
        backup_type: 备份类型
        
    Returns:
        BackupInfo: 备份信息
    """
    manager = DatabaseBackup(db_path, backup_dir)
    return manager.create_backup(backup_type)


def restore_from_backup(db_path: str, backup_path: str, backup_dir: str = None) -> bool:
    """
    从备份恢复数据库
    
    Args:
        db_path: 数据库路径
        backup_path: 备份文件路径
        backup_dir: 备份目录
        
    Returns:
        bool: 是否恢复成功
    """
    manager = DatabaseBackup(db_path, backup_dir)
    return manager.restore_backup(backup_path)


def get_backup_list(db_path: str, backup_dir: str = None, limit: int = 10) -> List[BackupInfo]:
    """获取备份列表"""
    manager = DatabaseBackup(db_path, backup_dir)
    return manager.list_backups(limit)