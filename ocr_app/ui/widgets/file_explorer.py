"""File explorer widget for browsing and selecting image/PDF files"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeView, QFileSystemModel, QPushButton
from PySide6.QtCore import Qt, Signal, QDir, QSize
from qt_material_icons import MaterialIcon
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

        # Header label
        label = QLabel("File Explorer")
        layout.addWidget(label)

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
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(20)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)

        # Hide unnecessary columns (keep only name column visible)
        self.tree_view.setHeaderHidden(False)
        self.tree_view.hideColumn(1)  # Size
        self.tree_view.hideColumn(2)  # Type
        self.tree_view.hideColumn(3)  # Date modified

        # Single selection mode
        self.tree_view.setSelectionMode(QTreeView.SingleSelection)

        # Connect single-click signal
        self.tree_view.clicked.connect(self.on_item_clicked)

        layout.addWidget(self.tree_view)

        # Upload button at the bottom with folder icon
        self.upload_btn = QPushButton()
        self.upload_btn.setIcon(MaterialIcon('folder_open'))
        self.upload_btn.setIconSize(QSize(24, 24))
        self.upload_btn.setToolTip("Upload Image or PDF")
        self.upload_btn.clicked.connect(self.upload_requested.emit)
        layout.addWidget(self.upload_btn)

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
