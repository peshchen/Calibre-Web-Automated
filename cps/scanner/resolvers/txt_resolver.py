"""
T003: TXT 解析器
================

专门处理纯文本格式的图书解析器

注意：TXT 文件通常没有内嵌元数据，需要：
1. 从文件名解析标题和作者
2. 从文件同目录的 .json 文件读取元数据（可选）
3. 提取第一张图片作为封面（可选）
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

from .base_resolver import BaseResolver, BookMetadata


logger = logging.getLogger(__name__)


class TxtResolver(BaseResolver):
    """
    TXT 纯文本解析器
    
    支持格式：txt, text
    """
    
    SUPPORTED_EXTENSIONS = ['txt', 'text']
    
    # TXT 文件编码尝试顺序
    ENCODING_PRIORITY = ['utf-8', 'gbk', 'gb2312', 'big5', 'latin1']
    
    def can_resolve(self, file_path: str) -> bool:
        """检查是否能处理此文件"""
        ext = self.get_file_extension(file_path)
        return ext.lower() in ['txt', 'text']
    
    def resolve(self, file_path: str) -> Optional[BookMetadata]:
        """
        解析 TXT 文件
        
        注意：TXT 文件没有标准元数据，主要靠：
        1. 文件名解析
        2. 同目录 .json 元数据文件
        3. 同目录 .jpg/.png 封面文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            BookMetadata: 提取的元数据
        """
        if not os.path.exists(file_path):
            self.logger.warning(f"文件不存在: {file_path}")
            return None
        
        try:
            metadata = BookMetadata()
            metadata.file_path = file_path
            metadata.file_format = 'txt'
            metadata.file_size = os.path.getsize(file_path)
            
            # 1. 首先尝试从文件名解析
            metadata = self._extract_from_filename(file_path, metadata)
            
            # 2. 尝试读取同目录的 .json 元数据文件
            json_metadata = self._load_json_metadata(file_path)
            if json_metadata:
                metadata = self._merge_metadata(metadata, json_metadata)
            
            # 3. 尝试提取第一张图片作为封面
            cover_image = self._extract_first_image(file_path)
            if cover_image:
                metadata.cover_image = cover_image
                metadata.cover_image_ext = 'jpg'
            
            # 4. 尝试从文件内容提取元数据（前几行）
            content_metadata = self._extract_from_content(file_path)
            if content_metadata:
                metadata = self._merge_metadata(metadata, content_metadata)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"解析 TXT 失败: {file_path}, 错误: {e}")
            return None
    
    def _load_json_metadata(self, file_path: str) -> Optional[dict]:
        """
        加载同目录的 JSON 元数据文件
        
        文件命名规则：{原文件名}.json
        例如：book.txt -> book.json
        """
        base_path = file_path.rsplit('.', 1)[0]  # 去掉扩展名
        json_path = f"{base_path}.json"
        
        if not os.path.exists(json_path):
            return None
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.logger.info(f"找到元数据文件: {json_path}")
                return data
        except Exception as e:
            self.logger.warning(f"读取 JSON 元数据失败: {json_path}, {e}")
        
        return None
    
    def _extract_first_image(self, file_path: str) -> Optional[bytes]:
        """
        提取同目录的第一张图片作为封面
        
        查找顺序：
        - {原文件名}_cover.jpg
        - {原文件名}_cover.png
        - cover.jpg
        - cover.png
        """
        base_path = file_path.rsplit('.', 1)[0]
        base_dir = os.path.dirname(file_path)
        
        # 候选封面文件
        cover_candidates = [
            f"{base_path}_cover.jpg",
            f"{base_path}_cover.png",
            f"{base_path}.jpg",
            f"{base_path}.png",
            "cover.jpg",
            "cover.png",
            "folder.jpg",
            "folder.png",
        ]
        
        for candidate in cover_candidates:
            candidate_path = os.path.join(base_dir, candidate)
            if os.path.exists(candidate_path):
                try:
                    with open(candidate_path, 'rb') as f:
                        image_data = f.read()
                        self.logger.info(f"找到封面图片: {candidate_path}")
                        return image_data
                except Exception as e:
                    self.logger.warning(f"读取封面失败: {candidate_path}, {e}")
        
        return None
    
    def _extract_from_content(self, file_path: str) -> Optional[dict]:
        """
        从文件内容提取元数据
        
        尝试从文件开头提取：
        - 标题（第一行，或以 "标题:" 开头）
        - 作者（以 "作者:" 开头）
        - 描述（前几段）
        """
        try:
            content = self._read_file_content(file_path, max_lines=100)
            if not content:
                return None
            
            metadata = {}
            lines = content.split('\n')
            
            # 检查前几行是否有元数据标记
            for line in lines[:10]:
                line = line.strip()
                if not line:
                    continue
                
                # 标题标记
                if line.startswith('标题:') or line.startswith('书名:'):
                    metadata['title'] = line.split(':', 1)[1].strip()
                
                # 作者标记
                elif line.startswith('作者:') or line.startswith('著:'):
                    metadata['author'] = line.split(':', 1)[1].strip()
                
                # 描述标记
                elif line.startswith('简介:') or line.startswith('内容简介:'):
                    metadata['description'] = line.split(':', 1)[1].strip()
            
            # 如果没有标记，尝试用第一行作为标题
            if 'title' not in metadata and lines:
                first_line = lines[0].strip()
                if first_line and len(first_line) > 0:
                    # 跳过非常短或很长的行
                    if 1 < len(first_line) < 200:
                        metadata['title'] = first_line
            
            return metadata if metadata else None
            
        except Exception as e:
            self.logger.debug(f"从内容提取元数据失败: {e}")
        
        return None
    
    def _read_file_content(self, file_path: str, max_lines: int = 100, max_chars: int = 50000) -> Optional[str]:
        """读取文件内容（自动检测编码）"""
        # 尝试多种编码
        for encoding in self.ENCODING_PRIORITY:
            try:
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    # 读取指定行数
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    
                    content = ''.join(lines)
                    
                    # 限制字符数
                    if len(content) > max_chars:
                        content = content[:max_chars]
                    
                    return content
                    
            except Exception as e:
                continue
        
        return None
    
    def _extract_from_filename(self, file_path: str, metadata: BookMetadata) -> BookMetadata:
        """从文件名解析元数据"""
        import re
        
        filename = Path(file_path).stem
        
        # 模式1: 《书名》- 作者
        match = re.match(r'[《"](.+)[》"]\s*[-–]\s*(.+)', filename)
        if match:
            metadata.title = match.group(1).strip()
            metadata.author = match.group(2).strip()
            metadata.author_sort = metadata.author
            return metadata
        
        # 模式2: 书名 - 作者
        match = re.match(r'(.+?)\s*[-–]\s*(.+)', filename)
        if match:
            title = match.group(1).strip()
            author = match.group(2).strip()
            if len(title) > len(author):
                metadata.title = title
                metadata.author = author
            else:
                metadata.title = author
                metadata.author = title
            metadata.author_sort = metadata.author
            return metadata
        
        # 模式3: 书名_作者
        match = re.match(r'(.+?)_(.+)', filename)
        if match:
            metadata.title = match.group(1).strip()
            metadata.author = match.group(2).strip()
            metadata.author_sort = metadata.author
            return metadata
        
        # 模式4: 书名#作者
        match = re.match(r'(.+)#(.+)', filename)
        if match:
            metadata.title = match.group(1).strip()
            metadata.author = match.group(2).strip()
            metadata.author_sort = metadata.author
            return metadata
        
        # 默认：使用文件名作为标题
        metadata.title = filename
        return metadata
    
    def _merge_metadata(self, base: BookMetadata, updates: dict) -> BookMetadata:
        """合并元数据（updates 优先）"""
        if not updates:
            return base
        
        if 'title' in updates and updates['title']:
            base.title = updates['title']
        
        if 'author' in updates and updates['author']:
            base.author = updates['author']
            base.author_sort = updates['author']
        
        if 'description' in updates and updates['description']:
            base.description = updates['description']
        
        if 'publisher' in updates and updates['publisher']:
            base.publisher = updates['publisher']
        
        if 'pubdate' in updates and updates['pubdate']:
            base.pubdate = self._parse_date(updates['pubdate'])
        
        if 'isbn' in updates and updates['isbn']:
            base.isbn = updates['isbn']
        
        if 'language' in updates and updates['language']:
            base.language = updates['language']
        
        if 'series' in updates and updates['series']:
            base.series = updates['series']
        
        if 'series_index' in updates and updates['series_index']:
            base.series_index = str(updates['series_index'])
        
        if 'tags' in updates and updates['tags']:
            if isinstance(updates['tags'], list):
                base.tags = updates['tags']
            elif isinstance(updates['tags'], str):
                base.tags = [t.strip() for t in updates['tags'].split(',')]
        
        if 'cover_image' in updates and updates['cover_image']:
            base.cover_image = updates['cover_image']
        
        return base
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """解析日期字符串"""
        from datetime import datetime
        
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y']
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None


# 注册解析器
def _register_resolver():
    """注册此解析器"""
    from .base_resolver import get_resolver_registry
    registry = get_resolver_registry()
    registry.register(TxtResolver())


_register_resolver()