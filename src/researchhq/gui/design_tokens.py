"""Central design tokens for the ResearchHQ Studio GUI.

QSS can express most colour / padding / border decisions but it can't
express animation durations, easings, drop-shadow blur radii, or
spacing scales programmatically. This module holds those values in one
place so animation helpers, custom-painted widgets, and the QSS
template all reference a single source of truth.

Tokens are organised into nested classes so they can be imported by
domain (``RADIUS.CARD``, ``DURATION.HOVER_IN``, ``SHADOW.CARD_REST``).
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve


class RADIUS:
    """Corner radii in pixels. Stick to these — ad-hoc radii compound
    into a noisy UI."""

    INPUT  = 8
    BUTTON = 8
    CHIP   = 12
    CARD   = 16
    PILL   = 999   # use for fully-rounded pills


class SPACING:
    """8-pt scale. Pages, layouts, and component internals should pick
    from this scale only."""

    XS  = 4
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 24
    XXL = 32


class DURATION:
    """All animation durations, in milliseconds.

    ``HOVER_*`` and ``PRESS`` are tuned to feel snappy without being
    glitchy (>= 90 ms, <= 220 ms). Page-level transitions sit at 220 ms
    so a fast click-through still reads as a transition. ``INTRO`` /
    ``REVEAL`` / ``PULSE`` are deliberately longer so brand moments
    breathe.
    """

    HOVER_IN  = 140
    HOVER_OUT = 180
    PRESS     = 90
    RELEASE   = 160
    FOCUS_IN  = 160
    FOCUS_OUT = 200
    PAGE_FADE = 220
    RIPPLE    = 480
    INTRO     = 360
    REVEAL    = 700   # splash wordmark sweep
    PULSE     = 1800  # logo / brand breathing
    SHIMMER   = 1600  # primary-button gradient drift
    COUNT_UP  = 700
    TOAST_IN  = 240
    TOAST_OUT = 200
    PALETTE   = 200   # command palette open/close


class EASING:
    """Curves for each motion role. Sharp deceleration ``OUT_*`` for
    "things landing"; smoother ``IN_OUT_*`` for transitions; ``OUT_BACK``
    for the small overshoot that gives hover a "spring" feel."""

    OUT      = QEasingCurve.Type.OutCubic
    OUT_BACK = QEasingCurve.Type.OutBack
    IN_OUT   = QEasingCurve.Type.InOutCubic
    PRESS    = QEasingCurve.Type.OutQuad
    SINE     = QEasingCurve.Type.InOutSine


class SHADOW:
    """Drop-shadow tunings: (blur_radius, dx, dy, alpha)."""

    CARD_REST  = (14.0, 0,  4, 120)
    CARD_HOVER = (34.0, 0,  6, 150)
    BUTTON_REST = (0.0,  0,  0,   0)
    BUTTON_HOVER_BLUR     = 18.0
    BUTTON_HOVER_BLUR_PRI = 28.0
    BUTTON_HOVER_ALPHA     = 110
    BUTTON_HOVER_ALPHA_PRI = 165
    BUTTON_PRESS_ALPHA     = 220
    FOCUS_BLUR  = 22.0
    FOCUS_ALPHA = 160


class TYPO:
    """Font family stacks. Bundled fonts (``Geist``, ``Inter``,
    ``JetBrains Mono``) win when present; the rest of the stack covers
    machines without them.

    Note: Qt resolves the first family it finds in the order given.
    Always end with ``system-ui`` so we degrade gracefully."""

    DISPLAY = '"Geist", "Satoshi", "Inter", "SF Pro Display", "Segoe UI", system-ui, sans-serif'
    BODY    = '"Inter", "SF Pro Text", "Segoe UI", system-ui, sans-serif'
    MONO    = '"JetBrains Mono", "Geist Mono", "SF Mono", "Menlo", "Consolas", monospace'

    # Tightened tracking for headings — large display text benefits.
    DISPLAY_TRACKING = -0.5
