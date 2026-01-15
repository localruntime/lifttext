"""Resource and model setup utilities for PyInstaller bundles"""
import sys
import os


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Running as normal script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def setup_bundled_models():
    """
    Configure OCR engine to use bundled models when running as .app bundle.
    MUST be called BEFORE importing paddleocr module.
    """
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        bundled_models_dir = os.path.join(sys._MEIPASS, 'models')

        if os.path.exists(bundled_models_dir):
            # Set environment variable BEFORE importing paddleocr
            os.environ['PADDLE_PDX_CACHE_HOME'] = bundled_models_dir
            print(f"Using bundled models from: {bundled_models_dir}")
            return bundled_models_dir
        else:
            print(f"WARNING: Bundled models not found at {bundled_models_dir}")
            print("LiftText will try to download models from internet...")

    return None
