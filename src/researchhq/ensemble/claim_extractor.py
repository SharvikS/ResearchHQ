"""Claim extractor — pulls structured claims from provider synthesis outputs.

Two extraction modes:
- Heuristic (default): regex + sentence splitting, no extra LLM call.
- LLM-powered (max_confidence mode): JSON extraction via a fast model,
  falls back to heuristic on parse failure.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(
    r"\b(20\d\d|19\d\d|Q[1-4]\s+20\d\d|"
    r"January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d[\d,.]*\s*[%$BbMmKkTt]?\b")
_URL_RE = re.compile(r"https?://[^\s\)\]]+")


@dataclass
class Claim:
    text: str
    provider: str
    claim_type: str = "fact"   # fact|statistic|date|entity|recommendation|conclusion
    confidence: float = 0.5
    source_mentions: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    has_number: bool = False
    has_date: bool = False


# ── Heuristic helpers ──────────────────────────────────────────────────────────

def _detect_type(text: str) -> str:
    tl = text.lower()
    if any(w in tl for w in ("recommend", "suggest", "should", "consider", "best practice")):
        return "recommendation"
    if any(w in tl for w in ("in conclusion", "in summary", "therefore", "overall,")):
        return "conclusion"
    if _NUMBER_RE.search(text) and any(w in tl for w in ("%", "percent", "million", "billion")):
        return "statistic"
    if _DATE_RE.search(text):
        return "date"
    return "fact"


def _split_sentences(text: str) -> list[str]:
    # Strip markdown syntax
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^[\-\*\•]\s+", "", text, flags=re.MULTILINE)
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if len(s.strip()) > 35]


def extract_claims_heuristic(text: str, provider: str) -> list[Claim]:
    """Extract claims using heuristic sentence analysis — no LLM needed."""
    claims: list[Claim] = []
    for sentence in _split_sentences(text):
        urls = _URL_RE.findall(sentence)
        has_num = bool(_NUMBER_RE.search(sentence))
        has_date = bool(_DATE_RE.search(sentence))
        ctype = _detect_type(sentence)
        conf = 0.50
        if has_num:
            conf += 0.10
        if has_date:
            conf += 0.08
        if urls:
            conf += 0.07
        claims.append(Claim(
            text=sentence,
            provider=provider,
            claim_type=ctype,
            confidence=min(conf, 0.85),
            source_mentions=urls,
            has_number=has_num,
            has_date=has_date,
        ))
    return claims


# ── LLM-powered extraction ─────────────────────────────────────────────────────

_EXTRACT_SYSTEM = (
    "You are a precise claim extractor. Extract every factual claim, statistic, date, "
    "recommendation, and conclusion from the given research text.\n\n"
    'Output a JSON array. Each element must have:\n'
    '  "claim"      : self-contained claim text (1-2 sentences max)\n'
    '  "type"       : one of fact, statistic, date, entity, recommendation, conclusion\n'
    '  "confidence" : float 0.0-1.0 (your estimate of accuracy)\n'
    '  "has_number" : true if contains specific numbers or percentages\n'
    '  "has_date"   : true if mentions a specific date or year\n'
    '  "topics"     : list of 1-3 keyword strings\n\n'
    "Output ONLY the JSON array. No other text."
)


async def extract_claims_llm(
    text: str,
    provider: str,
    router: object,
    *,
    max_tokens: int = 1200,
) -> list[Claim]:
    """LLM-powered extraction. Falls back to heuristic on any failure."""
    prompt = f"Extract all claims from this research text:\n\n{text[:5000]}"
    try:
        resp = await router.complete(  # type: ignore[attr-defined]
            prompt=prompt,
            system=_EXTRACT_SYSTEM,
            max_tokens=max_tokens,
            stage="ensemble_extract",
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        parsed = json.loads(raw)
        claims: list[Claim] = []
        for item in parsed:
            if not isinstance(item, dict) or not item.get("claim"):
                continue
            claims.append(Claim(
                text=str(item["claim"]),
                provider=provider,
                claim_type=str(item.get("type", "fact")),
                confidence=float(item.get("confidence", 0.5)),
                topics=list(item.get("topics", [])),
                has_number=bool(item.get("has_number", False)),
                has_date=bool(item.get("has_date", False)),
            ))
        return claims
    except Exception as e:  # noqa: BLE001
        logger.debug("LLM claim extraction failed for %s: %s — using heuristic", provider, e)
        return extract_claims_heuristic(text, provider)


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_claims(text: str, provider: str) -> list[Claim]:
    """Synchronous heuristic extraction. Use for cheap/balanced modes."""
    return extract_claims_heuristic(text, provider)


async def extract_all_claims(
    results: list,  # list[ProviderResult]
    router: Optional[object] = None,
    *,
    use_llm: bool = False,
    max_tokens: int = 1200,
) -> dict[str, list[Claim]]:
    """Extract claims from all successful provider results in parallel."""
    import asyncio as _asyncio

    async def _one(result) -> tuple[str, list[Claim]]:  # type: ignore[type-arg]
        if use_llm and router is not None:
            claims = await extract_claims_llm(result.text, result.provider, router, max_tokens=max_tokens)
        else:
            claims = extract_claims_heuristic(result.text, result.provider)
        return result.provider, claims

    pairs = await _asyncio.gather(*[_one(r) for r in results])
    return {provider: claims for provider, claims in pairs}
