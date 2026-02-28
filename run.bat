@echo off
REM ============================================================
REM ASC to CSV 运行脚本 (Windows)
REM ============================================================

echo ========================================
echo   ASC to CSV 转换与可视化工具
echo ========================================
echo.

REM 检查虚拟环境
if not exist "venv" (
    echo [错误] 虚拟环境不存在，请先运行 setup.bat
    pause
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 运行程序
echo [信息] 启动程序...
echo.
python main_app.py

echo.
echo ========================================
echo   程序已退出
echo ========================================
pause
