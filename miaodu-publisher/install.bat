@echo off
chcp 65001 >nul
title 秒读课堂 - 环境初始化安装
echo.
echo ========================================
echo   秒读课堂 v2.4 - 环境初始化安装
echo ========================================
echo.

:: 检查 Python 环境
echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境！
    echo 请先安装 Python 3.10+ 并添加到系统环境变量。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Python 版本: %%v

:: 安装 Python 依赖
echo.
echo [2/4] 安装 Python 依赖库...
pip install -r requirements.txt
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，尝试使用国内镜像...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo   依赖安装完成。

:: 安装 Playwright 浏览器驱动
echo.
echo [3/4] 安装 Playwright 浏览器驱动...
python -m playwright install chromium
if errorlevel 1 (
    echo [警告] Playwright 浏览器驱动安装失败，请手动运行: python -m playwright install chromium
) else (
    echo   浏览器驱动安装完成。
)

:: 创建必要目录
echo.
echo [4/4] 创建数据目录...
if not exist "data\logs" mkdir data\logs
if not exist "archives" mkdir archives
if not exist "recycle_bin" mkdir recycle_bin
if not exist "chrome_data" mkdir chrome_data
echo   目录创建完成。

echo.
echo ========================================
echo   环境初始化完成！
echo ========================================
echo.
echo 接下来请：
echo   1. 双击 start.bat 启动程序
echo   2. 在浏览器中打开 Web 后台
echo   3. 在采集源管理中添加采集网址
echo   4. 在参数配置中设置板块采集数量
echo.
echo 首次使用前，请先用 Chrome 浏览器访问：
echo   https://miaoduai.com/v2/
echo 并保存账号密码（勾选自动登录），以便程序调用浏览器发布文章。
echo.
pause
