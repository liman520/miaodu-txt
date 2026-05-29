/* ========== 秒读课堂 v2.3 — 前端交互逻辑 ========== */

let authToken = localStorage.getItem('auth_token') || '';
let currentPage = 1;
let collectPollTimer = null;
let publishPollTimer = null;

/* ===== API 工具 ===== */
async function api(url, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
    const resp = await fetch(url, { headers, ...options });
    if (resp.status === 401) { showLogin(); throw new Error('未认证，请重新登录'); }
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || '请求失败');
    }
    return resp.json();
}

function toast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.classList.add('toast-out'); setTimeout(() => el.remove(), 300); }, 3000);
}

function formatDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function statusBadge(status) {
    const map = {
        pending: ['待审核', 'status-pending'],
        approved: ['已通过', 'status-approved'],
        published: ['已发布', 'status-published'],
        rejected: ['已驳回', 'status-rejected']
    };
    const m = map[status] || [status, ''];
    return '<span class="status-badge ' + m[1] + '">' + m[0] + '</span>';
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* ===== 登录/登出 ===== */
function showLogin() {
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('mainApp').style.display = 'none';
    authToken = '';
    localStorage.removeItem('auth_token');
    stopCollectPolling();
    stopPublishPolling();
}

function showApp() {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('mainApp').style.display = 'flex';
}

async function handleLogin(e) {
    e.preventDefault();
    const password = document.getElementById('loginPassword').value;
    try {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        if (!resp.ok) throw new Error('密码错误');
        const data = await resp.json();
        authToken = data.token;
        localStorage.setItem('auth_token', authToken);
        showApp();
        loadDashboard();
        toast('登录成功', 'success');
    } catch (e2) { toast(e2.message, 'error'); }
}

async function handleLogout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (e) {}
    showLogin();
    toast('已登出');
}

/* ===== 修改密码 ===== */
function showChangePwdModal() {
    document.getElementById('oldPassword').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmPassword').value = '';
    document.getElementById('changePwdModal').classList.add('active');
}

function togglePwd(inputId, btn) {
    const input = document.getElementById(inputId);
    input.type = input.type === 'password' ? 'text' : 'password';
    btn.textContent = input.type === 'password' ? '👁' : '🙈';
}

async function changePassword() {
    const oldPwd = document.getElementById('oldPassword').value;
    const newPwd = document.getElementById('newPassword').value;
    const confirmPwd = document.getElementById('confirmPassword').value;
    if (!oldPwd || !newPwd || !confirmPwd) { toast('请填写所有字段', 'warning'); return; }
    if (newPwd !== confirmPwd) { toast('两次输入的新密码不一致', 'error'); return; }
    if (newPwd.length < 6) { toast('新密码长度不能少于6位', 'warning'); return; }
    try {
        const result = await api('/api/auth/change-password', {
            method: 'POST', body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
        });
        toast(result.message, 'success');
        closeModal('changePwdModal');
        setTimeout(() => { showLogin(); toast('请使用新密码重新登录', 'info'); }, 1500);
    } catch (e) { toast(e.message, 'error'); }
}

/* ===== 侧边栏 ===== */
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

/* ===== 页面导航 ===== */
const pageTitles = {
    dashboard: '数据概览', articles: '文章管理', sources: '采集源管理',
    collect: '采集任务', publish: '发布任务', config: '参数配置',
    logs: '操作日志', recycle: '回收站'
};

document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const page = item.dataset.page;
        if (!page) return;
        document.querySelectorAll('.sidebar-nav .nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const pageEl = document.getElementById('page-' + page);
        if (pageEl) pageEl.classList.add('active');
        document.getElementById('pageTitle').textContent = pageTitles[page] || page;
        // 加载数据
        if (page === 'dashboard') loadDashboard();
        if (page === 'articles') loadArticles();
        if (page === 'sources') loadSources();
        if (page === 'config') loadConfig();
        if (page === 'logs') loadLogs();
        if (page === 'recycle') loadRecycle();
        if (page === 'collect') { pollCollectOnce(); }
        if (page === 'publish') { pollPublishOnce(); }
        // 移动端关闭侧边栏
        document.getElementById('sidebar').classList.remove('open');
    });
});

