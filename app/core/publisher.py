# 秒读课堂 - 文章发布器
import asyncio
import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Publisher:
    """文章发布器 - 将审核通过的文章发布到平台"""

    def __init__(self, config):
        self.config = config
        if hasattr(config, 'get'):
            self.platform_url = config.get('platform.url', '')
            self.article_interval = config.get('publish.article_interval', 60)
        else:
            self.platform_url = ''
            self.article_interval = 60

    async def publish_article(self, article: dict) -> bool:
        """发布单篇文章到平台"""
        if not self.platform_url:
            logger.warning("未配置平台URL，跳过发布")
            return False

        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                data = {
                    "title": article.get("title", ""),
                    "content": article.get("content", ""),
                    "author": article.get("author", ""),
                    "source_url": article.get("source_url", ""),
                    "category": article.get("category", ""),
                }
                # 实际发布逻辑需对接平台 API
                # resp = await client.post(f'{self.platform_url}/api/articles', json=data)
                # return resp.status_code in (200, 201)
                logger.info(f"模拟发布: {article.get('title', '')[:30]}...")
                return True
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return False
