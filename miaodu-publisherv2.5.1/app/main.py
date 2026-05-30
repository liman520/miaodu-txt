"""
MiaoDuAI Workflow - FastAPI 主程序
AI智能全自动文章采集、数字审校与发布系统
企业级Web可视化管理后台
"""
import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 确保项目根目录在sys.path中
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import database as db
from app import config as cfg
from app.collector import ArticleCollector
from app.reviewer import ArticleReviewer
from app.publisher import ArticlePublisher
from app.scheduler import TaskScheduler
from app.llm_client import LLMClient
from app.utils import get_archive_dates, get_archive_files

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BASE_DIR / "data" / "miaoduai.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("miaoduai")

# ── 全局实例 ──
scheduler = TaskScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    await db.init_db_async()
    logger.info("数据库初始化完成")
    await db.add_log("系统启动", "main", "INFO")

    # 启动调度器
    scheduler.start()

    yield

    # 关闭时清理
    scheduler.stop()
    scheduler.publisher.close()
    logger.info("系统关闭")


# ── FastAPI 应用 ──
app = FastAPI(
    title="MiaoDuAI Workflow",
    description="AI智能全自动文章采集、审校与发布系统",
    version="2.5.1",
    lifespan=lifespan,
)

# 静态文件与模板
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ══════════════════════════════════════════════
#  页面路由
# ══════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 - 仪表盘"""
    stats = await db.get_dashboard_stats()
    logs = await db.get_logs(limit=20)
    scheduler_status = scheduler.get_status()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "logs": logs,
        "scheduler": scheduler_status,
        "categories": cfg.CATEGORIES,
    })


@app.get("/articles", response_class=HTMLResponse)
async def articles_page(
    request: Request,
    status: str = Query(None, description="按状态过滤"),
    category: str = Query(None, description="按板块过滤"),
    page: int = Query(1, ge=1),
):
    """文章管理页面"""
    page_size = 20
    offset = (page - 1) * page_size

    articles = await db.get_articles(
        status=status, category=category, limit=page_size, offset=offset
    )
    total = await db.get_article_count(status=status, category=category)
    total_pages = max(1, (total + page_size - 1) // page_size)

    return templates.TemplateResponse("articles.html", {
        "request": request,
        "articles": articles,
        "current_status": status,
        "current_category": category,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "categories": cfg.CATEGORIES,
    })


@app.get("/sources", response_class=HTMLResponse)
async def sources_page(request: Request):
    """采集源管理页面"""
    sources = await db.get_sources()
    return templates.TemplateResponse("sources.html", {
        "request": request,
        "sources": sources,
        "categories": cfg.CATEGORIES,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """参数配置页面"""
    config = cfg.load_config()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config,
        "categories": cfg.CATEGORIES,
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, level: str = Query(None)):
    """运行日志页面"""
    logs = await db.get_logs(limit=500, level=level)
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs,
        "current_level": level,
    })


@app.get("/archives", response_class=HTMLResponse)
async def archives_page(request: Request, date: str = Query(None)):
    """归档管理页面"""
    dates = get_archive_dates()
    files = get_archive_files(date) if date else []
    return templates.TemplateResponse("archives.html", {
        "request": request,
        "dates": dates,
        "files": files,
        "current_date": date,
    })


# ══════════════════════════════════════════════
#  API 路由 - 采集操作
# ══════════════════════════════════════════════

@app.post("/api/collect")
async def api_collect(category: str = Form(None)):
    """手动触发采集"""
    try:
        result = await scheduler.manual_collect(category)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@app.post("/api/collect/stop")
async def api_stop_collect():
    """停止采集"""
    scheduler.collector.stop()
    await db.add_log("手动停止采集", "api", "WARNING")
    return JSONResponse({"success": True, "message": "采集已停止"})


# ══════════════════════════════════════════════
#  API 路由 - 文章审核
# ══════════════════════════════════════════════

@app.get("/api/articles/{article_id}")
async def api_get_article(article_id: int):
    """获取单篇文章详情"""
    article = await db.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return JSONResponse(article)


@app.post("/api/articles/{article_id}/approve")
async def api_approve_article(article_id: int, note: str = Form("")):
    """人工审核通过"""
    reviewer = ArticleReviewer()
    result = await reviewer.manual_approve(article_id, note)
    return JSONResponse(result)


