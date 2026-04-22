# LCCG Gateway one-click installer - Windows PowerShell
# Usage:
#   irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1 | iex
#   or run locally: .\install.ps1

param(
    [switch]$SkipPythonCheck,
    [ValidateSet("source", "wheel")]
    [string]$InstallMode = $(if ($env:LCCG_INSTALL_MODE) { $env:LCCG_INSTALL_MODE } else { "source" })
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoUrl = "https://github.com/whoknowszy/local-claude-code.git"
$SourceDir = Join-Path $HOME ".lccg\source"
$ReleaseApiUrl = "https://api.github.com/repos/whoknowszy/local-claude-code/releases/latest"

function Write-Info($msg) { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Get-SourceVersion($sourceDir) {
    $branch = git -C $sourceDir rev-parse --abbrev-ref HEAD
    $commit = git -C $sourceDir rev-parse --short HEAD
    $commitTime = git -C $sourceDir log -1 --format='%ci'
    $subject = git -C $sourceDir log -1 --format='%s'
    return @{
        Branch = $branch
        Commit = $commit
        CommitTime = $commitTime
        Subject = $subject
    }
}

function Write-SourceVersion($label, $sourceDir) {
    if (-not (Test-Path (Join-Path $sourceDir ".git"))) {
        Write-Warn "$label unavailable: $sourceDir is not a Git repository"
        return
    }

    $version = Get-SourceVersion $sourceDir
    Write-Success "$label`: $($version.Branch)@$($version.Commit)"
    Write-Info "Commit time: $($version.CommitTime)"
    Write-Info "Commit subject: $($version.Subject)"
}

function Write-Banner {
    Write-Host ""
    Write-Host "  _   _                       _   _             " -ForegroundColor Cyan
    Write-Host " | \ | | _____      _____ _ __| | | | ___  _   _ " -ForegroundColor Cyan
    Write-Host " |  \| |/ _ \ \ /\ / / _ \ '__| |_| |/ _ \| | | |" -ForegroundColor Cyan
    Write-Host " |_|\  |  __/\ V  V /  __/ |  |  _  | (_) | |_| |" -ForegroundColor Cyan
    Write-Host "   |__/\___| \_/\_/ \___|_|  |_| |_|\___/ \__, |" -ForegroundColor Cyan
    Write-Host "                                            |___/  " -ForegroundColor Cyan
    Write-Host "Local Claude Code Gateway" -ForegroundColor White
    Write-Host ""
}

function Get-Python {
    $candidates = @("python3.12", "python3.11", "python3.10", "python3.9", "python3", "python")
    foreach ($cmd in $candidates) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $found) { continue }

        $versionOutput = & $cmd --version 2>&1
        if ($versionOutput -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 9) {
                return $cmd
            }
        }
    }
    return $null
}

function Ensure-Git {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Err "Git not found. Please install Git first: https://git-scm.com/download/win"
        exit 1
    }
}

function Install-Lccg($python) {
    if ($InstallMode -eq "wheel") {
        Install-LccgWheel $python
        return
    }

    if ($InstallMode -ne "source") {
        Write-Err "Unknown install mode: $InstallMode. Use 'source' or 'wheel'."
        exit 1
    }

    Install-LccgSource $python
}

function Install-LccgWheel($python) {
    $version = if ($env:LCCG_VERSION) { $env:LCCG_VERSION } else { "latest" }
    if ($env:LCCG_WHEEL_URL) {
        $wheelUrl = $env:LCCG_WHEEL_URL
    } elseif ($version -eq "latest") {
        $wheelUrl = Resolve-LatestWheelUrl
    } else {
        $wheelUrl = "https://github.com/whoknowszy/local-claude-code/releases/download/v$version/lccg-$version-py3-none-any.whl"
    }

    Write-Info "Installing lccg from wheel: $wheelUrl"
    & $python -m pip install --upgrade $wheelUrl
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Wheel install failed. Confirm the release wheel exists, or use: .\install.ps1 -InstallMode source"
        exit 1
    }

    try {
        $installedVersion = & $python -c "import importlib.metadata; print(importlib.metadata.version('lccg'))" 2>$null
        Write-Success "lccg v$installedVersion installed from wheel"
    } catch {
        Write-Success "lccg installed from wheel"
    }
}

function Resolve-LatestWheelUrl {
    $headers = @{
        Accept = "application/vnd.github+json"
        "User-Agent" = "lccg-installer"
    }
    $release = Invoke-RestMethod -Uri $ReleaseApiUrl -Headers $headers
    $asset = $release.assets |
        Where-Object { $_.name -like "lccg-*-py3-none-any.whl" } |
        Select-Object -First 1

    if (-not $asset) {
        Write-Err "No latest release wheel found. Confirm the GitHub Release has a wheel asset, or set LCCG_WHEEL_URL."
        exit 1
    }

    return $asset.browser_download_url
}

