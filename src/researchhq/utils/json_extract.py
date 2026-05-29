"""Robust extraction of a single JSON object from an LLM response.

LLMs frequently wrap JSON in prose, markdown fences, or emit a trailing example.
A naive ``re.search(r"\\{.*\\}")`` greedily spans from the first ``{`` to the last
``}``, which fails to parse whenever there is more than one object or stray braces
in surrounding prose. This scans for the first ``{`` and uses ``raw_decode`` so the
first well-formed object wins, ignoring whatever follows.
"""

from __future__ import annotations

import json


def extract_json_object(text: str) -> dict:
    """Return the first valid JSON object found in ``text``.

    Tolerates code fences and leading/trailing prose. Raises ``ValueError`` if no
    parseable object is present.
    """
    if not text:
        raise ValueError("empty LLM output")

    # Scanning for "{" and using raw_decode handles markdown fences, leading
    # prose, and trailing examples without any special-casing: the first "{"
    # that decodes to an object wins and whatever follows is ignored.
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(obj, dict):
            return obj
        start = text.find("{", start + 1)

    raise ValueError("no JSON object in LLM output")
