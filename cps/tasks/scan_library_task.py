"""
T006: 扫描任务调度
==================

功能：管理扫描任务的执行

支持：
- 手动触发全量/增量扫描
- 定时任务调度
- 进度回调
- 任务状态管理
"""

import os
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable, List
from enum import Enum


logger = logging.getLogger(__name__)


class ScanTaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanType(Enum):
    """扫描类型"""
    FULL = "full"        # 全量扫描
    INCREMENTAL = "incremental"  # 增量扫描


@dataclass
class ScanTask:
    """扫描任务"""
    task_id: str = ""
    scan_type: ScanType = ScanType.FULL
    scan_directories: List[str] = field(default_factory=list)
    status: ScanTaskStatus = ScanTaskStatus.PENDING
    
    # 进度信息
    progress: float = 0.0  # 0-100
    current_file: str = ""
    processed_count: int = 0
    total_count: int = 0
    
    # 结果
    total_files: int = 0
    new_books: int = 0
    updated_books: int = 0
    warnings: int = 0
    errors: int = 0
    
    # 时间
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # 错误信息
    error_message: str = ""
    
    # 创建者
    created_by: str = ""
    
    def __post_init__(self):
        if not self.task_id:
            import uuid
            self.task_id = str(uuid.uuid4())[:8]


