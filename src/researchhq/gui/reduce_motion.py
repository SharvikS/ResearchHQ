"""Global reduce-motion switch.

Users with vestibular sensitivities (or just personal preference) can
flatten animations to instant updates. Every motion helper consults
``is_reduced()`` and either uses zero duration or skips the animation
entirely. The toggle persists across runs via ``QSettings``.

Public surface
--------------
- ``is_reduced()``           current state
- ``set_reduced(value)``     update + persist + emit ``ReduceMotion.changed``
- ``ReduceMotion.changed``   Qt signal so widgets can re-render on change
- ``scaled(ms)``             returns 0 when reduce-motion is on, else ms
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QSettings, Signal


class _ReduceMotionManager(QObject):
    """Singleton manager."""

    changed = Signal(bool)

    _instance: Optional["_ReduceMotionManager"] = None

    @classmethod
    def instance(cls) -> "_ReduceMotionManager":
        if cls._instance is None:
            cls._instance = _ReduceMotionManager()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        qs = QSettings()
        self._reduced: bool = qs.value("a11y/reduce_motion", False, type=bool)

    def is_reduced(self) -> bool:
        return self._reduced

    def set_reduced(self, value: bool) -> None:
        value = bool(value)
        if value == self._reduced:
            return
        self._reduced = value
        QSettings().setValue("a11y/reduce_motion", value)
        self.changed.emit(value)


# ── module-level helpers ────────────────────────────────────────────────────


ReduceMotion = _ReduceMotionManager.instance


def is_reduced() -> bool:
    return _ReduceMotionManager.instance().is_reduced()


def set_reduced(value: bool) -> None:
    _ReduceMotionManager.instance().set_reduced(value)


def scaled(ms: int) -> int:
    """Return *ms* when full motion is on, 0 when reduced. Use this as
    the duration parameter to any ``QPropertyAnimation``."""
    return 0 if _ReduceMotionManager.instance().is_reduced() else int(ms)
