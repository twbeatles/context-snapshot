from __future__ import annotations
from typing import List
from PySide6 import QtCore, QtWidgets
from ctxsnap.i18n import tr


class OnboardingDialog(QtWidgets.QDialog):
    """Friendly first-run onboarding.

    A lightweight, in-app guide so users can learn the core workflow
    without opening external docs.
    """

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setWindowTitle(tr("Welcome to CtxSnap"))
        self.setModal(True)
        self.setMinimumSize(760, 560)

        # Header section
        header = QtWidgets.QLabel("🚀 " + tr("Welcome to CtxSnap"))
        header.setObjectName("TitleLabel")
        header.setAlignment(QtCore.Qt.AlignCenter)
        
        sub = QtWidgets.QLabel(tr("Onboarding header"))
        sub.setObjectName("HintLabel")
        sub.setAlignment(QtCore.Qt.AlignCenter)

        # Progress indicator
        self.progress_label = QtWidgets.QLabel("")
        self.progress_label.setObjectName("SubtitleLabel")
        self.progress_label.setAlignment(QtCore.Qt.AlignCenter)

        self.stack = QtWidgets.QStackedWidget()
        self.pages: List[QtWidgets.QWidget] = []
        self._build_pages()

        # Navigation buttons with modern styling
        self.btn_back = QtWidgets.QPushButton("← " + tr("Back"))
        self.btn_next = QtWidgets.QPushButton(tr("Next") + " →")
        self.btn_next.setProperty("primary", True)
        self.btn_finish = QtWidgets.QPushButton("✓ " + tr("Finish"))
        self.btn_finish.setProperty("primary", True)
        
        self.btn_back.clicked.connect(self._back)
        self.btn_next.clicked.connect(self._next)
        self.btn_finish.clicked.connect(self.accept)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addWidget(self.btn_back)
        btn_row.addStretch(1)
        btn_row.addWidget(self.progress_label)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_next)
        btn_row.addWidget(self.btn_finish)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addSpacing(8)
        layout.addWidget(self.stack, 1)
        layout.addLayout(btn_row)

        self._sync_buttons()

    def _mk_page(self, title: str, body_html: str, icon: str = "") -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        
        # Title with optional icon
        title_text = f"{icon} {title}" if icon else title
        t = QtWidgets.QLabel(title_text)
        t.setObjectName("SubtitleLabel")
        t.setAlignment(QtCore.Qt.AlignCenter)
        
        b = QtWidgets.QTextBrowser()
        b.setOpenExternalLinks(False)
        b.setHtml(f"""
            <div style="padding: 16px; line-height: 1.6; font-size: 14px; color: #f0f0f5;">
                {body_html}
            </div>
        """)
        b.setStyleSheet("""
            QTextBrowser { 
                background: rgba(26, 26, 36, 0.6); 
                border: 1px solid rgba(42, 42, 64, 0.5); 
                border-radius: 12px; 
                padding: 12px;
            }
        """)
        
        lay = QtWidgets.QVBoxLayout(w)
        lay.setSpacing(12)
        lay.addWidget(t)
        lay.addWidget(b, 1)
        return w

    def _build_pages(self) -> None:
        p1 = self._mk_page(
            tr("Onboarding p1 title"),
            tr("Onboarding p1 body"),
            "📸",
        )
        p2 = self._mk_page(
            tr("Onboarding p2 title"),
            tr("Onboarding p2 body"),
            "⚡",
        )
        p3 = self._mk_page(
            tr("Onboarding p3 title"),
            tr("Onboarding p3 body"),
            "🔄",
        )
        p4 = self._mk_page(
            tr("Onboarding p4 title"), 
            tr("Onboarding p4 body"),
            "⚙️",
        )
        for p in [p1, p2, p3, p4]:
            self.pages.append(p)
            self.stack.addWidget(p)

    def _sync_buttons(self) -> None:
        i = self.stack.currentIndex()
        total = self.stack.count()
        
        self.btn_back.setEnabled(i > 0)
        last = (i == total - 1)
        self.btn_next.setVisible(not last)
        self.btn_finish.setVisible(last)
        
        # Update progress indicator
        self.progress_label.setText(f"{i + 1} / {total}")

    def _next(self) -> None:
        i = self.stack.currentIndex()
        if i < self.stack.count() - 1:
            self.stack.setCurrentIndex(i + 1)
        self._sync_buttons()

    def _back(self) -> None:
        i = self.stack.currentIndex()
        if i > 0:
            self.stack.setCurrentIndex(i - 1)
        self._sync_buttons()