/* ===== 数据概览 ===== */
async function loadDashboard() {
    try {
        const data = await api('/api/dashboard');
        document.getElementById('statTotal').textContent = data.total_articles;
        document.getElementById('statPending').textContent = data.pending;
        document.getElementById('statApproved').textContent = data.approved;
        document.getElementById('statPublished').textContent = data.published;
        document.getElementById('statRejected').textContent = data.rejected;
        document.getElementById('statToday').textContent = data.today_collected;
        document.getElementById('srcTotal').textContent = data.sources_total;
        document.getElementById('srcActive').textContent = data.sources_active;
        document.getElementById('recycleCount').textContent = data.recycle_count;
        renderCategoryChart(data.category_stats);
        const logs = await api('/api/tasks/logs?size=5');
        renderRecentLogs(logs.items);
    } catch (e) { toast('加载仪表盘失败: ' + e.message, 'error'); }
}

function renderCategoryChart(stats) {
    const container = document.getElementById('categoryChart');
    if (!stats || Object.keys(stats).length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-text">暂无数据</div></div>';
        return;
    }
    const max = Math.max(...Object.values(stats), 1);
    const colors = ['var(--primary)', 'var(--info)', 'var(--success)', 'var(--warning)', 'var(--danger)', '#8B5CF6'];
    let i = 0;
    container.innerHTML = '<div class="bar-chart">' + Object.entries(stats).map(([cat, count]) => {
        const pct = (count / max * 100).toFixed(0);
        return `<div class="bar-item"><span class="bar-label">${esc(cat)}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${colors[i++ % colors.length]}">${count}</div></div></div>`;
    }).join('') + '</div>';
}

function renderRecentLogs(logs) {
    const container = document.getElementById('recentLogs');
    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-text">暂无任务日志</div></div>';
        return;
    }
    container.innerHTML = logs.map(l => {
        const typeLabel = l.task_type === 'collect' ? '采集' : '发布';
        const statusIcon = l.status === 'success' ? '✅' : (l.status === 'stopped' ? '⏹' : '❌');
        return `<div class="log-item"><span class="log-type ${l.task_type}">${typeLabel}</span><span class="log-status">${statusIcon}</span><span class="log-message">${esc(l.message)}</span><span class="log-time">${formatDate(l.created_at)}</span></div>`;
    }).join('');
}

/* ===== 文章管理 ===== */
async function loadArticles() {
    try {
        const status = document.getElementById('filterStatus').value;
        const category = document.getElementById('filterCategory').value;
        let url = `/api/articles?page=${currentPage}&size=20`;
        if (status) url += '&status=' + status;
        if (category) url += '&category=' + encodeURIComponent(category);
        const data = await api(url);
        const tbody = document.getElementById('articlesTable');
        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--gray-400);padding:40px;">暂无文章</td></tr>';
            document.getElementById('articlesPagination').innerHTML = '';
            return;
        }
        tbody.innerHTML = data.items.map(a => {
            let actions = '';
            if (a.status === 'pending') {
                actions = `<button class="btn btn-success btn-sm" onclick="reviewArticle(${a.id},'approve')">通过</button> <button class="btn btn-danger btn-sm" onclick="reviewArticle(${a.id},'reject')">驳回</button> `;
            }
            actions += `<button class="btn btn-outline btn-sm" onclick="previewArticle(${a.id})">预览</button> <button class="btn btn-danger btn-sm" onclick="deleteArticle(${a.id})">删除</button>`;
            return `<tr>
                <td><input type="checkbox" class="article-check" value="${a.id}"></td>
                <td>${a.id}</td>
                <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;color:var(--primary);font-weight:500;" onclick="previewArticle(${a.id})">${esc(a.title)}</td>
                <td>${esc(a.category)}</td>
                <td>${a.word_count}</td>
                <td>${statusBadge(a.status)}</td>
                <td>${esc(a.source_name || '-')}</td>
                <td>${formatDate(a.created_at)}</td>
                <td><div class="btn-group">${actions}</div></td>
            </tr>`;
        }).join('');
        renderPagination(data.total, data.page, data.size);
    } catch (e) { toast('加载文章失败: ' + e.message, 'error'); }
}

