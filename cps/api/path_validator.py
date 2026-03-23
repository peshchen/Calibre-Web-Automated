"""
T009: 路径验证 API
==================

提供路径验证的 API 端点
"""

import os
import logging
from flask import Blueprint, request, jsonify


logger = logging.getLogger(__name__)

# 创建蓝图
path_validator_bp = Blueprint('path_validator', __name__, url_prefix='/api/scanner/validate')


@path_validator_bp.route('/book/<int:book_id>', methods=['GET'])
def validate_book_path(book_id):
    """验证单个图书的路径"""
    try:
        from cps.scanner.path_validator import validate_book_path as validate
        
        is_valid, warnings = validate(book_id)
        
        return jsonify({
            'success': True,
            'data': {
                'book_id': book_id,
                'is_valid': is_valid,
                'warnings': [
                    {
                        'type': w.warning_type,
                        'message': w.message,
                        'severity': w.severity
                    }
                    for w in warnings
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"验证图书路径失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@path_validator_bp.route('/all', methods=['POST'])
def validate_all_paths():
    """验证所有扫描模式图书的路径"""
    try:
        from cps.scanner.path_validator import PathValidator
        
        limit = request.json.get('limit', 1000) if request.json else 1000
        
        validator = PathValidator()
        result = validator.validate_all_scanner_books(limit)
        
        return jsonify({
            'success': True,
            'data': {
                'total_checked': result.total_checked,
                'valid_count': result.valid_count,
                'warning_count': result.warning_count,
                'error_count': result.error_count,
                'warnings': [
                    {
                        'file_path': w.file_path,
                        'type': w.warning_type,
                        'message': w.message,
                        'severity': w.severity
                    }
                    for w in result.warnings
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"批量验证失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@path_validator_bp.route('/missing', methods=['GET'])
def get_missing_files():
    """获取缺失文件报告"""
    try:
        from cps.scanner.path_validator import get_missing_books_report
        
        missing = get_missing_books_report()
        
        return jsonify({
            'success': True,
            'data': {
                'count': len(missing),
                'books': missing
            }
        })
        
    except Exception as e:
        logger.error(f"获取缺失文件报告失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@path_validator_bp.route('/path', methods=['POST'])
def validate_single_path():
    """验证单个路径"""
    try:
        data = request.get_json()
        file_path = data.get('path', '')
        
        if not file_path:
            return jsonify({
                'success': False,
                'error': '路径不能为空'
            }), 400
        
        from cps.scanner.path_validator import PathValidator
        
        validator = PathValidator()
        is_valid, warning = validator.validate_path(file_path)
        
        return jsonify({
            'success': True,
            'data': {
                'path': file_path,
                'is_valid': is_valid,
                'warning': {
                    'type': warning.warning_type,
                    'message': warning.message,
                    'severity': warning.severity
                } if warning else None
            }
        })
        
    except Exception as e:
        logger.error(f"验证路径失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def register_path_validator_api(app):
    """注册路径验证 API"""
    from cps.api.scanner import scanner_bp
    app.register_blueprint(path_validator_bp)
    logger.info("路径验证 API 已注册")