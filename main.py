import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QTextEdit,
                               QFileDialog, QScrollArea, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from paddleocr import PaddleOCR
import os


class ImageWithBoxes(QLabel):
    """Custom widget that displays an image with clickable word boxes"""
    word_clicked = Signal(dict)  # Emits word data when a box is clicked

    def __init__(self):
        super().__init__()
        self.original_pixmap = None
        self.scaled_pixmap = None
        self.word_data = []
        self.selected_word_index = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.setMouseTracking(True)
        self.hovered_word_index = None

    def set_image(self, pixmap):
        """Set the image to display"""
        self.original_pixmap = pixmap
        self.word_data = []
        self.selected_word_index = None
        self.hovered_word_index = None
        # Debug: Print original image dimensions
        print(f"QPixmap dimensions: {pixmap.width()} x {pixmap.height()}")
        self.update_display()

    def set_word_data(self, words):
        """Set word bounding box data"""
        self.word_data = words
        self.update()

    def update_display(self):
        """Update the scaled pixmap and display"""
        if self.original_pixmap:
            # Scale image to fit while maintaining aspect ratio
            scaled = self.original_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.scaled_pixmap = scaled

            # Calculate scale factor and offset for centering
            self.scale_factor = scaled.width() / self.original_pixmap.width()
            self.offset_x = (self.width() - scaled.width()) // 2
            self.offset_y = (self.height() - scaled.height()) // 2

            self.update()

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        self.update_display()

    def paintEvent(self, event):
        """Custom paint to draw image and word boxes"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the scaled image centered
        if self.scaled_pixmap:
            painter.drawPixmap(self.offset_x, self.offset_y, self.scaled_pixmap)

            # Debug: Print paint info
            print(f"Painting {len(self.word_data)} word boxes, scale: {self.scale_factor}, offset: ({self.offset_x}, {self.offset_y})")

            # Draw word boxes
            boxes_drawn = 0
            for idx, word_info in enumerate(self.word_data):
                if 'bbox' in word_info and word_info['bbox']:
                    bbox = word_info['bbox']
                    print(f"Drawing box {idx}: {bbox}")

                    # Convert bbox coordinates to scaled display coordinates
                    scaled_points = []
                    for point in bbox:
                        x = int(point[0] * self.scale_factor + self.offset_x)
                        y = int(point[1] * self.scale_factor + self.offset_y)
                        scaled_points.append(QPoint(x, y))

                    print(f"Scaled points: {[(p.x(), p.y()) for p in scaled_points]}")

                    # Determine box color based on state
                    if idx == self.selected_word_index:
                        pen_color = QColor(25, 118, 210)  # Blue for selected
                        fill_color = QColor(187, 222, 251, 100)  # Light blue fill
                        pen_width = 3
                    elif idx == self.hovered_word_index:
                        pen_color = QColor(33, 150, 243)  # Lighter blue for hover
                        fill_color = QColor(227, 242, 253, 80)  # Very light blue fill
                        pen_width = 2
                    else:
                        pen_color = QColor(76, 175, 80)  # Green for normal
                        fill_color = QColor(76, 175, 80, 50)  # Light green fill
                        pen_width = 2

                    # Draw filled polygon
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(fill_color)
                    painter.drawPolygon(scaled_points)

                    # Draw border
                    pen = QPen(pen_color, pen_width)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawPolygon(scaled_points)
                    boxes_drawn += 1
                else:
                    print(f"Word {idx} has no bbox: {word_info}")

            print(f"Drew {boxes_drawn} boxes")

    def mousePressEvent(self, event):
        """Handle mouse clicks to detect word box selection"""
        if event.button() == Qt.LeftButton:
            click_pos = event.pos()

            # Check which word box was clicked (in reverse order for top-most)
            for idx in range(len(self.word_data) - 1, -1, -1):
                word_info = self.word_data[idx]
                if 'bbox' in word_info and word_info['bbox']:
                    bbox = word_info['bbox']

                    # Convert bbox to scaled coordinates
                    scaled_points = []
                    for point in bbox:
                        x = int(point[0] * self.scale_factor + self.offset_x)
                        y = int(point[1] * self.scale_factor + self.offset_y)
                        scaled_points.append(QPoint(x, y))

                    # Check if click is inside polygon
                    if self.point_in_polygon(click_pos, scaled_points):
                        self.selected_word_index = idx
                        self.word_clicked.emit(word_info)
                        self.update()
                        break

    def mouseMoveEvent(self, event):
        """Handle mouse hover to highlight word boxes"""
        hover_pos = event.pos()
        found_hover = False

        # Check which word box is hovered (in reverse order for top-most)
        for idx in range(len(self.word_data) - 1, -1, -1):
            word_info = self.word_data[idx]
            if 'bbox' in word_info and word_info['bbox']:
                bbox = word_info['bbox']

                # Convert bbox to scaled coordinates
                scaled_points = []
                for point in bbox:
                    x = int(point[0] * self.scale_factor + self.offset_x)
                    y = int(point[1] * self.scale_factor + self.offset_y)
                    scaled_points.append(QPoint(x, y))

                # Check if hover is inside polygon
                if self.point_in_polygon(hover_pos, scaled_points):
                    if self.hovered_word_index != idx:
                        self.hovered_word_index = idx
                        self.setCursor(Qt.PointingHandCursor)
                        self.update()
                    found_hover = True
                    break

        if not found_hover and self.hovered_word_index is not None:
            self.hovered_word_index = None
            self.setCursor(Qt.ArrowCursor)
            self.update()

    def point_in_polygon(self, point, polygon):
        """Check if a point is inside a polygon using ray casting algorithm"""
        x, y = point.x(), point.y()
        n = len(polygon)
        inside = False

        p1 = polygon[0]
        for i in range(1, n + 1):
            p2 = polygon[i % n]
            if y > min(p1.y(), p2.y()):
                if y <= max(p1.y(), p2.y()):
                    if x <= max(p1.x(), p2.x()):
                        if p1.y() != p2.y():
                            xinters = (y - p1.y()) * (p2.x() - p1.x()) / (p2.y() - p1.y()) + p1.x()
                        if p1.x() == p2.x() or x <= xinters:
                            inside = not inside
            p1 = p2

        return inside


class OCRWorker(QThread):
    """Worker thread for OCR processing to keep UI responsive"""
    finished = Signal(str)
    words_detected = Signal(list)  # Emits list of word dictionaries
    error = Signal(str)
    progress = Signal(str)
    preprocessed_image = Signal(str)  # ADD THIS: Signal to send preprocessed image path

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.ocr = None

    def run(self):
        try:
            # Initialize PaddleOCR v3 with mobile/slim models for fast performance
            self.progress.emit("Initializing PaddleOCR v3 (this may take a while on first run)...")
            self.ocr = PaddleOCR(
                # Use mobile/slim models for faster performance
                text_detection_model_name='PP-OCRv4_mobile_det',      # Mobile detection model
                text_recognition_model_name='en_PP-OCRv4_mobile_rec', # Mobile recognition model

                # Disable heavy preprocessing for speed
                use_doc_orientation_classify=False,  # Disable document orientation classification
                use_doc_unwarping=False,             # Disable document unwarping
                use_textline_orientation=False,      # Disable text orientation detection
                lang='en',

                # Detection optimizations (v3 uses text_det_* prefix)
                text_det_limit_side_len=960,     # Lower for faster processing (480-960 range)
                text_det_thresh=0.3,             # Detection threshold
                text_det_box_thresh=0.5,         # Box threshold

                # Recognition optimizations (v3 uses text_recognition_* prefix)
                text_recognition_batch_size=6    # Batch size (adjust based on available memory)
            )

            # Perform OCR (v3 uses predict method)
            self.progress.emit("Running OCR on image...")
            result = self.ocr.predict(self.image_path)

            # Debug: Print result structure
            print(f"OCR Result type: {type(result)}")

            # Extract text from results
            self.progress.emit("Extracting text from results...")
            text_lines = []
            word_data = []

            # PaddleOCR can return different formats
            if result and isinstance(result, list) and len(result) > 0:
                page_result = result[0]

                if page_result is None:
                    print("No text detected - page_result is None")

                # Handle dictionary format (newer PaddleOCR)
                elif isinstance(page_result, dict):
                    print(f"Dictionary format detected")
                    
                    # EXTRACT AND SAVE THE PREPROCESSED IMAGE
                    if 'doc_preprocessor_res' in page_result:
                        preprocessed_img = page_result['doc_preprocessor_res'].get('output_img')
                        
                        if preprocessed_img is not None:
                            import tempfile
                            from PIL import Image
                            
                            # Save preprocessed image to temp file
                            temp_path = tempfile.mktemp(suffix='.png')
                            Image.fromarray(preprocessed_img).save(temp_path)
                            print(f"Saved preprocessed image to: {temp_path}")
                            
                            # Emit signal with preprocessed image path
                            self.preprocessed_image.emit(temp_path)

                    # Extract data from dictionary (try both singular and plural keys)
                    bboxes = page_result.get('dt_polys', [])
                    texts = page_result.get('rec_texts', page_result.get('rec_text', []))
                    scores = page_result.get('rec_scores', page_result.get('rec_score', []))

                    print(f"Found {len(texts)} texts, {len(bboxes)} bboxes, {len(scores)} scores")

                    # Combine the data
                    for idx in range(len(texts)):
                        text_content = str(texts[idx])
                        text_lines.append(text_content)

                        word_entry = {
                            'text': text_content,
                            'index': idx
                        }

                        # Add confidence if available
                        if idx < len(scores):
                            confidence = scores[idx]
                            word_entry['confidence'] = f"{confidence:.2%}" if isinstance(confidence, (int, float)) else str(confidence)
                        else:
                            word_entry['confidence'] = 'N/A'

                        # Add bounding box if available
                        if idx < len(bboxes):
                            bbox = bboxes[idx]
                            # Convert numpy array or other formats to list
                            if hasattr(bbox, 'tolist'):
                                bbox = bbox.tolist()
                            word_entry['bbox'] = bbox
                            print(f"Word {idx}: '{text_content}' with bbox: {bbox}")
                        else:
                            print(f"Word {idx}: '{text_content}' - NO BBOX")

                        word_data.append(word_entry)

                # Handle list format (older PaddleOCR): [[bbox, (text, confidence)], ...]
                elif isinstance(page_result, list):
                    print(f"List format detected - Processing {len(page_result)} detected text regions")

                    for idx, detection in enumerate(page_result):
                        if detection and len(detection) >= 2:
                            bbox = detection[0]  # Bounding box coordinates
                            text_info = detection[1]  # (text, confidence) tuple

                            # Extract text and confidence
                            if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                                text_content = str(text_info[0])
                                confidence = text_info[1] if len(text_info) > 1 else None
                            else:
                                text_content = str(text_info)
                                confidence = None

                            text_lines.append(text_content)

                            # Create word data with bounding box
                            word_entry = {
                                'text': text_content,
                                'confidence': f"{confidence:.2%}" if isinstance(confidence, float) else 'N/A',
                                'index': idx
                            }

                            # Add bounding box if available
                            if bbox:
                                if hasattr(bbox, 'tolist'):
                                    bbox = bbox.tolist()
                                word_entry['bbox'] = bbox
                                print(f"Word {idx}: '{text_content}' with bbox: {bbox}")
                            else:
                                print(f"Word {idx}: '{text_content}' - NO BBOX")

                            word_data.append(word_entry)
                else:
                    print(f"Unexpected page_result type: {type(page_result)}")

            extracted_text = '\n'.join(text_lines) if text_lines else "No text detected in image"
            print(f"Total words extracted: {len(word_data)}")
            self.words_detected.emit(word_data)
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
        self.word_data = []  # Store detected words data
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

        # Image with word boxes display area
        image_container = QVBoxLayout()
        image_label = QLabel("Image with Detected Words")
        image_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        image_container.addWidget(image_label)

        # Scroll area for image
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(450)

        # Custom image widget with word boxes
        self.image_widget = ImageWithBoxes()
        self.image_widget.setAlignment(Qt.AlignCenter)
        self.image_widget.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc;")
        self.image_widget.setMinimumSize(400, 400)
        self.image_widget.word_clicked.connect(self.on_word_box_clicked)

        scroll_area.setWidget(self.image_widget)
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
            self.status_label.setText(f"Loaded: {os.path.basename(file_name)}")

            # Load image same way PaddleOCR does
            from PIL import Image
            import numpy as np
            
            pil_image = Image.open(file_name)
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Save to temporary file to ensure consistent loading
            import tempfile
            temp_path = tempfile.mktemp(suffix='.png')
            pil_image.save(temp_path)
            
            # Now load into QPixmap
            pixmap = QPixmap(temp_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)
                print(f"Loaded pixmap: {pixmap.width()}x{pixmap.height()}")

            self.text_output.clear()
            self.extract_text(file_name)  # Still use original file

    def extract_text(self, image_path):
        self.text_output.setText("Initializing OCR...")
        self.status_label.setText("Starting OCR process...")

        # Create and start worker thread
        self.ocr_worker = OCRWorker(image_path)
        self.ocr_worker.finished.connect(self.on_ocr_complete)
        self.ocr_worker.words_detected.connect(self.on_words_detected)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.progress.connect(self.on_ocr_progress)
        self.ocr_worker.preprocessed_image.connect(self.on_preprocessed_image)  # ADD THIS
        self.ocr_worker.start()

    def on_preprocessed_image(self, image_path):
        """Update display with the preprocessed image that OCR actually used"""
        print(f"Loading preprocessed image: {image_path}")
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_widget.set_image(pixmap)
            print(f"Loaded preprocessed image: {pixmap.width()}x{pixmap.height()}")
        else:
            print("Failed to load preprocessed image")        

    def on_ocr_progress(self, status):
        self.status_label.setText(status)
        self.text_output.setText(f"Processing...\n\n{status}")

    def on_words_detected(self, words):
        """Set word data on the image widget"""
        self.word_data = words

        # Debug: Print word data
        print(f"Received {len(words)} words")
        for i, word in enumerate(words):
            print(f"Word {i}: {word}")

        self.image_widget.set_word_data(words)

        if not words:
            self.text_output.setText("No words detected in image")
        else:
            # Count words with bounding boxes
            words_with_bbox = sum(1 for w in words if 'bbox' in w and w['bbox'])
            self.text_output.setText(f"Detected {len(words)} word(s) ({words_with_bbox} with bounding boxes). Click on a word box to see details.")

    def on_word_box_clicked(self, word_info):
        """Display word details when a word box is clicked"""
        if word_info:
            details = f"Word: {word_info.get('text', 'N/A')}\n"
            details += f"Confidence: {word_info.get('confidence', 'N/A')}\n"
            details += f"Index: {word_info.get('index', 'N/A')}\n"

            if 'bbox' in word_info and word_info['bbox']:
                details += f"\nBounding Box:\n"
                bbox = word_info['bbox']
                for i, point in enumerate(bbox):
                    details += f"  Point {i+1}: ({point[0]:.1f}, {point[1]:.1f})\n"

            self.text_output.setText(details)

    def on_ocr_complete(self, text):
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
