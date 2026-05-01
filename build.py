"""
PyInstaller 打包脚本
用法: python build.py

产出: dist/AMDS/ 文件夹（可交给 Inno Setup 打包安装程序）
"""

import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
ENTRY = os.path.join(SRC_DIR, "main.py")
ICON = os.path.join(ASSETS_DIR, "images", "icon.ico")

APP_NAME = "AMDS"
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")

DEPENDENCIES = [
    "PyQt6",
    "openai",
    "pygame",
    "requests",
    "Pillow",
    "pyinstaller",
]


def ensure_deps():
    missing = []
    for pkg in DEPENDENCIES:
        mod = "PIL" if pkg == "Pillow" else pkg
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"正在安装缺失依赖: {', '.join(missing)}")
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)
    else:
        print("所有依赖已就绪，跳过安装")
    print()


def clean():
    for d in ["build", "spec"]:
        p = os.path.join(PROJECT_ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
            print(f"已清理: {d}/")
    spec_file = os.path.join(PROJECT_ROOT, f"{APP_NAME}.spec")
    if os.path.isfile(spec_file):
        os.remove(spec_file)
        print(f"已清理: {APP_NAME}.spec")


def build():
    os.makedirs(DIST_DIR, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--name={APP_NAME}",
        f"--icon={ICON}",
        f"--distpath={DIST_DIR}",
        f"--workpath={os.path.join(PROJECT_ROOT, 'build')}",
        f"--specpath={PROJECT_ROOT}",

        # 资源文件打包到根目录（与 _MEIPASS 对应）
        f"--add-data={ASSETS_DIR}{os.pathsep}assets",

        # 隐藏导入
        "--hidden-import=pygame",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtMultimedia",

        # 入口
        ENTRY,
    ]

    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\n打包失败，退出码: {result.returncode}")
        sys.exit(1)

    out_dir = os.path.join(DIST_DIR, APP_NAME)
    if os.path.isdir(out_dir):
        size_mb = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fns in os.walk(out_dir)
            for f in fns
        ) / 1024 / 1024
        print(f"\n打包完成: {out_dir}")
        print(f"文件夹大小: {size_mb:.1f} MB")
    else:
        print(f"\n警告: 未找到输出目录 {out_dir}")


if __name__ == "__main__":
    ensure_deps()
    clean()
    build()
