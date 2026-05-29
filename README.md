# 秒读课堂 v2.5.0

> 文章采集与发布管理系统 — 自动化采集、智能审核、一键发布

---

## 系统简介

秒读课堂是一套基于 FastAPI 的文章采集与发布管理系统，用于从指定网页源自动采集文章内容，经过人工审核后批量发布到目标平台。适用于内容运营、素材收集、知识管理等场景。

---

## 核心功能

### 📊 仪表盘

- 文章总数、待审核、已通过、已发布、已拒绝等关键指标实时展示
- 采集源数量统计（活跃/总数）
- 回收站文章数统计
- 最近任务日志快捷查看
- 数据卡片支持悬停动效

### 📄 文章管理

- **列表浏览** — 分页展示全部文章，支持按状态/关键词筛选
- **文章预览** — 点击标题弹出预览模态框，查看完整正文内容
- **单篇审核** — 通过/拒绝操作，拒绝需填写原因
- **批量审核** — 勾选多篇文章一键批量通过
- **手动录入** — 支持手动创建文章（标题/分类/摘要/正文）
- **文章删除** — 删除后移入回收站，可恢复
- **全选操作** — 表头复选框全选当前页文章

### 🔗 采集源管理

- **添加采集源** — 填写名称、URL、分类、CSS选择器
- **编辑采集源** — 修改所有字段，启用/禁用切换
- **删除采集源** — 确认后删除
- **状态展示** — 显示启用状态、累计采集文章数、最后采集时间
- **CSS选择器** — 可选，用于精确提取页面中的文章链接

### ⬇️ 采集任务

- **一键采集** — 点击按钮触发异步采集任务
- **实时进度** — 进度条 + 百分比 + 当前采集源 + 已采集数量
- **停止采集** — 任务运行中可随时停止
- **状态轮询** — 前端每1.5秒自动刷新进度
- **完成通知** — 采集完成后自动弹出 Toast 通知
- **仪表盘联动** — 采集完成后自动刷新仪表盘数据

### 📤 发布任务

- **一键发布** — 将审核通过的文章批量发布到目标平台
- **实时进度** — 同采集任务，带进度条和详细状态
- **停止发布** — 运行中可随时停止
- **完成通知** — 发布完成后自动通知

### ⚙️ 系统配置

- **应用设置** — 应用名称、监听地址、端口
- **平台设置** — 目标发布平台 URL
- **采集设置** — Cron 定时表达式、请求间隔、字数范围
- **发布设置** — Cron 定时表达式、文章发布间隔
- **在线保存** — 修改后立即生效，无需重启

### 📋 运行日志

- 采集与发布任务的完整执行记录
- 支持按类型筛选（采集/发布）
- 分页浏览
- 展示：任务类型、状态、消息、采集数、发布数、耗时、时间

### 🗑️ 回收站

- 删除的文章自动归档到回收站
- 按日期目录组织，显示删除时间
- **单篇恢复** — 一键恢复到文章列表（状态重置为待审核）
- **清空回收站** — 一键清空所有已删除文章

### 🔐 用户认证

- 首次登录自动创建管理员账号
- 登录状态本地持久化
- 支持修改密码（旧密码验证 + 新密码确认）

---

## v2.5.0 升级说明

本次从 v2.4 升级到 v2.5，重点优化 AI 纠错稳定性、RESTful 规范修复、任务日志补全。

### 🔧 后端优化

| 项目 | 原有问题 | v2.5 改进 |
|------|----------|-----------|
| AI 纠错超时 | 超时 30 秒，网络波动时频繁失败 | 默认超时提升至 60 秒，支持配置 `timeout` |
| AI 纠错重试 | 超时后直接失败，无重试机制 | 新增重试机制（默认 2 次），指数退避，4xx 错误不重试 |
| 恢复接口规范 | `GET /api/articles/{id}/restore`（GET 请求执行写操作） | 改为 `POST /api/articles/{id}/restore`（RESTful 规范） |
| 手动录入日志 | 手动录入文章不写入任务日志 | 录入操作自动写入 `task_logs`（type=manual_add） |
| 审核操作日志 | 审核通过/拒绝不写入任务日志 | 审核操作自动写入 `task_logs`（type=review） |
| 删除操作日志 | 删除文章不写入任务日志 | 删除操作自动写入 `task_logs`（type=delete） |
| 恢复操作日志 | 恢复文章不写入任务日志 | 恢复操作自动写入 `task_logs`（type=restore） |
| 版本号 | v2.4.0 | 升级至 v2.5.0 |

### 📁 变更文件清单

