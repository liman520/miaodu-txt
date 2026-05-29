# 秒读课堂 - 文章采集器
import time
import hashlib
import httpx
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class Collector:
    """文章采集器"""

    def __init__(self, config):
        self.config = config
        if hasattr(config, 'get'):
            self.timeout = config.get('collection.timeout', 300)
            self.request_interval = config.get('collection.request_interval', 3)
            self.min_words = config.get('collection.min_word_count', 300)
            self.max_words = config.get('collection.max_word_count', 3000)
            self.max_articles = config.get('collection.max_articles_per_source', 20)
        else:
            self.timeout = 300
            self.request_interval = 3
            self.min_words = 300
            self.max_words = 3000
            self.max_articles = 20

    def collect_from_text(self, title: str, content: str, category: str,
                          author: str = "", source_url: str = "", source_name: str = "") -> dict:
        """从文本创建文章数据"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return {
            "title": title.strip(),
            "content": content.strip(),
            "category": category,
            "author": author,
            "source_url": source_url,
            "source_name": source_name or "手动录入",
            "word_count": len(content),
            "content_hash": content_hash,
        }

    def collect_from_source(self, source: dict) -> List[Dict]:
        """从采集源获取文章列表"""
        articles = []
        try:
            resp = httpx.get(source["url"], timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 移除脚本和样式
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()

            links = []
            link_selector = source.get("link_selector", "")
            if link_selector:
                elements = soup.select(link_selector)
                for el in elements[:self.max_articles * 2]:
                    href = el.get('href', '')
                    title = el.get_text(strip=True)
                    if href and title and len(title) > 3:
                        if not href.startswith('http'):
                            from urllib.parse import urljoin
                            href = urljoin(source["url"], href)
                        links.append({"url": href, "title": title})
            else:
                for a in soup.find_all('a', href=True)[:self.max_articles * 3]:
                    title = a.get_text(strip=True)
                    href = a['href']
                    if len(title) > 5 and href.startswith(('http', '/')):
                        if not href.startswith('http'):
                            from urllib.parse import urljoin
                            href = urljoin(source["url"], href)
                        links.append({"url": href, "title": title})

            # 去重
            seen = set()
            unique_links = []
            for link in links:
                if link["url"] not in seen:
                    seen.add(link["url"])
                    unique_links.append(link)
            links = unique_links[:self.max_articles]

            for link in links:
                try:
                    art = self._fetch_article(link["url"], link["title"], source)
                    if art:
                        articles.append(art)
                    time.sleep(0.5)
                except Exception as e:
                    logger.debug(f"获取文章失败 {link['url']}: {e}")
                    continue

        except Exception as e:
            logger.error(f"采集源 {source.get('name', '')} 失败: {e}")

        return articles

    def _fetch_article(self, url: str, fallback_title: str, source: dict) -> Optional[dict]:
        """获取单篇文章内容"""
        try:
            resp = httpx.get(url, timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()

            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            if not title:
                title = fallback_title

            # 使用内容选择器或默认策略
            content_selector = source.get("content_selector", "")
            if content_selector:
                content_el = soup.select_one(content_selector)
            else:
                content_el = (
                    soup.find('article') or
                    soup.find('div', class_='content') or
                    soup.find('div', class_='article') or
                    soup.find('div', id='content') or
                    soup.find('main') or
                    soup.body
                )

            if not content_el:
                return None

            text = content_el.get_text(separator='\n', strip=True)
            word_count = len(text)

            if word_count < self.min_words or word_count > self.max_words:
                return None

            content_hash = hashlib.md5(text.encode()).hexdigest()

            return {
                "title": title,
                "content": text,
                "category": source.get("category", ""),
                "source_url": url,
                "source_name": source.get("name", ""),
                "word_count": word_count,
                "content_hash": content_hash,
            }
        except Exception:
            return None
