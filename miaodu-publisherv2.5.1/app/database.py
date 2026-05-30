"""
MiaoDuAI Workflow - 数据库管理模块
使用SQLite + aiosqlite实现异步数据持久化
管理文章、采集源、操作日志三张核心表
"""
import aiosqlite
import json
import os
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "miaoduai.db"


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db_async():
    """异步初始化数据库表结构"""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                author TEXT DEFAULT '',
                source TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                word_count INTEGER DEFAULT 0,
                review_notes TEXT DEFAULT '',
                ai_corrected INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                published_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS collect_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '时政热点',
                selector_type TEXT DEFAULT 'css',
                title_selector TEXT DEFAULT '',
                content_selector TEXT DEFAULT '',
                author_selector TEXT DEFAULT '',
                source_selector TEXT DEFAULT '',
                link_selector TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                last_check TIMESTAMP,
                last_status TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT DEFAULT 'INFO',
                module TEXT DEFAULT '',
                message TEXT NOT NULL,
                detail TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_date TEXT NOT NULL,
                category TEXT NOT NULL,
                collected INTEGER DEFAULT 0,
                passed_review INTEGER DEFAULT 0,
                rejected INTEGER DEFAULT 0,
                published INTEGER DEFAULT 0,
                UNIQUE(stat_date, category)
            );
        """)
        await db.commit()
    finally:
        await db.close()


def init_db():
    """同步初始化（用于install.bat首次运行）"""
    import sqlite3

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            author TEXT DEFAULT '',
            source TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            word_count INTEGER DEFAULT 0,
            review_notes TEXT DEFAULT '',
            ai_corrected INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            published_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS collect_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '时政热点',
            selector_type TEXT DEFAULT 'css',
            title_selector TEXT DEFAULT '',
            content_selector TEXT DEFAULT '',
            author_selector TEXT DEFAULT '',
            source_selector TEXT DEFAULT '',
            link_selector TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            last_check TIMESTAMP,
            last_status TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT DEFAULT 'INFO',
            module TEXT DEFAULT '',
            message TEXT NOT NULL,
            detail TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date TEXT NOT NULL,
            category TEXT NOT NULL,
            collected INTEGER DEFAULT 0,
            passed_review INTEGER DEFAULT 0,
            rejected INTEGER DEFAULT 0,
            published INTEGER DEFAULT 0,
            UNIQUE(stat_date, category)
        );
    """)

    # 插入默认采集源（10大权威网站）
    default_sources = [
        ("人民网", "https://www.people.com.cn", "时政热点", "css", "h1 a, .text_title h1", ".text_con, .rm_txt_con, article", ".text_author, .editor", ".text_source, .source", "a[href*='202']"),
        ("新华网", "https://www.xinhuanet.com", "时政热点", "css", "h1, .head-line, .title", "#detail, .main-text, .content", ".author, .editor", ".source, .from", "a[href*='/202']"),
        ("光明网", "https://www.gmw.cn", "时政热点", "css", "h1, .article-title, .title", ".article-content, .content, #txt_content", ".author", ".source", "a[href*='/202']"),
        ("央视网", "https://www.cctv.com", "时政热点", "css", "h1, .title, .cnt_title", ".cnt_bd, .content, .text", ".author, .pub_date", ".source", "a[href*='202']"),
        ("中国网", "https://www.china.com.cn", "时政热点", "css", "h1, .article_title, .title", ".article_content, .text_con, .content", ".author", ".source", "a[href*='202']"),
        ("中国日报网", "https://www.chinadaily.com.cn", "时政热点", "css", "h1, .article-title, .title", "#Content, .article-content, .main_art", ".author", ".source", "a[href*='202']"),
        ("中国青年网", "https://www.youth.cn", "家国情怀", "css", "h1, .article-title, .title", ".article-content, .text, .content", ".author", ".source", "a[href*='202']"),
        ("中国经济网", "https://www.ce.cn", "时政热点", "css", "h1, .article_title, .title", ".article_content, .text, .content", ".author", ".source", "a[href*='202']"),
        ("央广网", "https://www.cnr.cn", "时政热点", "css", "h1, .article-title, .title", ".article-content, .text_con, .content", ".author", ".source", "a[href*='202']"),
        ("求是网", "https://www.qstheory.cn", "家国情怀", "css", "h1, .article-title, .title", ".article-content, .text, .content", ".author", ".source", "a[href*='202']"),
    ]

    # 检查是否已存在默认源
    cursor = conn.execute("SELECT COUNT(*) FROM collect_sources")
    count = cursor.fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO collect_sources (name, url, category, selector_type, title_selector, content_selector, author_selector, source_selector, link_selector) VALUES (?,?,?,?,?,?,?,?,?)",
            default_sources,
        )
    conn.commit()
    conn.close()


