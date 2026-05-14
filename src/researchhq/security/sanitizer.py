"""Input sanitizer for user-submitted research queries.

Performs three layers of defense:
  1. Length and blank-query rejection (returns HTTP 400)
  2. HTML/script tag stripping (prevents XSS in stored/displayed results)
  3. Prompt injection pattern detection (logs and flags but does NOT block —
     the agent system prompts are independently hardened against injection)

Returns (cleaned_query, warnings_list). Warnings are logged and stored in the
DB but do not stop the pipeline from running.
"""

from __future__ import annotations

import logging
import re
from html import escape

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 4000
MIN_QUERY_LENGTH = 3

# Patterns that indicate attempted prompt injection
# Note: we detect and log, not block — a legitimate user might ask *about*
# prompt injection, and the agent system prompts are independently hardened.
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), "ignore-previous-instructions"),
    (re.compile(r"you\s+are\s+now\s+a", re.I), "persona-override"),
    (re.compile(r"disregard\s+your\s+(system|instructions)", re.I), "disregard-system"),
    (re.compile(r"system\s*:\s*you\s+are", re.I), "system-prompt-injection"),
    (re.compile(r"<\|im_start\|>", re.I), "llm-control-token"),
    (re.compile(r"\[INST\]", re.I), "llama-control-token"),
    (re.compile(r"###\s*human\s*:", re.I), "alpaca-control-token"),
    (re.compile(r"<\s*/?(?:script|iframe|object|embed)\s*>", re.I), "html-script-tag"),
    (re.compile(r"javascript\s*:", re.I), "javascript-url"),
]

# HTML/script tags to strip (broader than injection patterns)
_TAG_STRIP_RE = re.compile(
    r"<\s*/?(?:script|iframe|object|embed|style|link|meta|form|input|button)\b[^>]*>",
    re.I | re.DOTALL,
)


def sanitize_query(query: str) -> tuple[str, list[str]]:
    """Sanitize a user query. Returns (cleaned_text, warnings).

    Raises ValueError for queries that are definitively unacceptable
    (too short, too long). Everything else is cleaned and returned with
    any warnings appended to the list.
    """
    warnings: list[str] = []

    if not query or not query.strip():
        raise ValueError("Query must not be empty.")

    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters "
            f"(got {len(query)})."
        )

    stripped = query.strip()
    if len(stripped) < MIN_QUERY_LENGTH:
        raise ValueError(
            f"Query must be at least {MIN_QUERY_LENGTH} characters long."
        )

    # Strip dangerous HTML tags
    cleaned = _TAG_STRIP_RE.sub("", stripped)

    # Escape remaining HTML entities (prevents XSS in rendered output)
    # We only escape angle brackets and ampersands to keep the query readable
    cleaned = cleaned.replace("<", "&lt;").replace(">", "&gt;")

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Detect prompt injection patterns (log + warn, do not block)
    lower = cleaned.lower()
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(lower):
            msg = f"Potential prompt injection detected ({label})"
            warnings.append(msg)
            logger.warning("Input security: %s — query_preview=%r", msg, cleaned[:80])

    return cleaned, warnings