function renderPagination(total, page, size) {
    const pages = Math.ceil(total / size);
    const container = document.getElementById('articlesPagination');
    if (pages <= 1) { container.innerHTML = ''; return; }
    let html = `<button ${page <= 1 ? 'disabled' : ''} onclick="currentPage=${page - 1};loadArticles()">‹</button>`;
    const start = Math.max(1, page - 4);
    const end = Math.min(pages, start + 9);
    for (let i = start; i <= end; i++) {
        html += `<button class="${i === page ? 'active' : ''}" onclick="currentPage=${i};loadArticles()">${i}</button>`;
    }
    html += `<button ${page >= pages ? 'disabled' : ''} onclick="currentPage=${page + 1};loadArticles()">›</button>`;
    container.innerHTML = html;
}

async function previewArticle(id) {
    try {
        const a = await api('/api/articles/' + id);
        document.getElementById('modalTitle').textContent = a.title;
        let meta = `<span class="status-badge status-${a.status}">${a.status}</span>`;
        meta += `<span>📂 ${esc(a.category)}</span>`;
        meta += `<span>📝 ${a.word_count} 字</span>`;
        if (a.author) meta += `<span>✍️ ${esc(a.author)}</span>`;
        if (a.source_name) meta += `<span>🔗 ${esc(a.source_name)}</span>`;
        if (a.auto_review_log) {
            meta += `<div style="width:100%;margin-top:0.5rem;"><pre style="font-size:0.72rem;color:var(--gray-500);white-space:pre-wrap;background:var(--gray-50);padding:0.6rem;border-radius:var(--radius-sm);">${esc(a.auto_review_log)}</pre></div>`;
        }
        document.getElementById('modalMeta').innerHTML = meta;
        document.getElementById('modalContent').textContent = a.content;
        let footer = `<button class="btn btn-outline" onclick="closeModal('articleModal')">关闭</button>`;
        if (a.status === 'pending') {
            footer += ` <button class="btn btn-danger" onclick="reviewArticle(${a.id},'reject');closeModal('articleModal')">驳回</button>`;
            footer += ` <button class="btn btn-success" onclick="reviewArticle(${a.id},'approve');closeModal('articleModal')">通过</button>`;
        }
        document.getElementById('modalFooter').innerHTML = footer;
        document.getElementById('articleModal').classList.add('active');
    } catch (e) { toast('加载文章详情失败: ' + e.message, 'error'); }
}

async function reviewArticle(id, action) {
    const reason = action === 'reject' ? (prompt('请输入驳回原因（可留空）:') || '') : '';
    try {
        const result = await api(`/api/articles/${id}/review`, {
            method: 'POST', body: JSON.stringify({ action, reason })
        });
        toast(result.message, action === 'approve' ? 'success' : 'warning');
        loadArticles();
    } catch (e) { toast('审核失败: ' + e.message, 'error'); }
}

async function batchReview(action) {
    const checks = document.querySelectorAll('.article-check:checked');
    if (checks.length === 0) { toast('请先选择文章', 'warning'); return; }
    const ids = Array.from(checks).map(c => parseInt(c.value));
    const reason = action === 'reject' ? (prompt('请输入驳回原因（可留空）:') || '') : '';
    try {
        const result = await api('/api/articles/batch-review', {
            method: 'POST', body: JSON.stringify({ article_ids: ids, action, reason })
        });
        const ok = result.results.filter(r => r.success).length;
        toast(`批量操作完成: ${ok}/${ids.length} 成功`, 'success');
        loadArticles();
    } catch (e) { toast('批量审核失败: ' + e.message, 'error'); }
}

async function deleteArticle(id) {
    if (!confirm('确定删除此文章？')) return;
    try {
        await api('/api/articles/' + id, { method: 'DELETE' });
        toast('文章已移入回收站', 'success');
        loadArticles();
    } catch (e) { toast('删除失败: ' + e.message, 'error'); }
}

function toggleSelectAll() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.article-check').forEach(c => c.checked = checked);
}

