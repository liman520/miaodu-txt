const cheerio = require('cheerio');
const { createClient, decodeResponse, cleanContent } = require('./index');

const SOURCE = '光明网';
// 尝试多个域名
const LIST_URLS = [
  'https://politics.guangming.cn/',
  'http://politics.guangming.cn/',
  'https://www.guangming.cn/',
];

async function scrape() {
  const client = createClient();
  const articles = [];

  // 1. 尝试多个URL获取文章列表
  let listHtml = '';
  let listUrl = '';
  for (const url of LIST_URLS) {
    try {
      const resp = await client.get(url, { timeout: 10000 });
      listHtml = decodeResponse(resp);
      listUrl = url;
      break;
    } catch (e) {
      console.warn(`[光明网] ${url} 不可访问: ${e.message}`);
    }
  }

  if (!listHtml) {
    throw new Error('光明网所有地址均不可访问，请检查网络');
  }

  const $ = cheerio.load(listHtml);

  // 提取文章链接
  const links = [];
  $('a').each(function () {
    const href = $(this).attr('href') || '';
    const title = $(this).text().trim();
    // 匹配光明网文章URL
    if (title.length > 8 && /guangming\.cn\/.*\d{4}.*\.html/.test(href)) {
      const fullUrl = href.startsWith('http') ? href : `https://politics.guangming.cn${href.startsWith('/') ? '' : '/'}${href}`;
      if (!links.find((l) => l.url === fullUrl)) {
        links.push({ title, url: fullUrl });
      }
    }
  });

  // 2. 获取每篇文章的详细内容（最多10篇）
  const toFetch = links.slice(0, 10);
  for (const link of toFetch) {
    try {
      const detailResp = await client.get(link.url);
      const detailHtml = decodeResponse(detailResp);
      const $d = cheerio.load(detailHtml);

      // 光明网文章内容选择器
      let contentHtml =
        $d('.article-content').html() ||
        $d('#articleContent').html() ||
        $d('.content-main').html() ||
        $d('.TRS_Editor').html() ||
        $d('.content').html() ||
        $d('article').html() ||
        '';

      // 提取作者
      let author = '';
      const authorEl = $d('.author, .source, [class*="author"], .info .name').first();
      if (authorEl.length) author = authorEl.text().trim();
      if (!author) {
        const match = detailHtml.match(/(?:作者|来源|责任编辑)[：:]\s*([^<\n]+)/);
        if (match) author = match[1].trim();
      }

      const content = cleanContent(contentHtml);
      if (content.length > 100) {
        articles.push({
          title: link.title,
          author: author || '光明网',
          content,
          source: SOURCE,
          category: '时政热点',
        });
      }
    } catch (err) {
      console.warn(`[光明网] 跳过: ${link.title} - ${err.message}`);
    }
    await new Promise((r) => setTimeout(r, 500));
  }

  return articles;
}

module.exports = { scrape };