| 文件 | 变更说明 |
|------|----------|
| `app/core/ai_corrector.py` | 重写：超时提升至 60s，新增重试机制（指数退避），错误分类处理 |
| `app/routes/api.py` | 修改：恢复接口 GET→POST，新增 4 类任务日志写入 |
| `app/main.py` | 修改：版本号升级至 v2.5.0 |
| `config.yaml` | 修改：AI 纠错超时 60s，新增 max_retries: 2，版本号 v2.5.0 |
| `README.md` | 修改：新增 v2.5.0 更新说明 |

### ⚙️ 新增配置项

```yaml
ai_correction:
  max_retries: 2    # AI 纠错最大重试次数（新增）
  timeout: 60       # 超时时间（从 30 调整为 60）
```

---

## v2.3 升级说明

本次从 v2.2 升级到 v2.3，涵盖后端修复、前端重写、架构优化三个方面：

### 🔧 后端修复与优化

| 项目 | 原有问题 | v2.3 改进 |
|------|----------|-----------|
| 配置文件 | config.yaml 不存在时启动报错 | 自动从 config.yaml.example 复制，或生成默认配置 |
| API Key 安全 | `/api/config` 返回明文 API Key | 返回脱敏结果，仅显示后4位 |
| 回收站数据 | `get_recycle_list()` 缺少 `deleted_at` 字段，前端显示空白 | 从日期目录名自动派生 `deleted_at` 字段 |
| 后台任务 | 使用 `BackgroundTasks`，可靠性差 | 改用 `asyncio.create_task`，独立运行不阻塞 |
| 循环导入 | `api.py` 从 `main.py` 导入采集/发布函数，存在循环依赖 | 抽离到独立的 `services.py` 模块，彻底解耦 |
| 平台URL配置 | `ConfigUpdate` 模型不支持 `platform_url` 字段 | 完整支持所有配置字段的更新 |
| 文章恢复 | 无恢复接口 | 新增 `GET /api/articles/{id}/restore` 端点 |
| 版本号 | v2.2.0 | 升级至 v2.4.0 |

### 🎨 前端全面重写

**设计语言升级：**

- 采用 Linear × Apple Settings 设计风格
- 深靛蓝渐变侧边栏（非纯黑）
- 玻璃拟态（Glass-morphism）顶栏
- 卡片带细边框和柔和阴影
- Inter 字体，统一字重体系
- CSS 自定义属性全局主题管理

**交互体验提升：**

- 页面切换带淡入滑动动画（cubic-bezier 缓动）
- 模态框弹出带缩放 + 淡入弹簧动画
- Toast 通知从右侧滑入，3秒后自动滑出
- 进度条带流光（shimmer）动画
- 按钮有 hover/active 状态反馈
- 表格行悬停高亮
- 表单输入聚焦带蓝色光环

**响应式适配：**

- 1200px — 卡片网格自适应
- 1024px — 侧边栏收起为抽屉模式，顶部显示汉堡菜单
- 768px — 表单单列布局，模态框全宽

**功能完整性：**

- 94个 HTML 元素 ID 与 JS 完全匹配
- 所有按钮均有事件绑定，无死角
- 所有 API 端点均从前端正确调用
- 错误处理覆盖每个 API 调用
- 采集/发布轮询自动管理生命周期

### 📁 新增/变更文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/__init__.py` | 新增 | 主应用包初始化 |
| `app/core/__init__.py` | 新增 | 核心模块初始化 |
| `app/models/__init__.py` | 新增 | 数据模型初始化 |
| `app/routes/__init__.py` | 新增 | 路由模块初始化 |
| `app/core/services.py` | 新增 | 后台任务调度服务 |
| `app/models/database.py` | 新增 | SQLAlchemy 数据模型定义 |
| `app/core/config_manager.py` | 重写 | 配置管理 + 脱敏 + 自动创建 |
| `app/core/archiver.py` | 重写 | 回收站管理，修复 deleted_at |
| `app/core/collector.py` | 重写 | 文章采集引擎 |
| `app/core/publisher.py` | 重写 | 文章发布引擎 |
| `app/routes/api.py` | 重写 | 20个 API 端点，新增恢复/批量/手动录入 |
| `app/main.py` | 重写 | v2.4.0 入口，asyncio 生命周期 |
| `app/templates/index.html` | 重写 | 566行，完整管理后台页面 |
| `web/css/style.css` | 重写 | 866行，Premium 设计系统 |
| `web/js/app.js` | 重写 | 894行，完整前端交互逻辑 |
| `config.yaml` | 修改 | 版本号升级为 2.4.0 |
| `README.md` | 新增 | 项目说明文档 |

