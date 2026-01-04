"""
py2app setup file for LiftText macOS application
"""
from setuptools import setup
from pathlib import Path
import os
import sys

# Increase recursion limit for py2app's module graph analysis
sys.setrecursionlimit(10000)

# Paths
home = Path.home()
models_dir = home / '.paddlex' / 'official_models'

# Collect PaddleOCR models
MODEL_DATA = []
default_models = [
    'PP-OCRv4_mobile_det',
    'en_PP-OCRv4_mobile_rec',
    'PP-LCNet_x1_0_textline_ori',
]

for model_name in default_models:
    model_path = models_dir / model_name
    if model_path.exists():
        MODEL_DATA.append(str(model_path))

# Get paddlex configs
import paddlex
paddlex_root = Path(paddlex.__file__).parent
configs_dir = paddlex_root / 'configs'

# Get qt-material resources
import qt_material
qt_material_root = Path(qt_material.__file__).parent

APP = ['main.py']
DATA_FILES = [
    # PaddleOCR models
    ('models', MODEL_DATA),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,
    'plist': {
        'CFBundleName': 'LiftText',
        'CFBundleDisplayName': 'LiftText Image Text Extractor',
        'CFBundleIdentifier': 'com.lifttext.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
    'packages': [
        'paddleocr',
        'paddlex',
        'paddle',
        'PySide6',
        'PIL',
        'cv2',
        'numpy',
        'scipy',
        'sklearn',
        'qt_material',
        'qt_material_icons',
        'fitz',
    ],
    'includes': [
        'scipy._lib._ccallback',
        'scipy.special.cython_special',
        'shapely._geos',
        'shapely._geometry_helpers',
        'setuptools.msvc',
    ],
    'excludes': [
        'PyInstaller',
        'matplotlib',
        'tkinter',
        'jupyter',
        'notebook',
        'ruamel',
    ],
    'resources': [
        str(configs_dir),
        str(qt_material_root / 'themes'),
        str(qt_material_root / 'resources'),
    ],
    'semi_standalone': True,  # Don't modify bundled libraries (avoids permission errors)
    'site_packages': True,
    'no_chdir': True,  # Prevent working directory changes
}

setup(
    name='LiftText',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
