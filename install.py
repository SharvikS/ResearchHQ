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
import shutil
import subprocess
import sys
from pathlib import Path

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
    result = _run(cmd)
    print()
    if result.returncode != 0:
        _err("Installation failed. See output above.")
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
