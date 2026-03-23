#!/usr/bin/env python3
"""
T001: 数据库扩展 - 扫描模式字段迁移脚本
============================================

任务：为 Calibre-Web-Automated 添加扫描模式所需数据库字段

迁移内容：
1. books 表添加 source_path 字段（源文件绝对路径）
2. books 表添加 scan_mode 字段（0=导入模式, 1=扫描模式）
3. 创建 scan_history 表记录扫描历史

执行方式：
    python scripts/migrations/001_add_scanner_fields.py

回滚方式：
    python scripts/migrations/001_rollback.py
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def get_db_path() -> str:
    """获取数据库路径"""
    # 优先使用环境变量
    db_path = os.environ.get('CWA_DB_PATH')
    if db_path:
        return db_path
    
    # 默认路径：项目目录下的 library.db
    default_db = os.path.join(project_root, 'library.db')
    if os.path.exists(default_db):
        return default_db
    
    # 检查 docker-compose 中的配置
    dirs_json = os.path.join(project_root, 'dirs.json')
    if os.path.exists(dirs_json):
        import json
        with open(dirs_json, 'r') as f:
            dirs = json.load(f)
            if 'config' in dirs:
                return dirs['config'].get('db_path', default_db)
    
    return default_db


def backup_database(db_path: str) -> str:
    """备份数据库"""
    if not os.path.exists(db_path):
        print(f"⚠️ 数据库文件不存在: {db_path}")
        return ""
    
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✅ 数据库已备份到: {backup_path}")
    return backup_path


def migrate_up(db_path: str) -> bool:
    """执行迁移（添加字段）"""
    print(f"\n📦 连接到数据库: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # T001.1: 添加 source_path 字段到 books 表
        print("\n🔧 T001.1: 添加 source_path 字段...")
        cursor.execute("PRAGMA table_info(books)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'source_path' not in columns:
            cursor.execute("ALTER TABLE books ADD COLUMN source_path TEXT")
            print("   ✅ source_path 字段已添加")
        else:
            print("   ℹ️ source_path 字段已存在，跳过")
        
        # 添加索引提升查询性能
        print("   🔍 创建 source_path 索引...")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_source_path ON books(source_path)")
            print("   ✅ 索引创建成功")
        except sqlite3.OperationalError as e:
            print(f"   ⚠️ 索引创建失败: {e}")
        
        # T001.2: 添加 scan_mode 字段到 books 表
        print("\n🔧 T001.2: 添加 scan_mode 字段...")
        if 'scan_mode' not in columns:
            cursor.execute("ALTER TABLE books ADD COLUMN scan_mode INTEGER DEFAULT 0")
            print("   ✅ scan_mode 字段已添加（默认值为 0，表示导入模式）")
        else:
            print("   ℹ️ scan_mode 字段已存在，跳过")
        
        # T001.3: 创建 scan_history 表
        print("\n🔧 T001.3: 创建 scan_history 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                scan_type TEXT NOT NULL,
                scan_directory TEXT,
                total_files INTEGER DEFAULT 0,
                books_added INTEGER DEFAULT 0,
                books_updated INTEGER DEFAULT 0,
                books_warning INTEGER DEFAULT 0,
                books_error INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_by TEXT
            )
        """)
        print("   ✅ scan_history 表已创建")
        
        # 创建索引
        print("   🔍 创建 scan_history 索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_scan_time ON scan_history(scan_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_status ON scan_history(status)")
        print("   ✅ 索引创建成功")
        
        conn.commit()
        print("\n✅ 迁移完成！")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {e}")
        return False
        
    finally:
        conn.close()


def migrate_down(db_path: str) -> bool:
    """执行回滚（移除字段）"""
    print(f"\n📦 连接到数据库: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 注意：SQLite 不支持直接删除列
        # 这里我们提供一个重建表的回滚方案
        
        print("\n⚠️ 警告：SQLite 不支持直接删除列")
        print("   回滚方案：创建新表并复制数据（不包含新字段）")
        
        # 获取现有表结构
        cursor.execute("PRAGMA table_info(books)")
        old_columns = [col[1] for col in cursor.fetchall()]
        
        # 要保留的列（排除新增的扫描字段）
        keep_columns = [col for col in old_columns if col not in ('source_path', 'scan_mode')]
        
        # 创建临时表
        print("\n🔧 创建临时表...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS books_backup (
                {', '.join([f'{col} TEXT' if col != 'id' else 'INTEGER PRIMARY KEY' for col in keep_columns])}
            )
        """)
        
        # 复制数据
        print("   复制数据到临时表...")
        placeholders = ', '.join(['?' for _ in keep_columns])
        cursor.execute(f"INSERT INTO books_backup ({', '.join(keep_columns)}) SELECT {', '.join(keep_columns)} FROM books")
        
        # 删除原表
        print("   删除原表...")
        cursor.execute("DROP TABLE books")
        
        # 重命名临时表
        print("   重命名表...")
        cursor.execute(f"RENAME TABLE books_backup TO books")
        
        # 重建索引（简化处理）
        print("   ℹ️ 索引需要在实际使用中重建")
        
        # 删除 scan_history 表
        print("\n🔧 删除 scan_history 表...")
        cursor.execute("DROP TABLE IF EXISTS scan_history")
        
        conn.commit()
        print("\n✅ 回滚完成！")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 回滚失败: {e}")
        return False
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='T001: 数据库扩展迁移脚本')
    parser.add_argument('--backup', action='store_true', default=True,
                        help='执行前自动备份数据库（默认开启）')
    parser.add_argument('--no-backup', action='store_true',
                        help='跳过数据库备份')
    parser.add_argument('--rollback', action='store_true',
                        help='执行回滚操作')
    parser.add_argument('--db-path', type=str,
                        help='指定数据库路径（可选）')
    
    args = parser.parse_args()
    
    # 获取数据库路径
    db_path = args.db_path if args.db_path else get_db_path()
    
    print("=" * 60)
    print("T001: 数据库扩展 - 扫描模式字段迁移")
    print("=" * 60)
    print(f"数据库路径: {db_path}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查数据库是否存在
    if not os.path.exists(db_path):
        print(f"\n❌ 错误：数据库文件不存在: {db_path}")
        print("\n💡 提示：")
        print("   1. 如果是新部署，需要先初始化数据库")
        print("   2. 可以通过设置环境变量 CWA_DB_PATH 指定数据库路径")
        sys.exit(1)
    
    # 备份数据库
    if args.backup and not args.no_backup:
        backup_database(db_path)
    
    # 执行迁移或回滚
    if args.rollback:
        success = migrate_down(db_path)
    else:
        success = migrate_up(db_path)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()