/* ===== 采集源管理 ===== */
async function loadSources() {
    try {
        const data = await api('/api/sources');
        const tbody = document.getElementById('sourcesTable');
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--gray-400);padding:40px;">暂无采集源，点击右上角添加</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(s => {
            const statusHtml = s.enabled
                ? '<span class="status-badge status-approved">启用</span>'
                : '<span class="status-badge status-rejected">禁用</span>';
            return `<tr>
                <td>${s.id}</td>
                <td style="font-weight:500;">${esc(s.name)}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(s.url)}">${esc(s.url)}</td>
                <td>${esc(s.category)}</td>
                <td>${statusHtml}</td>
                <td>${formatDate(s.last_collected_at)}</td>
                <td>${s.total_collected || 0}</td>
                <td><div class="btn-group">
                    <button class="btn btn-outline btn-sm" onclick="editSource(${s.id})">编辑</button>
                    <button class="btn btn-outline btn-sm" onclick="toggleSource(${s.id},${s.enabled})">${s.enabled ? '禁用' : '启用'}</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteSource(${s.id})">删除</button>
                </div></td>
            </tr>`;
        }).join('');
    } catch (e) { toast('加载采集源失败: ' + e.message, 'error'); }
}

function showAddSourceModal() {
    document.getElementById('srcEditId').value = '';
    document.getElementById('srcName').value = '';
    document.getElementById('srcUrl').value = '';
    document.getElementById('srcCategory').value = '';
    document.getElementById('srcLinkSel').value = '';
    document.getElementById('srcTitleSel').value = '';
    document.getElementById('srcContentSel').value = '';
    document.getElementById('srcEnabled').checked = true;
    document.getElementById('sourceModalTitle').textContent = '新增采集源';
    document.getElementById('sourceModal').classList.add('active');
}

async function editSource(id) {
    try {
        const sources = await api('/api/sources');
        const s = sources.find(x => x.id === id);
        if (!s) return;
        document.getElementById('srcEditId').value = s.id;
        document.getElementById('srcName').value = s.name;
        document.getElementById('srcUrl').value = s.url;
        document.getElementById('srcCategory').value = s.category;
        document.getElementById('srcLinkSel').value = s.link_selector || '';
        document.getElementById('srcTitleSel').value = s.title_selector || '';
        document.getElementById('srcContentSel').value = s.content_selector || '';
        document.getElementById('srcEnabled').checked = s.enabled;
        document.getElementById('sourceModalTitle').textContent = '编辑采集源';
        document.getElementById('sourceModal').classList.add('active');
    } catch (e) { toast('加载采集源失败: ' + e.message, 'error'); }
}

async function saveSource() {
    const id = document.getElementById('srcEditId').value;
    const data = {
        name: document.getElementById('srcName').value,
        url: document.getElementById('srcUrl').value,
        category: document.getElementById('srcCategory').value,
        link_selector: document.getElementById('srcLinkSel').value,
        title_selector: document.getElementById('srcTitleSel').value,
        content_selector: document.getElementById('srcContentSel').value,
        enabled: document.getElementById('srcEnabled').checked
    };
    if (!data.name || !data.url || !data.category) { toast('请填写必填项', 'warning'); return; }
    try {
        if (id) { await api('/api/sources/' + id, { method: 'PUT', body: JSON.stringify(data) }); toast('采集源已更新', 'success'); }
        else { await api('/api/sources', { method: 'POST', body: JSON.stringify(data) }); toast('采集源已添加', 'success'); }
        closeModal('sourceModal');
        loadSources();
    } catch (e) { toast('保存失败: ' + e.message, 'error'); }
}

async function toggleSource(id, enabled) {
    try {
        await api('/api/sources/' + id, { method: 'PUT', body: JSON.stringify({ enabled: !enabled }) });
        toast(enabled ? '已禁用' : '已启用', 'success');
        loadSources();
    } catch (e) { toast('操作失败: ' + e.message, 'error'); }
}

async function deleteSource(id) {
    if (!confirm('确定删除此采集源？')) return;
    try {
        await api('/api/sources/' + id, { method: 'DELETE' });
        toast('采集源已删除', 'success');
        loadSources();
    } catch (e) { toast('删除失败: ' + e.message, 'error'); }
}

