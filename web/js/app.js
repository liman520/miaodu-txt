/* ========== 秒读课堂 v2.3 - 前端交互逻辑 ========== */

let authToken = localStorage.getItem('auth_token') || '';
let currentPage = 1;
let collectPollTimer = null;

// ========== API 工具函数 ==========
async function api(url, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
    const resp = await fetch(url, { headers, ...options });
    if (resp.status === 401) { showLogin(); throw new Error('未认证，请重新登录'); }
    if (!resp.ok) {
        const err = await resp.json().catch(function() { return { detail: resp.statusText }; });
        throw new Error(err.detail || '请求失败');
    }
    return resp.json();
}

function toast(msg, type) {
    type = type || 'info';
    var container = document.getElementById('toastContainer');
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(function() { el.style.opacity = '0'; setTimeout(function() { el.remove(); }, 300); }, 3000);
}

function formatDate(iso) {
    if (!iso) return '-';
    var d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function statusBadge(status) {
    var map = {
        pending: ['待审核', 'badge-pending'],
        approved: ['已通过', 'badge-approved'],
        published: ['已发布', 'badge-published'],
        rejected: ['已驳回', 'badge-rejected']
    };
    var m = map[status] || [status, ''];
    return '<span class="badge ' + m[1] + '">' + m[0] + '</span>';
}

function esc(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ========== 登录/登出 ==========
function showLogin() {
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('mainApp').style.display = 'none';
    authToken = '';
    localStorage.removeItem('auth_token');
    stopCollectPolling();
}

function showApp() {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('mainApp').style.display = 'flex';
}

async function handleLogin(e) {
    e.preventDefault();
    var password = document.getElementById('loginPassword').value;
    try {
        var resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: password })
        });
        if (!resp.ok) throw new Error('密码错误');
        var data = await resp.json();
        authToken = data.token;
        localStorage.setItem('auth_token', authToken);
        showApp();
        loadDashboard();
        toast('登录成功', 'success');
    } catch (e2) {
        toast(e2.message, 'error');
    }
}

async function handleLogout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (e) {}
    showLogin();
    toast('已登出');
}

// ========== 修改密码 ==========
function showChangePwdModal() {
    document.getElementById('oldPassword').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmPassword').value = '';
    document.getElementById('changePwdModal').classList.add('active');
}

function togglePwd(inputId, btn) {
    var input = document.getElementById(inputId);
    if (input.type === 'password') { input.type = 'text'; btn.textContent = '\uD83D\uDE48'; }
    else { input.type = 'password'; btn.textContent = '\uD83D\uDC41'; }
}

async function changePassword() {
    var oldPwd = document.getElementById('oldPassword').value;
    var newPwd = document.getElementById('newPassword').value;
    var confirmPwd = document.getElementById('confirmPassword').value;
    if (!oldPwd || !newPwd || !confirmPwd) { toast('请填写所有字段', 'warning'); return; }
    if (newPwd !== confirmPwd) { toast('两次输入的新密码不一致', 'error'); return; }
    if (newPwd.length < 6) { toast('新密码长度不能少于6位', 'warning'); return; }
    try {
        var result = await api('/api/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
        });
        toast(result.message, 'success');
        closeModal('changePwdModal');
        setTimeout(function() { showLogin(); toast('请使用新密码重新登录', 'info'); }, 1500);
    } catch (e) { toast(e.message, 'error'); }
}

// ========== 页面导航 ==========
document.querySelectorAll('.nav-item').forEach(function(item) {
    item.addEventListener('click', function(e) {
        e.preventDefault();
        var page = item.dataset.page;
        document.querySelectorAll('.nav-item').forEach(function(n) { n.classList.remove('active'); });
        item.classList.add('active');
        document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
        var pageEl = document.getElementById('page-' + page);
        if (pageEl) pageEl.classList.add('active');
        var titles = {
            dashboard: '数据概览', articles: '文章管理', sources: '采集源管理',
            'manual-collect': '手动采集', config: '参数配置', logs: '操作日志', recycle: '回收站'
        };
        document.getElementById('pageTitle').textContent = titles[page] || page;
        if (page === 'dashboard') loadDashboard();
        if (page === 'articles') loadArticles();
        if (page === 'sources') loadSources();
        if (page === 'config') loadConfig();
        if (page === 'logs') loadLogs();
        if (page === 'recycle') loadRecycle();
    });
});

