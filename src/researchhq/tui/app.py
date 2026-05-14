"""ResearchHQ TUI app shell.

The app's compose builds a *persistent* shell that stays visible across
navigation:

  ┌──────────────────────────────────────────────┐
  │ Status header                       (dock=top)│
  ├────────┬─────────────────────────────────────┤
  │ Sidebar│ ContentSwitcher (active view)       │
  ├────────┴─────────────────────────────────────┤
  │ Global query input bar           (dock=bottom)│
  ├──────────────────────────────────────────────┤
  │ Footer (key hints)               (dock=bottom)│
  └──────────────────────────────────────────────┘

Views are plain Containers (not Screens) so the shell isn't hidden when the
user navigates. The Splash *is* a Screen — it's pushed once on boot and
auto-pops to reveal the shell beneath.
"""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Footer, Input

from researchhq.config import settings
from researchhq.effort import DEFAULT_EFFORT
from researchhq.tui.screens.dashboard import DashboardView
from researchhq.tui.screens.reports import ReportsView
from researchhq.tui.screens.research import ResearchView
from researchhq.tui.screens.settings import SettingsView
from researchhq.tui.screens.splash import SplashScreen
from researchhq.tui.theme import DEFAULT_THEME, PALETTES, THEME_CYCLE, render_css
from researchhq.tui.widgets.header import StatusHeader
from researchhq.tui.widgets.sidebar import NavRequest, Sidebar


