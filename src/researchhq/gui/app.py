"""QApplication bootstrap and the main entry point function."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "PySide6 is not installed. Install the GUI extras with:\n"
            "    pip install -e \".[gui]\"\n"
            "or:\n"
            "    pip install PySide6\n"
        )
        return 2

    from researchhq.gui.main_window import MainWindow
    from researchhq.gui.theme import DARK_QSS

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ResearchHQ Studio")
    app.setOrganizationName("researchhq")
    app.setStyleSheet(DARK_QSS)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
