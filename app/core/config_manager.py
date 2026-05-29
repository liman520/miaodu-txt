"""配置管理器 - 安全加载与加密"""

import os
import yaml
import logging
import secrets
from pathlib import Path
from typing import Any, Dict
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.yaml")


class ConfigManager:
    """线程安全的配置管理器，支持敏感字段加密"""

    def __init__(self, config_path: str = CONFIG_PATH):
        self._path = config_path
        self._data: Dict[str, Any] = {}
        self._fernet = None
        self.load()

    def load(self):
        """加载配置文件，如果不存在则创建默认"""
        if not os.path.exists(self._path):
            logger.info(f"配置文件不存在，创建默认: {self._path}")
            self._create_default_config()

        with open(self._path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        # 自动生成 secret_key
        if not self._data.get("app", {}).get("secret_key"):
            self._data.setdefault("app", {})["secret_key"] = secrets.token_hex(32)
            self._save_to_disk()

        # 初始化加密器
        key = self._data["app"]["secret_key"]
        import hashlib, base64
        derived = hashlib.sha256(key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))

    def _create_default_config(self):
        """创建默认配置文件"""
        default = {
            "app": {"host": "127.0.0.1", "port": 8080, "secret_key": "", "debug": False, "name": "秒读课堂采集发布系统", "version": "2.4.0"},
            "database": {"path": "./data/miaodu.db"},
            "categories": [
                {"name": "写作素材", "enabled": True, "daily_min": 2, "daily_max": 5},
                {"name": "古诗古文", "enabled": True, "daily_min": 2, "daily_max": 5},
                {"name": "时政热点", "enabled": True, "daily_min": 2, "daily_max": 5},
                {"name": "家国情怀", "enabled": True, "daily_min": 2, "daily_max": 5},
                {"name": "科技人文", "enabled": True, "daily_min": 2, "daily_max": 5},
                {"name": "思辨阅读", "enabled": True, "daily_min": 2, "daily_max": 5},
            ],
            "collection": {"schedule_cron": "0 7 * * *", "min_word_count": 300, "max_word_count": 3000, "max_retries": 3, "request_interval": 3, "timeout": 300, "max_articles_per_source": 20},
            "publish": {"schedule_cron": "0 17 * * *", "article_interval": 60, "time_range_start": "18:00", "time_range_end": "20:00"},
            "ai_correction": {"enabled": False, "provider": "deepseek", "timeout": 30, "deepseek": {"api_url": "", "api_key": "", "model": "deepseek-chat"}, "mimo": {"api_url": "", "api_key": "", "model": ""}},
            "platform": {"url": "https://miaoduai.com/v2/", "chrome_user_data_dir": ""},
            "logging": {"level": "INFO", "file": "./data/logs/app.log", "max_size_mb": 10, "backup_count": 5},
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(default, f, allow_unicode=True, default_flow_style=False)

    def get(self, dotpath: str, default=None) -> Any:
        """用点分路径获取配置值"""
        keys = dotpath.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, dotpath: str, value: Any):
        """用点分路径设置配置值"""
        keys = dotpath.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    def update_from_dict(self, updates: Dict[str, Any]):
        """从字典批量更新配置"""
        for dotpath, value in updates.items():
            self.set(dotpath, value)
        self._save_to_disk()

    def encrypt_value(self, plaintext: str) -> str:
        """加密敏感值"""
        if not self._fernet or not plaintext:
            return plaintext
        return "ENC:" + self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt_value(self, ciphertext: str) -> str:
        """解密敏感值"""
        if not self._fernet or not ciphertext or not ciphertext.startswith("ENC:"):
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext[4:].encode()).decode()
        except Exception:
            return ciphertext

    def get_decrypted(self, dotpath: str, default=None) -> Any:
        """获取并自动解密"""
        val = self.get(dotpath, default)
        if isinstance(val, str) and val.startswith("ENC:"):
            return self.decrypt_value(val)
        return val

    def mask_key(self, key: str) -> str:
        """遮蔽 API Key，只显示后4位"""
        if not key or len(key) <= 4:
            return "****"
        return "****" + key[-4:]

    def _save_to_disk(self):
        """原子写入配置文件"""
        import tempfile
        dir_name = os.path.dirname(self._path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".yaml.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)
            os.replace(tmp_path, self._path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def save(self):
        """公开保存方法"""
        self._save_to_disk()

    @property
    def data(self) -> Dict[str, Any]:
        return self._data
