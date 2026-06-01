# ResearchHQ — Production Feature Documentation

**Version 0.3.0** · Python 3.11+ · Free-tier LLM · Multi-surface

---

## Table of Contents

1. [What Is ResearchHQ?](#1-what-is-researchhq)
2. [Quick Start](#2-quick-start)
3. [Architecture Overview](#3-architecture-overview)
4. [Research Modes](#4-research-modes)
5. [The 8-Stage Pipeline](#5-the-8-stage-pipeline)
6. [User Interfaces](#6-user-interfaces)
   - [CLI](#61-command-line-interface-cli)
   - [Desktop GUI (Studio)](#62-desktop-gui-researchhq-studio)
   - [Terminal UI (TUI)](#63-terminal-ui-tui)
7. [LLM Providers & Routing](#7-llm-providers--routing)
8. [Source Quality System](#8-source-quality-system)
9. [Ensemble Mode](#9-ensemble-mode)
10. [Effort Levels](#10-effort-levels)
11. [Reports & Export](#11-reports--export)
12. [History & Database](#12-history--database)
13. [Configuration Reference](#13-configuration-reference)
14. [Environment Variables](#14-environment-variables)
15. [Installation](#15-installation)
16. [Docker Deployment](#16-docker-deployment)
17. [Testing](#17-testing)
18. [Extending the System](#18-extending-the-system)
19. [Cost Transparency](#19-cost-transparency)
20. [Health Check](#20-health-check)
21. [Troubleshooting](#21-troubleshooting)
22. [Changelog](#22-changelog)

---

## 1. What Is ResearchHQ?

ResearchHQ is a **multi-agent research workstation** that converts natural-language queries into structured, source-cited research reports. It orchestrates a chain of eight specialized AI agents — planner, searcher, source ranker, page fetcher, fact extractor, synthesizer, verifier, and formatter — across three user surfaces:

| Surface | Entry Point | Best For |
|---|---|---|
| **CLI** | `research <mode> "<query>"` | Scripting, CI pipelines, headless runs |
| **Desktop GUI** | `researchhq-gui` | Interactive research, report history |
| **Terminal UI** | `rhq` | SSH sessions, terminal-first workflows |

**Key differentiators:**

- **Zero operational cost** — runs entirely on free-tier providers (Groq, Gemini, Ollama)
- **Multi-mode** — seven specialized research strategies in one tool
- **Source-aware** — every URL classified into 13 quality tiers; confidence reflects evidence quality
- **Citation-safe** — verifier strips invented URLs before they reach the output
- **Ensemble synthesis** — optional parallel multi-provider runs for cross-validated answers
- **Transparent cost** — every run shows equivalent paid-API cost even when using free tiers

---

## 2. Quick Start

### 2.1 Install and Run (60 seconds)

```powershell
# Clone / enter project
cd "C:\Users\sharvik admin\Desktop\Projects\researchhq-multi-agent"

# Install (uv is fastest)
uv sync
# or: python -m pip install -e .

# Set at least one API key (Groq is free at console.groq.com)
echo GROQ_API_KEY=gsk_... >> .env

# Run your first report
research research topic "impact of AI agents on software development"
```

The report is written to `reports/topic__impact-of-ai-agents-on-software-development.md`.

### 2.2 Launch the GUI

```powershell
pip install -e ".[gui]"   # one-time
researchhq-gui
```

### 2.3 Launch the TUI

```powershell
pip install -e ".[tui]"   # one-time
rhq
```

---

## 3. Architecture Overview

### 3.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ResearchHQ v0.3                               │
│                                                                      │
│  ┌─────────┐   ┌─────────┐   ┌──────────────────────────────────┐  │
│  │   CLI   │   │   GUI   │   │        TUI (Textual)              │  │
│  │ (Typer) │   │(PySide6)│   │                                  │  │
│  └────┬────┘   └────┬────┘   └────────────────┬─────────────────┘  │
│       │              │                          │                    │
│       └──────────────┴──────────────────────────┘                   │
│                             │                                        │
│                    ┌────────▼────────┐                              │
│                    │  pipeline.run() │  ◄── PipelineEvent stream    │
│                    └────────┬────────┘                              │
│                             │                                        │
│         ┌───────────────────┼───────────────────┐                  │
│         │                   │                   │                   │
│   ┌─────▼──────┐   ┌───────▼──────┐   ┌───────▼──────┐          │
│   │  8 Agents  │   │  LLM Router  │   │  Web Search  │          │
│   │  (async)   │   │  (fallback   │   │ (DuckDuckGo) │          │
│   └─────┬──────┘   │   chain)     │   └──────────────┘          │
│         │           └───────┬──────┘                              │
│         │                   │                                       │
│         │           ┌───────▼──────────────────────────┐          │
│         │           │   LLM Providers                  │          │
│         │           │  ┌──────┐ ┌──────┐ ┌──────────┐ │          │
│         │           │  │ Groq │ │Gemini│ │  Ollama  │ │          │
│         │           │  └──────┘ └──────┘ └──────────┘ │          │
│         │           │  ┌────────┐ ┌───────────┐        │          │
│         │           │  │OpenAI  │ │ Anthropic │        │          │
│         │           │  │(opt.)  │ │  (opt.)   │        │          │
│         │           │  └────────┘ └───────────┘        │          │
│         │           └──────────────────────────────────┘          │
│         │                                                           │
│   ┌─────▼─────────────────────────────────────────────────┐       │
│   │  ResearchReport (Pydantic)                             │       │
│   │  mode · query · sections · facts · verifier · sources │       │
│   └─────┬─────────────────────────────────────────────────┘       │
│         │                                                           │
│   ┌─────▼───────────────────────────────────┐                     │
│   │   Exporter                               │                     │
│   │   ┌──────────┐ ┌──────┐ ┌──────┐       │                     │
│   │   │ Markdown │ │ JSON │ │ HTML │       │                     │
│   │   └──────────┘ └──────┘ └──────┘       │                     │
│   └──────────────────────────────────────────┘                     │
│                                                                      │
│   ┌──────────────────────────────────────────┐                     │
│   │   SQLite History DB (.researchhq.db)     │                     │
│   └──────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Pipeline Event Stream

Every stage emits typed `PipelineEvent` objects consumed in real time by all surfaces:

```
run_started
  └─ agent_started      (stage="planner")
  │    └─ agent_finished
  └─ agent_started      (stage="searcher")
  │    └─ source_found  (url, title, tier)
  │    └─ agent_finished
  └─ agent_started      (stage="source_ranker")
  │    └─ agent_finished
  └─ agent_started      (stage="fetcher")
  │    └─ agent_finished
  └─ agent_started      (stage="extractor")
  │    └─ llm_call_started / llm_call_finished (tokens, cost)
  │    └─ agent_finished
  └─ agent_started      (stage="synthesizer")
  │    └─ report_section_ready (heading, body)
  │    └─ agent_finished
  └─ agent_started      (stage="verifier")
  │    └─ agent_finished
  └─ agent_started      (stage="formatter")
  │    └─ agent_finished
run_completed (report, elapsed, cost)
```

---

## 4. Research Modes

ResearchHQ ships with seven specialized research modes. Each mode defines its own query-planning strategy, source-tier preferences, output structure, synthesizer persona, and verifier rules.

### 4.1 Mode Overview

| Mode | Alias | Best For | High-Weight Tiers | Dropped Tiers |
|---|---|---|---|---|
| `topic` | `general` | Open-ended research, trends, ideas, people | All | None |
| `company` | — | Company profile, product, momentum | `OFFICIAL`, `NEWS` | `SOCIAL` |
| `competitor` | — | Competitive landscape around a target | `OFFICIAL`, `COMPARISON`, `NEWS` | — |
| `technology` | `tech` | Framework / platform / tool deep-dive | `DOCS`, `GITHUB`, `ACADEMIC` | `SOCIAL` |
| `market` | — | Industry sizing, dynamics, players | `NEWS`, `COMPARISON`, `OFFICIAL` | `SOCIAL`, `BLOG` |
| `news` | — | Recent / breaking developments | `NEWS`, `OFFICIAL` | `SOCIAL`, `LOW_QUALITY` |
| `academic` | `paper` | Research-area literature survey | `ACADEMIC`, `GOVERNMENT` | `SOCIAL`, `BLOG` |

### 4.2 Report Sections Per Mode

Each mode generates a structured set of sections:

**Topic** — Introduction · Key Concepts · Current State · Applications · Challenges · Future Outlook · References

**Company** — Executive Overview · Products & Services · Market Position · Business Model · Leadership & Culture · Recent Developments · Risks & Challenges · Outlook

**Competitor** — Competitive Landscape · Key Players · Strengths & Weaknesses · Market Positioning · Feature Comparison · Strategic Moves · Conclusion

**Technology** — Overview · Technical Architecture · Key Features · Use Cases · Ecosystem & Community · Limitations · Alternatives · Getting Started

**Market** — Market Overview · Size & Growth · Key Players · Market Segments · Trends & Drivers · Challenges · Opportunities · Outlook

**News** — Summary · Key Developments · Timeline · Stakeholders · Context · Analysis · What to Watch

**Academic** — Research Overview · Key Papers & Authors · Core Concepts · Methodologies · Current Debates · Open Problems · Practical Applications

### 4.3 CLI Examples

```powershell
# Open-ended topic research
research research topic "impact of AI agents on software development"

# Company profiling
research research company "Supabase"

# Competitive intelligence
research research competitor "Linear"

# Technology deep-dive
research research tech "MISP threat intelligence platform"

# Market analysis
research research market "Backend as a Service market 2025"

# Breaking news
research research news "OpenAI latest product announcements"

# Literature survey
research research academic "retrieval augmented generation evaluation methods"
```

---

## 5. The 8-Stage Pipeline

The pipeline is a sequential async chain. Every stage tolerates partial failure — no single agent crashing stops the run.

### Stage Flow

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    Pipeline Execution                            │
  │                                                                  │
  │  ◈ PLANNER ──► ⌖ SEARCHER ──► ⊞ RANKER ──► ⬇ FETCHER          │
  │  (cyan)        (blue)          (magenta)     (yellow)           │
  │                                                                  │
  │  ⚗ EXTRACTOR ──► ⬡ SYNTHESIZER ──► ◉ VERIFIER ──► ◎ FORMATTER │
  │  (bright_yellow) (green)           (bright_blue)  (magenta)     │
  └─────────────────────────────────────────────────────────────────┘
```

### 5.1 Planner Agent

**Input:** user query + mode
**Output:** `ResearchPlan` (6–8 targeted web search queries + rationale)

The planner uses the mode's `seed_query_templates` as a starting point and augments them with an LLM call to generate query variants covering different angles (what, why, how, who, when). If LLM is unavailable, it falls back to template-filled queries without error.

```
User: "Supabase"  (mode: company)
Planner output:
  1. "Supabase company overview products 2025"
  2. "Supabase funding valuation investors"
  3. "Supabase vs Firebase comparison"
  4. "Supabase technical architecture PostgreSQL"
  5. "Supabase pricing plans enterprise"
  6. "Supabase recent news announcements"
  7. "Supabase user reviews community feedback"
  8. "Supabase roadmap upcoming features"
```

### 5.2 Search Agent

**Input:** list of planned queries
**Output:** deduplicated `SearchResult` list (title, URL, snippet)

Executes all queries concurrently via `asyncio.gather`. Uses DuckDuckGo by default (no API key required). Results are deduplicated by URL. Partial search failures are tolerated and logged.

**Configurable:**
- `max_results_per_query` (default: 6)
- `max_total_sources` (default: 18)
- `engines` (default: `[duckduckgo]`)

### 5.3 Source Ranker Agent

**Input:** raw search results + active mode
**Output:** ranked `RankedSource` list with tier classification and numeric score

Classifies every URL into one of 13 source tiers using domain registries, then applies the mode's tier weights and drops disallowed tiers.

```
Score = base_tier_score + mode_tier_weight_bonus
```

Results sorted descending by score; top N passed to fetcher.

### 5.4 Fetcher Agent

**Input:** top-ranked source URLs
**Output:** `FetchedPage` list (url, title, extracted text, status, byte count, truncated flag)

Fetches pages concurrently (max 5 simultaneous). Strips HTML tags via lightweight regex + `HTMLParser` (no external library). Text per page is capped (configurable, default 4000 chars) and truncation is tracked. Fetch errors return empty text — they never fail the pipeline.

**Timeout:** 10s per page

### 5.5 Fact Extractor Agent

**Input:** query + ranked sources + fetched pages
**Output:** `Fact` list — each with `claim`, `evidence_urls`, `confidence` (0.0–1.0)

Uses LLM to extract atomic factual claims from snippets and fetched text. Post-extraction validation:

1. `validate_evidence_urls` — ensures all evidence URLs are in the known source set
2. High-confidence claims (≥0.8) that lose all evidence after validation are demoted to 0.5

```
Example Fact:
  claim: "Supabase raised $80M Series C in August 2022"
  evidence_urls: ["https://techcrunch.com/2022/08/10/supabase-raises-80m/"]
  confidence: 0.92
```

### 5.6 Synthesizer Agent

**Input:** mode + query + ranked sources + facts + fetched pages
**Output:** `Section` list (heading, body in Markdown)

Composes the final report using the mode's synthesizer persona and section skeleton. Page content is budget-limited to prevent context overflow. After synthesis, `strip_unknown_citations` removes any invented URLs while preserving the surrounding text.

### 5.7 Verifier Agent

**Input:** sections + facts + sources
**Output:** `VerifierNote` (overall_confidence score, rule results, violations)

Runs 20+ deterministic rules including:

| Rule Category | Examples |
|---|---|
| Citation integrity | Invented URL detection, citation density |
| Evidence authority | HIGH_TIER source requirement (official, academic, government, news, docs) |
| Numeric specificity | Dollar amounts, percentages, dates cited |
| Attribution | Explicit "according to" phrasing |
| Mode-specific | Academic requires paper references; news requires multi-source corroboration |

**Confidence formula:**

```
confidence = 1.0
  - 0.10 per FAIL rule
  - 0.05 per WARN rule
  (clamped to [0.0, 1.0])
```

**Confidence labels:** ≥0.85 → High · ≥0.65 → Medium · <0.65 → Low

### 5.8 Formatter Agent

**Input:** mode + query + report sections
**Output:** 4–6 recommended follow-up research questions

LLM generates questions targeting gaps left open by the current report. Falls back to generic questions if LLM is unavailable.

---

## 6. User Interfaces

### 6.1 Command Line Interface (CLI)

#### Universal Command Pattern

```
research <mode> "<query>" [OPTIONS]
```

```
Options:
  --format    markdown | json | html     (default: from config.yaml)
  --quiet     suppress non-essential output
  --verbose   stage-by-stage progress lines
  --debug     all logs including HTTP traffic
  --effort    low | medium | high        (default: medium)
```

#### All Subcommands

```powershell
# Research commands
research research topic      "query"     # run topic research
research research company    "query"
research research competitor "query"
research research tech       "query"
research research market     "query"
research research news       "query"
research research academic   "query"

# Utility commands
research modes                           # list available modes
research status                          # show provider + model config
research history                         # show recent runs (DB-backed)
research agents                          # describe the 8 pipeline agents
research settings                        # show current settings
research config                          # show loaded config.yaml
research doctor                          # full health check
research setup                           # interactive first-run setup
research models                          # list models per provider
research test-models                     # fire test completion per provider
research export --id <run_id> --fmt html # re-export a past report
research logs                            # tail the log file
research clear-history                   # wipe the history DB
research reset-config                    # restore default config.yaml
```

#### Live Pipeline Display

```
┌─ ResearchHQ ───────────────────────────────────────────────────────┐
│                                                                     │
│  ◈ planner     [✓] Generated 8 search queries                      │
│  ⌖ searcher    [✓] Found 17 sources                                │
│  ⊞ ranker      [✓] Ranked: 6 OFFICIAL · 4 NEWS · 3 DOCS           │
│  ⬇ fetcher     [✓] Fetched 14 pages (3 failed)                    │
│  ⚗ extractor   [✓] Extracted 31 facts                             │
│  ⬡ synthesizer [●] Writing Executive Summary...                   │
│  ◉ verifier    [ ] Waiting                                         │
│  ◎ formatter   [ ] Waiting                                         │
│                                                                     │
│  Elapsed: 23s · Sources: 17 · LLM calls: 6 · Tokens: 14,230       │
│  Cost: $0.00 (equivalent: $0.011)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

#### Verbosity Levels

```powershell
# Quiet — report only, no progress
research research news "OpenAI" --quiet

# Normal (default) — spinner + summary stats
research research news "OpenAI"

# Verbose — per-stage progress lines
research research news "OpenAI" --verbose

# Debug — all logs including HTTP, raw LLM calls
research research news "OpenAI" --debug
```

### 6.2 Desktop GUI (ResearchHQ Studio)

Built on **PySide6** (Qt6). Launch with `researchhq-gui`.

#### GUI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ResearchHQ Studio                                    [─][□][×]    │
├──────────┬──────────────────────────────────────────────────────────┤
│          │                                                           │
│ SIDEBAR  │              CONTENT AREA                                │
│          │                                                           │
│ ● Dashboard        ┌─────────────────────────────────────────────┐ │
│   Research   ──►   │  Active page renders here                   │ │
│   History          │                                             │ │
│   Compare          │                                             │ │
│   Settings         └─────────────────────────────────────────────┘ │
│          │                                                           │
│ [Status] │                                                           │
└──────────┴──────────────────────────────────────────────────────────┘
```

#### Page: Dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│  DASHBOARD                                                           │
│                                                                      │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐          │
│  │  Total Reports │ │Sources Collected│ │  Last Run Cost │          │
│  │      142       │ │     3,847       │ │   $0.00        │          │
│  └────────────────┘ └────────────────┘ └────────────────┘          │
│                                                                      │
│  ┌──────────────────────────────────┐ ┌─────────────────────────┐  │
│  │  Provider Status                 │ │  Recent Reports          │  │
│  │  Groq      ● Connected           │ │  ► company__supabase.md  │  │
│  │  Gemini    ● Connected           │ │  ► topic__ai-agents.md   │  │
│  │  Ollama    ○ Offline             │ │  ► market__baas-2025.md  │  │
│  │  OpenAI    ─ No key              │ │  ► news__openai-news.md  │  │
│  │  Anthropic ─ No key              │ │                          │  │
│  └──────────────────────────────────┘ └─────────────────────────┘  │
│                                                                      │
│                    [ + New Research ]                                │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- Live provider/model status board (refreshed every 3s)
- Aggregate stats from SQLite history
- Clickable recent reports list
- Saved exports gallery
- "+ New Research" CTA button navigates to Research page

#### Page: New Research

```
┌─────────────────────────────────────────────────────────────────────┐
│  NEW RESEARCH                                                         │
│                                                                      │
│  Query ┌────────────────────────────────────────────────────┐       │
│  ──────│  Supabase competitive landscape 2025               │       │
│        └────────────────────────────────────────────────────┘       │
│                                                                      │
│  Mode [competitor ▾]  Provider [auto ▾]  Sources [18]  Depth [6]   │
│  Format [markdown ▾]  Preset [─ select ─ ▾]                         │
│                                                                      │
│  [ ▶ Run Research — Ctrl+Enter ]  [ ✕ Cancel ]                      │
│                                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  ◈ planner  ✓  │  ⌖ searcher  ✓  │  ⊞ ranker  ✓  │  ⬇ fetcher  ✓  │
│  ⚗ extractor ✓ │  ⬡ synthesizer ● Writing Key Findings...           │
│  ◉ verifier    │  ◎ formatter                                        │
│                                                                      │
│  Elapsed: 28s · Agent: synthesizer · Sources: 16 · Calls: 7        │
│  Tokens: 18,420 (in: 14,100 / out: 4,320) · Cost equiv: $0.013     │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Executive Summary │ Full Report │ Sources │ Evidence │ JSON │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │                                                             │   │
│  │  Supabase operates in a crowded BaaS market where Firebase  │   │
│  │  remains the incumbent. The company differentiates through  │   │
│  │  its open-source Postgres foundation...                     │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [↓ Markdown] [↓ JSON] [↓ HTML] [↓ PDF] [⎘ Summary] [⎘ Full]       │
│                                                                      │
│  ┌─ Logs ──────────────────────── [□ Debug] ──────────────────┐    │
│  │ 14:23:01  planner   Generated 8 queries                    │    │
│  │ 14:23:03  searcher  Found 16 sources                       │    │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- Query text input with Ctrl+K focus shortcut
- Mode, provider, source count, search depth, format, preset selectors
- Live 8-stage pipeline chip visualization with spinner on active stage
- Real-time stats strip: elapsed, current agent, sources, LLM calls, tokens (in/out), equivalent cost
- Tabbed report viewer: Executive Summary · Full Report · Sources · Evidence · JSON · Logs
- Evidence tab shows verifier rule outcomes and citation violations
- Logs tab with debug toggle (filters to DEBUG-level when enabled)
- Export buttons: `.md`, `.json`, `.html`, `.pdf` (no extra deps — uses Qt printer)
- Clipboard buttons: copy executive summary or full report

**Keyboard shortcuts:**

| Shortcut | Action |
|---|---|
| `Ctrl+Enter` | Run research |
| `Esc` | Cancel in-progress run |
| `Ctrl+S` | Save in default format |
| `Ctrl+K` | Focus query input |

**Research Presets:**

| Preset | Mode | Best For |
|---|---|---|
| Company Deep Dive | company | Full company profile |
| Competitor Comparison | competitor | Competitive landscape |
| Technology Explainer | tech | Framework/tool evaluation |
| Market Landscape | market | Industry sizing |
| Latest News Scan | news | Breaking developments |
| Academic Literature | academic | Research survey |
| Product Review Analysis | competitor | User review synthesis |

#### Page: History

```
┌─────────────────────────────────────────────────────────────────────┐
│  HISTORY                     Search: [__________] Mode: [All ▾]    │
│                                                                      │
│  Workspace: [Default ▾]                        [ ↻ Reindex ]        │
│                                                                      │
│  ┌──────────────────┬──────────┬──────────┬───────┬──────┬───────┐ │
│  │ Query            │ Mode     │ Provider │ Conf. │ Cost │ Date  │ │
│  ├──────────────────┼──────────┼──────────┼───────┼──────┼───────┤ │
│  │ Supabase comp... │ competitor│ groq    │ High  │$0.00 │ Today │ │
│  │ AI agents in ... │ topic    │ gemini   │ High  │$0.00 │ Today │ │
│  │ BaaS market 2025 │ market   │ groq     │ Medium│$0.00 │ 5/13  │ │
│  │ OpenAI latest ...│ news     │ groq     │ High  │$0.00 │ 5/12  │ │
│  └──────────────────┴──────────┴──────────┴───────┴──────┴───────┘ │
│                                                                      │
│  Selected: "Supabase comp..."      [ ► Open ] [ ⎘ Duplicate ] [ 🗑 ]│
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- Full-text search across query, mode, and provider fields
- Filter by workspace, mode, confidence tier
- Column-sortable table
- "Open" — loads report in viewer
- "Duplicate to Research" — pre-fills the Research page with the same query/mode/settings for a fresh run
- "Delete" — removes DB record and associated export files
- "Reindex" — rebuilds the DB from all JSON files in the output folder (recovery option)

#### Page: Compare

Select two past reports from the history to view them side-by-side in a split-pane Markdown view. Export button produces a combined comparison Markdown file.

```
┌──────────────────────────┬──────────────────────────────────────────┐
│ Report A                 │ Report B                                  │
│ competitor__supabase.md  │ competitor__firebase.md                  │
├──────────────────────────┼──────────────────────────────────────────┤
│ ## Competitive Landscape │ ## Competitive Landscape                  │
│                          │                                           │
│ Supabase positions as    │ Firebase, Google's BaaS platform,        │
│ the open-source alter... │ dominates with 1M+ apps...               │
└──────────────────────────┴──────────────────────────────────────────┘
[ Export Combined Markdown ]
```

#### Page: Settings

```
┌─────────────────────────────────────────────────────────────────────┐
│  SETTINGS                                                            │
│                                                                      │
│  Provider                                                            │
│    Default provider    [groq ▾]                                     │
│    Default model       [llama-3.3-70b-versatile ▾]                  │
│                                                                      │
│  Search                                                              │
│    Engines             [duckduckgo ▾]                               │
│    Max sources         [18      ]                                    │
│    Results per query   [6       ]                                    │
│                                                                      │
│  Output                                                              │
│    Output folder       [reports/         ] [Browse]                 │
│    Default format      [markdown ▾]                                  │
│                                                                      │
│  Appearance                                                          │
│    Theme               Dark (light theme coming soon)               │
│                                                                      │
│  [ Save Settings ]                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Terminal UI (TUI)

Built on **Textual**. Launch with `rhq`.

#### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ResearchHQ  │  workspace: default  │  ● groq  ● gemini  ○ ollama  │
├──────────────┬──────────────────────────────────────────────────────┤
│              │                                                       │
│ ▶ Dashboard  │         CONTENT AREA                                 │
│   Research   │                                                       │
│   Reports    │                                                       │
│   Settings   │                                                       │
│              │                                                       │
├──────────────┴──────────────────────────────────────────────────────┤
│ ^Q Quit  ^T Theme  ^R Research  ^H History  F1 Dashboard            │
└─────────────────────────────────────────────────────────────────────┘
```

#### TUI Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Q` | Quit |
| `Ctrl+T` | Cycle through themes |
| `Ctrl+R` | Go to Research screen |
| `Ctrl+H` | Go to History screen |
| `Ctrl+,` | Go to Settings |
| `F1` | Go to Dashboard |
| `Ctrl+/` | Focus query input |

#### TUI Screens

- **Dashboard** — recent runs, activity log, provider status
- **Research** — query input, mode/effort selectors, live pipeline widget, result tabs
- **Reports** — history table with search/filter and report viewer
- **Settings** — in-terminal config editor
- **Splash** — startup screen (auto-pops after load)

**Theme cycling** (`Ctrl+T`) toggles through available Textual themes. Override at launch with:

```powershell
$env:RESEARCHHQ_THEME = "nord"
rhq
```

---

## 7. LLM Providers & Routing

### 7.1 Provider Chain

ResearchHQ routes LLM calls through a configurable fallback chain. If the primary provider returns a rate-limit or error, it automatically tries the next.

```
Request ──► [Provider 1: Groq] ──fail──► [Provider 2: Gemini] ──fail──► [Provider 3: Ollama]
                     │                              │                              │
                  success                        success                       success
                     │                              │                              │
                     ▼                              ▼                              ▼
              LLMResponse                   LLMResponse                   LLMResponse
```

**Rate-limit cool-down:** After a 429 or 413 error, a provider enters a 60-second cool-down and is skipped for subsequent calls in that session.

### 7.2 Provider Details

| Provider | Models | Free Tier | Notes |
|---|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | Yes — sign up at console.groq.com | Recommended primary; fastest inference |
| **Gemini** | `gemini-2.0-flash-exp` | Yes — sign up at aistudio.google.com | Excellent quality; generous free tier |
| **Ollama** | `llama3.2:3b` | Free (local) | Requires local Ollama install; no API key |
| **OpenAI** | `gpt-4o-mini` | No | Optional extra: `pip install -e ".[openai]"` |
| **Anthropic** | `claude-haiku-4-5-20251001` | No | Optional extra: `pip install -e ".[anthropic]"` |

### 7.3 Configuring Providers

**Recommended minimum setup (free):**

```
GROQ_API_KEY=gsk_...         # Get at: console.groq.com/keys
GEMINI_API_KEY=AIza...       # Get at: aistudio.google.com/apikey
```

**With local Ollama:**

```
OLLAMA_HOST=http://localhost:11434    # default
```

Pull models locally:
```powershell
ollama pull llama3.2:3b
```

**Override model per provider in `config.yaml`:**

```yaml
models:
  groq: llama-3.3-70b-versatile
  gemini: gemini-2.0-flash-exp
  ollama: llama3.2:3b
  openai: gpt-4o-mini
  anthropic: claude-haiku-4-5-20251001
```

### 7.4 Testing Provider Connectivity

```powershell
# Visual status board
research status

# Fire a test completion per configured provider
research test-models

# Full health check including router init
researchhq doctor
```

---

## 8. Source Quality System

Every URL found during the search phase is classified into one of 13 quality tiers. The active mode's `tier_weights` boosts or penalizes each tier's score, and `drop_tiers` eliminates entire categories from the run.

### 8.1 Tier Reference

| Tier | Score | Examples |
|---|---|---|
| `OFFICIAL` | 10 | Vendor sites, product documentation owned by the company |
| `ACADEMIC` | 10 | arxiv.org, scholar.google.com, nature.com, ieee.org |
| `GOVERNMENT` | 10 | .gov, .mil, intergovernmental bodies |
| `NEWS` | 8 | TechCrunch, The Verge, Bloomberg, Reuters, Wired |
| `DOCS` | 8 | Technical documentation (docs.*, developer.*, api.*) |
| `GITHUB` | 7 | github.com, gitlab.com, huggingface.co |
| `COMPARISON` | 7 | g2.com, capterra.com, gartner.com, trustradius.com |
| `WIKI` | 6 | wikipedia.org, wikidata.org |
| `COMMUNITY` | 5 | reddit.com, news.ycombinator.com, stackoverflow.com, dev.to |
| `SOCIAL` | 4 | twitter.com, linkedin.com, youtube.com, tiktok.com |
| `BLOG` | 4 | Non-authoritative personal and company blogs |
| `LOW_QUALITY` | 1 | Content farms, thin-content sites |
| `SEARCH_ENGINE` | 0 | google.com, bing.com, duckduckgo.com — filtered out |

### 8.2 Mode × Tier Interaction

Each mode declares preferred tiers (score bonus), drop tiers (excluded), and tier weights:

```python
# Example: academic mode
preferred_tiers = [ACADEMIC, GOVERNMENT, DOCS]
drop_tiers = {SOCIAL, BLOG, LOW_QUALITY}
tier_weights = {
    ACADEMIC: +3.0,
    GOVERNMENT: +2.0,
    COMMUNITY: -1.0,  # slight penalty for community in academic mode
}
```

The final score for a source is:

```
score = TIER_BASE_SCORE + tier_weights.get(tier, 0)
```

Sources in `drop_tiers` are removed before ranking, regardless of score.

### 8.3 Source Table (GUI)

The Sources tab in the report viewer shows:

```
┌──────────────────────────────────────────────────────────────────────┐
│ # │ Tier        │ Score │ Domain              │ Title                │
├──────────────────────────────────────────────────────────────────────┤
│ 1 │ OFFICIAL    │  10   │ supabase.com        │ Supabase Overview    │
│ 2 │ NEWS        │   8   │ techcrunch.com      │ Supabase raises $80M │
│ 3 │ DOCS        │   8   │ supabase.com/docs   │ Getting Started      │
│ 4 │ GITHUB      │   7   │ github.com/supabase │ supabase/supabase    │
│ 5 │ COMPARISON  │   7   │ g2.com              │ Supabase Reviews     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Ensemble Mode

Ensemble mode runs the synthesis stage across **multiple LLM providers in parallel**, then applies consensus analysis to produce a cross-validated report with higher confidence.

### 9.1 Enabling Ensemble

**Via CLI:**

```powershell
research research market "BaaS market" --ensemble balanced
```

**Via `config.yaml`:**

```yaml
ensemble:
  enabled: true
  mode: balanced      # cheap | balanced | max_confidence
  provider_timeout: 60
```

### 9.2 Ensemble Profiles

| Profile | Providers | Cost | Quality |
|---|---|---|---|
| `cheap` | groq, ollama | $0.00 | Good |
| `balanced` | groq, gemini, openai | ~$0.001 | Better |
| `max_confidence` | groq, gemini, openai, anthropic, ollama | ~$0.005 | Best |

### 9.3 How Ensemble Works

```
Query + Mode
    │
    ▼
  Planner + Searcher + Ranker + Fetcher + Extractor
    │         (shared single-pass pipeline stages)
    │
    ├──► Synthesizer (Groq)    ──► Section draft A
    ├──► Synthesizer (Gemini)  ──► Section draft B
    └──► Synthesizer (OpenAI)  ──► Section draft C
                │
                ▼
         Claim Extractor    (atomic claims per provider)
                │
                ▼
         Consensus Engine   (Jaccard similarity grouping)
                │
          ┌─────┴───────────────┐
          │                     │
    CONSENSUS claims      CONTESTED claims
    (2+ providers agree)  (providers disagree)
          │                     │
          └─────────┬───────────┘
                    │
                    ▼
             Merger + Confidence
             ┌───────────────────────────────────────┐
             │ overall_score = weighted combination:  │
             │   40% provider_agreement               │
             │   25% source_quality                   │
             │   20% factual_consistency              │
             │   15% hallucination_safety             │
             └───────────────────────────────────────┘
                    │
                    ▼
           EnsembleReportSection (attached to ResearchReport)
```

### 9.4 Ensemble Output

The final report's `ensemble` field includes:

- List of providers that ran and their status
- Per-claim agreement score
- Contested claims (where providers disagreed)
- Overall confidence score with breakdown
- Providers run, providers failed

The Evidence tab in the GUI shows contested claims highlighted so users can see where providers disagreed.

---

## 10. Effort Levels

The `--effort` flag (or GUI setting) dials every depth parameter simultaneously to balance speed against report quality.

| Parameter | `low` | `medium` (default) | `high` |
|---|---|---|---|
| Search queries generated | 4 | 6 | 8 |
| Results per query | 4 | 6 | 8 |
| Total sources | 10 | 18 | 25 |
| Pages fetched | 4 | 6 | 8 |
| Chars per page | 2,500 | 4,000 | 8,000 |
| Extractor max tokens | 800 | 1,600 | 2,400 |
| Synthesizer max tokens | 1,200 | 2,400 | 4,000 |
| Synthesis depth | terse | balanced | thorough |
| Follow-up questions | 2 | 4 | 6 |

**Use `low`** for quick summaries or when API quota is tight.
**Use `high`** for comprehensive reports where quality matters more than speed.

---

## 11. Reports & Export

### 11.1 Report Structure

Every `ResearchReport` (Pydantic model) contains:

```
ResearchReport
├── mode          (topic | company | competitor | tech | market | news | academic)
├── query         (original user query string)
├── effort        (low | medium | high)
├── generated_at  (ISO 8601 timestamp)
├── provider_used (e.g. "groq")
├── plan          ResearchPlan
│   ├── queries   [list of search queries]
│   └── rationale
├── sources       [RankedSource]
│   ├── url
│   ├── title
│   ├── tier
│   ├── score
│   └── domain
├── facts         [Fact]
│   ├── claim
│   ├── evidence_urls
│   └── confidence (0.0–1.0)
├── sections      [Section]
│   ├── heading
│   └── body      (Markdown)
├── verifier      VerifierNote
│   ├── overall_confidence (0.0–1.0)
│   ├── rules     [RuleResult]
│   └── violations [CitationViolation]
├── next_questions [str]
├── stage_costs   [StageCost]
│   ├── stage, calls, input_tokens, output_tokens, equivalent_cost_usd
└── ensemble      EnsembleReportSection (if ensemble mode was used)
```

### 11.2 File Naming

Reports are saved as:

```
reports/<mode>__<slugified_query>.<ext>
```

Example: `reports/company__supabase.md`

Both the requested format and a JSON sidecar are always written (JSON is needed for history indexing and future re-export).

### 11.3 Export Formats

| Format | CLI Flag | GUI Button | Notes |
|---|---|---|---|
| Markdown | `--format markdown` | `↓ Markdown` | Default; best for reading, Git-friendly |
| JSON | `--format json` | `↓ JSON` | Machine-readable, full Pydantic schema |
| HTML | `--format html` | `↓ HTML` | Lightweight renderer, no extra deps |
| PDF | — | `↓ PDF` | GUI only; uses Qt printer (no wkhtmltopdf) |
| Clipboard | — | `⎘ Summary` / `⎘ Full` | GUI only; copies text to OS clipboard |

### 11.4 Re-exporting a Report

```powershell
# Re-export an existing report in a different format
research export --id <run_id> --fmt html

# Or use the Duplicate button in History page (GUI) and re-run
```

### 11.5 Markdown Report Anatomy

```markdown
# Supabase — Competitive Landscape

> **Confidence:** High (0.87) · **Sources:** 16 · **Generated:** 2026-05-14T14:23:01

## Executive Overview
...

## Competitive Landscape
...

## Key Players
...

---

## Sources

| # | Tier | Domain | Title |
|---|---|---|---|
| 1 | OFFICIAL | supabase.com | Supabase — The Open Source Firebase Alternative |
| 2 | NEWS | techcrunch.com | Supabase raises $80M Series C |
...

---

## Verifier Notes

- **Confidence:** High (0.87)
- ✓ Evidence authority: all key claims backed by OFFICIAL or NEWS sources
- ✓ Citation density: adequate inline citations
- ✗ Numeric specificity: 2 claims lack cited figures

---

## Next Research Questions

1. How does Supabase's pricing compare to Firebase at scale?
2. What is Supabase's enterprise customer traction?
...
```

---

## 12. History & Database

ResearchHQ maintains a SQLite database at `reports/.researchhq.db` for indexing all runs.

### 12.1 Schema

```sql
CREATE TABLE runs (
  id                  TEXT PRIMARY KEY,
  json_path           TEXT,
  mode                TEXT,
  query               TEXT,
  workspace           TEXT DEFAULT 'default',
  provider            TEXT,
  model               TEXT,
  confidence          REAL,
  sources_count       INTEGER,
  facts_count         INTEGER,
  rules_failed        INTEGER,
  equivalent_cost_usd REAL,
  input_tokens        INTEGER,
  output_tokens       INTEGER,
  elapsed_s           REAL,
  generated_at        TEXT
);
CREATE INDEX idx_runs_workspace    ON runs(workspace);
CREATE INDEX idx_runs_mode         ON runs(mode);
CREATE INDEX idx_runs_generated_at ON runs(generated_at);
```

### 12.2 History Commands

```powershell
# List recent runs (CLI)
research history

# Wipe history database
research clear-history

# Rebuild DB from disk (recovery)
# Use the "Reindex" button in GUI History page, or:
research export --reindex
```

### 12.3 Aggregates

The Dashboard displays aggregate statistics computed from the DB:

- Total runs
- Total unique sources collected
- Total equivalent cost (always $0 on free providers)
- Average confidence score

### 12.4 Workspaces

All runs belong to a workspace (default: `"default"`). Workspace-based filtering is available in the History page. Workspaces are created automatically when a report is saved with a `workspace=` argument (no UI to create them yet — coming in v0.4).

---

## 13. Configuration Reference

ResearchHQ uses a layered config system. Later layers override earlier ones:

```
1. Built-in defaults (hardcoded in config.py)
2. ~/.researchhq/config.yaml  (user global)
3. ./config.yaml              (project local)  ← recommended
4. .env file                  (API keys)
5. CLI flags                  (per-run overrides)
```

### 13.1 Full `config.yaml` Reference

```yaml
# LLM Provider configuration
provider:
  default: groq                        # primary provider
  fallback_chain: [groq, gemini, ollama]  # tried in order on failure

# Model selection per provider
models:
  groq: llama-3.3-70b-versatile
  gemini: gemini-2.0-flash-exp
  ollama: llama3.2:3b
  openai: gpt-4o-mini
  anthropic: claude-haiku-4-5-20251001

# Web search configuration
search:
  engines: [duckduckgo]                # pluggable; duckduckgo requires no key
  max_results_per_query: 6             # results fetched per search query
  max_total_sources: 18                # hard cap across all queries

# Report output
report:
  output_folder: reports               # relative to project root
  default_format: markdown             # markdown | json | html
  include_recent_developments: true    # append recent-developments section

# Verbosity
verbosity:
  default: normal                      # quiet | normal | verbose | debug
  hide_http_logs_unless_debug: true    # silences httpx, ddgs, urllib3 at normal level

# Ensemble (optional parallel multi-provider synthesis)
ensemble:
  enabled: false                       # set true to always use ensemble
  mode: balanced                       # cheap | balanced | max_confidence
  provider_timeout: 60                 # seconds before a provider times out

# Observability (optional — requires docker-compose services)
langfuse:
  public_key: ""
  secret_key: ""
  host: "http://localhost:3000"
```

### 13.2 Effort Presets (Read-only Reference)

Effort presets are hardcoded in `src/researchhq/effort.py`. They cannot be customized via `config.yaml` but `--effort` selects among them:

```powershell
research research company "Supabase" --effort high
```

---

## 14. Environment Variables

Create a `.env` file in the project root:

```bash
# ── LLM Provider Keys ──────────────────────────────────────────────
GROQ_API_KEY=gsk_...              # Free at: console.groq.com/keys
GEMINI_API_KEY=AIza...            # Free at: aistudio.google.com/apikey
OPENAI_API_KEY=sk-...             # Optional; requires billing
ANTHROPIC_API_KEY=sk-ant-...      # Optional; requires billing

# ── Local Ollama ────────────────────────────────────────────────────
OLLAMA_HOST=http://localhost:11434   # Default; override if Ollama runs elsewhere

# ── Storage (optional, for advanced features) ────────────────────────
POSTGRES_URL=postgresql://user:pass@localhost:5432/researchhq
REDIS_URL=redis://localhost:6379/0

# ── Observability (optional, requires docker-compose) ────────────────
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# ── Runtime ─────────────────────────────────────────────────────────
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR
RESEARCHHQ_CONFIG=/path/to/config.yaml   # Override config file path
RESEARCHHQ_THEME=nord               # TUI theme override
```

---

## 15. Installation

### 15.1 Prerequisites

- Python 3.11 or higher
- `uv` (recommended) or `pip`
- At least one LLM API key (Groq is free)

### 15.2 Standard Install

```powershell
# Navigate to project
cd "C:\Users\sharvik admin\Desktop\Projects\researchhq-multi-agent"

# Install with uv (fastest)
uv sync

# Or with pip
python -m pip install -e .
```

### 15.3 Optional Extras

```powershell
# Desktop GUI (PySide6 / Qt6)
python -m pip install -e ".[gui]"

# Terminal UI (Textual)
python -m pip install -e ".[tui]"

# OpenAI provider
python -m pip install -e ".[openai]"

# Anthropic provider
python -m pip install -e ".[anthropic]"

# Full development environment
python -m pip install -e ".[dev]"    # adds pytest, ruff, mypy

# Install everything
python -m pip install -e ".[gui,tui,openai,anthropic,dev]"
```

### 15.4 Entry Points After Install

| Command | Description |
|---|---|
| `research` | CLI research runner |
| `researchhq` | Interactive + utility CLI |
| `researchhq-gui` | Desktop GUI (Studio) |
| `rhq` | Terminal UI (TUI) |
| `competiq` | Legacy CLI (backward compat) |

### 15.5 Verify Installation

```powershell
# Comprehensive health check
researchhq doctor
```

Expected output:

```
✓ Python 3.11.9
✓ groq installed (0.13.0)
✓ google-genai installed
✓ GROQ_API_KEY set
✓ GEMINI_API_KEY set
✓ LLM router initialised (2 providers)
✓ Output folder writable: reports/
✓ History DB: reports/.researchhq.db (142 entries)
✓ GUI imports OK (PySide6 6.7.2)
○ OPENAI_API_KEY not set (optional)
○ ANTHROPIC_API_KEY not set (optional)
○ Ollama not reachable at localhost:11434 (optional)

All critical checks passed.
```

---

## 16. Docker Deployment

### 16.1 Start Supporting Services

```powershell
# Start PostgreSQL (with pgvector), Redis, and Langfuse observability stack
docker-compose up -d

# Services started:
#   PostgreSQL   localhost:5432   (persistent data in Docker volume)
#   Redis        localhost:6379
#   Langfuse DB  localhost:5433
#   Langfuse UI  localhost:3000   (open in browser for trace exploration)
```

### 16.2 Build and Run ResearchHQ Container

```powershell
docker build -t researchhq .

docker run \
  -e GROQ_API_KEY=$env:GROQ_API_KEY \
  -e GEMINI_API_KEY=$env:GEMINI_API_KEY \
  -v ${PWD}/reports:/app/reports \
  researchhq \
  research research company "Supabase"
```

### 16.3 Docker Compose File Overview

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: researchhq
      POSTGRES_DB: researchhq
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: pg_isready

  redis:
    image: redis:7-alpine
    volumes: [redisdata:/data]

  langfuse-db:
    image: postgres:16
    environment:
      POSTGRES_DB: langfuse

  langfuse:
    image: langfuse/langfuse:latest
    ports: ["3000:3000"]
    depends_on: [langfuse-db]
```

---

## 17. Testing

### 17.1 Run the Test Suite

```powershell
# Quick run (quiet)
pytest -q

# With verbose output
pytest -v

# Run specific test file
pytest tests/test_pipeline_events.py -v

# Run with coverage report
pytest --cov=src/researchhq --cov-report=term-missing
```

### 17.2 Test Coverage (74 tests)

| Test File | What It Covers |
|---|---|
| `test_modes.py` | Mode resolution, aliases (tech → technology, paper → academic) |
| `test_planner.py` | Query plan generation, JSON extraction, graceful fallback |
| `test_source_quality.py` | Domain classification, tier assignment for all 13 tiers |
| `test_citation_guard.py` | Citation validation, unknown URL stripping |
| `test_verifier.py` | Rule evaluation logic |
| `test_verifier_rules.py` | All 20+ rules: pass/fail/warn conditions |
| `test_ensemble_consensus.py` | Jaccard similarity grouping, consensus/contested classification |
| `test_ensemble_confidence.py` | Multi-dimensional confidence scoring |
| `test_ensemble_disagreement.py` | Conflict detection across providers |
| `test_report_format.py` | Markdown / JSON / HTML export correctness |
| `test_pipeline_events.py` | Event emission sequence and payload shape |
| `test_cli.py` | Command parsing, every mode + every flag |
| `test_history_db.py` | SQLite CRUD, filter, aggregate, corrupt DB recovery |
| `test_cost_tracker.py` | Token accumulation, per-stage rollup, equivalent-cost math |
| `test_doctor.py` | Health check conditions (missing key, unwritable folder, etc.) |
| `test_e2e_mocked.py` | Full end-to-end run with mocked LLM responses |
| `test_gui_worker_signals.py` | Qt worker signal emission from pipeline thread |

### 17.3 Writing New Tests

```python
# tests/test_myagent.py
import pytest
from researchhq.agents.myagent import my_agent_fn

@pytest.mark.asyncio
async def test_my_agent_basic():
    result = await my_agent_fn(query="test query", ...)
    assert result is not None
    assert len(result) > 0
```

Run with `pytest-asyncio` which is included in `[dev]` extras.

---

## 18. Extending the System

### 18.1 Adding a New Research Mode

1. **Create the mode file:**

```python
# src/researchhq/modes/legal.py
from .base import ResearchMode, ModeConfig
from ..search.source_quality import SourceTier

class LegalMode(ResearchMode):
    config = ModeConfig(
        name="legal",
        description="Legal research and regulatory analysis",
        seed_query_templates=[
            "{q} legal regulations compliance",
            "{q} court cases precedents",
            "{q} regulatory framework",
            "{q} legal requirements jurisdiction",
        ],
        preferred_tiers=[SourceTier.GOVERNMENT, SourceTier.ACADEMIC, SourceTier.OFFICIAL],
        drop_tiers={SourceTier.SOCIAL, SourceTier.LOW_QUALITY},
        tier_weights={
            SourceTier.GOVERNMENT: 3.0,
            SourceTier.ACADEMIC: 2.0,
            SourceTier.BLOG: -2.0,
        },
        report_sections=[
            "Regulatory Overview",
            "Key Legislation",
            "Case Law",
            "Compliance Requirements",
            "Jurisdictional Variations",
            "Recent Developments",
            "Practical Implications",
        ],
        confidence_rules=[
            "Legal claims must cite official government or academic sources",
            "Regulatory statements require jurisdiction specification",
        ],
        synthesizer_persona=(
            "You are a legal research analyst. Cite statutes, regulations, and "
            "case law precisely. Flag jurisdiction-specific variations. Never give "
            "legal advice — only factual legal research."
        ),
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
```

2. **Register in the modes registry:**

```python
# src/researchhq/modes/__init__.py
from .legal import LegalMode

MODES: dict[str, ResearchMode] = {
    ...
    "legal": LegalMode(),
}
```

3. **Add CLI subcommand** in `cli.py`:

```python
@research_app.command("legal")
def cmd_legal(query: str, ...):
    _execute("legal", query, ...)
```

4. **Add test:**

```python
# tests/test_modes.py
def test_legal_mode_resolves():
    mode = resolve_mode("legal")
    assert mode.config.name == "legal"
```

### 18.2 Adding a New LLM Provider

1. **Create provider class:**

```python
# src/researchhq/llm/providers/mistral_provider.py
from .base import LLMProvider, LLMResponse

class MistralProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "mistral-large-latest"):
        self.client = MistralClient(api_key=api_key)
        self.model = model

    async def complete(
        self, prompt: str, system: str = "", max_tokens: int = 1000
    ) -> LLMResponse:
        response = await self.client.chat_async(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            text=response.choices[0].message.content,
            model=self.model,
            provider="mistral",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
```

2. **Register in router:**

```python
# src/researchhq/llm/router.py
if settings.mistral_api_key:
    providers.append(MistralProvider(api_key=settings.mistral_api_key))
```

### 18.3 Adding a New Pipeline Agent

1. **Create agent function:**

```python
# src/researchhq/agents/semantic_deduplicator.py
from ..reports.schema import Fact

async def semantic_dedup(facts: list[Fact], threshold: float = 0.85) -> list[Fact]:
    """Remove semantically duplicate facts above similarity threshold."""
    ...
    return deduplicated_facts
```

2. **Wire into pipeline** (`pipeline.py`) between extractor and synthesizer:

```python
emit(PipelineEvent("agent_started", "semantic_deduplicator", "Deduplicating facts"))
facts = await semantic_dedup(facts)
emit(PipelineEvent("agent_finished", "semantic_deduplicator", f"{len(facts)} unique facts"))
```

3. **Add test in `tests/test_semantic_deduplicator.py`.**

### 18.4 Adding a New Search Engine

```python
# src/researchhq/search/web_search.py

async def _brave_search_async(query: str, max_results: int) -> list[SearchResult]:
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": max_results},
        )
        data = await resp.json()
        return [
            SearchResult(title=r["title"], url=r["url"], snippet=r["description"])
            for r in data["web"]["results"]
        ]

_ENGINES_ASYNC["brave"] = _brave_search_async
```

Then enable in `config.yaml`:

```yaml
search:
  engines: [duckduckgo, brave]
```

---

## 19. Cost Transparency

ResearchHQ tracks every LLM call and reports equivalent paid-API cost, even when running on free-tier providers. This helps teams understand what they would pay if they switched to paid tiers.

### 19.1 Reference Pricing (per million tokens)

| Provider | Input | Output |
|---|---|---|
| Groq (Llama 70B) | $0.59 | $0.79 |
| Gemini Flash | $0.075 | $0.30 |
| OpenAI GPT-4o-mini | $0.15 | $0.60 |
| Anthropic Haiku | $0.25 | $1.25 |
| Ollama (local) | $0.00 | $0.00 |

### 19.2 Cost Output

At the end of every CLI run:

```
┌─ Cost Summary ─────────────────────────────────────────────────────┐
│ Stage         Calls  In tokens  Out tokens  Equiv. cost            │
│ planner         1      420         180       $0.0004               │
│ extractor       1     6,240       1,120      $0.0043               │
│ synthesizer     1     8,100       2,840      $0.0069               │
│ formatter       1      380         240       $0.0004               │
│ ─────────────────────────────────────────────────────────────────  │
│ TOTAL           4    15,140       4,380      $0.0120               │
│                                                                     │
│ Actual cost: $0.00  (running on free-tier Groq)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 20. Health Check

```powershell
researchhq doctor
```

Checks and reports on:

| Check | Critical? | Description |
|---|---|---|
| Python version | Yes | Must be ≥ 3.11 |
| Core dependencies | Yes | groq, google-genai, duckduckgo-search, pydantic, etc. |
| GROQ_API_KEY | Warn | Not required if another provider is set |
| GEMINI_API_KEY | Warn | Not required if another provider is set |
| LLM router init | Yes | At least one provider must initialize |
| Output folder | Yes | Must be writable |
| History DB | Warn | Auto-created; warns if corrupt |
| GUI imports | Info | PySide6 availability (only if `[gui]` installed) |
| Optional providers | Info | OpenAI, Anthropic, Ollama connectivity |

**Exit code:** `0` (all critical checks pass) or `1` (any critical failure). CI-friendly.

---

## 21. Troubleshooting

### No output / silent failure

```powershell
# Run with debug to see all logs
research research topic "test" --debug
```

### LLM provider errors

```
Error: groq.RateLimitError: Rate limit exceeded
```

**Fix:** Add a second provider. The fallback chain handles this automatically:

```yaml
provider:
  fallback_chain: [groq, gemini, ollama]
```

### Ollama not connecting

```powershell
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Pull the required model
ollama pull llama3.2:3b
```

### GUI won't launch (PySide6 missing)

```powershell
python -m pip install -e ".[gui]"
```

### History DB corrupt

The DB self-heals on startup. If it doesn't:

```powershell
# Delete and let it rebuild
Remove-Item reports/.researchhq.db

# Then use "Reindex" in GUI History page to re-populate from disk JSONs
```

### Report confidence is "Low"

Low confidence usually means the verifier found issues. Check the Evidence tab in the GUI or look at the `verifier.violations` field in the JSON export to see which rules failed.

### Search returns few results

Increase search depth in `config.yaml`:

```yaml
search:
  max_results_per_query: 10
  max_total_sources: 30
```

Or use `--effort high` for the current run:

```powershell
research research market "BaaS" --effort high
```

### PDF export hangs (GUI)

This is a known issue (see audit). PDF generation via Qt printer can be slow for long reports. Wait for the progress spinner to complete — there is no timeout. Fix planned for v0.4.

---

## 22. Changelog

### v0.3.0 — Production-grade GUI upgrade (2026-05-06)

**Added:**
- Typed `PipelineEvent` stream consumed by all surfaces (CLI, GUI, TUI)
- SQLite history index with workspace support, filter, aggregate, reindex
- `researchhq doctor` health check (CI-friendly exit codes)
- GUI live stats strip: elapsed, agent, sources, calls, tokens, cost (real-time)
- GUI Compare page: side-by-side report diff, combined export
- GUI research presets (7 role-based configurations)
- GUI Evidence + Logs tabs in report viewer
- GUI PDF export (no extra deps — Qt printer)
- GUI History page upgrade: DB-backed, workspace/mode filters, text search
- GUI keyboard shortcuts: Ctrl+Enter, Esc, Ctrl+S, Ctrl+K
- GUI provider quick-select dropdown
- GUI clipboard: copy summary / copy full report
- 22 new tests (total: 74 passing)

**Changed:**
- `pipeline.run` accepts typed `on_event` callback (`StageEvent` aliased for back-compat)
- `exporter.save` now writes JSON sidecar and indexes to history DB on every save

**Known limitations (planned for v0.4):**
- Pause/Resume not implemented (Cancel works)
- Light theme not available (dark only)
- Per-workspace UI manager not yet built
- PDF export has no loading state (app appears to hang)

### v0.2.0 — Multi-surface + Ensemble

- Added PySide6 GUI with Dashboard, Research, History pages
- Added Textual TUI
- Added Ensemble multi-provider synthesis
- Added 7 research modes (was competitor-only)
- Added Effort levels (low/medium/high)

### v0.1.0 — Initial release (as `competiq`)

- Single competitor-intelligence mode
- CLI only
- Groq + Gemini providers
- Markdown export

---

## Appendix A: Project File Map

```
researchhq-multi-agent/
├── config.yaml                    # Layered config (edit this for your setup)
├── pyproject.toml                 # Package metadata, deps, entry points
├── .env                           # API keys (not committed)
├── .env.example                   # Template for .env
├── docker-compose.yml             # PostgreSQL + Redis + Langfuse stack
├── Dockerfile                     # Container build
├── README.md                      # Quick-start guide
├── DOCUMENTATION.md               # This file
├── CHANGELOG.md                   # Version history
├── audit_for_claude.md            # Known issues + remediation plan
│
├── src/
│   ├── researchhq/                # Main package
│   │   ├── cli.py                 # All CLI commands (Typer)
│   │   ├── pipeline.py            # 8-stage async orchestrator
│   │   ├── events.py              # PipelineEvent types
│   │   ├── config.py              # Layered settings loader
│   │   ├── effort.py              # low/medium/high effort profiles
│   │   ├── history.py             # SQLite history DB
│   │   │
│   │   ├── agents/
│   │   │   ├── planner.py         # Query plan generation
│   │   │   ├── searcher.py        # Web search (concurrent)
│   │   │   ├── source_ranker.py   # URL tier classification + scoring
│   │   │   ├── fetcher.py         # Async page fetching + HTML strip
│   │   │   ├── extractor.py       # LLM fact extraction
│   │   │   ├── synthesizer.py     # LLM report composition
│   │   │   ├── verifier.py        # Deterministic rule engine
│   │   │   ├── formatter.py       # Follow-up question generation
│   │   │   └── citation_guard.py  # URL validation + strip
│   │   │
│   │   ├── modes/
│   │   │   ├── base.py            # ResearchMode ABC + ModeConfig
│   │   │   ├── general.py         # topic / general
│   │   │   ├── company.py         # company
│   │   │   ├── competitor.py      # competitor
│   │   │   ├── technology.py      # tech / technology
│   │   │   ├── market.py          # market
│   │   │   ├── news.py            # news
│   │   │   └── academic.py        # academic / paper
│   │   │
│   │   ├── llm/
│   │   │   ├── router.py          # Provider chain + rate-limit handling
│   │   │   ├── cost_tracker.py    # Per-stage token + cost tracking
│   │   │   └── providers/
│   │   │       ├── base.py        # LLMProvider ABC + LLMResponse
│   │   │       ├── groq_provider.py
│   │   │       ├── gemini_provider.py
│   │   │       ├── ollama_provider.py
│   │   │       ├── openai_provider.py
│   │   │       └── anthropic_provider.py
│   │   │
│   │   ├── search/
│   │   │   ├── web_search.py      # DuckDuckGo async search
│   │   │   └── source_quality.py  # 13-tier domain classifier
│   │   │
│   │   ├── reports/
│   │   │   ├── schema.py          # All Pydantic models
│   │   │   └── exporter.py        # markdown / json / html export
│   │   │
│   │   ├── ensemble/
│   │   │   ├── orchestrator.py    # Parallel provider execution
│   │   │   ├── claim_extractor.py # Atomic claim extraction per provider
│   │   │   ├── consensus.py       # Jaccard similarity grouping
│   │   │   ├── confidence.py      # Multi-dimensional confidence scoring
│   │   │   ├── disagreement.py    # Conflict detection
│   │   │   ├── verifier.py        # Ensemble-specific verification
│   │   │   └── merger.py          # Multi-provider → single report
│   │   │
│   │   ├── gui/
│   │   │   ├── __main__.py        # Entry point
│   │   │   ├── main_window.py     # 5-page PySide6 main window
│   │   │   ├── pages/
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── research_page.py
│   │   │   │   ├── history_page.py
│   │   │   │   ├── compare_page.py
│   │   │   │   └── settings_page.py
│   │   │   ├── widgets/
│   │   │   │   ├── sidebar.py
│   │   │   │   ├── pipeline_status.py
│   │   │   │   ├── report_viewer.py
│   │   │   │   ├── log_console.py
│   │   │   │   ├── source_table.py
│   │   │   │   ├── card.py
│   │   │   │   └── theme.py
│   │   │   ├── workers/
│   │   │   │   ├── research_worker.py  # QRunnable wrapping pipeline
│   │   │   │   └── log_handler.py      # Python logging → Qt signal
│   │   │   ├── state.py
│   │   │   └── presets.py
│   │   │
│   │   ├── tui/
│   │   │   ├── app.py             # Textual app + bindings
│   │   │   ├── screens/
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── research.py
│   │   │   │   ├── reports.py
│   │   │   │   ├── settings.py
│   │   │   │   └── splash.py
│   │   │   └── widgets/
│   │   │       ├── agent_pipeline.py
│   │   │       ├── effort_selector.py
│   │   │       ├── header.py
│   │   │       ├── logo.py
│   │   │       ├── sidebar.py
│   │   │       └── toast.py
│   │   │
│   │   └── utils/
│   │       ├── logging.py         # Structured logging setup
│   │       ├── retry.py           # Retry + timeout wrapper
│   │       └── rich_ui.py         # Rich table + progress helpers
│   │
│   └── competiq/                  # Legacy package (backward compat)
│
├── frontend/                      # React/TypeScript dashboard (in progress)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── types.ts               # Full TypeScript type definitions
│   │   ├── pages/                 # Dashboard, Workspace, Agents, History, Settings
│   │   ├── api/client.ts          # API client (stub)
│   │   ├── hooks/useWebSocket.ts  # WebSocket hook (stub)
│   │   └── store/index.ts         # Zustand store (stub)
│   └── package.json
│
├── tests/                         # 74 passing tests
├── reports/                       # Generated reports (gitignored)
│   └── .researchhq.db             # SQLite history index
├── assets/                        # Screenshots (see README)
└── evals/                         # Evaluation harness (reserved)
```

---

## Appendix B: Pydantic Model Quick Reference

```python
from researchhq.reports.schema import (
    ResearchReport,    # top-level report
    ResearchPlan,      # planner output
    Fact,              # extractor output
    Section,           # synthesizer output
    RankedSource,      # ranker output
    FetchedPageSummary,
    VerifierNote,
    RuleResult,
    CitationViolation,
    StageCost,
    EnsembleReportSection,
)

# Load a saved report
import json
from pathlib import Path
data = json.loads(Path("reports/company__supabase.json").read_text())
report = ResearchReport.model_validate(data)

print(report.verifier.overall_confidence)   # 0.87
print(len(report.sources))                   # 16
print(report.stage_costs[-1].equivalent_cost_usd)  # 0.012
```

---

*ResearchHQ v0.3.0 — Documentation generated 2026-05-14*
*Built with: Python 3.11 · PySide6 · Textual · Typer · Groq · Gemini · DuckDuckGo*
