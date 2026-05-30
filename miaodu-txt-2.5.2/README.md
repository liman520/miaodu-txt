# 新闻管理平台 v2.5.1

全自动时政新闻采集与发布管理平台

## 功能

- **新闻采集**：自动抓取人民网、新华网、光明网时政新闻
- **后台审核**：登录后台查看、预览、审核文章
- **自动发布**：Playwright操控浏览器自动发布到知识库网站
- **设置管理**：发布目标URL可配置，不写死

## 快速开始

### 1. 安装 Node.js

访问 https://nodejs.org/ 下载 LTS 版本并安装

### 2. 安装依赖

```bash
npm install
```

### 3. 启动

**Windows**：双击 `start.bat`

**命令行**：
```bash
node server.js
```

### 4. 使用

- 浏览器打开 http://localhost:3001
- 账号：`admin`
- 密码：`123456`

## 技术栈

- Node.js + Express
- SQLite (better-sqlite3)
- Playwright (浏览器自动化)
- 前端：Apple风格科技感深色UI

## 版本

- v2.5.1 - 当前版本
