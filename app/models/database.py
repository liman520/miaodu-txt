# 秒读课堂 - 数据库模型定义
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Float, Index
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import contextmanager
from enum import Enum

Base = declarative_base()


class ArticleStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class Article(Base):
    """文章模型"""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    original_content = Column(Text, default="")
    author = Column(String(100), default="")
    category = Column(String(50), nullable=False, index=True)
    source_url = Column(String(1000), default="")
    source_name = Column(String(200), default="")
    word_count = Column(Integer, default=0)
    content_hash = Column(String(64), index=True)
    status = Column(String(20), default=ArticleStatus.PENDING.value, index=True)
    auto_review_passed = Column(Boolean, default=False)
    auto_review_log = Column(Text, default="")
    ai_corrected = Column(Boolean, default=False)
    reject_reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


class CollectionSource(Base):
    """采集源模型"""
    __tablename__ = "collection_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    url = Column(String(1000), nullable=False)
    category = Column(String(50), nullable=False)
    title_selector = Column(String(500), default="")
    content_selector = Column(String(500), default="")
    link_selector = Column(String(500), default="")
    enabled = Column(Boolean, default=True)
    last_collected_at = Column(DateTime, nullable=True)
    total_collected = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class TaskLog(Base):
    """任务日志模型"""
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    message = Column(Text, default="")
    detail = Column(Text, default="")
    duration_seconds = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserSession(Base):
    """登录会话"""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


# ========== 数据库引擎管理 ==========

_engine = None
_SessionFactory = None


def init_db(db_path: str):
    """初始化数据库引擎"""
    global _engine, _SessionFactory
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine)
    return _engine, _SessionFactory


@contextmanager
def get_session():
    """安全的数据库会话上下文管理器"""
    if _SessionFactory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_factory():
    """获取 SessionFactory"""
    return _SessionFactory
