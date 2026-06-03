"""QApplication bootstrap with animated splash → main window handoff.

Boot sequence
-------------
1. Build the QApplication and apply the active theme stylesheet.
2. Install the global motion event filter so hover/focus/press effects
   are wired up for every widget the app spawns from here on.
3. Show the animated splash and start its reveal animation.
4. While the splash is on screen, build the MainWindow on the main thread
   and step the splash's progress bar to reflect the boot milestones.
5. When MainWindow is ready, fade the splash out, then show the window.

The splash is purely cosmetic — it does not gate any IO. Every boot
milestone is a synchronous step that happens on the main thread.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "PySide6 is not installed. Install the GUI extras with:\n"
            '    pip install -e ".[gui]"\n'
            "or:\n"
            "    pip install PySide6\n"
        )
        return 2

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ResearchHQ Studio")
    app.setOrganizationName("researchhq")

    # 0. Bundled fonts — register any TTF/OTF dropped into the assets
    # dir so the QSS family stack can resolve "Geist" / "Inter" /
    # "JetBrains Mono" before falling back to system fonts.
    from researchhq.gui.fonts import load_bundled_fonts

    load_bundled_fonts()

    # 1. Theme — render fresh QSS for the active palette and apply.
    from researchhq.gui.theme import render_qss

    app.setStyleSheet(render_qss())

    # Window / dock icon — rasterised from the brand mark so the splash,
    # main window and macOS dock all show the same identity.
    from researchhq.gui.widgets.logo import logo_icon

    app.setWindowIcon(logo_icon(size=128))

    # 2. Global motion — instruments existing + future buttons/inputs.
    from researchhq.gui.motion import install_global_motion

    install_global_motion(app)

    # 3. Splash — frameless, animated, on top.
    from researchhq.gui.widgets.splash import SplashScreen

    splash = SplashScreen()
    splash.show_animated()
    splash.set_progress(8, "loading theme")
    app.processEvents()

    # 4. Build the main window while the splash is animating. Progress
    # values are advisory — even if a step is fast, the splash never
    # disappears in under ~1.1s so the brand reveal animation gets a
    # chance to play out.
    splash.set_progress(22, "loading workspace")
    app.processEvents()

    from researchhq.gui.main_window import MainWindow

    splash.set_progress(48, "wiring agents")
    app.processEvents()

    window = MainWindow()
    splash.set_progress(78, "preparing pages")
    app.processEvents()

    # 5. Hand off — when the splash finishes its fade-out we show the
    # main window. This keeps the two from overlapping visually.
    def _hand_off() -> None:
        try:
            window.show()
        except RuntimeError:
            logger.exception("Failed to show main window after splash")

    splash.finished.connect(_hand_off)

    # Minimum dwell: ~1.1s so the wordmark reveal completes before the
    # fade-out begins.
    QTimer.singleShot(1100, lambda: splash.set_progress(100, "ready"))
    QTimer.singleShot(1350, splash.finish)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
