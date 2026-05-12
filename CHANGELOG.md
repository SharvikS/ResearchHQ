# Changelog

## v0.3 — Production-grade GUI upgrade (2026-05-06)

### Added
- **Pipeline event system** (`researchhq.events.PipelineEvent`)
  Typed events emitted at every stage: `run_started`, `agent_started`,
  `agent_finished`, `source_found`, `llm_call_finished` (with token + cost
  data), `report_section_ready`, `run_completed`, `run_failed`, `run_canceled`.
  Both the CLI and GUI consume the same stream.
- **SQLite history index** (`researchhq.history`)
  Every saved report is indexed for filter/search/aggregate. Supports
  workspaces, mode/text/date filtering, totals/aggregates. DB self-heals if
  corrupt; `Reindex` button rebuilds from disk.
- **`researchhq doctor`** command
  Health check across Python version, required deps, provider keys, router
  init, output folder writability, history DB, GUI importability, optional
  deps. Critical-failure exit code so it's CI-friendly.
- **GUI: live stats strip** on Research page — elapsed, current agent,
  sources, LLM calls, tokens (in/out), equivalent cost, all updating in real
  time via worker signals.
- **GUI: Compare page** — pick two saved reports, render side-by-side,
  export combined markdown.
- **GUI: research presets** — Company deep dive, Competitor comparison,
  Technology explainer, Market landscape, Latest news scan, Academic
  literature scan, Product review analysis.
- **GUI: report viewer Evidence + Logs tabs** — Evidence shows verifier
  rule outcomes and citation violations; Logs preserves the run's log
  output.
- **GUI: PDF export** via `QTextDocument` → `QPrinter` (no extra deps).
- **GUI: history page upgrade** — DB-backed, workspace filter, mode filter,
  text search, duplicate-to-research, reindex button.
- **GUI: keyboard shortcuts** — Ctrl+Enter (Run), Esc (Cancel), Ctrl+S
  (Save default format), Ctrl+K (focus query).
- **GUI: provider quick-select** dropdown; rebuilds router for the run.
- **GUI: copy summary / copy full report** clipboard buttons.
- **22 new tests**: pipeline events, history DB (insert/filter/aggregate/
  reindex/corrupt-recovery), doctor checks, GUI worker signal dispatch.
  Total now 74 passing.

### Changed
- `pipeline.run` accepts the typed `on_event` callback (back-compat:
  `StageEvent` is an alias for `PipelineEvent`; CLI's existing renderer
  continues to read `.stage` and `.detail`).
- `exporter.save` now also writes the JSON form alongside the chosen
  format and indexes into the history DB. Failures in indexing never
  break the save.
- Sidebar gains a Compare entry; main window has 5 pages.

### Coming soon (intentionally not shipped)
- **Pause/Resume** during a run. Cancel works; pause needs mid-stage
  checkpointing in async LLM calls. Button is disabled with a tooltip.
- **Light theme + accent picker.** Theme dropdown is disabled with an
  inline note. Dark theme remains the only option.
- **Per-workspace creation/rename UI.** Workspaces are honored end-to-end
  (DB column, filters), but new workspaces are only created when reports
  are saved with a different `workspace=` argument. A workspace manager
  is the next obvious step.
- **Run multiple comparisons in-place** (kick off N pipelines from the
  Compare page). Today the Compare page only juxtaposes existing reports.

### Backward compatibility
- `competiq research <X>` and `competiq pipeline <X>` — unchanged.
- `research <mode> "<query>"` CLI — unchanged.
- Pipeline `on_event(StageEvent)` callers continue to receive `stage`
  and `detail` on every event.
- Reports saved by previous versions: GUI History will auto-`reindex`
  them on first launch (the empty-state in the History page also offers
  a button).
