"""本地归档引擎 - v2.3 增强版"""

import os
import json
import logging
import shutil
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ArticleArchiver:
    def __init__(self, archive_dir: str = "./archives", recycle_dir: str = "./recycle_bin"):
        self.archive_dir = archive_dir
        self.recycle_dir = recycle_dir
        os.makedirs(archive_dir, exist_ok=True)
        os.makedirs(recycle_dir, exist_ok=True)

    def archive_article(self, article: dict) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        date_dir = os.path.join(self.archive_dir, today)
        os.makedirs(date_dir, exist_ok=True)
        title_safe = self._safe_filename(article.get("title", "无标题"))
        existing = [f for f in os.listdir(date_dir) if f.endswith(".txt")]
        seq = len(existing) + 1
        filename = f"{seq:03d}_{title_safe[:20]}.txt"
        filepath = os.path.join(date_dir, filename)
        content = self._format_article(article)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        meta_path = filepath.replace(".txt", ".json")
        meta = {
            "title": article.get("title", ""), "author": article.get("author", ""),
            "category": article.get("category", ""), "source_name": article.get("source_name", ""),
            "source_url": article.get("source_url", ""), "word_count": article.get("word_count", 0),
            "content_hash": article.get("content_hash", ""), "archived_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info(f"文章已归档: {filepath}")
        return filepath

    def move_to_recycle(self, article_id: int, title: str, content: str, reason: str = "") -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        recycle_date_dir = os.path.join(self.recycle_dir, today)
        os.makedirs(recycle_date_dir, exist_ok=True)
        title_safe = self._safe_filename(title)
        filename = f"{article_id}_{title_safe[:20]}.txt"
        filepath = os.path.join(recycle_date_dir, filename)
        content_text = f"[回收站文章]\n标题: {title}\n文章ID: {article_id}\n驳回原因: {reason}\n回收时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'=' * 50}\n\n{content}\n"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content_text)
        logger.info(f"文章已移入回收站: {filepath}")
        return filepath

    def clear_recycle(self) -> int:
        count = 0
        if not os.path.exists(self.recycle_dir):
            return count
        for item in os.listdir(self.recycle_dir):
            item_path = os.path.join(self.recycle_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
            count += 1
        return count

    def get_recycle_list(self) -> List[Dict]:
        articles = []
        if not os.path.exists(self.recycle_dir):
            return articles
        for date_dir in sorted(os.listdir(self.recycle_dir), reverse=True):
            date_path = os.path.join(self.recycle_dir, date_dir)
            if not os.path.isdir(date_path):
                continue
            for filename in os.listdir(date_path):
                if not filename.endswith(".txt"):
                    continue
                filepath = os.path.join(date_path, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                lines = text.split("\n")
                title = reason = ""
                for line in lines:
                    if line.startswith("标题:"):
                        title = line[3:].strip()
                    elif line.startswith("驳回原因:"):
                        reason = line[5:].strip()
                # 从目录名推导 deleted_at
                deleted_at = date_dir
                articles.append({
                    "filename": filename,
                    "date": date_dir,
                    "title": title,
                    "reason": reason,
                    "deleted_at": deleted_at,
                    "path": filepath,
                })
        return articles

    def get_archive_stats(self) -> dict:
        stats = {"total_files": 0, "total_dirs": 0, "by_date": {}}
        if not os.path.exists(self.archive_dir):
            return stats
        for date_dir in sorted(os.listdir(self.archive_dir), reverse=True):
            date_path = os.path.join(self.archive_dir, date_dir)
            if os.path.isdir(date_path):
                files = [f for f in os.listdir(date_path) if f.endswith(".txt")]
                stats["by_date"][date_dir] = len(files)
                stats["total_files"] += len(files)
                stats["total_dirs"] += 1
        return stats

    def restore_from_recycle(self, article_id: int) -> Optional[Dict]:
        """从回收站恢复指定文章"""
        if not os.path.exists(self.recycle_dir):
            return None
        for date_dir in os.listdir(self.recycle_dir):
            date_path = os.path.join(self.recycle_dir, date_dir)
            if not os.path.isdir(date_path):
                continue
            for filename in os.listdir(date_path):
                if not filename.startswith(f"{article_id}_"):
                    continue
                filepath = os.path.join(date_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        text = f.read()
                    # 解析回收站文件
                    lines = text.split("\n")
                    title = ""
                    content_start = 0
                    for i, line in enumerate(lines):
                        if line.startswith("标题:"):
                            title = line[3:].strip()
                        if line.startswith("=" * 20):
                            content_start = i + 2
                            break
                    content = "\n".join(lines[content_start:]).strip() if content_start > 0 else text
                    # 删除回收站文件
                    os.remove(filepath)
                    # 如果日期目录空了，也删掉
                    if not os.listdir(date_path):
                        os.rmdir(date_path)
                    return {"title": title, "content": content, "category": ""}
                except Exception as e:
                    logger.error(f"恢复文章失败 {filepath}: {e}")
                    return None
        return None

    def _format_article(self, article: dict) -> str:
        return f"标题: {article.get('title', '')}\n作者: {article.get('author', '')}\n板块: {article.get('category', '')}\n来源: {article.get('source_name', '')} ({article.get('source_url', '')})\n字数: {article.get('word_count', 0)}\n归档时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'=' * 50}\n\n{article.get('content', '')}\n"

    def _safe_filename(self, name: str) -> str:
        import re
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
        safe = safe.replace(' ', '_')
        return safe[:50] if safe else "untitled"
