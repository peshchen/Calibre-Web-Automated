"""
T002: 扫描器模块 - 目录扫描器
=============================

功能：扫描指定目录，发现图书文件

支持格式：epub, mobi, azw3, pdf, txt, fb2, cbz, cbr, djvu, docx, rtf, html, lit, pdb

扫描模式：
- 全量扫描：扫描所有文件
- 增量扫描：只扫描新增/修改的文件（基于文件修改时间）

使用示例：
    from cps.scanner.library_scanner import LibraryScanner, ScanConfig
    
    config = ScanConfig(
        scan_directories=['/path/to/books'],
        supported_formats=['epub', 'pdf', 'mobi'],
        incremental=True,
        progress_callback=callback
    )
    
    scanner = LibraryScanner(config)
    result = scanner.scan()
"""

import os
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


# 支持的电子书格式
DEFAULT_SUPPORTED_FORMATS = [
    'epub', 'mobi', 'azw3', 'azw', 'pdf', 
    'txt', 'fb2', 'cbz', 'cbr', 'djvu', 
    'docx', 'doc', 'rtf', 'html', 'htm', 
    'lit', 'pdb', 'chm'
]

logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """扫描配置"""
    # 扫描目录列表
    scan_directories: list[str] = field(default_factory=list)
    
    # 支持的文件格式（不区分大小写）
    supported_formats: list[str] = field(default_factory=lambda: DEFAULT_SUPPORTED_FORMATS.copy())
    
    # 是否启用增量扫描
    incremental: bool = False
    
    # 增量扫描时，忽略修改时间超过此秒数的文件（默认 24 小时）
    incremental_threshold_seconds: int = 86400
    
    # 进度回调函数 (current: int, total: int, file_path: str) -> None
    progress_callback: Optional[Callable[[int, int, str], None]] = None
    
    # 是否递归扫描子目录
    recursive: bool = True
    
    # 最大文件数限制（防止内存溢出）
    max_files: int = 100000
    
    # 排除的目录（支持通配符）
    exclude_directories: list[str] = field(default_factory=lambda: ['.*', '__pycache__', 'node_modules'])


@dataclass
class BookFile:
    """图书文件信息"""
    file_path: str  # 绝对路径
    file_name: str
    file_ext: str
    file_size: int
    modified_time: datetime
    created_time: datetime
    
    # 用于增量扫描的文件特征
    file_hash: str = ""
    
    def __post_init__(self):
        if not self.file_hash:
            self.file_hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """计算文件哈希（仅用于增量扫描比对）"""
        # 简单哈希：路径 + 大小 + 修改时间
        key = f"{self.file_path}:{self.file_size}:{self.modified_time.timestamp()}"
        return hashlib.md5(key.encode()).hexdigest()[:16]


@dataclass
class ScanWarning:
    """扫描警告"""
    file_path: str
    warning_type: str  # 'file_not_found', 'permission_denied', 'duplicate', etc.
    message: str


@dataclass
class ScanError:
    """扫描错误"""
    file_path: str
    error_type: str  # 'parse_error', 'metadata_error', etc.
    message: str
    exception: Optional[Exception] = None