class ResearchHQApp(App):
    """ResearchHQ — premium interactive terminal workspace."""

    TITLE = "ResearchHQ"
    SUB_TITLE = "premium research workstation"

    BINDINGS = [
        Binding("ctrl+q", "quit", "quit"),
        Binding("ctrl+t", "cycle_theme", "theme"),
        Binding("ctrl+r", "show_research", "research"),
        Binding("ctrl+h", "show_reports", "history"),
        Binding("ctrl+comma", "show_settings", "settings"),
        Binding("f1", "show_dashboard", "dashboard"),
        Binding("ctrl+slash", "focus_query", "query"),
    ]

    def __init__(self, *, initial_query: str | None = None, workspace: str = "default") -> None:
        super().__init__()
        env_theme = (os.environ.get("RESEARCHHQ_THEME") or "").strip().lower()
        self._theme_name = env_theme if env_theme in PALETTES else DEFAULT_THEME
        self._workspace = workspace
        self._initial_query = initial_query
        self._activity_log: list[tuple[str, str]] = []
        self.CSS = render_css(self._theme_name)

    def log_activity(self, message: str) -> None:
        """Append a (timestamp, message) entry to the dashboard activity feed.
        Bounded to the last 30 entries."""
        from datetime import datetime
        self._activity_log.append((datetime.now().strftime("%H:%M"), message))
        del self._activity_log[:-30]

    # --- composition ----------------------------------------------------------

    def compose(self) -> ComposeResult:
        # Order matters: header (fixed 1) → root_row (1fr) → input (fixed 3)
        # → Footer (docks bottom, 1). Only Footer docks; everything else
        # flows so the input is always directly above the footer.
        yield StatusHeader(theme_name=self._theme_name)
        with Horizontal(id="root_row"):
            yield Sidebar()
            with ContentSwitcher(initial="view_dashboard", id="content_switcher"):
                yield DashboardView(id="view_dashboard")
                yield ResearchView(id="view_research")
                yield ReportsView(id="view_reports")
                yield SettingsView(id="view_settings")
        yield Input(
            placeholder="Ask ResearchHQ anything…  (Ctrl+/ focus · Enter run · Esc clear)",
            id="global_query",
        )
        yield Footer()

    def on_mount(self) -> None:
        try:
            header = self.query_one("#header_bar", StatusHeader)
            header.provider = settings.default_provider or "—"
            header.model = settings.models.get(header.provider, "—")
            header.workspace = self._workspace
            header.effort = DEFAULT_EFFORT
        except Exception:
            pass

        # Seed the activity feed with boot events.
        self.log_activity("ResearchHQ started")
        self.log_activity(f"Provider {settings.default_provider} ready")
        self.log_activity(f'Workspace "{self._workspace}" activated')
        self.log_activity("Dashboard loaded")

        # Background-check Ollama reachability so users learn early whether
        # local fallback will work when the primary provider hits a rate limit.
        self.run_worker(self._probe_ollama(), exclusive=True, group="probe_ollama")

        # Splash overlay: pushes once, then pops itself to reveal the shell.
        self.push_screen(SplashScreen(self._theme_name))

    async def _probe_ollama(self) -> None:
        """One-shot reachability probe against the Ollama HTTP endpoint.

        Logs an activity line either way and pops a one-time toast if we're
        on the free-tier Groq path with no working local fallback."""
        import httpx
        host = (settings.ollama_host or "http://localhost:11434").rstrip("/")
        url = f"{host}/api/tags"
        ok = False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                ok = resp.status_code < 500
        except Exception:
            ok = False
        if ok:
            self.log_activity(f"Ollama reachable at {host}")
        else:
            self.log_activity(f"Ollama unreachable ({host})")
            chain = [p.lower() for p in settings.fallback_chain]
            primary = settings.default_provider.lower()
            # Only nag if Ollama is in the fallback chain (i.e. they expect it
            # to backstop their primary provider).
            if "ollama" in chain and primary != "ollama":
                try:
                    self.notify(
                        "Ollama not running — start `ollama serve` so ResearchHQ "
                        "can fall back when the primary provider rate-limits.",
                        severity="warning",
                        timeout=8.0,
                    )
                except Exception:
                    pass

        if self._initial_query:
            q = self._initial_query
            self._initial_query = None
            self.set_timer(1.1, lambda: self._dispatch_query(q))

    # --- screen routing -------------------------------------------------------

    def action_show_dashboard(self) -> None: self._show("dashboard")
    def action_show_research(self) -> None:  self._show("research")
    def action_show_reports(self) -> None:   self._show("reports")
    def action_show_settings(self) -> None:  self._show("settings")

    def action_focus_query(self) -> None:
        try:
            self.query_one("#global_query", Input).focus()
        except Exception:
            pass

    def on_nav_request(self, message: NavRequest) -> None:
        self._show(message.target)

    def _show(self, target: str) -> None:
        # Make sure any modal screens (splash) are dismissed first.
        while len(self.screen_stack) > 1:
            self.pop_screen()
        try:
            cs = self.query_one("#content_switcher", ContentSwitcher)
            cs.current = f"view_{target}"
            self.query_one("#sidebar", Sidebar).set_active(target)
        except Exception:
            pass

    # --- global query input ---------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "global_query":
            return
        q = (event.value or "").strip()
        if not q:
            return
        event.input.value = ""
        self._dispatch_query(q)

    def on_key(self, event) -> None:
        """Esc on the global query clears it (or unfocuses if already empty)."""
        if event.key != "escape":
            return
        try:
            inp = self.query_one("#global_query", Input)
        except Exception:
            return
        if not inp.has_focus:
            return
        if inp.value:
            inp.value = ""
            event.stop()
        else:
            # Empty + Esc → unfocus so global Esc bindings can fire.
            try:
                self.set_focus(None)
            except Exception:
                pass

    def _dispatch_query(self, q: str) -> None:
        self._show("research")
        try:
            view = self.query_one("#view_research", ResearchView)
            view.run_query(q)
        except Exception:
            pass

    # --- live settings application -------------------------------------------

    def action_cycle_theme(self) -> None:
        """Cycle through the premium theme quartet — applied live (no restart)."""
        current = self._theme_name
        # Normalise legacy aliases to their canonical names
        if current not in THEME_CYCLE:
            current = THEME_CYCLE[0]
        idx = (THEME_CYCLE.index(current) + 1) % len(THEME_CYCLE)
        self.apply_theme(THEME_CYCLE[idx])

    def apply_theme(self, theme_name: str) -> bool:
        """Hot-swap the active theme. Returns True on success.

        Preserves focus + screen state. Repaints widgets that hold a palette
        reference (the wordmark variants build Rich Text with explicit colors
        so a CSS reparse alone does not re-tint them)."""
        if theme_name not in PALETTES:
            return False
        previous = self._theme_name
        focused = self.focused
        self._theme_name = theme_name
        try:
            from textual.css.stylesheet import Stylesheet
            new_ss = Stylesheet()
            new_ss.add_source(render_css(theme_name), is_default_css=False)
            new_ss.parse()
            self._stylesheet = new_ss  # type: ignore[attr-defined]
            try:
                self.refresh_css()
            except Exception:
                self.refresh(layout=True)
        except Exception:
            self._theme_name = previous
            try:
                self.notify(f"Theme apply failed; kept {previous}", severity="error")
            except Exception:
                pass
            return False

        # Re-theme widgets that hold their own palette reference.
        try:
            from researchhq.tui.widgets.logo import (
                CompactWordmark,
                ResponsiveWordmark,
                Wordmark,
            )
            for wm_cls in (Wordmark, ResponsiveWordmark, CompactWordmark):
                for wm in self.query(wm_cls):
                    if hasattr(wm, "set_theme"):
                        wm.set_theme(theme_name)
        except Exception:
            pass

        try:
            header = self.query_one("#header_bar", StatusHeader)
            header._theme_name = theme_name
            header._refresh()
        except Exception:
            pass

        if focused is not None:
            try:
                self.set_focus(focused)
            except Exception:
                pass

        try:
            self.notify(f"Theme → {theme_name}", severity="information")
        except Exception:
            pass
        return True

    def apply_runtime_settings(
        self,
        *,
        provider: str | None = None,
        effort: str | None = None,
        workspace: str | None = None,
    ) -> None:
        """Push non-theme runtime values into the header, EffortSelectors, and
        the LLM router. Missing args leave their cell unchanged."""
        try:
            header = self.query_one("#header_bar", StatusHeader)
            if provider:
                header.provider = provider
                header.model = settings.models.get(provider, "")
            if effort:
                header.effort = effort
            if workspace:
                header.workspace = workspace
                self._workspace = workspace
        except Exception:
            pass

        if effort:
            try:
                from researchhq.tui.widgets.effort_selector import EffortSelector
                for sel in self.query(EffortSelector):
                    sel.set_value(effort)
            except Exception:
                pass

        if provider:
            # Rebuild the router so the next run picks up the new provider order.
            # In-flight runs are unaffected — they captured a router ref at start.
            try:
                from researchhq.llm import router as _r
                _r.router = _r.LLMRouter()
            except Exception:
                pass
