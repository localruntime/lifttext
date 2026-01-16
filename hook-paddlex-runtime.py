# PyInstaller runtime hook to bypass paddlex dependency checks
# Patches paddlex.utils.deps to always consider OCR dependencies available

import sys
import importlib.util

_original_version = None

# All packages that are bundled - includes OCR extra dependencies
BUNDLED_PACKAGES = {
    # Core
    'paddlex',
    'paddleocr',
    'paddle',
    'paddlepaddle',
    'numpy',
    'opencv-python',
    'opencv-contrib-python',
    'Pillow',
    'pyyaml',
    'shapely',
    'pyclipper',
    'lmdb',
    'tqdm',
    'requests',
    'matplotlib',
    'scipy',
    'scikit-learn',
    'scikit-image',
    'soundfile',
    'librosa',
    'chinese_calendar',
    'holidays',
    'statsmodels',
    'pycocotools',
    # OCR extra dependencies
    'einops',
    'ftfy',
    'imagesize',
    'jinja2',
    'lxml',
    'openpyxl',
    'premailer',
    'pypdfium2',
    'python-bidi',
    'regex',
    'safetensors',
    'sentencepiece',
    'tiktoken',
    'tokenizers',
}

def _patched_version(package):
    """Return a fake version only for known bundled packages."""
    global _original_version
    try:
        return _original_version(package)
    except Exception:
        # Only fake version if we know it's bundled
        pkg_lower = package.lower().replace('-', '_').replace('.', '_')
        for bundled in BUNDLED_PACKAGES:
            if pkg_lower == bundled.lower().replace('-', '_').replace('.', '_'):
                return "999.0.0"
        # Let it fail naturally for packages we don't have
        raise

def _patch_importlib_metadata():
    global _original_version
    import importlib.metadata
    _original_version = importlib.metadata.version
    importlib.metadata.version = _patched_version

_patch_importlib_metadata()

# Patch paddlex.utils.deps to bypass OCR dependency checks
def _patch_paddlex_deps():
    """Patch paddlex dependency checking to always pass for OCR."""
    try:
        import paddlex.utils.deps as deps

        # Store original functions
        _original_is_extra_available = deps.is_extra_available.__wrapped__ if hasattr(deps.is_extra_available, '__wrapped__') else None
        _original_is_dep_available = deps.is_dep_available.__wrapped__ if hasattr(deps.is_dep_available, '__wrapped__') else None

        # Clear the lru_cache so our patches take effect
        deps.is_extra_available.cache_clear()
        deps.is_dep_available.cache_clear()

        # Patch is_extra_available to always return True for ocr/ocr-core
        original_is_extra = deps.is_extra_available
        def patched_is_extra_available(extra):
            if extra in ('ocr', 'ocr-core', 'cv', 'base'):
                return True
            return original_is_extra(extra)
        deps.is_extra_available = patched_is_extra_available

        # Patch require_extra to be a no-op for ocr
        original_require_extra = deps.require_extra
        def patched_require_extra(extra, *, obj_name=None, alt=None):
            if extra in ('ocr', 'ocr-core', 'cv', 'base'):
                return  # Skip check
            return original_require_extra(extra, obj_name=obj_name, alt=alt)
        deps.require_extra = patched_require_extra

    except ImportError:
        pass  # paddlex not yet imported

# Schedule the paddlex patch to run after paddlex is imported
class _PaddlexPatcher:
    """Import hook to patch paddlex when it's imported."""
    def find_module(self, name, path=None):
        if name == 'paddlex.utils.deps':
            return self
        return None

    def load_module(self, name):
        # Remove ourselves temporarily to avoid recursion
        sys.meta_path.remove(self)
        try:
            import importlib
            module = importlib.import_module(name)
            # Apply patches after the real module is loaded
            _patch_paddlex_deps()
            return module
        finally:
            # Re-add ourselves for future imports
            if self not in sys.meta_path:
                sys.meta_path.insert(0, self)

sys.meta_path.insert(0, _PaddlexPatcher())
