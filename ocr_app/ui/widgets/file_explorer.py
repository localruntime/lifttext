"""File explorer widget for browsing and selecting image/PDF files"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeView, QFileSystemModel
from PySide6.QtCore import Qt, Signal, QDir, QSize
from PySide6.QtGui import QFont
import os


class FileExplorerWidget(QWidget):
    """File explorer widget with image file filtering"""
    file_selected = Signal(str)  # Emits absolute file path when image selected
    upload_requested = Signal()  # Emits when upload button is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = None  # Set by parent
        self.current_directory = QDir.homePath()
        self.init_ui()

    def init_ui(self):
        """Initialize the file explorer UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Configure font size (80% of default = 20% decrease)
        default_font = QFont()
        smaller_font = QFont(default_font)
        smaller_font.setPointSizeF(default_font.pointSizeF() * 0.8)

        # File system model
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.rootPath())

        # Image and PDF file filters (only show these extensions)
        self.file_model.setNameFilters([
            '*.png', '*.PNG',
            '*.jpg', '*.JPG', '*.jpeg', '*.JPEG',
            '*.bmp', '*.BMP',
            '*.gif', '*.GIF',
            '*.tiff', '*.TIFF', '*.tif', '*.TIF',
            '*.pdf', '*.PDF'
        ])
        self.file_model.setNameFilterDisables(False)  # Hide non-matching files

        # Tree view
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        # Don't set root index - allow navigation to entire file system
        # self.tree_view.setRootIndex(self.file_model.index(QDir.homePath()))

        # Configure tree view appearance
        self.tree_view.setFont(smaller_font)
        # Use stylesheet to override Material Design theme font
        font_size = int(smaller_font.pointSizeF())
        self.tree_view.setStyleSheet(f"""
            QTreeView {{
                font-size: {font_size}pt !important;
            }}
            QTreeView::item {{
                padding: 0px 2px !important;
                margin: 0px !important;
                height: 20px !important;
                min-height: 20px !important;
                max-height: 20px !important;
            }}
            QTreeView::branch {{
                width: 10px !important;
            }}
            QScrollBar:vertical {{
                background: rgb(240, 240, 240);
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: rgb(180, 180, 180);
                min-height: 20px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgb(150, 150, 150);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: rgb(240, 240, 240);
                height: 8px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: rgb(180, 180, 180);
                min-width: 20px;
                border-radius: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: rgb(150, 150, 150);
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)
        # Set smaller icon size
        self.tree_view.setIconSize(QSize(12, 12))
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(12)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)

        # Hide header bar completely
        self.tree_view.setHeaderHidden(True)
        self.tree_view.hideColumn(1)  # Size
        self.tree_view.hideColumn(2)  # Type
        self.tree_view.hideColumn(3)  # Date modified

        # Single selection mode
        self.tree_view.setSelectionMode(QTreeView.SingleSelection)

        # Connect single-click signal
        self.tree_view.clicked.connect(self.on_item_clicked)

        layout.addWidget(self.tree_view)

        # Set minimum width for explorer panel
        self.setMinimumWidth(150)

    def on_item_clicked(self, index):
        """Handle item click - emit signal only for files (not directories)"""
        file_path = self.file_model.filePath(index)

        # Only emit signal for image files, not directories
        if os.path.isfile(file_path):
            self.current_directory = os.path.dirname(file_path)
            self.file_selected.emit(file_path)

    def set_root_path(self, path):
        """Navigate to and expand the given path in the explorer"""
        if os.path.exists(path):
            # If path is a file, use its directory
            if os.path.isfile(path):
                path = os.path.dirname(path)
            self.current_directory = path

            # Expand to and scroll to the directory instead of restricting view
            index = self.file_model.index(path)
            self.tree_view.expand(index)
            self.tree_view.scrollTo(index)
            self.tree_view.setCurrentIndex(index)

    def get_current_directory(self):
        """Return current directory path for use by file dialog"""
        return self.current_directory

    def restore_last_directory(self, settings):
        """Load last used directory from QSettings"""
        self.settings = settings
        saved_dir = settings.value('ui/explorer_last_directory', QDir.homePath())
        self.set_root_path(saved_dir)

    def save_current_directory(self, settings):
        """Save current directory to QSettings for persistence"""
        if self.current_directory:
            settings.setValue('ui/explorer_last_directory', self.current_directory)
