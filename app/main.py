# 秒读课堂 v2.3.1 - 主应用入口
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
from app.core.reviewer import ContentReviewer
from app.core.ai_corrector import AICorrector
from app.models.database import init_db

import hashlib, secrets, time
from datetime import datetime

logger = logging.getLogger('miaodu')


class AuthManager:
    """认证管理器 - 密码哈希持久化到文件"""

    def __init__(self, data_dir='./data'):
        self._tokens = {}
        self._password_file = os.path.join(data_dir, '.password')
        os.makedirs(data_dir, exist_ok=True)
        self._password_hash = self._load_password()

    def _load_password(self):
        if os.path.exists(self._password_file):
            with open(self._password_file, 'r') as f:
                h = f.read().strip()
                if h:
                    return h
        return None

    def _save_password(self, pw_hash):
        with open(self._password_file, 'w') as f:
            f.write(pw_hash)

    def set_password(self, password: str):
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()
        self._save_password(self._password_hash)

    def verify_password(self, password: str) -> bool:
        if self._password_hash:
            return hashlib.sha256(password.encode()).hexdigest() == self._password_hash
        # 首次登录，自动设置密码
        self.set_password(password)
        return True

    def change_password(self, old_pw: str, new_pw: str) -> tuple:
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


class TaskState:
    def __init__(self, task_name: str):
        self.task_name = task_name
        self.is_running = False
        self.finished_at = None
        self._stop_requested = False
        self.logs = []

    def start(self):
        self.is_running = True
        self.finished_at = None
        self._stop_requested = False
        self.logs = []

    def finish(self, success=True):
        self.is_running = False
        self.finished_at = datetime.now().isoformat()

    def request_stop(self):
        self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def add_log(self, message, level="info"):
        self.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        })
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]


class CollectState(TaskState):
    def __init__(self):
        super().__init__("collect")
        self.total_sources = 0
        self.completed_sources = 0
        self.current_source = ""
        self.current_action = ""
        self.total_articles = 0
        self.passed_articles = 0
        self.rejected_articles = 0
        self.skipped_articles = 0

    def start(self, total_sources=0):
        super().start()
        self.total_sources = total_sources
        self.completed_sources = 0
        self.current_source = ""
        self.current_action = ""
        self.total_articles = 0
        self.passed_articles = 0
        self.rejected_articles = 0
        self.skipped_articles = 0

    def update_source(self, name, action):
        self.current_source = name
        self.current_action = action

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

    def get_status(self) -> dict:
        pct = 0
        if self.total_sources > 0:
            pct = round(self.completed_sources / self.total_sources * 100)
        return {
            "is_running": self.is_running,
            "finished_at": self.finished_at,
            "total_sources": self.total_sources,
            "completed_sources": self.completed_sources,
            "current_source": self.current_source,
            "current_action": self.current_action,
            "progress": pct,
            "total_articles": self.total_articles,
            "passed_articles": self.passed_articles,
            "rejected_articles": self.rejected_articles,
            "skipped_articles": self.skipped_articles,
            "stop_requested": self._stop_requested,
            "logs": self.logs[-50:],
        }


class PublishState(TaskState):
    def __init__(self):
        super().__init__("publish")
        self.total_articles = 0
        self.published_articles = 0
        self.failed_articles = 0
        self.current_title = ""

    def start(self, total_articles=0):
        super().start()
        self.total_articles = total_articles
        self.published_articles = 0
        self.failed_articles = 0
        self.current_title = ""

    def update_progress(self, title, success: bool):
        if success:
            self.published_articles += 1
        else:
            self.failed_articles += 1
        self.current_title = title

    def get_status(self) -> dict:
        pct = 0
        if self.total_articles > 0:
            pct = round((self.published_articles + self.failed_articles) / self.total_articles * 100)
        return {
            "is_running": self.is_running,
            "finished_at": self.finished_at,
            "total_articles": self.total_articles,
            "published_articles": self.published_articles,
            "failed_articles": self.failed_articles,
            "current_title": self.current_title,
            "progress": pct,
            "stop_requested": self._stop_requested,
            "logs": self.logs[-50:],
        }


class SchedulerStub:
    def get_jobs_info(self):
        return []
    def setup_schedules(self, collect_cron, publish_cron):
        pass


os.makedirs('./data/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler('./data/logs/app.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = app.state.config
    db_path = cfg.get('database.path', './data/miaodu.db')
    init_db(db_path)

    ai_cfg = cfg.get('ai_correction', {})
    ai_corrector = AICorrector(ai_cfg)
    app.state.reviewer = ContentReviewer(ai_corrector=ai_corrector)
    logger.info(f'AI纠错: {"已启用" if ai_corrector.enabled else "未启用"} (provider: {ai_corrector.provider})')
    logger.info('秒读课堂 v2.3.1 启动完成')
    logger.info(f'数据库: {db_path}')
    logger.info(f'监听: {cfg.get("app.host", "127.0.0.1")}:{cfg.get("app.port", 8080)}')
    yield
    logger.info('秒读课堂关闭')


app = FastAPI(title='秒读课堂采集发布系统', version='2.3.1', lifespan=lifespan)

config = ConfigManager()

app.state.config = config
app.state.auth = AuthManager()
app.state.collect_state = CollectState()
app.state.publish_state = PublishState()
app.state.archiver = ArticleArchiver()
app.state.collector = Collector(config)
app.state.publisher = Publisher(config)
app.state.reviewer = None  # set in lifespan
app.state.scheduler = SchedulerStub()

app.mount('/static', StaticFiles(directory='web'), name='static')
templates = Jinja2Templates(directory='app/templates')

from app.routes.api import public_router, router as auth_router
app.include_router(public_router)
app.include_router(auth_router)


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name='index.html',
        context={'app_name': config.get('app.name', '秒读课堂'), 'version': '2.3.1'},
    )


def run():
    import uvicorn
    uvicorn.run('app.main:app', host=config.get('app.host', '127.0.0.1'), port=config.get('app.port', 8080))


if __name__ == '__main__':
    run()
