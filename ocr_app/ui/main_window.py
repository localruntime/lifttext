"""Main application window for PaddleOCR Image Text Extractor"""
import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QScrollArea,
    QProgressBar, QSplitter, QDialog
)
from PySide6.QtCore import Qt, QSettings, QDir, QSize
from PySide6.QtGui import QPixmap
from qt_material_icons import MaterialIcon
from PIL import Image
import tempfile

from ocr_app.core import OCRWorker, PDFHandler
from ocr_app.ui.widgets import ImageWithBoxes, FileExplorerWidget
from ocr_app.ui.dialogs import SettingsDialog
from ocr_app.utils.constants import (
    DETECTION_MODELS, RECOGNITION_MODELS,
    SETTINGS_DET_MODEL, SETTINGS_REC_MODEL, SETTINGS_LANGUAGE, SETTINGS_THEME,
    SETTINGS_SPLITTER_SIZES, DEFAULT_DET_MODEL, DEFAULT_REC_MODEL,
    DEFAULT_LANGUAGE, DEFAULT_THEME, DEFAULT_SPLITTER_SIZES
)


class OCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.ocr_worker = None
        self.word_data = []
        self.all_words = []  # Cache all detected words for deselection

        # Selection tracking
        self.current_crop_rect = None
        self.is_processing_selection = False

        # Initialize QSettings for persistence
        self.settings = QSettings('PaddleOCR', 'ImageTextExtractor')

        # Load settings
        self._load_settings()

        # Initialize PDF handler with UI callbacks
        self.pdf_handler = PDFHandler(ui_callbacks={
            'update_page_label': self.update_page_label,
            'update_page_buttons': self.update_page_buttons,
            'show_navigation': self.show_pdf_navigation,
            'hide_navigation': self.hide_pdf_navigation,
        })

        self.init_ui()

    def _load_settings(self):
        """Load application settings from QSettings"""
        # Load model selections with validation
        saved_det_model = self.settings.value(SETTINGS_DET_MODEL, DEFAULT_DET_MODEL)
        saved_rec_model = self.settings.value(SETTINGS_REC_MODEL, DEFAULT_REC_MODEL)

        # Validate saved models exist in current model lists
        self.selected_det_model = saved_det_model if saved_det_model in DETECTION_MODELS else DEFAULT_DET_MODEL
        self.selected_rec_model = saved_rec_model if saved_rec_model in RECOGNITION_MODELS else DEFAULT_REC_MODEL

        # Load language and theme settings
        self.selected_language = self.settings.value(SETTINGS_LANGUAGE, DEFAULT_LANGUAGE)
        self.selected_theme = self.settings.value(SETTINGS_THEME, DEFAULT_THEME)

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("LiftText")
        self.setGeometry(100, 100, 1000, 700)

        # Create menu bar
        self._create_menu_bar()

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create toolbar
        button_layout = self._create_toolbar()
        main_layout.addLayout(button_layout)

        # Create main panels
        self.content_splitter = self._create_main_panels()
        main_layout.addWidget(self.content_splitter)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { height: 20px; text-align: center; }")
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

    def _create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()

        # File menu (placeholder for future)
        file_menu = menubar.addMenu("&File")

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        settings_action = edit_menu.addAction("Settings...")
        settings_action.setIcon(MaterialIcon('settings'))
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings_dialog)

    def _create_toolbar(self):
        """Create the toolbar with buttons and controls"""
        button_layout = QHBoxLayout()

        # Upload button
        upload_btn = QPushButton("Upload Image")
        upload_btn.clicked.connect(self.upload_image)
        button_layout.addWidget(upload_btn)

        # Process image button
        self.process_btn = QPushButton("Process Image")
        self.process_btn.clicked.connect(self.process_image)
        self.process_btn.setEnabled(False)
        button_layout.addWidget(self.process_btn)

        # PDF Navigation Controls (initially hidden)
        self.pdf_nav_widget = QWidget()
        pdf_nav_layout = QHBoxLayout(self.pdf_nav_widget)
        pdf_nav_layout.setContentsMargins(0, 0, 0, 0)

        self.prev_page_btn = QPushButton("← Prev")
        self.prev_page_btn.clicked.connect(self.navigate_to_prev_page)
        pdf_nav_layout.addWidget(self.prev_page_btn)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(100)
        pdf_nav_layout.addWidget(self.page_label)

        self.next_page_btn = QPushButton("Next →")
        self.next_page_btn.clicked.connect(self.navigate_to_next_page)
        pdf_nav_layout.addWidget(self.next_page_btn)

        button_layout.addWidget(self.pdf_nav_widget)
        self.pdf_nav_widget.setVisible(False)

        # Selection mode toggle button
        self.select_area_btn = QPushButton()
        self.select_area_btn.setIcon(MaterialIcon('crop_free'))
        self.select_area_btn.setIconSize(QSize(20, 20))
        self.select_area_btn.setToolTip("Select Area")
        self.select_area_btn.setMaximumWidth(40)
        self.select_area_btn.setCheckable(True)
        self.select_area_btn.clicked.connect(self.toggle_selection_mode)
        self.select_area_btn.setEnabled(False)
        button_layout.addWidget(self.select_area_btn)

        # Process selection button
        self.process_selection_btn = QPushButton("Process Selection")
        self.process_selection_btn.clicked.connect(self.process_selection)
        self.process_selection_btn.setEnabled(False)
        button_layout.addWidget(self.process_selection_btn)

        # Clear selection button
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setEnabled(False)
        button_layout.addWidget(self.clear_selection_btn)

        # Settings button
        settings_btn = QPushButton()
        settings_btn.setIcon(MaterialIcon('settings'))
        settings_btn.setIconSize(QSize(20, 20))
        settings_btn.setToolTip("Settings (Ctrl+,)")
        settings_btn.setMaximumWidth(40)
        settings_btn.clicked.connect(self.show_settings_dialog)
        button_layout.addWidget(settings_btn)

        return button_layout

    def _create_main_panels(self):
        """Create the main 3-panel layout"""
        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL: File Explorer
        self.explorer_widget = FileExplorerWidget(self)
        self.explorer_widget.file_selected.connect(self.on_file_selected)
        self.explorer_widget.restore_last_directory(self.settings)

        # CENTER PANEL: Image Viewer
        image_panel = QWidget()
        image_container = QVBoxLayout(image_panel)
        image_container.setContentsMargins(5, 5, 5, 5)

        image_label = QLabel("Image with Detected Words")
        image_container.addWidget(image_label)

        # Add zoom controls toolbar (inline, above scroll area)
        zoom_toolbar = QHBoxLayout()
        zoom_toolbar.setContentsMargins(0, 5, 0, 5)
        zoom_toolbar.setSpacing(5)

        zoom_in_btn = QPushButton()
        zoom_in_btn.setIcon(MaterialIcon('zoom_in'))
        zoom_in_btn.setToolTip("Zoom In (+)")
        zoom_in_btn.setIconSize(QSize(20, 20))
        zoom_in_btn.setMaximumWidth(40)
        zoom_toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton()
        zoom_out_btn.setIcon(MaterialIcon('zoom_out'))
        zoom_out_btn.setToolTip("Zoom Out (-)")
        zoom_out_btn.setIconSize(QSize(20, 20))
        zoom_out_btn.setMaximumWidth(40)
        zoom_toolbar.addWidget(zoom_out_btn)

        zoom_reset_btn = QPushButton()
        zoom_reset_btn.setIcon(MaterialIcon('zoom_out_map'))
        zoom_reset_btn.setToolTip("Reset Zoom")
        zoom_reset_btn.setIconSize(QSize(20, 20))
        zoom_reset_btn.setMaximumWidth(40)
        zoom_toolbar.addWidget(zoom_reset_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)
        zoom_toolbar.addWidget(self.zoom_label)

        zoom_toolbar.addStretch()  # Push buttons to the left
        image_container.addLayout(zoom_toolbar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(450)

        self.image_widget = ImageWithBoxes()
        self.image_widget.setAlignment(Qt.AlignCenter)
        self.image_widget.setMinimumSize(400, 400)
        self.image_widget.word_clicked.connect(self.on_word_box_clicked)
        self.image_widget.selection_changed.connect(self.on_selection_changed)

        # Connect zoom button signals
        zoom_in_btn.clicked.connect(self.image_widget.zoom_in)
        zoom_out_btn.clicked.connect(self.image_widget.zoom_out)
        zoom_reset_btn.clicked.connect(self.image_widget.zoom_reset)
        self.image_widget.zoom_changed.connect(lambda zoom: self.zoom_label.setText(f"{int(zoom * 100)}%"))

        scroll_area.setWidget(self.image_widget)
        image_container.addWidget(scroll_area)

        # RIGHT PANEL: Text Output
        text_panel = QWidget()
        text_container = QVBoxLayout(text_panel)
        text_container.setContentsMargins(5, 5, 5, 5)

        text_label = QLabel("Extracted Text")
        text_container.addWidget(text_label)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("Extracted text will appear here...")
        text_container.addWidget(self.text_output)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        text_container.addWidget(copy_btn)

        # Assemble splitter
        splitter.addWidget(self.explorer_widget)
        splitter.addWidget(image_panel)
        splitter.addWidget(text_panel)

        # Set initial sizes
        saved_sizes = self.settings.value(SETTINGS_SPLITTER_SIZES, DEFAULT_SPLITTER_SIZES)
        if isinstance(saved_sizes, str):
            saved_sizes = [int(x) for x in saved_sizes.split(',')]
        elif not isinstance(saved_sizes, list):
            saved_sizes = DEFAULT_SPLITTER_SIZES
        splitter.setSizes(saved_sizes)

        # Make explorer collapsible
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)

        # Connect splitter moved signal
        splitter.splitterMoved.connect(self.on_splitter_moved)

        return splitter

    # File loading methods
    def upload_image(self):
        """Upload image via file dialog"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image or PDF",
            self.explorer_widget.get_current_directory(),
            "Image and PDF Files (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.pdf);;All Files (*)"
        )

        if file_name:
            self.load_image_from_path(file_name)
            self.explorer_widget.set_root_path(os.path.dirname(file_name))
            self.explorer_widget.save_current_directory(self.settings)

    def on_file_selected(self, file_path):
        """Handle file selection from explorer"""
        if os.path.exists(file_path) and self._is_valid_file(file_path):
            self.load_image_from_path(file_path)
            self.explorer_widget.save_current_directory(self.settings)

    def load_image_from_path(self, file_path):
        """Load image or PDF from given path"""
        if self._is_pdf_file(file_path):
            self._load_pdf(file_path)
        else:
            self.pdf_handler.reset_pdf_state()
            self._load_image(file_path)

    def _load_image(self, file_path):
        """Load a regular image file"""
        self.image_path = file_path
        self.status_label.setText(f"Loaded: {os.path.basename(file_path)} - Click 'Process Image' to run OCR")

        # Load image same way PaddleOCR does
        pil_image = Image.open(file_path)
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Save to temporary file
        temp_path = tempfile.mktemp(suffix='.png')
        pil_image.save(temp_path)

        # Load into QPixmap
        pixmap = QPixmap(temp_path)
        if not pixmap.isNull():
            self.image_widget.set_image(pixmap)

        self.text_output.clear()
        self.text_output.setPlaceholderText("Click 'Process Image' to extract text...")

        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)

    def _load_pdf(self, pdf_path):
        """Load a PDF file"""
        success, message, first_page_path = self.pdf_handler.load_pdf_file(pdf_path)

        if success and first_page_path:
            self.image_path = first_page_path
            pixmap = QPixmap(first_page_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)

            self.text_output.clear()
            self.text_output.setPlaceholderText("Click 'Process Image' to extract text from this page...")

            self.process_btn.setEnabled(True)
            self.select_area_btn.setEnabled(True)

        self.status_label.setText(message)

    def _is_pdf_file(self, file_path):
        """Check if file is a PDF"""
        return file_path.lower().endswith('.pdf')

    def _is_valid_file(self, file_path):
        """Check if file is a valid image or PDF"""
        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.pdf')
        return file_path.lower().endswith(valid_extensions)

    # PDF navigation methods
    def navigate_to_prev_page(self):
        """Navigate to previous PDF page"""
        page_path = self.pdf_handler.navigate_to_prev_page()
        if page_path:
            self.image_path = page_path
            pixmap = QPixmap(page_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)
            self.text_output.clear()
            self.text_output.setPlaceholderText("Click 'Process Image' to extract text from this page...")

    def navigate_to_next_page(self):
        """Navigate to next PDF page"""
        page_path = self.pdf_handler.navigate_to_next_page()
        if page_path:
            self.image_path = page_path
            pixmap = QPixmap(page_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)
            self.text_output.clear()
            self.text_output.setPlaceholderText("Click 'Process Image' to extract text from this page...")

    def show_pdf_navigation(self):
        """Show PDF navigation controls"""
        self.pdf_nav_widget.setVisible(True)

    def hide_pdf_navigation(self):
        """Hide PDF navigation controls"""
        self.pdf_nav_widget.setVisible(False)

    def update_page_label(self):
        """Update page indicator text"""
        current, total = self.pdf_handler.get_page_info()
        self.page_label.setText(f"Page {current} of {total}")

    def update_page_buttons(self):
        """Enable/disable prev/next based on current page"""
        self.prev_page_btn.setEnabled(self.pdf_handler.can_navigate_prev())
        self.next_page_btn.setEnabled(self.pdf_handler.can_navigate_next())

    # OCR processing methods
    def process_image(self):
        """Process the currently loaded image with OCR"""
        if self.image_path:
            self.process_btn.setEnabled(False)
            self.extract_text(self.image_path)

    def extract_text(self, image_path, crop_rect=None):
        """Start OCR worker to extract text"""
        self.text_output.setText("Initializing OCR...")
        self.status_label.setText("Starting OCR process...")

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Create and start worker thread
        self.ocr_worker = OCRWorker(
            image_path,
            det_model=self.selected_det_model,
            rec_model=self.selected_rec_model,
            language=self.selected_language,
            crop_rect=crop_rect
        )
        self.ocr_worker.finished.connect(self.on_ocr_complete)
        self.ocr_worker.words_detected.connect(self.on_words_detected)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.progress.connect(self.on_ocr_progress)
        self.ocr_worker.progress_value.connect(self.on_progress_value_changed)
        self.ocr_worker.preprocessed_image.connect(self.on_preprocessed_image)
        self.ocr_worker.start()

    def on_preprocessed_image(self, image_path):
        """Update display with preprocessed image"""
        if self.is_processing_selection:
            return  # Don't replace image during selection processing

        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_widget.set_image(pixmap)

    def on_ocr_progress(self, status):
        """Handle OCR progress updates"""
        self.status_label.setText(status)
        self.text_output.setText(f"Processing...\n\n{status}")

    def on_progress_value_changed(self, value):
        """Update progress bar value"""
        self.progress_bar.setValue(value)

    def on_words_detected(self, words):
        """Handle detected words from OCR"""
        self.word_data = words
        self.all_words = words
        self.image_widget.set_word_data(words)

        if not words:
            self.text_output.setText("No words detected in image")
        else:
            all_text = '\n'.join(word.get('text', '') for word in words)
            self.text_output.setText(all_text)

    def on_ocr_complete(self, text):
        """Handle OCR completion"""
        self.status_label.setText("OCR completed successfully")
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)
        self.is_processing_selection = False

    def on_ocr_error(self, error_msg):
        """Handle OCR errors"""
        self.text_output.setText(error_msg)
        self.status_label.setText("OCR failed")
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)
        self.is_processing_selection = False

    # Selection methods
    def toggle_selection_mode(self, enabled):
        """Handle selection mode toggle"""
        self.image_widget.set_selection_mode(enabled)

        if enabled:
            self.process_btn.setEnabled(False)
            self.status_label.setText("Selection mode active - draw a rectangle on the image")
        else:
            self.process_btn.setEnabled(True)
            self.status_label.setText("Selection mode disabled")

    def process_selection(self):
        """Process the selected area with OCR"""
        if not self.image_widget.selection_rect_original:
            return

        if not self.image_widget.validate_selection():
            self.status_label.setText(f"Selection too small - minimum {self.image_widget.MIN_SELECTION_SIZE}px")
            return

        crop_rect = self.image_widget.selection_rect_original
        if crop_rect and self.image_path:
            self.image_widget.set_word_data([])
            self.current_crop_rect = crop_rect
            self.is_processing_selection = True
            self.process_selection_btn.setEnabled(False)
            self.select_area_btn.setEnabled(False)
            self.extract_text(self.image_path, crop_rect)

    def clear_selection(self):
        """Clear the selection and return to normal mode"""
        self.image_widget.clear_selection()
        self.image_widget.set_selection_mode(False)
        self.select_area_btn.setChecked(False)
        self.process_btn.setEnabled(True)
        self.current_crop_rect = None
        self.is_processing_selection = False
        self.status_label.setText("Selection cleared")

    def on_selection_changed(self, has_selection):
        """Handle selection state changes"""
        is_valid = has_selection and self.image_widget.validate_selection()
        self.process_selection_btn.setEnabled(is_valid)
        self.clear_selection_btn.setEnabled(has_selection)

        if has_selection and not is_valid:
            self.status_label.setText(f"Selection too small - minimum {self.image_widget.MIN_SELECTION_SIZE}px")
        elif has_selection:
            x, y, w, h = self.image_widget.selection_rect_original
            self.status_label.setText(f"Selection: {w}x{h}px at ({x}, {y}) - Click 'Process Selection' to run OCR")

    # Event handlers
    def on_word_box_clicked(self, word_info):
        """Display word when a word box is clicked"""
        if word_info is None:
            if self.all_words:
                all_text = '\n'.join(word.get('text', '') for word in self.all_words)
                self.text_output.setText(all_text)
            else:
                self.text_output.setText("No words detected in image")
        else:
            self.text_output.setText(word_info.get('text', ''))

    def copy_to_clipboard(self):
        """Copy the extracted text to the clipboard"""
        text = self.text_output.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Text copied to clipboard")
        else:
            self.status_label.setText("No text to copy")

    def on_splitter_moved(self, pos, index):
        """Save splitter sizes when user resizes panels"""
        sizes = self.content_splitter.sizes()
        self.settings.setValue(SETTINGS_SPLITTER_SIZES, sizes)

    # Settings dialog
    def show_settings_dialog(self):
        """Show the settings dialog"""
        current_settings = {
            'detection_model': self.selected_det_model,
            'recognition_model': self.selected_rec_model,
            'language': self.selected_language,
            'theme': self.selected_theme,
        }

        dialog = SettingsDialog(self, current_settings)

        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()

            # Save to instance variables
            self.selected_det_model = new_settings['detection_model']
            self.selected_rec_model = new_settings['recognition_model']
            self.selected_language = new_settings['language']
            self.selected_theme = new_settings['theme']

            # Save to QSettings
            self.settings.setValue(SETTINGS_DET_MODEL, new_settings['detection_model'])
            self.settings.setValue(SETTINGS_REC_MODEL, new_settings['recognition_model'])
            self.settings.setValue(SETTINGS_LANGUAGE, new_settings['language'])
            self.settings.setValue(SETTINGS_THEME, new_settings['theme'])

            # Apply theme immediately
            try:
                from qt_material import apply_stylesheet
                apply_stylesheet(QApplication.instance(), theme=new_settings['theme'])
            except Exception as e:
                print(f"Warning: Could not apply theme: {e}")

            # Update status
            theme_name = new_settings['theme'].replace('.xml', '').replace('_', ' ').title()
            self.status_label.setText(
                f"Settings saved: {new_settings['detection_model']}, "
                f"{new_settings['recognition_model']}, "
                f"lang={new_settings['language']}, "
                f"theme={theme_name}. "
                f"Process image to apply OCR changes."
            )


def main():
    """Application entry point"""
    app = QApplication(sys.argv)

    # Apply Material Design theme
    try:
        from qt_material import apply_stylesheet
        settings = QSettings('PaddleOCR', 'ImageTextExtractor')
        theme = settings.value('ui/theme', 'light_blue.xml')
        apply_stylesheet(app, theme=theme)
    except ImportError:
        print("Warning: qt-material not installed. Using default Qt styling.")
    except Exception as e:
        print(f"Warning: Could not apply theme: {e}")

    window = OCRApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
