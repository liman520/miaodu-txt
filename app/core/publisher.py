# 秒读课堂 - 文章发布器（浏览器自动化版）
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 六大板块名称映射（平台页面上的分类名称）
CATEGORY_MAP = {
    "写作素材": "写作素材",
    "古诗古文": "古诗古文",
    "时政热点": "时政热点",
    "家国情怀": "家国情怀",
    "科技人文": "科技人文",
    "思辨阅读": "思辨阅读",
}


class Publisher:
    """文章发布器 - 通过浏览器模拟真人操作发布到平台"""

    def __init__(self, config):
        self.config = config
        if hasattr(config, 'get'):
            self.platform_url = config.get('platform.url', 'https://miaoduai.com/v2/')
            self.article_interval = config.get('publish.article_interval', 60)
            self.chrome_user_data_dir = config.get('platform.chrome_user_data_dir', '')
        else:
            self.platform_url = 'https://miaoduai.com/v2/'
            self.article_interval = 60
            self.chrome_user_data_dir = ''
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        """确保浏览器实例存在"""
        if self._browser is not None:
            return True
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

            launch_args = [
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-blink-features=AutomationControlled',
            ]

            # 使用持久化上下文以复用已保存的登录状态
            user_data_dir = self.chrome_user_data_dir or './chrome_data'
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                channel='chrome',
                args=launch_args,
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
                ignore_https_errors=True,
            )
            self._browser = self._context
            logger.info("浏览器启动成功")
            return True
        except ImportError:
            logger.error("未安装 playwright，请运行: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            return False

    async def _close_browser(self):
        """关闭浏览器"""
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._browser = None
            self._context = None

    async def publish_article(self, article: dict) -> bool:
        """发布单篇文章到平台（浏览器模拟操作）"""
        if not await self._ensure_browser():
            return False

        title = article.get("title", "")
        content = article.get("content", "")
        author = article.get("author", "")
        source_url = article.get("source_url", "")
        category = article.get("category", "")

        platform_category = CATEGORY_MAP.get(category, category)

        try:
            page = await self._context.new_page()

            # Step 1: 访问平台后台
            logger.info(f"正在访问平台: {self.platform_url}")
            await page.goto(self.platform_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # Step 2: 点击"进入备课工作台"
            logger.info("查找并点击【进入备课工作台】...")
            workbench_btn = page.locator('text=进入备课工作台')
            if await workbench_btn.count() > 0:
                await workbench_btn.first.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                await asyncio.sleep(2)
            else:
                # 尝试其他可能的按钮文本
                for alt_text in ['备课工作台', '进入工作台', '工作台']:
                    alt_btn = page.locator(f'text={alt_text}')
                    if await alt_btn.count() > 0:
                        await alt_btn.first.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await asyncio.sleep(2)
                        break

            # Step 3: 点击"我的上传"
            logger.info("查找并点击【我的上传】...")
            upload_tab = page.locator('text=我的上传')
            if await upload_tab.count() > 0:
                await upload_tab.first.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                await asyncio.sleep(2)
            else:
                for alt_text in ['上传管理', '我的文章', '内容管理']:
                    alt_tab = page.locator(f'text={alt_text}')
                    if await alt_tab.count() > 0:
                        await alt_tab.first.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await asyncio.sleep(2)
                        break

            # Step 4: 点击"上传新文章"
            logger.info("查找并点击【上传新文章】...")
            new_btn = page.locator('text=上传新文章')
            if await new_btn.count() > 0:
                await new_btn.first.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                await asyncio.sleep(2)
            else:
                for alt_text in ['新建文章', '发布文章', '新增文章', '写文章']:
                    alt_btn = page.locator(f'text={alt_text}')
                    if await alt_btn.count() > 0:
                        await alt_btn.first.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await asyncio.sleep(2)
                        break

            # Step 5: 填写表单
            logger.info(f"填写文章信息: {title[:30]}...")

            # 填写标题
            title_input = page.locator('input[placeholder*="标题"], input[name*="title"], #title, [data-field="title"] input')
            if await title_input.count() > 0:
                await title_input.first.fill(title)
            else:
                # 尝试通过标签定位
                title_label = page.locator('label:has-text("标题")')
                if await title_label.count() > 0:
                    label_for = await title_label.first.get_attribute('for')
                    if label_for:
                        await page.locator(f'#{label_for}').fill(title)
                    else:
                        input_near = page.locator('label:has-text("标题") + input, label:has-text("标题") ~ input')
                        if await input_near.count() > 0:
                            await input_near.first.fill(title)

            # 填写作者（可选）
            if author:
                author_input = page.locator('input[placeholder*="作者"], input[name*="author"], #author, [data-field="author"] input')
                if await author_input.count() > 0:
                    await author_input.first.fill(author)

            # 选择分类
            logger.info(f"选择分类: {platform_category}")
            category_select = page.locator('select[name*="category"], select[name*="板块"], #category, [data-field="category"] select')
            if await category_select.count() > 0:
                await category_select.first.select_option(label=platform_category)
            else:
                # 尝试点击下拉框再选择
                category_trigger = page.locator('[data-field="category"], .category-select, .ant-select, [class*="select"]:near(:text("分类")), [class*="select"]:near(:text("板块"))')
                if await category_trigger.count() > 0:
                    await category_trigger.first.click()
                    await asyncio.sleep(0.5)
                    option = page.locator(f'.ant-select-item:has-text("{platform_category}"), li:has-text("{platform_category}"), [role="option"]:has-text("{platform_category}")')
                    if await option.count() > 0:
                        await option.first.click()
                    else:
                        # 直接输入
                        await category_trigger.first.fill(platform_category)
                        await asyncio.sleep(0.5)
                        await page.keyboard.press('Enter')

            # 填写正文
            logger.info("填写正文内容...")
            content_input = page.locator('textarea, [contenteditable="true"], .ql-editor, .w-e-text, #content, [data-field="content"] textarea, .editor-content, .article-content')
            if await content_input.count() > 0:
                await content_input.first.fill(content)
            else:
                # 尝试 iframe 编辑器
                editor_frame = page.frame_locator('iframe[id*="editor"], iframe[class*="editor"], iframe[src*="editor"]')
                if editor_frame:
                    body = editor_frame.locator('body')
                    if await body.count() > 0:
                        await body.fill(content)

            # 填写来源（可选）
            if source_url:
                source_input = page.locator('input[placeholder*="来源"], input[placeholder*="出处"], input[name*="source"], #source, [data-field="source"] input')
                if await source_input.count() > 0:
                    await source_input.first.fill(source_url)

            await asyncio.sleep(1)

            # Step 6: 提交
            logger.info("提交文章...")
            submit_btn = page.locator('button:has-text("提交"), button:has-text("发布"), button:has-text("上传"), button[type="submit"]')
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
            else:
                # 尝试通过 class 定位
                submit_btn = page.locator('.submit-btn, .publish-btn, .btn-primary:has-text("提交")')
                if await submit_btn.count() > 0:
                    await submit_btn.first.click()

            # 等待提交完成
            await asyncio.sleep(3)
            await page.wait_for_load_state('networkidle', timeout=15000)

            # 检查是否有成功提示
            success_indicators = page.locator('text=成功, text=已上传, text=已发布, .success, .ant-message-success')
            if await success_indicators.count() > 0:
                logger.info(f"✅ 文章发布成功: {title[:30]}...")
                await page.close()
                return True

            # 检查是否有错误提示
            error_indicators = page.locator('text=失败, text=错误, .error, .ant-message-error')
            if await error_indicators.count() > 0:
                error_text = await error_indicators.first.text_content()
                logger.error(f"发布失败: {error_text}")
                await page.close()
                return False

            # 没有明确提示，假设成功
            logger.info(f"文章已提交（无明确状态提示）: {title[:30]}...")
            await page.close()
            return True

        except Exception as e:
            logger.error(f"发布异常: {e}")
            try:
                await page.close()
            except Exception:
                pass
            return False

    async def publish_batch(self, articles: list) -> list:
        """批量发布文章"""
        results = []
        for i, article in enumerate(articles):
            logger.info(f"发布进度: {i+1}/{len(articles)}")
            success = await self.publish_article(article)
            results.append({"title": article.get("title", ""), "success": success})
            if i < len(articles) - 1:
                interval = self.article_interval
                logger.info(f"等待 {interval} 秒后发布下一篇...")
                await asyncio.sleep(interval)
        return results

    async def cleanup(self):
        """清理浏览器资源"""
        await self._close_browser()
