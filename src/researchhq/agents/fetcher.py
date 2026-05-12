"""Content fetcher — downloads top-N ranked URLs and reduces them to plain text.

Design choices:
- Concurrency-limited (configurable). Each request has its own timeout.
- Partial-failure tolerant: a fetch error returns an empty page, not a pipeline failure.
- HTML stripping is regex + html.parser based to avoid pulling beautifulsoup4 just for this.
- Per-page text is capped to keep prompt sizes bounded.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from researchhq.search.source_quality import RankedSource
from researchhq.utils.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_FETCH = 8
DEFAULT_PER_PAGE_CHARS = 4000
DEFAULT_CONCURRENCY = 5

USER_AGENT = (
    "Mozilla/5.0 (compatible; researchhq/0.2; +https://github.com/researchhq) "
    "research-agent"
)


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    status: int  # 0 = network/timeout error, otherwise HTTP status
    bytes_in: int
    truncated: bool


class _TextOnly(HTMLParser):
    """Lightweight HTML-to-text. Drops <script>/<style>; collapses whitespace."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "svg"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "svg") and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "div"):
            self._buf.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._buf.append(data)

    def text(self) -> str:
        raw = "".join(self._buf)
        # Collapse runs of whitespace. Keep newline structure light.
        raw = re.sub(r"[\t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"[ ]{2,}", " ", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    p = _TextOnly()
    try:
        p.feed(html)
    except Exception as e:  # noqa: BLE001
        logger.debug("html parser bailed: %s", e)
    return p.text()


async def _fetch_one(
    client: httpx.AsyncClient, src: RankedSource, per_page_chars: int
) -> FetchedPage:
    label = f"fetch[{src.domain or src.url}]"

    async def _do() -> httpx.Response:
        return await client.get(src.url, follow_redirects=True)

    try:
        resp = await with_retry(_do, attempts=2, timeout=DEFAULT_TIMEOUT_S, label=label)
    except Exception as e:  # noqa: BLE001
        logger.info("%s: failed (%s)", label, type(e).__name__)
        return FetchedPage(url=src.url, title=src.title, text="", status=0, bytes_in=0, truncated=False)

    if resp.status_code >= 400:
        return FetchedPage(
            url=src.url, title=src.title, text="", status=resp.status_code,
            bytes_in=len(resp.content), truncated=False,
        )

    ctype = resp.headers.get("content-type", "")
    body = resp.text if "html" in ctype or "text" in ctype or not ctype else ""
    text = html_to_text(body) if "html" in ctype else body
    truncated = len(text) > per_page_chars
    if truncated:
        text = text[:per_page_chars] + " [...truncated]"
    return FetchedPage(
        url=src.url, title=src.title, text=text, status=resp.status_code,
        bytes_in=len(resp.content), truncated=truncated,
    )


async def fetch_top(
    sources: list[RankedSource],
    *,
    max_fetch: int = DEFAULT_MAX_FETCH,
    per_page_chars: int = DEFAULT_PER_PAGE_CHARS,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[FetchedPage]:
    """Fetch up to `max_fetch` highest-ranked sources concurrently. Never raises."""
    if not sources:
        return []
    targets = sources[:max_fetch]
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(DEFAULT_TIMEOUT_S),
    ) as client:

        async def _gated(src: RankedSource) -> FetchedPage:
            async with sem:
                return await _fetch_one(client, src, per_page_chars)

        results = await asyncio.gather(*[_gated(s) for s in targets], return_exceptions=False)

    ok = sum(1 for p in results if p.text)
    logger.info("Fetcher: %d/%d pages returned content", ok, len(results))
    return list(results)
