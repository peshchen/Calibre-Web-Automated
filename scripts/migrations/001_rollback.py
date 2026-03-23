#!/usr/bin/env python3
"""
T001 回滚脚本：移除扫描模式数据库字段
============================================

用途：撤销 T001 迁移添加的数据库字段

注意：SQLite 不支持直接删除列，此脚本通过重建表的方式回滚

执行方式：
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
    db_path = os.environ.get('CWA_DB_PATH')
    if db_path:
        return db_path
    
    default_db = os.path.join(project_root, 'library.db')
    if os.path.exists(default_db):
        return default_db
    
    dirs_json = os.path.join(project_root, 'dirs.json')
    if os.path.exists(dirs_json):
        import json
        with open(dirs_json, 'r') as f:
            dirs = json.load(f)
            if 'config' in dirs:
                return dirs['config'].get('db_path', default_db)
    
    return default_db


def rollback(db_path: str) -> bool:
    """执行回滚"""
    print(f"\n📦 连接到数据库: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("\n⚠️ 开始回滚 T001 迁移...")
        print("   注意：SQLite 不支持直接删除列，将重建表")
        
        # 获取现有表结构
        cursor.execute("PRAGMA table_info(books)")
        columns_info = cursor.fetchall()
        
        print(f"\n📋 当前 books 表列: {[col[1] for col in columns_info]}")
        
        # 检查是否有需要移除的字段
        column_names = [col[1] for col in columns_info]
        if 'source_path' not in column_names and 'scan_mode' not in column_names:
            print("\nℹ️ 没有需要回滚的字段，迁移可能未执行")
            return True
        
        # 要保留的列
        keep_columns = [col for col in column_names if col not in ('source_path', 'scan_mode')]
        
        print(f"\n🔧 将保留的列: {keep_columns}")
        
        # 创���临时表（只包含原始列）
        print("\n🔧 创建临时表...")
        col_defs = []
        for col in columns_info:
            col_name = col[1]
            if col_name in keep_columns:
                col_type = col[2]
                col_defs.append(f"{col_name} {col_type}")
        
        create_sql = f"CREATE TABLE IF NOT EXISTS books_backup ({', '.join(col_defs)})"
        cursor.execute(create_sql)
        
        # 复制数据
        print("   复制数据...")
        placeholders = ', '.join(['?' for _ in keep_columns])
        cursor.execute(f"INSERT INTO books_backup ({', '.join(keep_columns)}) SELECT {', '.join(keep_columns)} FROM books")
        
        # 删除原表
        print("   删除原表...")
        cursor.execute("DROP TABLE books")
        
        # 重命名临时表
        print("   重命名表...")
        cursor.execute("RENAME TABLE books_backup TO books")
        
        # 恢复主键自增
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='books'")
        
        # 删除 scan_history 表
        print("\n🔧 删除 scan_history 表...")
        cursor.execute("DROP TABLE IF EXISTS scan_history")
        
        # 删除相关索引
        print("   删除相关索引...")
        cursor.execute("DROP INDEX IF EXISTS idx_books_source_path")
        
        conn.commit()
        print("\n✅ 回滚完成！")
        print("   ✅ 已移除 source_path 字段")
        print("   ✅ 已移除 scan_mode 字段")
        print("   ✅ 已删除 scan_history 表")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 回滚失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='T001 回滚脚本')
    parser.add_argument('--db-path', type=str,
                        help='指定数据库路径（可选）')
    
    args = parser.parse_args()
    
    db_path = args.db_path if args.db_path else get_db_path()
    
    print("=" * 60)
    print("T001 回滚：移除扫描模式数据库字段")
    print("=" * 60)
    print(f"数据库路径: {db_path}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(db_path):
        print(f"\n❌ 错误：数据库文件不存在: {db_path}")
        sys.exit(1)
    
    success = rollback(db_path)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()