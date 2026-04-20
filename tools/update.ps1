# Update LCCG from the local source checkout used by install.ps1.

param(
    [string]$SourceDir = $env:LCCG_SOURCE_DIR
)

$ErrorActionPreference = "Stop"

if (-not $SourceDir) {
    $RepoDir = Resolve-Path (Join-Path $PSScriptRoot "..")
    $SourceDir = $RepoDir.Path
}

if (-not (Test-Path (Join-Path $SourceDir ".git")) -or -not (Test-Path (Join-Path $SourceDir "pyproject.toml"))) {
    $SourceDir = Join-Path $HOME ".lccg\source"
}

if (-not (Test-Path (Join-Path $SourceDir ".git")) -or -not (Test-Path (Join-Path $SourceDir "pyproject.toml"))) {
    Write-Host "[ERROR] Cannot find a local LCCG source checkout." -ForegroundColor Red
    Write-Host "        Reinstall with install.ps1, or pass -SourceDir C:\path\to\local-claude-code." -ForegroundColor Gray
    exit 1
}

$python = $env:PYTHON
if (-not $python) {
    foreach ($cmd in @("python3.12", "python3.11", "python3.10", "python3.9", "python3", "python")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $python = $cmd
            break
        }
    }
}

if (-not $python) {
    Write-Host "[ERROR] Python 3.9+ is required." -ForegroundColor Red
    exit 1
}

function Get-SourceVersion($sourceDir) {
    $branch = git -C $sourceDir rev-parse --abbrev-ref HEAD
    $commit = git -C $sourceDir rev-parse --short HEAD
    $commitTime = git -C $sourceDir log -1 --format='%ci'
    $subject = git -C $sourceDir log -1 --format='%s'
    return "$branch@$commit  $commitTime  $subject"
}

Write-Host "[INFO] Updating source checkout: $SourceDir" -ForegroundColor Cyan
Write-Host "[INFO] Before update: $(Get-SourceVersion $SourceDir)" -ForegroundColor Cyan
git -C $SourceDir pull --ff-only origin main
Write-Host "[INFO] After update:  $(Get-SourceVersion $SourceDir)" -ForegroundColor Cyan

Write-Host "[INFO] Reinstalling editable package..." -ForegroundColor Cyan
& $python -m pip install -e $SourceDir

Write-Host "[OK] Update complete." -ForegroundColor Green
try { lccg --version } catch {}
