<#
.SYNOPSIS
  ResearchHQ — one-command installer bootstrap (Windows / PowerShell).

.DESCRIPTION
  Thin wrapper that locates a Python 3.11+ interpreter, downloads install.py
  robustly, and runs it interactively. Intended to be invoked as:

      irm https://raw.githubusercontent.com/SharvikS/ResearchHQ/master/install.ps1 | iex

  Overrides (useful for testing a branch before it is merged to master):
      $env:RHQ_INSTALL_REF = 'my-branch'          # pick a git ref
      $env:RESEARCHHQ_INSTALL_URL = '<raw url>'    # full URL override
#>

$ErrorActionPreference = 'Stop'

$Repo = 'SharvikS/ResearchHQ'
$Ref  = if ($env:RHQ_INSTALL_REF) { $env:RHQ_INSTALL_REF } else { 'master' }
$Url  = if ($env:RESEARCHHQ_INSTALL_URL) {
    $env:RESEARCHHQ_INSTALL_URL
} else {
    "https://raw.githubusercontent.com/$Repo/$Ref/install.py"
}

function Write-Info($m) { Write-Host "  $m" -ForegroundColor DarkGray }
function Write-Ok($m)   { Write-Host "  $([char]0x2713) $m" -ForegroundColor Green }
function Write-Err($m)  { Write-Host "  $([char]0x2717) $m" -ForegroundColor Red }

Write-Host ""
Write-Host "  ResearchHQ" -ForegroundColor Cyan -NoNewline
Write-Host " - multi-agent research workstation" -ForegroundColor DarkGray
Write-Host ""

# ── 1. Locate a suitable Python (>= 3.11) ───────────────────────────────────
# Probe `py -3` first: the Windows launcher is the most reliable and dodges the
# Microsoft Store "python.exe" stub that otherwise hijacks the PATH. Each
# candidate is verified by actually executing it, so a stub or old version
# can never slip through.
function Find-Python {
    $cands = @(
        [pscustomobject]@{ Exe = 'py';      Pre = @('-3') },
        [pscustomobject]@{ Exe = 'python';  Pre = @() },
        [pscustomobject]@{ Exe = 'python3'; Pre = @() }
    )
    $code = 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)'
    foreach ($c in $cands) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        try {
            # Note: avoid the automatic $args variable name here.
            $probe = @($c.Pre) + @('-c', $code)
            & $c.Exe @probe 2>$null
            if ($LASTEXITCODE -eq 0) { return $c }
        } catch { }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Err 'Python 3.11+ is required but was not found.'
    Write-Host ''
    Write-Host '  Install it, then re-run this command:' -ForegroundColor DarkGray
    Write-Host '    winget install Python.Python.3.12'
    Write-Host '    (or download from https://www.python.org/downloads/ and tick "Add python.exe to PATH")'
    throw 'Python 3.11+ not found.'
}
$verArgs = @($py.Pre) + @('-c', 'import sys;print("Python %d.%d.%d"%sys.version_info[:3])')
$ver = (& $py.Exe @verArgs 2>$null)
Write-Ok "Using $ver"

# ── 2. Download installer + 3. run it ───────────────────────────────────────
$tmp = Join-Path $env:TEMP ("rhq_install_{0}.py" -f ([guid]::NewGuid().ToString('N')))
try {
    Write-Info 'Downloading installer...'
    try {
        # TLS 1.2 for older PowerShell defaults; -UseBasicParsing for PS 5.1.
        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
        Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
    } catch {
        Write-Err "Download failed: $Url"
        Write-Err $_.Exception.Message
        throw
    }

    if (-not (Select-String -Path $tmp -Pattern 'ResearchHQ' -Quiet)) {
        Write-Err 'Downloaded file does not look like the installer (got an error page?).'
        throw "Unexpected installer content from $Url"
    }

    $runArgs = @($py.Pre) + @($tmp)
    & $py.Exe @runArgs
    $rc = $LASTEXITCODE
} finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}

if ($rc -and $rc -ne 0) {
    throw "Installer exited with code $rc."
}
