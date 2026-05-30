@echo off
chcp 65001 >nul
title 新闻管理平台
color 0A

echo.
echo  ══════════════════════════════════════════
echo       新闻管理平台 - 一键启动
echo  ══════════════════════════════════════════
echo.

:: 检查 Node.js
echo  [1/3] 检查 Node.js...
node -v >nul 2>&1
if errorlevel 1 (
    echo  [错误] 未安装 Node.js！
    echo  请先访问 https://nodejs.org/ 下载安装 LTS 版本
    echo  安装时务必勾选 "Add to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node -v') do echo  [OK] Node.js %%v 已安装

:: 检查并安装依赖
echo.
echo  [2/3] 检查项目依赖...
if not exist "%~dp0node_modules" (
    echo  [提示] 首次运行，正在安装依赖（可能需要2-5分钟）...
    cd /d "%~dp0"
    call npm install
    if errorlevel 1 (
        echo  [错误] 依赖安装失败！请检查网络连接
        pause
        exit /b 1
    )
    echo  [OK] 依赖安装完成
) else (
    echo  [OK] 依赖已存在
)

:: 启动服务
echo.
echo  [3/3] 启动服务器...
echo.
echo  ══════════════════════════════════════════
echo   访问地址：http://localhost:3001
echo   登录账号：admin
echo   登录密码：123456
echo  ══════════════════════════════════════════
echo.
echo  提示：按 Ctrl+C 可停止服务器
echo.

cd /d "%~dp0"
node server.js

echo.
echo  服务器已停止
pause
