@echo off
chcp 65001 >nul 2>&1
title MiaoDuAI Workflow - 环境初始化安装程序
color 0A

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║      AI智能全自动文章采集、审校与发布系统 - 安装程序        ║
echo ║                    MiaoDuAI Workflow v2.5.1                    ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 检测管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 建议以管理员身份运行以获得最佳兼容性。
    echo [提示] 右键本文件 -> 以管理员身份运行
    echo.
)

:: 检测Python环境
echo [步骤 1/4] 检测Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python环境！
    echo [解决方案] 请安装Python 3.10+并勾选"Add Python to PATH"
    echo [下载地址] https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [成功] 检测到 %PYVER%

:: 检测pip
echo [步骤 2/4] 检测pip包管理器...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到pip！尝试自动修复...
    python -m ensurepip --default-pip
)
echo [成功] pip就绪

:: 安装依赖
echo [步骤 3/4] 使用清华镜像源安装项目依赖...
echo.
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn
if %errorlevel% neq 0 (
    echo.
    echo [警告] 清华源安装失败，尝试默认源...
    pip install -r requirements.txt
)

:: 安装ChromeDriver
echo.
echo [步骤 4/4] 安装Chrome WebDriver驱动...
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()" >nul 2>&1
if %errorlevel% equ 0 (
    echo [成功] Chrome WebDriver安装完成
) else (
    echo [提示] WebDriver自动安装将在首次运行时由系统自动处理
)

:: 初始化数据库
echo.
echo [初始化] 创建数据库与默认配置...
python -c "import sys; sys.path.insert(0,'.'); from app.database import init_db; init_db(); print('[成功] 数据库初始化完成')"

:: 创建归档目录
if not exist "Archive_Data" mkdir "Archive_Data"

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║      环境初始化完成，全套依赖就绪！                         ║
echo ║                                                            ║
echo ║      请双击 [一键启动.bat] 启动系统                        ║
echo ║                                                            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause
