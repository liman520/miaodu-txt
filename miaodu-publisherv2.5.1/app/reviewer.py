"""
MiaoDuAI Workflow - 文章审校模块
实现双层审核清洗流水线：
  第一层：系统自动化智能预审（规则 + AI大模型）
  第二层：人工终审（Web后台交互）
"""
import logging
from typing import Optional
from datetime import datetime

from . import database as db
from . import config as cfg
from .utils import (
    rule_based_correct, validate_article_length, check_content_fitness,
    count_words, archive_article, delete_archive
)
from .llm_client import LLMClient

logger = logging.getLogger("miaoduai.reviewer")


class ArticleReviewer:
    """文章审校器，提供自动化预审和人工终审接口"""

    def __init__(self):
        self.config = cfg.load_config()
        self.llm_client = LLMClient(self.config.get("llm", {}))

    async def auto_review_single(self, article_id: int) -> dict:
        """
        对单篇文章执行第一层自动化预审
        返回审核结果 {"passed": bool, "reason": str}
        """
        article = await db.get_article_by_id(article_id)
        if not article:
            return {"passed": False, "reason": "文章不存在"}

        content = article["content"]
        title = article["title"]

        # 1. 规则级纠错
        cleaned = rule_based_correct(content)

        # 2. 字数验证
        min_len = self.config["article"]["min_length"]
        max_len = self.config["article"]["max_length"]
        is_valid, wc, msg = validate_article_length(cleaned, min_len, max_len)
        if not is_valid:
            await db.update_article_status(article_id, "rejected", f"字数不达标: {msg}")
            return {"passed": False, "reason": msg}

        # 3. 内容适配性校验
        is_fit, reason = check_content_fitness(cleaned)
        if not is_fit:
            await db.update_article_status(article_id, "rejected", f"内容不适配: {reason}")
            return {"passed": False, "reason": reason}

        # 4. AI语义纠错（可选）
        if cfg.is_llm_enabled():
            corrected = await self.llm_client.correct_article(cleaned)
            if corrected:
                cleaned = corrected
                wc = count_words(cleaned)
                # 更新数据库中的内容
                article_db = await db.get_db()
                try:
                    await article_db.execute(
                        "UPDATE articles SET content=?, word_count=?, ai_corrected=1 WHERE id=?",
                        (cleaned, wc, article_id),
                    )
                    await article_db.commit()
                finally:
                    await article_db.close()

        # 5. 更新清洗后的内容和字数
        article_db = await db.get_db()
        try:
            await article_db.execute(
                "UPDATE articles SET content=?, word_count=? WHERE id=?",
                (cleaned, wc, article_id),
            )
            await article_db.commit()
        finally:
            await article_db.close()

        # 6. 更新归档文件
        article["content"] = cleaned
        article["word_count"] = wc
        archive_article(article)

        await db.add_log(
            f"自动预审通过: [{article['category']}] {title[:30]} ({wc}字)",
            "reviewer", "INFO"
        )

        return {"passed": True, "reason": f"预审通过，{wc}字"}

    async def manual_approve(self, article_id: int, reviewer_note: str = "") -> dict:
        """
        第二层：人工终审 - 通过
        文章状态变为 ready，进入待发布队列
        """
        article = await db.get_article_by_id(article_id)
        if not article:
            return {"success": False, "message": "文章不存在"}

        if article["status"] not in ("pending", "ready"):
            return {"success": False, "message": f"文章状态({article['status']})不允许此操作"}

        await db.update_article_status(article_id, "ready", reviewer_note or "人工审核通过")
        await db.add_log(
            f"人工审核通过: [{article['category']}] {article['title'][:30]}",
            "reviewer", "INFO"
        )
        return {"success": True, "message": "已通过，进入待发布队列"}

    async def manual_reject(self, article_id: int, reviewer_note: str = "") -> dict:
        """
        第二层：人工终审 - 驳回
        文章状态变为 rejected，本地归档文件被物理删除
        """
        article = await db.get_article_by_id(article_id)
        if not article:
            return {"success": False, "message": "文章不存在"}

        if article["status"] in ("published",):
            return {"success": False, "message": "已发布文章不可驳回"}

        # 删除本地归档
        delete_archive(article)

        # 更新状态
        await db.update_article_status(
            article_id, "rejected", reviewer_note or "人工驳回废弃"
        )
        await db.add_log(
            f"人工驳回废弃: [{article['category']}] {article['title'][:30]}",
            "reviewer", "WARNING"
        )
        return {"success": True, "message": "已驳回废弃，本地归档已清除"}

    async def batch_approve(self, article_ids: list) -> dict:
        """批量通过"""
        success = 0
        failed = 0
        for aid in article_ids:
            result = await self.manual_approve(aid)
            if result["success"]:
                success += 1
            else:
                failed += 1
        return {"success": True, "message": f"批量通过: 成功{success}篇, 失败{failed}篇"}

    async def batch_reject(self, article_ids: list) -> dict:
        """批量驳回"""
        success = 0
        failed = 0
        for aid in article_ids:
            result = await self.manual_reject(aid)
            if result["success"]:
                success += 1
            else:
                failed += 1
        return {"success": True, "message": f"批量驳回: 成功{success}篇, 失败{failed}篇"}

    async def batch_transfer(self, article_ids: list, target_category: str) -> dict:
        """批量转移分类"""
        valid_categories = cfg.CATEGORIES
        if target_category not in valid_categories:
            return {"success": False, "message": f"无效分类: {target_category}"}

        db_conn = await db.get_db()
        try:
            count = 0
            for aid in article_ids:
                await db_conn.execute(
                    "UPDATE articles SET category = ? WHERE id = ?",
                    (target_category, aid),
                )
                count += 1
            await db_conn.commit()
            await db.add_log(
                f"批量转移分类: {count}篇文章 -> {target_category}",
                "reviewer", "INFO"
            )
            return {"success": True, "message": f"已将{count}篇文章转移至{target_category}"}
        finally:
            await db_conn.close()
