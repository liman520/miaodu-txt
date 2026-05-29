"""API 路由 - v2.3 增强版（密码修改 + 采集可视化 + 停止控制）"""

import html
import logging
import asyncio
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from app.models.database import (
    Article, CollectionSource, TaskLog, ArticleStatus,
    get_session
)

logger = logging.getLogger(__name__)

# ========== 认证依赖 ==========
def require_auth(request: Request):
    """API 路由认证依赖"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("auth_token", "")
    auth_mgr = request.app.state.auth
    if not auth_mgr.verify_token(token):
        raise HTTPException(status_code=401, detail="未认证，请先登录")
    return True

# 公开路由（无需认证）
public_router = APIRouter(prefix="/api")

# 需认证路由
router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


# ========== Pydantic 模型 ==========

class ArticleCreate(BaseModel):
    title: str
    content: str
    category: str
    author: str = ""
    source_url: str = ""
    source_name: str = ""

class SourceCreate(BaseModel):
    name: str
    url: str
    category: str
    title_selector: str = ""
    content_selector: str = ""
    link_selector: str = ""
    enabled: bool = True

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    title_selector: Optional[str] = None
    content_selector: Optional[str] = None
    link_selector: Optional[str] = None
    enabled: Optional[bool] = None

class ReviewAction(BaseModel):
    action: str  # "approve" or "reject"
    reason: str = ""

class BatchReviewAction(BaseModel):
    article_ids: List[int]
    action: str
    reason: str = ""

class ConfigUpdate(BaseModel):
    categories: Optional[list] = None
    collection_schedule: Optional[str] = None
    publish_schedule: Optional[str] = None
    ai_correction_enabled: Optional[bool] = None
    ai_correction_provider: Optional[str] = None
    deepseek_api_url: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    mimo_api_url: Optional[str] = None
    mimo_api_key: Optional[str] = None
    mimo_model: Optional[str] = None
    platform_url: Optional[str] = None

class LoginRequest(BaseModel):
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ========== 辅助函数 ==========

def _escape(text: str) -> str:
    """HTML 转义"""
    return html.escape(str(text)) if text else ""


# ========== 认证路由（无需认证） ==========

@router.post("/auth/login")
async def login(data: LoginRequest, request: Request):
    """登录获取 token"""
    auth_mgr = request.app.state.auth
    config = request.app.state.config
    password = data.password
    if not auth_mgr.verify_password(password, config.get("app.secret_key", "")):
        raise HTTPException(status_code=401, detail="密码错误")
    token = auth_mgr.generate_token(expires_hours=24)
    return {"token": token, "message": "登录成功"}

@router.post("/auth/logout")
async def logout(request: Request):
    """登出"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    auth_mgr = request.app.state.auth
    auth_mgr.revoke_token(token)
    return {"message": "已登出"}

@router.post("/auth/change-password")
async def change_password(data: ChangePasswordRequest, request: Request):
    """修改密码"""
    auth_mgr = request.app.state.auth
    config = request.app.state.config
    success, message = auth_mgr.change_password(data.old_password, data.new_password, config)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


# ========== 采集状态路由 ==========

@router.get("/tasks/collect/status")
async def get_collect_status(request: Request):
    """获取采集进度状态"""
    state = request.app.state.collect_state
    return state.get_status()

@router.post("/tasks/collect/stop")
async def stop_collect(request: Request):
    """停止采集"""
    state = request.app.state.collect_state
    if not state.is_running:
        return {"message": "当前没有正在执行的采集任务"}
    state.request_stop()
    return {"message": "正在停止采集，请稍候..."}


# ========== 文章路由 ==========

