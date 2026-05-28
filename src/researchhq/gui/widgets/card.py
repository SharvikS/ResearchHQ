"""Card primitives: rounded, bordered panels with title + optional subtitle and body.

Cards auto-instrument with a hover-lift drop-shadow (see
``motion.attach_card_hover``) so they feel tactile across the app
without each call site needing to wire it up.
"""

from __future__ import annotations

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
            t = QLabel(title)
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
