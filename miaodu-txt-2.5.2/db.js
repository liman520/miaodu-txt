const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const path = require('path');
const fs = require('fs');

const DB_PATH = path.join(__dirname, 'data', 'news.db');

// Ensure data directory exists
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

const db = new Database(DB_PATH);

// Enable WAL mode for better concurrency
db.pragma('journal_mode = WAL');

function init() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS articles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      author TEXT,
      content TEXT NOT NULL,
      source TEXT,
      category TEXT DEFAULT '时政热点',
      status TEXT DEFAULT 'pending',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      reviewed_at DATETIME,
      published_at DATETIME
    );

    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
    CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
    CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at DESC);
  `);

  // Insert default admin user if not exists
  const existingUser = db.prepare('SELECT id FROM users WHERE username = ?').get('admin');
  if (!existingUser) {
    const hash = bcrypt.hashSync('123456', 10);
    db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').run('admin', hash);
  }

  // Insert default settings if not exists
  const defaultSettings = {
    publish_url: 'http://localhost:3000/',
    auto_publish_delay: '3',
  };
  const insertSetting = db.prepare('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)');
  for (const [key, value] of Object.entries(defaultSettings)) {
    insertSetting.run(key, value);
  }
}

// ── User operations ──
const findUser = (username) => db.prepare('SELECT * FROM users WHERE username = ?').get(username);

// ── Article operations ──
const getArticles = ({ status, page = 1, pageSize = 20 }) => {
  let sql = 'SELECT * FROM articles';
  const params = [];
  if (status) {
    sql += ' WHERE status = ?';
    params.push(status);
  }
  sql += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
  params.push(pageSize, (page - 1) * pageSize);

  let countSql = 'SELECT COUNT(*) as total FROM articles';
  const countParams = [];
  if (status) {
    countSql += ' WHERE status = ?';
    countParams.push(status);
  }

  return {
    articles: db.prepare(sql).all(...params),
    total: db.prepare(countSql).get(...countParams).total,
    page,
    pageSize,
  };
};

const getArticle = (id) => db.prepare('SELECT * FROM articles WHERE id = ?').get(id);

const updateStatus = (id, status) => {
  const timeField = status === 'published' ? 'published_at' : 'reviewed_at';
  return db.prepare(`UPDATE articles SET status = ?, ${timeField} = datetime('now') WHERE id = ?`).run(status, id);
};

const updateCategory = (id, category) => {
  return db.prepare('UPDATE articles SET category = ? WHERE id = ?').run(category, id);
};

const insertArticle = (article) => {
  // Check duplicate by title
  const existing = db.prepare('SELECT id FROM articles WHERE title = ?').get(article.title);
  if (existing) return null;

  return db.prepare(
    'INSERT INTO articles (title, author, content, source, category, status) VALUES (?, ?, ?, ?, ?, ?)'
  ).run(article.title, article.author || '', article.content, article.source, article.category || '时政热点', 'pending');
};

// ── Settings operations ──
const getSettings = () => {
  const rows = db.prepare('SELECT * FROM settings').all();
  const result = {};
  for (const row of rows) {
    result[row.key] = row.value;
  }
  return result;
};

const updateSetting = (key, value) => {
  return db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)').run(key, String(value));
};

module.exports = {
  db,
  init,
  findUser,
  getArticles,
  getArticle,
  updateStatus,
  updateCategory,
  insertArticle,
  getSettings,
  updateSetting,
};