# ── 文章 CRUD ──

async def insert_article(title: str, content: str, category: str,
                         author: str = "", source: str = "",
                         source_url: str = "", word_count: int = 0) -> int:
    """插入新文章，返回文章ID"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO articles (title, content, category, author, source, source_url, word_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (title, content, category, author, source, source_url, word_count),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_articles(status: str = None, category: str = None,
                       limit: int = 100, offset: int = 0) -> list:
    """查询文章列表"""
    db = await get_db()
    try:
        sql = "SELECT * FROM articles WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_article_by_id(article_id: int) -> dict:
    """根据ID获取单篇文章"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_article_status(article_id: int, status: str, notes: str = "") -> None:
    """更新文章状态 (pending/ready/rejected/published)"""
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        if status == "published":
            await db.execute(
                "UPDATE articles SET status=?, review_notes=?, published_at=? WHERE id=?",
                (status, notes, now, article_id),
            )
        elif status in ("ready", "rejected"):
            await db.execute(
                "UPDATE articles SET status=?, review_notes=?, reviewed_at=? WHERE id=?",
                (status, notes, now, article_id),
            )
        else:
            await db.execute(
                "UPDATE articles SET status=?, review_notes=? WHERE id=?",
                (status, notes, article_id),
            )
        await db.commit()
    finally:
        await db.close()


async def batch_update_status(article_ids: list, status: str, notes: str = "") -> int:
    """批量更新文章状态，返回更新数量"""
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        placeholders = ",".join(["?"] * len(article_ids))
        if status == "published":
            await db.execute(
                f"UPDATE articles SET status=?, review_notes=?, published_at=? WHERE id IN ({placeholders})",
                [status, notes, now] + article_ids,
            )
        elif status in ("ready", "rejected"):
            await db.execute(
                f"UPDATE articles SET status=?, review_notes=?, reviewed_at=? WHERE id IN ({placeholders})",
                [status, notes, now] + article_ids,
            )
        else:
            await db.execute(
                f"UPDATE articles SET status=?, review_notes=? WHERE id IN ({placeholders})",
                [status, notes] + article_ids,
            )
        await db.commit()
        return len(article_ids)
    finally:
        await db.close()


async def delete_article(article_id: int) -> None:
    """物理删除文章"""
    db = await get_db()
    try:
        await db.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        await db.commit()
    finally:
        await db.close()


async def get_article_count(status: str = None, category: str = None) -> int:
    """统计文章数量"""
    db = await get_db()
    try:
        sql = "SELECT COUNT(*) as cnt FROM articles WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if category:
            sql += " AND category = ?"
            params.append(category)
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
    finally:
        await db.close()


async def get_today_collected_count(category: str = None) -> int:
    """获取今日已采集的文章数量"""
    db = await get_db()
    try:
        today = date.today().isoformat()
        sql = "SELECT COUNT(*) as cnt FROM articles WHERE DATE(created_at) = ?"
        params = [today]
        if category:
            sql += " AND category = ?"
            params.append(category)
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
    finally:
        await db.close()


# ── 采集源 CRUD ──

