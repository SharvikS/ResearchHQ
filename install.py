#!/usr/bin/env python3
"""ResearchHQ — one-command interactive installer.

Run from anywhere:
  python install.py

Or pipe from GitHub (Linux/Mac):
  curl -sSL https://raw.githubusercontent.com/SharvikS/PROJECT_NAME/master/install.py | python3

Windows (PowerShell):
  irm https://raw.githubusercontent.com/SharvikS/PROJECT_NAME/master/install.py | python
"""

from __future__ import annotations

import getpass
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from dataclasses import field as _dc_field
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: when piped (curl|python / irm|python), stdin is the script so
# input() returns EOF immediately.  Fix: download to a temp file and re-exec
# with the real terminal as stdin.
# ---------------------------------------------------------------------------

_INSTALLER_URL = "https://raw.githubusercontent.com/SharvikS/ResearchHQ/master/install.py"


def _bootstrap_interactive() -> None:
    if sys.stdin.isatty():
        return  # Already running interactively — nothing to do

    print("Downloading installer for interactive setup...")
    tmp = tempfile.mktemp(suffix="_rhq_install.py")
    try:
        urllib.request.urlretrieve(_INSTALLER_URL, tmp)
    except Exception as e:
        print(f"Download failed: {e}")
        sys.exit(1)

    try:
        if sys.platform == "win32":
            con = open("CONIN$")
        else:
            con = open("/dev/tty")
        result = subprocess.run([sys.executable, tmp], stdin=con)
        con.close()
    except Exception as e:
        print(f"Could not attach terminal: {e}")
        print(f"Run directly instead:  python {tmp}")
        sys.exit(1)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    sys.exit(result.returncode)


_bootstrap_interactive()

# ---------------------------------------------------------------------------
# Encoding: switch Windows console to UTF-8 so Unicode renders correctly.
# ---------------------------------------------------------------------------

def _setup_encoding() -> None:
    if sys.platform == "win32":
        os.system("chcp 65001 > nul 2>&1")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except AttributeError:
        pass

_setup_encoding()

# ---------------------------------------------------------------------------
# ANSI colours (disabled automatically on Windows without ANSI support)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty() and (
    platform.system() != "Windows"
    or os.environ.get("WT_SESSION")  # Windows Terminal
    or os.environ.get("TERM_PROGRAM")
)


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t: str) -> str:       return _c("1", t)
def dim(t: str) -> str:        return _c("2", t)
def green(t: str) -> str:      return _c("32", t)
def yellow(t: str) -> str:     return _c("33", t)
def cyan(t: str) -> str:       return _c("36", t)
def red(t: str) -> str:        return _c("31", t)
def magenta(t: str) -> str:    return _c("35", t)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GITHUB_REPO = "https://github.com/SharvikS/ResearchHQ"
INSTALL_DIR = Path.home() / ".researchhq"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kwargs)


