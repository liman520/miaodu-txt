const cheerio = require('cheerio');
const { createClient, decodeResponse, cleanContent } = require('./index');

const SOURCE = '新华网';
// 新华网有JSON数据接口，直接获取文章列表
const API_URL = 'http://www.news.cn/politicspro/json/xh_politicsproDepth.js';

async function scrape() {
  const client = createClient();
  const articles = [];

  // 1. 通过JSON接口获取文章列表
  const listResp = await client.get(API_URL);
  const listText = decodeResponse(listResp);

  // 解析JSONP格式: var politicsproDepth = { ... };
  const jsonMatch = listText.match(/var\s+\w+\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
  if (!jsonMatch) {
    throw new Error('无法解析新华网JSON数据');
  }

  const data = JSON.parse(jsonMatch[1]);
  const list = data?.data?.list || [];

  // 提取文章链接（最多10篇）
  const links = [];
  for (const item of list) {
    if (links.length >= 10) break;
    const detail = item.artDetails?.[0];
    if (detail?.title && detail?.url) {
      links.push({ title: detail.title.trim(), url: detail.url });
    }
  }

  // 2. 获取每篇文章的详细内容
  for (const link of links) {
    try {
      const detailResp = await client.get(link.url);
      const detailHtml = decodeResponse(detailResp);
      const $ = cheerio.load(detailHtml);

      // 新华网文章内容在 #detail 或 .article-content 中
      let contentHtml =
        $('#detail').html() ||
        $('.article-content').html() ||
        $('#content').html() ||
        '';

      // 提取作者/来源
      let author = '';
      const sourceEl = $('.header-time .source, .source, [class*="source"]').first();
      if (sourceEl.length) author = sourceEl.text().trim().replace(/^来源[：:]\s*/, '');
      if (!author) {
        const match = detailHtml.match(/(?:来源|作者|编辑)[：:]\s*([^<\n]+)/);
        if (match) author = match[1].trim();
      }

      const content = cleanContent(contentHtml);
      if (content.length > 100) {
        articles.push({
          title: link.title,
          author: author || '新华网',
          content,
          source: SOURCE,
          category: '时政热点',
        });
      }
    } catch (err) {
      console.warn(`[新华网] 跳过: ${link.title} - ${err.message}`);
    }
    await new Promise((r) => setTimeout(r, 500));
  }

  return articles;
}

module.exports = { scrape };
