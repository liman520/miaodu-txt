# MiaoDuAI Publisher v2.5.1

AI智能全自动文章采集、数字审校与发布系统

## 功能特性

- 🔄 全自动文章采集（10大国家级权威网站默认源）
- 🤖 AI双层审校（规则纠错 + DeepSeek/MIMO语义纠错）
- 📊 六大板块精细化管理（写作素材/古诗古文/时政热点/家国情怀/科技人文/思辨阅读）
- 🌐 Selenium自动发布（1:1模拟真人Chrome浏览器操作）
- ⏰ 定时调度（自动采集/发布 + 手动触发双轨制）
- 💾 本地JSON归档（Archive_Data/YYYY-MM-DD/）
- 📈 可视化管理后台（Tailwind CSS仪表盘）

## 快速部署

### 环境要求

- Windows 10/11
- Python 3.10+
- Google Chrome 正式版

### 安装步骤

1. 将本文件夹放到纯英文路径（如 `D:\MiaoDuAI_Workflow\`）
2. 右键 `install.bat` → 以管理员身份运行
3. 等待提示「环境初始化完成，全套依赖就绪！」
4. 双击 `一键启动.bat` 启动系统
5. 浏览器自动打开 http://127.0.0.1:5000

### 配置说明

- **发布目标**：默认 http://localhost:3000（本地测试），正式使用请在【配置】页面改为 https://miaoduai.com/v2/
- **AI纠错**：在【配置】页面填入DeepSeek或MIMO的API Key即可启用
- **采集源**：系统预置10大权威网站，可在【采集源管理】中增删改

## 版本日志

### v2.5.1 (2026-05-30)
- 初始发布版本
- 完整的Web可视化管理后台
- 10大国家级权威网站默认采集源
- 双层审校流水线（规则+AI）
- Selenium自动化发布
- 本地归档系统

## 目录结构

```
miaodu-publisherv2.5.1/
├── install.bat              # 首次部署脚本
├── 一键启动.bat              # 日常启动脚本
├── requirements.txt         # Python依赖
├── config.json              # 系统配置
├── app/                     # 后端源码
│   ├── main.py              # FastAPI主程序
│   ├── database.py          # SQLite数据库
│   ├── collector.py         # 采集引擎
│   ├── reviewer.py          # 双层审校
│   ├── publisher.py         # Selenium发布
│   ├── scheduler.py         # 定时调度
│   ├── llm_client.py        # 大模型客户端
│   ├── config.py            # 配置管理
│   └── utils.py             # 工具函数
├── templates/               # HTML模板
├── static/css/              # 样式文件
├── Archive_Data/            # 本地归档目录
└── data/                    # 数据库+日志
```
