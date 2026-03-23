"""
T003: 通用图书解析器
====================

解析常见的电子书格式（epub, mobi, azw3 等）

使用现有 CWA 的 uploader.py 元数据提取逻辑
"""

import os
import logging
from pathlib import Path
from typing import Optional

from .base_resolver import BaseResolver, BookMetadata, get_resolver_registry


logger = logging.getLogger(__name__)


class BookResolver(BaseResolver):
    """
    通用图书解析器
    
    支持格式：epub, mobi, azw3, azw, fb2, lit, pdb, chm
    """
    
    SUPPORTED_EXTENSIONS = [
        'epub', 'mobi', 'azw3', 'azw', 
        'fb2', 'lit', 'pdb', 'chm'
    ]
    
    def can_resolve(self, file_path: str) -> bool:
        """检查是否能处理此文件"""
        ext = self.get_file_extension(file_path)
        return ext.lower() in [e.lower() for e in self.SUPPORTED_EXTENSIONS]
    
    def resolve(self, file_path: str) -> Optional[BookMetadata]:
        """
        解析电子书文件，提取元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            BookMetadata: 提取的元数据
        """
        if not os.path.exists(file_path):
            self.logger.warning(f"文件不存在: {file_path}")
            return None
        
        try:
            # 使用 CWA 现有 uploader 逻辑提取元数据
            metadata = self._extract_metadata(file_path)
            
            if metadata:
                metadata.file_path = file_path
                metadata.file_format = self.get_file_extension(file_path)
                metadata.file_size = os.path.getsize(file_path)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"解析文件失败: {file_path}, 错误: {e}")
            return None
    
    def _extract_metadata(self, file_path: str) -> Optional[BookMetadata]:
        """
        提取元数据的核心逻辑
        
        复用 cps/uploader.py 的元数据提取逻辑
        """
        metadata = BookMetadata()
        file_ext = self.get_file_extension(file_path)
        
        # 尝试多种提取方法
        if file_ext == 'epub':
            return self._extract_epub_metadata(file_path, metadata)
        elif file_ext == 'pdf':
            return self._extract_pdf_metadata(file_path, metadata)
        elif file_ext in ('mobi', 'azw3', 'azw'):
            return self._extract_mobi_metadata(file_path, metadata)
        elif file_ext == 'fb2':
            return self._extract_fb2_metadata(file_path, metadata)
        else:
            # 通用处理：尝试从文件名提取
            return self._extract_from_filename(file_path, metadata)
    
    def _extract_epub_metadata(self, file_path: str, metadata: BookMetadata) -> Optional[BookMetadata]:
        """提取 EPUB 元数据"""
        import zipfile
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # 查找 container.xml 确定内容文件位置
                container_path = 'META-INF/container.xml'
                if container_path not in zf.namelist():
                    return self._extract_from_filename(file_path, metadata)
                
                # 读取 container.xml
                with zf.open(container_path) as f:
                    import xml.etree.ElementTree as ET
                    content = f.read()
                    root = ET.fromstring(content)
                    
                    # 查找 rootfile
                    ns = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                    rootfile = root.find('.//c:rootfile', ns)
                    if rootfile is None:
                        # 尝试不使用命名空间
                        rootfile = root.find('.//rootfile')
                    
                    if rootfile is not None:
                        opf_path = rootfile.get('full-path')
                        if opf_path:
                            return self._extract_from_opf(file_path, opf_path, metadata)
        
        except Exception as e:
            self.logger.warning(f"EPUB 解析失败: {file_path}, {e}")
        
        return self._extract_from_filename(file_path, metadata)
    
    def _extract_from_opf(self, file_path: str, opf_path: str, metadata: BookMetadata) -> Optional[BookMetadata]:
        """从 OPF 文件提取元数据"""
        import zipfile
        import re
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # 获取 OPF 文件所在目录
                opf_dir = os.path.dirname(opf_path)
                
                with zf.open(opf_path) as f:
                    content = f.read().decode('utf-8', errors='ignore')
                
                # 解析元数据
                # 标题
                title_match = re.search(r'<dc:title[^>]*>([^<]+)</dc:title>', content, re.I)
                if not title_match:
                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.I)
                if title_match:
                    metadata.title = title_match.group(1).strip()
                
                # 作者
                author_match = re.search(r'<dc:creator[^>]*>([^<]+)</dc:creator>', content, re.I)
                if not author_match:
                    author_match = re.search(r'<creator[^>]*>([^<]+)</creator>', content, re.I)
                if author_match:
                    metadata.author = author_match.group(1).strip()
                    metadata.author_sort = metadata.author
                
                # 描述
                desc_match = re.search(r'<dc:description[^>]*>([^<]+)</dc:description>', content, re.I)
                if not desc_match:
                    desc_match = re.search(r'<description[^>]*>([^<]+)</description>', content, re.I)
                if desc_match:
                    metadata.description = desc_match.group(1).strip()
                
                # 出版商
                pub_match = re.search(r'<dc:publisher[^>]*>([^<]+)</dc:publisher>', content, re.I)
                if pub_match:
                    metadata.publisher = pub_match.group(1).strip()
                
                # 出版日期
                date_match = re.search(r'<dc:date[^>]*>([^<]+)</dc:date>', content, re.I)
                if date_match:
                    metadata.pubdate = self._parse_date(date_match.group(1).strip())
                
                # 语言
                lang_match = re.search(r'<dc:language[^>]*>([^<]+)</dc:language>', content, re.I)
                if lang_match:
                    metadata.language = lang_match.group(1).strip()
                
                # ISBN
                isbn_match = re.search(r'<dc:identifier[^>]*>([^<]+)</dc:identifier>', content, re.I)
                if isbn_match:
                    metadata.isbn = isbn_match.group(1).strip()
                
                # 封面
                cover_match = re.search(r'<meta[^>]*name=["\']cover["\'][^>]*content=["\']([^"\']+)["\']', content, re.I)
                if cover_match:
                    cover_id = cover_match.group(1)
                    # 查找封面对应的 item
                    cover_pattern = rf'<item[^>]*id=["\'{cover_id}["\'][^>]*href=["\']([^"\']+)["\']'
                    href_match = re.search(cover_pattern, content, re.I)
                    if href_match:
                        cover_path = os.path.join(opf_dir, href_match.group(1))
                        metadata.cover_image = self._extract_cover_from_archive(file_path, [opf_path.split('/')[0] if '/' in opf_path else ''])
                        # 这里简化处理，实际需要正确读取
                
                # 如果没有从 OPF 提取到标题，使用文件名
                if not metadata.title:
                    metadata.title = Path(file_path).stem
        
        except Exception as e:
            self.logger.warning(f"OPF 解析失败: {file_path}, {e}")
        
        return metadata
    
    def _extract_pdf_metadata(self, file_path: str, metadata: BookMetadata) -> Optional[BookMetadata]:
        """提取 PDF 元数据（使用 PyPDF2 或 pdfminer）"""
        # 简化实现：先尝试从文件名提取
        metadata = self._extract_from_filename(file_path, metadata)
        
        # 尝试使用 pypdf（如果可用）
        try:
            from pypdf import PdfReader
            
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                
                # 获取元数据
                if reader.metadata:
                    if not metadata.title and reader.metadata.get('/Title'):
                        metadata.title = reader.metadata.get('/Title').strip()
                    
                    if not metadata.author and reader.metadata.get('/Author'):
                        metadata.author = reader.metadata.get('/Author').strip()
                    
                    if not metadata.publisher and reader.metadata.get('/Producer'):
                        metadata.publisher = reader.metadata.get('/Producer').strip()
                    
                    if not metadata.pubdate and reader.metadata.get('/CreationDate'):
                        # PDF 日期格式通常是 D:YYYYMMDDHHmmSS
                        date_str = reader.metadata.get('/CreationDate', '')
                        if date_str.startswith('D:'):
                            date_str = date_str[2:8]
                            try:
                                metadata.pubdate = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                            except:
                                pass
                
                # 提取封面（第一页的图片）
                if reader.metadata and not metadata.cover_image:
                    # 尝试提取封面图片
                    pass
                    
        except ImportError:
            self.logger.debug("pypdf 未安装，使用文件名解析")
        except Exception as e:
            self.logger.warning(f"PDF 解析失败: {file_path}, {e}")
        
        return metadata
    
    def _extract_mobi_metadata(self, file_path: str, metadata: BookMetadata) -> Optional[BookMetadata]:
        """提取 MOBI/AZW3 元数据"""
        # MOBI 格式解析比较复杂，这里简化处理
        # 实际可以用 python-mobi 或 mobi
        metadata = self._extract_from_filename(file_path, metadata)
        
        # 尝试使用 python-mobi（如果可用）
        try:
            import mobi
            
            # 提取元数据
            # 注意：这个库可能需要单独安装
            # metadata = mobi.extract_metadata(file_path)
            pass
            
        except ImportError:
            self.logger.debug("mobi 库未安装，使用文件名解析")
        except Exception as e:
            self.logger.warning(f"MOBI 解析失败: {file_path}, {e}")
        
        return metadata
    
    def _extract_fb2_metadata(self, file_path: str, metadata: BookMetadata) -> Optional[BookMetadata]:
        """提取 FB2 元数据"""
        import xml.etree.ElementTree as ET
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # FB2 命名空间
            ns = {'fb': 'http://www.gribuser.ru/xml/fictionbook/2.0'}
            
            # 标题
            title_elem = root.find('.//fb:book-title', ns)
            if title_elem is not None:
                metadata.title = title_elem.text or ""
            
            # 作者
            for author in root.findall('.//fb:author', ns):
                first_name = author.find('.//fb:first-name', ns)
                last_name = author.find('.//fb:last-name', ns)
                
                parts = []
                if first_name is not None and first_name.text:
                    parts.append(first_name.text)
                if last_name is not None and last_name.text:
                    parts.append(last_name.text)
                
                if parts:
                    if metadata.author:
                        metadata.author += ", "
                    metadata.author += " ".join(parts)
            
            # 描述
            desc_elem = root.find('.//fb:annotation', ns)
            if desc_elem is not None:
                metadata.description = ''.join(desc_elem.itertext()).strip()
            
            # 出版商
            pub_elem = root.find('.//fb:publisher', ns)
            if pub_elem is not None and pub_elem.text:
                metadata.publisher = pub_elem.text
            
            # 出版日期
            date_elem = root.find('.//fb:date', ns)
            if date_elem is not None and date_elem.text:
                metadata.pubdate = self._parse_date(date_elem.text)
            
            # ISBN
            isbn_elem = root.find('.//fb:isbn', ns)
            if isbn_elem is not None and isbn_elem.text:
                metadata.isbn = isbn_elem.text
            
            if not metadata.title:
                metadata.title = Path(file_path).stem
                
        except Exception as e:
            self.logger.warning(f"FB2 解析失败: {file_path}, {e}")
            metadata = self._extract_from_filename(file_path, metadata)
        
        return metadata
    
    def _extract_from_filename(self, file_path: str, metadata: BookMetadata) -> BookMetadata:
        """
        从文件名解析元数据
        
        支持格式：
        - 《书名》- 作者.epub
        - 书名 - 作者.epub
        - 书名_作者.epub
        - 书名.epub
        """
        import re
        
        filename = Path(file_path).stem
        
        # 移除文件扩展名
        # filename 已经是 stem，不含扩展名
        
        # 尝试多种命名模式
        
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
            
            # 检查哪个是标题（通常标题更长）
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
        
        # 模式4: 只使用文件名作为标题
        metadata.title = filename
        return metadata
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """解析日期"""
        from datetime import datetime
        
        if not date_str:
            return None
        
        # 清理日期字符串
        date_str = date_str.strip()
        
        # 尝试多种格式
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y-%m',
            '%Y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
    
    def _extract_cover_from_archive(self, file_path: str, archive_extensions: list[str]) -> Optional[bytes]:
        """从压缩包提取封面"""
        return super()._extract_cover_from_archive(file_path, archive_extensions)


# 注册解析器
def _register_resolver():
    """注册此解析器到全局注册表"""
    registry = get_resolver_registry()
    registry.register(BookResolver())


# 自动注册
_register_resolver()