def _check(cmd: list[str]) -> bool:
    try:
        _run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        answer = input(f"  {prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return answer or default


def _ask_secret(prompt: str) -> str:
    try:
        return getpass.getpass(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def _ask_yn(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = _ask(f"{prompt} ({hint})", "")
    if not raw:
        return default
    return raw.lower().startswith("y")


def _section(title: str) -> None:
    print()
    print(bold(cyan(f"  ── {title} ")))


def _ok(msg: str) -> None:
    print(f"  {green('✓')} {msg}")


def _warn(msg: str) -> None:
    print(f"  {yellow('⚠')} {msg}")


def _err(msg: str) -> None:
    print(f"  {red('✗')} {msg}")


def _info(msg: str) -> None:
    print(f"  {dim('·')} {msg}")


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = r"""
  ██████╗ ███████╗███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗██╗  ██╗ ██████╗
  ██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║██║  ██║██╔═══██╗
  ██████╔╝█████╗  ███████╗█████╗  ███████║██████╔╝██║     ███████║███████║██║   ██║
  ██╔══██╗██╔══╝  ╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║██╔══██║██║▄▄ ██║
  ██║  ██║███████╗███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║██║  ██║╚██████╔╝
  ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚══▀▀═╝
"""


def print_banner() -> None:
    print(magenta(BANNER))
    print(f"  {bold('Premium multi-agent research workstation')}")
    print(f"  {dim('github.com/SharvikS/ResearchHQ')}")
    print()


# ---------------------------------------------------------------------------
# Step 1 — Prerequisites
# ---------------------------------------------------------------------------

def check_python() -> None:
    _section("Checking prerequisites")
    v = sys.version_info
    if v < (3, 11):
        _err(f"Python 3.11+ required  (found {v.major}.{v.minor})")
        sys.exit(1)
    _ok(f"Python {v.major}.{v.minor}.{v.micro}")


def detect_managers() -> dict[str, bool]:
    managers = {
        "uv":    shutil.which("uv") is not None,
        "pipx":  shutil.which("pipx") is not None,
        "pip":   shutil.which("pip") is not None or shutil.which("pip3") is not None,
    }
    if managers["uv"]:
        _ok("uv detected  (will be used as primary installer)")
    elif managers["pipx"]:
        _ok("pipx detected  (recommended for CLI tools)")
    elif managers["pip"]:
        _ok("pip detected")
        _warn("Consider installing pipx for isolated installs: pip install pipx")
    else:
        _err("No package manager found (pip / pipx / uv). Install one and retry.")
        sys.exit(1)
    return managers


# ---------------------------------------------------------------------------
# Step 2 — Install source & extras
# ---------------------------------------------------------------------------

def choose_source() -> str:
    _section("Installation source")
    print(f"  {dim('1)')} {bold('GitHub')}  — latest master from {GITHUB_REPO}")
    print(f"  {dim('2)')} {bold('Local')}   — install from this cloned directory")
    choice = _ask("Choice", "1")
    if choice == "2":
        local = Path(__file__).parent.resolve()
        _info(f"Using local path: {local}")
        return str(local)
    return f"git+{GITHUB_REPO}.git"


def choose_extras() -> list[str]:
    _section("Optional features")
    extras: list[str] = []

    extras.append("tui")   # always include — needed for rhq / researchhq commands
    _ok("TUI  (terminal workstation — included by default)")

    if _ask_yn("Install GUI desktop app?  (requires PySide6 ~200 MB)", default=False):
        extras.append("gui")
        _ok("GUI")

    if _ask_yn("Enable Anthropic / Claude provider?", default=False):
        extras.append("anthropic")
        _ok("Anthropic")

    if _ask_yn("Enable OpenAI / GPT provider?", default=False):
        extras.append("openai")
        _ok("OpenAI")

    return extras


# ---------------------------------------------------------------------------
# Step 3 — Run install
# ---------------------------------------------------------------------------

PACKAGE_NAME = "researchhq"


def run_install(source: str, extras: list[str], managers: dict[str, bool]) -> None:
    _section("Installing ResearchHQ")

    is_local = not source.startswith("git+")
    extras_str = ",".join(extras)

    # Build a PEP 508 spec that every modern tool understands
    if is_local:
        # e.g.  /path/to/repo[tui,anthropic]
        local_spec = f".[{extras_str}]" if extras_str else "."
    else:
        # e.g.  researchhq[tui] @ git+https://github.com/SharvikS/ResearchHQ.git
        pkg = f"{PACKAGE_NAME}[{extras_str}]" if extras_str else PACKAGE_NAME
        remote_spec = f"{pkg} @ {source}"

    pip = shutil.which("pip3") or shutil.which("pip")

    if is_local:
        # Local installs: always use pip -e (works universally)
        cmd = [pip, "install", "-e", local_spec]
    elif managers["pipx"]:
        # pipx gives an isolated env + automatic PATH wiring — best for CLI tools
        cmd = ["pipx", "install", remote_spec, "--force"]
    elif managers["uv"]:
        # uv tool install with PEP 508 spec
        cmd = ["uv", "tool", "install", remote_spec]
    else:
        # Plain pip --user as last resort
        cmd = [pip, "install", "--user", remote_spec]

    _info(f"Running: {' '.join(cmd)}")
    print()
    if _game_capable():
        returncode = run_game_overlay(cmd)
    else:
        result = _run(cmd)
        returncode = result.returncode
    print()
    if returncode != 0:
        _err("Installation failed. Run with: research doctor  for details.")
        sys.exit(1)
    _ok("Package installed successfully")


# ---------------------------------------------------------------------------
# Step 4 — Collect API keys
# ---------------------------------------------------------------------------

def collect_api_keys() -> dict[str, str]:
    _section("API Keys")
    print(f"  {dim('Keys are stored in')} {bold(str(INSTALL_DIR / '.env'))}")
    print(f"  {dim('Press Enter to skip any key.')}")
    print()

    keys: dict[str, str] = {}

    # Groq (free tier, recommended)
    print(f"  {bold('Groq')}  {dim('(free 14 400 req/day — recommended primary)')} "
          f"{dim('→ console.groq.com/keys')}")
    k = _ask_secret("GROQ_API_KEY")
    if k:
        keys["GROQ_API_KEY"] = k
        _ok("Groq key set")
    else:
        _warn("Groq key skipped")

    # Gemini
    print()
    print(f"  {bold('Google Gemini')}  {dim('(free tier available)')} "
          f"{dim('→ aistudio.google.com/apikey')}")
    k = _ask_secret("GEMINI_API_KEY")
    if k:
        keys["GEMINI_API_KEY"] = k
        _ok("Gemini key set")
    else:
        _info("Gemini key skipped")

    # Anthropic (only if extra was chosen)
    if "ANTHROPIC_API_KEY" not in keys:
        print()
        print(f"  {bold('Anthropic / Claude')}  {dim('→ console.anthropic.com/keys')}")
        k = _ask_secret("ANTHROPIC_API_KEY")
        if k:
            keys["ANTHROPIC_API_KEY"] = k
            _ok("Anthropic key set")
        else:
            _info("Anthropic key skipped")

    # OpenAI
    print()
    print(f"  {bold('OpenAI / GPT')}  {dim('→ platform.openai.com/api-keys')}")
    k = _ask_secret("OPENAI_API_KEY")
    if k:
        keys["OPENAI_API_KEY"] = k
        _ok("OpenAI key set")
    else:
        _info("OpenAI key skipped")

    # Ollama
    print()
    if _ask_yn("Using local Ollama?", default=False):
        host = _ask("OLLAMA_HOST", "http://localhost:11434")
        keys["OLLAMA_HOST"] = host
        _ok(f"Ollama host: {host}")

    if not keys.get("GROQ_API_KEY") and not keys.get("GEMINI_API_KEY") and "OLLAMA_HOST" not in keys:
        _warn("No provider configured — add at least one key or Ollama before using the tool.")

    return keys


# ---------------------------------------------------------------------------
# Step 5 — Optional: configure provider & models
# ---------------------------------------------------------------------------

def configure_provider(keys: dict[str, str]) -> dict[str, str]:
    _section("Default provider")

    available: list[str] = []
    if keys.get("GROQ_API_KEY"):
        available.append("groq")
    if keys.get("GEMINI_API_KEY"):
        available.append("gemini")
    if keys.get("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    if keys.get("OPENAI_API_KEY"):
        available.append("openai")
    if keys.get("OLLAMA_HOST"):
        available.append("ollama")

    if not available:
        return {}

    print(f"  Available: {', '.join(available)}")
    default = available[0]
    provider = _ask("Default provider", default)
    if provider not in available:
        _warn(f"'{provider}' not configured — using '{default}' instead")
        provider = default

    cfg: dict[str, str] = {"default_provider": provider}
    return cfg


# ---------------------------------------------------------------------------
# Step 6 — Write config files
# ---------------------------------------------------------------------------

def write_config(keys: dict[str, str], provider_cfg: dict[str, str]) -> None:
    _section("Writing configuration")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    # .env
    env_path = INSTALL_DIR / ".env"
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    existing.update(keys)

    lines = [
        "# ResearchHQ — global API keys",
        "# Generated by install.py — edit freely",
        "",
    ]
    for k, v in existing.items():
        lines.append(f"{k}={v}")
    lines.append("")

    env_path.write_text("\n".join(lines), encoding="utf-8")
    _ok(f"Keys written to {env_path}")

    # config.yaml (only if provider was chosen)
    if provider_cfg:
        try:
            import yaml  # type: ignore[import]
            cfg_path = INSTALL_DIR / "config.yaml"
            existing_yaml: dict = {}
            if cfg_path.exists():
                with cfg_path.open("r", encoding="utf-8") as f:
                    existing_yaml = yaml.safe_load(f) or {}
            existing_yaml.setdefault("provider", {})["default"] = provider_cfg["default_provider"]
            with cfg_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(existing_yaml, f, sort_keys=False, default_flow_style=False)
            _ok(f"Provider config written to {cfg_path}")
        except ImportError:
            _info("PyYAML not available yet — provider config will use defaults")


# ---------------------------------------------------------------------------
# Step 7 — Verify
# ---------------------------------------------------------------------------

def verify_install() -> None:
    _section("Verifying installation")
    for cmd_name in ("research", "researchhq", "rhq"):
        if shutil.which(cmd_name):
            _ok(f"Command '{cmd_name}' is on PATH")
            break
    else:
        _warn("Commands not found on PATH yet.")
        _info("If using pip --user, add ~/.local/bin to your PATH:")
        _info("  export PATH=\"$HOME/.local/bin:$PATH\"  (add to ~/.bashrc or ~/.zshrc)")
        _info("If using pipx, run: pipx ensurepath")
        return

    if shutil.which("research"):
        result = _run(
            ["research", "doctor"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            _ok("Health check passed")
        else:
            _warn("Health check reported issues — see output with: research doctor")


# ---------------------------------------------------------------------------
# Step 8 — Success banner
# ---------------------------------------------------------------------------

def print_success() -> None:
    print()
    print(bold(green("  ══════════════════════════════════════════")))
    print(bold(green("    ResearchHQ installed successfully! 🎉   ")))
    print(bold(green("  ══════════════════════════════════════════")))
    print()
    print(f"  {bold('Quick start:')}")
    print()
    _topic = dim('"your topic"')
    print(f"    {cyan('research')} {_topic}         # one-shot research report")
    print(f"    {cyan('rhq')}                         # interactive TUI workstation")
    print(f"    {cyan('research doctor')}              # check provider connectivity")
    print(f"    {cyan('research --help')}              # full CLI reference")
    print()
    print(f"  {bold('Config:')}")
    print(f"    {dim(str(INSTALL_DIR / '.env'))}          # API keys")
    print(f"    {dim(str(INSTALL_DIR / 'config.yaml'))}   # provider & model settings")
    print()
    print(f"  {bold('Docs:')}  {dim(GITHUB_REPO)}")
    print()


# =============================================================================
# MINI-GAME: Research Runner
# A non-blocking terminal game that plays while the package installs.
# =============================================================================

_FPS      = 15
_FRAME_T  = 1.0 / _FPS
_GRAVITY  = 0.75    # fall speed per tick
_JUMP_VY  = 4.2     # initial jump velocity
_PX       = 4       # player fixed column (0-indexed inside play area)
_PW       = 3       # player width in chars
_PH       = 2       # player height in rows (body + head)
_PLAY_H   = 10      # play area row count (gives room for tall blocks + jumps)
_MIN_COLS = 64      # minimum terminal width to enable game


# ── Terminal capability ───────────────────────────────────────────────────────

def _win_enable_ansi() -> bool:
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h   = k32.GetStdHandle(-11)
        m   = ctypes.c_ulong()
        k32.GetConsoleMode(h, ctypes.byref(m))
        k32.SetConsoleMode(h, m.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return True
    except Exception:
        return False


def _game_capable() -> bool:
    if not (sys.stdout.isatty() and sys.stdin.isatty()):
        return False
    cols, rows = shutil.get_terminal_size(fallback=(0, 0))
    if cols < _MIN_COLS or rows < _PLAY_H + 6:
        return False
    if sys.platform == "win32":
        return _win_enable_ansi()
    return os.environ.get("TERM", "dumb") not in ("", "dumb")


# ── Non-blocking input ────────────────────────────────────────────────────────

def _read_key() -> str | None:
    """Return key name or None without blocking."""
    if sys.platform == "win32":
        import msvcrt
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getch()
        if ch in (b"\xe0", b"\x00"):
            ext = msvcrt.getch()
            return {b"H": "UP", b"P": "DOWN"}.get(ext)
        if ch == b" ":    return "SPACE"
        if ch == b"\r":   return "ENTER"
        if ch == b"\x1b": return "ESC"
        if ch == b"\x03": return "CTRL_C"
        s = ch.decode("ascii", errors="ignore").upper()
        return s if s else None
    # ── Unix ──────────────────────────────────────────────────────────────
    import select, tty, termios
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        rr, _, _ = select.select([fd], [], [], 0)
        if not rr:
            return None
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            rr2, _, _ = select.select([fd], [], [], 0.02)
            if rr2:
                seq = os.read(fd, 3)
                if b"A" in seq: return "UP"
                if b"B" in seq: return "DOWN"
            return "ESC"
        if ch == b" ":    return "SPACE"
        if ch == b"\x03": return "CTRL_C"
        if ch in (b"\r", b"\n"): return "ENTER"
        s = ch.decode("ascii", errors="ignore").upper()
        return s if s else None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


# ── Game data ─────────────────────────────────────────────────────────────────

@dataclass
class _Entity:
    x:      float
    row:    int    # bottom row (0 = ground level)
    kind:   str    # 'block' | 'spike' | 'source' | 'shield' | 'boost'
    height: int = 1   # rows tall  (blocks: 1-3, others: 1)
    width:  int = 3   # chars wide


@dataclass
class _GS:
    py:       float = 0.0
    pvy:      float = 0.0
    shield:   int   = 0      # frames of invincibility remaining
    boost:    int   = 0      # frames of 2x score remaining
    lives:    int   = 3
    score:    int   = 0
    speed:    float = 1.2
    spawn_cd: int   = 28
    frame:    int   = 0
    paused:   bool  = False
    dead:     bool  = False
    entities: list  = _dc_field(default_factory=list)


# ── Game logic ────────────────────────────────────────────────────────────────

def _jump(gs: _GS) -> None:
    if gs.py < 0.05 and not gs.dead and not gs.paused:
        gs.pvy = _JUMP_VY


def _tick(gs: _GS, gw: int) -> None:
    if gs.paused or gs.dead:
        return
    gs.frame += 1
    gs.score += 2 if gs.boost > 0 else 1
    gs.speed  = 1.2 + gs.frame * 0.00022
    if gs.shield > 0: gs.shield -= 1
    if gs.boost  > 0: gs.boost  -= 1

    gs.pvy -= _GRAVITY
    gs.py  += gs.pvy
    if gs.py <= 0.0:
        gs.py, gs.pvy = 0.0, 0.0
    gs.py = min(gs.py, float(_PLAY_H - _PH))   # ceiling: keep head inside

    gs.entities = [e for e in gs.entities if e.x > -6]
    for e in gs.entities:
        e.x -= gs.speed

    gs.spawn_cd -= 1
    if gs.spawn_cd <= 0:
        _spawn(gs, gw)
        gs.spawn_cd = max(18, 50 - gs.frame // 150)

    _collide(gs)


def _spawn(gs: _GS, gw: int) -> None:
    r = random.random()
    x = float(gw - 1)
    if r < 0.50:
        # solid block obstacle — height 1, 2, or 3 rows
        h = random.choices([1, 2, 3], weights=[40, 40, 20])[0]
        gs.entities.append(_Entity(x=x, row=0, height=h, width=3, kind="block"))
    elif r < 0.62:
        # fast narrow spike on the ground
        gs.entities.append(_Entity(x=x, row=0, height=1, width=1, kind="spike"))
    elif r < 0.78:
        # source coin — floats at mid-air heights
        gs.entities.append(_Entity(x=x, row=random.randint(1, 4), height=1, width=3, kind="source"))
    elif r < 0.90:
        # boost powerup — floats higher
        gs.entities.append(_Entity(x=x, row=random.randint(2, 5), height=1, width=3, kind="boost"))
    else:
        # shield powerup
        gs.entities.append(_Entity(x=x, row=random.randint(2, 5), height=1, width=3, kind="shield"))


def _collide(gs: _GS) -> None:
    # Player occupies columns _PX.._PX+_PW-1 and rows round(py)..round(py)+_PH-1
    p_lo_col = _PX
    p_hi_col = _PX + _PW - 1
    p_lo_row = round(gs.py)
    p_hi_row = p_lo_row + _PH - 1

    for e in list(gs.entities):
        e_lo_col = round(e.x)
        e_hi_col = e_lo_col + e.width - 1
        e_lo_row = e.row
        e_hi_row = e.row + e.height - 1

        # AABB check
        if e_hi_col < p_lo_col or e_lo_col > p_hi_col:
            continue
        if e_hi_row < p_lo_row or e_lo_row > p_hi_row:
            continue

        if e.kind in ("block", "spike"):
            gs.entities.remove(e)
            if gs.shield > 0:
                gs.shield = max(0, gs.shield - _FPS)
            else:
                gs.lives -= 1
                gs.dead   = gs.lives <= 0
        elif e.kind == "source":
            gs.entities.remove(e)
            gs.score += 50 * (2 if gs.boost > 0 else 1)
        elif e.kind == "shield":
            gs.entities.remove(e)
            gs.shield = _FPS * 4
        elif e.kind == "boost":
            gs.entities.remove(e)
            gs.boost = _FPS * 5


# ── Renderer ──────────────────────────────────────────────────────────────────

# Player animation frames  (body, head)
# frame index alternates every 4 ticks on the ground, fixed when airborne
_PLAYER_RUN = [("/R\\", " o "), ("\\R/", " o ")]
_PLAYER_AIR = ("[R]",          "\\o/")
_PLAYER_DEAD = ("xxx",         " X ")

# Entity visuals  (char-string, ANSI colour code)
_ENTITY_VIS = {
    "block":  ("█",   "31"),   # red solid blocks
    "spike":  ("/!\\","91"),   # bright-red spike
    "source": ("($)", "33"),   # yellow coin
    "shield": ("[C]", "36"),   # cyan shield
    "boost":  ("[+]", "32"),   # green boost
}


def _draw(gs: _GS, info: dict, notify: str, top: int) -> None:
    """
    Render one game frame using ANSI cursor positioning (no full-clear flicker).

    top  — 1-indexed terminal row of the header border line.
    Total height = _PLAY_H + 5  (header + play + ground + status + progress + footer).
    """
    B = "\033[0m"
    cols, _ = shutil.get_terminal_size(fallback=(80, 24))
    gw = min(cols - 4, 100)    # inner play width (between the two │ chars)

    r_header = top
    r_playN  = top + _PLAY_H   # terminal row of the ground-level play row
    r_ground = r_playN + 1
    r_status = r_playN + 2
    r_prog   = r_playN + 3
    r_footer = r_playN + 4

    def G(r: int, c: int = 1) -> str:
        return f"\033[{r};{c}H\033[2K"

    out: list[str] = []

    # ── header ─────────────────────────────────────────────────────────────
    lives_s = "H" * gs.lives + "." * (3 - gs.lives)
    score_s = f"Score:{gs.score:07d}"
    title   = "RESEARCH RUNNER"
    hpad    = max(0, gw - len(title) - len(lives_s) - len(score_s) - 5)
    header  = f" {title} {' ' * hpad}{lives_s}  {score_s} "
    out.append(G(r_header) + f"┌{header[:gw]}┐")

    # ── play area (clear each row; entities/player drawn with cursor below) ─
    for r in range(top + 1, r_playN + 1):
        out.append(G(r) + f"│{' ' * gw}│")

    # ── ground separator ───────────────────────────────────────────────────
    out.append(G(r_ground) + f"│{'═' * gw}│")

    # ── status / controls ──────────────────────────────────────────────────
    ctrl  = "SPACE/UP:Jump  P:Pause  Q:Quit"
    extra = notify
    if not extra:
        if gs.paused:       extra = "-- PAUSED --"
        elif gs.dead:       extra = "GAME OVER | SPACE: Restart"
        elif gs.shield > 0: extra = "[SHIELD]"
        elif gs.boost  > 0: extra = "[2x SCORE]"
    spad  = max(0, gw - len(ctrl) - len(extra) - 2)
    out.append(G(r_status) + f"│ {ctrl}{' ' * spad}{extra} │"[:gw + 2] + "│")

    # ── install progress bar ────────────────────────────────────────────────
    prog   = info.get("progress", 0)
    ptext  = str(info.get("status", ""))[:35]
    bw     = 18
    filled = int(bw * prog / 100)
    bar    = "█" * filled + "░" * (bw - filled)
    pline  = f" [{bar}] {prog}%  {ptext}"
    out.append(G(r_prog) + f"│{pline:{gw}s}│")

    # ── footer ─────────────────────────────────────────────────────────────
    out.append(G(r_footer) + f"└{'─' * gw}┘")

    # ── entities (cursor-positioned after borders to avoid length issues) ───
    for e in gs.entities:
        e_col = round(e.x) + 2    # +1 for border │, +1 for 1-indexing
        vis, ecol = _ENTITY_VIS.get(e.kind, ("?", "0"))

        if e.kind == "block":
            # draw a solid wall column from e.row up to e.row+height-1
            block_row = vis * e.width    # e.g. "███"
            for h in range(e.height):
                er = r_playN - e.row - h
                if top + 1 <= er <= r_playN and 2 <= e_col <= gw + 1:
                    if _USE_COLOR:
                        out.append(f"\033[{er};{e_col}H\033[{ecol}m{block_row}\033[0m")
                    else:
                        out.append(f"\033[{er};{e_col}H{block_row}")
        else:
            # single-row entity
            er = r_playN - e.row
            if top + 1 <= er <= r_playN and 2 <= e_col <= gw + 1:
                w = min(len(vis), e.width)
                if _USE_COLOR:
                    out.append(f"\033[{er};{e_col}H\033[{ecol}m{vis[:w]}\033[0m")
                else:
                    out.append(f"\033[{er};{e_col}H{vis[:w]}")

    # ── player (2-row animated character, cursor-positioned) ────────────────
    p_row = round(min(gs.py, float(_PLAY_H - _PH)))
    p_body_r = r_playN - p_row           # terminal row of body
    p_head_r = p_body_r - 1             # terminal row of head
    p_col    = _PX + 2                  # terminal col of leftmost char

    if gs.dead:
        body, head = _PLAYER_DEAD
    elif p_row > 0:
        body, head = _PLAYER_AIR
    else:
        body, head = _PLAYER_RUN[(gs.frame // 4) % 2]

    if _USE_COLOR:
        clr = "36" if gs.shield > 0 else ("33" if gs.boost > 0 else "97")
        if top + 1 <= p_body_r <= r_playN:
            out.append(f"\033[{p_body_r};{p_col}H\033[{clr}m{body}{B}")
        if top + 1 <= p_head_r <= r_playN:
            out.append(f"\033[{p_head_r};{p_col}H\033[{clr}m{head}{B}")
    else:
        if top + 1 <= p_body_r <= r_playN:
            out.append(f"\033[{p_body_r};{p_col}H{body}")
        if top + 1 <= p_head_r <= r_playN:
            out.append(f"\033[{p_head_r};{p_col}H{head}")

    sys.stdout.write("".join(out))
    sys.stdout.flush()


# ── Splash shown while waiting for user to press G ───────────────────────────

def _splash(info: dict, elapsed: float) -> None:
    sp = "|/-\\"[int(elapsed * 4) % 4]
    status = str(info.get("status", ""))[:50]
    prog   = info.get("progress", 0)
    sys.stdout.write(
        f"\033[5;3H\033[2K  {sp} Installing... {prog}%  {status}          "
    )
    sys.stdout.flush()


# ── Main overlay entry point ──────────────────────────────────────────────────

def run_game_overlay(cmd: list[str]) -> int:
    """
    Run *cmd* as a subprocess; show Research Runner mini-game overlay.
    Download/install runs in a background thread.
    Returns the install process exit code.
    """
    info: dict = {"progress": 0, "status": "Starting...", "done": False, "rc": 0}
    start = time.perf_counter()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def _reader() -> None:
        try:
            for line in iter(proc.stdout.readline, ""):
                l = line.strip()
                if not l:
                    continue
                if any(k in l for k in ("Collecting", "Downloading", "Fetching")):
                    info["status"]   = l[:40]
                    info["progress"] = min(info["progress"] + 2, 80)
                elif "Installing" in l:
                    info["status"]   = l[:40]
                    info["progress"] = min(info["progress"] + 5, 92)
                elif "Successfully" in l:
                    info["status"]   = "Done!"
                    info["progress"] = 100
                else:
                    info["status"] = l[:40]
        finally:
            proc.stdout.close()
            proc.wait()
            info["done"] = True
            info["rc"]   = proc.returncode if proc.returncode is not None else 0

    threading.Thread(target=_reader, daemon=True).start()

    # ── initialise terminal ────────────────────────────────────────────────
    sys.stdout.write("\033[?25l")    # hide cursor
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(
        f"\n  {bold(cyan('ResearchHQ Installer'))}\n"
        f"  {dim('Installing dependencies in the background...')}\n\n"
        f"  Press {bold('G')} to launch {bold('Research Runner')} while you wait.\n"
        f"  Press {bold('Q')} to skip the game and watch output.\n"
    )
    sys.stdout.flush()

    TOP_ROW      = 2   # game frame starts at terminal row 2
    gs           = _GS()
    game_on      = False
    done_noticed = False
    wait_enter   = False
    notify_msg   = ""

    try:
        while True:
            t0 = time.perf_counter()

            try:
                key = _read_key()
            except Exception:
                key = None

            if key == "CTRL_C":
                proc.terminate()
                break

            # ── handle terminal resize ─────────────────────────────────────
            if game_on:
                _, rows = shutil.get_terminal_size(fallback=(80, 24))
                if rows < _PLAY_H + 6:
                    # terminal too small — exit game gracefully
                    game_on = False
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.write(
                        f"\n  {yellow('Terminal too small for game.')}"
                        f"  Waiting for install...\n"
                    )
                    sys.stdout.flush()

            # ── splash / waiting ───────────────────────────────────────────
            if not game_on and not wait_enter:
                if key == "G":
                    game_on = True
                    gs      = _GS()
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()
                elif key == "Q":
                    break  # fall through to blocking wait

                _splash(info, time.perf_counter() - start)

                if info["done"] and not done_noticed:
                    done_noticed = True
                    wait_enter   = True
                    sys.stdout.write(
                        f"\n\n  {green('✓')} Install complete!"
                        f"  Press Enter to continue setup.\n"
                    )
                    sys.stdout.flush()

                if wait_enter and key == "ENTER":
                    break

            # ── game active ────────────────────────────────────────────────
            elif game_on:
                if   key in ("SPACE", "UP"):           _jump(gs)
                elif key == "P":                        gs.paused = not gs.paused
                elif key in ("Q", "ESC"):
                    game_on = False
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.write(
                        f"\n  {dim('Game closed.')}"
                        f"  Waiting for install to finish...\n"
                    )
                    sys.stdout.flush()
                    if info["done"]:
                        wait_enter = True
                elif gs.dead and key == "SPACE":
                    gs = _GS()       # restart after death
                elif wait_enter and key == "ENTER":
                    break

                cols, _ = shutil.get_terminal_size(fallback=(80, 24))
                gw = cols - 4

                if not gs.dead:
                    _tick(gs, gw)

                # synthetic progress (pip doesn't emit real percentages)
                if not info["done"]:
                    elapsed = time.perf_counter() - start
                    info["progress"] = min(int(elapsed / 90 * 80), 88)

                if info["done"] and not done_noticed:
                    done_noticed = True
                    wait_enter   = True
                    notify_msg   = "INSTALL COMPLETE -- Press Enter to continue"

                try:
                    _draw(gs, info, notify_msg, TOP_ROW)
                except Exception:
                    pass   # game crash must never abort the install

            # ── frame rate cap ─────────────────────────────────────────────
            elapsed = time.perf_counter() - t0
            rem     = _FRAME_T - elapsed
            if rem > 0:
                time.sleep(rem)

    except KeyboardInterrupt:
        proc.terminate()
    finally:
        sys.stdout.write("\033[?25h")    # restore cursor
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    # If user quit early, wait for install to finish before returning
    if not info["done"]:
        _info("Waiting for installation to complete...")
        proc.wait()
        info["done"] = True
        info["rc"]   = proc.returncode or 0

    return info["rc"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print_banner()

    check_python()
    managers = detect_managers()

    source = choose_source()
    extras = choose_extras()

    run_install(source, extras, managers)

    keys = collect_api_keys()
    provider_cfg = configure_provider(keys)
    write_config(keys, provider_cfg)

    verify_install()
    print_success()


if __name__ == "__main__":
    main()