// ========== 数据概览 ==========
async function loadDashboard() {
    try {
        var data = await api('/api/dashboard');
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
        var logs = await api('/api/tasks/logs?size=5');
        renderRecentLogs(logs.items);
    } catch (e) { toast('加载仪表盘失败: ' + e.message, 'error'); }
}

function renderCategoryChart(stats) {
    var container = document.getElementById('categoryChart');
    if (!stats || Object.keys(stats).length === 0) { container.innerHTML = '<p class="text-muted">暂无数据</p>'; return; }
    var max = Math.max.apply(null, Object.values(stats).concat([1]));
    var colors = ['#007AFF', '#5856D6', '#34C759', '#FF9500', '#FF3B30', '#AF52DE'];
    var html = '<div class="bar-chart">';
    var i = 0;
    for (var cat in stats) {
        var count = stats[cat];
        var pct = (count / max * 100).toFixed(0);
        html += '<div class="bar-item"><span class="bar-label">' + esc(cat) + '</span><div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + colors[i % colors.length] + '">' + count + '</div></div></div>';
        i++;
    }
    html += '</div>';
    container.innerHTML = html;
}

function renderRecentLogs(logs) {
    var container = document.getElementById('recentLogs');
    if (!logs || logs.length === 0) { container.innerHTML = '<p class="text-muted">暂无日志</p>'; return; }
    container.innerHTML = logs.map(function(l) {
        return '<div class="log-item"><span class="log-type ' + l.task_type + '">' + (l.task_type === 'collect' ? '采集' : '发布') + '</span><span class="log-status ' + l.status + '">' + (l.status === 'success' ? '✅' : (l.status === 'stopped' ? '⏹' : '❌')) + '</span><span class="log-message">' + esc(l.message) + '</span><span class="log-time">' + formatDate(l.created_at) + '</span></div>';
    }).join('');
}

// ========== 文章管理 ==========
async function loadArticles() {
    try {
        var status = document.getElementById('filterStatus').value;
        var category = document.getElementById('filterCategory').value;
        var url = '/api/articles?page=' + currentPage + '&size=20';
        if (status) url += '&status=' + status;
        if (category) url += '&category=' + encodeURIComponent(category);
        var data = await api(url);
        var tbody = document.getElementById('articlesTable');
        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--gray-400);padding:40px;">暂无文章</td></tr>';
            return;
        }
        tbody.innerHTML = data.items.map(function(a) {
            var actions = '';
            if (a.status === 'pending') {
                actions = '<button class="btn btn-xs btn-success" onclick="reviewArticle(' + a.id + ',\'approve\')">通过</button> <button class="btn btn-xs btn-danger" onclick="reviewArticle(' + a.id + ',\'reject\')">驳回</button> ';
            }
            actions += '<button class="btn btn-xs" onclick="previewArticle(' + a.id + ')">预览</button> <button class="btn btn-xs btn-danger" onclick="deleteArticle(' + a.id + ')">删除</button>';
            return '<tr><td><input type="checkbox" class="article-check" value="' + a.id + '"></td><td>' + a.id + '</td><td><a href="#" onclick="previewArticle(' + a.id + ');return false;" style="color:var(--blue);text-decoration:none;font-weight:500;">' + esc(a.title) + '</a></td><td>' + esc(a.category) + '</td><td>' + a.word_count + '</td><td>' + statusBadge(a.status) + '</td><td>' + esc(a.source_name || '-') + '</td><td>' + formatDate(a.created_at) + '</td><td class="actions">' + actions + '</td></tr>';
        }).join('');
        renderPagination(data.total, data.page, data.size);
    } catch (e) { toast('加载文章失败: ' + e.message, 'error'); }
}