/* ===== 采集任务 ===== */
async function triggerCollect() {
    try {
        const result = await api('/api/tasks/collect', { method: 'POST' });
        toast(result.message, 'info');
        startCollectPolling();
        // 切换到采集页面
        document.querySelector('[data-page="collect"]').click();
    } catch (e) { toast('采集触发失败: ' + e.message, 'error'); }
}

async function stopCollect() {
    if (!confirm('确定要停止采集吗？')) return;
    try {
        const result = await api('/api/tasks/collect/stop', { method: 'POST' });
        toast(result.message, 'warning');
    } catch (e) { toast('停止失败: ' + e.message, 'error'); }
}

function startCollectPolling() {
    if (collectPollTimer) return;
    collectPollTimer = setInterval(pollCollectStatus, 1500);
}

function stopCollectPolling() {
    if (collectPollTimer) { clearInterval(collectPollTimer); collectPollTimer = null; }
}

async function pollCollectOnce() {
    try {
        const status = await api('/api/tasks/collect/status');
        updateCollectUI(status);
        if (status.is_running) startCollectPolling();
    } catch (e) {}
}

async function pollCollectStatus() {
    try {
        const status = await api('/api/tasks/collect/status');
        updateCollectUI(status);
        if (!status.is_running && status.finished_at) {
            stopCollectPolling();
            toast('采集任务已完成', 'success');
            setTimeout(loadDashboard, 500);
        }
    } catch (e) { if (e.message.includes('未认证')) stopCollectPolling(); }
}

function updateCollectUI(status) {
    const panel = document.getElementById('collectPanel');
    const idle = document.getElementById('collectIdle');
    const btn = document.getElementById('btnCollect');
    const btn2 = document.getElementById('btnCollect2');
    const btnStop = document.getElementById('btnStopCollect');
    const badge = document.getElementById('collectStatusBadge');

    if (status.is_running) {
        panel.style.display = 'block'; idle.style.display = 'none';
        btn.disabled = true; btn.textContent = '⏳ 采集中...';
        btn2.disabled = true; btn2.textContent = '⏳ 采集中...';
        btnStop.style.display = 'inline-flex';
        badge.textContent = status.stop_requested ? '正在停止...' : '采集中...';
    } else {
        panel.style.display = 'none'; idle.style.display = 'block';
        btn.disabled = false; btn.textContent = '⬇️ 采集';
        btn2.disabled = false; btn2.textContent = '🔄 手动采集';
        btnStop.style.display = 'none';
        return;
    }

    document.getElementById('progressPct').textContent = status.progress + '%';
    document.getElementById('progressFill').style.width = status.progress + '%';
    document.getElementById('collectProgressLabel').textContent = `采集源 ${status.completed_sources} / ${status.total_sources}`;
    document.getElementById('currentSource').textContent = status.current_source || '-';
    document.getElementById('currentAction').textContent = status.current_action || '';
    document.getElementById('collectTotal').textContent = status.total_articles;
    document.getElementById('collectPassed').textContent = status.passed_articles;
    document.getElementById('collectRejected').textContent = status.rejected_articles;
    document.getElementById('collectSkipped').textContent = status.skipped_articles;

    if (status.logs && status.logs.length > 0) {
        const logsEl = document.getElementById('collectLogs');
        logsEl.innerHTML = status.logs.map(l =>
            `<div class="log-entry ${l.level || ''}"><span style="color:var(--gray-400);">[${l.time}]</span> ${esc(l.message)}</div>`
        ).join('');
        logsEl.scrollTop = logsEl.scrollHeight;
    }
}

/* ===== 发布任务 ===== */
async function triggerPublish() {
    try {
        const result = await api('/api/tasks/publish', { method: 'POST' });
        toast(result.message, 'info');
        startPublishPolling();
        document.querySelector('[data-page="publish"]').click();
    } catch (e) { toast('发布触发失败: ' + e.message, 'error'); }
}

async function stopPublish() {
    if (!confirm('确定要停止发布吗？')) return;
    try {
        const result = await api('/api/tasks/publish/stop', { method: 'POST' });
        toast(result.message, 'warning');
    } catch (e) { toast('停止失败: ' + e.message, 'error'); }
}

function startPublishPolling() {
    if (publishPollTimer) return;
    publishPollTimer = setInterval(pollPublishStatus, 1500);
}

