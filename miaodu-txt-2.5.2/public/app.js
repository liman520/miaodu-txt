/* ═══════════════════════════════════════════════════
   新闻管理平台 - 前端逻辑
   ═══════════════════════════════════════════════════ */

// ── Auth ──
const token = localStorage.getItem('token');
if (!token) window.location.href = '/';

const headers = {
  'Content-Type': 'application/json',
  Authorization: `Bearer ${token}`,
};

// Display username
document.getElementById('navUser').textContent = localStorage.getItem('username') || '';

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('username');
  window.location.href = '/';
}

// ── State ──
let currentStatus = '';
let currentPage = 1;
let currentArticleId = null;

// ── API Helper ──
async function api(url, options = {}) {
  const resp = await fetch(url, { headers, ...options });
  if (resp.status === 401) {
    logout();
    return;
  }
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || '请求失败');
  return data;
}

// ── Toast ──
function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type} show`;
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// ── Page Navigation ──
function switchPage(page) {
  document.querySelectorAll('.page-section').forEach((s) => s.classList.remove('active'));
  document.querySelectorAll('.sidebar-item').forEach((s) => s.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');
  document.querySelector(`.sidebar-item[data-page="${page}"]`)?.classList.add('active');
  if (page === 'settings') loadSettings();
}

// ── Articles ──
async function loadArticles() {
  const listEl = document.getElementById('articleList');
  listEl.innerHTML = '<div class="loading-overlay"><svg class="spinner" width="24" height="24" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="60" stroke-dashoffset="20"/></svg> 加载中...</div>';

  try {
    const params = new URLSearchParams({ page: currentPage, pageSize: 20 });
    if (currentStatus) params.set('status', currentStatus);
    const data = await api(`/api/articles?${params}`);
    renderArticles(data.articles);
    renderPagination(data.total, data.page, data.pageSize);
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state"><p>加载失败: ${err.message}</p></div>`;
  }
}

function renderArticles(articles) {
  const listEl = document.getElementById('articleList');
  if (!articles.length) {
    listEl.innerHTML = `
      <div class="empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/></svg>
        <p>暂无文章</p>
      </div>`;
    return;
  }

  const statusMap = { pending: '待审核', approved: '待发布', published: '已发布', rejected: '已驳回' };
  const sourceClass = { '人民网': 'people', '新华网': 'xinhua', '光明网': 'guangming' };

  listEl.innerHTML = articles
    .map(
      (a) => `
    <div class="article-card">
      <div class="article-card-header">
        <div class="article-title" onclick="openModal(${a.id})">${escHtml(a.title)}</div>
        <span class="badge badge-${a.status}">${statusMap[a.status] || a.status}</span>
      </div>
      <div class="article-meta">
        <span class="tag tag-source-${sourceClass[a.source] || 'people'}">${escHtml(a.source || '未知')}</span>
        <span class="tag tag-category">${escHtml(a.category || '时政热点')}</span>
        ${a.author ? `<span class="time-text">作者: ${escHtml(a.author)}</span>` : ''}
        <span class="time-text">${formatTime(a.created_at)}</span>
      </div>
      <div class="article-content-preview">${escHtml((a.content || '').substring(0, 200))}</div>
      <div class="article-actions">
        <button class="btn btn-ghost btn-sm" onclick="openModal(${a.id})">查看</button>
        ${a.status === 'pending' ? `
          <button class="btn btn-success btn-sm" onclick="approveArticle(${a.id})">通过</button>
          <button class="btn btn-danger btn-sm" onclick="rejectArticle(${a.id})">驳回</button>
        ` : ''}
        ${a.status === 'approved' ? `
          <button class="btn btn-primary btn-sm" onclick="publishArticle(${a.id})">发布</button>
        ` : ''}
      </div>
    </div>`
    )
    .join('');
}

function renderPagination(total, page, pageSize) {
  const totalPages = Math.ceil(total / pageSize);
  const el = document.getElementById('pagination');
  if (totalPages <= 1) {
    el.innerHTML = '';
    return;
  }

  let html = '';
  html += `<button class="btn btn-ghost btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="goToPage(${page - 1})">‹</button>`;
  for (let i = 1; i <= totalPages; i++) {
    if (totalPages > 7 && i > 2 && i < totalPages - 1 && Math.abs(i - page) > 1) {
      if (html.slice(-3) !== '...') html += `<span class="time-text">...</span>`;
      continue;
    }
    html += `<button class="btn ${i === page ? 'current' : 'btn-ghost'} btn-sm" onclick="goToPage(${i})">${i}</button>`;
  }
  html += `<button class="btn btn-ghost btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="goToPage(${page + 1})">›</button>`;
  el.innerHTML = html;
}

function goToPage(p) {
  currentPage = p;
  loadArticles();
}

function filterByStatus(el, status) {
  document.querySelectorAll('.status-tab').forEach((t) => t.classList.remove('active'));
  el.classList.add('active');
  currentStatus = status;
  currentPage = 1;
  loadArticles();
}

