# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LiftText is a PySide6 desktop application for extracting text from images. The app uses PaddleOCR v3 as its OCR engine, displays images with interactive word bounding boxes, and allows users to click on detected text regions.

## Environment Setup

### Virtual Environment (Required)
Always activate the virtual environment before running commands:
```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
```

### Dependencies
```bash
pip install -r requirements.txt
```

First-time initialization will download OCR models (~100MB) to `~/.paddlex/official_models/`.

## Running the Application

```bash
source venv/bin/activate
python main.py
```

Or use the convenience scripts:
```bash
./run.sh        # macOS/Linux
run.bat         # Windows
```

## Architecture

### Layered Package Structure

The application is organized into a clean package structure with separation of concerns:

```
ocr_app/
├── core/               # Core business logic
│   ├── ocr_worker.py   # OCRWorker background thread
│   └── pdf_handler.py  # PDF loading and page navigation
├── ui/                 # User interface components
│   ├── main_window.py  # Main application window (OCRApp)
│   ├── widgets/        # Custom widgets
│   │   ├── image_viewer.py    # ImageWithBoxes (with mixins)
│   │   ├── image_mixins.py    # ZoomPanMixin, SelectionMixin, RenderingMixin
│   │   └── file_explorer.py   # FileExplorerWidget
│   └── dialogs/        # Dialog windows
│       └── settings_dialog.py # SettingsDialog
└── utils/              # Utility functions
    ├── resources.py    # Resource path helpers, model setup
    └── constants.py    # Application constants
```

### Key Components

1. **`ImageWithBoxes`** (ocr_app/ui/widgets/image_viewer.py): Custom widget using mixin composition
   - **ZoomPanMixin**: Handles zoom (in/out/reset) and pan (drag with middle/right mouse)
   - **SelectionMixin**: Manages selection rectangle, coordinate conversion, handle dragging
   - **RenderingMixin**: Draws image, word boxes, and selection overlay
   - Uses ray-casting algorithm for point-in-polygon detection
   - Key method: `paintEvent()` draws boxes using scaled coordinates with `scale_factor` and offsets

2. **`OCRWorker`** (ocr_app/core/ocr_worker.py): Background QThread for OCR processing
   - Initializes the OCR engine (PaddleOCR v3) with mobile models for speed
   - Uses `predict()` method (not deprecated `ocr()`)
   - Emits signals: `words_detected`, `finished`, `error`, `progress`, `preprocessed_image`
   - Handles both dictionary and list result formats from PaddleOCR
   - Supports cropping for selection-based OCR

3. **`PDFHandler`** (ocr_app/core/pdf_handler.py): PDF file management
   - Loads PDF files using PyMuPDF (fitz)
   - Renders pages to temporary PNG files
   - Caches up to 10 pages for fast navigation
   - Provides page navigation (prev/next) and state management

4. **`OCRApp`** (ocr_app/ui/main_window.py): Main application window
   - 3-panel layout: file explorer, image viewer with boxes, text output
   - Connects OCRWorker signals to UI update slots
   - Manages image/PDF loading with PIL for consistent preprocessing
   - Delegates PDF handling to PDFHandler
   - Uses QSettings for persistent configuration

### PaddleOCR v3 Configuration

The app uses **mobile/slim models** for fast performance:
- Detection: `PP-OCRv4_mobile_det`
- Recognition: `en_PP-OCRv4_mobile_rec`
- Preprocessing disabled: `use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `use_textline_orientation=False`

**Important**: PaddleOCR v3 changed parameter names from v2:
- `use_angle_cls` → `use_textline_orientation`
- `det_*` → `text_det_*` prefix
- `rec_batch_num` → `text_recognition_batch_size`
- `.ocr()` → `.predict()` method

### Coordinate System

Critical for bounding box rendering:
- PaddleOCR returns coordinates in **original image space**
- `ImageWithBoxes` transforms to **display space** using:
  - `scale_factor = scaled_width / original_width`
  - `offset_x`, `offset_y` for centering
- Transformation: `display_x = original_x * scale_factor + offset_x`

### Result Format

PaddleOCR v3 returns `OCRResult` objects with dictionary keys:
- `dt_polys`: Bounding box polygons (4-point coordinates)
- `rec_texts`: Recognized text strings
- `rec_scores`: Confidence scores
- `doc_preprocessor_res`: Contains preprocessed image if document processing enabled

The code handles both v2 list format `[[bbox, (text, score)], ...]` and v3 dictionary format for backwards compatibility.

## Testing

```bash
# Test OCR directly (uses legacy v2 API - outdated)
python test_ocr_direct.py

# Create test image
python create_test.py
```

## Import Examples

```python
# Import core components
from ocr_app.core import OCRWorker, PDFHandler

# Import UI widgets
from ocr_app.ui.widgets import ImageWithBoxes, FileExplorerWidget
from ocr_app.ui.dialogs import SettingsDialog

# Import utilities
from ocr_app.utils import get_resource_path, setup_bundled_models
from ocr_app.utils.constants import DETECTION_MODELS, SUPPORTED_LANGUAGES

# Import main window and entry point
from ocr_app.ui.main_window import OCRApp, main
```

## Mixin Pattern

The `ImageWithBoxes` widget uses mixin composition for modularity:

```python
class ImageWithBoxes(QLabel, ZoomPanMixin, SelectionMixin, RenderingMixin):
    def __init__(self):
        QLabel.__init__(self)
        self.__init_zoom_pan__()      # Initialize zoom/pan properties
        self.__init_selection__()      # Initialize selection properties
        # RenderingMixin has no state, just rendering methods
```

Each mixin is responsible for a specific concern:
- **ZoomPanMixin** (~150 lines): Zoom level, pan offset, zoom/pan methods
- **SelectionMixin** (~250 lines): Selection rectangle, coordinate conversion, handle management
- **RenderingMixin** (~100 lines): Rendering image, word boxes, and selection overlay

## Key Implementation Notes

### When modifying OCR engine initialization:
- Always use mobile models for performance: `text_detection_model_name='PP-OCRv4_mobile_det'`
- Disable heavy preprocessing for speed
- Use `predict()` instead of deprecated `ocr()`
- Test with `test.png` to verify changes

### When modifying bounding box rendering:
- Debug prints are enabled in `paintEvent()` - disable in production
- Ensure coordinate transformations account for aspect ratio and centering
- Test with images of different sizes and aspect ratios

### When adding new features:
- OCR processing must stay in `OCRWorker` thread (non-blocking UI)
- Use Qt signals for thread communication
- Handle both PaddleOCR v2 and v3 result formats for compatibility
