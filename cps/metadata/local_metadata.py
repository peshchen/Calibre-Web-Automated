"""
T004: 本地元数据读取
====================

从图书文件同目录的 JSON 文件读取元数据

文件命名规则：
- book.json （与书籍同名）
- metadata.json （通用）
- .json （隐藏文件，与书籍同名）

JSON 格式示例：
```json
{
    "title": "书名",
    "author": "作者",
    "description": "简介",
    "publisher": "出版社",
    "pubdate": "2024-01-01",
    "isbn": "978-7-xxx",
    "language": "zh-CN",
    "series": "系列名",
    "series_index": "1",
    "tags": ["标签1", "标签2"],
    "cover": "cover.jpg"
}
```
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class LocalMetadataReader:
    """
    本地元数据读取器
    
    从图书文件同目录的 JSON 文件读取元数据
    """
    
    # JSON 元数据文件名模式
    METADATA_FILENAMES = [
        '{base}.json',           # book.json (与书籍同名)
        'metadata.json',          # 通用元数据文件
        '.{base}.json',          # .book.json (隐藏文件)
        '{base}_meta.json',      # book_meta.json
        'info.json',             # info.json
    ]
    
    # 支持的封面文件名模式
    COVER_FILENAMES = [
        '{base}_cover.jpg',
        '{base}_cover.png',
        '{base}.jpg',
        '{base}.png',
        'cover.jpg',
        'cover.png',
        'folder.jpg',
        'folder.png',
    ]
    
    def __init__(self):
        """初始化读取器"""
        self._cache = {}  # 缓存已读取的元数据
    
    def read_metadata(self, book_path: str) -> Optional[dict]:
        """
        读取图书的元数据
        
        Args:
            book_path: 图书文件路径
            
        Returns:
            dict: 元数据字典，或 None
        """
        if not os.path.exists(book_path):
            logger.warning(f"文件不存在: {book_path}")
            return None
        
        # 检查缓存
        if book_path in self._cache:
            return self._cache[book_path]
        
        # 查找 JSON 元数据文件
        metadata = self._find_and_load_json(book_path)
        
        if metadata:
            logger.info(f"从本地文件加载元数据: {book_path}")
            self._cache[book_path] = metadata
        
        return metadata
    
    def read_cover_path(self, book_path: str) -> Optional[str]:
        """
        获取封面图片路径
        
        Args:
            book_path: 图书文件路径
            
        Returns:
            str: 封面图片路径，或 None
        """
        book_dir = os.path.dirname(book_path)
        book_stem = Path(book_path).stem
        
        for pattern in self.COVER_FILENAMES:
            # 替换占位符
            filename = pattern.replace('{base}', book_stem)
            cover_path = os.path.join(book_dir, filename)
            
            if os.path.exists(cover_path):
                logger.debug(f"找到封面: {cover_path}")
                return cover_path
        
        return None
    
    def read_cover_image(self, book_path: str) -> Optional[bytes]:
        """
        读取封面图片数据
        
        Args:
            book_path: 图书文件路径
            
        Returns:
            bytes: 图片数据，或 None
        """
        cover_path = self.read_cover_path(book_path)
        
        if not cover_path:
            return None
        
        try:
            with open(cover_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"读取封面失败: {cover_path}, {e}")
        
        return None
    
    def _find_and_load_json(self, book_path: str) -> Optional[dict]:
        """查找并加载 JSON 元数据文件"""
        book_dir = os.path.dirname(book_path)
        book_stem = Path(book_path).stem
        
        for pattern in self.METADATA_FILENAMES:
            # 替换占位符
            filename = pattern.replace('{base}', book_stem)
            json_path = os.path.join(book_dir, filename)
            
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return self._normalize_metadata(data)
                except Exception as e:
                    logger.warning(f"读取元数据失败: {json_path}, {e}")
        
        return None
    
    def _normalize_metadata(self, data: dict) -> dict:
        """标准化元数据"""
        normalized = {}
        
        # 字符串字段
        for field in ['title', 'author', 'description', 'publisher', 'pubdate', 'isbn', 'language', 'series']:
            if field in data and data[field]:
                normalized[field] = str(data[field]).strip()
        
        # 系列序号
        if 'series_index' in data and data['series_index']:
            normalized['series_index'] = str(data['series_index'])
        
        # 标签
        if 'tags' in data:
            tags = data['tags']
            if isinstance(tags, list):
                normalized['tags'] = [str(t).strip() for t in tags if t]
            elif isinstance(tags, str):
                normalized['tags'] = [t.strip() for t in tags.split(',') if t.strip()]
        
        # 封面文件名
        if 'cover' in data and data['cover']:
            normalized['cover'] = str(data['cover']).strip()
        
        return normalized
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 全局实例
_default_reader: Optional[LocalMetadataReader] = None


def get_local_metadata_reader() -> LocalMetadataReader:
    """获取默认的本地元数据读取器"""
    global _default_reader
    if _default_reader is None:
        _default_reader = LocalMetadataReader()
    return _default_reader


def read_local_metadata(book_path: str) -> Optional[dict]:
    """
    便捷函数：读取本地元数据
    
    Args:
        book_path: 图书文件路径
        
    Returns:
        dict: 元数据，或 None
    """
    reader = get_local_metadata_reader()
    return reader.read_metadata(book_path)


def read_local_cover(book_path: str) -> Optional[bytes]:
    """
    便捷函数：读取本地封面
    
    Args:
        book_path: 图书文件路径
        
    Returns:
        bytes: 封面图片数据，或 None
    """
    reader = get_local_metadata_reader()
    return reader.read_cover_image(book_path)


# 测试
if __name__ == '__main__':
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        book_path = os.path.join(tmpdir, 'test_book.txt')
        Path(book_path).touch()
        
        # 创建元数据文件
        metadata = {
            "title": "测试图书",
            "author": "测试作者",
            "description": "这是一个测试",
            "tags": ["测试", "���例"]
        }
        
        json_path = os.path.join(tmpdir, 'test_book.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 测试读取
        reader = LocalMetadataReader()
        result = reader.read_metadata(book_path)
        
        print("测试结果:")
        print(f"  元数据: {result}")
        print(f"  封面: {reader.read_cover_path(book_path)}")