function renderPagination(total, page, size) {
    var pages = Math.ceil(total / size);
    var container = document.getElementById('articlesPagination');
    if (pages <= 1) { container.innerHTML = ''; return; }
    var html = '<button ' + (page <= 1 ? 'disabled' : '') + ' onclick="currentPage=' + (page-1) + ';loadArticles()">上一页</button>';
    for (var i = 1; i <= Math.min(pages, 10); i++) {
        html += '<button class="' + (i === page ? 'active' : '') + '" onclick="currentPage=' + i + ';loadArticles()">' + i + '</button>';
    }
    html += '<button ' + (page >= pages ? 'disabled' : '') + ' onclick="currentPage=' + (page+1) + ';loadArticles()">下一页</button>';
    container.innerHTML = html;
}

async function previewArticle(id) {
    try {
        var a = await api('/api/articles/' + id);
        document.getElementById('modalTitle').textContent = a.title;
        document.getElementById('modalMeta').innerHTML = '<span class="badge badge-' + a.status + '">' + a.status + '</span> <span>板块: ' + esc(a.category) + '</span> <span>字数: ' + a.word_count + '</span> <span>作者: ' + esc(a.author || '无') + '</span> <span>来源: ' + esc(a.source_name || '无') + '</span>' + (a.auto_review_log ? '<div style="width:100%;margin-top:8px;"><pre style="font-size:12px;color:var(--gray-500);white-space:pre-wrap;">' + esc(a.auto_review_log) + '</pre></div>' : '');
        document.getElementById('modalContent').textContent = a.content;
        var footer = '';
        if (a.status === 'pending') {
            footer = '<button class="btn" onclick="closeModal(\'articleModal\')">关闭</button> <button class="btn btn-danger" onclick="reviewArticle(' + a.id + ',\'reject\');closeModal(\'articleModal\')">驳回</button> <button class="btn btn-success" onclick="reviewArticle(' + a.id + ',\'approve\');closeModal(\'articleModal\')">通过</button>';
        } else {
            footer = '<button class="btn" onclick="closeModal(\'articleModal\')">关闭</button>';
        }
        document.getElementById('modalFooter').innerHTML = footer;
        document.getElementById('articleModal').classList.add('active');
    } catch (e) { toast('加载文章详情失败: ' + e.message, 'error'); }
}

async function reviewArticle(id, action) {
    var reason = action === 'reject' ? (prompt('请输入驳回原因（可留空）:') || '') : '';
    try {
        var result = await api('/api/articles/' + id + '/review', { method: 'POST', body: JSON.stringify({ action: action, reason: reason }) });
        toast(result.message, action === 'approve' ? 'success' : 'warning');
        loadArticles();
    } catch (e) { toast('审核失败: ' + e.message, 'error'); }
}

async function batchReview(action) {
    var checks = document.querySelectorAll('.article-check:checked');
    if (checks.length === 0) { toast('请先选择文章', 'warning'); return; }
    var ids = Array.from(checks).map(function(c) { return parseInt(c.value); });
    var reason = action === 'reject' ? (prompt('请输入驳回原因（可留空）:') || '') : '';
    try {
        var result = await api('/api/articles/batch-review', { method: 'POST', body: JSON.stringify({ article_ids: ids, action: action, reason: reason }) });
        var successCount = result.results.filter(function(r) { return r.success; }).length;
        toast('批量操作完成: ' + successCount + '/' + ids.length + ' 成功', 'success');
        loadArticles();
    } catch (e) { toast('批量审核失败: ' + e.message, 'error'); }
}

