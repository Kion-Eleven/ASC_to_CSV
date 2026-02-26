#!/bin/bash
# ============================================================
# ASC to CSV 环境配置脚本 (Linux/macOS)
# ============================================================

echo "========================================"
echo "  ASC to CSV 环境配置"
echo "========================================"
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python3，请先安装Python 3.8+"
    exit 1
fi

echo "[信息] Python版本:"
python3 --version
echo

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "[步骤1] 创建虚拟环境..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[错误] 创建虚拟环境失败"
        exit 1
    fi
    echo "[完成] 虚拟环境创建成功"
else
    echo "[跳过] 虚拟环境已存在"
fi
echo

# 激活虚拟环境
echo "[步骤2] 激活虚拟环境..."
source venv/bin/activate
echo

# 安装依赖
echo "[步骤3] 安装依赖包..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[错误] 依赖安装失败"
    exit 1
fi
echo "[完成] 依赖安装成功"
echo

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "[警告] 未找到config.json配置文件"
    if [ -f "config.example.json" ]; then
        echo "[提示] 正在复制config.example.json为config.json..."
        cp config.example.json config.json
        echo "[完成] 已创建config.json，请根据实际情况修改配置"
    else
        echo "[提示] 请手动创建config.json配置文件"
    fi
else
    echo "[信息] 配置文件config.json已存在"
fi
echo

# 创建数据目录
if [ ! -d "data" ]; then
    echo "[步骤4] 创建数据目录..."
    mkdir -p data
    echo "[完成] 已创建data目录，请将ASC和DBC文件放入此目录"
fi
echo

echo "========================================"
echo "  环境配置完成！"
echo "========================================"
echo
echo "后续步骤:"
echo "  1. 编辑config.json配置文件"
echo "  2. 将ASC文件和DBC文件放入data目录"
echo "  3. 运行 ./run.sh 启动程序"
echo