## v2.4 升级说明

本次从 v2.3 升级到 v2.4，重点实现浏览器自动化发布、站点专用采集器、前端全面重设计。

### 🔧 后端修复与新增

| 项目 | 原有问题 | v2.4 改进 |
|------|----------|-----------|
| 发布器 | HTTP 模拟发布（注释代码） | 基于 Playwright 的浏览器自动化发布，模拟真人操作全流程 |
| 采集器 | 通用爬虫，无站点适配 | 新增光明网/新华网/人民网/光明时评专用解析器 |
| 删除功能 | 直接物理删除，不进回收站 | 删除前自动归档到回收站 |
| 恢复功能 | 不存在 | 新增 `GET /api/articles/{id}/restore` 恢复接口 |
| 系统信息 | 不存在 | 新增 `GET /api/system/info` 接口 |
| 发布清理 | 浏览器资源不释放 | 发布完成后自动关闭浏览器 |

### 🎨 前端全面重设计

**设计语言升级：**
- 深靛蓝渐变侧边栏 + 磨砂玻璃顶栏
- 登录页背景光晕动画 + 弹入式卡片
- 统一 Inter 字体体系
- CSS 自定义属性全局主题管理

**新增页面：**
- 采集任务独立页面（进度条 + 流光动画 + 实时统计 + 滚动日志）
- 发布任务独立页面（同采集任务，带成功/失败计数）

**交互改进：**
- 侧边栏导航改为 button 元素，移动端变抽屉
- 状态徽章统一为 `status-badge` 组件
- Toast 通知右侧滑入 + 滑出动画
- 表格行悬停高亮 + 标题可点击预览
- 统计卡片带彩色图标 + 悬停上浮

**响应式：**
- 1024px — 侧边栏收起为抽屉，顶部显示汉堡菜单
- 768px — 表单单列布局，模态框全宽

### 📁 新增/变更文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/core/publisher.py` | 重写 | Playwright 浏览器自动化发布 |
| `app/core/collector.py` | 重写 | 站点专用解析器 + 智能链接过滤 |
| `app/core/archiver.py` | 修改 | 新增 `restore_from_recycle()` |
| `app/routes/api.py` | 修改 | 修复删除、新增恢复/系统信息接口 |
| `app/core/services.py` | 修改 | 发布后自动关闭浏览器 |
| `app/templates/index.html` | 重写 | 12 个页面组件，全新结构 |
| `web/css/style.css` | 重写 | Linear × Apple Settings 设计系统 |
| `web/js/app.js` | 重写 | 采集/发布独立页面 + 实时轮询 |
| `install.bat` | 新增 | Windows 一键初始化脚本 |
| `start.bat` | 新增 | Windows 一键启动脚本 |
| `requirements.txt` | 修改 | 新增 playwright 依赖 |

---

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装

```bash
cd miaodu-publisher
pip install -r requirements.txt
```

### 启动

```bash
# 方式一
python -m app.main

# 方式二
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 访问

浏览器打开 `http://localhost:8080`

首次登录输入任意用户名和密码，系统会自动创建管理员账号。

---

## 项目结构

```
miaodu-publisher/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config_manager.py    # 配置加载/保存/脱敏/自动创建
│   │   ├── collector.py         # 文章采集引擎（httpx + BeautifulSoup）
│   │   ├── publisher.py         # 文章发布引擎
│   │   ├── archiver.py          # 回收站管理（JSON 文件归档）
│   │   └── services.py          # 后台任务调度（asyncio.create_task）
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py          # SQLAlchemy ORM 模型
│   ├── routes/
│   │   ├── __init__.py
│   │   └── api.py               # 全部 REST API 端点
│   └── templates/
│       └── index.html           # 管理后台单页应用
├── web/
│   ├── css/
│   │   └── style.css            # 样式（CSS 自定义属性 + 响应式）
│   └── js/
│       └── app.js               # 前端交互（原生 JS，无框架）
├── config.yaml                  # 运行时配置（首次自动生成）
├── requirements.txt             # Python 依赖
└── README.md                    # 本文档
```

---

## API 接口文档

### 认证

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/login` | 登录/自动注册 | `{ username, password }` |
| POST | `/api/password` | 修改密码 | `{ old_password, new_password }` |

### 仪表盘

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard` | 统计数据 + 最近5条日志 |

