import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QTextEdit,
                               QFileDialog, QScrollArea)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from paddleocr import PaddleOCR
import os


class OCRWorker(QThread):
    """Worker thread for OCR processing to keep UI responsive"""
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.ocr = None

    def run(self):
        try:
            # Initialize PaddleOCR with slim model (smallest and fastest)
            self.progress.emit("Initializing PaddleOCR (this may take a while on first run)...")
            self.ocr = PaddleOCR(
                use_angle_cls=False,
                lang='en',
                det_limit_side_len=480,
                rec_batch_num=3
            )

            # Perform OCR
            self.progress.emit("Running OCR on image...")
            result = self.ocr.ocr(self.image_path)

            # Debug: Print result structure
            print(f"OCR Result type: {type(result)}")
            print(f"OCR Result: {result}")

            # Extract text from results
            self.progress.emit("Extracting text from results...")
            text_lines = []

            if result:
                # Handle different result formats
                if isinstance(result, list) and len(result) > 0:
                    first_result = result[0]

                    # Check if result is dictionary format (newer PaddleOCR with rec_texts key)
                    if isinstance(first_result, dict) and 'rec_texts' in first_result:
                        # Dictionary format with 'rec_texts' key (plural)
                        rec_texts = first_result['rec_texts']
                        if isinstance(rec_texts, list):
                            text_lines = [str(text) for text in rec_texts if text]

                    # Check if result is dictionary format with old key name
                    elif isinstance(first_result, dict) and 'rec_text' in first_result:
                        # Dictionary format with 'rec_text' key (singular)
                        rec_texts = first_result['rec_text']
                        if isinstance(rec_texts, list):
                            text_lines = [str(text) for text in rec_texts if text]

                    # Check if result is list format (older PaddleOCR)
                    elif isinstance(first_result, list):
                        for line in first_result:
                            if line and len(line) >= 2:
                                # line[0] is bounding box, line[1] is (text, confidence)
                                text_content = line[1][0] if isinstance(line[1], (list, tuple)) else line[1]
                                text_lines.append(str(text_content))

            extracted_text = '\n'.join(text_lines) if text_lines else "No text detected in image"
            self.finished.emit(extracted_text)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"OCR Error: {error_details}")
            self.error.emit(f"Error during OCR: {str(e)}\n\nDetails:\n{error_details}")


class OCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.ocr_worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("PaddleOCR Image Text Extractor")
        self.setGeometry(100, 100, 1000, 700)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Upload button
        upload_btn = QPushButton("Upload Image")
        upload_btn.clicked.connect(self.upload_image)
        upload_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        main_layout.addWidget(upload_btn)

        # Content layout (image and text side by side)
        content_layout = QHBoxLayout()

        # Image display area
        image_container = QVBoxLayout()
        image_label = QLabel("Image Preview")
        image_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        image_container.addWidget(image_label)

        # Scroll area for image
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(450)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #f0f0f0; border: 2px dashed #ccc;")
        self.image_label.setText("No image loaded")
        self.image_label.setMinimumSize(400, 400)

        scroll_area.setWidget(self.image_label)
        image_container.addWidget(scroll_area)

        content_layout.addLayout(image_container)

        # Text output area
        text_container = QVBoxLayout()
        text_label = QLabel("Extracted Text")
        text_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        text_container.addWidget(text_label)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("Extracted text will appear here...")
        self.text_output.setStyleSheet("font-size: 12px; padding: 5px;")
        text_container.addWidget(self.text_output)

        content_layout.addLayout(text_container)

        main_layout.addLayout(content_layout)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 5px; background-color: #e8e8e8;")
        main_layout.addWidget(self.status_label)

    def upload_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )

        if file_name:
            self.image_path = file_name
            self.display_image(file_name)
            self.extract_text(file_name)

    def display_image(self, image_path):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # Scale image to fit while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                800, 800,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setAlignment(Qt.AlignCenter)
            self.status_label.setText(f"Loaded: {os.path.basename(image_path)}")
        else:
            self.status_label.setText("Failed to load image")

    def extract_text(self, image_path):
        self.text_output.setText("Initializing OCR...")
        self.status_label.setText("Starting OCR process...")

        # Create and start worker thread
        self.ocr_worker = OCRWorker(image_path)
        self.ocr_worker.finished.connect(self.on_ocr_complete)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.progress.connect(self.on_ocr_progress)
        self.ocr_worker.start()

    def on_ocr_progress(self, status):
        self.status_label.setText(status)
        self.text_output.setText(f"Processing...\n\n{status}")

    def on_ocr_complete(self, text):
        self.text_output.setText(text)
        self.status_label.setText("OCR completed successfully")

    def on_ocr_error(self, error_msg):
        self.text_output.setText(error_msg)
        self.status_label.setText("OCR failed")


def main():
    app = QApplication(sys.argv)
    window = OCRApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
