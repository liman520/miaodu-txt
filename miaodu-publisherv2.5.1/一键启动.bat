@echo off
chcp 65001 >nul 2>&1
title MiaoDuAI Workflow - 系统运行中
color 0B

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║      AI智能全自动文章采集、审校与发布系统                    ║
echo ║                    MiaoDuAI Workflow v2.5.1                    ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo [启动中] 正在初始化后端服务...
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检测Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python环境，请先运行 install.bat
    pause
    exit /b 1
)

:: 启动后端服务（后台运行）
echo [服务] 启动FastAPI后端服务 (http://127.0.0.1:5000)...
start /b python -m uvicorn app.main:app --host 127.0.0.1 --port 5000 --reload > logs.txt 2>&1

:: 等待服务启动
echo [等待] 等待服务就绪...
timeout /t 3 /nobreak >nul

:: 自动打开浏览器
echo [浏览器] 自动打开Web管理后台...
start http://127.0.0.1:5000

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  系统已启动！                                               ║
echo ║  Web管理后台: http://127.0.0.1:5000                         ║
echo ║  关闭此窗口将停止系统服务                                   ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 保持窗口打开，显示日志
echo [运行日志 实时输出]
echo ─────────────────────────────────────────────────
:loop
timeout /t 1 /nobreak >nul
if exist logs.txt (
    type logs.txt
    :: 清空日志避免重复
    break
)
goto loop

:: 保持窗口
cmd /k "echo 系统运行中... 关闭此窗口停止服务"
