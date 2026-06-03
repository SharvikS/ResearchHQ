"""⌘K command palette.

A translucent modal overlay parented to the main window. The user types
to filter commands; Enter executes the highlighted entry; Esc dismisses.

Commands are registered through ``CommandPalette.register(...)`` from
``MainWindow.__init__`` so the palette has visibility of every nav
target, theme switch, and global action without holding a hard link
to each page.

Visual
------
- 560-px-wide rounded card centred ~25% from the top of the window
- Dark background with a soft accent halo (drop shadow)
- Search field on top, filter results list below, footer hint below
- Smooth fade-in (window opacity) on show, fade-out on dismiss
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QPainter,
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import theme


@dataclass(frozen=True)
class Command:
    """One row in the palette.

    Attributes
    ----------
    title:
        Short action label ("Open Dashboard", "Switch theme: Neon", …).
    section:
        Categorisation header — palette sorts + groups by this.
    keywords:
        Extra strings to match against the user's query. Useful for
        synonyms ("settings" should also match "preferences").
    shortcut:
        Display-only keyboard shortcut hint (e.g. ⌘+R). The actual
        binding lives elsewhere — this is just a visual cue.
    action:
        Zero-arg callable invoked when the user picks this command.
    """

    title: str
    section: str
    action: Callable[[], None]
    keywords: tuple[str, ...] = field(default_factory=tuple)
    shortcut: str = ""


class _OverlayBackdrop(QWidget):
    """Click-through-to-dismiss backdrop behind the palette card."""

    clicked = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        # Cover the whole parent window; semi-transparent dim layer.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 130))

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt method
        # Clicks outside the inner card dismiss the palette.
        self.clicked.emit()
        super().mousePressEvent(event)


class CommandPalette(QWidget):
    """Modal command palette overlay."""

    CARD_WIDTH = 560
    CARD_HEIGHT = 420

    executed = Signal(str)  # emits the command title that just ran

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._commands: list[Command] = []
        self._filtered: list[Command] = []

        # Cover the entire parent — the backdrop dims everything else.
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        # Backdrop fills the whole overlay.
        self._backdrop = _OverlayBackdrop(self)
        self._backdrop.setGeometry(0, 0, parent.width(), parent.height())
        self._backdrop.clicked.connect(self.dismiss)

        # Inner card — frameless rounded surface.
        self._card = QWidget(self)
        self._card.setObjectName("PaletteCard")
        self._card.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 200))
        self._card.setGraphicsEffect(shadow)
        self._center_card()

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(18, 18, 18, 16)
        card_layout.setSpacing(10)

        # Search field — autofocused on show.
        self._search = QLineEdit()
        self._search.setObjectName("PaletteSearch")
        self._search.setPlaceholderText("Type a command, or jump to a page…")
        self._search.textChanged.connect(self._on_filter)
        self._search.returnPressed.connect(self._on_enter)
        # We need to catch arrow-keys + Escape on the search field too,
        # so they navigate the list and dismiss respectively.
        self._search.installEventFilter(self)
        card_layout.addWidget(self._search)

        # Results list.
        self._list = QListWidget()
        self._list.setObjectName("PaletteList")
        self._list.itemActivated.connect(self._on_activate)
        card_layout.addWidget(self._list, 1)

        # Footer hint pill.
        footer = QLabel("↑↓  navigate    ↵  run    ⎋  dismiss")
        footer.setObjectName("PaletteFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(footer)

        # Style the card via inline QSS so it doesn't depend on the
        # global stylesheet picking up #PaletteCard.
        self._apply_card_qss()

        # Fade animation for show/hide via setWindowOpacity-style
        # property on the overlay. The overlay is a child widget, so we
        # use a QGraphicsOpacityEffect on the *card* only — the
        # backdrop has no other effects so it's safe.
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        self._fade_effect = QGraphicsOpacityEffect(self)
        self._fade_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._fade_effect)

    # ── public API ─────────────────────────────────────────────────────────

    def register(self, command: Command) -> None:
        """Add a command to the palette. Safe to call repeatedly with the
        same title — duplicates are skipped."""
        if any(c.title == command.title for c in self._commands):
            return
        self._commands.append(command)

    def show_palette(self) -> None:
        """Show the palette, focus the search field, fade in."""
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())
            self._backdrop.setGeometry(0, 0, parent.width(), parent.height())
            self._center_card()
        self._search.clear()
        self._populate_filtered("")
        self.show()
        self.raise_()
        self._search.setFocus()

        anim = QPropertyAnimation(self._fade_effect, b"opacity", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(scaled(180))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim_in = anim  # type: ignore[attr-defined]

    def dismiss(self) -> None:
        anim = QPropertyAnimation(self._fade_effect, b"opacity", self)
        anim.setStartValue(float(self._fade_effect.opacity()))
        anim.setEndValue(0.0)
        anim.setDuration(scaled(160))
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.finished.connect(self.hide)
        anim.start()
        self._anim_out = anim  # type: ignore[attr-defined]

    # ── filter / list ──────────────────────────────────────────────────────

    def _on_filter(self, text: str) -> None:
        self._populate_filtered(text.strip().lower())

    def _populate_filtered(self, needle: str) -> None:
        self._list.clear()
        if not needle:
            self._filtered = list(self._commands)
        else:
            self._filtered = [
                c
                for c in self._commands
                if needle in c.title.lower()
                or needle in c.section.lower()
                or any(needle in k.lower() for k in c.keywords)
            ]

        # Group by section, sorted by section then title.
        by_section: dict[str, list[Command]] = {}
        for c in self._filtered:
            by_section.setdefault(c.section, []).append(c)

        for section in sorted(by_section):
            section_item = QListWidgetItem(section.upper())
            section_item.setFlags(Qt.ItemFlag.NoItemFlags)
            font = section_item.font()
            font.setBold(True)
            font.setPointSize(font.pointSize() - 1)
            section_item.setFont(font)
            section_item.setForeground(QColor(theme().text_dim))
            self._list.addItem(section_item)
            for c in sorted(by_section[section], key=lambda c: c.title):
                row = QListWidgetItem(f"{c.title}" + (f"   {c.shortcut}" if c.shortcut else ""))
                row.setData(Qt.ItemDataRole.UserRole, c)
                self._list.addItem(row)

        # Pick the first runnable row by default.
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.flags() & Qt.ItemFlag.ItemIsSelectable:
                self._list.setCurrentRow(i)
                break

    def _on_enter(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        self._on_activate(item)

    def _on_activate(self, item: QListWidgetItem) -> None:
        cmd = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(cmd, Command):
            return
        self.dismiss()
        try:
            cmd.action()
        except Exception:  # noqa: BLE001 - command callbacks shouldn't crash the palette
            import logging

            logging.getLogger(__name__).exception("Command '%s' raised", cmd.title)
        self.executed.emit(cmd.title)

    # ── keyboard ───────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt method
        if (
            obj is self._search
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.dismiss()
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                # Advance the list selection, skipping section headers.
                cur = self._list.currentRow()
                direction = 1 if key == Qt.Key.Key_Down else -1
                next_row = cur + direction
                while 0 <= next_row < self._list.count():
                    it = self._list.item(next_row)
                    if it.flags() & Qt.ItemFlag.ItemIsSelectable:
                        self._list.setCurrentRow(next_row)
                        break
                    next_row += direction
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt method
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            return
        super().keyPressEvent(event)

    # ── layout helpers ─────────────────────────────────────────────────────

    def _center_card(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.CARD_WIDTH) // 2
        # 22% from the top — feels balanced and matches macOS Spotlight.
        y = int(parent.height() * 0.18)
        self._card.move(x, y)

    def _apply_card_qss(self) -> None:
        t = theme()
        self._card.setStyleSheet(f"""
            #PaletteCard {{
                background-color: {t.bg_raised};
                border: 1px solid {t.border_lt};
                border-radius: 16px;
            }}
            #PaletteSearch {{
                background-color: {t.bg_input};
                border: 1px solid {t.border_lt};
                border-radius: 10px;
                padding: 12px 14px;
                color: {t.text};
                font-size: 15px;
            }}
            #PaletteSearch:focus {{
                border: 1px solid {t.accent};
            }}
            #PaletteList {{
                background-color: transparent;
                border: none;
                outline: none;
                color: {t.text};
            }}
            #PaletteList::item {{
                padding: 9px 12px;
                border-radius: 6px;
            }}
            #PaletteList::item:selected {{
                background-color: {t.accent_bg};
                color: {t.accent};
            }}
            #PaletteFooter {{
                color: {t.text_dim};
                font-size: 11px;
                letter-spacing: 1px;
                padding: 4px 0 0 0;
                background: transparent;
            }}
        """)
