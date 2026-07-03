@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo ============================================
echo    StockX Pro - Agent Memory Hub
echo ============================================
echo.

cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

:: ==================== 环境检查 ====================
echo [0/5] 检查 uv 虚拟环境...
if not exist "%PY%" (
    echo [提示] 虚拟环境不存在，正在创建...
    uv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [错误] 虚拟环境创建失败!
        pause
        exit /b 1
    )
)
echo [OK] 虚拟环境: %PY%

echo.
echo [提示] 检查依赖是否完整...
"%PY%" -c "import django" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [提示] 正在安装依赖...
    uv pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [错误] 依赖安装失败!
        pause
        exit /b 1
    )
)
echo [OK] 依赖就绪

echo.
echo ============================================
echo    请选择操作:
echo    1. 启动 Django 服务器 (投研平台)
echo    2. 测试 Agent Memory Hub (单元测试)
echo    3. 测试 Agent Memory Hub API (需先启动 main.py)
echo    4. 一键全部测试 (单元 + 数据库迁移)
echo    5. 刷新市场数据 + 启动服务器
echo    0. 退出
echo ============================================
set /p menu=请输入选项 [0-5]: 

if "!menu!"=="1" goto :start_django
if "!menu!"=="2" goto :test_memory
if "!menu!"=="3" goto :test_api
if "!menu!"=="4" goto :test_all
if "!menu!"=="5" goto :refresh_and_start
if "!menu!"=="0" goto :end

echo [错误] 无效选项，请输入 0-5
goto :end

:: ==================== 1. 启动 Django ====================
:start_django
echo.
echo [1/2] 执行数据库迁移检查...
"%PY%" "manage.py" migrate --check
if %ERRORLEVEL% NEQ 0 (
    echo [提示] 有未应用的迁移，正在执行...
    "%PY%" "manage.py" migrate
)

echo.
echo [2/2] 启动 Django 服务器...
"%PY%" "manage.py" runserver
goto :end

:: ==================== 2. 单元测试 ====================
:test_memory
echo.
echo ============================================
echo    Agent Memory Hub - 单元测试
echo ============================================
echo.
echo [提示] 若 HuggingFace 下载失败，请先设置镜像:
echo        set HF_ENDPOINT=https://hf-mirror.com
echo.
"%PY%" "test_memory.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [提示] 测试遇到错误，常见原因:
    echo   1. 无法连接 huggingface.co 下载模型
    echo   2. ChromaDB 数据目录损坏（删除 .\data\chroma 重试）
)
goto :end

:: ==================== 3. API 测试 ====================
:test_api
echo.
echo ============================================
echo    Agent Memory Hub - API 测试
echo ============================================
echo.
echo [提示] 此测试需要先启动 main.py (FastAPI 服务)
echo.
echo 是否现在启动 FastAPI 服务? (Y/N)
set /p start_api=
if /i "!start_api!"=="Y" (
    echo 正在后台启动 FastAPI 服务 (端口 8000)...
    start "MemoryHub-API" "%PY%" "main.py"
    echo 等待服务启动 (5秒)...
    timeout /t 5 /nobreak >nul
)

echo.
echo 运行 API 测试...
"%PY%" -c "import httpx" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [提示] 正在安装 httpx...
    uv pip install httpx
)
"%PY%" "test_memory_api.py"

echo.
echo [提示] 如果测试失败，请确认 main.py 已启动 (http://127.0.0.1:8000)
goto :end

:: ==================== 4. 一键全部测试 ====================
:test_all
echo.
echo ============================================
echo    一键全部测试
echo ============================================

echo.
echo --- [1/2] 数据库迁移 ---
"%PY%" "manage.py" migrate --check
if %ERRORLEVEL% NEQ 0 (
    "%PY%" "manage.py" migrate
)

echo.
echo --- [2/2] Agent Memory Hub 单元测试 ---
echo [提示] 若 HuggingFace 下载失败，请先: set HF_ENDPOINT=https://hf-mirror.com
echo.
"%PY%" "test_memory.py"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo    ✓ 全部测试通过!
    echo ============================================
) else (
    echo.
    echo [提示] 测试未完全通过，请检查上方错误信息
)
goto :end

:: ==================== 5. 刷新数据 + 启动 ====================
:refresh_and_start
echo.
echo [1/3] 运行美股爬虫...
"%PY%" ".\Data\spider_pro.py"

echo.
echo [2/3] 导入 CSV 到数据库...
"%PY%" "import_csv.py"

echo.
echo [3/3] 刷新 A 股实时行情...
"%PY%" "manage.py" populate_a_stocks --refresh

echo.
echo 执行数据库迁移...
"%PY%" "manage.py" migrate

echo.
echo 启动 Django 服务器...
"%PY%" "manage.py" runserver
goto :end

:: ==================== 结束 ====================
:end
echo.
echo ============================================
echo    操作完成
echo ============================================
pause
