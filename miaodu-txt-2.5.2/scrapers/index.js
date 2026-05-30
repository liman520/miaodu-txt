const axios = require('axios');
const cheerio = require('cheerio');
const db = require('../db');

const USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

const TIMEOUT = 15000;

// Common HTTP client
function createClient() {
  return axios.create({
    timeout: TIMEOUT,
    headers: {
      'User-Agent': USER_AGENT,
      Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      'Accept-Encoding': 'gzip, deflate',
    },
    responseType: 'arraybuffer',
    responseEncoding: 'utf8',
  });
}

// Decode response with auto charset detection
function decodeResponse(response) {
  const buf = Buffer.from(response.data);
  // Try to detect charset from content-type header
  const contentType = response.headers['content-type'] || '';
  if (contentType.includes('gb2312') || contentType.includes('gbk')) {
    const iconv = require('iconv-lite');
    return iconv.decode(buf, 'gbk');
  }
  // Default utf-8, with fallback
  let text = buf.toString('utf8');
  // If garbled, try gbk
  if (text.includes('\ufffd') && text.includes('%')) {
    try {
      const iconv = require('iconv-lite');
      text = iconv.decode(buf, 'gbk');
    } catch (e) {
      // keep utf8
    }
  }
  return text;
}

// Clean article content
function cleanContent(html) {
  if (!html) return '';
  const $ = cheerio.load(html);

  // Remove unwanted elements
  $('script, style, iframe, ins, .ad, .advertisement, .related, .recommend, .comment, .footer, .header, nav, aside').remove();

  // Get text with paragraph breaks
  let text = '';
  $('p, div, section, article').each(function () {
    const t = $(this).text().trim();
    if (t) text += t + '\n\n';
  });

  if (!text.trim()) {
    text = $.text().trim();
  }

  // Clean up
  text = text
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '') // Remove control chars
    .replace(/\n{3,}/g, '\n\n') // Max 2 consecutive newlines
    .replace(/[ \t]+\n/g, '\n') // Trailing spaces
    .replace(/\n[ \t]+/g, '\n') // Leading spaces
    .replace(/\s{3,}/g, '  ') // Max 2 consecutive spaces
    .replace(/[\u200B\u200C\u200D\uFEFF]/g, '') // Zero-width chars
    .trim();

  return text;
}

// Insert articles into DB, returns count of new articles
function insertArticles(articles) {
  let inserted = 0;
  for (const article of articles) {
    if (!article.title || !article.content) continue;
    const result = db.insertArticle(article);
    if (result) inserted++;
  }
  return inserted;
}

// ── Scraper registry ──
const scraperMap = {
  people: () => require('./people').scrape(),
  xinhua: () => require('./xinhua').scrape(),
  guangming: () => require('./guangming').scrape(),
};

async function scrapeAll(source) {
  const results = {};
  const sources = source ? [source] : Object.keys(scraperMap);

  for (const src of sources) {
    if (!scraperMap[src]) {
      results[src] = { error: `未知来源: ${src}` };
      continue;
    }
    try {
      console.log(`[采集] 开始采集 ${src}...`);
      const articles = await scraperMap[src]();
      const inserted = insertArticles(articles);
      results[src] = { total: articles.length, inserted, skipped: articles.length - inserted };
      console.log(`[采集] ${src} 完成: ${articles.length}篇, 新增${inserted}篇`);
    } catch (err) {
      console.error(`[采集] ${src} 失败:`, err.message);
      results[src] = { error: err.message };
    }
  }
  return results;
}

module.exports = { scrapeAll, createClient, decodeResponse, cleanContent, insertArticles, USER_AGENT };
