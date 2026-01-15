# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for LiftText macOS application
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all paddlex data files (configs, version, etc.)
paddlex_datas = collect_data_files('paddlex')

# Collect all paddleocr data files
paddleocr_datas = collect_data_files('paddleocr')

# Collect qt_material themes
qt_material_datas = collect_data_files('qt_material')

# Collect qt_material_icons resources
qt_material_icons_datas = collect_data_files('qt_material_icons')

# Hidden imports for packages that PyInstaller might miss
hidden_imports = [
    # PaddleOCR/PaddleX
    'paddleocr',
    'paddlex',
    'paddle',
    # Image processing
    'PIL',
    'cv2',
    'numpy',
    'scipy',
    'sklearn',
    'skimage',
    'shapely',
    # Qt
    'PySide6',
    'qt_material',
    # PDF
    'fitz',
    'pymupdf',
    # YAML (namespace package - PyInstaller handles this)
    'ruamel.yaml',
    # Other deps
    'pydantic',
    'tqdm',
    'requests',
    'certifi',
    'qt_material_icons.resources', 
]

# Add all submodules for packages with dynamic imports
hidden_imports += collect_submodules('paddlex')
hidden_imports += collect_submodules('paddleocr')
hidden_imports += collect_submodules('qt_material_icons')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=paddlex_datas + paddleocr_datas + qt_material_datas + qt_material_icons_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'jupyter',
        'notebook',
        'IPython',
        'torch',
        'tensorflow',
        'keras',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    module_collection_mode={
        'qt_material_icons': 'pyz+py',
    },
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LiftText',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LiftText',
)

app = BUNDLE(
    coll,
    name='LiftText.app',
    icon=None,
    bundle_identifier='com.lifttext.app',
    info_plist={
        'CFBundleName': 'LiftText',
        'CFBundleDisplayName': 'LiftText Image Text Extractor',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
)