async def get_sources(enabled_only: bool = False) -> list:
    """获取所有采集源"""
    db = await get_db()
    try:
        sql = "SELECT * FROM collect_sources"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id"
        cursor = await db.execute(sql)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_source_by_id(source_id: int) -> dict:
    """根据ID获取采集源"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM collect_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def add_source(data: dict) -> int:
    """新增采集源"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO collect_sources (name, url, category, selector_type,
               title_selector, content_selector, author_selector, source_selector,
               link_selector, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"], data["url"], data.get("category", "时政热点"),
                data.get("selector_type", "css"),
                data.get("title_selector", ""), data.get("content_selector", ""),
                data.get("author_selector", ""), data.get("source_selector", ""),
                data.get("link_selector", ""), data.get("enabled", 1),
            ),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_source(source_id: int, data: dict) -> None:
    """更新采集源"""
    db = await get_db()
    try:
        fields = []
        values = []
        for k in ["name", "url", "category", "selector_type", "title_selector",
                   "content_selector", "author_selector", "source_selector",
                   "link_selector", "enabled"]:
            if k in data:
                fields.append(f"{k} = ?")
                values.append(data[k])
        if fields:
            values.append(source_id)
            await db.execute(
                f"UPDATE collect_sources SET {', '.join(fields)} WHERE id = ?", values
            )
            await db.commit()
    finally:
        await db.close()


async def delete_source(source_id: int) -> None:
    """删除采集源"""
    db = await get_db()
    try:
        await db.execute("DELETE FROM collect_sources WHERE id = ?", (source_id,))
        await db.commit()
    finally:
        await db.close()


async def update_source_status(source_id: int, status: str) -> None:
    """更新采集源最后检测状态"""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE collect_sources SET last_check = ?, last_status = ? WHERE id = ?",
            (datetime.now().isoformat(), status, source_id),
        )
        await db.commit()
    finally:
        await db.close()


# ── 操作日志 ──

async def add_log(message: str, module: str = "", level: str = "INFO", detail: str = "") -> None:
    """写入操作日志"""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO operation_logs (level, module, message, detail) VALUES (?, ?, ?, ?)",
            (level, module, message, detail),
        )
        await db.commit()
    finally:
        await db.close()


async def get_logs(limit: int = 200, level: str = None) -> list:
    """获取操作日志"""
    db = await get_db()
    try:
        sql = "SELECT * FROM operation_logs WHERE 1=1"
        params = []
        if level:
            sql += " AND level = ?"
            params.append(level)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def clear_logs() -> None:
    """清空所有日志"""
    db = await get_db()
    try:
        await db.execute("DELETE FROM operation_logs")
        await db.commit()
    finally:
        await db.close()


# ── 统计数据 ──

async def get_dashboard_stats() -> dict:
    """获取仪表盘统计数据"""
    db = await get_db()
    try:
        today = date.today().isoformat()

        # 今日采集数
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE DATE(created_at) = ?", (today,)
        )
        row = await cursor.fetchone()
        today_collected = row["cnt"]

        # 待审核数
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE status = 'pending'"
        )
        row = await cursor.fetchone()
        pending_review = row["cnt"]

        # 已通过待发布数
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE status = 'ready'"
        )
        row = await cursor.fetchone()
        ready_count = row["cnt"]

        # 已发布总数
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE status = 'published'"
        )
        row = await cursor.fetchone()
        published_total = row["cnt"]

        # AI拦截数（今日被rejected的）
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE status = 'rejected' AND DATE(reviewed_at) = ?",
            (today,),
        )
        row = await cursor.fetchone()
        today_rejected = row["cnt"]

        # 各板块储备明细
        category_stats = {}
        for cat in ["写作素材", "古诗古文", "时政热点", "家国情怀", "科技人文", "思辨阅读"]:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM articles WHERE category = ? AND status IN ('pending','ready')",
                (cat,),
            )
            row = await cursor.fetchone()
            category_stats[cat] = row["cnt"]

        return {
            "today_collected": today_collected,
            "pending_review": pending_review,
            "ready_count": ready_count,
            "published_total": published_total,
            "today_rejected": today_rejected,
            "category_stats": category_stats,
        }
    finally:
        await db.close()
