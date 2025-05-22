"""
Configuration and constants for the Redshift GUI application.
"""

# Redshift fitting constants
REDSHIFT_GUESS_LOWER_FACTOR = 0.95
REDSHIFT_GUESS_UPPER_FACTOR = 1.05
DEFAULT_Z_MIN = 0.0
DEFAULT_Z_MAX = 10.0

# UI theme
DARK_THEME_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #292E3C;
    color: #E0E0E0;
}
QLabel {
    color: #E0E0E0;
    font-weight: bold;
    padding: 2px;
    border-radius: 3px;
}
QLabel#header {
    font-size: 14px;
    color: #62AAFF;
}
QPushButton {
    background-color: #4A6DB5;
    color: white;
    border-radius: 4px;
    padding: 5px 10px;
    font-weight: bold;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #5A7DC5;
}
QPushButton:pressed {
    background-color: #3A5DA5;
}
QPushButton:disabled {
    background-color: #3A4055;
    color: #808080;
}
QDoubleSpinBox, QComboBox, QTextEdit {
    background-color: #383E50;
    color: #E0E0E0;
    border: 1px solid #5A6374;
    border-radius: 3px;
    padding: 2px;
    min-height: 20px;
}
QComboBox {
    min-width: 80px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-left: 1px solid #5A6374;
}
QComboBox::down-arrow {
    image: none;
    width: 10px;
    height: 10px;
    background-color: #E0E0E0;
}
QComboBox QAbstractItemView {
    background-color: #383E50;
    color: #E0E0E0;
    selection-background-color: #4A6DB5;
    selection-color: #FFFFFF;
    border: 2px solid #5A6374;
    font-weight: bold;
    padding: 5px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 20px;
    padding: 5px;
}
QScrollArea {
    background-color: #292E3C;
    border: 1px solid #383E50;
    border-radius: 3px;
}
QWidget#scrollWidget {
    background-color: #292E3C;
}
"""