function Install-LccgSource($python) {
    Ensure-Git

    $sourceParent = Split-Path -Parent $SourceDir
    if (-not (Test-Path $sourceParent)) {
        New-Item -ItemType Directory -Path $sourceParent | Out-Null
    }

    if (Test-Path (Join-Path $SourceDir ".git")) {
        Write-Info "Updating source checkout: $SourceDir"
        git -C $SourceDir pull --ff-only origin main
    } else {
        if (Test-Path $SourceDir) {
            Write-Err "$SourceDir exists but is not a Git repository. Move or remove it, then retry."
            exit 1
        }
        Write-Info "Cloning source checkout to: $SourceDir"
        git clone $RepoUrl $SourceDir
    }

    Write-Info "Installing lccg from local source checkout..."
    & $python -m pip install -e $SourceDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install failed. Try manually: $python -m pip install -e $SourceDir"
        exit 1
    }

    try {
        $version = & $python -c "import importlib.metadata; print(importlib.metadata.version('lccg'))" 2>$null
        Write-Success "lccg v$version installed"
    } catch {
        Write-Success "lccg installed"
    }
    Write-SourceVersion "Source version" $SourceDir
}

function Create-Config {
    $configDir = Join-Path $HOME ".lccg"
    $configFile = Join-Path $configDir "config.yaml"
    if (Test-Path $configFile) {
        Write-Info "Config already exists: $configFile"
        return
    }

    Write-Info "Creating config: $configFile"
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir | Out-Null
    }

    @"
# LCCG Gateway config
# Docs: https://github.com/whoknowszy/local-claude-code

server:
  host: 127.0.0.1
  port: 8765
  # api_key: "your-proxy-api-key"

logging:
  level: info
  # log_dir: ~\.lccg\logs

# Add providers here, for example:
# providers:
#   - name: anthropic
#     type: anthropic
#     base_url: https://api.anthropic.com/v1/messages
#     api_key: sk-ant-...
#     models:
#       - claude-sonnet-4-7-20250514
#     timeout: 600

# router:
#   default: "provider,model"
#   fallback: "provider,model"
"@ | Out-File -FilePath $configFile -Encoding UTF8
}

function Install-Claude-Code {
    Write-Info "Checking Claude Code..."
    if (Get-Command claude -ErrorAction SilentlyContinue) {
        try {
            $claudeVer = & claude --version 2>&1
            Write-Success "Claude Code installed: $claudeVer"
        } catch {
            Write-Success "Claude Code installed"
        }
        return
    }

    Write-Warn "Claude Code not found"
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Info "Installing Claude Code with npm..."
        npm install -g @anthropic-ai/claude-code
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Claude Code installed"
        } else {
            Write-Warn "Claude Code install failed. Run manually: npm install -g @anthropic-ai/claude-code"
        }
    } else {
        Write-Warn "npm not found. Install Node.js first: https://nodejs.org/"
    }
}

function Configure-Environment {
    Write-Info "Configuring ANTHROPIC_BASE_URL..."
    $currentBaseUrl = [Environment]::GetEnvironmentVariable("ANTHROPIC_BASE_URL", "User")
    if (-not $currentBaseUrl) {
        [Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://127.0.0.1:8765", "User")
        $env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8765"
        Write-Success "ANTHROPIC_BASE_URL set to http://127.0.0.1:8765"
    } elseif ($currentBaseUrl -like "*127.0.0.1*") {
        Write-Info "ANTHROPIC_BASE_URL already configured: $currentBaseUrl"
    } else {
        Write-Warn "ANTHROPIC_BASE_URL is currently: $currentBaseUrl"
        Write-Host "  Set it to http://127.0.0.1:8765 if you want to use this gateway." -ForegroundColor Gray
    }
}

function Verify-Install($python) {
    Write-Host ""
    Write-Info "Verifying install..."
    try {
        $verifyResult = & $python -m lccg --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "lccg verified: $verifyResult"
            return
        }
    } catch {}

    $lccgCmd = Get-Command lccg -ErrorAction SilentlyContinue
    if ($lccgCmd) {
        Write-Success "lccg command available: $($lccgCmd.Source)"
    } else {
        Write-Warn "lccg installed, but the command is not on PATH yet."
        Write-Warn "Restart the terminal or run with: $python -m lccg"
    }
}

Write-Banner

$python = Get-Python
if (-not $python) {
    if ($SkipPythonCheck) {
        $python = "python"
        Write-Warn "Skipping Python detection; using 'python'"
    } else {
        Write-Err "Python 3.9+ not found. Install from https://www.python.org/downloads/windows/"
        Write-Host "Install tip: check 'Add Python to PATH'." -ForegroundColor Gray
        Write-Host "Or use: winget install Python.Python.3.12" -ForegroundColor Gray
        exit 1
    }
} else {
    $ver = & $python --version 2>&1
    Write-Success "Python: $ver"
}

Write-Info "Ensuring pip is available..."
& $python -m pip install --upgrade pip 2>$null | Out-Null

Install-Lccg $python
Create-Config
Install-Claude-Code
Configure-Environment
Verify-Install $python

Write-Host ""
Write-Success "Install complete!"
Write-Host ""
Write-Host "  Recommended:" -ForegroundColor Green
Write-Host "    lccg code              start gateway + Claude Code"
Write-Host ""
Write-Host "  Manual commands:" -ForegroundColor Green
Write-Host "    lccg serve             start gateway"
Write-Host "    lccg update            pull latest code and reinstall"
Write-Host "    lccg status            show gateway status"
Write-Host "    lccg stop              stop background gateway"
Write-Host ""
Write-Host "  Source checkout: $SourceDir" -ForegroundColor Green
Write-Host "  Config file:     $(Join-Path $HOME ".lccg\config.yaml")" -ForegroundColor Green
Write-Host "  Docs:            https://github.com/whoknowszy/local-claude-code"
Write-Host ""
