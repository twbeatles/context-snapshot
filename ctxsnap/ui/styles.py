"""
CtxSnap Modern Design System
A comprehensive styling module with modern aesthetics, glassmorphism effects,
and smooth micro-animations.
"""
from PySide6 import QtCore, QtGui, QtWidgets


# ============================================================
# Scroll-Safe Widgets (prevent accidental value changes on scroll)
# ============================================================
class NoScrollMixin:
    """Mixin to prevent wheel events from changing values unless focused."""
    
    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoScrollComboBox(NoScrollMixin, QtWidgets.QComboBox):
    """ComboBox that ignores wheel events unless focused."""
    pass


class NoScrollSpinBox(NoScrollMixin, QtWidgets.QSpinBox):
    """SpinBox that ignores wheel events unless focused."""
    pass


class NoScrollDoubleSpinBox(NoScrollMixin, QtWidgets.QDoubleSpinBox):
    """DoubleSpinBox that ignores wheel events unless focused."""
    pass


def disable_wheel_scroll(widget: QtWidgets.QWidget) -> None:
    """
    Install an event filter on a widget to prevent wheel events 
    from changing its value unless it has focus.
    """
    class WheelFilter(QtCore.QObject):
        def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
            if event.type() == QtCore.QEvent.Wheel:
                if not obj.hasFocus():
                    event.ignore()
                    return True
            return False
    
    # Store the filter on the widget to prevent garbage collection
    widget._wheel_filter = WheelFilter(widget)
    widget.installEventFilter(widget._wheel_filter)
    widget.setFocusPolicy(QtCore.Qt.StrongFocus)

# ============================================================
# Design Tokens
# ============================================================
COLORS = {
    # Backgrounds
    "bg_primary": "#0f0f14",
    "bg_secondary": "#1a1a24",
    "bg_tertiary": "#24243a",
    "bg_card": "rgba(26, 26, 36, 0.85)",
    "bg_input": "rgba(15, 15, 20, 0.7)",
    
    # Accents
    "accent": "#7c5cff",
    "accent_hover": "#9175ff",
    "accent_light": "rgba(124, 92, 255, 0.15)",
    
    # Text
    "text_primary": "#f0f0f5",
    "text_secondary": "#9090a8",
    "text_muted": "#606078",
    
    # Borders
    "border": "#2a2a40",
    "border_light": "rgba(42, 42, 64, 0.5)",
    
    # Status
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    
    # Special
    "pinned": "#fbbf24",
    "archived": "#6b7280",
}

