"""
T010: Google Books 元数据提供者
================================

功能：集成 Google Books API 获取图书元数据

API 文档：https://developers.google.com/books/docs/v1/using
"""

import logging
from typing import Optional, List

from .base_provider import (
    BaseMetadataProvider, 
    ExternalMetadata
)


logger = logging.getLogger(__name__)


class GoogleBooksProvider(BaseMetadataProvider):
    """
    Google Books 元数据提供者
    
    支持：
    - 按书名/作者搜索
    - 按 ISBN 查询
    - 封面图片获取
    """
    
    PROVIDER_NAME = "GoogleBooks"
    SUPPORTED_COUNTRIES = []
    
    # API 基础 URL
    BASE_URL = "https://www.googleapis.com/books/v1"
    
    def __init__(self, api_key: str = "", rate_limit: float = 5.0):
        """
        初始化提供者
        
        Args:
            api_key: Google Books API 密钥（可选）
        """
        super().__init__(rate_limit)
        self.api_key = api_key
    
    def search(self, query: str, author: str = "", isbn: str = "") -> List[ExternalMetadata]:
        """
        搜索图书
        
        API: https://www.googleapis.com/books/v1/volumes?q={query}
        """
        results = []
        
        # 构建搜索查询
        search_query = query
        if author:
            search_query += f"+inauthor:{author}"
        if isbn:
            search_query = f"isbn:{isbn}"
        
        try:
            params = {
                'q': search_query,
                'maxResults': 10,
                'fields': 'items(id,volumeInfo(title,authors,publishedDate,publisher,description,pageCount,imageLinks,industryIdentifiers,categories,language))'
            }
            
            if self.api_key:
                params['key'] = self.api_key
            
            data = self._http_get(f"{self.BASE_URL}/volumes", params)
            
            if 'items' in data:
                for item in data['items']:
                    metadata = self._parse_search_result(item)
                    if metadata:
                        results.append(metadata)
            
            self.logger.info(f"Google Books 搜索: {query}, 找到 {len(results)} 条结果")
            
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
        
        return results
    
    def get_by_isbn(self, isbn: str) -> Optional[ExternalMetadata]:
        """
        根据 ISBN 获取元数据
        
        API: https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}
        """
        results = self.search("", "", isbn)
        return results[0] if results else None
    
    def _parse_search_result(self, item: dict) -> Optional[ExternalMetadata]:
        """解析搜索结果"""
        try:
            volume_info = item.get('volumeInfo', {})
            
            metadata = ExternalMetadata()
            metadata.source = self.PROVIDER_NAME
            metadata.source_id = item.get('id', '')
            metadata.confidence = 0.5
            
            # 标题
            if 'title' in volume_info:
                metadata.title = volume_info['title']
            
            # 作者
            if 'authors' in volume_info:
                metadata.author = ', '.join(volume_info['authors'][:3])
            
            # 出版日期
            if 'publishedDate' in volume_info:
                date_str = volume_info['publishedDate']
                # 标准化日期格式
                if len(date_str) == 4:  # 只有年
                    metadata.pubdate = date_str
                elif len(date_str) == 7:  # 年-月
                    metadata.pubdate = date_str + "-01"
                else:
                    metadata.pubdate = date_str[:10]  # 年-月-日
            
            # 出版商
            if 'publisher' in volume_info:
                metadata.publisher = volume_info['publisher']
            
            # 描述
            if 'description' in volume_info:
                metadata.description = volume_info['description']
            
            # 页数
            if 'pageCount' in volume_info:
                metadata.tags = [f"pages:{volume_info['pageCount']}"]
            
            # 封面
            if 'imageLinks' in volume_info:
                image_links = volume_info['imageLinks']
                metadata.cover_url = (
                    image_links.get('thumbnail') or 
                    image_links.get('smallThumbnail', '')
                ).replace('http://', 'https://')
            
            # ISBN
            if 'industryIdentifiers' in volume_info:
                for identifier in volume_info['industryIdentifiers']:
                    if identifier.get('type') in ('ISBN_13', 'ISBN_10'):
                        metadata.isbn = identifier.get('identifier', '')
                        break
            
            # 分类/标签
            if 'categories' in volume_info:
                metadata.tags = metadata.tags or []
                metadata.tags.extend(volume_info['categories'][:5])
            
            # 语言
            if 'language' in volume_info:
                metadata.language = volume_info['language']
            
            return metadata
            
        except Exception as e:
            self.logger.warning(f"解析搜索结果失败: {e}")
            return None


def get_google_books_provider(api_key: str = "") -> GoogleBooksProvider:
    """获取 Google Books 提供者实例"""
    return GoogleBooksProvider(api_key)