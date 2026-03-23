"""
T007: 扫描配置 API
==================

提供扫描目录管理的 REST API 端点
"""

import os
import json
import logging
from flask import Blueprint, request, jsonify, g


logger = logging.getLogger(__name__)

# 创建蓝图
scanner_bp = Blueprint('scanner', __name__, url_prefix='/api/scanner')


# ========== 扫描目录配置 API ==========

@scanner_bp.route('/directories', methods=['GET'])
def get_scan_directories():
    """获取扫描目录列表"""
    try:
        from cps import config
        
        # 从配置中获取扫描目录
        scan_dirs = config.config_scanner_directories or []
        
        return jsonify({
            'success': True,
            'data': scan_dirs
        })
        
    except Exception as e:
        logger.error(f"获取扫描目录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/directories', methods=['POST'])
def add_scan_directory():
    """添加扫描目录"""
    try:
        data = request.get_json()
        directory = data.get('directory', '').strip()
        
        if not directory:
            return jsonify({
                'success': False,
                'error': '目录路径不能为空'
            }), 400
        
        # 检查目录是否存在
        if not os.path.exists(directory):
            return jsonify({
                'success': False,
                'error': '目录不存在'
            }), 400
        
        if not os.path.isdir(directory):
            return jsonify({
                'success': False,
                'error': '路径不是有效目录'
            }), 400
        
        # 获取当前配置
        from cps import config
        scan_dirs = config.config_scanner_directories or []
        
        # 检查是否已存在
        if directory in scan_dirs:
            return jsonify({
                'success': False,
                'error': '目录已存在'
            }), 400
        
        # 添加新目录
        scan_dirs.append(directory)
        
        # 保存配置
        config.config_scanner_directories = json.dumps(scan_dirs)
        
        logger.info(f"添加扫描目录: {directory}")
        
        return jsonify({
            'success': True,
            'data': scan_dirs
        })
        
    except Exception as e:
        logger.error(f"添加扫描目录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/directories/<path:directory>', methods=['DELETE'])
def remove_scan_directory(directory):
    """移除扫描目录"""
    try:
        from cps import config
        
        scan_dirs = config.config_scanner_directories or []
        
        if directory not in scan_dirs:
            return jsonify({
                'success': False,
                'error': '目录不存在'
            }), 404
        
        # 移除目录
        scan_dirs.remove(directory)
        
        # 保存配置
        config.config_scanner_directories = json.dumps(scan_dirs)
        
        logger.info(f"移除扫描目录: {directory}")
        
        return jsonify({
            'success': True,
            'data': scan_dirs
        })
        
    except Exception as e:
        logger.error(f"移除扫描目录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 扫描任务 API ==========

@scanner_bp.route('/scan', methods=['POST'])
def trigger_scan():
    """触发扫描任务"""
    try:
        data = request.get_json() or {}
        scan_type = data.get('type', 'full')  # 'full' or 'incremental'
        
        from cps.tasks.scan_library_task import (
            ScanType,
            create_scan_task,
            execute_scan_task
        )
        
        # 获取扫描目录
        from cps import config
        scan_dirs = config.config_scanner_directories or []
        
        if not scan_dirs:
            return jsonify({
                'success': False,
                'error': '请先配置扫描目录'
            }), 400
        
        # 创建任务
        st = ScanType.FULL if scan_type == 'full' else ScanType.INCREMENTAL
        task = create_scan_task(
            scan_type=st,
            scan_directories=scan_dirs,
            created_by=g.user.name if hasattr(g, 'user') else 'admin'
        )
        
        # 异步执行
        task_id = execute_scan_task(task, async_mode=True)
        
        logger.info(f"触发扫描任务: {task_id}, 类型={scan_type}")
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'{scan_type} 扫描已启动'
        })
        
    except Exception as e:
        logger.error(f"触发扫描失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/status', methods=['GET'])
def get_scan_status():
    """获取扫描状态"""
    try:
        from cps.tasks.scan_library_task import get_scan_task_manager
        
        manager = get_scan_task_manager()
        current_task = manager.get_current_task()
        
        if current_task:
            return jsonify({
                'success': True,
                'data': {
                    'running': True,
                    'task_id': current_task.task_id,
                    'scan_type': current_task.scan_type.value,
                    'progress': current_task.progress,
                    'current_file': current_task.current_file,
                    'processed_count': current_task.processed_count,
                    'total_count': current_task.total_count
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'running': False
                }
            })
            
    except Exception as e:
        logger.error(f"获取扫描状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/cancel', methods=['POST'])
def cancel_scan():
    """取消当前扫描任务"""
    try:
        from cps.tasks.scan_library_task import get_scan_task_manager
        
        manager = get_scan_task_manager()
        success = manager.cancel_current_task()
        
        if success:
            return jsonify({
                'success': True,
                'message': '扫描任务已取消'
            })
        else:
            return jsonify({
                'success': False,
                'error': '没有正在运行的扫描任务'
            }), 400
            
    except Exception as e:
        logger.error(f"取消扫描失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 扫描历史 API ==========

@scanner_bp.route('/history', methods=['GET'])
def get_scan_history():
    """获取扫描历史"""
    try:
        from cps import db
        from sqlalchemy import text
        
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # 查询历史记录
        result = db.session.execute(
            text("""
                SELECT id, scan_time, scan_type, scan_directory,
                       total_files, books_added, books_updated,
                       books_warning, books_error, duration_seconds,
                       status, error_message, created_by
                FROM scan_history
                ORDER BY scan_time DESC
                LIMIT :limit OFFSET :offset
            """),
            {'limit': limit, 'offset': offset}
        )
        
        history = []
        for row in result:
            history.append({
                'id': row[0],
                'scan_time': row[1],
                'scan_type': row[2],
                'scan_directory': row[3],
                'total_files': row[4] or 0,
                'books_added': row[5] or 0,
                'books_updated': row[6] or 0,
                'books_warning': row[7] or 0,
                'books_error': row[8] or 0,
                'duration_seconds': row[9] or 0,
                'status': row[10] or 'unknown',
                'error_message': row[11] or '',
                'created_by': row[12] or ''
            })
        
        # 获取总数
        count_result = db.session.execute(
            text("SELECT COUNT(*) FROM scan_history")
        )
        total = count_result.scalar()
        
        return jsonify({
            'success': True,
            'data': history,
            'total': total,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"获取扫描历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/history/<int:history_id>', methods=['GET'])
def get_scan_history_detail(history_id):
    """获取扫描历史详情"""
    try:
        from cps import db
        from sqlalchemy import text
        
        result = db.session.execute(
            text("""
                SELECT id, scan_time, scan_type, scan_directory,
                       total_files, books_added, books_updated,
                       books_warning, books_error, duration_seconds,
                       status, error_message, created_by
                FROM scan_history
                WHERE id = :id
            """),
            {'id': history_id}
        )
        
        row = result.fetchone()
        
        if not row:
            return jsonify({
                'success': False,
                'error': '记录不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'id': row[0],
                'scan_time': row[1],
                'scan_type': row[2],
                'scan_directory': row[3],
                'total_files': row[4] or 0,
                'books_added': row[5] or 0,
                'books_updated': row[6] or 0,
                'books_warning': row[7] or 0,
                'books_error': row[8] or 0,
                'duration_seconds': row[9] or 0,
                'status': row[10] or 'unknown',
                'error_message': row[11] or '',
                'created_by': row[12] or ''
            }
        })
        
    except Exception as e:
        logger.error(f"获取扫描历史详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/history/<int:history_id>', methods=['DELETE'])
def delete_scan_history(history_id):
    """删除扫描历史记录"""
    try:
        from cps import db
        from sqlalchemy import text
        
        db.session.execute(
            text("DELETE FROM scan_history WHERE id = :id"),
            {'id': history_id}
        )
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '记录已删除'
        })
        
    except Exception as e:
        logger.error(f"删除扫描历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 扫描配置 API ==========

@scanner_bp.route('/config', methods=['GET'])
def get_scanner_config():
    """获取扫描配置"""
    try:
        from cps import config
        
        return jsonify({
            'success': True,
            'data': {
                'directories': config.config_scanner_directories or [],
                'supported_formats': config.config_scanner_formats or [],
                'incremental_threshold_hours': config.config_scanner_incremental_hours or 24,
                'auto_scan_enabled': config.config_scanner_auto_enabled or False,
                'auto_scan_interval_hours': config.config_scanner_auto_interval or 24
            }
        })
        
    except Exception as e:
        logger.error(f"获取扫描配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/config', methods=['PUT'])
def update_scanner_config():
    """更新扫描配置"""
    try:
        data = request.get_json()
        from cps import config
        
        if 'supported_formats' in data:
            config.config_scanner_formats = json.dumps(data['supported_formats'])
        
        if 'incremental_threshold_hours' in data:
            config.config_scanner_incremental_hours = data['incremental_threshold_hours']
        
        if 'auto_scan_enabled' in data:
            config.config_scanner_auto_enabled = data['auto_scan_enabled']
        
        if 'auto_scan_interval_hours' in data:
            config.config_scanner_auto_interval = data['auto_scan_interval_hours']
        
        logger.info("扫描配置已更新")
        
        return jsonify({
            'success': True,
            'message': '配置已更新'
        })
        
    except Exception as e:
        logger.error(f"更新扫描配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def register_scanner_api(app):
    """注册扫描 API 蓝图"""
    app.register_blueprint(scanner_bp)
    logger.info("扫描 API 已注册")