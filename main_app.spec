# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ASC to CSV GUI (main_app.py) - 优化版(onedir模式)"""

import os

block_cipher = None
root = os.path.abspath(SPECPATH)

icon_path = os.path.join(root, "resource", "icon.ico")
if not os.path.isfile(icon_path):
    icon_path = None

# 排除不需要的重量级模块，减小体积、加快启动
EXCLUDES = [
    # 其他 GUI 后端（Tk 程序不需要）
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt4agg",
    "matplotlib.backends.backend_wxagg",
    "matplotlib.backends.backend_macosx",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_gtk3cairo",
    "matplotlib.backends.backend_gtk4agg",
    "matplotlib.backends.backend_gtk4cairo",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_pgf",
    "matplotlib.backends.backend_ps",
    "matplotlib.backends.backend_svg",
    # 测试框架
    "pytest", "unittest", "nose", "doctest",
    # 本项目未使用的科学计算包
    "scipy", "pandas", "sympy", "IPython", "jupyter",
    "notebook", "ipykernel", "qtconsole",
    # 网络相关（本项目为本地工具，不需要）
    "urllib3", "requests", "http.server", "ftplib",
    "smtplib", "xmlrpc",
    # 其他不需要的
    "tkinter.test",
    "setuptools", "pip", "wheel",
    "distutils",
    # pkg_resources 已弃用且运行时未被 matplotlib/cantools 使用，
    # 其运行时钩子(pyi_rth_pkgres)依赖 jaraco.text，排除以避免启动报错
    "pkg_resources",
]

a = Analysis(
    [os.path.join(root, "main_app.py")],
    pathex=[root],
    binaries=[],
    datas=[],
    hiddenimports=[
        "cantools",
        "cantools.database",
        "cantools.database.can",
        "matplotlib.backends.backend_tkagg",
        "PIL",
        "PIL._imagingtk",
    ],
    hookspath=[],
    hooksconfig={
        # 限制 matplotlib 只收集 TkAgg 后端，减小打包体积
        "matplotlib": {"backends": ["TkAgg"]},
    },
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ===== onedir 模式：EXE 不打包二进制，配合 COLLECT 输出到文件夹 =====
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # 二进制文件不打进 exe，放在外面
    name="ASCtoCSV",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# 收集所有依赖到 dist/ASCtoCSV 文件夹（启动时无需解压，速度更快）
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ASCtoCSV",
)
