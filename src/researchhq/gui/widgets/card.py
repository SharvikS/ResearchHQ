"""Card primitives: rounded, bordered panels with title + optional subtitle and body.

Cards auto-instrument with a hover-lift drop-shadow (see
``motion.attach_card_hover``) so they feel tactile across the app
without each call site needing to wire it up. They also fire a soft
ripple from the click point on mousePressEvent so the whole card
reads as a tactile surface — useful even for cards that don't have a
dedicated click handler (the ripple is harmless visual feedback).

The card title is rendered through ``SectionTitle`` so each card has a
slow accent gradient sweep painted under its heading — a quiet
ambient touch that ties the cards into the rest of the animated UI.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)


class Card(QFrame):
    """Generic content card with an optional title + subtitle header."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(18, 16, 18, 16)
        self._outer.setSpacing(8)

        if title:
            # SectionTitle is a QLabel subclass that paints a slow
            # accent gradient underline. Same QSS hooks (objectName)
            # as before so existing theme rules still apply.
            from researchhq.gui.widgets.section_title import SectionTitle
            t = SectionTitle(title)
            t.setObjectName("CardTitle")
            self._outer.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("CardSubtitle")
            self._outer.addWidget(s)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 6, 0, 0)
        self._body.setSpacing(8)
        self._outer.addLayout(self._body)

        # Hover-lift drop shadow. Lazy-imported so card.py stays usable
        # in environments that haven't installed the GUI extras yet.
        self._attach_hover()

    def _attach_hover(self) -> None:
        try:
            from researchhq.gui.motion import attach_card_hover
            attach_card_hover(self)
        except ImportError:
            # Motion module not available — card still renders, just no glow.
            pass

    def add(self, w: QWidget) -> None:
        self._body.addWidget(w)

    def add_layout(self, layout) -> None:
        self._body.addLayout(layout)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt method
        # Spawn a soft ripple at the click point. The ripple is purely
        # cosmetic — we don't consume the event, so any layout-level
        # click handlers still see it.
        try:
            from researchhq.gui.motion import Ripple
            try:
                pt = event.position().toPoint()
            except (AttributeError, TypeError):
                pt = event.pos()
            Ripple.spawn(self, pt)
        except (ImportError, RuntimeError):
            pass
        super().mousePressEvent(event)


class StatCard(QFrame):
    """Compact dashboard stat: a small label kicker over a big value.

    The label uses the theme's `StatLabel` style (muted, uppercase, tight
    tracking), the value uses `StatValue` (large, accent-coloured). The
    `value_label` attribute is exposed so callers can drive ``count_up``
    or ``count_up_float`` animations against it.
    """

    def __init__(
        self,
        label: str,
        value: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        self._value = QLabel(value)
        self._value.setObjectName("StatValue")

        layout.addWidget(self._label)
        layout.addWidget(self._value)

        # Hover-lift parity with Card.
        try:
            from researchhq.gui.motion import attach_card_hover
            attach_card_hover(self)
        except ImportError:
            pass

    @property
    def value_label(self) -> QLabel:
        """Public reference to the big-value label so callers can run
        count-up animations against it."""
        return self._value

    def set_value(self, value: str) -> None:
        # Flash the value to accent2 before easing back to the theme
        # text colour — gives an obvious "this number just changed"
        # affordance. Skip the first set so the dashboard's count_up
        # animation isn't fighting the flash.
        previous = self._value.text()
        self._value.setText(value)
        if previous and previous != value:
            try:
                from researchhq.gui.motion import flash_value_change
                flash_value_change(self._value)
            except ImportError:
                pass
