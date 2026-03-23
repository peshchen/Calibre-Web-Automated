"""
T004: 封面保存器
================

当图书源文件没有内嵌元数据/封面时（如 TXT），将提取的封面和元数据保存到源文件同目录

保存规则：
- 封面保存为：{原文件名}.jpg 或 {原文件名}.png
- 元数据保存为：{原文件名}.json

这对应需求文档中的 M006 功能：
"源文件无元数据时（如txt），额外提取的封面和元数据保存在源文件相同目录，文件名与源文件相同"
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class CoverSaver:
    """
    封面和元数据保存器
    
    功能：
    - 保存封面图片到源文件同目录
    - 保存元数据到 JSON 文件
    - 避免重复保存（检查文件是否存在）
    """
    
    def __init__(self):
        """初始化保存器"""
        self._saved_count = 0
    
    def save_cover(self, book_path: str, cover_data: bytes, image_format: str = 'jpg') -> Optional[str]:
        """
        保存封面图片
        
        Args:
            book_path: 图书文件路径
            cover_data: 封面图片数据
            image_format: 图片格式 ('jpg' 或 'png')
            
        Returns:
            str: 保存的文件路径，或 None
        """
        if not cover_data:
            logger.debug("没有封面数据可保存")
            return None
        
        book_dir = os.path.dirname(book_path)
        book_stem = Path(book_path).stem
        
        # 封面文件名
        cover_filename = f"{book_stem}.{image_format}"
        cover_path = os.path.join(book_dir, cover_filename)
        
        # 检查是否已存在
        if os.path.exists(cover_path):
            logger.info(f"封面已存在，跳过保存: {cover_path}")
            return cover_path
        
        try:
            with open(cover_path, 'wb') as f:
                f.write(cover_data)
            
            self._saved_count += 1
            logger.info(f"封面已保存: {cover_path}")
            return cover_path
            
        except Exception as e:
            logger.error(f"保存封面失败: {cover_path}, {e}")
            return None
    
    def save_metadata(self, book_path: str, metadata: dict) -> Optional[str]:
        """
        保存元数据到 JSON 文件
        
        Args:
            book_path: 图书文件路径
            metadata: 元数据字典
            
        Returns:
            str: 保存的文件路径，或 None
        """
        if not metadata:
            logger.debug("没有元数据可保存")
            return None
        
        book_dir = os.path.dirname(book_path)
        book_stem = Path(book_path).stem
        
        # 元数据文件名
        json_filename = f"{book_stem}.json"
        json_path = os.path.join(book_dir, json_filename)
        
        # 检查是否已存在
        if os.path.exists(json_path):
            logger.info(f"元数据已存在，跳过保存: {json_path}")
            return json_path
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            self._saved_count += 1
            logger.info(f"元数据已保存: {json_path}")
            return json_path
            
        except Exception as e:
            logger.error(f"保存元数据失败: {json_path}, {e}")
            return None
    
    def save(self, book_path: str, cover_data: Optional[bytes] = None, 
             metadata: Optional[dict] = None, cover_format: str = 'jpg') -> dict:
        """
        统一保存封面和元数据
        
        Args:
            book_path: 图书文件路径
            cover_data: 封面图片数据
            metadata: 元数据字典
            cover_format: 封面格式 ('jpg' 或 'png')
            
        Returns:
            dict: 保存结果 {'cover': path, 'metadata': path}
        """
        result = {
            'cover': None,
            'metadata': None
        }
        
        # 保存封面
        if cover_data:
            result['cover'] = self.save_cover(book_path, cover_data, cover_format)
        
        # 保存元数据
        if metadata:
            result['metadata'] = self.save_metadata(book_path, metadata)
        
        return result
    
    def should_save_cover(self, book_path: str) -> bool:
        """
        检查是否应该保存封面
        
        条件：
        - 封面文件不存在
        - 图书文件存在
        """
        if not os.path.exists(book_path):
            return False
        
        book_dir = os.path.dirname(book_path)
        book_stem = Path(book_path).stem
        
        for ext in ['jpg', 'png']:
            cover_path = os.path.join(book_dir, f"{book_stem}.{ext}")
            if not os.path.exists(cover_path):
                return True
        
        return False
    
    def should_save_metadata(self, book_path: str) -> bool:
        """
        检查是否应该保存元数据
        
        条件：
        - 元数据文件不存在
        - 图书文件存在
        """
        if not os.path.exists(book_path):
            return False
        
        book_dir = os.path.dirname(book_path)
        book_stem = Path(book_path).stem
        json_path = os.path.join(book_dir, f"{book_stem}.json")
        
        return not os.path.exists(json_path)
    
    @property
    def saved_count(self) -> int:
        """获取已保存的文件数量"""
        return self._saved_count
    
    def reset_count(self):
        """重置计数器"""
        self._saved_count = 0


# 全局实例
_default_saver: Optional[CoverSaver] = None


def get_cover_saver() -> CoverSaver:
    """获取默认的封面保存器"""
    global _default_saver
    if _default_saver is None:
        _default_saver = CoverSaver()
    return _default_saver


def save_book_cover(book_path: str, cover_data: bytes, image_format: str = 'jpg') -> Optional[str]:
    """
    便捷函数：保存图书封面
    
    Args:
        book_path: 图书文件路径
        cover_data: 封面图片数据
        image_format: 图片格式
        
    Returns:
        str: 保存的文件路径
    """
    saver = get_cover_saver()
    return saver.save_cover(book_path, cover_data, image_format)


def save_book_metadata(book_path: str, metadata: dict) -> Optional[str]:
    """
    便捷函数：保存图书元数据
    
    Args:
        book_path: 图书文件路径
        metadata: 元数据字典
        
    Returns:
        str: 保存的文件路径
    """
    saver = get_cover_saver()
    return saver.save_metadata(book_path, metadata)


def save_book_extras(book_path: str, cover_data: Optional[bytes] = None, 
                     metadata: Optional[dict] = None) -> dict:
    """
    便捷函数：保存图书的额外元数据和封面
    
    对应需求 M006：
    "源文件无元数据时（如txt），额外提取的封面和元数据保存在源文件相同目录"
    
    Args:
        book_path: 图书文件路径
        cover_data: 封面图片数据
        metadata: 元数据字典
        
    Returns:
        dict: 保存结果
    """
    saver = get_cover_saver()
    return saver.save(book_path, cover_data, metadata)


# 测试
if __name__ == '__main__':
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试图书文件
        book_path = os.path.join(tmpdir, 'test_book.txt')
        Path(book_path).touch()
        
        # 测试封面保存
        saver = CoverSaver()
        cover_data = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # 模拟 JPEG 头
        cover_result = saver.save_cover(book_path, cover_data, 'jpg')
        print(f"封面保存结果: {cover_result}")
        
        # 测试元数据保存
        metadata = {
            'title': '测试图书',
            'author': '测试作者',
            'tags': ['测试']
        }
        metadata_result = saver.save_metadata(book_path, metadata)
        print(f"元数据保存结果: {metadata_result}")
        
        print(f"已保存文件数: {saver.saved_count}")