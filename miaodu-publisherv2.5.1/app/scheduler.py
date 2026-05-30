"""
MiaoDuAI Workflow - 定时调度模块
使用APScheduler实现定时采集和定时发布
支持双轨制激活：定时自动模式 + 手动触发模式
"""
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import config as cfg
from . import database as db
from .collector import ArticleCollector
from .publisher import ArticlePublisher

logger = logging.getLogger("miaoduai.scheduler")


class TaskScheduler:
    """任务调度器，管理定时采集和发布任务"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.collector = ArticleCollector()
        self.publisher = ArticlePublisher()
        self._setup_done = False

    def setup(self):
        """根据配置初始化定时任务"""
        config = cfg.load_config()
        schedule_cfg = config.get("auto_schedule", {})

        # 移除旧任务
        if self._setup_done:
            try:
                self.scheduler.remove_all_jobs()
            except Exception:
                pass

        # 定时采集任务
        collect_cron = schedule_cfg.get("collect_cron", "0 6 * * *")
        if collect_cron:
            parts = collect_cron.split()
            if len(parts) == 5:
                self.scheduler.add_job(
                    self._run_collect,
                    CronTrigger(
                        hour=int(parts[1]),
                        minute=int(parts[0]),
                        timezone="Asia/Shanghai"
                    ),
                    id="auto_collect",
                    name="定时自动采集",
                    replace_existing=True,
                )
                logger.info(f"定时采集任务已配置: 每日 {parts[1]}:{parts[0].zfill(2)}")

        # 定时发布任务
        publish_time = config.get("publish_time", "18:00")
        hour, minute = publish_time.split(":")
        self.scheduler.add_job(
            self._run_publish,
            CronTrigger(
                hour=int(hour),
                minute=int(minute),
                timezone="Asia/Shanghai"
            ),
            id="auto_publish",
            name="定时自动发布",
            replace_existing=True,
        )
        logger.info(f"定时发布任务已配置: 每日 {publish_time}")

        self._setup_done = True

    def start(self):
        """启动调度器"""
        if not self._setup_done:
            self.setup()

        config = cfg.load_config()
        if config.get("auto_schedule", {}).get("enabled", False):
            self.scheduler.start()
            logger.info("定时调度器已启动")
            asyncio.create_task(db.add_log("定时调度器已启动", "scheduler", "INFO"))
        else:
            logger.info("定时调度未启用，手动模式运行")
            asyncio.create_task(db.add_log("系统启动（手动模式）", "scheduler", "INFO"))

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("定时调度器已停止")

    def get_status(self) -> dict:
        """获取调度器状态"""
        jobs = []
        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else "无",
                })

        config = cfg.load_config()
        return {
            "running": self.scheduler.running,
            "auto_enabled": config.get("auto_schedule", {}).get("enabled", False),
            "publish_time": config.get("publish_time", "18:00"),
            "collect_cron": config.get("auto_schedule", {}).get("collect_cron", ""),
            "jobs": jobs,
        }

    async def _run_collect(self):
        """调度器触发的采集任务"""
        logger.info("定时采集任务触发")
        await db.add_log("定时采集任务触发", "scheduler", "INFO")
        try:
            stats = await self.collector.run_collection()
            await db.add_log(
                f"定时采集完成: 抓取{stats['total_fetched']}篇, "
                f"通过{stats['total_passed']}篇",
                "scheduler", "INFO"
            )
        except Exception as e:
            logger.error(f"定时采集异常: {str(e)}")
            await db.add_log(f"定时采集异常: {str(e)}", "scheduler", "ERROR")

    async def _run_publish(self):
        """调度器触发的发布任务"""
        logger.info("定时发布任务触发")
        await db.add_log("定时发布任务触发", "scheduler", "INFO")
        try:
            stats = await self.publisher.run_batch_publish()
            await db.add_log(
                f"定时发布完成: 成功{stats['success']}篇, 失败{stats['failed']}篇",
                "scheduler", "INFO"
            )
        except Exception as e:
            logger.error(f"定时发布异常: {str(e)}")
            await db.add_log(f"定时发布异常: {str(e)}", "scheduler", "ERROR")

    async def manual_collect(self, category: str = None) -> dict:
        """手动触发采集"""
        logger.info(f"手动采集触发, 板块: {category or '全部'}")
        await db.add_log(f"手动采集触发, 板块: {category or '全部'}", "scheduler", "INFO")
        try:
            stats = await self.collector.run_collection(category_filter=category)
            return {"success": True, "stats": stats}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def manual_publish(self) -> dict:
        """手动触发发布"""
        logger.info("手动发布触发")
        await db.add_log("手动发布触发", "scheduler", "INFO")
        try:
            stats = await self.publisher.run_batch_publish()
            return {"success": True, "stats": stats}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_schedule(self, schedule_cfg: dict) -> None:
        """动态更新调度配置"""
        cfg.update_config({"auto_schedule": schedule_cfg})
        self.setup()

        if schedule_cfg.get("enabled") and not self.scheduler.running:
            self.scheduler.start()
        elif not schedule_cfg.get("enabled") and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
