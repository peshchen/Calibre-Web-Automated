"""
T003: PDF 解析器
================

专门处理 PDF 格式的图书解析器
"""

import os
import logging
from pathlib import Path
from typing import Optional

from .base_resolver import BaseResolver, BookMetadata


logger = logging.getLogger(__name__)


class PdfResolver(BaseResolver):
    """
    PDF 解析器
    
    支持格式：pdf
    """
    
    SUPPORTED_EXTENSIONS = ['pdf']
    
    def can_resolve(self, file_path: str) -> bool:
        """检查是否能处理此文件"""
        ext = self.get_file_extension(file_path)
        return ext.lower() == 'pdf'
    
    def resolve(self, file_path: str) -> Optional[BookMetadata]:
        """
        解析 PDF 文件，提取元数据
        
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
            metadata.file_format = 'pdf'
            metadata.file_size = os.path.getsize(file_path)
            
            # 尝试使用 pypdf（推荐）
            try:
                from pypdf import PdfReader
                metadata = self._extract_with_pypdf(file_path, metadata)
            except ImportError:
                # 尝试使用 pdfminer.six
                try:
                    from pdfminer.high_level import extract_metadata
                    from pdfminer.pdfparser import PDFParser
                    from pdfminer.pdfdocument import PDFDocument
                    metadata = self._extract_with_pdfminer(file_path, metadata)
                except ImportError:
                    self.logger.warning("未安装 pypdf 或 pdfminer，将使用文件名解析")
                    metadata = self._extract_from_filename(file_path, metadata)
            
            # 封面提取
            if not metadata.cover_image:
                metadata.cover_image = self._extract_cover(file_path)
            
            # 如果没有标题，使用文件名
            if not metadata.title:
                metadata.title = Path(file_path).stem
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"解析 PDF 失败: {file_path}, 错误: {e}")
            return None
    
    def _extract_with_pypdf(self, file_path: str, metadata: BookMetadata) -> BookMetadata:
        """使用 pypdf 提取元数据"""
        from pypdf import PdfReader
        
        try:
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                
                # 获取元数据
                if reader.metadata:
                    # 标题
                    title = reader.metadata.get('/Title')
                    if title:
                        metadata.title = title.strip()
                    
                    # 作者
                    author = reader.metadata.get('/Author')
                    if author:
                        metadata.author = author.strip()
                        metadata.author_sort = metadata.author
                    
                    # 主题/描述
                    subject = reader.metadata.get('/Subject')
                    if subject:
                        metadata.description = subject.strip()
                    
                    # 出版商
                    creator = reader.metadata.get('/Creator')
                    producer = reader.metadata.get('/Producer')
                    metadata.publisher = producer.strip() if producer else (creator.strip() if creator else "")
                    
                    # 出版日期
                    creation_date = reader.metadata.get('/CreationDate')
                    if creation_date:
                        metadata.pubdate = self._parse_pdf_date(creation_date)
                    
                    # ISBN / 识别符
                    # PDF 元数据中通常没有标准 ISBN 字段
                
                # 页数（可用于估算）
                metadata.tags = [f"pages:{len(reader.pages)}"]
                
        except Exception as e:
            self.logger.warning(f"pypdf 解析失败: {e}")
            metadata = self._extract_from_filename(file_path, metadata)
        
        return metadata
    
    def _extract_with_pdfminer(self, file_path: str, metadata: BookMetadata) -> BookMetadata:
        """使用 pdfminer 提取元数据"""
        try:
            from pdfminer.pdfparser import PDFParser
            from pdfminer.pdfdocument import PDFDocument
            
            with open(file_path, 'rb') as f:
                parser = PDFParser(f)
                doc = PDFDocument(parser)
                
                if doc.info:
                    info = doc.info[0] if doc.info else {}
                    
                    # 标题
                    if '/Title' in info:
                        title = info['/Title']
                        if title:
                            metadata.title = str(title).strip()
                    
                    # 作者
                    if '/Author' in info:
                        author = info['/Author']
                        if author:
                            metadata.author = str(author).strip()
                            metadata.author_sort = metadata.author
                    
                    # 主题
                    if '/Subject' in info:
                        subject = info['/Subject']
                        if subject:
                            metadata.description = str(subject).strip()
                    
                    # 出版商
                    if '/Creator' in info:
                        creator = info['/Creator']
                        if creator:
                            metadata.publisher = str(creator).strip()
                    
                    # 创建日期
                    if '/CreationDate' in info:
                        date_str = info['/CreationDate']
                        if date_str:
                            metadata.pubdate = self._parse_pdf_date(str(date_str))
                
        except Exception as e:
            self.logger.warning(f"pdfminer 解析失败: {e}")
            metadata = self._extract_from_filename(file_path, metadata)
        
        return metadata
    
    def _extract_cover(self, file_path: str) -> Optional[bytes]:
        """提取 PDF ��面（首页图片）"""
        try:
            from pypdf import PdfReader
            
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                
                # 获取第一页
                if len(reader.pages) > 0:
                    first_page = reader.pages[0]
                    
                    # 尝试提取图片
                    # 注意：pypdf 提取图片比较复杂，这里简化处理
                    # 实际可能需要使用 PyMuPDF (fitz)
                    pass
                    
        except Exception as e:
            self.logger.debug(f"PDF 封面提取失败: {e}")
        
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
        
        # 默认
        metadata.title = filename
        return metadata
    
    def _parse_pdf_date(self, date_str: str) -> Optional[str]:
        """解析 PDF 日期格式（D:YYYYMMDDHHmmSS）"""
        from datetime import datetime
        
        if not date_str:
            return None
        
        # 清理日期字符串
        date_str = date_str.strip()
        
        # 处理 D: 格式
        if date_str.startswith('D:'):
            date_str = date_str[2:]
        
        # 尝试提取日期部分
        try:
            if len(date_str) >= 8:
                year = int(date_str[0:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            pass
        
        return None


# 注册解析器
def _register_resolver():
    """注册此解析器"""
    from .base_resolver import get_resolver_registry
    registry = get_resolver_registry()
    registry.register(PdfResolver())


_register_resolver()