function stopPublishPolling() {
    if (publishPollTimer) { clearInterval(publishPollTimer); publishPollTimer = null; }
}

async function pollPublishOnce() {
    try {
        const status = await api('/api/tasks/publish/status');
        updatePublishUI(status);
        if (status.is_running) startPublishPolling();
    } catch (e) {}
}

async function pollPublishStatus() {
    try {
        const status = await api('/api/tasks/publish/status');
        updatePublishUI(status);
        if (!status.is_running && status.finished_at) {
            stopPublishPolling();
            toast('发布任务已完成', 'success');
            setTimeout(loadDashboard, 500);
        }
    } catch (e) { if (e.message.includes('未认证')) stopPublishPolling(); }
}

function updatePublishUI(status) {
    const panel = document.getElementById('publishPanel');
    const idle = document.getElementById('publishIdle');
    const btn = document.getElementById('btnPublish');
    const btn2 = document.getElementById('btnPublish2');
    const btnStop = document.getElementById('btnStopPublish');
    const badge = document.getElementById('publishStatusBadge');

    if (status.is_running) {
        panel.style.display = 'block'; idle.style.display = 'none';
        btn.disabled = true; btn.textContent = '⏳ 发布中...';
        btn2.disabled = true; btn2.textContent = '⏳ 发布中...';
        btnStop.style.display = 'inline-flex';
        badge.textContent = status.stop_requested ? '正在停止...' : '发布中...';
    } else {
        panel.style.display = 'none'; idle.style.display = 'block';
        btn.disabled = false; btn.textContent = '📤 发布';
        btn2.disabled = false; btn2.textContent = '🚀 开始发布';
        btnStop.style.display = 'none';
        return;
    }

    document.getElementById('publishProgressPct').textContent = status.progress + '%';
    document.getElementById('publishProgressFill').style.width = status.progress + '%';
    document.getElementById('publishProgressLabel').textContent = `${status.published_articles + status.failed_articles} / ${status.total_articles}`;
    document.getElementById('publishCurrentTitle').textContent = status.current_title || '-';
    document.getElementById('publishTotal').textContent = status.total_articles;
    document.getElementById('publishSuccess').textContent = status.published_articles;
    document.getElementById('publishFailed').textContent = status.failed_articles;

    if (status.logs && status.logs.length > 0) {
        const logsEl = document.getElementById('publishLogs');
        logsEl.innerHTML = status.logs.map(l =>
            `<div class="log-entry ${l.level || ''}"><span style="color:var(--gray-400);">[${l.time}]</span> ${esc(l.message)}</div>`
        ).join('');
        logsEl.scrollTop = logsEl.scrollHeight;
    }
}

/* ===== 参数配置 ===== */
let categoryData = [];

async function loadConfig() {
    try {
        const data = await api('/api/config');
        document.getElementById('cfgCollectCron').value = data.collection_schedule || '';
        document.getElementById('cfgPublishCron').value = data.publish_schedule || '';
        categoryData = data.categories || [];
        document.getElementById('categoryConfig').innerHTML = categoryData.map((c, i) =>
            `<div style="display:flex;align-items:center;gap:0.75rem;padding:0.5rem 0;border-bottom:1px solid var(--gray-100);">
                <span style="width:80px;font-weight:500;font-size:0.88rem;">${esc(c.name)}</span>
                <label class="checkbox-label" style="font-size:0.82rem;"><input type="checkbox" ${c.enabled ? 'checked' : ''} onchange="updateCategoryEnabled(${i},this.checked)"> 启用</label>
                <span style="color:var(--gray-400);font-size:0.78rem;margin-left:auto;">${c.daily_min || 0}-${c.daily_max || 0} 篇/日</span>
            </div>`
        ).join('');
        const ai = data.ai_correction || {};
        document.getElementById('cfgAiEnabled').checked = ai.enabled || false;
        document.getElementById('cfgAiProvider').value = ai.provider || 'deepseek';
        const ds = ai.deepseek || {};
        document.getElementById('cfgDeepseekUrl').value = ds.api_url || '';
        document.getElementById('cfgDeepseekKey').value = ds.api_key || '';
        document.getElementById('cfgDeepseekModel').value = ds.model || 'deepseek-chat';
        const mi = ai.mimo || {};
        document.getElementById('cfgMimoUrl').value = mi.api_url || '';
        document.getElementById('cfgMimoKey').value = mi.api_key || '';
        document.getElementById('cfgMimoModel').value = mi.model || '';
    } catch (e) { toast('加载配置失败: ' + e.message, 'error'); }
}