@app.post("/api/articles/{article_id}/reject")
async def api_reject_article(article_id: int, note: str = Form("")):
    """人工审核驳回"""
    reviewer = ArticleReviewer()
    result = await reviewer.manual_reject(article_id, note)
    return JSONResponse(result)


@app.post("/api/articles/batch/approve")
async def api_batch_approve(ids: str = Form(...)):
    """批量通过"""
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    reviewer = ArticleReviewer()
    result = await reviewer.batch_approve(id_list)
    return JSONResponse(result)


@app.post("/api/articles/batch/reject")
async def api_batch_reject(ids: str = Form(...)):
    """批量驳回"""
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    reviewer = ArticleReviewer()
    result = await reviewer.batch_reject(id_list)
    return JSONResponse(result)


@app.post("/api/articles/batch/transfer")
async def api_batch_transfer(ids: str = Form(...), category: str = Form(...)):
    """批量转移分类"""
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    reviewer = ArticleReviewer()
    result = await reviewer.batch_transfer(id_list, category)
    return JSONResponse(result)


@app.post("/api/articles/{article_id}/delete")
async def api_delete_article(article_id: int):
    """物理删除文章"""
    article = await db.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    from app.utils import delete_archive
    delete_archive(article)
    await db.delete_article(article_id)
    await db.add_log(f"物理删除文章: {article['title'][:30]}", "api", "WARNING")
    return JSONResponse({"success": True, "message": "已删除"})


# ══════════════════════════════════════════════
#  API 路由 - 采集源管理
# ══════════════════════════════════════════════

@app.post("/api/sources/add")
async def api_add_source(
    name: str = Form(...),
    url: str = Form(...),
    category: str = Form("时政热点"),
    selector_type: str = Form("css"),
    title_selector: str = Form(""),
    content_selector: str = Form(""),
    author_selector: str = Form(""),
    source_selector: str = Form(""),
    link_selector: str = Form(""),
    enabled: int = Form(1),
):
    """新增采集源"""
    data = {
        "name": name, "url": url, "category": category,
        "selector_type": selector_type,
        "title_selector": title_selector, "content_selector": content_selector,
        "author_selector": author_selector, "source_selector": source_selector,
        "link_selector": link_selector, "enabled": enabled,
    }
    source_id = await db.add_source(data)
    await db.add_log(f"新增采集源: {name} ({url})", "api", "INFO")
    return JSONResponse({"success": True, "id": source_id, "message": f"采集源 {name} 已添加"})


@app.post("/api/sources/{source_id}/update")
async def api_update_source(source_id: int, request: Request):
    """更新采集源"""
    data = await request.json()
    await db.update_source(source_id, data)
    await db.add_log(f"更新采集源 ID:{source_id}", "api", "INFO")
    return JSONResponse({"success": True, "message": "更新成功"})


@app.post("/api/sources/{source_id}/delete")
async def api_delete_source(source_id: int):
    """删除采集源"""
    source = await db.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="采集源不存在")
    await db.delete_source(source_id)
    await db.add_log(f"删除采集源: {source['name']}", "api", "WARNING")
    return JSONResponse({"success": True, "message": "已删除"})


@app.post("/api/sources/{source_id}/toggle")
async def api_toggle_source(source_id: int):
    """启用/禁用采集源"""
    source = await db.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="采集源不存在")
    new_enabled = 0 if source["enabled"] else 1
    await db.update_source(source_id, {"enabled": new_enabled})
    status = "启用" if new_enabled else "禁用"
    await db.add_log(f"{status}采集源: {source['name']}", "api", "INFO")
    return JSONResponse({"success": True, "enabled": new_enabled, "message": f"已{status}"})


@app.get("/api/sources/{source_id}/test")
async def api_test_source(source_id: int):
    """测试采集源连接"""
    source = await db.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="采集源不存在")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(source["url"], headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"
            })
            status = f"连接成功 (HTTP {resp.status_code}, {len(resp.text)}字节)"
            await db.update_source_status(source_id, status)
            return JSONResponse({"success": True, "message": status})
    except Exception as e:
        status = f"连接失败: {str(e)[:100]}"
        await db.update_source_status(source_id, status)
        return JSONResponse({"success": False, "message": status})


# ══════════════════════════════════════════════
#  API 路由 - 发布操作
# ══════════════════════════════════════════════

@app.post("/api/publish")
async def api_publish():
    """手动触发批量发布"""
    try:
        result = await scheduler.manual_publish()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@app.post("/api/publish/stop")
