"""ResearchHQ TUI — premium interactive terminal workspace.

Phase 1: dashboard, research screen with live agent pipeline, sidebar
navigation, status header, theme switching, effort selector. Built on Textual.
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> None:
    from researchhq.tui.entry import main as _main

    _main()