function updateCategoryEnabled(i, enabled) { if (categoryData[i]) categoryData[i].enabled = enabled; }

async function saveConfig() {
    const data = {
        collection_schedule: document.getElementById('cfgCollectCron').value,
        publish_schedule: document.getElementById('cfgPublishCron').value,
        categories: categoryData,
        ai_correction_enabled: document.getElementById('cfgAiEnabled').checked,
        ai_correction_provider: document.getElementById('cfgAiProvider').value,
        deepseek_api_url: document.getElementById('cfgDeepseekUrl').value,
        deepseek_api_key: document.getElementById('cfgDeepseekKey').value,
        deepseek_model: document.getElementById('cfgDeepseekModel').value,
        mimo_api_url: document.getElementById('cfgMimoUrl').value,
        mimo_api_key: document.getElementById('cfgMimoKey').value,
        mimo_model: document.getElementById('cfgMimoModel').value,
    };
    try {
        await api('/api/config', { method: 'PUT', body: JSON.stringify(data) });
        toast('配置已保存', 'success');
    } catch (e) { toast('保存失败: ' + e.message, 'error'); }
}

/* ===== 操作日志 ===== */
async function loadLogs() {
    try {
        const data = await api('/api/tasks/logs?size=50');
        const container = document.getElementById('logsContainer');
        if (data.items.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-text">暂无日志</div></div>';
            return;
        }
        container.innerHTML = data.items.map(l => {
            const typeLabel = l.task_type === 'collect' ? '采集' : '发布';
            const statusIcon = l.status === 'success' ? '✅' : (l.status === 'stopped' ? '⏹' : '❌');
            const duration = l.duration_seconds ? `<span style="color:var(--gray-400);font-size:0.72rem;">${l.duration_seconds.toFixed(1)}s</span>` : '';
            return `<div class="log-item"><span class="log-type ${l.task_type}">${typeLabel}</span><span class="log-status">${statusIcon}</span><span class="log-message">${esc(l.message)}</span>${duration}<span class="log-time">${formatDate(l.created_at)}</span></div>`;
        }).join('');
    } catch (e) { toast('加载日志失败: ' + e.message, 'error'); }
}

/* ===== 回收站 ===== */
async function loadRecycle() {
    try {
        const data = await api('/api/recycle');
        const container = document.getElementById('recycleContainer');
        if (data.items.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🗑️</div><div class="empty-state-text">回收站为空</div></div>';
            return;
        }
        container.innerHTML = data.items.map(item =>
            `<div class="recycle-item">
                <div><span class="title">${esc(item.title)}</span>${item.reason ? `<span style="color:var(--gray-400);font-size:0.75rem;margin-left:0.5rem;">原因: ${esc(item.reason)}</span>` : ''}</div>
                <span class="date">${esc(item.deleted_at || item.date)}</span>
            </div>`
        ).join('');
    } catch (e) { toast('加载回收站失败: ' + e.message, 'error'); }
}

async function clearRecycle() {
    if (!confirm('确定清空回收站？此操作不可恢复。')) return;
    try {
        const result = await api('/api/recycle/clear', { method: 'POST' });
        toast(result.message, 'success');
        loadRecycle();
    } catch (e) { toast('清空失败: ' + e.message, 'error'); }
}

/* ===== 模态框 ===== */
function closeModal(id) { document.getElementById(id).classList.remove('active'); }
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.classList.remove('active'); });
});

/* ===== 初始化 ===== */
document.addEventListener('DOMContentLoaded', () => {
    if (authToken) {
        api('/api/dashboard').then(() => {
            showApp();
            loadDashboard();
            pollCollectOnce();
            pollPublishOnce();
        }).catch(() => showLogin());
    } else { showLogin(); }
});
