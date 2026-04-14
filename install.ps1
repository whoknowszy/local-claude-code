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
$REPO_URL = "git+https://github.com/whoknowszy/local-claude-code.git@main"
$installSuccess = $false

# 方式1：uv（推荐，最快）
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCmd) {
    Write-Info "检测到 uv，使用 uv 安装..."
    $bat = "$env:TEMP\lccg_install_uv_$PID.bat"
    @"
@echo off
uv tool install --force "$REPO_URL" >NUL 2>&1
exit /b %ERRORLEVEL%
"@ | Out-File -FilePath $bat -Encoding ASCII
    cmd /c $bat
    $uvExitCode = $LASTEXITCODE
    Remove-Item $bat -ErrorAction SilentlyContinue
    if ($uvExitCode -eq 0) {
        Write-Success "lccg 安装完成（via uv）"
        Write-Info "提示: uv 安装的命令位于 ~/.local/bin，请确保该路径在 PATH 中"
        $installSuccess = $true
    } else {
        Write-Warn "uv tool install 失败，尝试其他方式..."
    }
}

# 方式2：pipx（隔离环境，推荐）
if (-not $installSuccess) {
    $pipxCmd = Get-Command pipx -ErrorAction SilentlyContinue
    if ($pipxCmd) {
        Write-Info "检测到 pipx，使用 pipx 安装..."
        $bat = "$env:TEMP\lccg_install_pipx_$PID.bat"
        @"
@echo off
pipx install --force "$REPO_URL" >NUL 2>&1
exit /b %ERRORLEVEL%
"@ | Out-File -FilePath $bat -Encoding ASCII
        cmd /c $bat
        $pipxExitCode = $LASTEXITCODE
        Remove-Item $bat -ErrorAction SilentlyContinue
        if ($pipxExitCode -eq 0) {
            Write-Success "lccg 安装完成（via pipx）"
            $installSuccess = $true
        } else {
            Write-Warn "pipx install 失败，尝试其他方式..."
        }
    }
}

# 方式3：pip（兼容传统环境）
if (-not $installSuccess) {
    Write-Info "使用 pip 安装..."
    $bat = "$env:TEMP\lccg_install_pip_$PID.bat"
    @"
@echo off
"$python" -m pip install --force-reinstall --no-cache-dir "$REPO_URL" >NUL 2>&1
exit /b %ERRORLEVEL%
"@ | Out-File -FilePath $bat -Encoding ASCII
    cmd /c $bat
    $pipExitCode = $LASTEXITCODE
    Remove-Item $bat -ErrorAction SilentlyContinue
    if ($pipExitCode -eq 0) {
        Write-Success "lccg 安装完成（via pip）"
        $installSuccess = $true
    }
}

# 方式4：pip + --break-system-packages（PEP 668 兼容）
if (-not $installSuccess) {
    Write-Info "检测到受管理的 Python 环境，尝试 --break-system-packages..."
    $bat = "$env:TEMP\lccg_install_pip_break_$PID.bat"
    @"
@echo off
"$python" -m pip install --force-reinstall --no-cache-dir --break-system-packages "$REPO_URL" >NUL 2>&1
exit /b %ERRORLEVEL%
"@ | Out-File -FilePath $bat -Encoding ASCII
    cmd /c $bat
    $pipBreakExitCode = $LASTEXITCODE
    Remove-Item $bat -ErrorAction SilentlyContinue
    if ($pipBreakExitCode -eq 0) {
        Write-Success "lccg 安装完成（via pip --break-system-packages）"
        $installSuccess = $true
    }
}

# 所有方式都失败
if (-not $installSuccess) {
    Write-Err "lccg 安装失败"
    Write-Host ""
    Write-Host "  请尝试以下方式手动安装：" -ForegroundColor Yellow
    Write-Host "    方式1: uv tool install $REPO_URL" -ForegroundColor Gray
    Write-Host "    方式2: pipx install $REPO_URL" -ForegroundColor Gray
    Write-Host "    方式3: pip install --break-system-packages $REPO_URL" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  常见问题排查：" -ForegroundColor Yellow
    Write-Host "    1. 检查网络连接和 GitHub 访问" -ForegroundColor Gray
    Write-Host "    2. 确保 pip 可用: $python -m pip --version" -ForegroundColor Gray
    Write-Host "    3. 尝试升级 pip: $python -m pip install --upgrade pip" -ForegroundColor Gray
    Write-Host "    4. 检查 Git 是否安装: git --version" -ForegroundColor Gray
    exit 1
}

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

# 只设置 ANTHROPIC_BASE_URL，不设置 API_KEY 占位符
# lccg code 命令会自动处理 API_KEY 的传递
$currentBaseUrl = [Environment]::GetEnvironmentVariable("ANTHROPIC_BASE_URL", "User")
if (-not $currentBaseUrl) {
    [Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://127.0.0.1:8765", "User")
    $env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8765"
    Write-Success "已设置 ANTHROPIC_BASE_URL"
} elseif ($currentBaseUrl -like "*127.0.0.1*") {
    Write-Info "ANTHROPIC_BASE_URL 已配置: $currentBaseUrl"
} else {
    Write-Warn "ANTHROPIC_BASE_URL 已配置为: $currentBaseUrl"
    Write-Host "  如需使用本地网关，请手动设置为 http://127.0.0.1:8765" -ForegroundColor Gray
}

# 验证安装
Write-Host ""
Write-Info "验证安装..."
try {
    $verifyResult = & $python -m lccg --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "lccg 安装验证通过: $verifyResult"
    } else {
        Write-Warn "lccg 命令验证失败，请检查 Python PATH"
    }
} catch {
    Write-Warn "lccg 命令验证失败: $_"
}

Write-Host ""
Write-Success "安装完成！"
Write-Host ""
Write-Host "  推荐使用:" -ForegroundColor Green
Write-Host "    lccg code              一键启动网关 + Claude Code"
Write-Host ""
Write-Host "  手动管理:" -ForegroundColor Green
Write-Host "    lccg serve             启动网关"
Write-Host "    lccg status            查看网关状态"
Write-Host "    lccg stop              停止后台网关"
Write-Host ""
Write-Host "  配置文件: $configFile" -ForegroundColor Green
Write-Host "  重要: 请编辑配置文件添加你的 Provider API Key" -ForegroundColor Yellow
Write-Host ""
Write-Host "  文档: https://github.com/whoknowszy/local-claude-code"
Write-Host ""