@router.get("/articles")
async def list_articles(
    status: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    size: int = 20,
):
    """文章列表"""
    with get_session() as session:
        query = session.query(Article)
        if status:
            query = query.filter(Article.status == status)
        if category:
            query = query.filter(Article.category == category)
        total = query.count()
        articles = query.order_by(Article.created_at.desc()).offset((page - 1) * size).limit(size).all()
        return {
            "total": total,
            "page": page,
            "size": size,
            "items": [
                {
                    "id": a.id,
                    "title": _escape(a.title),
                    "author": _escape(a.author or ""),
                    "category": a.category,
                    "word_count": a.word_count,
                    "status": a.status,
                    "source_name": _escape(a.source_name or ""),
                    "auto_review_passed": a.auto_review_passed,
                    "auto_review_log": a.auto_review_log or "",
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "content_preview": _escape((a.content or "")[:200] + "..." if len(a.content or "") > 200 else a.content or ""),
                }
                for a in articles
            ],
        }


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    """文章详情"""
    with get_session() as session:
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        return {
            "id": article.id,
            "title": _escape(article.title),
            "author": _escape(article.author or ""),
            "content": article.content,
            "category": article.category,
            "word_count": article.word_count,
            "status": article.status,
            "source_name": _escape(article.source_name or ""),
            "source_url": article.source_url or "",
            "auto_review_passed": article.auto_review_passed,
            "auto_review_log": article.auto_review_log or "",
            "ai_corrected": article.ai_corrected,
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "published_at": article.published_at.isoformat() if article.published_at else None,
        }


@router.post("/articles")
async def create_article(data: ArticleCreate, request: Request):
    """手动添加文章"""
    collector = request.app.state.collector
    reviewer = request.app.state.reviewer
    archiver = request.app.state.archiver

    article_data = collector.collect_from_text(
        title=data.title, content=data.content, category=data.category,
        author=data.author, source_url=data.source_url, source_name=data.source_name,
    )

    passed, corrected_content, review_log = reviewer.review(
        article_data["title"], article_data["content"], article_data["category"]
    )

    with get_session() as session:
        new_article = Article(
            title=article_data["title"],
            content=corrected_content,
            original_content=article_data["content"] if corrected_content != article_data["content"] else "",
            author=article_data.get("author", ""),
            source_url=article_data.get("source_url", ""),
            source_name=article_data.get("source_name", ""),
            category=article_data["category"],
            word_count=article_data["word_count"],
            content_hash=article_data["content_hash"],
            status=ArticleStatus.PENDING.value if passed else ArticleStatus.REJECTED.value,
            auto_review_passed=passed,
            auto_review_log=review_log,
            ai_corrected=corrected_content != article_data["content"],
        )
        session.add(new_article)
        session.flush()
        new_id = new_article.id

        if passed:
            article_data["content"] = corrected_content
            archiver.archive_article(article_data)

    return {
        "id": new_id,
        "status": ArticleStatus.PENDING.value if passed else ArticleStatus.REJECTED.value,
        "passed": passed,
        "review_log": review_log,
        "message": "文章已提交并归档" if passed else "文章未通过预审，已驳回",
    }


@router.post("/articles/{article_id}/review")
async def review_article(article_id: int, data: ReviewAction, request: Request):
    """审核文章"""
    archiver = request.app.state.archiver

    with get_session() as session:
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        if article.status not in [ArticleStatus.PENDING.value, ArticleStatus.APPROVED.value]:
            raise HTTPException(status_code=400, detail=f"文章当前状态({article.status})不允许审核")

        if data.action == "approve":
            article.status = ArticleStatus.APPROVED.value
            article.updated_at = datetime.utcnow()
            return {"message": "文章已通过审核", "status": "approved"}

        elif data.action == "reject":
            archiver.move_to_recycle(article.id, article.title, article.content, data.reason)
            article.status = ArticleStatus.REJECTED.value
            article.reject_reason = data.reason
            article.updated_at = datetime.utcnow()
            return {"message": "文章已驳回并移入回收站", "status": "rejected"}

        else:
            raise HTTPException(status_code=400, detail="无效操作，请使用 approve/reject")


@router.post("/articles/batch-review")
async def batch_review(data: BatchReviewAction, request: Request):
    """批量审核"""
    results = []
    for article_id in data.article_ids:
        try:
            result = await review_article(article_id, ReviewAction(action=data.action, reason=data.reason), request)
            results.append({"id": article_id, "success": True, "message": result["message"]})
        except Exception as e:
            results.append({"id": article_id, "success": False, "message": str(e)})
    return {"results": results}


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int):
    """删除文章"""
    with get_session() as session:
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        session.delete(article)
    return {"message": "文章已删除"}


