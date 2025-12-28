"""Settings dialog for OCR configuration"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                               QLabel, QDialogButtonBox, QGroupBox)
from ocr_app.utils.constants import (
    DETECTION_MODELS, RECOGNITION_MODELS, SUPPORTED_LANGUAGES, AVAILABLE_THEMES
)


class SettingsDialog(QDialog):
    """Settings dialog for OCR configuration"""

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(450)

        self.current_settings = current_settings or {}
        self.init_ui()

    def init_ui(self):
        """Initialize the settings dialog UI"""
        layout = QVBoxLayout(self)

        # OCR Models Group
        models_group = QGroupBox("OCR Models")
        models_layout = QFormLayout()

        # Detection model dropdown
        self.det_model_combo = QComboBox()
        self.det_model_combo.addItems(DETECTION_MODELS)
        current_det = self.current_settings.get('detection_model', 'PP-OCRv4_mobile_det')
        if current_det in DETECTION_MODELS:
            self.det_model_combo.setCurrentText(current_det)
        models_layout.addRow("Detection Model:", self.det_model_combo)

        # Recognition model dropdown
        self.rec_model_combo = QComboBox()
        self.rec_model_combo.addItems(RECOGNITION_MODELS)
        current_rec = self.current_settings.get('recognition_model', 'en_PP-OCRv4_mobile_rec')
        if current_rec in RECOGNITION_MODELS:
            self.rec_model_combo.setCurrentText(current_rec)
        models_layout.addRow("Recognition Model:", self.rec_model_combo)

        models_group.setLayout(models_layout)
        layout.addWidget(models_group)

        # Language Group
        language_group = QGroupBox("Language")
        language_layout = QFormLayout()

        # Language dropdown
        self.language_combo = QComboBox()
        for lang_name, lang_code in SUPPORTED_LANGUAGES:
            self.language_combo.addItem(lang_name, lang_code)

        # Set current language
        current_lang = self.current_settings.get('language', 'en')
        for i, (_, code) in enumerate(SUPPORTED_LANGUAGES):
            if code == current_lang:
                self.language_combo.setCurrentIndex(i)
                break

        language_layout.addRow("Language:", self.language_combo)
        language_group.setLayout(language_layout)
        layout.addWidget(language_group)

        # Theme Group
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout()

        # Theme dropdown
        self.theme_combo = QComboBox()
        for theme_name, theme_file in AVAILABLE_THEMES:
            self.theme_combo.addItem(theme_name, theme_file)

        # Set current theme
        current_theme = self.current_settings.get('theme', 'light_blue.xml')
        for i, (_, theme_file) in enumerate(AVAILABLE_THEMES):
            if theme_file == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break

        theme_layout.addRow("Application Theme:", self.theme_combo)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Info label
        info_label = QLabel("Note: Changes will take effect when you next process an image.")
        layout.addWidget(info_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_settings(self):
        """Return the selected settings as a dictionary"""
        return {
            'detection_model': self.det_model_combo.currentText(),
            'recognition_model': self.rec_model_combo.currentText(),
            'language': self.language_combo.currentData(),
            'theme': self.theme_combo.currentData(),
        }
