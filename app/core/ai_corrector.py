"""AI 语义纠错引擎 - v2.3 增强版"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class AICorrector:
    CORRECTION_PROMPT = """你是一位专业的中文文章编辑，请对以下文章进行语义纠错和优化。
要求：
1. 修正错别字、语法错误
2. 优化句子流畅度，保持原意
3. 补充缺失的标点符号
4. 不要改变文章的核心观点和风格
5. 不要添加额外内容
6. 直接输出修改后的完整文章，不要加任何说明

原文如下：
{content}"""

    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
        self.provider = config.get("provider", "deepseek")
        self.timeout = config.get("timeout", 30)
        self.config = config

    def correct(self, content: str) -> Optional[str]:
        if not self.enabled:
            return content
        try:
            if self.provider == "deepseek":
                return self._call_deepseek(content)
            elif self.provider == "mimo":
                return self._call_mimo(content)
            else:
                logger.warning(f"不支持的 AI 提供商: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"AI 纠错异常: {e}")
            return None

    def _call_deepseek(self, content: str) -> Optional[str]:
        cfg = self.config.get("deepseek", {})
        api_url = cfg.get("api_url", "")
        api_key = cfg.get("api_key", "")
        model = cfg.get("model", "deepseek-chat")
        if not api_url or not api_key:
            return None
        prompt = self.CORRECTION_PROMPT.format(content=content)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(api_url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                               json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 8192})
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result if result else None

    def _call_mimo(self, content: str) -> Optional[str]:
        cfg = self.config.get("mimo", {})
        api_url = cfg.get("api_url", "")
        api_key = cfg.get("api_key", "")
        model = cfg.get("model", "")
        if not api_url or not api_key:
            return None
        prompt = self.CORRECTION_PROMPT.format(content=content)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(api_url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                               json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 8192})
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result if result else None
