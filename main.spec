# -*- mode: python ; coding: utf-8 -*-
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZipFile

if TYPE_CHECKING:
    from typing import cast

    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis
    from PyInstaller.config import CONF
    DISTPATH = cast(str, CONF['distpath'])


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy'],
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


def zip_directory(folder_path, zip_path):
    folder_path = Path(folder_path)
    zip_path = Path(zip_path)

    with ZipFile(zip_path, 'w', ZIP_DEFLATED, compresslevel=9) as zip_file:
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                arcname: Path = file_path.relative_to(folder_path)
                zip_file.write(file_path, arcname)


dest_path: Path = Path(DISTPATH) / 'main'
dest_path.mkdir(parents=True, exist_ok=True)
(dest_path / 'fonts').mkdir(exist_ok=True)
shutil.copy('README.md', dest_path)
shutil.copy('draft_settings.yml', dest_path)
shutil.copy('fonts/SourceHanSans.otf', dest_path / 'fonts')
zip_directory(Path(DISTPATH) / 'main',
              Path(DISTPATH) / f'Music-Box-Designer-{time.strftime('%Y-%m-%d', time.localtime())}.zip')
