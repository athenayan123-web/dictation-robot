# -*- coding: utf-8 -*-
"""
报听写机器人 - 配置管理（含密钥安全存储与季度刷新提醒）
"""
import os
import json
import time
import hashlib
import base64
from pathlib import Path
from datetime import datetime, timedelta

# ===== 路径 =====
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
SECRETS_FILE = DATA_DIR / '.secrets.enc'
CONFIG_FILE = DATA_DIR / 'config.json'
DB_PATH = DATA_DIR / 'dictation.db'

# ===== 默认配置 =====
DEFAULT_CONFIG = {
    'llm_base_url': 'https://api.stepfun.com/v1',
    'llm_model': 'step-1v-8k',
    'server_port': 3801,
    'dictation_repeat': 3,
    'dictation_interval': 5,
    'key_created_at': None,       # 密钥创建时间
    'key_refresh_days': 90,       # 90天（季度）刷新周期
    'key_last_reminded': None,    # 上次提醒时间
    'first_run': True,            # 首次运行标记
}


def _get_machine_key():
    """基于机器特征生成加密密钥（不存储明文）"""
    import platform
    raw = f"{platform.node()}-{platform.machine()}-dictation-robot-2026"
    return hashlib.sha256(raw.encode()).digest()


def encrypt_secret(plaintext: str) -> str:
    """简单对称加密（XOR + base64）"""
    key = _get_machine_key()
    encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(plaintext.encode('utf-8'))])
    return base64.b64encode(encrypted).decode('ascii')


def decrypt_secret(ciphertext: str) -> str:
    """解密"""
    key = _get_machine_key()
    encrypted = base64.b64decode(ciphertext)
    decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(encrypted)])
    return decrypted.decode('utf-8')


def load_config() -> dict:
    """加载配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            # 合并默认值
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    """保存配置"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def save_api_key(api_key: str):
    """加密保存API Key"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    encrypted = encrypt_secret(api_key)
    secrets = {'llm_api_key': encrypted}
    with open(SECRETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(secrets, f)
    # 更新配置中的时间戳
    cfg = load_config()
    cfg['key_created_at'] = datetime.now().isoformat()
    cfg['first_run'] = False
    save_config(cfg)


def load_api_key() -> str:
    """加载并解密API Key"""
    if not SECRETS_FILE.exists():
        return ''
    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            secrets = json.load(f)
        return decrypt_secret(secrets.get('llm_api_key', ''))
    except Exception:
        return ''


def check_key_status() -> dict:
    """
    检查密钥状态，返回：
    - need_first_setup: 首次运行需要输入密钥
    - need_refresh: 超过90天需要刷新
    - days_remaining: 距离下次刷新天数
    - has_key: 是否已有密钥
    """
    cfg = load_config()
    has_key = bool(load_api_key())

    result = {
        'need_first_setup': cfg.get('first_run', True) or not has_key,
        'need_refresh': False,
        'days_remaining': 90,
        'has_key': has_key,
        'key_created_at': cfg.get('key_created_at'),
        'refresh_cycle_days': cfg.get('key_refresh_days', 90),
    }

    if has_key and cfg.get('key_created_at'):
        created = datetime.fromisoformat(cfg['key_created_at'])
        elapsed = (datetime.now() - created).days
        remaining = cfg.get('key_refresh_days', 90) - elapsed
        result['days_remaining'] = max(0, remaining)
        result['need_refresh'] = remaining <= 0
        # 如果在刷新期内且未提醒过，也标记
        if remaining <= 7 and remaining > 0:
            result['need_refresh_soon'] = True

    return result
