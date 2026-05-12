# researchhq — Multi-Agent Research Workstation

A general-purpose multi-agent research assistant. Two surfaces, one engine:

- **CLI** — `research <mode> "<query>"`. Scriptable, deterministic, CI-friendly.
- **ResearchHQ Studio (GUI)** — desktop workstation built on PySide6: dashboard,
  live agent pipeline, source intelligence, history with search/filter,
  side-by-side compare, multi-format export including PDF.

Built on free-tier providers (Groq, Gemini, local Ollama). Operational cost: **$0**.

> **Heritage**: this project began as `competiq`, a competitor-only intelligence tool. The legacy `competiq` CLI is preserved for backward compatibility (see [Backward compatibility](#backward-compatibility)).

## Launching ResearchHQ Studio

```powershell
# One-time install of GUI extras
.venv\Scripts\python.exe -m pip install -e ".[gui]"

# Launch
python -m researchhq.gui
# or, after `pip install -e .`:
researchhq-gui
```

**Pages**

- **Dashboard** — Quick stats (total reports, sources collected, last-run cost), provider/model status, recent reports, saved exports, "+ New Research" CTA.
- **New Research** — Query input, mode + provider + max sources + search depth + format selectors, presets dropdown, Run/Cancel, **live stats** (elapsed, current agent, sources, LLM calls, tokens, cost), pipeline chip view, report tabs (Executive Summary / Full Report / Sources / Evidence / JSON / Logs), live log console with debug toggle, exports (.md / .json / .html / .pdf / copy summary / copy full).
- **History** — DB-backed; search by query/mode/provider, filter by workspace and mode, open or duplicate-to-research, delete with sibling exports.
- **Compare** — Pick two saved reports and view them side-by-side; export a combined markdown.
- **Settings** — Default provider/model, search engines, max sources, max results per query, output folder, default format, theme (dark only today; light + accent picker coming soon).

**Keyboard shortcuts** (Research page): `Ctrl+Enter` run · `Esc` cancel · `Ctrl+S` save in default format · `Ctrl+K` focus query.

## Health check

```powershell
researchhq doctor
```

Verifies Python version, required deps, provider keys, router init, output folder writability, history DB, and GUI importability. Exit code 1 on any critical failure.

## What it does

Give it a query in any of these modes and get back a structured, source-cited report:

| Mode | Use it for |
|------|------------|
| `topic` | Open-ended research on a topic, idea, trend, or person |
| `company` | Profile a company (product, market, momentum) |
| `competitor` | Competitive landscape around a target company |
| `tech` | A technology / framework / platform |
| `market` | Industry / market sizing & dynamics |
| `news` | Recent / breaking developments |
| `academic` | Research-paper survey on an area |

Every report includes:

- Executive summary
- Key findings
- Source-backed evidence (inline-cited)
- Recent developments (if relevant for the mode)
- Risks & limitations
- Confidence score
- Source list with URLs and quality tier
- Recommended next research questions

## Architecture

```
User Query + Mode
   |
   v
Planner agent      -> 6-8 specific search queries
   |
   v
Search agent       -> DuckDuckGo (more engines pluggable)
   |
   v
Source-ranker      -> classifies + tier-weights every URL
   |
   v
Fact extractor     -> atomic claims with evidence URLs
   |
   v
Synthesizer        -> composes report sections (mode-specific)
   |
   v
Verifier / critic  -> confidence score, flags weak claims
   |
   v
Formatter          -> follow-up questions + final ResearchReport
   |
   v
Exporter           -> markdown / json / html
```

Each mode declares its own:

- **Query planning strategy** (template seeds + LLM-augmented planner)
- **Preferred source tiers** (e.g. academic mode favors arxiv & .edu)
- **Tier weights & drop list** (e.g. market mode drops social)
- **Output structure** (section headings)
- **Confidence rules** (e.g. news requires multi-source corroboration)

## Source quality ranking

Sources are classified into tiers. Each tier has a default credibility score that the active mode can override:

- `OFFICIAL` (10) — vendor/company-owned site or product docs
- `ACADEMIC` (10) — arxiv, .edu, peer-reviewed venues
- `GOVERNMENT` (10) — .gov, .mil, intergovernmental bodies
- `NEWS` (8) — established trade & general press
- `DOCS` (8) — technical documentation
- `GITHUB` (7) — code repositories
- `COMPARISON` (7) — review aggregators (G2, Capterra, etc.)
- `WIKI` (6) — Wikipedia, Wikidata
- `COMMUNITY` (5) — Reddit, HN, StackExchange, dev.to
- `SOCIAL` (4) — Twitter/X, LinkedIn, YouTube
- `BLOG` (4) — non-authoritative blogs
- `LOW_QUALITY` (1) — content farms
- `SEARCH_ENGINE` (0) — search-aggregator pages (filtered out)

## Installation

```powershell
cd "C:\Users\sharvik admin\Desktop\VsCode\multi_agent"
uv sync
```

Or with pip:

```powershell
python -m pip install -e .
```

Optional providers:

```powershell
python -m pip install -e ".[openai]"
python -m pip install -e ".[anthropic]"
```

## Environment variables

Place these in a `.env` file at the project root:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq API key (recommended primary) |
| `GEMINI_API_KEY` | Gemini API key |
| `OPENAI_API_KEY` | (optional) OpenAI |
| `ANTHROPIC_API_KEY` | (optional) Anthropic |
| `OLLAMA_HOST` | Ollama URL (default `http://localhost:11434`) |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `RESEARCHHQ_CONFIG` | Override path to a `config.yaml` |

## Configuration: `config.yaml`

```yaml
provider:
  default: groq
  fallback_chain: [groq, gemini, ollama]

models:
  groq: llama-3.3-70b-versatile
  gemini: gemini-2.0-flash-exp
  ollama: llama3.2:3b
  openai: gpt-4o-mini
  anthropic: claude-haiku-4-5-20251001

search:
  engines: [duckduckgo]
  max_results_per_query: 6
  max_total_sources: 18

report:
  output_folder: reports
  default_format: markdown   # markdown | json | html
  include_recent_developments: true

verbosity:
  default: normal             # quiet | normal | verbose | debug
  hide_http_logs_unless_debug: true
```

## CLI

The universal command pattern:

```
research <mode> "<query>" [--format markdown|json|html] [--quiet|--verbose|--debug]
```

(Equivalently: `python -m researchhq.cli research <mode> ...` or via the `researchhq` script.)

### Examples — one per mode

```powershell
research research topic      "AI agents in cybersecurity"
research research company    "Supabase"
research research competitor "Linear"
research research tech       "MISP threat intelligence platform"
research research market     "Backend as a Service market"
research research news       "OpenAI latest product updates"
research research academic   "retrieval augmented generation evaluation"
```

> Note: the entry-point name is `research` and the subcommand group is also `research`; that is intentional and matches the spec. If you prefer, the entry point `researchhq` also works:
>
> `researchhq research topic "AI agents in cybersecurity"`

### Export formats

```powershell
research research market "BaaS market" --format markdown
research research market "BaaS market" --format json
research research market "BaaS market" --format html
```

Reports are saved into `reports/` (configurable via `output_folder`) as `<mode>__<slugified_query>.<ext>`.

### Verbosity controls

```powershell
research research news "OpenAI" --quiet     # suppresses non-essential output
research research news "OpenAI"             # default: progress spinner + report
research research news "OpenAI" --verbose   # stage-by-stage progress lines
research research news "OpenAI" --debug     # all logs including HTTP
```

By default, noisy HTTP logs (httpx, urllib3, ddgs, etc.) are silenced; `--debug` re-enables them.

### Other commands

```powershell
research modes      # list available research modes
research status     # show provider configuration
```

## Backward compatibility

The original CLI is preserved unchanged:

```powershell
competiq research "Linear"     # original single-agent briefing
competiq pipeline "Supabase"   # original LangGraph multi-agent flow
competiq status                # original provider status
```

The `competiq` package remains installed alongside `researchhq`; the new CLI does not depend on it.

## Project structure

```
multi_agent/
+-- config.yaml
+-- pyproject.toml
+-- README.md
+-- src/
|   +-- researchhq/                # new universal package
|   |   +-- cli.py                 # `research <mode> "<query>"`
|   |   +-- config.py              # YAML + env settings loader
|   |   +-- pipeline.py            # orchestrator
|   |   +-- agents/
|   |   |   +-- planner.py
|   |   |   +-- searcher.py
|   |   |   +-- source_ranker.py
|   |   |   +-- extractor.py
|   |   |   +-- synthesizer.py
|   |   |   +-- verifier.py
|   |   |   +-- formatter.py
|   |   +-- modes/
|   |   |   +-- base.py
|   |   |   +-- general.py
|   |   |   +-- company.py
|   |   |   +-- competitor.py
|   |   |   +-- technology.py
|   |   |   +-- market.py
|   |   |   +-- news.py
|   |   |   +-- academic.py
|   |   +-- llm/
|   |   |   +-- router.py
|   |   |   +-- cost_tracker.py
|   |   |   +-- providers/         # base, groq, gemini, ollama, openai, anthropic
|   |   +-- search/
|   |   |   +-- web_search.py
|   |   |   +-- source_quality.py
|   |   +-- reports/
|   |   |   +-- schema.py
|   |   |   +-- exporter.py        # markdown / json / html
|   |   +-- utils/
|   |       +-- logging.py
|   |       +-- rich_ui.py
|   +-- competiq/                  # legacy package (preserved)
+-- tests/
```

## Adding a new agent

1. Add `src/researchhq/agents/<myagent>.py` with the function signature you need (sync or async).
2. Wire it into `researchhq/pipeline.py` between two existing stages, emitting a `StageEvent` so the CLI can show progress.
3. Add a unit test in `tests/test_<myagent>.py`.

The pipeline is a flat sequence rather than a graph (intentionally — easier to extend than the LangGraph version in the legacy `competiq` package). If you need fan-out / fan-in, mirror the structure in `competiq/graph/workflow.py`.

## Adding a new research mode

1. Create `src/researchhq/modes/<mymode>.py`. Subclass `ResearchMode` from `modes.base` and define a `ModeConfig` with:
   - `name`, `description`
   - `seed_query_templates` — list of `"{q} ..."` formatters
   - `preferred_tiers`, `drop_tiers`, `tier_weights`
   - `report_sections` — section headings for the synthesizer
   - `confidence_rules` — strings appended to verifier notes
   - `synthesizer_persona` — first-person system-prompt persona
2. Implement `seed_queries(self, query)`.
3. Register the mode in `researchhq/modes/__init__.py` (`MODES` dict).
4. Add a Typer subcommand in `researchhq/cli.py` that delegates to `_execute("<mymode>", ...)`.
5. Add it to the test in `tests/test_modes.py`.

## Tests

The test suite covers:

- Planner output structure and graceful fallback
- Source-quality classification and ranking
- Mode selection (and aliasing)
- Report formatting (markdown / json / html)
- CLI command parsing (every mode + every flag)
- Confidence-score behavior

```powershell
pytest -q
```

## Why this is useful

- **Multi-mode** — one tool for company / market / tech / news / academic / topic / competitor research
- **Multi-provider LLM** — Groq primary, Gemini synthesis, Ollama fallback, plus OpenAI/Anthropic stubs
- **Source-aware** — every URL classified and ranked; confidence reflects evidence quality
- **Free tier** — runs on $0 if you use Groq + Gemini + Ollama
- **Structured output** — markdown / json / html exports, ready to feed downstream tools
