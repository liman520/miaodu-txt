const cheerio = require('cheerio');
const { createClient, decodeResponse, cleanContent } = require('./index');

const SOURCE = '人民网';
// 人民网主站可访问，从主站提取时政类文章链接
const LIST_URL = 'http://www.people.com.cn/';

async function scrape() {
  const client = createClient();
  const articles = [];

  // 1. 从主站获取文章列表
  const listResp = await client.get(LIST_URL);
  const listHtml = decodeResponse(listResp);
  const $ = cheerio.load(listHtml);

  // 提取时政类文章链接（politics, cpc, world, opinion频道）
  const links = [];
  $('a').each(function () {
    const href = $(this).attr('href') || '';
    const title = $(this).text().trim();
    // 匹配 people.com.cn 的文章URL
    if (title.length > 8 && /people\.com\.cn\/n1\/\d{4}\/\d{4}\//.test(href)) {
      // 优先时政相关频道
      const isPolitics = /politics|cpc|world|opinion|leaders/.test(href);
      if (isPolitics) {
        const fullUrl = href.startsWith('http') ? href : `http:${href}`;
        if (!links.find((l) => l.url === fullUrl)) {
          links.push({ title, url: fullUrl });
        }
      }
    }
  });

  // 2. 获取每篇文章的详细内容（最多10篇）
  const toFetch = links.slice(0, 10);
  for (const link of toFetch) {
    try {
      const detailResp = await client.get(link.url, {
        headers: { Referer: 'http://www.people.com.cn/' },
      });
      const detailHtml = decodeResponse(detailResp);
      const $d = cheerio.load(detailHtml);

      // 人民网文章内容选择器
      let contentHtml =
        $d('.rm_txt_con').html() ||
        $d('#rwb_zw').html() ||
        $d('.text_con').html() ||
        $d('.content').html() ||
        $d('article').html() ||
        $d('.article_content').html() ||
        '';

      // 如果没找到特定容器，尝试从正文段落提取
      if (!contentHtml || contentHtml.length < 200) {
        const paragraphs = [];
        $d('p').each(function () {
          const text = $d(this).text().trim();
          if (text.length > 30) paragraphs.push(`<p>${text}</p>`);
        });
        if (paragraphs.length > 2) contentHtml = paragraphs.join('');
      }

      // 提取作者
      let author = '';
      const authorMatch = detailHtml.match(/(?:责任编辑|作者|来源|编辑)[：:]\s*([^\s<\n]+)/);
      if (authorMatch) author = authorMatch[1].trim();
      if (!author) {
        author = $d('.author, .editor, [class*="author"]').first().text().trim();
      }

      const content = cleanContent(contentHtml);
      if (content.length > 100) {
        articles.push({
          title: link.title,
          author: author || '人民网',
          content,
          source: SOURCE,
          category: '时政热点',
        });
      }
    } catch (err) {
      console.warn(`[人民网] 跳过: ${link.title} - ${err.message}`);
    }
    await new Promise((r) => setTimeout(r, 500));
  }

  return articles;
}

module.exports = { scrape };
