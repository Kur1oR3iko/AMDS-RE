#!/bin/bash
echo "========================================"
echo "AMDS macOS Build Script"
echo "========================================"

# 切换到脚本目录
cd "$(dirname "$0")"

echo ""
echo "[1/4] 清理旧的构建文件..."

if [ -d "build" ]; then
    rm -rf "build"
fi
if [ -d "dist" ]; then
    rm -rf "dist"
fi
if [ -f "AMDS.spec" ]; then
    rm -f "AMDS.spec"
fi

echo "[OK] 清理完成"

echo ""
echo "[2/4] 检查 Python..."

python3 --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[ERROR] Python3 未找到"
    exit 1
fi

echo "[OK] Python3 已安装"

echo ""
echo "[3/4] 检查图标文件..."

if [ ! -f "assets/images/logo39.ico" ]; then
    echo "[WARNING] ICO 图标文件不存在，将使用 PNG 图标"
    ICON_OPTION="--icon=assets/images/ic_launcher.png"
else
    ICON_OPTION="--icon=assets/images/logo39.ico"
fi

echo "[OK] 图标文件检查完成"

echo ""
echo "[4/4] 开始构建..."

# 使用 PyInstaller 构建
python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "AMDS" \
    $ICON_OPTION \
    --add-data "assets:assets" \
    --paths "src" \
    --hidden-import "PyQt6" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "requests" \
    --hidden-import "openai" \
    --exclude-module "tkinter" \
    "src/run.py"

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] 构建失败!"
    exit 1
fi

echo ""
echo "========================================"
echo "构建完成!"
echo "========================================"
echo ""
echo "输出文件: dist/AMDS.app"
echo "或直接运行: dist/AMDS"
echo ""

# 尝试打开输出目录
open dist
