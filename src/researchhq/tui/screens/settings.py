"""Editable settings screen.

Form fields:
  - Theme              (Select)         persisted via config.yaml
  - Default provider   (Select)
  - Default model      (Input — free text per provider)
  - Fallback chain     (Input — comma-separated list of provider names)
  - Default mode       (Select)
  - Default effort     (RadioSet — low / medium / high; in-session default)
  - Max sources kept   (Input numeric)
  - Results per query  (Input numeric)
  - Default format     (Select — markdown / json / html)
  - Output folder      (Input)
  - Verbosity          (Select — quiet / normal / verbose / debug)

Read-only:
  - API key statuses (set / missing / local) — secrets are never displayed.

Buttons: Save · Reset · Cancel.
Validation runs before save. On success the global `settings` singleton is
mutated in place and the header refreshes immediately.
"""

from __future__ import annotations

from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select, Static

from researchhq.config import reload_settings, save_settings, settings
from researchhq.effort import PROFILES
from researchhq.tui.theme import PALETTES, THEME_CYCLE


PROVIDERS = ["groq", "gemini", "openai", "anthropic", "ollama"]
MODES = ["topic", "company", "competitor", "technology", "market", "news", "academic"]
FORMATS = ["markdown", "json", "html"]
VERBOSITY = ["quiet", "normal", "verbose", "debug"]
# Show premium themes first, then legacy extras
THEMES = THEME_CYCLE + [t for t in PALETTES if t not in THEME_CYCLE]


