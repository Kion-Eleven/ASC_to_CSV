@echo off
REM ============================================================
REM ASC to CSV 环境配置脚本 (Windows)
REM ============================================================

echo ========================================
echo   ASC to CSV 环境配置
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [信息] Python版本:
python --version
echo.

REM 创建虚拟环境
if not exist "venv" (
    echo [步骤1] 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [完成] 虚拟环境创建成功
) else (
    echo [跳过] 虚拟环境已存在
)
echo.

REM 激活虚拟环境
echo [步骤2] 激活虚拟环境...
call venv\Scripts\activate.bat
echo.

REM 安装依赖
echo [步骤3] 安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [完成] 依赖安装成功
echo.

REM 检查配置文件
if not exist "config.json" (
    echo [警告] 未找到config.json配置文件
    if exist "config.example.json" (
        echo [提示] 正在复制config.example.json为config.json...
        copy config.example.json config.json >nul
        echo [完成] 已创建config.json，请根据实际情况修改配置
    ) else (
        echo [提示] 请手动创建config.json配置文件
    )
) else (
    echo [信息] 配置文件config.json已存在
)
echo.

REM 创建数据目录
if not exist "data" (
    echo [步骤4] 创建数据目录...
    mkdir data
    echo [完成] 已创建data目录，请将ASC和DBC文件放入此目录
)
echo.

echo ========================================
echo   环境配置完成！
echo ========================================
echo.
echo 后续步骤:
echo   1. 编辑config.json配置文件
echo   2. 将ASC文件和DBC文件放入data目录
echo   3. 运行 run.bat 启动程序
echo.
pause
