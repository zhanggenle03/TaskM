# -*- mode: python ; coding: utf-8 -*-
"""TaskM PyInstaller 打包配置  构建：pyinstaller TaskM.spec"""
from pathlib import Path

ROOT = Path(__file__).parent

# ── 收集前端文件（如果 dist 存在） ──
frontend_datas = []
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    frontend_datas = [
        (str(f), str(Path("frontend_dist") / f.relative_to(FRONTEND_DIST)))
        for f in FRONTEND_DIST.rglob("*") if f.is_file()
    ]

a = Analysis(
    [str(ROOT / "backend" / "run_packaged.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "backend" / "taskm.ico"), "."),   # 托盘图标 → _MEIPASS/
    ] + frontend_datas,
    hiddenimports=["pystray", "pystray._win32", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TaskM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=str(ROOT / "backend" / "taskm.ico"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TaskM",
)
