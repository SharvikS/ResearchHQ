"""Bundled-font loader.

Loads any ``.ttf`` / ``.otf`` files found under
``researchhq/gui/assets/fonts/`` into the application's font database
via :class:`QFontDatabase`. The QSS template references font families
by name (``Geist``, ``Inter``, ``JetBrains Mono``), so once registered
they take precedence over system fonts.

Falling back is automatic — if no font files are bundled the loader
returns the list of system families it would have preferred so callers
can log it.

Drop fonts at: ``src/researchhq/gui/assets/fonts/*.{ttf,otf}``
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)


# Family stacks we expect for each role — the loader can't enforce that
# a file with the right *name* contains glyphs we want, it just lists what
# we *intend* to bundle so the asset README + audit tooling stay in sync.
EXPECTED_FAMILIES = {
    "display": ["Geist", "Satoshi"],
    "body":    ["Inter"],
    "mono":    ["JetBrains Mono", "Geist Mono"],
}


def _font_dir() -> Path:
    """Resolve to ``researchhq/gui/assets/fonts/`` regardless of where
    the package was installed from (editable, wheel, frozen)."""
    return Path(__file__).resolve().parent / "assets" / "fonts"


def load_bundled_fonts() -> list[str]:
    """Register every ``.ttf`` / ``.otf`` under the asset dir.

    Returns the list of family names successfully registered. The list
    is empty when no fonts are bundled — the QSS family stack falls
    back to system fonts so the app still looks correct.
    """
    folder = _font_dir()
    if not folder.exists():
        logger.info("Font asset dir not found at %s — using system fallbacks", folder)
        return []

    registered: set[str] = set()
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".ttf", ".otf"):
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            logger.warning("QFontDatabase rejected %s", path)
            continue
        # One file can declare multiple families (rare); register all.
        for family in QFontDatabase.applicationFontFamilies(font_id):
            registered.add(family)

    if registered:
        logger.info("Loaded %d bundled font families: %s",
                    len(registered), sorted(registered))
    else:
        logger.info(
            "No bundled fonts found in %s — drop %s into that folder "
            "to upgrade the typography",
            folder,
            ", ".join(sum(EXPECTED_FAMILIES.values(), [])),
        )
    return sorted(registered)
