"""任务调度器 - v2.3 增强版"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, collect_callback, publish_callback):
        self.collect_callback = collect_callback
        self.publish_callback = publish_callback
        self.scheduler = AsyncIOScheduler()
        self._collect_job = None
        self._publish_job = None

    def setup_schedules(self, collect_cron: str = "0 8 * * *", publish_cron: str = "0 18 * * *"):
        if self._collect_job:
            try: self.scheduler.remove_job(self._collect_job.id)
            except Exception: pass
        if self._publish_job:
            try: self.scheduler.remove_job(self._publish_job.id)
            except Exception: pass
        try:
            trigger = CronTrigger.from_crontab(collect_cron)
            self._collect_job = self.scheduler.add_job(self._run_collect, trigger, id="auto_collect", name="定时采集", replace_existing=True)
        except ValueError as e:
            logger.error(f"无效的采集 cron 表达式 '{collect_cron}': {e}")
            self._collect_job = self.scheduler.add_job(self._run_collect, CronTrigger(hour=8, minute=0), id="auto_collect", name="定时采集(默认)", replace_existing=True)
        try:
            trigger = CronTrigger.from_crontab(publish_cron)
            self._publish_job = self.scheduler.add_job(self._run_publish, trigger, id="auto_publish", name="定时发布", replace_existing=True)
        except ValueError as e:
            logger.error(f"无效的发布 cron 表达式 '{publish_cron}': {e}")
            self._publish_job = self.scheduler.add_job(self._run_publish, CronTrigger(hour=18, minute=0), id="auto_publish", name="定时发布(默认)", replace_existing=True)
        logger.info(f"定时任务已设置 - 采集: {collect_cron}, 发布: {publish_cron}")

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("调度器已启动")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("调度器已停止")

    def get_jobs_info(self) -> list:
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({"id": job.id, "name": job.name, "next_run": str(job.next_run_time) if job.next_run_time else "未调度"})
        return jobs

    async def _run_collect(self):
        logger.info("=== 定时采集任务开始 ===")
        start = datetime.now()
        try:
            await self.collect_callback()
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"=== 定时采集任务完成 (耗时 {duration:.1f}s) ===")
        except Exception as e:
            logger.error(f"定时采集任务失败: {e}")

    async def _run_publish(self):
        logger.info("=== 定时发布任务开始 ===")
        start = datetime.now()
        try:
            await self.publish_callback()
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"=== 定时发布任务完成 (耗时 {duration:.1f}s) ===")
        except Exception as e:
            logger.error(f"定时发布任务失败: {e}")
