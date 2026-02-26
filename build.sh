#!/bin/bash
# ============================================================
# ASC to CSV 打包脚本 (Linux/macOS)
# 将Python项目打包为独立可执行文件
# ============================================================

echo "========================================"
echo "  ASC to CSV 打包工具"
echo "========================================"
echo

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python3"
    exit 1
fi

# 检查PyInstaller
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "[信息] 正在安装PyInstaller..."
    pip3 install pyinstaller
fi

echo "[步骤1] 清理旧的构建文件..."
rm -rf build dist
echo

echo "[步骤2] 开始打包..."
echo "这可能需要几分钟，请耐心等待..."
echo

pyinstaller asc_to_csv.spec --clean

if [ $? -ne 0 ]; then
    echo
    echo "[错误] 打包失败！"
    exit 1
fi

echo
echo "========================================"
echo "  打包完成！"
echo "========================================"
echo
echo "可执行文件位置: dist/ASCtoCSV"
echo
echo "使用说明:"
echo "  1. 将 dist/ASCtoCSV 复制到任意目录"
echo "  2. 运行 chmod +x ASCtoCSV"
echo "  3. 运行 ./ASCtoCSV"
echo "  4. 首次运行会在同目录创建config.json"
echo

# 询问是否打开输出目录
read -p "是否打开输出目录？(y/n): " OPEN_DIR
if [ "$OPEN_DIR" = "y" ] || [ "$OPEN_DIR" = "Y" ]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open dist
    elif command -v open &> /dev/null; then
        open dist
    else
        echo "输出目录: $(pwd)/dist"
    fi
fi