class ScanLibraryTask:
    """
    扫描任务管理器
    
    功能：
    - 创建和执行扫描任务
    - 进度跟踪和回调
    - 任务状态管理
    - 后台执行
    """
    
    def __init__(self):
        """初始化任务管理器"""
        self._current_task: Optional[ScanTask] = None
        self._task_lock = threading.Lock()
        self._callbacks: List[Callable] = []
    
    def create_task(
        self,
        scan_type: ScanType = ScanType.FULL,
        scan_directories: Optional[List[str]] = None,
        created_by: str = ""
    ) -> ScanTask:
        """
        创建扫描任务
        
        Args:
            scan_type: 扫描类型
            scan_directories: 扫描目录列表
            created_by: 创建者
            
        Returns:
            ScanTask: 任务对象
        """
        task = ScanTask(
            scan_type=scan_type,
            scan_directories=scan_directories or [],
            created_by=created_by,
            status=ScanTaskStatus.PENDING
        )
        
        logger.info(f"创建扫描任务: {task.task_id}, 类型={scan_type.value}")
        return task
    
    def execute(
        self,
        task: ScanTask,
        db_session=None,
        progress_callback: Optional[Callable] = None
    ) -> ScanTask:
        """
        执行扫描任务
        
        Args:
            task: 扫描任务
            db_session: 数据库会话
            progress_callback: 进度回调函数
            
        Returns:
            ScanTask: 更新后的任务对象
        """
        with self._task_lock:
            # 检查是否有任务在运行
            if self._current_task and self._current_task.status == ScanTaskStatus.RUNNING:
                logger.warning("已有任务在运行")
                task.status = ScanTaskStatus.FAILED
                task.error_message = "已有任务在运行"
                return task
            
            self._current_task = task
        
        task.status = ScanTaskStatus.RUNNING
        task.start_time = datetime.now(timezone.utc)
        
        # 记录到数据库
        self._save_task_to_db(task, db_session)
        
        # 触发回调
        self._trigger_callbacks(task)
        
        try:
            # 执行扫描
            logger.info(f"开始执行扫描任务: {task.task_id}")
            
            # 导入扫描器模块
            from cps.scanner import LibraryScanner, ScanConfig
            
            # 创建扫描配置
            config = ScanConfig(
                scan_directories=task.scan_directories,
                incremental=(task.scan_type == ScanType.INCREMENTAL),
                progress_callback=lambda current, total, file_path: self._on_progress(
                    task, current, total, file_path, progress_callback
                )
            )
            
            # 执行扫描
            scanner = LibraryScanner(config)
            result = scanner.scan()
            
            # 更新任务结果
            task.total_files = result.total_files
            task.new_books = result.new_books
            task.updated_books = result.updated_books
            task.warnings = len(result.warnings)
            task.errors = len(result.errors)
            task.duration_seconds = result.duration_seconds
            
            # 记录扫描历史到数据库
            self._save_scan_result_to_db(task, db_session)
            
            task.status = ScanTaskStatus.COMPLETED
            logger.info(f"扫描任务完成: {task.task_id}, 新增={task.new_books}, 更新={task.updated_books}")
            
        except Exception as e:
            task.status = ScanTaskStatus.FAILED
            task.error_message = str(e)
            logger.error(f"扫描任务失败: {task.task_id}, 错误: {e}")
        
        finally:
            task.end_time = datetime.now(timezone.utc)
            if task.duration_seconds == 0:
                task.duration_seconds = (task.end_time - task.start_time).total_seconds()
            
            # 更新数据库
            self._update_task_in_db(task, db_session)
            
            # 触发回调
            self._trigger_callbacks(task)
            
            with self._task_lock:
                self._current_task = None
        
        return task
    
    def execute_async(
        self,
        task: ScanTask,
        db_session=None,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        异步执行扫描任务
        
        Args:
            task: 扫描任务
            db_session: 数据库会话
            progress_callback: 进度回调
            
        Returns:
            str: 任务 ID
        """
        thread = threading.Thread(
            target=self.execute,
            args=(task, db_session, progress_callback),
            daemon=True
        )
        thread.start()
        
        logger.info(f"异步任务已启动: {task.task_id}")
        return task.task_id
    
    def get_current_task(self) -> Optional[ScanTask]:
        """获取当前运行的任务"""
        with self._task_lock:
            return self._current_task
    
    def cancel_current_task(self) -> bool:
        """取消当前任务"""
        with self._task_lock:
            if self._current_task and self._current_task.status == ScanTaskStatus.RUNNING:
                self._current_task.status = ScanTaskStatus.CANCELLED
                logger.info(f"任务已取消: {self._current_task.task_id}")
                return True
        return False
    
    def register_callback(self, callback: Callable):
        """注册任务状态回调"""
        self._callbacks.append(callback)
    
    def _on_progress(
        self,
        task: ScanTask,
        current: int,
        total: int,
        file_path: str,
        user_callback: Optional[Callable]
    ):
        """进度回调处理"""
        task.current_file = file_path
        task.processed_count = current
        task.total_count = total
        
        if total > 0:
            task.progress = (current / total) * 100
        
        # 触发用户回调
        if user_callback:
            user_callback(current, total, file_path)
        
        # 触发注册回调
        self._trigger_callbacks(task)
    
    def _trigger_callbacks(self, task: ScanTask):
        """触发所有注册的回调"""
        for callback in self._callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.warning(f"回调执行失败: {e}")
    
    def _save_task_to_db(self, task: ScanTask, db_session):
        """保存任务到数据库"""
        if not db_session:
            return
        
        try:
            from sqlalchemy import text
            
            db_session.execute(
                text("""
                    INSERT INTO scan_history 
                    (scan_time, scan_type, status, created_by)
                    VALUES (:scan_time, :scan_type, :status, :created_by)
                """),
                {
                    'scan_time': task.start_time or datetime.now(timezone.utc),
                    'scan_type': task.scan_type.value,
                    'status': task.status.value,
                    'created_by': task.created_by
                }
            )
            db_session.commit()
            
        except Exception as e:
            logger.warning(f"保存任务到数据库失败: {e}")
    
    def _save_scan_result_to_db(self, task: ScanTask, db_session):
        """保存扫描结果到数据库"""
        if not db_session:
            return
        
        try:
            from sqlalchemy import text
            
            db_session.execute(
                text("""
                    UPDATE scan_history SET
                        total_files = :total_files,
                        books_added = :books_added,
                        books_updated = :books_updated,
                        books_warning = :books_warning,
                        books_error = :books_error,
                        duration_seconds = :duration_seconds,
                        status = :status
                    WHERE scan_type = :scan_type AND status = 'running'
                    ORDER BY scan_time DESC LIMIT 1
                """),
                {
                    'total_files': task.total_files,
                    'books_added': task.new_books,
                    'books_updated': task.updated_books,
                    'books_warning': task.warnings,
                    'books_error': task.errors,
                    'duration_seconds': task.duration_seconds,
                    'status': task.status.value,
                    'scan_type': task.scan_type.value
                }
            )
            db_session.commit()
            
        except Exception as e:
            logger.warning(f"保存扫描结果失败: {e}")
    
    def _update_task_in_db(self, task: ScanTask, db_session):
        """更新任务状态到数据库"""
        if not db_session:
            return
        
        try:
            from sqlalchemy import text
            
            db_session.execute(
                text("""
                    UPDATE scan_history SET
                        status = :status,
                        error_message = :error_message
                    WHERE scan_type = :scan_type AND status = 'running'
                    ORDER BY scan_time DESC LIMIT 1
                """),
                {
                    'status': task.status.value,
                    'error_message': task.error_message,
                    'scan_type': task.scan_type.value
                }
            )
            db_session.commit()
            
        except Exception as e:
            logger.warning(f"更新任务状态失败: {e}")


# 全局任务管理器
_task_manager: Optional[ScanLibraryTask] = None


def get_scan_task_manager() -> ScanLibraryTask:
    """获取全局任务管理器"""
    global _task_manager
    if _task_manager is None:
        _task_manager = ScanLibraryTask()
    return _task_manager


def create_scan_task(
    scan_type: ScanType = ScanType.FULL,
    scan_directories: Optional[List[str]] = None,
    created_by: str = ""
) -> ScanTask:
    """创建扫描任务的便捷函数"""
    manager = get_scan_task_manager()
    return manager.create_task(scan_type, scan_directories, created_by)


def execute_scan_task(
    task: ScanTask,
    db_session = None,
    progress_callback: Optional[Callable] = None,
    async_mode: bool = False
) -> str:
    """
    执行扫描任务的便捷函数
    
    Args:
        task: 扫描任务
        db_session: 数据库会话
        progress_callback: 进度回调
        async_mode: 是否异步执行
        
    Returns:
        str: 任务 ID
    """
    manager = get_scan_task_manager()
    
    if async_mode:
        return manager.execute_async(task, db_session, progress_callback)
    else:
        manager.execute(task, db_session, progress_callback)
        return task.task_id


# 定时任务相关（需要与 APScheduler 集成）
def schedule_periodic_scan(
    scan_directories: List[str],
    interval_hours: int = 24,
    scan_type: ScanType = ScanType.INCREMENTAL
) -> str:
    """
    创建定时扫描任务
    
    注意：需要与 APScheduler 集成，这里只提供接口
    """
    # TODO: 与现有 schedule.py 集成
    logger.info(f"创建定时扫描: 每 {interval_hours} 小时执行 {scan_type.value} 扫描")
    return ""


def cancel_scheduled_scan(job_id: str) -> bool:
    """取消定时扫描任务"""
    # TODO: 与 APScheduler 集成
    logger.info(f"取消定时扫描: {job_id}")
    return True