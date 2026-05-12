from researchhq.reports.exporter import to_html, to_json, to_markdown
from researchhq.reports.schema import (
    Fact,
    ResearchPlan,
    ResearchReport,
    Section,
    VerifierNote,
)
from researchhq.search.source_quality import RankedSource, SourceTier


def _sample_report() -> ResearchReport:
    return ResearchReport(
        mode="topic",
        query="AI agents in cybersecurity",
        plan=ResearchPlan(queries=["a", "b"], rationale="r"),
        sources=[
            RankedSource(
                url="https://arxiv.org/abs/1234.5678",
                title="Paper",
                snippet="abs",
                tier=SourceTier.ACADEMIC,
                score=10,
                domain="arxiv.org",
            ),
        ],
        facts=[Fact(claim="X", evidence_urls=["https://arxiv.org/abs/1234.5678"], confidence=0.9)],
        sections=[
            Section(heading="Executive summary", body="One-line summary."),
            Section(heading="Key findings", body="- Finding A\n- Finding B"),
        ],
        verifier=VerifierNote(overall_confidence=0.78, notes=["sample note"]),
        next_questions=["What's next?"],
        provider_used="groq",
    )


def test_markdown_contains_all_required_sections():
    md = to_markdown(_sample_report())
    for required in (
        "# Research report",
        "## Executive summary",
        "## Key findings",
        "## Confidence score",
        "## Sources",
        "## Recommended next research questions",
    ):
        assert required in md, f"missing section: {required!r}\n--- markdown ---\n{md}"


def test_markdown_includes_source_link():
    md = to_markdown(_sample_report())
    assert "[Paper](https://arxiv.org/abs/1234.5678)" in md


def test_json_round_trips():
    js = to_json(_sample_report())
    assert "AI agents in cybersecurity" in js
    assert "arxiv.org" in js


def test_html_contains_headings_and_escapes():
    html = to_html(_sample_report())
    assert "<h1>" in html
    assert "<h2>Executive summary</h2>" in html
    assert "<title>" in html
