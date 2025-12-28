# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_submodules, collect_all, collect_data_files

# Paths
project_root = Path('/Users/stevenlau/git/ocr')
home = Path.home()
models_dir = home / '.paddlex' / 'official_models'

# Model directories to bundle (default models only)
default_models = [
    'PP-OCRv4_mobile_det',
    'en_PP-OCRv4_mobile_rec',
    'PP-LCNet_x1_0_textline_ori',
]

# Build list of model data files
model_datas = []
for model_name in default_models:
    model_path = models_dir / model_name
    if model_path.exists():
        # Copy entire model directory to Resources/models/
        model_datas.append((str(model_path), f'models/{model_name}'))
    else:
        print(f"WARNING: Model not found: {model_path}")

# qt-material theme files (XML + resources)
qt_material_datas = []
try:
    import qt_material
    qt_material_root = Path(qt_material.__file__).parent

    # Themes directory (XML files)
    themes_dir = qt_material_root / 'themes'
    if themes_dir.exists():
        qt_material_datas.append((str(themes_dir), 'qt_material/themes'))

    # Resources directory (icons, fonts)
    resources_dir = qt_material_root / 'resources'
    if resources_dir.exists():
        qt_material_datas.append((str(resources_dir), 'qt_material/resources'))

    # Fonts directory
    fonts_dir = qt_material_root / 'fonts'
    if fonts_dir.exists():
        qt_material_datas.append((str(fonts_dir), 'qt_material/fonts'))

    # QSS template file
    qss_template = qt_material_root / 'material.qss.template'
    if qss_template.exists():
        qt_material_datas.append((str(qss_template), 'qt_material'))

    # Dock theme UI file
    dock_theme = qt_material_root / 'dock_theme.ui'
    if dock_theme.exists():
        qt_material_datas.append((str(dock_theme), 'qt_material'))

except ImportError:
    print("WARNING: qt_material not found")

# qt-material-icons resources
qt_icons_datas = []
try:
    import qt_material_icons
    qt_icons_root = Path(qt_material_icons.__file__).parent

    # Resources directory
    icons_resources = qt_icons_root / 'resources'
    if icons_resources.exists():
        qt_icons_datas.append((str(icons_resources), 'qt_material_icons/resources'))

except ImportError:
    print("WARNING: qt_material_icons not found")

# PaddleX version file and configs (required for paddlex initialization)
paddlex_datas = []
try:
    import paddlex
    paddlex_root = Path(paddlex.__file__).parent

    # .version file
    version_file = paddlex_root / '.version'
    if version_file.exists():
        paddlex_datas.append((str(version_file), 'paddlex'))
    else:
        print("WARNING: paddlex/.version not found")

    # configs directory (pipelines and modules)
    configs_dir = paddlex_root / 'configs'
    if configs_dir.exists():
        paddlex_datas.append((str(configs_dir), 'paddlex/configs'))
    else:
        print("WARNING: paddlex/configs not found")

except ImportError:
    print("WARNING: paddlex not found")

# Copy package metadata for ALL OCR dependencies (required for importlib.metadata to work)
# Based on: https://github.com/PaddlePaddle/PaddleOCR/issues/15918
metadata_datas = []
metadata_packages = [
    'paddlex', 'ftfy', 'imagesize', 'lxml', 'opencv-contrib-python',
    'openpyxl', 'premailer', 'pyclipper', 'pypdfium2', 'scikit-learn',
    'shapely', 'tokenizers', 'einops', 'jinja2', 'regex', 'tiktoken'
]

for pkg in metadata_packages:
    try:
        metadata_datas += copy_metadata(pkg)
        print(f"INFO: Copied {pkg} metadata")
    except Exception as e:
        print(f"WARNING: Could not copy {pkg} metadata: {e}")

# Collect all scipy modules, data, and binaries (required for scikit-learn)
scipy_datas, scipy_binaries, scipy_hiddenimports = collect_all('scipy')

# Collect Cython utility files (required for scipy C extensions)
cython_datas = collect_data_files("Cython", includes=["Utility/*.c", "Utility/*.cpp", "Utility/*.h", "Utility/*.pxd", "Utility/*.pyx"])

# Combine all data files (including scipy and Cython data)
all_datas = model_datas + qt_material_datas + qt_icons_datas + paddlex_datas + metadata_datas + scipy_datas + cython_datas

# Hidden imports (modules not auto-detected)
hiddenimports = scipy_hiddenimports + [
    # PyMuPDF (dynamically imported in load_pdf_file at line 1549)
    'fitz',
    'fitz._fitz',

    # qt-material dependencies
    'qt_material',
    'qt_material.resources',

    # qt-material-icons
    'qt_material_icons',
    'qt_material_icons._icon',

    # PaddleOCR internals (may not be auto-detected)
    'paddleocr',
    'paddleocr.paddleocr',
    'paddlex',
    'paddlex.inference',
    'paddlepaddle',

    # Image processing
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',

    # Other dependencies
    'numpy',
    'cv2',
    'shapely',
    'pyclipper',

    # Required for PaddleOCR (from GitHub issue #15918)
    'scipy',
    'scipy._cyutility',
    'sklearn',
    'sklearn.utils',
]

# Analysis
a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=scipy_binaries,
    datas=all_datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_root)],  # Use custom hook for scipy
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'pandas.tests',
        'numpy.tests',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PaddleOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX (can corrupt large binaries)
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # No code signing
    entitlements_file=None,
    icon=None,  # Use macOS default icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PaddleOCR',
)

app = BUNDLE(
    coll,
    name='PaddleOCR.app',
    icon=None,  # Use default macOS icon
    bundle_identifier='com.paddleocr.imagetextextractor',
    version='1.0.0',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleName': 'PaddleOCR',
        'CFBundleDisplayName': 'PaddleOCR Image Text Extractor',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': 'com.paddleocr.imagetextextractor',
        'NSHumanReadableCopyright': 'PaddleOCR Desktop App',
        'LSMinimumSystemVersion': '10.13',
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
    },
)
