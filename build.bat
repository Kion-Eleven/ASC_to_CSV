@echo off
chcp 65001 >nul
echo ========================================
echo   ASC to CSV Build Tool
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Pillow for icon conversion...
    pip install Pillow
)

echo [STEP 1] Converting icon...
if exist "resource\icon.png" (
    if not exist "resource\icon.ico" (
        python convert_icon.py
    ) else (
        echo Icon already exists, skipping conversion.
    )
) else (
    echo [WARNING] icon.png not found, building without custom icon.
)
echo.

echo [STEP 2] Cleaning old build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo.

echo [STEP 3] Building executable...
echo Please wait, this may take a few minutes...
echo.

pyinstaller main_app.spec --clean

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Output: dist\ASCtoCSV\ASCtoCSV.exe  (onedir mode, faster startup)
echo.

if exist "resource\icon.ico" (
    echo Icon: resource\icon.ico (applied)
) else (
    echo Icon: Default (no custom icon)
)
echo.

echo Usage:
echo   1. Copy the entire dist\ASCtoCSV\ folder to any location
echo   2. Double-click ASCtoCSV.exe inside that folder to run
echo   3. Use "Data Convert" tab to convert ASC to CSV
echo   4. Use "Data Visualize" tab to view charts
echo.

set /p OPEN_DIR="Open output folder? (Y/N): "
if /i "%OPEN_DIR%"=="Y" (
    explorer dist
)

pause
