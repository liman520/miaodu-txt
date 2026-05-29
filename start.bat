@echo off
chcp 65001 >nul
title 秒读课堂 v2.4 - 采集发布系统
echo.
echo ========================================
echo   秒读课堂 v2.4 - 一键启动
echo ========================================
echo.

:: 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境！请先运行 install.bat。
    pause
    exit /b 1
)

:: 检查依赖是否已安装
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [提示] 依赖未安装，正在自动安装...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

:: 创建必要目录
if not exist "data\logs" mkdir data\logs
if not exist "archives" mkdir archives
if not exist "recycle_bin" mkdir recycle_bin

:: 读取配置中的端口号
set PORT=8080
for /f "tokens=2 delims=: " %%p in ('findstr /r "port:" config.yaml 2^>nul') do (
    set PORT=%%p
)

echo [启动中] 后端服务端口: %PORT%
echo [启动中] Web 后台地址: http://127.0.0.1:%PORT%
echo.
echo 提示：按 Ctrl+C 可停止程序
echo.

:: 自动打开浏览器
start "" http://127.0.0.1:%PORT%

:: 启动后端服务
python -m app.main

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出！请检查日志文件: data\logs\app.log
    pause
)