// ── Article Actions ──
async function approveArticle(id) {
  try {
    await api(`/api/articles/${id}/approve`, { method: 'PUT' });
    showToast('已审核通过', 'success');
    loadArticles();
    if (currentArticleId === id) closeModal();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function rejectArticle(id) {
  try {
    await api(`/api/articles/${id}/reject`, { method: 'PUT' });
    showToast('已驳回', 'info');
    loadArticles();
    if (currentArticleId === id) closeModal();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function publishArticle(id) {
  try {
    await api(`/api/publish/${id}`, { method: 'POST' });
    showToast('发布任务已启动', 'info');
    // Poll for completion
    setTimeout(() => loadArticles(), 5000);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Modal ──
async function openModal(id) {
  try {
    const article = await api(`/api/articles/${id}`);
    currentArticleId = id;
    document.getElementById('modalTitle').textContent = article.title;

    const sourceClass = { '人民网': 'people', '新华网': 'xinhua', '光明网': 'guangming' };
    const sourceEl = document.getElementById('modalSource');
    sourceEl.textContent = article.source || '未知';
    sourceEl.className = `tag tag-source-${sourceClass[article.source] || 'people'}`;

    document.getElementById('modalCategory').textContent = article.category || '时政热点';
    document.getElementById('modalCategorySelect').value = article.category || '时政热点';

    const statusMap = { pending: '待审核', approved: '待发布', published: '已发布', rejected: '已驳回' };
    const statusEl = document.getElementById('modalStatus');
    statusEl.textContent = statusMap[article.status];
    statusEl.className = `badge badge-${article.status}`;

    document.getElementById('modalTime').textContent = formatTime(article.created_at);
    document.getElementById('modalContent').innerHTML = (article.content || '').split('\n\n').map((p) => `<p>${escHtml(p)}</p>`).join('');

    // Show/hide action buttons based on status
    document.getElementById('modalApproveBtn').style.display = article.status === 'pending' ? '' : 'none';
    document.getElementById('modalRejectBtn').style.display = article.status === 'pending' ? '' : 'none';

    document.getElementById('modalOverlay').classList.add('active');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('active');
  currentArticleId = null;
}

function closeModalOutside(e) {
  if (e.target === document.getElementById('modalOverlay')) closeModal();
}

async function updateArticleCategory() {
  if (!currentArticleId) return;
  const category = document.getElementById('modalCategorySelect').value;
  try {
    await api(`/api/articles/${currentArticleId}/category`, {
      method: 'PUT',
      body: JSON.stringify({ category }),
    });
    document.getElementById('modalCategory').textContent = category;
    showToast('分类已更新', 'success');
    loadArticles();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function approveFromModal() {
  if (currentArticleId) approveArticle(currentArticleId);
}

function rejectFromModal() {
  if (currentArticleId) rejectArticle(currentArticleId);
}

// ── Scrape ──
async function startScrape() {
  const btn = document.getElementById('scrapeBtn');
  btn.disabled = true;
  btn.innerHTML = '<svg class="spinner" width="16" height="16" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="60" stroke-dashoffset="20"/></svg> 采集中...';
  try {
    const data = await api('/api/scrape', { method: 'POST', body: '{}' });
    showToast(data.message, 'info');
    // Poll status
    const poll = setInterval(async () => {
      try {
        const status = await api('/api/scrape/status');
        if (!status.running) {
          clearInterval(poll);
          btn.disabled = false;
          btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.22-8.56"/><path d="M21 3v6h-6"/></svg> 开始采集';
          if (status.results) {
            const summary = Object.entries(status.results)
              .map(([k, v]) => `${k}: ${v.inserted || 0}篇新增`)
              .join(', ');
            showToast(`采集完成! ${summary}`, 'success');
          }
          loadArticles();
        }
      } catch (e) {}
    }, 2000);
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '开始采集';
    showToast(err.message, 'error');
  }
}

// ── Batch Publish ──
async function batchPublish() {
  const btn = document.getElementById('batchBtn');
  btn.disabled = true;
  try {
    const data = await api('/api/publish/batch', { method: 'POST' });
    showToast(data.message, 'info');
    setTimeout(() => {
      btn.disabled = false;
      loadArticles();
    }, 10000);
  } catch (err) {
    btn.disabled = false;
    showToast(err.message, 'error');
  }
}

// ── Settings ──
async function loadSettings() {
  try {
    const settings = await api('/api/settings');
    document.getElementById('settingPublishUrl').value = settings.publish_url || '';
    document.getElementById('settingDelay').value = settings.auto_publish_delay || 3;
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function saveSettings() {
  try {
    await api('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({
        publish_url: document.getElementById('settingPublishUrl').value,
        auto_publish_delay: document.getElementById('settingDelay').value,
      }),
    });
    showToast('设置已保存', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Helpers ──
function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatTime(t) {
  if (!t) return '';
  const d = new Date(t + (t.includes('Z') || t.includes('+') ? '' : 'Z'));
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ── Keyboard shortcuts ──
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});

// ── Init ──
loadArticles();
