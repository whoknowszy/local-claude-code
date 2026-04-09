# LCCG Gateway 一键安装脚本 - Windows PowerShell
# 用法:
#   一键安装: irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1 | iex
#   或下载后运行: .\install.ps1

param(
    [switch]$SkipPythonCheck
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Banner
Write-Host ""
Write-Host "  _   _                       _   _             " -ForegroundColor Cyan
Write-Host " | \ | | _____      _____ _ __| | | | ___  _   _ " -ForegroundColor Cyan
Write-Host " |  \| |/ _ \ \ /\ / / _ \ '__| |_| |/ _ \| | | |" -ForegroundColor Cyan
Write-Host " |_|\  |  __/\ V  V /  __/ |  |  _  | (_) | |_| |" -ForegroundColor Cyan
Write-Host "   |__/\___| \_/\_/ \___|_|  |_| |_|\___/ \__, |" -ForegroundColor Cyan
Write-Host "                                            |___/  " -ForegroundColor Cyan

$INSTALL_VERSION = "v0.3.0"
try {
    $resp = Invoke-WebRequest -Uri "https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/pyproject.toml" -UseBasicParsing -TimeoutSec 5
    if ($resp.Content -match 'version\s*=\s*"([^"]+)"') { $INSTALL_VERSION = "v" + $Matches[1] }
} catch {}
Write-Host "Local Claude Code Gateway  $INSTALL_VERSION" -ForegroundColor White
Write-Host ""

# Detect Python
function Get-Python {
    $candidates = @("python3.12", "python3.11", "python3.9", "python3", "python")
    foreach ($cmd in $candidates) {
        $path = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($path) {
            $versionOutput = & $cmd --version 2>&1
            if ($versionOutput -match "Python (\d+)\.(\d+)") {
                $minor = [int]$matches[2]
                if ($minor -ge 9) { return $cmd }
            }
        }
    }
    return $null
}

if (-not $SkipPythonCheck) {
    Write-Info "检测 Python..."
    $python = Get-Python
    if (-not $python) {
        Write-Err "未找到 Python 3.9+，请先安装"
        Write-Host ""
        Write-Host "下载地址: https://www.python.org/downloads/windows/" -ForegroundColor Yellow
        Write-Host "安装时勾选: Add Python to PATH" -ForegroundColor Gray
        Write-Host "或使用 winget: winget install Python.Python.3.12" -ForegroundColor Gray
        exit 1
    }
    $ver = & $python --version 2>&1
    Write-Success "Python: $ver"
}

# Ensure pip
Write-Info "确保 pip 可用..."
& $python -m pip install --upgrade pip 2>$null | Out-Null

# Install lccg
Write-Info "安装 lccg..."
# Write pip command to a temp .bat file and run via cmd /c
# This is the only reliable way to suppress Python's Information stream (stream #6)
# in PowerShell 5.x — all output stays inside cmd and gets swallowed by >NUL
$bat = "$env:TEMP\lccg_install_$PID.bat"
@"
@echo off
"$python" -m pip install --force-reinstall --no-cache-dir --no-deps "git+https://github.com/whoknowszy/local-claude-code.git@main#egg=lccg" >NUL 2>&1
exit /b %ERRORLEVEL%
"@ | Out-File -FilePath $bat -Encoding ASCII
cmd /c $bat
$exitCode = $LASTEXITCODE
Remove-Item $bat -ErrorAction SilentlyContinue
if ($exitCode -ne 0 -or -not (Get-Command lccg -ErrorAction SilentlyContinue)) {
    Write-Err "lccg 安装失败，请手动运行以下命令排查："
    Write-Host "  $python -m pip install --force-reinstall --no-cache-dir --no-deps `"git+https://github.com/whoknowszy/local-claude-code.git@main#egg=lccg`"" -ForegroundColor Gray
    exit 1
}
Write-Success "lccg 安装完成"

# Create config
$configDir = "$HOME\.lccg"
$configFile = "$configDir\config.yaml"
if (Test-Path $configFile) {
    Write-Info "配置文件已存在: $configFile"
} else {
    Write-Info "创建配置文件: $configFile"
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir | Out-Null
    }
    @"
# LCCG Gateway 配置文件
# 文档: https://github.com/whoknowszy/local-claude-code

server:
  host: 127.0.0.1
  port: 8765
  # api_key: "your-proxy-api-key"

logging:
  level: info
  # log_dir: ~\.lccg\logs

providers:
  # 请在此添加你的 Provider，例如:
  # - name: anthropic
  #   type: anthropic
  #   base_url: https://api.anthropic.com/v1/messages
  #   api_key: sk-ant-...
  #   models:
  #     - claude-sonnet-4-7-20250514
  #   timeout: 600

router:
  # default: "provider,model"
  # fallback: "provider,model"
"@ | Out-File -FilePath $configFile -Encoding UTF8
}

# Detect and install Claude Code
Write-Info "检测 Claude Code..."
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeCmd) {
    try {
        $claudeVer = & claude --version 2>&1
        Write-Success "Claude Code 已安装: $claudeVer"
    } catch {
        Write-Success "Claude Code 已安装"
    }
} else {
    Write-Warn "Claude Code 未安装"
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmCmd) {
        Write-Info "正在安装 Claude Code..."
        npm install -g @anthropic-ai/claude-code 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Claude Code 安装完成"
        } else {
            Write-Warn "Claude Code 安装失败，请手动安装: npm install -g @anthropic-ai/claude-code"
        }
    } else {
        Write-Warn "npm 未找到，请先安装 Node.js: https://nodejs.org/"
        Write-Warn "Claude Code 安装后请手动配置环境变量"
    }
}

# Configure environment variables
Write-Info "配置环境变量..."
$added = $false
$userEnv = "HKCU:\Environment"

# ANTHROPIC_BASE_URL
$existingUrl = [Environment]::GetEnvironmentVariable("ANTHROPIC_BASE_URL", "User")
if ($existingUrl -notlike "*127.0.0.1*") {
    [Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://127.0.0.1:8765", "User")
    $added = $true
}

# ANTHROPIC_API_KEY
$existingKey = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if ([string]::IsNullOrEmpty($existingKey)) {
    [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-placeholder", "User")
    $added = $true
}

if ($added) {
    Write-Success "已添加到用户环境变量（当前会话需重启或重新打开终端）"
} else {
    Write-Info "环境变量已配置"
}

Write-Host ""
Write-Success "安装完成！"
Write-Host ""
Write-Host "  启动 Gateway:  lccg serve" -ForegroundColor Green
Write-Host "  编辑配置:     $configFile" -ForegroundColor Green
Write-Host ""
Write-Host "  重要: 请编辑 $configFile 添加你的 Provider API Key" -ForegroundColor Yellow
Write-Host ""
Write-Host "  文档: https://github.com/whoknowszy/local-claude-code"
Write-Host ""
