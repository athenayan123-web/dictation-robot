# -*- coding: utf-8 -*-
"""
报听写机器人 - 商业化SKILL封装
基础版 vs 进阶版 功能矩阵 + 许可证管理
"""
import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

COMMERCIAL_DIR = Path(__file__).parent.parent
LICENSE_FILE = COMMERCIAL_DIR / 'data' / 'licenses.json'

# ===== 版本功能矩阵 =====
PLANS = {
    'free': {
        'name': '免费体验版',
        'price': 0,
        'features': {
            'max_grades': 2,           # 最多2个年级
            'max_words_per_day': 20,   # 每天最多20个词
            'tts_enabled': True,       # TTS语音
            'repeat_count': 3,         # 每词3遍
            'interval_sec': 5,         # 间隔5秒
            'schedule_types': ['once'],# 仅单次
            'memory_curve': False,     # 无记忆曲线
            'mistake_book': False,     # 无错题本
            'photo_ocr': False,        # 无拍照识别
            'custom_words': False,     # 无自定义词库
            'export_report': False,    # 无导出报告
            'multi_user': False,       # 单用户
            'max_tasks': 3,            # 最多3个任务
            'ads': True,               # 有广告
            'watermark': True,         # 有水印
        },
        'limits_text': '每天20词 · 2个年级 · 单次听写'
    },
    'basic': {
        'name': '基础版',
        'price_monthly': 9.9,
        'price_yearly': 68,
        'features': {
            'max_grades': 12,          # 全部年级
            'max_words_per_day': 100,  # 每天100词
            'tts_enabled': True,
            'repeat_count': 5,         # 最多5遍
            'interval_sec': 10,        # 最长10秒
            'schedule_types': ['once', 'daily', 'weekly'],
            'memory_curve': True,      # SM-2记忆曲线
            'mistake_book': True,      # 错题本
            'photo_ocr': False,        # 无拍照识别
            'custom_words': True,      # 自定义词库（限50词）
            'custom_words_limit': 50,
            'export_report': False,
            'multi_user': False,
            'max_tasks': 20,
            'ads': False,
            'watermark': False,
        },
        'limits_text': '全年级 · 每天100词 · 记忆曲线 · 错题本'
    },
    'pro': {
        'name': '进阶版',
        'price_monthly': 19.9,
        'price_yearly': 128,
        'features': {
            'max_grades': 12,
            'max_words_per_day': 999,  # 不限
            'tts_enabled': True,
            'repeat_count': 10,
            'interval_sec': 30,
            'schedule_types': ['once', 'daily', 'weekly', 'custom'],
            'memory_curve': True,
            'mistake_book': True,
            'photo_ocr': True,         # LLM拍照识别
            'photo_ocr_daily': 20,     # 每天20次
            'custom_words': True,
            'custom_words_limit': 500,
            'export_report': True,     # 导出学习报告
            'multi_user': True,        # 多用户（家庭版，最多5人）
            'multi_user_limit': 5,
            'max_tasks': 999,
            'ads': False,
            'watermark': False,
            'priority_support': True,  # 优先客服
        },
        'limits_text': '全功能 · 不限词数 · AI拍照 · 学习报告 · 家庭共享'
    }
}


def generate_license_key(user_id: str, plan: str, days: int = 365) -> dict:
    """生成许可证密钥"""
    now = datetime.now()
    raw = f"{user_id}-{plan}-{now.isoformat()}-dictation2026"
    key = 'DR-' + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    
    license_data = {
        'key': key,
        'user_id': user_id,
        'plan': plan,
        'plan_name': PLANS[plan]['name'],
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(days=days)).isoformat(),
        'status': 'active'
    }
    
    # 持久化
    licenses = load_licenses()
    licenses[key] = license_data
    save_licenses(licenses)
    
    return license_data


def verify_license(key: str) -> dict:
    """验证许可证"""
    licenses = load_licenses()
    if key not in licenses:
        return {'valid': False, 'error': '许可证不存在'}
    
    lic = licenses[key]
    expires = datetime.fromisoformat(lic['expires_at'])
    if datetime.now() > expires:
        return {'valid': False, 'error': '许可证已过期', 'expired_at': lic['expires_at']}
    
    plan = lic['plan']
    return {
        'valid': True,
        'plan': plan,
        'plan_name': PLANS[plan]['name'],
        'features': PLANS[plan]['features'],
        'expires_at': lic['expires_at'],
        'days_remaining': (expires - datetime.now()).days
    }


def check_feature(key: str, feature: str) -> bool:
    """检查某功能是否可用"""
    result = verify_license(key)
    if not result['valid']:
        # 降级到免费版
        return PLANS['free']['features'].get(feature, False)
    return result['features'].get(feature, False)


import threading
_license_lock = threading.Lock()

def load_licenses() -> dict:
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _license_lock:
        if LICENSE_FILE.exists():
            try:
                return json.loads(LICENSE_FILE.read_text(encoding='utf-8'))
            except:
                return {}
        return {}

def save_licenses(data: dict):
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _license_lock:
        LICENSE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