async function deleteArticle(id) {
    if (!confirm('确定删除此文章？')) return;
    try {
        await api('/api/articles/' + id, { method: 'DELETE' });
        toast('文章已删除', 'success');
        loadArticles();
    } catch (e) { toast('删除失败: ' + e.message, 'error'); }
}

function toggleSelectAll() {
    var checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.article-check').forEach(function(c) { c.checked = checked; });
}

// ========== 采集源管理 ==========
async function loadSources() {
    try {
        var data = await api('/api/sources');
        var tbody = document.getElementById('sourcesTable');
        if (data.length === 0) { tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--gray-400);padding:40px;">暂无采集源</td></tr>'; return; }
        tbody.innerHTML = data.map(function(s) {
            return '<tr><td>' + s.id + '</td><td>' + esc(s.name) + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + esc(s.url) + '">' + esc(s.url) + '</td><td>' + esc(s.category) + '</td><td><span class="badge ' + (s.enabled ? 'badge-enabled' : 'badge-disabled') + '">' + (s.enabled ? '启用' : '禁用') + '</span></td><td>' + formatDate(s.last_collected_at) + '</td><td>' + s.total_collected + '</td><td class="actions"><button class="btn btn-xs" onclick="editSource(' + s.id + ')">编辑</button> <button class="btn btn-xs" onclick="toggleSource(' + s.id + ',' + s.enabled + ')">' + (s.enabled ? '禁用' : '启用') + '</button> <button class="btn btn-xs btn-danger" onclick="deleteSource(' + s.id + ')">删除</button></td></tr>';
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
        var sources = await api('/api/sources');
        var s = sources.find(function(x) { return x.id === id; });
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
    var id = document.getElementById('srcEditId').value;
    var data = {
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

async function toggleSource(id, currentEnabled) {
    try {
        await api('/api/sources/' + id, { method: 'PUT', body: JSON.stringify({ enabled: !currentEnabled }) });
        toast(currentEnabled ? '已禁用' : '已启用', 'success');
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

// ========== 手动采集 ==========
async function submitManualArticle(e) {
    e.preventDefault();
    var data = {
        title: document.getElementById('manualTitle').value,
        content: document.getElementById('manualContent').value,
        category: document.getElementById('manualCategory').value,
        author: document.getElementById('manualAuthor').value,
        source_name: document.getElementById('manualSourceName').value,
        source_url: document.getElementById('manualSourceUrl').value
    };
    try {
        var result = await api('/api/articles', { method: 'POST', body: JSON.stringify(data) });
        var resultDiv = document.getElementById('manualResult');
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = '<p><strong>文章ID:</strong> ' + result.id + '</p><p><strong>状态:</strong> ' + statusBadge(result.status) + '</p><p><strong>预审结果:</strong> ' + (result.passed ? '✅ 通过' : '❌ 未通过') + '</p><pre style="font-size:12px;white-space:pre-wrap;">' + esc(result.review_log) + '</pre><p style="margin-top:12px;">' + esc(result.message) + '</p>';
        toast(result.message, result.passed ? 'success' : 'warning');
        if (result.passed) document.getElementById('manualForm').reset();
    } catch (e2) { toast('提交失败: ' + e2.message, 'error'); }
}

// ========== 采集控制 ==========
async function triggerCollect() {
    try {
        var result = await api('/api/tasks/collect', { method: 'POST' });
        toast(result.message, 'info');
        startCollectPolling();
    } catch (e) { toast('采集触发失败: ' + e.message, 'error'); }
}

async function stopCollect() {
    if (!confirm('确定要停止采集吗？已采集的内容会保留。')) return;
    try {
        var result = await api('/api/tasks/collect/stop', { method: 'POST' });
        toast(result.message, 'warning');
        document.getElementById('btnStopCollect').disabled = true;
        document.getElementById('btnStopCollect').textContent = '⏳ 正在停止...';
    } catch (e) { toast('停止失败: ' + e.message, 'error'); }
}

function startCollectPolling() {
    if (collectPollTimer) return;
    updateCollectUI(true);
    collectPollTimer = setInterval(pollCollectStatus, 1000);
}

function stopCollectPolling() {
    if (collectPollTimer) { clearInterval(collectPollTimer); collectPollTimer = null; }
}

async function pollCollectStatus() {
    try {
        var status = await api('/api/tasks/collect/status');
        updateCollectUI(status.is_running, status);
        if (!status.is_running && status.finished_at) { stopCollectPolling(); setTimeout(function() { loadDashboard(); }, 500); }
    } catch (e) { if (e.message.includes('未认证')) stopCollectPolling(); }
}

function updateCollectUI(isRunning, status) {
    var panel = document.getElementById('collectPanel');
    var statusDot = document.getElementById('statusDot');
    var statusText = document.getElementById('statusText');
    var btnCollect = document.getElementById('btnCollect');
    if (isRunning) {
        panel.style.display = 'block'; statusDot.className = 'status-dot running'; statusText.textContent = '正在采集...';
        btnCollect.disabled = true; btnCollect.textContent = '⏳ 采集中...';
    } else {
        panel.style.display = 'none'; statusDot.className = 'status-dot idle'; statusText.textContent = '系统空闲';
        btnCollect.disabled = false; btnCollect.textContent = '🔄 采集';
    }
    if (status) {
        document.getElementById('progressPct').textContent = status.progress + '%';
        document.getElementById('progressFill').style.width = status.progress + '%';
        document.getElementById('progressLabel').textContent = '采集源 ' + status.completed_sources + ' / ' + status.total_sources;
        document.getElementById('currentSource').textContent = status.current_source || '等待开始...';
        document.getElementById('currentAction').textContent = status.current_action || '-';
        document.getElementById('collectTotal').textContent = status.total_articles;
        document.getElementById('collectPassed').textContent = status.passed_articles;
        document.getElementById('collectRejected').textContent = status.rejected_articles;
        document.getElementById('collectSkipped').textContent = status.skipped_articles;
        if (status.stop_requested) {
            document.getElementById('collectPanelTitle').textContent = '正在停止采集...';
            document.getElementById('btnStopCollect').disabled = true; document.getElementById('btnStopCollect').textContent = '⏳ 正在停止...';
        } else {
            document.getElementById('collectPanelTitle').textContent = '正在采集...';
            document.getElementById('btnStopCollect').disabled = false; document.getElementById('btnStopCollect').textContent = '⏹ 停止采集';
        }
        if (status.logs && status.logs.length > 0) {
            var logsContainer = document.getElementById('collectLogs');
            logsContainer.innerHTML = status.logs.map(function(log) {
                return '<div class="collect-log-entry ' + (log.level || 'info') + '"><span class="log-time">[' + log.time + ']</span> ' + esc(log.message) + '</div>';
            }).join('');
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
    }
}

// ========== 发布 ==========
async function triggerPublish() {
    try {
        var result = await api('/api/tasks/publish', { method: 'POST' });
        toast(result.message, 'info');
    } catch (e) { toast('发布触发失败: ' + e.message, 'error'); }
}

// ========== 参数配置 ==========
async function loadConfig() {
    try {
        var data = await api('/api/config');
        document.getElementById('cfgCollectCron').value = data.collection_schedule || '';
        document.getElementById('cfgPublishCron').value = data.publish_schedule || '';
        var container = document.getElementById('categoryConfig');
        var cats = data.categories || [];
        container.innerHTML = cats.map(function(c, i) {
            return '<div class="form-row" style="align-items:center;display:flex;gap:12px;"><div style="width:100px;font-weight:500;">' + esc(c.name) + '</div><label style="display:flex;align-items:center;gap:4px;font-size:13px;"><input type="checkbox" ' + (c.enabled ? 'checked' : '') + ' onchange="updateCategoryEnabled(' + i + ', this.checked)"> 启用</label></div>';
        }).join('');
        var ai = data.ai_correction || {};
        document.getElementById('cfgAiEnabled').checked = ai.enabled || false;
        document.getElementById('cfgAiProvider').value = ai.provider || 'deepseek';
        var ds = ai.deepseek || {};
        document.getElementById('cfgDeepseekUrl').value = ds.api_url || '';
        document.getElementById('cfgDeepseekKey').value = ds.api_key || '';
        document.getElementById('cfgDeepseekModel').value = ds.model || 'deepseek-chat';
        var mi = ai.mimo || {};
        document.getElementById('cfgMimoUrl').value = mi.api_url || '';
        document.getElementById('cfgMimoKey').value = mi.api_key || '';
        document.getElementById('cfgMimoModel').value = mi.model || '';
    } catch (e) { toast('加载配置失败: ' + e.message, 'error'); }
}

var categoryData = [];
function updateCategoryEnabled(index, enabled) { if (categoryData[index]) categoryData[index].enabled = enabled; }

async function saveConfig() {
    var data = {
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
        mimo_model: document.getElementById('cfgMimoModel').value
    };
    try { await api('/api/config', { method: 'PUT', body: JSON.stringify(data) }); toast('配置已保存', 'success'); }
    catch (e) { toast('保存失败: ' + e.message, 'error'); }
}

// ========== 操作日志 ==========
async function loadLogs() {
    try {
        var data = await api('/api/tasks/logs?size=50');
        var container = document.getElementById('logsContainer');
        if (data.items.length === 0) { container.innerHTML = '<p class="text-muted" style="text-align:center;padding:40px;">暂无日志</p>'; return; }
        container.innerHTML = data.items.map(function(l) {
            return '<div class="log-item"><span class="log-type ' + l.task_type + '">' + (l.task_type === 'collect' ? '采集' : '发布') + '</span><span class="log-status">' + (l.status === 'success' ? '✅' : (l.status === 'stopped' ? '⏹' : '❌')) + '</span><span class="log-message">' + esc(l.message) + '</span>' + (l.duration_seconds ? '<span style="color:var(--gray-400);font-size:12px;">' + l.duration_seconds.toFixed(1) + 's</span>' : '') + '<span class="log-time">' + formatDate(l.created_at) + '</span></div>';
        }).join('');
    } catch (e) { toast('加载日志失败: ' + e.message, 'error'); }
}

// ========== 回收站 ==========
async function loadRecycle() {
    try {
        var data = await api('/api/recycle');
        var container = document.getElementById('recycleContainer');
        if (data.items.length === 0) { container.innerHTML = '<p class="text-muted" style="text-align:center;padding:40px;">回收站为空</p>'; return; }
        container.innerHTML = data.items.map(function(item) {
            return '<div class="recycle-item"><div><span class="title">' + esc(item.title) + '</span>' + (item.reason ? '<span style="color:var(--gray-400);font-size:12px;margin-left:8px;">原因: ' + esc(item.reason) + '</span>' : '') + '</div><span class="date">' + esc(item.deleted_at || item.date) + '</span></div>';
        }).join('');
    } catch (e) { toast('加载回收站失败: ' + e.message, 'error'); }
}

async function clearRecycle() {
    if (!confirm('确定清空回收站？此操作不可恢复。')) return;
    try { var result = await api('/api/recycle/clear', { method: 'POST' }); toast(result.message, 'success'); loadRecycle(); }
    catch (e) { toast('清空失败: ' + e.message, 'error'); }
}

// ========== 模态框通用 ==========
function closeModal(id) { document.getElementById(id).classList.remove('active'); }
document.querySelectorAll('.modal').forEach(function(modal) {
    modal.addEventListener('click', function(e) { if (e.target === modal) modal.classList.remove('active'); });
});

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function() {
    if (authToken) {
        api('/api/dashboard').then(function() { showApp(); loadDashboard(); pollCollectStatus().catch(function(){}); }).catch(function() { showLogin(); });
    } else { showLogin(); }
});
