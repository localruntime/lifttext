"""Main application window for PaddleOCR Image Text Extractor"""
import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QScrollArea,
    QProgressBar, QSplitter, QDialog
)
from PySide6.QtCore import Qt, QSettings, QDir, QSize
from PySide6.QtGui import QPixmap, QPalette, QColor, QFont
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

        # Central widget and main horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        horizontal_layout = QHBoxLayout(central_widget)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_layout.setSpacing(0)

        # Create left sidebar toolbar
        left_sidebar = self._create_left_sidebar()
        horizontal_layout.addWidget(left_sidebar)

        # Create right side content (everything else)
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)

        # Create main panels
        self.content_splitter = self._create_main_panels()
        main_layout.addWidget(self.content_splitter, 1)  # Stretch factor: expand to fill available space

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { height: 20px; text-align: center; }")
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        horizontal_layout.addWidget(content_widget, 1)

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

    def _create_left_sidebar(self):
        """Create the left sidebar toolbar with Search and Settings buttons"""
        sidebar = QWidget()
        sidebar.setMaximumWidth(50)
        sidebar.setStyleSheet("QWidget { background-color: palette(window); }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        sidebar_layout.setSpacing(10)

        # Search/Upload button at the top
        self.upload_btn = QPushButton()
        self.upload_btn.setIcon(MaterialIcon('search'))
        self.upload_btn.setIconSize(QSize(24, 24))
        self.upload_btn.setToolTip("Upload Image or PDF")
        self.upload_btn.setMinimumSize(40, 40)
        self.upload_btn.setMaximumSize(40, 40)
        self.upload_btn.clicked.connect(self.upload_image)
        sidebar_layout.addWidget(self.upload_btn)

        # Add stretch to push Settings button to the bottom
        sidebar_layout.addStretch()

        # Settings button at the bottom
        settings_btn = QPushButton()
        settings_btn.setIcon(MaterialIcon('settings'))
        settings_btn.setIconSize(QSize(24, 24))
        settings_btn.setToolTip("Settings (Ctrl+,)")
        settings_btn.setMinimumSize(40, 40)
        settings_btn.setMaximumSize(40, 40)
        settings_btn.clicked.connect(self.show_settings_dialog)
        sidebar_layout.addWidget(settings_btn)

        return sidebar

    def _create_main_panels(self):
        """Create the main 3-panel layout"""
        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL: File Explorer
        self.explorer_widget = FileExplorerWidget(self)
        self.explorer_widget.file_selected.connect(self.on_file_selected)
        self.explorer_widget.upload_requested.connect(self.upload_image)
        self.explorer_widget.restore_last_directory(self.settings)

        # CENTER PANEL: Image Viewer
        image_panel = QWidget()
        # Set background color for the entire image panel
        image_panel.setStyleSheet("""
            QWidget {
                background-color: rgb(252, 252, 252);
            }
            QPushButton {
                background-color: palette(button);
            }
        """)
        image_panel.setAutoFillBackground(True)
        image_container = QVBoxLayout(image_panel)
        image_container.setContentsMargins(5, 5, 5, 5)

        # Add action toolbar (Scan and Select Area buttons)
        action_toolbar = QHBoxLayout()
        action_toolbar.setContentsMargins(0, 5, 0, 5)
        action_toolbar.setSpacing(5)

        # Scan button (smart - handles both full image and selection)
        self.process_btn = QPushButton("Scan")
        self.process_btn.setToolTip("Scan the full image, or the selected area if a selection is active")
        self.process_btn.clicked.connect(self.process)
        self.process_btn.setEnabled(False)
        action_toolbar.addWidget(self.process_btn)

        action_toolbar.addStretch()  # Push Select Area button to the right

        # Selection mode toggle button
        self.select_area_btn = QPushButton()
        self.select_area_btn.setIcon(MaterialIcon('crop_free'))
        self.select_area_btn.setIconSize(QSize(20, 20))
        self.select_area_btn.setToolTip("Select Area")
        self.select_area_btn.setMaximumWidth(40)
        self.select_area_btn.setCheckable(True)
        self.select_area_btn.clicked.connect(self.toggle_selection_mode)
        self.select_area_btn.setEnabled(False)
        action_toolbar.addWidget(self.select_area_btn)

        image_container.addLayout(action_toolbar)

        # Create horizontal layout for left toolbar and image viewer
        viewer_layout = QHBoxLayout()
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(5)

        # LEFT VERTICAL TOOLBAR (Zoom and PDF pagination controls)
        left_toolbar = QWidget()
        left_toolbar.setStyleSheet("QWidget { background-color: rgb(252, 252, 252); }")
        left_toolbar_layout = QVBoxLayout(left_toolbar)
        left_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        left_toolbar_layout.setSpacing(8)
        left_toolbar.setMaximumWidth(50)

        # Zoom controls (initially hidden)
        self.zoom_in_btn = QPushButton()
        self.zoom_in_btn.setIcon(MaterialIcon('zoom_in'))
        self.zoom_in_btn.setToolTip("Zoom In (+)")
        self.zoom_in_btn.setIconSize(QSize(24, 24))
        self.zoom_in_btn.setMinimumSize(40, 40)
        self.zoom_in_btn.setMaximumSize(40, 40)
        left_toolbar_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton()
        self.zoom_out_btn.setIcon(MaterialIcon('zoom_out'))
        self.zoom_out_btn.setToolTip("Zoom Out (-)")
        self.zoom_out_btn.setIconSize(QSize(24, 24))
        self.zoom_out_btn.setMinimumSize(40, 40)
        self.zoom_out_btn.setMaximumSize(40, 40)
        left_toolbar_layout.addWidget(self.zoom_out_btn)

        self.zoom_reset_btn = QPushButton()
        self.zoom_reset_btn.setIcon(MaterialIcon('zoom_out_map'))
        self.zoom_reset_btn.setToolTip("Reset Zoom")
        self.zoom_reset_btn.setIconSize(QSize(24, 24))
        self.zoom_reset_btn.setMinimumSize(40, 40)
        self.zoom_reset_btn.setMaximumSize(40, 40)
        left_toolbar_layout.addWidget(self.zoom_reset_btn)

        # Add separator space between zoom and PDF controls
        left_toolbar_layout.addSpacing(20)

        # PDF pagination controls (initially hidden, shown only for PDFs)
        self.prev_page_btn = QPushButton()
        self.prev_page_btn.setIcon(MaterialIcon('keyboard_arrow_up'))
        self.prev_page_btn.setToolTip("Previous Page")
        self.prev_page_btn.setIconSize(QSize(24, 24))
        self.prev_page_btn.setMinimumSize(40, 40)
        self.prev_page_btn.setMaximumSize(40, 40)
        self.prev_page_btn.clicked.connect(self.navigate_to_prev_page)
        left_toolbar_layout.addWidget(self.prev_page_btn)

        self.page_label = QLabel("1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(40)
        self.page_label.setMaximumWidth(40)
        left_toolbar_layout.addWidget(self.page_label)

        self.next_page_btn = QPushButton()
        self.next_page_btn.setIcon(MaterialIcon('keyboard_arrow_down'))
        self.next_page_btn.setToolTip("Next Page")
        self.next_page_btn.setIconSize(QSize(24, 24))
        self.next_page_btn.setMinimumSize(40, 40)
        self.next_page_btn.setMaximumSize(40, 40)
        self.next_page_btn.clicked.connect(self.navigate_to_next_page)
        left_toolbar_layout.addWidget(self.next_page_btn)

        left_toolbar_layout.addStretch()  # Push controls to the top

        # Initially hide zoom and PDF controls
        self.zoom_in_btn.setVisible(False)
        self.zoom_out_btn.setVisible(False)
        self.zoom_reset_btn.setVisible(False)
        self.prev_page_btn.setVisible(False)
        self.page_label.setVisible(False)
        self.next_page_btn.setVisible(False)

        viewer_layout.addWidget(left_toolbar)

        # Image scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(450)
        # Set background color to RGB(252, 252, 252) - force override theme
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: rgb(252, 252, 252) !important;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: rgb(252, 252, 252) !important;
            }
        """)

        self.image_widget = ImageWithBoxes()
        self.image_widget.setAlignment(Qt.AlignCenter)
        self.image_widget.setMinimumSize(400, 400)
        # Set background color without border
        self.image_widget.setStyleSheet("""
            ImageWithBoxes {
                border: none;
                background-color: rgb(252, 252, 252) !important;
            }
        """)
        self.image_widget.word_clicked.connect(self.on_word_box_clicked)
        self.image_widget.selection_changed.connect(self.on_selection_changed)
        self.image_widget.zoom_changed.connect(self.on_zoom_changed)

        scroll_area.setWidget(self.image_widget)

        # Programmatically set the viewport background color to override theme
        viewport_palette = scroll_area.viewport().palette()
        viewport_palette.setColor(QPalette.Window, QColor(252, 252, 252))
        viewport_palette.setColor(QPalette.Base, QColor(252, 252, 252))
        scroll_area.viewport().setPalette(viewport_palette)
        scroll_area.viewport().setAutoFillBackground(True)

        viewer_layout.addWidget(scroll_area, 1)  # Stretch factor 1 to fill remaining space

        # Connect zoom button signals after image_widget is created
        self.zoom_in_btn.clicked.connect(self.image_widget.zoom_in)
        self.zoom_out_btn.clicked.connect(self.image_widget.zoom_out)
        self.zoom_reset_btn.clicked.connect(self.image_widget.zoom_reset)

        image_container.addLayout(viewer_layout, 1)

        # RIGHT PANEL: Text Output
        text_panel = QWidget()
        text_container = QVBoxLayout(text_panel)
        text_container.setContentsMargins(0, 0, 0, 0)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("Extracted text will appear here...")
        # Remove widget padding but keep text content padding
        self.text_output.setStyleSheet("""
            QTextEdit {
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        # Add padding around text content only (not affecting scrollbar)
        self.text_output.document().setDocumentMargin(8)
        text_container.addWidget(self.text_output)

        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        text_container.addWidget(self.copy_btn)

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
            # Reset PDF state before loading new PDF to clear cache
            if self.pdf_handler.current_pdf_path != file_path:
                self.pdf_handler.reset_pdf_state()
            self._load_pdf(file_path)
        else:
            self.pdf_handler.reset_pdf_state()
            self._load_image(file_path)

    def _load_image(self, file_path):
        """Load a regular image file"""
        self.image_path = file_path
        self.status_label.setText(f"Loaded: {os.path.basename(file_path)} - Click 'Scan' to run OCR")

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
        self.text_output.setPlaceholderText("Click 'Scan' to extract text...")

        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)

        # Show zoom controls when image is loaded
        self.zoom_in_btn.setVisible(True)
        self.zoom_out_btn.setVisible(True)
        self.zoom_reset_btn.setVisible(True)

    def _load_pdf(self, pdf_path):
        """Load a PDF file"""
        success, message, first_page_path = self.pdf_handler.load_pdf_file(pdf_path)

        if success and first_page_path:
            self.image_path = first_page_path
            pixmap = QPixmap(first_page_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)

            self.text_output.clear()
            self.text_output.setPlaceholderText("Click 'Scan' to extract text from this page...")

            self.process_btn.setEnabled(True)
            self.select_area_btn.setEnabled(True)

            # Show zoom controls when PDF is loaded
            self.zoom_in_btn.setVisible(True)
            self.zoom_out_btn.setVisible(True)
            self.zoom_reset_btn.setVisible(True)

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
            self.text_output.setPlaceholderText("Click 'Scan' to extract text from this page...")

    def navigate_to_next_page(self):
        """Navigate to next PDF page"""
        page_path = self.pdf_handler.navigate_to_next_page()
        if page_path:
            self.image_path = page_path
            pixmap = QPixmap(page_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)
            self.text_output.clear()
            self.text_output.setPlaceholderText("Click 'Scan' to extract text from this page...")

    def show_pdf_navigation(self):
        """Show PDF navigation controls"""
        self.prev_page_btn.setVisible(True)
        self.page_label.setVisible(True)
        self.next_page_btn.setVisible(True)

    def hide_pdf_navigation(self):
        """Hide PDF navigation controls"""
        self.prev_page_btn.setVisible(False)
        self.page_label.setVisible(False)
        self.next_page_btn.setVisible(False)

    def update_page_label(self):
        """Update page indicator text"""
        current, total = self.pdf_handler.get_page_info()
        self.page_label.setText(str(current))

    def update_page_buttons(self):
        """Enable/disable prev/next based on current page"""
        self.prev_page_btn.setEnabled(self.pdf_handler.can_navigate_prev())
        self.next_page_btn.setEnabled(self.pdf_handler.can_navigate_next())

    # OCR processing methods
    def process(self):
        """Smart process method - handles both full image and selection"""
        if not self.image_path:
            return

        # Check if we have a valid selection
        has_selection = (self.image_widget.selection_rect_original is not None
                         and self.image_widget.validate_selection())

        if has_selection:
            # Process selection path
            crop_rect = self.image_widget.selection_rect_original
            self.image_widget.set_word_data([])
            self.current_crop_rect = crop_rect
            self.is_processing_selection = True
            self.process_btn.setEnabled(False)
            self.select_area_btn.setEnabled(False)
            # Disable zoom and PDF pagination buttons during OCR
            self.zoom_in_btn.setEnabled(False)
            self.zoom_out_btn.setEnabled(False)
            self.zoom_reset_btn.setEnabled(False)
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)
            # Disable file explorer during OCR
            self.explorer_widget.setEnabled(False)
            # Disable text output panel and copy button during OCR
            self.text_output.setEnabled(False)
            self.copy_btn.setEnabled(False)
            self.extract_text(self.image_path, crop_rect)
        else:
            # Process full image path
            self.process_btn.setEnabled(False)
            self.select_area_btn.setEnabled(False)
            # Disable zoom and PDF pagination buttons during OCR
            self.zoom_in_btn.setEnabled(False)
            self.zoom_out_btn.setEnabled(False)
            self.zoom_reset_btn.setEnabled(False)
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)
            # Disable file explorer during OCR
            self.explorer_widget.setEnabled(False)
            # Disable text output panel and copy button during OCR
            self.text_output.setEnabled(False)
            self.copy_btn.setEnabled(False)
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
        # Re-enable zoom buttons
        self.zoom_in_btn.setEnabled(True)
        self.zoom_out_btn.setEnabled(True)
        self.zoom_reset_btn.setEnabled(True)
        # Re-enable PDF pagination buttons based on navigation state
        self.update_page_buttons()
        # Re-enable file explorer
        self.explorer_widget.setEnabled(True)
        # Re-enable text output panel and copy button
        self.text_output.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.is_processing_selection = False

    def on_ocr_error(self, error_msg):
        """Handle OCR errors"""
        self.text_output.setText(error_msg)
        self.status_label.setText("OCR failed")
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)
        # Re-enable zoom buttons
        self.zoom_in_btn.setEnabled(True)
        self.zoom_out_btn.setEnabled(True)
        self.zoom_reset_btn.setEnabled(True)
        # Re-enable PDF pagination buttons based on navigation state
        self.update_page_buttons()
        # Re-enable file explorer
        self.explorer_widget.setEnabled(True)
        # Re-enable text output panel and copy button
        self.text_output.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.is_processing_selection = False

    # Selection methods
    def toggle_selection_mode(self, enabled):
        """Handle selection mode toggle"""
        self.image_widget.set_selection_mode(enabled)

        if enabled:
            self.status_label.setText("Selection mode active - draw a rectangle on the image")
        else:
            # Update UI state when selection mode is disabled
            self.process_btn.setEnabled(True)
            self.current_crop_rect = None
            self.is_processing_selection = False
            self.status_label.setText("Selection mode disabled")

    def on_selection_changed(self, has_selection):
        """Handle selection state changes"""
        is_valid = has_selection and self.image_widget.validate_selection()

        if has_selection and not is_valid:
            self.status_label.setText(f"Selection too small - minimum {self.image_widget.MIN_SELECTION_SIZE}px. 'Scan' will process full image.")
        elif has_selection:
            x, y, w, h = self.image_widget.selection_rect_original
            self.status_label.setText(f"Selection: {w}x{h}px at ({x}, {y}) - Click 'Scan' to run OCR on selection")

    def on_zoom_changed(self, zoom):
        """Handle zoom level changes"""
        # Update tooltips to show current zoom level
        zoom_pct = int(zoom * 100)
        self.zoom_in_btn.setToolTip(f"Zoom In (+)\nCurrent: {zoom_pct}%")
        self.zoom_out_btn.setToolTip(f"Zoom Out (-)\nCurrent: {zoom_pct}%")
        self.zoom_reset_btn.setToolTip(f"Reset Zoom\nCurrent: {zoom_pct}%")

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
