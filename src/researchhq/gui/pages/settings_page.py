"""Settings page: provider/model defaults, output folder, theme, search engines.

Settings here are session-level overrides. They modify `researchhq.config.settings` in-process
so the running pipeline picks them up immediately. We never display API keys; only their
configured/missing status.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QSettings
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

from researchhq.config import settings
from researchhq.gui.widgets.card import Card

PROVIDERS = ["groq", "gemini", "ollama", "openai", "anthropic"]
SEARCH_ENGINES = ["duckduckgo"]


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._qs = QSettings()  # uses org/app set in app.py

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: 700; background: transparent;")
        outer.addWidget(title)

        # --- LLM provider card ---
        prov = Card("LLM provider", "Default provider, model, and API key status")
        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("Default provider"), 0, 0)
        self._provider = QComboBox()
        self._provider.addItems(PROVIDERS)
        self._provider.setCurrentText(settings.default_provider)
        grid.addWidget(self._provider, 0, 1)

        grid.addWidget(QLabel("Model name"), 1, 0)
        self._model = QLineEdit(settings.models.get(settings.default_provider, ""))
        grid.addWidget(self._model, 1, 1)
        self._provider.currentTextChanged.connect(
            lambda p: self._model.setText(settings.models.get(p, ""))
        )

        # API key status (read-only). Never shows the actual key.
        grid.addWidget(QLabel("API key status"), 2, 0)
        self._key_status = QLabel(self._key_status_text())
        self._key_status.setStyleSheet("background: transparent;")
        grid.addWidget(self._key_status, 2, 1)

        prov.add_layout(grid)
        outer.addWidget(prov)

        # --- Search & sources card ---
        src = Card("Search & sources", "Engines and source caps")
        grid2 = QGridLayout(); grid2.setHorizontalSpacing(10); grid2.setVerticalSpacing(6)

        grid2.addWidget(QLabel("Max sources per run"), 0, 0)
        self._max_sources = QSpinBox()
        self._max_sources.setRange(3, 50)
        self._max_sources.setValue(settings.max_total_sources)
        grid2.addWidget(self._max_sources, 0, 1)

        grid2.addWidget(QLabel("Max results per query"), 1, 0)
        self._per_query = QSpinBox()
        self._per_query.setRange(1, 20)
        self._per_query.setValue(settings.max_results_per_query)
        grid2.addWidget(self._per_query, 1, 1)

        grid2.addWidget(QLabel("Engines enabled"), 2, 0)
        engines_row = QHBoxLayout()
        self._engine_checks: dict[str, QCheckBox] = {}
        for eng in SEARCH_ENGINES:
            cb = QCheckBox(eng)
            cb.setChecked(eng in settings.search_engines)
            engines_row.addWidget(cb)
            self._engine_checks[eng] = cb
        engines_row.addStretch(1)
        engines_w = QWidget(); engines_w.setLayout(engines_row)
        grid2.addWidget(engines_w, 2, 1)

        src.add_layout(grid2)
        outer.addWidget(src)

        # --- Output / appearance card ---
        out_card = Card("Output & appearance", "Where reports are saved and how the app looks")
        grid3 = QGridLayout(); grid3.setHorizontalSpacing(10); grid3.setVerticalSpacing(6)

        grid3.addWidget(QLabel("Output folder"), 0, 0)
        folder_row = QHBoxLayout()
        self._folder = QLineEdit(settings.output_folder)
        folder_row.addWidget(self._folder)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_browse_folder)
        folder_row.addWidget(browse)
        open_folder = QPushButton("Open")
        open_folder.clicked.connect(self._on_open_folder)
        folder_row.addWidget(open_folder)
        folder_w = QWidget(); folder_w.setLayout(folder_row)
        grid3.addWidget(folder_w, 0, 1)

        grid3.addWidget(QLabel("Default format"), 1, 0)
        self._format = QComboBox()
        self._format.addItems(["markdown", "json", "html"])
        self._format.setCurrentText(settings.default_format)
        grid3.addWidget(self._format, 1, 1)

        grid3.addWidget(QLabel("Theme"), 2, 0)
        theme_row = QHBoxLayout()
        self._theme = QComboBox()
        self._theme.addItem("Dark")
        self._theme.setEnabled(False)
        theme_row.addWidget(self._theme)
        coming = QLabel("Light theme & accent picker coming soon")
        coming.setStyleSheet("color: #8a96a8; background: transparent; font-style: italic;")
        theme_row.addWidget(coming); theme_row.addStretch(1)
        theme_w = QWidget(); theme_w.setLayout(theme_row)
        grid3.addWidget(theme_w, 2, 1)

        out_card.add_layout(grid3)
        outer.addWidget(out_card)

        # --- Save button row ---
        actions = QHBoxLayout()
        actions.addStretch(1)
        save = QPushButton("Apply")
        save.setObjectName("Primary")
        save.clicked.connect(self._on_save)
        actions.addWidget(save)
        outer.addLayout(actions)

        outer.addStretch(1)

    # ---- helpers ----

    def _key_status_text(self) -> str:
        rows = [
            ("Groq",      bool(settings.groq_api_key)),
            ("Gemini",    bool(settings.gemini_api_key)),
            ("OpenAI",    bool(settings.openai_api_key)),
            ("Anthropic", bool(settings.anthropic_api_key)),
        ]
        bits = [f"<span style='color:{'#3ecf8e' if ok else '#8a96a8'};'>{name}: {'set' if ok else 'not set'}</span>"
                for name, ok in rows]
        return "  ·  ".join(bits) + "  ·  Ollama: local"

    def _on_browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose reports folder", self._folder.text())
        if path:
            self._folder.setText(path)

    def _on_open_folder(self) -> None:
        p = Path(self._folder.text())
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:  # noqa: BLE001
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    def _on_save(self) -> None:
        # In-process settings overrides — the pipeline reads `settings` at call time.
        settings.default_provider = self._provider.currentText().strip().lower()
        # Keep models dict in sync with chosen model for the active provider.
        settings.models[settings.default_provider] = self._model.text().strip()
        settings.max_total_sources = int(self._max_sources.value())
        settings.max_results_per_query = int(self._per_query.value())
        settings.search_engines = [
            eng for eng, cb in self._engine_checks.items() if cb.isChecked()
        ] or ["duckduckgo"]
        settings.output_folder = self._folder.text().strip() or "reports"
        settings.default_format = self._format.currentText()

        # Persist preferences (not secrets) into QSettings so they survive restarts.
        self._qs.setValue("provider/default", settings.default_provider)
        self._qs.setValue("provider/model", settings.models[settings.default_provider])
        self._qs.setValue("output/folder", settings.output_folder)
        self._qs.setValue("output/format", settings.default_format)
        self._qs.setValue("search/engines", ",".join(settings.search_engines))
        self._qs.setValue("search/max_sources", settings.max_total_sources)
        self._qs.setValue("search/per_query", settings.max_results_per_query)
        self._qs.sync()

        self._key_status.setText(self._key_status_text())
