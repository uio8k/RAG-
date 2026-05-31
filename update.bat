@echo off
chcp 65001 >nul
echo ============================================
echo    StockX Pro - 数据更新脚本
echo ============================================
echo.

cd /d %~dp0

echo [1/3] 激活 conda 环境...
call conda activate Py313
if %ERRORLEVEL% NEQ 0 (
    echo [错误] conda 环境激活失败!
    pause
    exit /b 1
)

echo.
echo [2/3] 是否刷新数据? (Y/N 默认N)
set /p choice=
if /i "%choice%"=="Y" (
    echo 正在运行美股爬虫...
    python ./Data/spider_pro.py
    echo 正在导入 CSV 到数据库...
    python import_csv.py
    echo 正在刷新 A 股实时行情...
    python manage.py populate_a_stocks --refresh
)

echo.
echo [3/3] 启动 Django 服务器...
python manage.py runserver

echo.
echo ============================================
echo    服务器已停止
echo ============================================
pause
