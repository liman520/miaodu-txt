"""
MiaoDuAI Workflow - 大模型API客户端模块
支持DeepSeek与小米MIMO两大主流大模型的语义纠错
提供标准的流式/非流式HTTP API接入机制
"""
import httpx
import json
import logging
from typing import Optional

logger = logging.getLogger("miaoduai.llm")


class LLMClient:
    """大模型API客户端，支持DeepSeek和XiaomiMIMO"""

    # 预设的纠错Prompt
    CORRECTION_PROMPT = """你是一位专业的中文文章审校编辑，专门负责初高中学生阅读材料的质量把关。
请对以下文章进行深度语义审查和纠错，具体要求：

1. 修正所有错别字、语病、成分残缺
2. 修复逻辑前后矛盾、语序不当
3. 补全因网络抓取导致的残缺句子
4. 优化文章可读性和流畅度
5. 确保内容适合初高中生阅读，无超纲、成人化内容
6. 保持原文的核心意思和风格不变
7. 输出修改后的完整文章正文（不包含标题）

原文如下：
{content}

请直接输出修正后的完整正文，不要添加任何解释说明。"""

    def __init__(self, config: dict):
        self.provider = config.get("provider", "deepseek")
        self.api_url = config.get("api_url", "")
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.model_name = config.get("model_name", "")
        self.enabled = config.get("enabled", False)
        self.timeout = 120

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_api_url(self) -> str:
        """根据provider获取实际API URL"""
        if self.api_url:
            return self.api_url

        if self.provider == "deepseek":
            base = self.base_url or "https://api.deepseek.com"
            return f"{base.rstrip('/')}/v1/chat/completions"
        elif self.provider == "mimo":
            base = self.base_url or "https://api.mimo.xiaomi.com"
            return f"{base.rstrip('/')}/v1/chat/completions"
        else:
            base = self.base_url or "https://api.deepseek.com"
            return f"{base.rstrip('/')}/v1/chat/completions"

    def _get_model_name(self) -> str:
        """获取模型名称"""
        if self.model_name:
            return self.model_name
        if self.provider == "deepseek":
            return "deepseek-chat"
        elif self.provider == "mimo":
            return "mimo-chat"
        return "deepseek-chat"

    async def correct_article(self, content: str) -> Optional[str]:
        """
        调用大模型进行文章语义纠错
        返回纠错后的文本，失败返回None
        """
        if not self.enabled or not self.api_key:
            logger.warning("AI语义纠错未启用或API Key未配置")
            return None

        url = self._get_api_url()
        payload = {
            "model": self._get_model_name(),
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的中文语文教师和文字编辑，专注于初高中生学习材料的审校工作。",
                },
                {
                    "role": "user",
                    "content": self.CORRECTION_PROMPT.format(content=content),
                },
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    url, headers=self._get_headers(), json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                corrected = data["choices"][0]["message"]["content"].strip()
                if corrected and len(corrected) > 100:
                    logger.info(f"AI纠错完成，原文{len(content)}字 -> 纠错后{len(corrected)}字")
                    return corrected
                else:
                    logger.warning("AI纠错返回内容异常，保留原文")
                    return None
        except httpx.TimeoutException:
            logger.error("AI纠错请求超时")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"AI纠错HTTP错误: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"AI纠错异常: {str(e)}")
            return None

    async def test_connection(self) -> dict:
        """测试API连接是否正常"""
        if not self.api_key:
            return {"success": False, "message": "API Key未配置"}

        url = self._get_api_url()
        payload = {
            "model": self._get_model_name(),
            "messages": [{"role": "user", "content": "你好，请回复OK"}],
            "max_tokens": 10,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url, headers=self._get_headers(), json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                reply = data["choices"][0]["message"]["content"].strip()
                return {"success": True, "message": f"连接成功，模型回复: {reply}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}
