# -*- mode: python ; coding: utf-8 -*-
import shutil
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='libs',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)

dest_path: Path = Path(DISTPATH) / 'main'
dest_path.mkdir(parents=True, exist_ok=True)
(dest_path / 'fonts').mkdir(exist_ok=True)
shutil.copy('README.md', dest_path)
shutil.copy('draft_settings.yml', dest_path)
shutil.copy('fonts/SourceHanSans.otf', dest_path / 'fonts')
