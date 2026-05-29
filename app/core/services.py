"""业务服务层 - v2.3（避免循环导入，使用 asyncio.create_task）"""

import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


async def do_collection(app):
    """执行采集任务（带进度追踪 + 停止支持）"""
    from app.models.database import Article, CollectionSource, TaskLog, get_session

    config = app.state.config
    collector = app.state.collector
    reviewer = app.state.reviewer
    archiver = app.state.archiver
    collect_state = app.state.collect_state

    logger.info("=== 采集任务开始 ===")

    with get_session() as session:
        sources = session.query(CollectionSource).filter(CollectionSource.enabled == True).all()
        if not sources:
            logger.warning("没有启用的采集源")
            collect_state.add_log("没有启用的采集源，任务结束", "warning")
            return

        collect_state.start(total_sources=len(sources))
        collect_state.add_log(f"开始采集，共 {len(sources)} 个采集源", "info")

        start = datetime.now()

        for source in sources:
            # 检查停止请求
            if collect_state.should_stop():
                collect_state.add_log("采集已被用户停止", "warning")
                break

            source_dict = {
                "name": source.name,
                "url": source.url,
                "category": source.category,
                "title_selector": source.title_selector,
                "content_selector": source.content_selector,
                "link_selector": source.link_selector,
            }

            collect_state.update_source(source.name, "connecting")
            collect_state.add_log(f"开始处理采集源：{source.name}", "info")

            # 采集
            collect_state.update_source(source.name, "fetching")
            articles = collector.collect_from_source(source_dict)
            collect_state.add_log(f"从 {source.name} 获取到 {len(articles)} 篇候选文章", "info")

            for i, article_data in enumerate(articles):
                # 检查停止请求
                if collect_state.should_stop():
                    collect_state.add_log("采集已被用户停止", "warning")
                    break

                # 去重
                existing = session.query(Article).filter(
                    Article.content_hash == article_data["content_hash"]
                ).first()
                if existing:
                    collect_state.add_skip()
                    collect_state.add_log(f"跳过重复文章：{article_data['title'][:30]}...", "info")
                    continue

                # 审核
                collect_state.update_source(source.name, "reviewing")
                collect_state.add_log(f"正在审核：{article_data['title'][:30]}...", "info")

                passed, corrected_content, review_log = reviewer.review(
                    article_data["title"], article_data["content"], article_data["category"]
                )

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
                    status="pending" if passed else "rejected",
                    auto_review_passed=passed,
                    auto_review_log=review_log,
                    ai_corrected=corrected_content != article_data["content"],
                )
                session.add(new_article)
                collect_state.add_article(passed)

                if passed:
                    article_data["content"] = corrected_content
                    archiver.archive_article(article_data)
                    collect_state.add_log(f"✅ 审核通过：{article_data['title'][:30]}...", "success")
                else:
                    collect_state.add_log(f"❌ 审核驳回：{article_data['title'][:30]}...", "error")

            # 更新采集源统计
            source.last_collected_at = datetime.utcnow()
            source.total_collected = (source.total_collected or 0) + len(articles)
            collect_state.complete_source()
            collect_state.add_log(f"采集源 {source.name} 处理完成", "info")

        session.flush()

        duration = (datetime.now() - start).total_seconds()

        if collect_state.should_stop():
            msg = f"采集已手动停止：处理了 {collect_state.total_articles} 篇文章"
        else:
            msg = f"采集完成：共 {collect_state.total_articles} 篇，通过 {collect_state.passed_articles} 篇，驳回 {collect_state.rejected_articles} 篇"

        log = TaskLog(
            task_type="collect", status="stopped" if collect_state.should_stop() else "success",
            message=msg,
            duration_seconds=duration,
        )
        session.add(log)

    collect_state.finish(success=not collect_state.should_stop())
    collect_state.add_log(f"采集任务结束（耗时 {duration:.1f} 秒）", "info")
    logger.info(f"=== 采集任务完成 (耗时 {duration:.1f}s) ===")


async def do_publish(app):
    """执行发布"""
    from app.models.database import Article, TaskLog, ArticleStatus, get_session

    config = app.state.config
    publisher = app.state.publisher

    logger.info("=== 发布任务开始 ===")
    start = datetime.now()

    with get_session() as session:
        articles = session.query(Article).filter(
            Article.status == ArticleStatus.APPROVED.value
        ).all()

        if not articles:
            logger.info("没有待发布的文章")
            return

        published_count = 0
        failed_count = 0

        for article in articles:
            article_dict = {
                "title": article.title,
                "content": article.content,
                "author": article.author or "",
                "source_url": article.source_url or "",
                "category": article.category,
            }

            success = await publisher.publish_article(article_dict)

            if success:
                article.status = ArticleStatus.PUBLISHED.value
                article.published_at = datetime.utcnow()
                published_count += 1
            else:
                failed_count += 1

            # 发布间隔
            interval = config.get("publish.article_interval", 60)
            await asyncio.sleep(interval)

        session.flush()

        duration = (datetime.now() - start).total_seconds()
        log = TaskLog(
            task_type="publish", status="success",
            message=f"发布完成: 成功{published_count}篇, 失败{failed_count}篇",
            duration_seconds=duration,
        )
        session.add(log)

    logger.info(f"=== 发布任务完成 (耗时 {duration:.1f}s) ===")