# ========== 采集源路由 ==========

@router.get("/sources")
async def list_sources():
    """采集源列表"""
    with get_session() as session:
        sources = session.query(CollectionSource).order_by(CollectionSource.created_at.desc()).all()
        return [
            {
                "id": s.id, "name": _escape(s.name), "url": s.url, "category": s.category,
                "enabled": s.enabled, "title_selector": s.title_selector,
                "content_selector": s.content_selector, "link_selector": s.link_selector,
                "last_collected_at": s.last_collected_at.isoformat() if s.last_collected_at else None,
                "total_collected": s.total_collected,
            }
            for s in sources
        ]


@router.post("/sources")
async def create_source(data: SourceCreate):
    """创建采集源"""
    with get_session() as session:
        source = CollectionSource(
            name=data.name, url=data.url, category=data.category,
            title_selector=data.title_selector, content_selector=data.content_selector,
            link_selector=data.link_selector, enabled=data.enabled,
        )
        session.add(source)
        session.flush()
        return {"id": source.id, "message": "采集源创建成功"}


@router.put("/sources/{source_id}")
async def update_source(source_id: int, data: SourceUpdate):
    """更新采集源"""
    with get_session() as session:
        source = session.query(CollectionSource).filter(CollectionSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="采集源不存在")
        for key, val in data.dict(exclude_none=True).items():
            setattr(source, key, val)
    return {"message": "采集源已更新"}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int):
    """删除采集源"""
    with get_session() as session:
        source = session.query(CollectionSource).filter(CollectionSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="采集源不存在")
        session.delete(source)
    return {"message": "采集源已删除"}


# ========== 任务路由 ==========

@router.post("/tasks/collect")
async def trigger_collect(request: Request):
    """手动触发采集（使用 asyncio.create_task 避免阻塞）"""
    state = request.app.state.collect_state
    if state.is_running:
        return {"message": "采集任务正在执行中，请勿重复触发"}

    from app.core.services import do_collection
    asyncio.create_task(do_collection(request.app))
    return {"message": "采集任务已提交，后台执行中"}


@router.post("/tasks/publish")
async def trigger_publish(request: Request):
    """手动触发发布"""
    from app.core.services import do_publish
    asyncio.create_task(do_publish(request.app))
    return {"message": "发布任务已提交，后台执行中"}


@router.get("/tasks/logs")
async def get_task_logs(page: int = 1, size: int = 20):
    """任务日志"""
    with get_session() as session:
        total = session.query(TaskLog).count()
        logs = session.query(TaskLog).order_by(TaskLog.created_at.desc()).offset((page - 1) * size).limit(size).all()
        return {
            "total": total,
            "items": [
                {
                    "id": l.id, "task_type": l.task_type, "status": l.status,
                    "message": l.message, "detail": l.detail or "",
                    "duration_seconds": l.duration_seconds,
                    "created_at": l.created_at.isoformat() if l.created_at else None,
                }
                for l in logs
            ],
        }


@router.get("/tasks/schedules")
async def get_schedules(request: Request):
    """获取调度信息"""
    scheduler = request.app.state.scheduler
    if scheduler:
        return {"jobs": scheduler.get_jobs_info()}
    return {"jobs": []}


# ========== 回收站路由 ==========

@router.get("/recycle")
async def list_recycle(request: Request):
    """回收站列表"""
    archiver = request.app.state.archiver
    return {"items": archiver.get_recycle_list()}

@router.post("/recycle/clear")
async def clear_recycle(request: Request):
    """清空回收站"""
    archiver = request.app.state.archiver
    count = archiver.clear_recycle()
    return {"message": f"回收站已清空，删除 {count} 个项目"}


# ========== 配置路由 ==========

