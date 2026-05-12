"""Entry point for the `researchhq` and `rhq` console scripts.

Supports a few flags:
  --quick "<query>"   land directly on Research and auto-run the query
  --workspace <name>  set the active workspace
  --dashboard         skip splash, jump straight to the dashboard
  --no-tui            forward to the classic CLI (alias of `research --help`)
  -h/--help           show usage
"""

from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="researchhq",
        description="ResearchHQ — premium interactive terminal workspace.",
    )
    p.add_argument("--quick", metavar="QUERY",
                   help="Land on the Research screen and auto-launch this query.")
    p.add_argument("--workspace", default="default",
                   help="Active workspace name (default: 'default').")
    p.add_argument("--dashboard", action="store_true",
                   help="Skip the splash and open the dashboard immediately.")
    p.add_argument("--no-tui", action="store_true",
                   help="Bypass the TUI and use the classic CLI instead.")
    return p


def main() -> None:
    args, unknown = _build_parser().parse_known_args()

    # --no-tui: forward to the classic CLI. Sub-args follow after --.
    if args.no_tui:
        from researchhq.cli import app as cli_app
        sys.argv = ["research", *unknown]
        cli_app()
        return

    try:
        from researchhq.tui.app import ResearchHQApp
    except ModuleNotFoundError as e:
        if "textual" in str(e).lower():
            print("ResearchHQ TUI requires the 'textual' package.\n"
                  "Install it with:\n"
                  "    pip install -e \".[tui]\"\n"
                  "Or run the classic CLI:\n"
                  "    researchhq-cli research topic \"your query\"")
            sys.exit(2)
        raise

    app = ResearchHQApp(initial_query=args.quick, workspace=args.workspace)
    if args.dashboard and args.quick is None:
        # Tell the splash to dismiss immediately.
        app._initial_query = None  # type: ignore[attr-defined]
    app.run()


if __name__ == "__main__":
    main()
