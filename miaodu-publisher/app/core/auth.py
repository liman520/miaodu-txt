"""认证模块 - v2.3 增强版（支持修改密码）"""

import os
import time
import secrets
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class AuthManager:
    """基于 token 的轻量级认证管理"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self._tokens = {}  # token -> expires_at

    def generate_token(self, expires_hours: int = 24) -> str:
        """生成认证 token"""
        token = secrets.token_hex(32)
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        self._tokens[token] = expires_at
        self._cleanup_expired()
        return token

    def verify_token(self, token: str) -> bool:
        """验证 token 是否有效"""
        if not token:
            return False
        self._cleanup_expired()
        expires_at = self._tokens.get(token)
        if not expires_at:
            return False
        if datetime.utcnow() > expires_at:
            del self._tokens[token]
            return False
        return True

    def revoke_token(self, token: str):
        """撤销 token"""
        self._tokens.pop(token, None)

    def verify_password(self, password: str, config_secret: str) -> bool:
        """验证密码（使用 hmac 比较防时序攻击）"""
        if not config_secret:
            return True  # 未设置密码时允许登录
        return hmac.compare_digest(password.encode(), config_secret.encode())

    def change_password(self, old_password: str, new_password: str, config_manager) -> tuple:
        """
        修改密码
        返回: (success: bool, message: str)
        """
        current_password = config_manager.get("app.secret_key", "")

        # 验证旧密码
        if not self.verify_password(old_password, current_password):
            return False, "当前密码错误"

        # 校验新密码
        if len(new_password) < 6:
            return False, "新密码长度不能少于6位"

        if old_password == new_password:
            return False, "新密码不能与当前密码相同"

        # 更新密码
        config_manager.set("app.secret_key", new_password)
        config_manager.save()  # 持久化到配置文件
        logger.info("管理员密码已修改")

        return True, "密码修改成功，请重新登录"

    def _cleanup_expired(self):
        """清理过期 token"""
        now = datetime.utcnow()
        expired = [t for t, exp in self._tokens.items() if now > exp]
        for t in expired:
            del self._tokens[t]
