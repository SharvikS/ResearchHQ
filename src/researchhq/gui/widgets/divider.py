"""Theme-aware vertical hairline divider painted with a soft alpha gradient.

Sits between the sidebar and the main content area to give the workspace
a subtle premium edge that isn't a hard line. Repaints on theme change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from researchhq.gui.theme import ThemeManager, theme


class WorkspaceDivider(QWidget):
    """3-px vertical band with a top→middle→bottom alpha fade so it reads
    as a deliberate hairline rather than a hard wall."""

    WIDTH = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkspaceDivider")
        self.setFixedWidth(self.WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._color = QColor(theme().accent)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _t) -> None:
        try:
            self._color = QColor(theme().accent)
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        grad = QLinearGradient(0, 0, 0, h)
        base = self._color
        c_clear = QColor(base); c_clear.setAlpha(0)
        c_soft = QColor(base); c_soft.setAlpha(36)
        c_peak = QColor(base); c_peak.setAlpha(110)
        grad.setColorAt(0.0, c_clear)
        grad.setColorAt(0.15, c_soft)
        grad.setColorAt(0.5, c_peak)
        grad.setColorAt(0.85, c_soft)
        grad.setColorAt(1.0, c_clear)
        p.fillRect(self.rect(), grad)
