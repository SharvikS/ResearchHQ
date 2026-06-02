"""Run the ResearchHQ API server."""

from __future__ import annotations


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Install the server extra with `pip install -e '.[server]'`.") from exc

    uvicorn.run("researchhq.server.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()

