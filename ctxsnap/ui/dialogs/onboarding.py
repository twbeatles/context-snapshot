from __future__ import annotations
from PySide6 import QtCore, QtWidgets
from ctxsnap.i18n import tr


class OnboardingDialog(QtWidgets.QDialog):
    """First-run onboarding guide with 4-step walkthrough."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Welcome to CtxSnap"))
        self.setModal(True)
        self.setMinimumSize(620, 500)

        self.stack = QtWidgets.QStackedWidget()

        # ── Shared HTML wrapper ──
        def _page_html(title: str, body: str) -> str:
            return f"""
            <div style="font-family:'Segoe UI','Malgun Gothic',sans-serif; color:#e8e8f0;
                        padding:20px 24px; line-height:1.75;">
                <h2 style="color:#8178ff; margin:0 0 12px 0; font-size:18px; font-weight:700;">
                    {title}
                </h2>
                <div style="font-size:13px; color:#c0c0d0;">
                    {body}
                </div>
            </div>
            """

        # ── Page 0: Welcome ──
        welcome_body = f"""
        <p style="font-size:15px; color:#e8e8f0; margin-bottom:16px;">
            {tr('Onboarding header')}
        </p>
        <div style="background:#1a1a24; border:1px solid #2a2a3a; border-radius:10px;
                    padding:16px 18px; margin-bottom:14px;">
            <div style="font-size:12px; color:#8178ff; font-weight:600;
                        text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
                {tr('Onboarding p1 title')}
            </div>
            <div style="font-size:12px; color:#9090a8;">
                Save your current work state with a single click or hotkey.
            </div>
        </div>
        <div style="background:#1a1a24; border:1px solid #2a2a3a; border-radius:10px;
                    padding:16px 18px; margin-bottom:14px;">
            <div style="font-size:12px; color:#8178ff; font-weight:600;
                        text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
                {tr('Onboarding p2 title')}
            </div>
            <div style="font-size:12px; color:#9090a8;">
                Restore your saved context and pick up where you left off.
            </div>
        </div>
        <div style="background:#1a1a24; border:1px solid #2a2a3a; border-radius:10px;
                    padding:16px 18px; margin-bottom:14px;">
            <div style="font-size:12px; color:#8178ff; font-weight:600;
                        text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
                {tr('Onboarding p3 title')}
            </div>
            <div style="font-size:12px; color:#9090a8;">
                Filter and organize your snapshots with tags and pins.
            </div>
        </div>
        <div style="background:#1a1a24; border:1px solid #2a2a3a; border-radius:10px;
                    padding:16px 18px;">
            <div style="font-size:12px; color:#8178ff; font-weight:600;
                        text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
                {tr('Onboarding p4 title')}
            </div>
            <div style="font-size:12px; color:#9090a8;">
                Customize hotkeys, restore defaults, and manage backups.
            </div>
        </div>
        """
        p0 = QtWidgets.QTextBrowser()
        p0.setOpenExternalLinks(True)
        p0.setHtml(_page_html(tr("Welcome to CtxSnap"), welcome_body))
        self.stack.addWidget(p0)

        # ── Page 1: Snapshot ──
        p1 = QtWidgets.QTextBrowser()
        p1.setOpenExternalLinks(True)
        p1.setHtml(_page_html(tr("Onboarding p1 title"), tr("Onboarding p1 body")))
        self.stack.addWidget(p1)

        # ── Page 2: Restore ──
        p2 = QtWidgets.QTextBrowser()
        p2.setOpenExternalLinks(True)
        p2.setHtml(_page_html(tr("Onboarding p2 title"), tr("Onboarding p2 body")))
        self.stack.addWidget(p2)

        # ── Page 3: Tags & Pin ──
        p3 = QtWidgets.QTextBrowser()
        p3.setOpenExternalLinks(True)
        p3.setHtml(_page_html(tr("Onboarding p3 title"), tr("Onboarding p3 body")))
        self.stack.addWidget(p3)

        # ── Page 4: Settings & Backup ──
        p4 = QtWidgets.QTextBrowser()
        p4.setOpenExternalLinks(True)
        p4.setHtml(_page_html(tr("Onboarding p4 title"), tr("Onboarding p4 body")))
        self.stack.addWidget(p4)

        # ── Progress indicator (dots) ──
        self._dots = QtWidgets.QLabel()
        self._dots.setAlignment(QtCore.Qt.AlignCenter)
        self._dots.setStyleSheet("font-size: 16px; color: #8178ff; letter-spacing: 6px;")

        # ── Navigation buttons ──
        self.btn_prev = QtWidgets.QPushButton(tr("Back"))
        self.btn_next = QtWidgets.QPushButton(tr("Next"))
        self.btn_next.setProperty("primary", True)
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self.btn_prev)
        btn_row.addStretch(1)
        btn_row.addWidget(self._dots)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_next)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(self.stack, 1)
        layout.addLayout(btn_row)

        self._sync_buttons()

    def _update_dots(self) -> None:
        total = self.stack.count()
        current = self.stack.currentIndex()
        dots = "  ".join("●" if i == current else "○" for i in range(total))
        self._dots.setText(dots)

    def _sync_buttons(self) -> None:
        idx = self.stack.currentIndex()
        total = self.stack.count()
        self.btn_prev.setEnabled(idx > 0)
        if idx == total - 1:
            self.btn_next.setText(tr("Finish"))
        else:
            self.btn_next.setText(tr("Next"))
        self._update_dots()

    def _prev(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._sync_buttons()

    def _next(self) -> None:
        idx = self.stack.currentIndex()
        total = self.stack.count()
        if idx < total - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._sync_buttons()
        else:
            self.accept()
