# 秒读课堂 - 文章采集器（支持站点专用解析器）
import time
import hashlib
import httpx
import logging
import re
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# 站点专用解析策略
SITE_PARSERS = {
    "guancha.gmw.cn": {
        "name": "光明时评",
        "link_patterns": [r'/\d{4}/\d{4}/', r'/content_', r'/article_'],
        "content_selector": ".article_content, .content, .article-body, #articleContent, .main-content",
        "title_selector": "h1, .article-title, .title",
    },
    "news.cn": {
        "name": "新华网",
        "link_patterns": [r'/\d{4}-', r'/content_', r'/\d{8}/'],
        "content_selector": "#detail, .article, .content, .detail-content",
        "title_selector": "h1, .title, #title",
    },
    "gmw.cn": {
        "name": "光明网",
        "link_patterns": [r'/\d{4}-', r'/content_', r'/\d{8}/'],
        "content_selector": ".article_content, .content, #articleContent, .txt_con",
        "title_selector": "h1, .article_title, .title",
    },
    "people.com.cn": {
        "name": "人民网",
        "link_patterns": [r'/n1/', r'/\d{4}/', r'c\d{8}'],
        "content_selector": ".rm_txt_con, .article, .content, #rwb_zw",
        "title_selector": "h1, .title, #title",
    },
}


def _get_site_parser(url: str) -> Optional[dict]:
    """根据 URL 匹配站点专用解析器"""
    for domain, parser in SITE_PARSERS.items():
        if domain in url:
            return parser
    return None


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

        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

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
        url = source["url"]
        site_parser = _get_site_parser(url)

        try:
            resp = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers=self._headers)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
                tag.decompose()

            links = self._extract_links(soup, source, site_parser, url)

            # 去重
            seen = set()
            unique_links = []
            for link in links:
                if link["url"] not in seen:
                    seen.add(link["url"])
                    unique_links.append(link)
            links = unique_links[:self.max_articles]

            logger.info(f"从 {source.get('name', url)} 提取到 {len(links)} 个链接")

            for link in links:
                try:
                    art = self._fetch_article(link["url"], link["title"], source, site_parser)
                    if art:
                        articles.append(art)
                    time.sleep(self.request_interval)
                except Exception as e:
                    logger.debug(f"获取文章失败 {link['url']}: {e}")
                    continue

        except Exception as e:
            logger.error(f"采集源 {source.get('name', '')} 失败: {e}")

        return articles

    def _extract_links(self, soup: BeautifulSoup, source: dict, site_parser: Optional[dict], base_url: str) -> List[Dict]:
        """提取文章链接列表"""
        links = []
        link_selector = source.get("link_selector", "")

        if link_selector:
            elements = soup.select(link_selector)
            for el in elements[:self.max_articles * 2]:
                href = el.get('href', '')
                title = el.get_text(strip=True)
                if href and title and len(title) > 5:
                    if not href.startswith('http'):
                        href = urljoin(base_url, href)
                    links.append({"url": href, "title": title})
        else:
            # 使用站点专用策略或通用策略
            link_patterns = []
            if site_parser:
                link_patterns = site_parser.get("link_patterns", [])

            for a in soup.find_all('a', href=True)[:self.max_articles * 5]:
                title = a.get_text(strip=True)
                href = a['href']

                if len(title) < 6 or len(title) > 100:
                    continue
                if not href.startswith(('http', '/')):
                    continue

                if not href.startswith('http'):
                    href = urljoin(base_url, href)

                # 过滤非文章链接
                if any(skip in href.lower() for skip in [
                    '/tag/', '/category/', '/login/', '/register/',
                    '/about/', '/contact/', '/search/', '.css', '.js',
                    '.jpg', '.png', '.gif', '.mp4', '.mp3',
                    'javascript:', '#', '/page/',
                ]):
                    continue

                # 使用正则匹配文章链接模式
                if link_patterns:
                    if any(re.search(p, href) for p in link_patterns):
                        links.append({"url": href, "title": title})
                else:
                    # 通用启发式：链接路径深度 >= 3 或包含日期格式
                    path_depth = len([p for p in href.split('/') if p]) - 2
                    has_date = bool(re.search(r'/20\d{2}', href))
                    if path_depth >= 2 or has_date:
                        links.append({"url": href, "title": title})

        return links

    def _fetch_article(self, url: str, fallback_title: str, source: dict,
                       site_parser: Optional[dict] = None) -> Optional[dict]:
        """获取单篇文章内容"""
        try:
            resp = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers=self._headers)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
                tag.decompose()

            # 提取标题
            title = ''
            if site_parser and site_parser.get("title_selector"):
                title_el = soup.select_one(site_parser["title_selector"])
                if title_el:
                    title = title_el.get_text(strip=True)
            if not title and soup.title:
                title = soup.title.get_text(strip=True)
            if not title:
                title = fallback_title

            # 清理标题（去掉网站名后缀）
            for suffix in ['-光明网', '-新华网', '-人民网', '_光明网', '_新华网', '_人民网',
                           '-光明时评', '_光明时评', '-光明日报', '_光明日报']:
                title = title.replace(suffix, '').strip()

            # 提取正文
            content_selector = source.get("content_selector", "")
            content_el = None

            if content_selector:
                content_el = soup.select_one(content_selector)

            if not content_el and site_parser and site_parser.get("content_selector"):
                for sel in site_parser["content_selector"].split(','):
                    content_el = soup.select_one(sel.strip())
                    if content_el:
                        break

            if not content_el:
                content_el = (
                    soup.find('article') or
                    soup.find('div', class_='content') or
                    soup.find('div', class_='article') or
                    soup.find('div', id='content') or
                    soup.find('div', class_='article_content') or
                    soup.find('div', class_='txt_con') or
                    soup.find('div', class_='rm_txt_con') or
                    soup.find('main') or
                    soup.body
                )

            if not content_el:
                return None

            # 提取段落文本
            paragraphs = []
            for p in content_el.find_all(['p', 'div', 'section']):
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    # 过滤广告和无关内容
                    if any(kw in text for kw in [
                        '微信号', '加微信', '扫码关注', '点击链接', '限时优惠',
                        '免费领取', '转发有礼', '广告合作', '商务合作',
                        '编辑：', '责任编辑：', '来源：', '原标题：',
                    ]):
                        continue
                    paragraphs.append(text)

            if not paragraphs:
                text = content_el.get_text(separator='\n', strip=True)
            else:
                text = '\n'.join(paragraphs)

            # 清理多余空白
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ 　]+', ' ', text)
            text = text.strip()

            word_count = len(text)

            if word_count < self.min_words or word_count > self.max_words:
                logger.debug(f"字数不符合要求 ({word_count}): {title[:30]}")
                return None

            content_hash = hashlib.md5(text.encode()).hexdigest()

            # 提取作者
            author = ''
            author_patterns = [
                r'(?:作者|撰文|文)[：:]\s*(.{2,10})',
                r'(?:记者|通讯员)[：:]\s*(.{2,10})',
            ]
            for pattern in author_patterns:
                m = re.search(pattern, text[:200])
                if m:
                    author = m.group(1).strip()
                    break

            return {
                "title": title,
                "content": text,
                "author": author,
                "category": source.get("category", ""),
                "source_url": url,
                "source_name": source.get("name", ""),
                "word_count": word_count,
                "content_hash": content_hash,
            }
        except Exception as e:
            logger.debug(f"获取文章失败 {url}: {e}")
            return None
