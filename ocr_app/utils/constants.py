"""Application constants and configuration"""

# OCR Model Options
DETECTION_MODELS = [
    'PP-OCRv4_mobile_det',
    'PP-OCRv4_server_det',
    'PP-OCRv5_mobile_det',
    'PP-OCRv5_server_det',
]

RECOGNITION_MODELS = [
    'en_PP-OCRv4_mobile_rec',      # English (fast)
    'en_PP-OCRv5_mobile_rec',      # English (latest)
    'PP-OCRv4_mobile_rec',         # Chinese (fast)
    'PP-OCRv4_server_rec',         # Chinese (high accuracy)
    'PP-OCRv5_mobile_rec',         # Multi-language (latest, supports CN/EN/JP)
    'PP-OCRv5_server_rec',         # Multi-language (best accuracy)
]

# Supported Languages (display_name, code)
SUPPORTED_LANGUAGES = [
    ('Chinese & English', 'ch'),
    ('English', 'en'),
    ('Chinese Traditional', 'ch_tra'),
    ('Japanese', 'japan'),
    ('Korean', 'korean'),
    ('French', 'fr'),
    ('German', 'german'),
    ('Spanish', 'es'),
    ('Portuguese', 'pt'),
    ('Russian', 'ru'),
    ('Italian', 'it'),
    ('Arabic', 'ar'),
    ('Hindi', 'hi'),
    ('Vietnamese', 'vi'),
    ('Thai', 'th'),
    ('Indonesian', 'id'),
    ('Turkish', 'tr'),
    ('Polish', 'pl'),
    ('Dutch', 'nl'),
    ('Swedish', 'sv'),
]

# Available UI Themes (display_name, filename)
AVAILABLE_THEMES = [
    # Light themes
    ('Light Blue', 'light_blue.xml'),
    ('Light Cyan', 'light_cyan.xml'),
    ('Light Green', 'light_lightgreen.xml'),
    ('Light Pink', 'light_pink.xml'),
    ('Light Purple', 'light_purple.xml'),
    ('Light Red', 'light_red.xml'),
    ('Light Teal', 'light_teal.xml'),
    ('Light Yellow', 'light_yellow.xml'),
    ('Light Amber', 'light_amber.xml'),

    # Dark themes
    ('Dark Blue', 'dark_blue.xml'),
    ('Dark Cyan', 'dark_cyan.xml'),
    ('Dark Green', 'dark_lightgreen.xml'),
    ('Dark Pink', 'dark_pink.xml'),
    ('Dark Purple', 'dark_purple.xml'),
    ('Dark Red', 'dark_red.xml'),
    ('Dark Teal', 'dark_teal.xml'),
    ('Dark Yellow', 'dark_yellow.xml'),
]

# QSettings Keys
SETTINGS_DET_MODEL = 'ocr/detection_model'
SETTINGS_REC_MODEL = 'ocr/recognition_model'
SETTINGS_LANGUAGE = 'ocr/language'
SETTINGS_THEME = 'ui/theme'
SETTINGS_EXPLORER_DIR = 'ui/explorer_last_directory'
SETTINGS_SPLITTER_SIZES = 'ui/splitter_sizes'

# Default Values
DEFAULT_DET_MODEL = 'PP-OCRv4_mobile_det'
DEFAULT_REC_MODEL = 'en_PP-OCRv4_mobile_rec'
DEFAULT_LANGUAGE = 'en'
DEFAULT_THEME = 'light_blue.xml'
DEFAULT_SPLITTER_SIZES = [200, 450, 350]
