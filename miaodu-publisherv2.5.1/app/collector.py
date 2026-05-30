"""
MiaoDuAI Workflow - 文章采集引擎模块
负责从配置的指定网站采集文章，进行DOM解析、内容提取
拒绝泛化抓取，仅在可视化配置的信任网址库内运行
"""
import re
import logging
import asyncio
from typing import Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from . import database as db
from . import config as cfg
from .utils import (
    rule_based_correct, validate_article_length, check_content_fitness,
    count_words, archive_article
)
from .llm_client import LLMClient

logger = logging.getLogger("miaoduai.collector")

# 请求头模拟真实浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


class ArticleCollector:
    """文章采集器，从指定源URL提取文章内容"""

    def __init__(self):
        self.config = cfg.load_config()
        self.llm_client = LLMClient(self.config.get("llm", {}))
        self._running = False

    async def collect_from_source(self, source: dict) -> list:
        """
        从单个采集源抓取文章列表
        返回解析出的文章字典列表
        """
        url = source["url"]
        name = source["name"]
        logger.info(f"开始采集: {name} ({url})")

        articles = []
        try:
            proxy = None
            if self.config.get("proxy", {}).get("enabled"):
                proxy = self.config["proxy"].get("http") or self.config["proxy"].get("https")

            async with httpx.AsyncClient(
                headers=HEADERS, timeout=30, follow_redirects=True, proxy=proxy
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "lxml")

            # 提取文章链接列表
            link_selector = source.get("link_selector", "")
            if not link_selector:
                link_selector = "a[href]"

            links = soup.select(link_selector)
            article_urls = []
            for link in links[:20]:  # 最多处理前20个链接
                href = link.get("href", "")
                if not href or href == "#":
                    continue
                # 补全相对路径
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)
                if not href.startswith("http"):
                    continue
                # 过滤明显非文章链接
                if any(skip in href.lower() for skip in [
                    "javascript:", "mailto:", ".jpg", ".png", ".gif", ".mp4",
                    ".pdf", ".doc", "#", "/tag/", "/category/"
                ]):
                    continue
                if href not in [a["url"] for a in article_urls]:
                    link_text = link.get_text(strip=True)[:100]
                    if link_text and len(link_text) > 4:
                        article_urls.append({"url": href, "title_hint": link_text})

            logger.info(f"发现 {len(article_urls)} 个候选链接: {name}")

            # 逐个抓取文章详情
            for item in article_urls[:10]:  # 每个源最多采集10篇
                try:
                    article = await self._fetch_article(
                        item["url"], source, item["title_hint"]
                    )
                    if article:
                        articles.append(article)
                        logger.info(f"采集成功: {article['title'][:30]}...")
                except Exception as e:
                    logger.warning(f"采集文章失败 {item['url']}: {str(e)}")
                    continue

            await db.update_source_status(source["id"], f"成功采集{len(articles)}篇")

        except httpx.HTTPStatusError as e:
            err_msg = f"HTTP错误 {e.response.status_code}"
            logger.error(f"采集源 {name} {err_msg}")
            await db.update_source_status(source["id"], err_msg)
            await db.add_log(f"采集源 {name} {err_msg}", "collector", "ERROR")
        except Exception as e:
            err_msg = f"采集异常: {str(e)[:100]}"
            logger.error(f"采集源 {name} {err_msg}")
            await db.update_source_status(source["id"], err_msg)
            await db.add_log(f"采集源 {name} {err_msg}", "collector", "ERROR")

        return articles

    async def _fetch_article(self, url: str, source: dict, title_hint: str) -> Optional[dict]:
        """抓取并解析单篇文章"""
        proxy = None
        if self.config.get("proxy", {}).get("enabled"):
            proxy = self.config["proxy"].get("http") or self.config["proxy"].get("https")

        async with httpx.AsyncClient(
            headers=HEADERS, timeout=30, follow_redirects=True, proxy=proxy
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "lxml")

        # 使用配置的选择器提取内容
        title_sel = source.get("title_selector", "h1")
        content_sel = source.get("content_selector", "article, .content, .article-content")
        author_sel = source.get("author_selector", ".author")
        source_sel = source.get("source_selector", ".source")

        # 提取标题
        title = ""
        for sel in title_sel.split(","):
            sel = sel.strip()
            if sel:
                elem = soup.select_one(sel)
                if elem:
                    title = elem.get_text(strip=True)
                    if title:
                        break
        if not title:
            title = title_hint
        if not title or len(title) < 2:
            return None

        # 提取正文
        content = ""
        for sel in content_sel.split(","):
            sel = sel.strip()
            if sel:
                elem = soup.select_one(sel)
                if elem:
                    content = elem.get_text(separator="\n", strip=True)
                    if content and len(content) > 100:
                        break
        if not content or len(content) < 50:
            return None

        # 提取作者
        author = ""
        for sel in author_sel.split(","):
            sel = sel.strip()
            if sel:
                elem = soup.select_one(sel)
                if elem:
                    author = elem.get_text(strip=True)
                    if author:
                        break

        # 提取来源
        source_name = ""
        for sel in source_sel.split(","):
            sel = sel.strip()
            if sel:
                elem = soup.select_one(sel)
                if elem:
                    source_name = elem.get_text(strip=True)
                    if source_name:
                        break
        if not source_name:
            source_name = source["name"]

        return {
            "title": title,
            "content": content,
            "category": source["category"],
            "author": author,
            "source": source_name,
            "source_url": url,
        }

    async def process_article(self, article: dict) -> Optional[int]:
        """
        处理单篇文章：审校 -> 验证 -> 归档 -> 入库
        返回文章ID，不合规返回None
        """
        content = article["content"]
        title = article["title"]

        # 1. 规则级纠错清洗
        cleaned_content = rule_based_correct(content)

        # 2. 字数验证
        is_valid, word_count, msg = validate_article_length(
            cleaned_content,
            self.config["article"]["min_length"],
            self.config["article"]["max_length"],
        )
        if not is_valid:
            logger.info(f"字数不达标丢弃: {title[:20]} - {msg}")
            return None

        # 3. 学段适配性校验
        is_fit, reason = check_content_fitness(cleaned_content)
        if not is_fit:
            logger.info(f"内容不适配丢弃: {title[:20]} - {reason}")
            return None

        # 4. AI语义纠错（可选）
        ai_corrected = 0
        if cfg.is_llm_enabled():
            corrected = await self.llm_client.correct_article(cleaned_content)
            if corrected:
                cleaned_content = corrected
                ai_corrected = 1
                # 重新统计字数
                word_count = count_words(cleaned_content)

        # 5. 写入数据库
        article_id = await db.insert_article(
            title=title,
            content=cleaned_content,
            category=article["category"],
            author=article.get("author", ""),
            source=article.get("source", ""),
            source_url=article.get("source_url", ""),
            word_count=word_count,
        )

        # 如果AI纠错了，更新标记
        if ai_corrected:
            await_db = await db.get_db()
            try:
                await await_db.execute(
                    "UPDATE articles SET ai_corrected = 1 WHERE id = ?", (article_id,)
                )
                await await_db.commit()
            finally:
                await await_db.close()

        # 6. 本地归档
        article["word_count"] = word_count
        archive_path = archive_article(article)
        logger.info(f"文章已归档: {archive_path}")

        return article_id

    async def run_collection(self, category_filter: str = None) -> dict:
        """
        执行一次完整的采集流程
        category_filter: 仅采集指定板块（None表示全部）
        返回采集统计
        """
        self._running = True
        config = cfg.load_config()
        categories_cfg = config.get("categories", {})

        stats = {"total_fetched": 0, "total_passed": 0, "total_rejected": 0, "by_category": {}}

        sources = await db.get_sources(enabled_only=True)
        if not sources:
            logger.warning("没有启用的采集源")
            await db.add_log("采集失败：没有启用的采集源", "collector", "WARNING")
            return stats

        for source in sources:
            if not self._running:
                break

            cat = source["category"]
            if category_filter and cat != category_filter:
                continue

            # 检查板块配额
            cat_cfg = categories_cfg.get(cat, {})
            if not cat_cfg.get("enabled", True):
                continue

            daily_max = cat_cfg.get("daily_max", 5)
            current_count = await db.get_today_collected_count(cat)
            if current_count >= daily_max:
                logger.info(f"板块 {cat} 已达今日上限 {daily_max}，跳过")
                continue

            # 执行采集
            articles = await self.collect_from_source(source)
            stats["total_fetched"] += len(articles)

            if cat not in stats["by_category"]:
                stats["by_category"][cat] = {"fetched": 0, "passed": 0, "rejected": 0}

            for article in articles:
                if not self._running:
                    break

                # 再次检查配额
                current_count = await db.get_today_collected_count(cat)
                if current_count >= daily_max:
                    logger.info(f"板块 {cat} 已达今日上限，停止采集")
                    break

                stats["by_category"][cat]["fetched"] += 1

                article_id = await self.process_article(article)
                if article_id:
                    stats["total_passed"] += 1
                    stats["by_category"][cat]["passed"] += 1
                    await db.add_log(
                        f"采集入库: [{cat}] {article['title'][:30]}",
                        "collector", "INFO"
                    )
                else:
                    stats["total_rejected"] += 1
                    stats["by_category"][cat]["rejected"] += 1

        # 写入日志
        await db.add_log(
            f"采集完成: 抓取{stats['total_fetched']}篇, "
            f"通过{stats['total_passed']}篇, 拦截{stats['total_rejected']}篇",
            "collector", "INFO"
        )

        self._running = False
        return stats

    def stop(self):
        """停止采集"""
        self._running = False
