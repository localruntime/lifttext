# PaddleOCR Image Text Extractor

A PySide6 application that allows users to upload images and extract text using PaddleOCR.

## Requirements

- Python 3.8 or higher

## Quick Start

### macOS/Linux

1. Run the setup script:
```bash
chmod +x setup.sh run.sh
./setup.sh
```

2. Run the application:
```bash
./run.sh
```

### Windows

1. Run the setup script:
```cmd
setup.bat
```

2. Run the application:
```cmd
run.bat
```

## Manual Installation

If you prefer to set up manually:

### macOS/Linux

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python main.py
```

### Windows

1. Create a virtual environment:
```cmd
python -m venv venv
```

2. Activate the virtual environment:
```cmd
venv\Scripts\activate.bat
```

3. Install dependencies:
```cmd
pip install -r requirements.txt
```

4. Run the application:
```cmd
python main.py
```

### Build for prod distro

```cmd
source venv/bin/activate
python setup.py py2app
open dist/PaddleOCR.app
```

### 
  Creating a Distributable DMG

  Once the app is built, create a disk image for distribution:

  # Create a DMG file
  hdiutil create -volname "PaddleOCR" \
    -srcfolder dist/PaddleOCR.app \
    -ov -format UDZO \
    PaddleOCR-1.0.0.dmg

  This creates PaddleOCR-1.0.0.dmg that users can download, open, and drag to Applications.

## Features

- Upload images (PNG, JPG, JPEG, BMP)
- Display uploaded images with automatic scaling
- Extract text using PaddleOCR (Slim model)
- View extracted text in a text area
- Non-blocking OCR processing with threading
- Clean and intuitive user interface
- Lightweight and fast - uses PaddleOCR's slim model for minimal download size and quick processing
