"""
MiaoDuAI Workflow - 配置管理模块
负责读取、写入和管理系统配置文件 config.json
"""
import json
import os
import threading
from pathlib import Path
from copy import deepcopy

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"

_lock = threading.Lock()

# 默认配置
DEFAULT_CONFIG = {
    "categories": {
        "写作素材": {"daily_max": 5, "daily_min": 1, "enabled": True},
        "古诗古文": {"daily_max": 3, "daily_min": 1, "enabled": True},
        "时政热点": {"daily_max": 5, "daily_min": 2, "enabled": True},
        "家国情怀": {"daily_max": 3, "daily_min": 1, "enabled": True},
        "科技人文": {"daily_max": 4, "daily_min": 1, "enabled": True},
        "思辨阅读": {"daily_max": 3, "daily_min": 1, "enabled": True},
    },
    "article": {"min_length": 300, "max_length": 3000},
    "publish_time": "18:00",
    "auto_schedule": {
        "collect_cron": "0 6 * * *",
        "publish_cron": "0 18 * * *",
        "enabled": False,
    },
    "llm": {
        "provider": "deepseek",
        "api_url": "",
        "base_url": "",
        "api_key": "",
        "model_name": "",
        "enabled": False,
    },
    "selenium": {"headless": False, "miaoduai_url": "https://miaoduai.com/v2/"},
    "proxy": {"enabled": False, "http": "", "https": ""},
}

# 六大板块名称常量
CATEGORIES = [
    "写作素材",
    "古诗古文",
    "时政热点",
    "家国情怀",
    "科技人文",
    "思辨阅读",
]


def _load_raw() -> dict:
    """从磁盘读取原始JSON配置"""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: dict) -> None:
    """将配置字典写入磁盘"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_config() -> dict:
    """加载完整配置（默认配置 + 用户覆盖）"""
    with _lock:
        raw = _load_raw()
        merged = deepcopy(DEFAULT_CONFIG)
        _deep_merge(merged, raw)
        return merged


def save_config(cfg: dict) -> None:
    """保存完整配置到磁盘"""
    with _lock:
        _save_raw(cfg)


def update_config(patch: dict) -> dict:
    """部分更新配置（深度合并），返回更新后的完整配置"""
    with _lock:
        raw = _load_raw()
        merged = deepcopy(DEFAULT_CONFIG)
        _deep_merge(merged, raw)
        _deep_merge(merged, patch)
        _save_raw(merged)
        return merged


def get(key: str, default=None):
    """获取单个配置项，支持点号路径如 'llm.api_key'"""
    cfg = load_config()
    keys = key.split(".")
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
        if val is None:
            return default
    return val


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深度合并字典，override覆盖base"""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def get_category_config(category: str) -> dict:
    """获取单个板块的配置"""
    cfg = load_config()
    return cfg.get("categories", {}).get(category, {})


def get_today_quota(category: str) -> tuple:
    """获取板块的今日配额 (min, max)"""
    cat_cfg = get_category_config(category)
    return (cat_cfg.get("daily_min", 1), cat_cfg.get("daily_max", 5))


def is_llm_enabled() -> bool:
    """判断AI语义纠错是否已启用"""
    llm = get("llm", {})
    return llm.get("enabled", False) and bool(llm.get("api_key"))