@router.get("/config")
async def get_config(request: Request):
    """获取配置（脱敏）"""
    cfg = request.app.state.config
    ds_key = cfg.get_decrypted("ai_correction.deepseek.api_key", "")
    mi_key = cfg.get_decrypted("ai_correction.mimo.api_key", "")
    return {
        "categories": cfg.get("categories", []),
        "collection_schedule": cfg.get("collection.schedule_cron", ""),
        "publish_schedule": cfg.get("publish.schedule_cron", ""),
        "ai_correction": {
            "enabled": cfg.get("ai_correction.enabled", False),
            "provider": cfg.get("ai_correction.provider", "deepseek"),
            "deepseek": {
                "api_url": cfg.get("ai_correction.deepseek.api_url", ""),
                "api_key": cfg.mask_key(ds_key),
                "model": cfg.get("ai_correction.deepseek.model", ""),
            },
            "mimo": {
                "api_url": cfg.get("ai_correction.mimo.api_url", ""),
                "api_key": cfg.mask_key(mi_key),
                "model": cfg.get("ai_correction.mimo.model", ""),
            },
        },
        "platform_url": cfg.get("platform.url", ""),
    }


@router.put("/config")
async def update_config(data: ConfigUpdate, request: Request):
    """更新配置"""
    cfg = request.app.state.config
    scheduler = request.app.state.scheduler

    updates = {}
    if data.categories is not None:
        updates["categories"] = data.categories
    if data.collection_schedule:
        updates["collection.schedule_cron"] = data.collection_schedule
    if data.publish_schedule:
        updates["publish.schedule_cron"] = data.publish_schedule
    if data.ai_correction_enabled is not None:
        updates["ai_correction.enabled"] = data.ai_correction_enabled
    if data.ai_correction_provider:
        updates["ai_correction.provider"] = data.ai_correction_provider
    if data.deepseek_api_url:
        updates["ai_correction.deepseek.api_url"] = data.deepseek_api_url
    if data.deepseek_api_key and not data.deepseek_api_key.startswith("****"):
        updates["ai_correction.deepseek.api_key"] = cfg.encrypt_value(data.deepseek_api_key)
    if data.deepseek_model:
        updates["ai_correction.deepseek.model"] = data.deepseek_model
    if data.mimo_api_url:
        updates["ai_correction.mimo.api_url"] = data.mimo_api_url
    if data.mimo_api_key and not data.mimo_api_key.startswith("****"):
        updates["ai_correction.mimo.api_key"] = cfg.encrypt_value(data.mimo_api_key)
    if data.mimo_model:
        updates["ai_correction.mimo.model"] = data.mimo_model
    if data.platform_url:
        updates["platform.url"] = data.platform_url

    cfg.update_from_dict(updates)

    if scheduler:
        collect_cron = cfg.get("collection.schedule_cron", "0 8 * * *")
        publish_cron = cfg.get("publish.schedule_cron", "0 18 * * *")
        scheduler.setup_schedules(collect_cron, publish_cron)

    return {"message": "配置已保存"}


# ========== 仪表盘路由 ==========

@router.get("/dashboard")
async def dashboard_stats(request: Request):
    """仪表盘数据"""
    archiver = request.app.state.archiver

    with get_session() as session:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        total = session.query(Article).count()
        pending = session.query(Article).filter(Article.status == ArticleStatus.PENDING.value).count()
        approved = session.query(Article).filter(Article.status == ArticleStatus.APPROVED.value).count()
        published = session.query(Article).filter(Article.status == ArticleStatus.PUBLISHED.value).count()
        rejected = session.query(Article).filter(Article.status == ArticleStatus.REJECTED.value).count()

        from sqlalchemy import func
        category_stats = dict(
            session.query(Article.category, func.count(Article.id))
            .group_by(Article.category).all()
        )

        today_collected = session.query(Article).filter(
            Article.created_at >= datetime.strptime(today, "%Y-%m-%d")
        ).count()

        sources_count = session.query(CollectionSource).count()
        active_sources = session.query(CollectionSource).filter(CollectionSource.enabled == True).count()

        return {
            "total_articles": total,
            "pending": pending,
            "approved": approved,
            "published": published,
            "rejected": rejected,
            "today_collected": today_collected,
            "category_stats": category_stats,
            "sources_total": sources_count,
            "sources_active": active_sources,
            "recycle_count": len(archiver.get_recycle_list()),
            "archive_stats": archiver.get_archive_stats(),
        }