# ============================================================
# Main Application Stylesheet
# ============================================================
APP_QSS = """
/* ============================================================
   Global Styles
   ============================================================ */
QMainWindow, QDialog, QWidget {
    background-color: #0f0f14;
    color: #f0f0f5;
    font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
    font-size: 13px;
}

/* ============================================================
   Group Box - Card Style
   ============================================================ */
QGroupBox {
    background-color: rgba(26, 26, 36, 0.6);
    border: 1px solid rgba(42, 42, 64, 0.5);
    border-radius: 12px;
    margin-top: 1.5em;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    background-color: #1a1a24;
    border-radius: 6px;
    color: #a78bfa;
    font-weight: 600;
}

/* ============================================================
   Input Fields - Modern Style
   ============================================================ */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: rgba(15, 15, 20, 0.7);
    border: 1px solid #2a2a40;
    border-radius: 8px;
    padding: 10px 12px;
    color: #f0f0f5;
    selection-background-color: #7c5cff;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #7c5cff;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {
    border: 1px solid #3a3a50;
}

QLineEdit::placeholder {
    color: #606078;
}

/* ============================================================
   ComboBox & SpinBox
   ============================================================ */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: rgba(26, 26, 36, 0.8);
    border: 1px solid #2a2a40;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f0f0f5;
    min-height: 20px;
}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #3a3a50;
}

QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #7c5cff;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #9090a8;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a24;
    border: 1px solid #2a2a40;
    border-radius: 8px;
    selection-background-color: #7c5cff;
    outline: none;
    padding: 4px;
}

/* ============================================================
   Buttons - Hierarchy System
   ============================================================ */
QPushButton {
    background-color: #24243a;
    border: 1px solid #3a3a50;
    border-radius: 8px;
    padding: 10px 18px;
    color: #f0f0f5;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2e2e48;
    border-color: #4a4a60;
}

QPushButton:pressed {
    background-color: #1a1a2a;
}

QPushButton:disabled {
    background-color: #1a1a24;
    color: #606078;
    border-color: #2a2a40;
}

/* Primary Button - Accent Gradient */
QPushButton#PrimaryButton, QPushButton[primary="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7c5cff, stop:1 #a855f7);
    border: none;
    color: white;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover, QPushButton[primary="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #9175ff, stop:1 #c084fc);
}

QPushButton#PrimaryButton:pressed, QPushButton[primary="true"]:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6b4ce0, stop:1 #9333ea);
}

/* Danger Button */
QPushButton#DangerButton, QPushButton[danger="true"] {
    background-color: rgba(239, 68, 68, 0.15);
    border: 1px solid #ef4444;
    color: #ef4444;
}

QPushButton#DangerButton:hover, QPushButton[danger="true"]:hover {
    background-color: rgba(239, 68, 68, 0.25);
}

/* ============================================================
   Tool Buttons
   ============================================================ */
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 12px;
    color: #9090a8;
}

QToolButton:hover {
    background-color: rgba(124, 92, 255, 0.1);
    border-color: #7c5cff;
    color: #f0f0f5;
}

QToolButton:pressed {
    background-color: rgba(124, 92, 255, 0.2);
}

QToolButton::menu-indicator {
    image: none;
}

/* ============================================================
   List Views - Card Style Items
   ============================================================ */
QListWidget, QListView {
    background-color: #0f0f14;
    border: 1px solid #2a2a40;
    border-radius: 12px;
    outline: none;
    padding: 8px;
}

QListWidget::item, QListView::item {
    background-color: rgba(26, 26, 36, 0.6);
    border: 1px solid rgba(42, 42, 64, 0.3);
    border-radius: 10px;
    padding: 12px 14px;
    margin: 4px 2px;
    color: #f0f0f5;
}

QListWidget::item:hover, QListView::item:hover {
    background-color: rgba(36, 36, 58, 0.8);
    border-color: rgba(124, 92, 255, 0.3);
}

QListWidget::item:selected, QListView::item:selected {
    background-color: rgba(124, 92, 255, 0.2);
    border: 1px solid #7c5cff;
}

/* ============================================================
   Table Widget
   ============================================================ */
QTableWidget {
    background-color: #0f0f14;
    border: 1px solid #2a2a40;
    border-radius: 12px;
    gridline-color: #2a2a40;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #1a1a24;
}

QTableWidget::item:selected {
    background-color: rgba(124, 92, 255, 0.2);
}

QHeaderView::section {
    background-color: #1a1a24;
    color: #9090a8;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #2a2a40;
    font-weight: 600;
}

/* ============================================================
   Scrollbars - Minimal Style
   ============================================================ */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: #3a3a50;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #4a4a60;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px 4px;
}

QScrollBar::handle:horizontal {
    background: #3a3a50;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #4a4a60;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ============================================================
   Splitter
   ============================================================ */
QSplitter::handle {
    background-color: #2a2a40;
    width: 2px;
    margin: 0 4px;
}

QSplitter::handle:hover {
    background-color: #7c5cff;
}

/* ============================================================
   Tab Widget
   ============================================================ */
QTabWidget::pane {
    background-color: #1a1a24;
    border: 1px solid #2a2a40;
    border-radius: 12px;
    top: -1px;
}

QTabBar::tab {
    background-color: #0f0f14;
    border: 1px solid #2a2a40;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 10px 20px;
    margin-right: 2px;
    color: #9090a8;
}

QTabBar::tab:selected {
    background-color: #1a1a24;
    color: #f0f0f5;
    border-color: #7c5cff;
    border-bottom: 2px solid #1a1a24;
}

QTabBar::tab:hover:!selected {
    background-color: #1a1a24;
    color: #f0f0f5;
}

/* ============================================================
   Check Box & Radio Button
   ============================================================ */
QCheckBox, QRadioButton {
    color: #f0f0f5;
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #3a3a50;
    border-radius: 4px;
    background-color: #0f0f14;
}

QRadioButton::indicator {
    border-radius: 10px;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #7c5cff;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #7c5cff;
    border-color: #7c5cff;
}

/* ============================================================
   Labels - Typography Hierarchy
   ============================================================ */
QLabel {
    color: #f0f0f5;
}

QLabel#TitleLabel {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 4px;
}

QLabel#SubtitleLabel {
    font-size: 16px;
    font-weight: 600;
    color: #a78bfa;
}

QLabel#HintLabel {
    font-size: 12px;
    color: #606078;
}

QLabel#SuccessLabel {
    color: #22c55e;
}

QLabel#WarningLabel {
    color: #f59e0b;
}

QLabel#DangerLabel, QLabel#ErrorLabel {
    color: #ef4444;
}

/* ============================================================
   Status Bar
   ============================================================ */
QStatusBar {
    background-color: #0a0a0f;
    color: #606078;
    border-top: 1px solid #1a1a24;
    padding: 4px 8px;
}

/* ============================================================
   Menu Bar & Menus
   ============================================================ */
QMenuBar {
    background-color: #0f0f14;
    color: #f0f0f5;
    border-bottom: 1px solid #1a1a24;
    padding: 4px;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: rgba(124, 92, 255, 0.1);
}

QMenu {
    background-color: #1a1a24;
    border: 1px solid #2a2a40;
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: rgba(124, 92, 255, 0.2);
}

QMenu::separator {
    height: 1px;
    background-color: #2a2a40;
    margin: 6px 12px;
}

/* ============================================================
   Message Box
   ============================================================ */
QMessageBox {
    background-color: #1a1a24;
}

QMessageBox QLabel {
    color: #f0f0f5;
}

/* ============================================================
   Tooltips
   ============================================================ */
QToolTip {
    background-color: #24243a;
    color: #f0f0f5;
    border: 1px solid #3a3a50;
    border-radius: 6px;
    padding: 8px 12px;
}

/* ============================================================
   Progress Bar
   ============================================================ */
QProgressBar {
    background-color: #1a1a24;
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7c5cff, stop:1 #a855f7);
    border-radius: 6px;
}

/* ============================================================
   Text Browser (for Onboarding, etc.)
   ============================================================ */
QTextBrowser {
    background-color: rgba(26, 26, 36, 0.6);
    border: 1px solid rgba(42, 42, 64, 0.5);
    border-radius: 12px;
    padding: 16px;
    color: #f0f0f5;
}
"""


def set_pretty_style(app: QtWidgets.QApplication) -> None:
    """Apply the modern design system to the application."""
    app.setStyle("Fusion")
    
    # Create a dark, modern palette
    palette = QtGui.QPalette()
    
    # Window colors
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(15, 15, 20))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(240, 240, 245))
    
    # Base colors (for input fields, lists)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(26, 26, 36))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(36, 36, 58))
    
    # Text colors
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(240, 240, 245))
    palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(96, 96, 120))
    
    # Button colors
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(36, 36, 58))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(240, 240, 245))
    
    # Highlight colors (selection)
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(124, 92, 255))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    
    # Tooltip colors
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(36, 36, 58))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(240, 240, 245))
    
    # Link color
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(124, 92, 255))
    palette.setColor(QtGui.QPalette.LinkVisited, QtGui.QColor(167, 139, 250))
    
    # Disabled colors
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor(96, 96, 120))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtGui.QColor(96, 96, 120))
    
    app.setPalette(palette)