### 文章管理

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/articles` | 文章列表 | `?page=1&size=20&status=&keyword=` |
| GET | `/api/articles/{id}` | 文章详情 | — |
| POST | `/api/articles/{id}/review` | 审核文章 | `{ status: "approved"/"rejected", reject_reason }` |
| POST | `/api/articles/batch-review` | 批量审核 | `{ ids: [1,2,3], status, reject_reason }` |
| DELETE | `/api/articles/{id}` | 删除（移入回收站） | — |
| POST | `/api/articles/{id}/restore` | 从回收站恢复 | — |
| POST | `/api/articles/manual` | 手动录入 | `{ title, content, category, summary }` |

### 采集源管理

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| GET | `/api/sources` | 采集源列表 | — |
| POST | `/api/sources` | 添加采集源 | `{ name, url, category, selector, enabled }` |
| PUT | `/api/sources/{id}` | 更新采集源 | `{ name?, url?, category?, selector?, enabled? }` |
| DELETE | `/api/sources/{id}` | 删除采集源 | — |

### 采集/发布控制

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/collect` | 触发采集任务 |
| POST | `/api/collect/stop` | 停止采集 |
| GET | `/api/collect/status` | 采集进度（实时） |
| POST | `/api/publish` | 触发发布任务 |
| POST | `/api/publish/stop` | 停止发布 |
| GET | `/api/publish/status` | 发布进度（实时） |

### 配置管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取配置（API Key 已脱敏） |
| PUT | `/api/config` | 更新配置（支持部分更新） |

### 日志

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/logs` | 运行日志 | `?page=1&size=20&task_type=collect/publish` |

### 回收站

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/recycle` | 回收站列表 |
| POST | `/api/recycle/clear` | 清空回收站 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/system/info` | 系统信息（名称/版本/数据库路径/平台URL） |

---

## 配置说明

`config.yaml` 首次运行时自动生成，支持在线修改（`/api/config`）。

```yaml
app:
  name: 秒读课堂采集发布系统   # 应用名称
  version: 2.3.0
  host: 127.0.0.1              # 监听地址
  port: 8080                   # 监听端口
  debug: false
  secret_key: ''               # 自动生成的加密密钥

database:
  path: ./data/miaodu.db       # SQLite 数据库路径

logging:
  level: INFO                  # 日志级别
  file: ./data/logs/app.log    # 日志文件
  max_size_mb: 10              # 单文件最大 10MB
  backup_count: 5              # 保留 5 个备份

platform:
  url: https://miaoduai.com/v2/   # 发布目标平台地址
  chrome_user_data_dir: ''        # Chrome 用户数据目录（如需要）

collection:
  schedule_cron: 0 7 * * *     # 每天 07:00 自动采集
  timeout: 300                 # 请求超时（秒）
  max_retries: 3               # 最大重试次数
  request_interval: 3          # 请求间隔（秒）
  min_word_count: 300          # 最少字数过滤
  max_word_count: 3000         # 最多字数过滤
  max_articles_per_source: 20  # 每源最多采集数

publish:
  schedule_cron: 0 17 * * *    # 每天 17:00 自动发布
  time_range_start: '18:00'    # 发布时间窗口开始
  time_range_end: '20:00'      # 发布时间窗口结束
  article_interval: 60         # 文章发布间隔（秒）

categories:                     # 文章分类列表
  - name: 写作素材
    enabled: true
    daily_min: 2               # 每日最少采集数
    daily_max: 5               # 每日最多采集数
  - name: 古诗古文
    enabled: true
    daily_min: 2
    daily_max: 5
  - name: 时政热点
    enabled: true
    daily_min: 2
    daily_max: 5
  - name: 家国情怀
    enabled: true
    daily_min: 2
    daily_max: 5
  - name: 科技人文
    enabled: true
    daily_min: 2
    daily_max: 5
  - name: 思辨阅读
    enabled: true
    daily_min: 2
    daily_max: 5

ai_correction:                  # AI 纠错（可选）
  enabled: false
  provider: deepseek           # deepseek / mimo
  timeout: 60                  # 超时时间（秒）
  max_retries: 2               # 最大重试次数
  deepseek:
    api_url: ''
    api_key: ''
    model: deepseek-chat
  mimo:
    api_url: ''
    api_key: ''
    model: ''
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 数据库 | SQLite |
| HTTP 客户端 | httpx（异步） |
| HTML 解析 | BeautifulSoup4 |
| 定时任务 | APScheduler |
| 加密 | cryptography (Fernet) |
| 模板 | Jinja2 |
| 前端 | 原生 HTML/CSS/JS |
| 浏览器自动化 | Playwright (Chromium) |
| 字体 | Inter (Google Fonts) |
| 设计语言 | Linear × Apple Settings |

---

## 许可证

MIT