@dataclass
class ScanResult:
    """扫描结果"""
    total_files: int = 0
    new_books: int = 0
    updated_books: int = 0
    warnings: list[ScanWarning] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)
    duration_seconds: float = 0.0
    scan_type: str = "full"  # 'full' or 'incremental'
    scan_directories: list[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """扫描是否成功完成"""
        return len(self.errors) == 0
    
    @property
    def summary(self) -> str:
        """结果摘要"""
        return f"扫描完成: {self.total_files} 文件, {self.new_books} 新增, {self.updated_books} 更新, {len(self.warnings)} 警告, {len(self.errors)} 错误"


class LibraryScanner:
    """
    图书目录扫描器
    
    功能：
    - 遍历指定目录，发现支持的图书文件
    - 支持全量扫描和增量扫描
    - 过滤不支持的文件格式
    - 进度报告
    """
    
    def __init__(self, config: ScanConfig):
        """
        初始化扫描器
        
        Args:
            config: 扫描配置
        """
        self.config = config
        self._book_files: list[BookFile] = []
        self._processed_count = 0
        self._last_state_file = None
        
        # 标准化支持格式（转小写）
        self._supported_formats = {fmt.lower().strip('.') for fmt in config.supported_formats}
        
        logger.info(f"LibraryScanner 初始化完成，扫描目录: {config.scan_directories}")
    
    def scan_full(self) -> ScanResult:
        """执行全量扫描"""
        start_time = datetime.now()
        result = ScanResult(scan_type="full", scan_directories=self.config.scan_directories)
        
        logger.info("开始全量扫描...")
        
        # 获取所有要扫描的文件
        all_files = self._discover_files()
        result.total_files = len(all_files)
        
        logger.info(f"发现 {result.total_files} 个文件")
        
        # 处理每个文件
        for idx, file_path in enumerate(all_files):
            try:
                book_file = self._process_file(file_path)
                if book_file:
                    self._book_files.append(book_file)
                    
                    # 增量检测：新文件 vs 已存在
                    existing = self._find_existing_by_path(book_file.file_path)
                    if existing:
                        result.updated_books += 1
                    else:
                        result.new_books += 1
                        
            except Exception as e:
                logger.warning(f"处理文件失败: {file_path}, 错误: {e}")
                result.errors.append(ScanError(
                    file_path=file_path,
                    error_type="process_error",
                    message=str(e),
                    exception=e
                ))
            
            # 进度回调
            if self.config.progress_callback:
                self.config.progress_callback(idx + 1, result.total_files, file_path)
        
        # 计算耗时
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"全量扫描完成: {result.summary}")
        return result
    
    def scan_incremental(self) -> ScanResult:
        """执行增量扫描"""
        start_time = datetime.now()
        result = ScanResult(scan_type="incremental", scan_directories=self.config.scan_directories)
        
        logger.info("开始增量扫描...")
        
        # 获取所有文件
        all_files = self._discover_files()
        result.total_files = len(all_files)
        
        # 与已存在记录对比
        existing_paths = self._get_existing_paths()
        
        threshold = datetime.now().timestamp() - self.config.incremental_threshold_seconds
        
        for idx, file_path in enumerate(all_files):
            try:
                # 检查文件修改时间
                file_mtime = os.path.getmtime(file_path)
                
                if file_mtime < threshold:
                    # 文件未在阈值时间内修改，跳过
                    continue
                
                # 新增或修改的文件
                book_file = self._process_file(file_path)
                if book_file:
                    self._book_files.append(book_file)
                    
                    if file_path in existing_paths:
                        result.updated_books += 1
                    else:
                        result.new_books += 1
                        
            except Exception as e:
                logger.warning(f"处理文件失败: {file_path}, 错误: {e}")
                result.errors.append(ScanError(
                    file_path=file_path,
                    error_type="process_error",
                    message=str(e),
                    exception=e
                ))
            
            # 进度回调
            if self.config.progress_callback:
                self.config.progress_callback(idx + 1, result.total_files, file_path)
        
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"增量扫描完成: {result.summary}")
        return result
    
    def scan(self) -> ScanResult:
        """执行扫描（根据配置自动选择全量或增量）"""
        if self.config.incremental:
            return self.scan_incremental()
        else:
            return self.scan_full()
    
    def _discover_files(self) -> list[str]:
        """发现所有支持的图书文件"""
        files = []
        
        for directory in self.config.scan_directories:
            if not os.path.exists(directory):
                logger.warning(f"扫描目录不存在: {directory}")
                continue
            
            if not os.path.isdir(directory):
                logger.warning(f"扫描路径不是目录: {directory}")
                continue
            
            # 递归或非递归遍历
            if self.config.recursive:
                files.extend(self._discover_recursive(directory))
            else:
                files.extend(self._discover_single(directory))
            
            logger.info(f"目录扫描完成: {directory}, 发现 {len(files)} 个文件")
        
        # 检查文件数限制
        if len(files) > self.config.max_files:
            logger.warning(f"文件数超过限制 {self.config.max_files}，将只处理前 {self.config.max_files} 个")
            files = files[:self.config.max_files]
        
        return files
    
    def _discover_recursive(self, directory: str) -> list[str]:
        """递归发现文件"""
        files = []
        
        for root, dirs, filenames in os.walk(directory):
            # 过滤排除的目录
            dirs[:] = [d for d in dirs if not self._is_excluded_directory(d)]
            
            for filename in filenames:
                file_path = os.path.join(root, filename)
                if self._is_supported_file(filename):
                    files.append(file_path)
        
        return files
    
    def _discover_single(self, directory: str) -> list[str]:
        """单层目录发现文件"""
        files = []
        
        for entry in os.scandir(directory):
            if entry.is_file() and self._is_supported_file(entry.name):
                files.append(entry.path)
        
        return files
    
    def _is_supported_file(self, filename: str) -> bool:
        """检查文件是否支持"""
        ext = Path(filename).suffix.lower().strip('.')
        return ext in self._supported_formats
    
    def _is_excluded_directory(self, dirname: str) -> bool:
        """检查目录是否应排除"""
        for pattern in self.config.exclude_directories:
            import fnmatch
            if fnmatch.fnmatch(dirname, pattern):
                return True
        return False
    
    def _process_file(self, file_path: str) -> Optional[BookFile]:
        """处理单个文件，返回 BookFile 对象"""
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return None
        
        stat = os.stat(file_path)
        
        book_file = BookFile(
            file_path=os.path.abspath(file_path),
            file_name=os.path.basename(file_path),
            file_ext=Path(file_path).suffix.lower().strip('.'),
            file_size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            created_time=datetime.fromtimestamp(stat.st_ctime)
        )
        
        return book_file
    
    def _find_existing_by_path(self, file_path: str) -> Optional[BookFile]:
        """根据路径查找已存在的记录（用于增量扫描比对）"""
        # 实际实现需要查询数据库
        # 这里提供接口，具体实现由 BookRepository 完成
        return None
    
    def _get_existing_paths(self) -> set[str]:
        """获取所有已存在文件的路径集合"""
        # 实际实现需要查询数据库
        return set()
    
    def get_book_files(self) -> list[BookFile]:
        """获取扫描到的图书文件列表"""
        return self._book_files
    
    @property
    def book_count(self) -> int:
        """获取扫描到的图书数量"""
        return len(self._book_files)


