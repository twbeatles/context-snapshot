"""
CtxSnap Modern Design System v2
Clean, minimal dark theme with refined spacing and typography.
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
    # Backgrounds — smooth gradient from deep to light
    "bg_primary": "#101016",
    "bg_secondary": "#18181f",
    "bg_tertiary": "#1e1e2a",
    "bg_card": "#1c1c28",
    "bg_input": "#141420",
    "bg_hover": "#22222e",

    # Accents
    "accent": "#6c63ff",
    "accent_hover": "#8178ff",
    "accent_muted": "rgba(108, 99, 255, 0.12)",
    "accent_border": "rgba(108, 99, 255, 0.35)",

    # Text — 4-level hierarchy
    "text_primary": "#e8e8f0",
    "text_secondary": "#8888a0",
    "text_muted": "#555568",
    "text_inverse": "#ffffff",

    # Borders
    "border": "#262636",
    "border_light": "#2e2e3e",
    "border_focus": "#6c63ff",

    # Status
    "success": "#34d399",
    "warning": "#fbbf24",
    "danger": "#f87171",

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
    background-color: #101016;
    color: #e8e8f0;
    font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
    font-size: 13px;
}

/* ============================================================
   Group Box — Subtle Card
   ============================================================ */
QGroupBox {
    background-color: #18181f;
    border: 1px solid #262636;
    border-radius: 10px;
    margin-top: 1.5em;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 3px 10px;
    background-color: transparent;
    border: none;
    color: #6c63ff;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ============================================================
   Input Fields
   ============================================================ */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #141420;
    border: 1px solid #262636;
    border-radius: 8px;
    padding: 9px 12px;
    color: #e8e8f0;
    selection-background-color: #6c63ff;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #6c63ff;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {
    border: 1px solid #2e2e3e;
}

QLineEdit::placeholder {
    color: #555568;
}

/* ============================================================
   ComboBox & SpinBox
   ============================================================ */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #18181f;
    border: 1px solid #262636;
    border-radius: 8px;
    padding: 7px 12px;
    color: #e8e8f0;
    min-height: 20px;
}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #2e2e3e;
}

QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #6c63ff;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8888a0;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #18181f;
    border: 1px solid #262636;
    border-radius: 8px;
    selection-background-color: rgba(108, 99, 255, 0.2);
    outline: none;
    padding: 4px;
}

/* ============================================================
   Buttons — 3-level hierarchy
   ============================================================ */

/* Default (tertiary / ghost) */
QPushButton {
    background-color: #1e1e2a;
    border: 1px solid #2e2e3e;
    border-radius: 8px;
    padding: 8px 16px;
    color: #e8e8f0;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #262636;
    border-color: #3a3a4e;
}

QPushButton:pressed {
    background-color: #18181f;
}

QPushButton:disabled {
    background-color: #141420;
    color: #555568;
    border-color: #1e1e2a;
}

/* Primary Button — Solid accent */
QPushButton#PrimaryButton, QPushButton[primary="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6c63ff, stop:1 #8b5cf6);
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 9px 20px;
}

QPushButton#PrimaryButton:hover, QPushButton[primary="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #8178ff, stop:1 #a78bfa);
}

QPushButton#PrimaryButton:pressed, QPushButton[primary="true"]:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #5b52e0, stop:1 #7c3aed);
}

/* Secondary Button — Ghost with accent border */
QPushButton[secondary="true"] {
    background-color: transparent;
    border: 1px solid rgba(108, 99, 255, 0.4);
    color: #8178ff;
    font-weight: 500;
}

QPushButton[secondary="true"]:hover {
    background-color: rgba(108, 99, 255, 0.08);
    border-color: #6c63ff;
}

/* Danger Button */
QPushButton#DangerButton, QPushButton[danger="true"] {
    background-color: rgba(248, 113, 113, 0.1);
    border: 1px solid rgba(248, 113, 113, 0.4);
    color: #f87171;
}

QPushButton#DangerButton:hover, QPushButton[danger="true"]:hover {
    background-color: rgba(248, 113, 113, 0.18);
}

/* ============================================================
   Tool Buttons
   ============================================================ */
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 7px 12px;
    color: #8888a0;
    font-size: 13px;
}

QToolButton:hover {
    background-color: rgba(108, 99, 255, 0.08);
    border-color: rgba(108, 99, 255, 0.3);
    color: #e8e8f0;
}

QToolButton:pressed {
    background-color: rgba(108, 99, 255, 0.15);
}

QToolButton::menu-indicator {
    image: none;
}

/* ============================================================
   List Views — Clean card items
   ============================================================ */
QListWidget, QListView {
    background-color: #101016;
    border: 1px solid #262636;
    border-radius: 10px;
    outline: none;
    padding: 6px;
}

QListWidget::item, QListView::item {
    background-color: #18181f;
    border: 1px solid #1e1e2a;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 3px 2px;
    color: #e8e8f0;
}

QListWidget::item:hover, QListView::item:hover {
    background-color: #1e1e2a;
    border-color: rgba(108, 99, 255, 0.2);
}

QListWidget::item:selected, QListView::item:selected {
    background-color: rgba(108, 99, 255, 0.12);
    border: 1px solid rgba(108, 99, 255, 0.4);
    border-left: 3px solid #6c63ff;
}

/* ============================================================
   Table Widget
   ============================================================ */
QTableWidget {
    background-color: #101016;
    border: 1px solid #262636;
    border-radius: 10px;
    gridline-color: #1e1e2a;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #18181f;
}

QTableWidget::item:selected {
    background-color: rgba(108, 99, 255, 0.15);
}

QHeaderView::section {
    background-color: #18181f;
    color: #8888a0;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #262636;
    font-weight: 600;
    font-size: 12px;
}

/* ============================================================
   Scrollbars — Minimal
   ============================================================ */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: #2e2e3e;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #3a3a4e;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px 4px;
}

QScrollBar::handle:horizontal {
    background: #2e2e3e;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #3a3a4e;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ============================================================
   Splitter
   ============================================================ */
QSplitter::handle {
    background-color: #262636;
    width: 1px;
    margin: 0 6px;
}

QSplitter::handle:hover {
    background-color: #6c63ff;
}

/* ============================================================
   Tab Widget
   ============================================================ */
QTabWidget::pane {
    background-color: #18181f;
    border: 1px solid #262636;
    border-radius: 10px;
    top: -1px;
}

QTabBar::tab {
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 18px;
    margin-right: 2px;
    color: #8888a0;
    font-weight: 500;
    font-size: 13px;
}

QTabBar::tab:selected {
    color: #e8e8f0;
    border-bottom: 2px solid #6c63ff;
}

QTabBar::tab:hover:!selected {
    color: #c0c0d0;
    border-bottom: 2px solid #2e2e3e;
}

/* ============================================================
   Check Box & Radio Button
   ============================================================ */
QCheckBox, QRadioButton {
    color: #e8e8f0;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #3a3a4e;
    border-radius: 4px;
    background-color: #141420;
}

QRadioButton::indicator {
    border-radius: 9px;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #6c63ff;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #6c63ff;
    border-color: #6c63ff;
}

/* ============================================================
   Labels — Typography Hierarchy
   ============================================================ */
QLabel {
    color: #e8e8f0;
}

QLabel#TitleLabel {
    font-size: 18px;
    font-weight: 700;
    color: #f0f0f8;
    margin-bottom: 2px;
}

QLabel#SubtitleLabel {
    font-size: 14px;
    font-weight: 600;
    color: #8178ff;
}

QLabel#SectionTitle {
    font-size: 12px;
    font-weight: 600;
    color: #8888a0;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

QLabel#HintLabel {
    font-size: 12px;
    color: #555568;
}

QLabel#SuccessLabel {
    color: #34d399;
}

QLabel#WarningLabel {
    color: #fbbf24;
}

QLabel#DangerLabel, QLabel#ErrorLabel {
    color: #f87171;
}

/* ============================================================
   Status Bar
   ============================================================ */
QStatusBar {
    background-color: #0c0c12;
    color: #555568;
    border-top: 1px solid #18181f;
    padding: 4px 12px;
    font-size: 12px;
}

/* ============================================================
   Menu Bar & Menus
   ============================================================ */
QMenuBar {
    background-color: #101016;
    color: #e8e8f0;
    border-bottom: 1px solid #18181f;
    padding: 4px;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: rgba(108, 99, 255, 0.08);
}

QMenu {
    background-color: #18181f;
    border: 1px solid #262636;
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 6px;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: rgba(108, 99, 255, 0.15);
}

QMenu::separator {
    height: 1px;
    background-color: #262636;
    margin: 6px 12px;
}

/* ============================================================
   Message Box
   ============================================================ */
QMessageBox {
    background-color: #18181f;
}

QMessageBox QLabel {
    color: #e8e8f0;
}

/* ============================================================
   Tooltips
   ============================================================ */
QToolTip {
    background-color: #1e1e2a;
    color: #e8e8f0;
    border: 1px solid #2e2e3e;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ============================================================
   Progress Bar
   ============================================================ */
QProgressBar {
    background-color: #18181f;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6c63ff, stop:1 #8b5cf6);
    border-radius: 4px;
}

/* ============================================================
   Text Browser (for Onboarding, etc.)
   ============================================================ */
QTextBrowser {
    background-color: #18181f;
    border: 1px solid #262636;
    border-radius: 10px;
    padding: 14px;
    color: #e8e8f0;
}

/* ============================================================
   Frame Separator
   ============================================================ */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #262636;
    max-height: 1px;
}
"""


def set_pretty_style(app: QtWidgets.QApplication) -> None:
    """Apply the modern design system to the application."""
    app.setStyle("Fusion")

    # Create a dark, modern palette
    palette = QtGui.QPalette()

    # Window colors
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(16, 16, 22))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(232, 232, 240))

    # Base colors (for input fields, lists)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(24, 24, 31))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(30, 30, 42))

    # Text colors
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(232, 232, 240))
    palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(85, 85, 104))

    # Button colors
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(30, 30, 42))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(232, 232, 240))

    # Highlight colors (selection)
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(108, 99, 255))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))

    # Tooltip colors
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(30, 30, 42))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(232, 232, 240))

    # Link color
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(108, 99, 255))
    palette.setColor(QtGui.QPalette.LinkVisited, QtGui.QColor(129, 120, 255))

    # Disabled colors
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor(85, 85, 104))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtGui.QColor(85, 85, 104))

    app.setPalette(palette)
