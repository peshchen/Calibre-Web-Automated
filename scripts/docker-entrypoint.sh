#!/bin/bash
# CWA 启动脚本 - 自动执行数据库迁移
# =================================

set -e

echo "🚀 CWA 启动中..."

# 数据库迁移（只执行一次）
MIGRATION_LOG="/config/.migration_done"
DB_PATH="/config/metadata.db"

if [ -f "$DB_PATH" ] && [ ! -f "$MIGRATION_LOG" ]; then
    echo "📦 执行数据库迁移..."
    cd /app
    python scripts/migrations/001_add_scanner_fields.py --db-path "$DB_PATH" --no-backup || true
    touch "$MIGRATION_LOG"
    echo "✅ 数据库迁移完成"
elif [ -f "$MIGRATION_LOG" ]; then
    echo "ℹ️ 迁移已执行，跳过"
else
    echo "ℹ️ 新部署，将在使用时创建数据库"
fi

# 启动 CWA
echo "🌐 启动 CWA..."
exec python cps.py "$@"