def create_scanner(
    scan_directories: list[str],
    supported_formats: Optional[list[str]] = None,
    incremental: bool = False,
    progress_callback: Optional[Callable] = None
) -> LibraryScanner:
    """创建扫描器的便捷函数"""
    config = ScanConfig(
        scan_directories=scan_directories,
        supported_formats=supported_formats or DEFAULT_SUPPORTED_FORMATS,
        incremental=incremental,
        progress_callback=progress_callback
    )
    return LibraryScanner(config)


# 单元测试入口
if __name__ == '__main__':
    import tempfile
    
    # 创建临时测试目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        test_files = [
            'test.epub',
            'test.pdf',
            'test.txt',
            'test.jpg',  # 不支持
        ]
        
        for f in test_files:
            Path(tmpdir, f).touch()
        
        # 测试扫描
        scanner = create_scanner(
            scan_directories=[tmpdir],
            incremental=False
        )
        
        result = scanner.scan()
        
        print(f"\n扫描结果:")
        print(f"  总文件数: {result.total_files}")
        print(f"  新增图书: {result.new_books}")
        print(f"  更新图书: {result.updated_books}")
        print(f"  警告数: {len(result.warnings)}")
        print(f"  错误数: {len(result.errors)}")
        print(f"  耗时: {result.duration_seconds:.2f}秒")
        
        # 验证结果
        assert result.total_files == 3, f"期望3个文件，实际{result.total_files}"
        print("\n✅ 单元测试通过")