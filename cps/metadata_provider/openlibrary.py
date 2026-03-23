"""
T010: OpenLibrary 元数据提供者
===============================

功能：集成 OpenLibrary API 获取图书元数据

API 文档：https://openlibrary.org/dev/docs/api
"""

import logging
from typing import Optional, List

from .base_provider import (
    BaseMetadataProvider, 
    ExternalMetadata,
    MetadataProviderRegistry
)


logger = logging.getLogger(__name__)


class OpenLibraryProvider(BaseMetadataProvider):
    """
    OpenLibrary 元数据提供者
    
    支持：
    - 按书名/作者搜索
    - 按 ISBN 查询
    - 封面图片获取
    """
    
    PROVIDER_NAME = "OpenLibrary"
    SUPPORTED_COUNTRIES = ["US", "UK", "AU", "CA"]
    
    # API 基础 URL
    BASE_URL = "https://openlibrary.org"
    COVER_URL = "https://covers.openlibrary.org/b"
    
    def __init__(self, rate_limit: float = 5.0):
        super().__init__(rate_limit)
    
    def search(self, query: str, author: str = "", isbn: str = "") -> List[ExternalMetadata]:
        """
        搜索图书
        
        API: https://openlibrary.org/search.json?q={query}
        """
        results = []
        
        # 构建搜索查询
        search_query = query
        if author:
            search_query += f" {author}"
        if isbn:
            search_query = isbn
        
        try:
            params = {
                'q': search_query,
                'limit': 10,
                'fields': 'key,title,author_name,first_publish_year,publisher,isbn,cover_i,number_of_pages_median,subject,language'
            }
            
            data = self._http_get(f"{self.BASE_URL}/search.json", params)
            
            if 'docs' in data:
                for doc in data['docs']:
                    metadata = self._parse_search_result(doc)
                    if metadata:
                        results.append(metadata)
            
            self.logger.info(f"OpenLibrary 搜索: {query}, 找到 {len(results)} 条结果")
            
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
        
        return results
    
    def get_by_isbn(self, isbn: str) -> Optional[ExternalMetadata]:
        """
        根据 ISBN 获取元数据
        
        API: https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data
        """
        try:
            # 清理 ISBN
            isbn = isbn.replace('-', '').replace(' ', '')
            
            params = {
                'bibkeys': f"ISBN:{isbn}",
                'format': 'json',
                'jscmd': 'data'
            }
            
            data = self._http_get(f"{self.BASE_URL}/api/books", params)
            
            key = f"ISBN:{isbn}"
            if key in data:
                book_data = data[key]
                return self._parse_isbn_result(book_data, isbn)
            
            self.logger.info(f"OpenLibrary 未找到 ISBN: {isbn}")
            
        except Exception as e:
            self.logger.error(f"ISBN 查询失败: {e}")
        
        return None
    
    def _parse_search_result(self, doc: dict) -> Optional[ExternalMetadata]:
        """解析搜索结果"""
        try:
            metadata = ExternalMetadata()
            metadata.source = self.PROVIDER_NAME
            metadata.source_id = doc.get('key', '')
            metadata.confidence = 0.5  # 默认置信度
            
            # 标题
            if 'title' in doc:
                metadata.title = doc['title']
            
            # 作者
            if 'author_name' in doc:
                metadata.author = ', '.join(doc['author_name'][:3])  # 最多3个作者
            
            # 出版年
            if 'first_publish_year' in doc:
                metadata.pubdate = str(doc['first_publish_year'])
            
            # 出版商
            if 'publisher' in doc:
                publishers = doc['publisher']
                if isinstance(publishers, list) and publishers:
                    metadata.publisher = publishers[0]
                elif isinstance(publishers, str):
                    metadata.publisher = publishers
            
            # ISBN
            if 'isbn' in doc:
                isbns = doc['isbn']
                if isinstance(isbns, list) and isbns:
                    metadata.isbn = isbns[0]
            
            # 封面
            if 'cover_i' in doc:
                metadata.cover_url = f"{self.COVER_URL}/id/{doc['cover_i']}-M.jpg"
            
            # 页数
            if 'number_of_pages_median' in doc:
                metadata.tags = [f"pages:{int(doc['number_of_pages_median'])}"]
            
            # 主题/标签
            if 'subject' in doc:
                subjects = doc['subject']
                if isinstance(subjects, list):
                    metadata.tags = metadata.tags or []
                    metadata.tags.extend([s for s in subjects[:5] if isinstance(s, str)])
            
            # 语言
            if 'language' in doc:
                languages = doc['language']
                if isinstance(languages, list) and languages:
                    metadata.language = languages[0]
            
            return metadata
            
        except Exception as e:
            self.logger.warning(f"解析搜索结果失败: {e}")
            return None
    
    def _parse_isbn_result(self, data: dict, isbn: str) -> ExternalMetadata:
        """解析 ISBN 查询结果"""
        metadata = ExternalMetadata()
        metadata.source = self.PROVIDER_NAME
        metadata.source_id = data.get('key', '')
        metadata.isbn = isbn
        metadata.confidence = 0.9  # ISBN 查询置信度较高
        
        # 标题
        if 'title' in data:
            metadata.title = data['title']
        
        # 作者
        if 'authors' in data:
            authors = []
            for author in data['authors'][:3]:
                if isinstance(author, dict) and 'name' in author:
                    authors.append(author['name'])
            metadata.author = ', '.join(authors)
        
        # 描述
        if 'notes' in data:
            metadata.description = data['notes']
        elif 'excerpts' in data:
            excerpts = data['excerpts']
            if isinstance(excerpts, list) and excerpts:
                metadata.description = excerpts[0].get('text', '')
        
        # 出版商
        if 'publishers' in data:
            publishers = data['publishers']
            if isinstance(publishers, list) and publishers:
                metadata.publisher = publishers[0].get('name', '')
        
        # 出版日期
        if 'publish_date' in data:
            metadata.pubdate = data['publish_date']
        
        # 页数
        if 'number_of_pages' in data:
            metadata.tags = [f"pages:{data['number_of_pages']}"]
        
        # 封面
        if 'cover' in data:
            cover = data['cover']
            if 'medium' in cover:
                metadata.cover_url = cover['medium']
            elif 'small' in cover:
                metadata.cover_url = cover['small']
            elif 'large' in cover:
                metadata.cover_url = cover['large']
        
        # ISBN
        if 'identifiers' in data and 'isbn_13' in data['identifiers']:
            isbns = data['identifiers']['isbn_13']
            if isbns:
                metadata.isbn = isbns[0]
        
        return metadata
    
    def get_cover_url(self, isbn: str, size: str = 'M') -> str:
        """
        获取封面图片 URL
        
        Args:
            isbn: ISBN
            size: S/M/L
        """
        isbn = isbn.replace('-', '').replace(' ', '')
        return f"{self.COVER_URL}/isbn/{isbn}-{size}.jpg"


def get_openlibrary_provider() -> OpenLibraryProvider:
    """获取 OpenLibrary 提供者实例"""
    return OpenLibraryProvider()