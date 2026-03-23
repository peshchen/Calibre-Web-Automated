"""
T004: 文件名解析器
==================

从文件名中提取元数据（标题、作者、系列等）

支持多种命名格式：
- 《书名》- 作者.epub
- 书名 - 作者.epub  
- 书名_作者.epub
- 书名#作者.epub
- 书名-作者.epub
- 作者_书名.epub

支持从文件路径提取系列信息：
- Series/Book Title - Author.epub
- Author - Series Name #Book Number.epub
"""

import re
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ParsedFilename:
    """文件名解析结果"""
    title: str = ""
    author: str = ""
    series: str = ""
    series_index: str = "1.0"
    format: str = ""
    
    def is_valid(self) -> bool:
        """是否有效（至少有标题）"""
        return bool(self.title)


class FilenameParser:
    """
    文件名解析器
    
    支持多种常见的图书命名格式
    """
    
    # 命名模式（按优先级排序）
    PATTERNS = [
        # 《书名》- 作者
        (r'[《"](?P<title>[^》"]+)[》"]\s*[-–—]\s*(?P<author>.+)', 'title_first'),
        
        # 书名 - 作者
        (r'^(?P<title>.+?)\s*[-–—]\s*(?P<author>.+)$', 'title_first'),
        
        # 作者 - 书名
        (r'^(?P<author>.+?)\s*[-–—]\s*(?P<title>.+)$', 'author_first'),
        
        # 书名_作者
        (r'^(?P<title>[^_]+)_(?P<author>.+)$', 'title_first'),
        
        # 书名#作者
        (r'^(?P<title>[^#]+)#(?P<author>.+)$', 'title_first'),
        
        # 书名-作者（无空格）
        (r'^(?P<title>.+?)-(?P<author>.+)$', 'title_first'),
        
        # 系列/书名 - 作者
        (r'^(?P<series>.+?)[/\\](?P<title>[^_-]+)[_-](?P<author>.+)$', 'path_series'),
        
        # 作者 - 系列名 #序号
        (r'^(?P<author>.+?)\s*[-–—]\s*(?P<series>[^#]+)\s*#\s*(?P<series_index>\d+)\s*[-–—]\s*(?P<title>.+)$', 'series_format'),
        
        # 系列名 #序号 - 书名
        (r'^(?P<series>[^#]+)\s*#\s*(?P<series_index>\d+)\s*[-–—]\s*(?P<title>.+)$', 'series_number_first'),
    ]
    
    # 常见作者姓氏（用于判断作者名位置）
    COMMON_AUTHOR_PATTERNS = [
        r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$',  # 英文名
        r'^[\u4e00-\u9fa5]{2,4}$',  # 中文名 2-4 字
    ]
    
    def __init__(self):
        """初始化解析器"""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self._patterns = []
        for pattern, format_type in self.PATTERNS:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self._patterns.append((compiled, format_type))
            except re.error:
                pass
    
    def parse(self, file_path: str) -> ParsedFilename:
        """
        解析文件名
        
        Args:
            file_path: 文件路径或文件名
            
        Returns:
            ParsedFilename: 解析结果
        """
        # 获取文件名（不含路径和扩展名）
        path = Path(file_path)
        filename = path.stem
        
        # 尝试每种模式
        for pattern, format_type in self._patterns:
            match = pattern.match(filename)
            if match:
                result = self._create_result(match.groupdict(), format_type)
                if result.is_valid():
                    result.format = path.suffix.lower().strip('.')
                    return result
        
        # 无法解析，返回文件名作为标题
        return ParsedFilename(
            title=filename,
            format=path.suffix.lower().strip('.')
        )
    
    def _create_result(self, groups: dict, format_type: str) -> ParsedFilename:
        """根据匹配组创建结果"""
        result = ParsedFilename()
        
        # 清理标题
        if 'title' in groups and groups['title']:
            result.title = self._clean_title(groups['title'].strip())
        
        # 清理作者
        if 'author' in groups and groups['author']:
            result.author = self._clean_author(groups['author'].strip())
        
        # 提取系列
        if 'series' in groups and groups['series']:
            result.series = groups['series'].strip()
        
        # 提取系列序号
        if 'series_index' in groups and groups['series_index']:
            result.series_index = groups['series_index'].strip()
        
        # 根据格式类型调整作者/标题顺序
        if format_type == 'author_first':
            # 交换标题和作者
            result.title, result.author = result.author, result.title
        
        return result
    
    def _clean_title(self, title: str) -> str:
        """清理标题"""
        # 移除常见的前后缀
        title = re.sub(r'^\[\S+\]\s*', '', title)  # [格式]
        title = re.sub(r'\s*\(\S+\)$', '', title)  # (语言)
        title = re.sub(r'\s*【\S+】$', '', title)  # 【出版社】
        
        # 清理多余空格
        title = ' '.join(title.split())
        
        return title.strip()
    
    def _clean_author(self, author: str) -> str:
        """清理作者名"""
        # 移除括号内的内容（如出版社信息）
        author = re.sub(r'\s*\([^)]*\)', '', author)
        author = re.sub(r'\s*【[^】]*】', '', author)
        
        # 清理多余空格
        author = ' '.join(author.split())
        
        return author.strip()
    
    def parse_from_path(self, file_path: str) -> ParsedFilename:
        """
        从完整文件路径解析（包含系列信息）"""
        path = Path(file_path)
        
        # 首先尝试从完整路径提取系列信息
        parts = path.parts
        
        # 查找可能的系列目录
        series = ""
        for i, part in enumerate(parts[:-1]):
            # 跳过以字母/数字开头的普通目录
            if re.match(r'^[A-Za-z0-9]', part):
                continue
            # 找到可能的系列目录
            if not re.match(r'^\d+$', part):  # 跳过纯数字目录
                series = part
                break
        
        # 解析文件名
        result = self.parse(file_path)
        
        # 如果从路径找到系列但解析结果没有，则使用路径系列
        if series and not result.series:
            result.series = series
        
        return result


def parse_filename(file_path: str) -> ParsedFilename:
    """
    便捷函数：解析文件名
    
    Args:
        file_path: 文件路径
        
    Returns:
        ParsedFilename: 解析结果
    """
    parser = FilenameParser()
    return parser.parse(file_path)


def parse_author_from_filename(filename: str) -> str:
    """
    从文件名提取作者名（简单版本）
    
    Args:
        filename: 文件名
        
    Returns:
        str: 作者名
    """
    parsed = parse_filename(filename)
    return parsed.author


def parse_title_from_filename(filename: str) -> str:
    """
    从文件名提取书名（简单版本���
    
    Args:
        filename: 文件名
        
    Returns:
        str: 书名
    """
    parsed = parse_filename(filename)
    return parsed.title


# 测试
if __name__ == '__main__':
    test_cases = [
        '《三体》- 刘慈欣.epub',
        '书名 - 作者.txt',
        '作者_书名.pdf',
        '三体_刘慈欣.mobi',
        '系列名 #1 - 书名.azw3',
        '/path/to/系列/书名 - 作者.fb2',
    ]
    
    parser = FilenameParser()
    
    print("文件名解析测试：\n")
    for tc in test_cases:
        result = parser.parse(tc)
        print(f"输入: {tc}")
        print(f"  标题: {result.title}")
        print(f"  作者: {result.author}")
        print(f"  系列: {result.series}")
        print(f"  序号: {result.series_index}")
        print(f"  格式: {result.format}")
        print()