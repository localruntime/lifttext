"""
py2app setup file for LiftText macOS application
"""
from setuptools import setup
from pathlib import Path
import subprocess
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

# Get package paths without importing (avoids loading huge dependency trees)
def get_package_path(package_name):
    """Get package path using subprocess to avoid import side effects."""
    try:
        result = subprocess.run(
            [sys.executable, '-c', f'import {package_name}; print({package_name}.__file__)'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).parent
    except Exception as e:
        print(f"Warning: Could not find {package_name}: {e}")
    return None

paddlex_root = get_package_path('paddlex')
configs_dir = paddlex_root / 'configs' if paddlex_root else None

qt_material_root = get_package_path('qt_material')

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
        # Build tools
        'PyInstaller',
        'nuitka',
        'cx_Freeze',
        # GUI frameworks we don't use
        'tkinter',
        'matplotlib',
        'wx',
        'PyQt5',
        'PyQt6',
        # Jupyter/notebook
        'jupyter',
        'notebook',
        'ipython',
        'ipykernel',
        'IPython',
        # Heavy ML libraries not needed at runtime
        'modelscope',
        'transformers',
        'torch',
        'tensorflow',
        'keras',
        'onnx',
        'onnxruntime',
        # Other heavy deps
        'ruamel',
        'black',
        'sphinx',
        'pytest',
        'setuptools',
        'pip',
        'wheel',
    ],
    'resources': [
        r for r in [
            str(configs_dir) if configs_dir else None,
            str(qt_material_root / 'themes') if qt_material_root else None,
            str(qt_material_root / 'resources') if qt_material_root else None,
        ] if r is not None
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
