#!/usr/bin/env python3
"""
LiftText Image Text Extractor - Entry Point

This file serves as the entry point for the application.
The main application code is in the ocr_app package.
"""
import sys
from ocr_app.utils.resources import setup_bundled_models

# CRITICAL: Setup bundled models BEFORE importing PaddleOCR
# This must happen before the ocr_app modules are imported
setup_bundled_models()

# Now safe to import the main application
from ocr_app.ui.main_window import main

if __name__ == "__main__":
    sys.exit(main())