class SettingsView(Container):
    """Editable settings form. Holds pending edits in-memory until Save."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Snapshot of current settings used for Reset.
        self._snapshot = self._capture()

    def _capture(self) -> dict:
        return {
            "theme":              getattr(self.app, "_theme_name", "default") if self.is_mounted else "default",
            "default_provider":   settings.default_provider,
            "default_model":      settings.models.get(settings.default_provider, ""),
            "fallback_chain":     ", ".join(settings.fallback_chain),
            "default_mode":       getattr(settings, "default_mode", "topic"),
            "default_effort":     "medium",
            "max_total_sources":  settings.max_total_sources,
            "max_results_per_query": settings.max_results_per_query,
            "default_format":     settings.default_format,
            "output_folder":      settings.output_folder,
            "verbosity_default":  settings.verbosity_default,
        }

    # ------------------------------------------------------------------ compose

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="settings_scroll"):
            with Container(classes="card"):
                yield Static("APPEARANCE", classes="card_title")
                with Horizontal(classes="settings_row"):
                    yield Label("Theme", classes="settings_label")
                    yield Select(
                        options=[(t, t) for t in THEMES],
                        value=getattr(self.app, "_theme_name", "default"),
                        id="set_theme", allow_blank=False,
                    )

            with Container(classes="card"):
                yield Static("PROVIDERS", classes="card_title")
                with Horizontal(classes="settings_row"):
                    yield Label("Active provider", classes="settings_label")
                    yield Select(
                        options=[(p, p) for p in PROVIDERS],
                        value=settings.default_provider, id="set_provider",
                        allow_blank=False,
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Active model", classes="settings_label")
                    yield Input(
                        value=settings.models.get(settings.default_provider, ""),
                        placeholder="e.g. llama-3.3-70b-versatile",
                        id="set_model",
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Fallback chain", classes="settings_label")
                    yield Input(
                        value=", ".join(settings.fallback_chain),
                        placeholder="comma-separated, e.g. groq, gemini, ollama",
                        id="set_fallback",
                    )

            with Container(classes="card"):
                yield Static("RESEARCH DEFAULTS", classes="card_title")
                with Horizontal(classes="settings_row"):
                    yield Label("Default mode", classes="settings_label")
                    yield Select(
                        options=[(m, m) for m in MODES],
                        value=getattr(settings, "default_mode", "topic"),
                        id="set_mode", allow_blank=False,
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Default effort", classes="settings_label")
                    with RadioSet(id="set_effort"):
                        for level in PROFILES:
                            yield RadioButton(level, value=(level == "medium"))
                with Horizontal(classes="settings_row"):
                    yield Label("Max sources kept", classes="settings_label")
                    yield Input(
                        value=str(settings.max_total_sources),
                        placeholder="3-50",
                        id="set_max_sources",
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Results per query", classes="settings_label")
                    yield Input(
                        value=str(settings.max_results_per_query),
                        placeholder="1-12",
                        id="set_results_per_query",
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Default format", classes="settings_label")
                    yield Select(
                        options=[(f, f) for f in FORMATS],
                        value=settings.default_format, id="set_format",
                        allow_blank=False,
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Output folder", classes="settings_label")
                    yield Input(
                        value=settings.output_folder,
                        placeholder="reports",
                        id="set_output_folder",
                    )
                with Horizontal(classes="settings_row"):
                    yield Label("Verbosity", classes="settings_label")
                    yield Select(
                        options=[(v, v) for v in VERBOSITY],
                        value=settings.verbosity_default, id="set_verbosity",
                        allow_blank=False,
                    )

            with Container(classes="card"):
                yield Static("API KEYS", classes="card_title")
                yield Static(self._key_status_table(), id="set_key_status")
                yield Static(
                    "[dim italic]Keys are read from your .env file. "
                    "Edit .env in the project root to add or change them — "
                    "ResearchHQ never displays the key values themselves.[/]"
                )

            with Container(id="settings_buttons"):
                yield Button("Save", id="set_save", variant="primary")
                yield Button("Reset", id="set_reset")
                yield Button("Cancel", id="set_cancel")

            yield Static("", id="set_status")

    # --------------------------------------------------------- key status table

    @staticmethod
    def _key_status_table() -> Table:
        rows = [
            ("groq",      bool(settings.groq_api_key),      False),
            ("gemini",    bool(settings.gemini_api_key),    False),
            ("openai",    bool(settings.openai_api_key),    False),
            ("anthropic", bool(settings.anthropic_api_key), False),
            ("ollama",    True,                              True),
        ]
        t = Table.grid(padding=(0, 2))
        t.add_column(); t.add_column(); t.add_column()
        for name, ready, local in rows:
            mark = ("[#4ade80]●[/]" if ready else "[#5a6573]○[/]")
            status = ("local" if local else ("set" if ready else "missing"))
            colour = "#4ade80" if ready and not local else ("#34d4bb" if local else "#f87171")
            t.add_row(mark, Text(name, style="bold"), Text(status, style=colour))
        return t

    # ---------------------------------------------------------------- handlers

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set_save":
            self._save()
        elif event.button.id == "set_reset":
            self._reset()
        elif event.button.id == "set_cancel":
            try:
                self.app.action_show_dashboard()  # type: ignore[attr-defined]
            except Exception:
                pass

    # --------------------------------------------------------------- save flow

    def _collect(self) -> tuple[dict, list[str]]:
        """Read form values; return (updates_dict, errors)."""
        errs: list[str] = []
        try:
            theme = str(self.query_one("#set_theme", Select).value)
        except Exception:
            theme = "default"
        if theme not in THEMES:
            errs.append("Theme must be one of: " + ", ".join(THEMES))

        provider = str(self.query_one("#set_provider", Select).value)
        if provider not in PROVIDERS:
            errs.append("Active provider must be one of: " + ", ".join(PROVIDERS))

        model = self.query_one("#set_model", Input).value.strip()
        if not model:
            errs.append("Model name is required.")

        fb_text = self.query_one("#set_fallback", Input).value.strip()
        fallback = [p.strip() for p in fb_text.split(",") if p.strip()]
        for p in fallback:
            if p not in PROVIDERS:
                errs.append(f"Fallback contains unknown provider: {p}")

        mode = str(self.query_one("#set_mode", Select).value)
        if mode not in MODES:
            errs.append("Default mode must be one of: " + ", ".join(MODES))

        # RadioSet: scan its children for the pressed RadioButton.
        rs = self.query_one("#set_effort", RadioSet)
        effort = "medium"
        for rb in rs.query(RadioButton):
            if rb.value:
                effort = str(rb.label)
                break

        ms_text = self.query_one("#set_max_sources", Input).value.strip()
        try:
            max_sources = int(ms_text)
            if not (3 <= max_sources <= 50):
                raise ValueError
        except ValueError:
            errs.append("Max sources must be an integer in 3–50.")
            max_sources = settings.max_total_sources

        rpq_text = self.query_one("#set_results_per_query", Input).value.strip()
        try:
            results_pq = int(rpq_text)
            if not (1 <= results_pq <= 12):
                raise ValueError
        except ValueError:
            errs.append("Results per query must be an integer in 1–12.")
            results_pq = settings.max_results_per_query

        fmt = str(self.query_one("#set_format", Select).value)
        if fmt not in FORMATS:
            errs.append("Default format must be markdown, json, or html.")

        out = self.query_one("#set_output_folder", Input).value.strip() or "reports"
        try:
            Path(out).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errs.append(f"Output folder is not writable: {e}")

        verb = str(self.query_one("#set_verbosity", Select).value)
        if verb not in VERBOSITY:
            errs.append("Verbosity must be one of: " + ", ".join(VERBOSITY))

        # Build updates dict (excluding theme + effort which aren't in the
        # YAML schema today; effort is in-session, theme is via env var).
        merged_models = dict(settings.models)
        merged_models[provider] = model
        updates = {
            "default_provider":      provider,
            "fallback_chain":        fallback or [provider],
            "models":                merged_models,
            "max_total_sources":     max_sources,
            "max_results_per_query": results_pq,
            "default_format":        fmt,
            "output_folder":         out,
            "verbosity_default":     verb,
        }
        # Carry through TUI-only state via app attributes for live update.
        updates["__theme"]   = theme
        updates["__mode"]    = mode
        updates["__effort"]  = effort
        return updates, errs

    def _save(self) -> None:
        updates, errs = self._collect()
        status = self.query_one("#set_status", Static)
        save_btn = self.query_one("#set_save", Button)

        if errs:
            status.update(Text("✗  " + "\n   ".join(errs), style="bold #f87171"))
            try:
                self.app.notify("Validation failed — see Settings panel", severity="error")
            except Exception:
                pass
            return

        # Capture pre-apply snapshot for rollback on live-apply failure.
        prev_theme   = getattr(self.app, "_theme_name", "default")
        prev_provider = settings.default_provider
        prev_effort   = getattr(self.app.query_one("#header_bar"), "effort", "medium")

        # Pop transient fields before persisting (theme/mode/effort aren't
        # in the YAML schema; theme is in-app, mode/effort are runtime defaults).
        theme  = updates.pop("__theme",  "default")
        mode   = updates.pop("__mode",   "topic")
        effort = updates.pop("__effort", "medium")

        # Disable Save while the apply happens so a double-click can't queue
        # two writes.
        save_btn.disabled = True
        save_btn.label = "Saving…"

        try:
            path = save_settings(updates)
            reload_settings()
        except Exception as e:  # noqa: BLE001
            save_btn.disabled = False
            save_btn.label = "Save"
            status.update(Text(f"✗  could not write config: {e}", style="bold #f87171"))
            try:
                self.app.notify(f"Save failed: {e}", severity="error")
            except Exception:
                pass
            return

        # ---- live apply ----
        try:
            applied: list[str] = []
            new_provider = settings.default_provider
            if new_provider != prev_provider:
                applied.append(f"provider={new_provider}")
            if effort != prev_effort:
                applied.append(f"effort={effort}")
            self.app.apply_runtime_settings(  # type: ignore[attr-defined]
                provider=new_provider,
                effort=effort,
                workspace=getattr(self.app, "_workspace", "default"),
            )
            if theme != prev_theme:
                if self.app.apply_theme(theme):  # type: ignore[attr-defined]
                    applied.append(f"theme={theme}")
                else:
                    # Hot-swap failed — revert _theme_name; settings file is fine.
                    self.app._theme_name = prev_theme  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            # Rollback: restore prior live state (settings file is already saved
            # but the user can re-save). Notify and bail.
            try:
                self.app.apply_runtime_settings(  # type: ignore[attr-defined]
                    provider=prev_provider,
                    effort=prev_effort,
                )
            except Exception:
                pass
            save_btn.disabled = False
            save_btn.label = "Save"
            status.update(Text(
                f"✗  saved to disk but live apply failed; rolled back UI: {e}",
                style="bold #f87171",
            ))
            try:
                self.app.notify(f"Apply failed; rolled back: {e}", severity="error")
            except Exception:
                pass
            return

        # Success.
        save_btn.disabled = False
        save_btn.label = "Save"
        suffix = f" · {', '.join(applied)}" if applied else " · no live changes"
        status.update(Text(f"✓  saved to {path}{suffix}", style="bold #4ade80"))
        try:
            self.app.notify("Settings updated", severity="information")
        except Exception:
            pass
        self._snapshot = self._capture()

    def _reset(self) -> None:
        s = self._snapshot
        self.query_one("#set_theme",     Select).value = s["theme"]
        self.query_one("#set_provider",  Select).value = s["default_provider"]
        self.query_one("#set_model",     Input).value  = s["default_model"]
        self.query_one("#set_fallback",  Input).value  = s["fallback_chain"]
        self.query_one("#set_mode",      Select).value = s["default_mode"]
        self.query_one("#set_max_sources",        Input).value = str(s["max_total_sources"])
        self.query_one("#set_results_per_query",  Input).value = str(s["max_results_per_query"])
        self.query_one("#set_format",    Select).value = s["default_format"]
        self.query_one("#set_output_folder", Input).value = s["output_folder"]
        self.query_one("#set_verbosity", Select).value = s["verbosity_default"]
        rs = self.query_one("#set_effort", RadioSet)
        for rb in rs.query(RadioButton):
            rb.value = (str(rb.label) == s["default_effort"])
        self.query_one("#set_status", Static).update(
            Text("Reverted to last saved values.", style="dim"),
        )
