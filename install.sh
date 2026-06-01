#!/bin/sh
# ResearchHQ — one-command installer bootstrap (macOS / Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/SharvikS/ResearchHQ/master/install.sh | sh
#
# This thin wrapper does three things and then hands off to the real
# (interactive) Python installer:
#   1. Locate a Python 3.11+ interpreter (python3, then python).
#   2. Download install.py robustly (curl or wget, with retries + timeouts).
#   3. Run it with the real terminal attached so its TUI is fully interactive.
#
# Overrides (handy for testing a branch before it is merged to master):
#   RHQ_INSTALL_REF=my-branch        sh install.sh   # pick a git ref
#   RESEARCHHQ_INSTALL_URL=<raw url> sh install.sh   # full URL override
#
# POSIX sh only — no bashisms — so it runs under dash/ash/busybox too.
set -eu

REPO="SharvikS/ResearchHQ"
REF="${RHQ_INSTALL_REF:-master}"
INSTALLER_URL="${RESEARCHHQ_INSTALL_URL:-https://raw.githubusercontent.com/${REPO}/${REF}/install.py}"

# ── Colours (only when stderr is a terminal) ────────────────────────────────
if [ -t 2 ]; then
  BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; RED="$(printf '\033[31m')"
  GRN="$(printf '\033[32m')"; CYN="$(printf '\033[36m')"; RST="$(printf '\033[0m')"
else
  BOLD=""; DIM=""; RED=""; GRN=""; CYN=""; RST=""
fi

say()  { printf '%s\n' "$*" >&2; }
info() { printf '%s%s%s %s\n' "$DIM" "·" "$RST" "$*" >&2; }
ok()   { printf '%s%s%s %s\n' "$GRN" "✓" "$RST" "$*" >&2; }
err()  { printf '%s%s%s %s\n' "$RED" "✗" "$RST" "$*" >&2; }

say ""
say "  ${BOLD}${CYN}ResearchHQ${RST} ${DIM}— multi-agent research workstation${RST}"
say ""

# ── 1. Locate a suitable Python ─────────────────────────────────────────────
# We require >= 3.11 and verify it by actually running the interpreter, so a
# stale shim or an old `python` on PATH can never slip through.
find_python() {
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" - >/dev/null 2>&1 <<'PYEOF'
import sys
raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)
PYEOF
      then
        printf '%s' "$cand"
        return 0
      fi
    fi
  done
  return 1
}

PY="$(find_python || true)"
if [ -z "${PY:-}" ]; then
  err "Python 3.11+ is required but was not found on your PATH."
  say ""
  say "  Install Python, then re-run this command:"
  say "    ${DIM}macOS  ${RST} brew install python@3.12"
  say "    ${DIM}Debian ${RST} sudo apt-get install -y python3"
  say "    ${DIM}Fedora ${RST} sudo dnf install -y python3"
  say "    ${DIM}Arch   ${RST} sudo pacman -S python"
  say "    ${DIM}other  ${RST} https://www.python.org/downloads/"
  exit 1
fi
ok "Using $("$PY" -c 'import sys;print("Python %d.%d.%d"%sys.version_info[:3])' 2>/dev/null || echo "$PY")"

# ── 2. Download the installer to a temp file ────────────────────────────────
TMP="$(mktemp 2>/dev/null || mktemp -t rhq_install)"
# Give it a .py suffix so any error message / editor opens it sensibly.
TMP_PY="${TMP}.py"
mv -f "$TMP" "$TMP_PY" 2>/dev/null || TMP_PY="$TMP"
cleanup() { rm -f "$TMP" "$TMP_PY" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

download() {
  # download <url> <out>  — prefers curl, falls back to wget.
  _url="$1"; _out="$2"
  if command -v curl >/dev/null 2>&1; then
    # -f: fail (and write nothing) on HTTP >= 400 so an error page can never be
    #     piped into Python.  -sS: quiet but still show real errors.
    curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 30 "$_url" -o "$_out"
  elif command -v wget >/dev/null 2>&1; then
    wget -q --tries=3 --timeout=30 -O "$_out" "$_url"
  else
    err "Neither curl nor wget is available — cannot download the installer."
    return 127
  fi
}

info "Downloading installer…"
if ! download "$INSTALLER_URL" "$TMP_PY"; then
  err "Download failed: $INSTALLER_URL"
  say "  Check your internet connection and try again."
  exit 1
fi
# Sanity-check that we actually got Python source, not a stray HTML error page.
if ! grep -q "ResearchHQ" "$TMP_PY" 2>/dev/null; then
  err "Downloaded file does not look like the installer (got an error page?)."
  say "  URL: $INSTALLER_URL"
  exit 1
fi

# ── 3. Run it interactively ─────────────────────────────────────────────────
# When this script is itself piped through `curl … | sh`, our stdin IS the
# pipe — so we must reconnect the installer to the real terminal, otherwise it
# would see EOF on every prompt.  /dev/tty is that real terminal.
set +e
if [ -r /dev/tty ]; then
  "$PY" "$TMP_PY" </dev/tty
else
  # No controlling terminal (CI, container build, …) — run anyway; install.py
  # degrades gracefully and treats EOF as "skip/accept default".
  "$PY" "$TMP_PY"
fi
rc=$?
set -e
exit "$rc"