async def api_stop_publish():
    """停止发布"""
    scheduler.publisher.stop()
    await db.add_log("手动停止发布", "api", "WARNING")
    return JSONResponse({"success": True, "message": "发布已停止"})


# ══════════════════════════════════════════════
#  API 路由 - 系统配置
# ══════════════════════════════════════════════

@app.get("/api/config")
async def api_get_config():
    """获取当前配置"""
    return JSONResponse(cfg.load_config())


@app.post("/api/config/save")
async def api_save_config(request: Request):
    """保存配置"""
    data = await request.json()
    cfg.save_config(data)
    # 更新调度器
    scheduler.update_schedule(data.get("auto_schedule", {}))
    await db.add_log("系统配置已更新", "api", "INFO")
    return JSONResponse({"success": True, "message": "配置已保存"})


@app.post("/api/config/llm")
async def api_save_llm_config(request: Request):
    """保存大模型配置"""
    data = await request.json()
    cfg.update_config({"llm": data})
    await db.add_log(f"大模型配置已更新: {data.get('provider', 'unknown')}", "api", "INFO")
    return JSONResponse({"success": True, "message": "大模型配置已保存"})


@app.post("/api/llm/test")
async def api_test_llm():
    """测试大模型连接"""
    config = cfg.load_config()
    llm = LLMClient(config.get("llm", {}))
    result = await llm.test_connection()
    return JSONResponse(result)


# ══════════════════════════════════════════════
#  API 路由 - 调度器控制
# ══════════════════════════════════════════════

@app.get("/api/scheduler/status")
async def api_scheduler_status():
    """获取调度器状态"""
    return JSONResponse(scheduler.get_status())


@app.post("/api/scheduler/toggle")
async def api_toggle_scheduler():
    """启用/禁用定时调度"""
    config = cfg.load_config()
    current = config.get("auto_schedule", {}).get("enabled", False)
    cfg.update_config({"auto_schedule": {"enabled": not current}})
    scheduler.update_schedule({"enabled": not current, **config.get("auto_schedule", {})})
    status = "启用" if not current else "禁用"
    await db.add_log(f"定时调度已{status}", "api", "INFO")
    return JSONResponse({"success": True, "enabled": not current, "message": f"定时调度已{status}"})


# ══════════════════════════════════════════════
#  API 路由 - 日志与统计
# ══════════════════════════════════════════════

@app.get("/api/logs")
async def api_get_logs(limit: int = Query(200), level: str = Query(None)):
    """获取操作日志"""
    logs = await db.get_logs(limit=limit, level=level)
    return JSONResponse(logs)


@app.post("/api/logs/clear")
async def api_clear_logs():
    """清空日志"""
    await db.clear_logs()
    return JSONResponse({"success": True, "message": "日志已清空"})


@app.get("/api/stats")
async def api_get_stats():
    """获取仪表盘统计数据"""
    stats = await db.get_dashboard_stats()
    return JSONResponse(stats)


@app.get("/api/stats/categories")
async def api_category_stats():
    """获取各板块详细统计"""
    result = {}
    for cat in cfg.CATEGORIES:
        pending = await db.get_article_count(status="pending", category=cat)
        ready = await db.get_article_count(status="ready", category=cat)
        published = await db.get_article_count(status="published", category=cat)
        rejected = await db.get_article_count(status="rejected", category=cat)
        today_count = await db.get_today_collected_count(cat)
        cat_cfg = cfg.get_category_config(cat)
        result[cat] = {
            "pending": pending,
            "ready": ready,
            "published": published,
            "rejected": rejected,
            "today_collected": today_count,
            "daily_max": cat_cfg.get("daily_max", 5),
            "daily_min": cat_cfg.get("daily_min", 1),
        }
    return JSONResponse(result)


@app.get("/api/stats/overview")
async def api_overview_stats():
    """获取总览统计（用于图表）"""
    import aiosqlite
    from app.database import DB_PATH

    # 最近7天的采集趋势
    db_conn = await aiosqlite.connect(str(DB_PATH))
    db_conn.row_factory = aiosqlite.Row
    try:
        cursor = await db_conn.execute("""
            SELECT DATE(created_at) as dt, COUNT(*) as cnt
            FROM articles
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY dt
        """)
        rows = await cursor.fetchall()
        trend = [{"date": r["dt"], "count": r["cnt"]} for r in rows]
    finally:
        await db_conn.close()

    return JSONResponse({"trend": trend})


# ══════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=5000, reload=True)
