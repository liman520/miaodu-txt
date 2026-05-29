# 秒读课堂 v2.3.0 - 主应用入口
import os
import logging
import asyncio
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from app.core.config_manager import ConfigManager
from app.core.archiver import ArticleArchiver
from app.core.collector import Collector
from app.core.publisher import Publisher
from app.core.services import do_collection, do_publish
from app.models.database import init_db

# ========== 认证管理器 ==========
import hashlib, secrets, time


class AuthManager:
    """简易认证管理器"""

    def __init__(self):
        self._tokens = {}
        self._password_hash = None

    def set_password(self, password: str):
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, fallback: str = "") -> bool:
        if self._password_hash:
            return hashlib.sha256(password.encode()).hexdigest() == self._password_hash
        # 首次登录，自动设置密码
        if fallback:
            self.set_password(fallback)
            return True
        return False

    def change_password(self, old_pw: str, new_pw: str, config) -> tuple:
        if not self._password_hash:
            return False, "未设置密码"
        if hashlib.sha256(old_pw.encode()).hexdigest() != self._password_hash:
            return False, "旧密码错误"
        self.set_password(new_pw)
        return True, "密码修改成功"

    def generate_token(self, expires_hours=24) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = time.time() + expires_hours * 3600
        return token

    def verify_token(self, token: str) -> bool:
        if not token:
            return False
        exp = self._tokens.get(token)
        if exp is None:
            return False
        if time.time() > exp:
            del self._tokens[token]
            return False
        return True

    def revoke_token(self, token: str):
        self._tokens.pop(token, None)


# ========== 采集状态管理 ==========
class CollectState:
    """采集任务状态追踪"""

    def __init__(self):
        self.is_running = False
        self.total_sources = 0
        self.completed_sources = 0
        self.current_source = ""
        self.current_status = ""
        self.total_articles = 0
        self.passed_articles = 0
        self.rejected_articles = 0
        self.skipped_articles = 0
        self.logs = []
        self._stop_requested = False

    def start(self, total_sources=0):
        self.is_running = True
        self.total_sources = total_sources
        self.completed_sources = 0
        self.current_source = ""
        self.current_status = ""
        self.total_articles = 0
        self.passed_articles = 0
        self.rejected_articles = 0
        self.skipped_articles = 0
        self.logs = []
        self._stop_requested = False

    def finish(self, success=True):
        self.is_running = False
        self.current_status = "完成" if success else "已停止"

    def request_stop(self):
        self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def update_source(self, name, status):
        self.current_source = name
        self.current_status = status

    def complete_source(self):
        self.completed_sources += 1

    def add_article(self, passed: bool):
        self.total_articles += 1
        if passed:
            self.passed_articles += 1
        else:
            self.rejected_articles += 1

    def add_skip(self):
        self.skipped_articles += 1

    def add_log(self, message, level="info"):
        self.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        })
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]

    def get_status(self) -> dict:
        pct = 0
        if self.total_sources > 0:
            pct = round(self.completed_sources / self.total_sources * 100)
        return {
            "is_running": self.is_running,
            "total_sources": self.total_sources,
            "completed_sources": self.completed_sources,
            "current_source": self.current_source,
            "current_status": self.current_status,
            "progress_percent": pct,
            "total_articles": self.total_articles,
            "passed_articles": self.passed_articles,
            "rejected_articles": self.rejected_articles,
            "skipped_articles": self.skipped_articles,
            "logs": self.logs[-50:],
        }


from datetime import datetime

# ========== 调度器占位 ==========
class SchedulerStub:
    def get_jobs_info(self):
        return []
    def setup_schedules(self, collect_cron, publish_cron):
        pass

# ========== 采集审查器占位 ==========
class ReviewerStub:
    def review(self, title, content, category):
        return True, content, "自动通过"


# 设置日志
os.makedirs('./data/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler(
            './data/logs/app.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('miaodu')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    cfg = app.state.config
    db_path = cfg.get('database.path', './data/miaodu.db')
    init_db(db_path)
    logger.info('秒读课堂 v2.3.0 启动完成')
    logger.info(f'数据库: {db_path}')
    logger.info(f'监听: {cfg.get("app.host", "127.0.0.1")}:{cfg.get("app.port", 8080)}')
    yield
    logger.info('秒读课堂关闭')


# 创建 FastAPI 应用
app = FastAPI(
    title='秒读课堂采集发布系统',
    version='2.3.0',
    lifespan=lifespan,
)

# 初始化配置
config = ConfigManager()

# 挂载到 app.state
app.state.config = config
app.state.auth = AuthManager()
app.state.collect_state = CollectState()
app.state.archiver = ArticleArchiver()
app.state.collector = Collector(config)
app.state.publisher = Publisher(config)
app.state.reviewer = ReviewerStub()
app.state.scheduler = SchedulerStub()

# 挂载静态文件
app.mount('/static', StaticFiles(directory='web'), name='static')

# 模板引擎
templates = Jinja2Templates(directory='app/templates')

# 注册 API 路由
from app.routes.api import router as api_router
app.include_router(api_router)


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    return templates.TemplateResponse('index.html', {
        'request': request,
        'app_name': config.get('app.name', '秒读课堂'),
        'version': '2.3.0',
    })


def run():
    """启动服务"""
    import uvicorn
    uvicorn.run(
        'app.main:app',
        host=config.get('app.host', '127.0.0.1'),
        port=config.get('app.port', 8080),
        reload=config.get('app.debug', False),
    )


if __name__ == '__main__':
    run()
