const express = require('express');
const cors = require('cors');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const path = require('path');
const db = require('./db');

const app = express();
const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'news-platform-secret-key-2024';

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// Initialize database
db.init();

// ── Auth middleware ──
function authMiddleware(req, res, next) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.status(401).json({ error: '未登录' });
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'Token无效或已过期' });
  }
}

// ── Auth routes ──
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) return res.status(400).json({ error: '请输入用户名和密码' });

  const user = db.findUser(username);
  if (!user || !bcrypt.compareSync(password, user.password)) {
    return res.status(401).json({ error: '用户名或密码错误' });
  }

  const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '7d' });
  res.json({ token, username: user.username });
});

// ── Articles routes ──
app.get('/api/articles', authMiddleware, (req, res) => {
  const { status, page = 1, pageSize = 20 } = req.query;
  const result = db.getArticles({ status, page: Number(page), pageSize: Number(pageSize) });
  res.json(result);
});

app.get('/api/articles/:id', authMiddleware, (req, res) => {
  const article = db.getArticle(Number(req.params.id));
  if (!article) return res.status(404).json({ error: '文章不存在' });
  res.json(article);
});

app.put('/api/articles/:id/approve', authMiddleware, (req, res) => {
  db.updateStatus(Number(req.params.id), 'approved');
  res.json({ success: true });
});

app.put('/api/articles/:id/reject', authMiddleware, (req, res) => {
  db.updateStatus(Number(req.params.id), 'rejected');
  res.json({ success: true });
});

app.put('/api/articles/:id/category', authMiddleware, (req, res) => {
  const { category } = req.body;
  if (!category) return res.status(400).json({ error: '请选择分类' });
  db.updateCategory(Number(req.params.id), category);
  res.json({ success: true });
});

// ── Scrape routes ──
let scrapeStatus = { running: false, lastRun: null, results: null };

app.post('/api/scrape', authMiddleware, async (req, res) => {
  if (scrapeStatus.running) return res.status(409).json({ error: '采集任务正在运行中' });
  const { source } = req.body;
  scrapeStatus.running = true;
  scrapeStatus.lastRun = new Date().toISOString();

  // Run in background
  const scrapers = require('./scrapers');
  scrapers
    .scrapeAll(source)
    .then((results) => {
      scrapeStatus.results = results;
      scrapeStatus.running = false;
    })
    .catch((err) => {
      scrapeStatus.results = { error: err.message };
      scrapeStatus.running = false;
    });

  res.json({ message: '采集任务已启动' });
});

app.get('/api/scrape/status', authMiddleware, (req, res) => {
  res.json(scrapeStatus);
});

// ── Publish routes ──
let publishStatus = { running: false, lastRun: null, results: null };

app.post('/api/publish/:id', authMiddleware, async (req, res) => {
  const article = db.getArticle(Number(req.params.id));
  if (!article) return res.status(404).json({ error: '文章不存在' });
  if (article.status !== 'approved') return res.status(400).json({ error: '只有待发布状态的文章才能发布' });

  publishStatus.running = true;
  const publisher = require('./publisher/playwright');
  publisher
    .publishArticle(article)
    .then(() => {
      db.updateStatus(article.id, 'published');
      publishStatus.running = false;
      publishStatus.lastRun = new Date().toISOString();
    })
    .catch((err) => {
      publishStatus.running = false;
      publishStatus.results = { error: err.message };
    });

  res.json({ message: '发布任务已启动' });
});

app.post('/api/publish/batch', authMiddleware, async (req, res) => {
  if (publishStatus.running) return res.status(409).json({ error: '发布任务正在运行中' });

  publishStatus.running = true;
  publishStatus.lastRun = new Date().toISOString();

  const publisher = require('./publisher/playwright');
  publisher
    .publishBatch()
    .then((results) => {
      publishStatus.results = results;
      publishStatus.running = false;
    })
    .catch((err) => {
      publishStatus.results = { error: err.message };
      publishStatus.running = false;
    });

  res.json({ message: '批量发布任务已启动' });
});

app.get('/api/publish/status', authMiddleware, (req, res) => {
  res.json(publishStatus);
});

// ── Settings routes ──
app.get('/api/settings', authMiddleware, (req, res) => {
  res.json(db.getSettings());
});

app.put('/api/settings', authMiddleware, (req, res) => {
  for (const [key, value] of Object.entries(req.body)) {
    db.updateSetting(key, value);
  }
  res.json({ success: true });
});

// ── SPA fallback ──
app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'Not found' });
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`🚀 新闻管理平台已启动: http://localhost:${PORT}`);
});
