const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const db = require('../db');

const STORAGE_STATE_PATH = path.join(__dirname, '..', 'data', 'browser-state.json');
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'data', 'screenshots');

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

async function getBrowser() {
  const stateExists = fs.existsSync(STORAGE_STATE_PATH);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    storageState: stateExists ? STORAGE_STATE_PATH : undefined,
    viewport: { width: 1280, height: 800 },
  });
  return { browser, context };
}

async function saveState(context) {
  try {
    await context.storageState({ path: STORAGE_STATE_PATH });
  } catch (e) {
    console.warn('[发布] 保存浏览器状态失败:', e.message);
  }
}

async function publishArticle(article) {
  const settings = db.getSettings();
  const publishUrl = settings.publish_url || 'http://localhost:3000/';
  const delay = parseInt(settings.auto_publish_delay) || 3;

  const { browser, context } = await getBrowser();
  const page = await context.newPage();

  try {
    // Navigate to knowledge assistant page
    const targetUrl = new URL('knowledge/assistant', publishUrl).href;
    console.log(`[发布] 导航到: ${targetUrl}`);
    await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Click "写作助手" button/link if present
    const writingAssistant = page.locator('text=写作助手').first();
    if (await writingAssistant.isVisible({ timeout: 5000 }).catch(() => false)) {
      await writingAssistant.click();
      await page.waitForTimeout(1000);
    }

    // Fill title
    const titleInput = page.locator('input[placeholder*="标题"], input[name*="title"], .title-input input, #title').first();
    await titleInput.waitFor({ timeout: 10000 });
    await titleInput.fill(article.title);

    // Select category
    const categorySelect = page.locator('select[name*="category"], .category-select, [class*="category"] select').first();
    if (await categorySelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      await categorySelect.selectOption({ label: article.category });
    } else {
      // Try clicking category dropdown
      const categoryTrigger = page.locator('[class*="category"], text=分类').first();
      if (await categoryTrigger.isVisible({ timeout: 3000 }).catch(() => false)) {
        await categoryTrigger.click();
        await page.waitForTimeout(500);
        const categoryOption = page.locator(`text=${article.category}`).first();
        if (await categoryOption.isVisible({ timeout: 3000 }).catch(() => false)) {
          await categoryOption.click();
        }
      }
    }

    // Fill author
    const authorInput = page.locator('input[placeholder*="作者"], input[name*="author"], .author-input input').first();
    if (await authorInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await authorInput.fill(article.author || '');
    }

    // Fill content in rich text editor (contenteditable div)
    const editor = page.locator('[contenteditable="true"], .ql-editor, .ProseMirror, .editor-content, textarea[name*="content"]').first();
    await editor.waitFor({ timeout: 10000 });
    await editor.click();
    await page.waitForTimeout(300);

    // Split content into paragraphs and type with Enter between them
    const paragraphs = article.content.split('\n\n').filter((p) => p.trim());
    for (let i = 0; i < paragraphs.length; i++) {
      await page.keyboard.type(paragraphs[i].trim(), { delay: 5 });
      if (i < paragraphs.length - 1) {
        await page.keyboard.press('Enter');
        await page.keyboard.press('Enter');
      }
    }

    await page.waitForTimeout(1000);

    // Click "存为草稿" button
    const draftBtn = page.locator('button:has-text("存为草稿"), button:has-text("保存草稿"), button:has-text("Save Draft"), button:has-text("保存")').first();
    await draftBtn.click();

    // Wait for success indication
    await page.waitForTimeout(3000);

    // Save browser state for reuse
    await saveState(context);

    console.log(`[发布] 成功: ${article.title}`);
    return { success: true, articleId: article.id };
  } catch (err) {
    // Save screenshot on failure
    const screenshotPath = path.join(SCREENSHOTS_DIR, `error-${article.id}-${Date.now()}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
    console.error(`[发布] 失败: ${article.title} - ${err.message}`);
    throw err;
  } finally {
    await browser.close();
  }
}

async function publishBatch() {
  const dbModule = require('../db');
  const settings = dbModule.getSettings();
  const delay = parseInt(settings.auto_publish_delay) || 3;

  // Get all approved articles
  const { articles } = dbModule.getArticles({ status: 'approved', page: 1, pageSize: 100 });

  if (articles.length === 0) {
    return { message: '没有待发布的文章', published: 0 };
  }

  let published = 0;
  const errors = [];

  for (const article of articles) {
    try {
      await publishArticle(article);
      dbModule.updateStatus(article.id, 'published');
      published++;
      // Wait between publishes
      await new Promise((r) => setTimeout(r, delay * 1000));
    } catch (err) {
      errors.push({ id: article.id, title: article.title, error: err.message });
    }
  }

  return { published, total: articles.length, errors };
}

module.exports = { publishArticle, publishBatch };
