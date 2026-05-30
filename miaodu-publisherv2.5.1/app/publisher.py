"""
MiaoDuAI Workflow - 自动发布模块
通过Selenium驱动本地Chrome浏览器，1:1模拟真人操作
登录秒读课堂后台，完成文章自动化发布
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from . import database as db
from . import config as cfg

logger = logging.getLogger("miaoduai.publisher")

# Selenium相关导入（延迟导入，无浏览器时不影响其他模块）
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException,
        ElementClickInterceptedException, WebDriverException
    )
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class ArticlePublisher:
    """文章自动发布器，通过Selenium控制Chrome完成发文"""

    def __init__(self):
        self.config = cfg.load_config()
        self.selenium_cfg = self.config.get("selenium", {})
        self.driver = None
        self._running = False

    def _create_driver(self):
        """创建Chrome WebDriver实例"""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium未安装，请运行 install.bat 安装依赖")

        options = ChromeOptions()

        # 使用本地已登录的Chrome用户数据（继承Cookies和保存的密码）
        import os
        chrome_user_data = os.path.expanduser(
            "~/AppData/Local/Google/Chrome/User Data"
        )
        if os.path.exists(chrome_user_data):
            options.add_argument(f"--user-data-dir={chrome_user_data}")
            options.add_argument("--profile-directory=Default")

        if self.selenium_cfg.get("headless"):
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--start-maximized")

        # 自动匹配ChromeDriver
        try:
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            # 尝试系统PATH中的chromedriver
            driver = webdriver.Chrome(options=options)

        # 隐藏自动化特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = {runtime: {}};
            """
        })

        return driver

    async def publish_single(self, article: dict) -> dict:
        """
        发布单篇文章到秒读课堂后台
        article 需包含: title, content, category, author, source
        返回 {"success": bool, "message": str}
        """
        url = self.selenium_cfg.get("miaoduai_url", "https://miaoduai.com/v2/")

        try:
            if not self.driver:
                self.driver = self._create_driver()

            logger.info(f"开始发布: {article['title'][:30]}...")

            # 步骤1: 访问后台（利用本地已保存的Cookies自动登录）
            self.driver.get(url)
            await asyncio.sleep(3)

            # 步骤2: 点击【进入备课工作台】
            try:
                workbench_btn = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(),'进入备课工作台') or contains(text(),'工作台')]")
                    )
                )
                workbench_btn.click()
                await asyncio.sleep(3)
            except TimeoutException:
                # 可能已经在工作台页面
                logger.info("未找到工作台按钮，可能已在工作台页面")

            # 步骤3: 点击【我的上传】
            try:
                upload_nav = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(),'我的上传') or contains(text(),'上传管理')]")
                    )
                )
                upload_nav.click()
                await asyncio.sleep(2)
            except TimeoutException:
                logger.warning("未找到'我的上传'导航项")

            # 步骤4: 点击【上传新文章】
            try:
                new_article_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(),'上传新文章') or contains(text(),'新建文章') or contains(text(),'发布文章')]")
                    )
                )
                new_article_btn.click()
                await asyncio.sleep(2)
            except TimeoutException:
                logger.warning("未找到'上传新文章'按钮")

            # 步骤5: 填充表单

            # 5a. 选择分类板块
            category = article.get("category", "写作素材")
            try:
                # 尝试Select下拉框
                select_elem = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "select[name*='category'], select[name*='type'], select.category, #category")
                    )
                )
                select = Select(select_elem)
                # 尝试按文本匹配
                for option in select.options:
                    if category in option.text or option.text in category:
                        select.select_by_visible_text(option.text)
                        break
            except (TimeoutException, NoSuchElementException):
                # 尝试Radio按钮或自定义下拉
                try:
                    self.driver.find_element(
                        By.XPATH, f"//*[contains(text(),'{category}')]"
                    ).click()
                except NoSuchElementException:
                    logger.warning(f"未找到分类选择器: {category}")

            await asyncio.sleep(1)

            # 5b. 填写标题
            try:
                title_input = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input[name*='title'], input[placeholder*='标题'], #title, .title-input")
                    )
                )
                title_input.clear()
                title_input.send_keys(article["title"])
            except TimeoutException:
                # 尝试用XPath
                try:
                    self.driver.find_element(
                        By.XPATH, "//input[contains(@placeholder,'标题')]"
                    ).send_keys(article["title"])
                except NoSuchElementException:
                    logger.error("未找到标题输入框")

            # 5c. 填写正文
            try:
                # 可能是textarea或富文本编辑器
                content_elem = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR,
                         "textarea[name*='content'], textarea[placeholder*='正文'], "
                         "#content, .content-input, .ql-editor, .CodeMirror")
                    )
                )
                content_elem.clear()
                content_elem.send_keys(article["content"])
            except TimeoutException:
                # 尝试iframe中的编辑器
                try:
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        self.driver.switch_to.frame(iframe)
                        try:
                            body = self.driver.find_element(By.TAG_NAME, "body")
                            body.clear()
                            body.send_keys(article["content"])
                            self.driver.switch_to.default_content()
                            break
                        except Exception:
                            self.driver.switch_to.default_content()
                            continue
                except Exception:
                    logger.error("未找到正文输入区域")

            # 5d. 填写作者（可选）
            author = article.get("author", "")
            if author:
                try:
                    author_input = self.driver.find_element(
                        By.CSS_SELECTOR, "input[name*='author'], input[placeholder*='作者']"
                    )
                    author_input.clear()
                    author_input.send_keys(author)
                except NoSuchElementException:
                    pass

            # 5e. 填写来源（可选）
            source = article.get("source", "")
            if source:
                try:
                    source_input = self.driver.find_element(
                        By.CSS_SELECTOR, "input[name*='source'], input[placeholder*='来源'], input[placeholder*='出处']"
                    )
                    source_input.clear()
                    source_input.send_keys(source)
                except NoSuchElementException:
                    pass

            await asyncio.sleep(1)

            # 步骤6: 提交发布
            try:
                submit_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH,
                         "//*[contains(text(),'提交') or contains(text(),'发布') or contains(text(),'保存')]")
                    )
                )
                submit_btn.click()
                await asyncio.sleep(3)
            except TimeoutException:
                logger.error("未找到提交按钮")
                return {"success": False, "message": "未找到提交按钮"}

            # 更新文章状态
            await db.update_article_status(
                article["id"], "published", "自动发布成功"
            )

            # 更新统计
            today = datetime.now().strftime("%Y-%m-%d")
            stat_db = await db.get_db()
            try:
                await stat_db.execute(
                    """INSERT INTO daily_stats (stat_date, category, published)
                       VALUES (?, ?, 1)
                       ON CONFLICT(stat_date, category)
                       DO UPDATE SET published = published + 1""",
                    (today, article["category"]),
                )
                await stat_db.commit()
            finally:
                await stat_db.close()

            await db.add_log(
                f"发布成功: [{article['category']}] {article['title'][:30]}",
                "publisher", "INFO"
            )

            return {"success": True, "message": "发布成功"}

        except WebDriverException as e:
            err_msg = f"浏览器异常: {str(e)[:200]}"
            logger.error(err_msg)
            await db.add_log(err_msg, "publisher", "ERROR")
            return {"success": False, "message": err_msg}
        except Exception as e:
            err_msg = f"发布异常: {str(e)[:200]}"
            logger.error(err_msg)
            await db.add_log(err_msg, "publisher", "ERROR")
            return {"success": False, "message": err_msg}

    async def run_batch_publish(self) -> dict:
        """
        批量发布所有ready状态的文章
        返回发布统计
        """
        self._running = True
        articles = await db.get_articles(status="ready")
        if not articles:
            logger.info("没有待发布的文章")
            return {"total": 0, "success": 0, "failed": 0}

        stats = {"total": len(articles), "success": 0, "failed": 0}

        for article in articles:
            if not self._running:
                break

            result = await self.publish_single(article)
            if result["success"]:
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # 每篇发布间隔，模拟真人操作节奏
            await asyncio.sleep(5)

        await db.add_log(
            f"批量发布完成: 总计{stats['total']}篇, 成功{stats['success']}篇, 失败{stats['failed']}篇",
            "publisher", "INFO"
        )

        self.close()
        return stats

    def close(self):
        """关闭浏览器和WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def stop(self):
        """停止发布流程"""
        self._running = False
