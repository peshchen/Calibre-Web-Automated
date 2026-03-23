"""
T005: 数据库写入模块 - 图书仓储
=================================

功能：管理图书数据的持久化操作

主要功能：
- 添加图书（支持扫描模式）
- 更新图书
- 删除图书（软删）
- 路径查重
- 批量操作
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# 扫描模式常量
SCAN_MODE_IMPORT = 0  # 导入模式（原有方式）
SCAN_MODE_SCANNER = 1  # 扫描模式


@dataclass
class BookRecord:
    """图书记录数据类"""
    title: str
    author: str = ""
    author_sort: str = ""
    description: str = ""
    publisher: str = ""
    pubdate: str = ""
    isbn: str = ""
    language: str = "und"
    series: str = ""
    series_index: str = "1.0"
    tags: List[str] = None
    
    # 封面
    has_cover: bool = False
    
    # 文件信息
    file_path: str = ""  # 绝对路径
    file_format: str = ""
    file_size: int = 0
    
    # 扫描模式字段
    source_path: str = ""  # 源文件路径
    scan_mode: int = SCAN_MODE_SCANNER  # 默认为扫描模式
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class BookRepository:
    """
    图书仓储
    
    负责图书数据的数据库操作
    """
    
    def __init__(self, db_session: Session):
        """
        初始化仓储
        
        Args:
            db_session: SQLAlchemy 数据库会话
        """
        self.db = db_session
        self._ Books = None
    
    @property
    def Books(self):
        """获取 Books 模型类（延迟加载）"""
        if self._Books is None:
            from cps.db import Books
            self._Books = Books
        return self._Books
    
    def add_book(self, book: BookRecord) -> int:
        """
        添加新图书
        
        Args:
            book: 图书记录
            
        Returns:
            int: 新图书的 ID
        """
        try:
            # 创建图书记录
            now = datetime.now(timezone.utc)
            
            book_obj = self.Books(
                title=book.title,
                sort=book.title,
                author_sort=book.author_sort or book.author,
                timestamp=now,
                pubdate=now,
                series_index=book.series_index,
                last_modified=now,
                path=self._generate_book_path(book),
                has_cover=1 if book.has_cover else 0,
                uuid=self._generate_uuid()
            )
            
            self.db.add(book_obj)
            self.db.flush()  # 获取 ID
            
            book_id = book_obj.id
            
            # 添加作者关联
            if book.author:
                self._add_author(book_id, book.author)
            
            # 添加标签关联
            if book.tags:
                self._add_tags(book_id, book.tags)
            
            # 添加系列关联
            if book.series:
                self._add_series(book_id, book.series, book.series_index)
            
            # 添加发布商关联
            if book.publisher:
                self._add_publisher(book_id, book.publisher)
            
            # 添加扫描模式字段
            if book.source_path:
                self._update_scan_fields(book_id, book.source_path, book.scan_mode)
            
            self.db.commit()
            
            logger.info(f"添加图书成功: ID={book_id}, 标题={book.title}")
            return book_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"添加图书失败: {e}")
            raise
    
    def update_book(self, book_id: int, book: BookRecord) -> bool:
        """
        更新图书信息
        
        Args:
            book_id: 图书 ID
            book: 新的图书数据
            
        Returns:
            bool: 是否更新成功
        """
        try:
            book_obj = self.db.query(self.Books).filter(self.Books.id == book_id).first()
            
            if not book_obj:
                logger.warning(f"图书不存在: ID={book_id}")
                return False
            
            # 更新基本字段
            book_obj.title = book.title
            book_obj.sort = book.title
            book_obj.author_sort = book.author_sort or book.author
            book_obj.last_modified = datetime.now(timezone.utc)
            
            if book.description:
                self._update_description(book_id, book.description)
            
            # 更新封面标志
            if book.has_cover:
                book_obj.has_cover = 1
            
            # 更新扫描模式字段
            if book.source_path or book.scan_mode is not None:
                self._update_scan_fields(
                    book_id, 
                    book.source_path or book_obj.source_path,
                    book.scan_mode if book.scan_mode is not None else book_obj.scan_mode
                )
            
            # 更新作者
            if book.author:
                self._update_author(book_id, book.author)
            
            # 更新标签
            if book.tags:
                self._update_tags(book_id, book.tags)
            
            # 更新系列
            if book.series:
                self._update_series(book_id, book.series, book.series_index)
            
            # 更新发布商
            if book.publisher:
                self._update_publisher(book_id, book.publisher)
            
            self.db.commit()
            
            logger.info(f"更新图书成功: ID={book_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新图书失败: {e}")
            return False
    
    def delete_book(self, book_id: int, soft: bool = True) -> bool:
        """
        删除图书
        
        Args:
            book_id: 图书 ID
            soft: 是否软删（True=软删，False=硬删）
            
        Returns:
            bool: 是否删除成功
        """
        try:
            book_obj = self.db.query(self.Books).filter(self.Books.id == book_id).first()
            
            if not book_obj:
                logger.warning(f"图书不存在: ID={book_id}")
                return False
            
            if soft:
                # 软删：将标题标记为已删除
                book_obj.title = f"[已删除] {book_obj.title}"
                book_obj.last_modified = datetime.now(timezone.utc)
                logger.info(f"软删图书: ID={book_id}")
            else:
                # 硬删：实际删除记录
                # 注意：这会触发级联删除，删除关联的作者、标签等
                self.db.delete(book_obj)
                logger.info(f"硬删图书: ID={book_id}")
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除图书失败: {e}")
            return False
    
    def find_by_path(self, file_path: str) -> Optional[int]:
        """
        根据文件路径查找图书
        
        Args:
            file_path: 源文件绝对路径
            
        Returns:
            int: 图书 ID，或 None
        """
        from cps.db import Books
        
        book = self.db.query(Books).filter(Books.source_path == file_path).first()
        return book.id if book else None
    
    def find_duplicates(self, file_path: str) -> List[dict]:
        """
        查找重复的图书（相同源路径）
        
        Args:
            file_path: 文件路径
            
        Returns:
            list: 重复图书列表
        """
        from cps.db import Books
        
        books = self.db.query(Books).filter(
            Books.source_path == file_path
        ).all()
        
        return [
            {
                'id': b.id,
                'title': b.title,
                'source_path': b.source_path
            }
            for b in books
        ]
    
    def find_by_title_author(self, title: str, author: str) -> List[int]:
        """
        根据标题和作者查找图书
        
        Args:
            title: 书名
            author: 作者
            
        Returns:
            list: 匹配的图书 ID 列表
        """
        from cps.db import Books, Authors, books_authors_link
        
        query = self.db.query(Books).join(
            books_authors_link, Books.id == books_authors_link.c.book
        ).join(
            Authors, books_authors_link.c.author == Authors.id
        ).filter(
            Books.title == title,
            Authors.name == author
        )
        
        return [b.id for b in query.all()]
    
    def get_book(self, book_id: int) -> Optional[dict]:
        """
        获取图书详情
        
        Args:
            book_id: 图书 ID
            
        Returns:
            dict: 图书信息，或 None
        """
        from cps.db import Books
        
        book = self.db.query(Books).filter(Books.id == book_id).first()
        
        if not book:
            return None
        
        return {
            'id': book.id,
            'title': book.title,
            'sort': book.sort,
            'author_sort': book.author_sort,
            'path': book.path,
            'has_cover': book.has_cover,
            'uuid': book.uuid,
            'source_path': getattr(book, 'source_path', ''),
            'scan_mode': getattr(book, 'scan_mode', 0),
            'timestamp': book.timestamp,
            'last_modified': book.last_modified
        }
    
    def list_scanner_books(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """
        获取扫描模式的图书列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            list: 图书列表
        """
        from cps.db import Books
        
        books = self.db.query(Books).filter(
            Books.scan_mode == SCAN_MODE_SCANNER
        ).offset(offset).limit(limit).all()
        
        return [
            {
                'id': b.id,
                'title': b.title,
                'source_path': b.source_path,
                'has_cover': b.has_cover
            }
            for b in books
        ]
    
    def _generate_book_path(self, book: BookRecord) -> str:
        """
        生成 Calibre 库中的图书路径
        
        扫描模式图书：使用源文件的相对路径
        """
        # 扫描模式：使用源文件的绝对路径（后续可以在配置中设置相对路径）
        # 这里返回一个基于源文件名的相对路径
        import hashlib
        
        # 使用 title + author 生成唯一目录名
        key = f"{book.title}:{book.author}".encode()
        dir_hash = hashlib.sha1(key).hexdigest()[:8]
        
        filename = f"{book.title}.{book.file_format}"
        
        # 返回相对路径格式：hash/title.format
        return f"{dir_hash}/{filename}"
    
    def _generate_uuid(self) -> str:
        """生成 UUID"""
        import uuid
        return str(uuid.uuid4())
    
    def _add_author(self, book_id: int, author_name: str):
        """添加作者关联"""
        from cps.db import Authors, books_authors_link
        
        # 查找或创建作者
        author = self.db.query(Authors).filter(Authors.name == author_name).first()
        
        if not author:
            author = Authors(name=author_name, sort=author_name)
            self.db.add(author)
            self.db.flush()
        
        # 关联
        link = books_authors_link.insert().values(book=book_id, author=author.id)
        self.db.execute(link)
    
    def _add_tags(self, book_id: int, tags: List[str]):
        """添加标签关联"""
        from cps.db import Tags, books_tags_link
        
        for tag_name in tags:
            tag = self.db.query(Tags).filter(Tags.name == tag_name).first()
            
            if not tag:
                tag = Tags(name=tag_name)
                self.db.add(tag)
                self.db.flush()
            
            link = books_tags_link.insert().values(book=book_id, tag=tag.id)
            self.db.execute(link)
    
    def _add_series(self, book_id: int, series_name: str, series_index: str = "1.0"):
        """添加系列关联"""
        from cps.db import Series, books_series_link
        
        series = self.db.query(Series).filter(Series.name == series_name).first()
        
        if not series:
            series = Series(name=series_name)
            self.db.add(series)
            self.db.flush()
        
        link = books_series_link.insert().values(
            book=book_id, series=series.id, series_index=float(series_index)
        )
        self.db.execute(link)
    
    def _add_publisher(self, book_id: int, publisher_name: str):
        """添加发布商关联"""
        from cps.db import Publishers, books_publishers_link
        
        publisher = self.db.query(Publishers).filter(
            Publishers.name == publisher_name
        ).first()
        
        if not publisher:
            publisher = Publishers(name=publisher_name)
            self.db.add(publisher)
            self.db.flush()
        
        link = books_publishers_link.insert().values(book=book_id, publisher=publisher.id)
        self.db.execute(link)
    
    def _update_scan_fields(self, book_id: int, source_path: str, scan_mode: int):
        """更新扫描模式字段"""
        # 直接执行 SQL 更新（因为这些是新增的列）
        from sqlalchemy import text
        
        self.db.execute(
            text("UPDATE books SET source_path = :source_path, scan_mode = :scan_mode WHERE id = :book_id"),
            {'source_path': source_path, 'scan_mode': scan_mode, 'book_id': book_id}
        )
    
    def _update_description(self, book_id: int, description: str):
        """更新描述"""
        from cps.db import Comments
        
        # 删除旧描述
        self.db.query(Comments).filter(Comments.book == book_id).delete()
        
        # 添加新描述
        comment = Comments(book=book_id, text=description)
        self.db.add(comment)
    
    def _update_author(self, book_id: int, author_name: str):
        """更新作者"""
        from cps.db import books_authors_link
        
        # 删除旧关联
        self.db.execute(books_authors_link.delete().where(books_authors_link.c.book == book_id))
        
        # 添加新关联
        self._add_author(book_id, author_name)
    
    def _update_tags(self, book_id: int, tags: List[str]):
        """更新标签"""
        from cps.db import books_tags_link
        
        # 删除旧关联
        self.db.execute(books_tags_link.delete().where(books_tags_link.c.book == book_id))
        
        # 添加新关联
        self._add_tags(book_id, tags)
    
    def _update_series(self, book_id: int, series_name: str, series_index: str):
        """更新系列"""
        from cps.db import books_series_link
        
        # 删除旧关联
        self.db.execute(books_series_link.delete().where(books_series_link.c.book == book_id))
        
        # 添加新关联
        self._add_series(book_id, series_name, series_index)
    
    def _update_publisher(self, book_id: int, publisher_name: str):
        """更新发布商"""
        from cps.db import books_publishers_link
        
        # 删除旧关联
        self.db.execute(books_publishers_link.delete().where(books_publishers_link.c.book == book_id))
        
        # 添加新关联
        self._add_publisher(book_id, publisher_name)


def create_repository(db_session: Session) -> BookRepository:
    """
    创建图书仓储实例
    
    Args:
        db_session: 数据库会话
        
    Returns:
        BookRepository: 仓储实例
    """
    return BookRepository(db_session)