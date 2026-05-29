"""AI 语义纠错引擎 - v2.5.0 优化版（超时+重试+错误分类）"""

import logging
import time
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
        self.timeout = config.get("timeout", 60)
        self.max_retries = config.get("max_retries", 2)
        self.config = config

    def correct(self, content: str) -> Optional[str]:
        if not self.enabled:
            return content
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.provider == "deepseek":
                    result = self._call_deepseek(content)
                elif self.provider == "mimo":
                    result = self._call_mimo(content)
                else:
                    logger.warning(f"不支持的 AI 提供商: {self.provider}")
                    return None
                if result:
                    if attempt > 1:
                        logger.info(f"AI纠错第{attempt}次尝试成功")
                    return result
                logger.warning(f"AI纠错第{attempt}次返回空结果")
            except httpx.TimeoutException:
                last_err = "超时"
                logger.warning(f"AI纠错第{attempt}次超时({self.timeout}s)")
            except httpx.HTTPStatusError as e:
                last_err = f"HTTP {e.response.status_code}"
                logger.warning(f"AI纠错第{attempt}次HTTP错误: {e.response.status_code}")
                # 4xx 客户端错误不重试
                if 400 <= e.response.status_code < 500:
                    return None
            except Exception as e:
                last_err = str(e)
                logger.warning(f"AI纠错第{attempt}次异常: {e}")
            if attempt < self.max_retries:
                wait = attempt * 2
                logger.info(f"等待{wait}秒后重试...")
                time.sleep(wait)
        logger.error(f"AI纠错最终失败(重试{self.max_retries}次): {last_err}")
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
