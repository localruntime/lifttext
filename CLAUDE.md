# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PySide6 desktop application for extracting text from images using PaddleOCR v3. The app displays images with interactive word bounding boxes and allows users to click on detected text regions.

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

First-time initialization will download PaddleOCR models (~100MB) to `~/.paddlex/official_models/`.

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

### Single-File Application (`main.py`)

The application consists of three main components:

1. **`ImageWithBoxes` (QLabel subclass)**: Custom widget that renders images with clickable word bounding boxes
   - Handles coordinate transformation from original image space to scaled display space
   - Manages hover/selection states for interactive boxes
   - Uses ray-casting algorithm for point-in-polygon detection
   - Key method: `paintEvent()` draws boxes using scaled coordinates with `scale_factor` and offsets

2. **`OCRWorker` (QThread)**: Background thread for OCR processing
   - Initializes PaddleOCR v3 with mobile models for speed
   - Uses `predict()` method (not deprecated `ocr()`)
   - Emits signals: `words_detected`, `finished`, `error`, `progress`, `preprocessed_image`
   - Handles both dictionary and list result formats from PaddleOCR

3. **`OCRApp` (QMainWindow)**: Main application window
   - Side-by-side layout: image viewer with boxes on left, text output on right
   - Connects OCRWorker signals to UI update slots
   - Manages image loading with PIL to ensure consistent preprocessing

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
# Test OCR directly (uses PaddleOCR v2 API - outdated)
python test_ocr_direct.py

# Create test image
python create_test.py
```

## Key Implementation Notes

### When modifying PaddleOCR initialization:
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
