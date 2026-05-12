"""Render a ResearchReport to markdown / json / html and write to disk."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from researchhq.config import settings
from researchhq.reports.schema import ResearchReport


def _slug(s: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "report"


def _confidence_label(value: float) -> str:
    if value >= 0.75:
        return "High"
    if value >= 0.5:
        return "Medium"
    if value > 0:
        return "Low"
    return "Unknown"


def to_markdown(report: ResearchReport) -> str:
    lines: list[str] = []
    lines.append(f"# Research report — {report.query}")
    lines.append(f"_Mode_: **{report.mode}** · _Generated_: {report.generated_at} · _Provider_: {report.provider_used or 'n/a'}")
    lines.append("")

    # Executive summary is the first synthesized section by convention; otherwise pick the first section.
    exec_section = next((s for s in report.sections if s.heading.lower().startswith("executive")), None)
    if exec_section:
        lines.append("## Executive summary")
        lines.append(exec_section.body.strip())
        lines.append("")

    for s in report.sections:
        if exec_section is not None and s is exec_section:
            continue
        lines.append(f"## {s.heading}")
        lines.append(s.body.strip())
        lines.append("")

    # Confidence
    if report.verifier is not None:
        lines.append("## Confidence score")
        label = _confidence_label(report.verifier.overall_confidence)
        lines.append(f"**Overall confidence:** {report.verifier.overall_confidence:.2f} ({label})")
        if report.verifier.rules:
            lines.append("")
            lines.append("**Rule checks:**")
            for r in report.verifier.rules:
                tag = "PASS" if r.passed else r.severity.upper()
                lines.append(f"- [{tag}] {r.name}: {r.message}")
        if report.verifier.violations:
            lines.append("")
            lines.append(f"**Citation violations ({len(report.verifier.violations)}):**")
            for v in report.verifier.violations[:20]:
                tail = f" url={v.url}" if v.url else ""
                lines.append(f"- {v.kind} @ {v.location[:60]}: {v.detail}{tail}")
        if report.verifier.notes:
            lines.append("")
            lines.append("**Notes:**")
            for n in report.verifier.notes:
                lines.append(f"- {n}")
        lines.append("")

    # Sources
    lines.append("## Sources")
    if report.sources:
        for i, s in enumerate(report.sources, 1):
            lines.append(f"{i}. [{s.title}]({s.url}) — _{s.tier.value}_ (score {s.score})")
    else:
        lines.append("_No sources retained after ranking._")
    lines.append("")

    # Next questions
    if report.next_questions:
        lines.append("## Recommended next research questions")
        for q in report.next_questions:
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def to_json(report: ResearchReport) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False)


def to_html(report: ResearchReport) -> str:
    md = to_markdown(report)
    # Lightweight markdown -> HTML; intentionally minimal to avoid a heavy dependency.
    body_lines: list[str] = []
    in_list = False
    for line in md.splitlines():
        if line.startswith("# "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_list:
                body_lines.append("<ul>")
                in_list = True
            body_lines.append(f"<li>{escape(line[2:])}</li>")
        elif not line.strip():
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append("")
        else:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<p>{escape(line)}</p>")
    if in_list:
        body_lines.append("</ul>")
    body = "\n".join(body_lines)
    title = escape(f"Research report — {report.query}")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:780px;margin:2rem auto;padding:0 1rem;line-height:1.55}"
        "h1{border-bottom:1px solid #ddd;padding-bottom:.3rem}h2{margin-top:1.5rem}"
        "code{background:#f4f4f4;padding:.1rem .3rem;border-radius:3px}</style></head>"
        f"<body>{body}</body></html>"
    )


_FORMATS = {
    "markdown": (to_markdown, ".md"),
    "md": (to_markdown, ".md"),
    "json": (to_json, ".json"),
    "html": (to_html, ".html"),
}


def render(report: ResearchReport, fmt: str) -> str:
    fn, _ = _FORMATS[fmt.lower()]
    return fn(report)


def save(
    report: ResearchReport,
    fmt: str | None = None,
    folder: str | None = None,
    workspace: str = "default",
) -> Path:
    fmt = (fmt or settings.default_format).lower()
    if fmt not in _FORMATS:
        raise ValueError(f"Unsupported format '{fmt}'. Choose one of {list(_FORMATS)}")
    fn, ext = _FORMATS[fmt]
    out_dir = Path(folder or settings.output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{report.mode}__{_slug(report.query)}{ext}"
    path = out_dir / name
    path.write_text(fn(report), encoding="utf-8")

    # Always also write the JSON form (small) so the history index has a stable
    # JSON to reference. It's fine for fmt==json (no-op overwrite).
    json_path = out_dir / f"{report.mode}__{_slug(report.query)}.json"
    if fmt != "json":
        json_path.write_text(to_json(report), encoding="utf-8")

    # Index into history DB. Failures here must not break the save.
    try:
        from researchhq.history import index_report_dict
        index_report_dict(json_path, report.model_dump(mode="json"), workspace=workspace)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("history index skipped")

    return path
