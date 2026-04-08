# LCCG Gateway 一键安装脚本 - Windows PowerShell
# 用法: powershell -ExecutionPolicy Bypass -File install.ps1
# 或直接: irm https://.../install.ps1 | iex

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
Write-Host "Local Claude Code Gateway v0.2.0" -ForegroundColor White
Write-Host ""

# Detect Python
function Get-Python {
    $candidates = @("python3.12", "python3.11", "python3.9", "python3", "python")
    foreach ($cmd in $candidates) {
        $path = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($path) {
            $versionOutput = & $cmd --version 2>&1
            if ($versionOutput -match "Python (\d+)\.(\d+)") {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]
                if ($major -eq 3 -and $minor -ge 9) {
                    return $cmd
                }
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
        Write-Host "下载 Python 3.12 安装包，运行安装程序" -ForegroundColor Gray
        Write-Host "安装时勾选: Add Python to PATH" -ForegroundColor Gray
        Write-Host ""
        Write-Host "或者使用 winget 安装:" -ForegroundColor Yellow
        Write-Host "  winget install Python.Python.3.12" -ForegroundColor Gray
        exit 1
    }

    $ver = & $python --version 2>&1
    Write-Success "使用 Python: $ver"
}

# Upgrade pip
Write-Info "确保 pip 可用..."
$pipCmd = "$python -m pip"
& $pipCmd install --upgrade pip 2>$null | Out-Null

# Install lccg
Write-Info "安装 lccg..."
& $pipCmd install --force-reinstall --no-deps "git+https://github.com/whoknowszy/local-claude-code.git@main#egg=lccg" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "lccg 安装失败，请检查网络连接"
    exit 1
}
Write-Success "lccg 安装完成！"

# Create config
$configDir = "$HOME\.lccg"
$configFile = "$configDir\config.yaml"

if (Test-Path $configFile) {
    Write-Warn "配置文件已存在: $configFile，跳过创建"
} else {
    Write-Info "创建配置文件: $configFile"
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir | Out-Null
    }

    $configContent = @"
# LCCG Gateway 配置文件
# 文档: https://github.com/whoknowszy/local-claude-code

server:
  host: 127.0.0.1
  port: 8765
  # api_key: "your-proxy-api-key"   # 可选，启用代理认证

logging:
  level: info
  # log_dir: ~/.lccg/logs           # 可选，启用文件日志

providers:
  # 示例 Anthropic 兼容 Provider
  # - name: anthropic
  #   type: anthropic
  #   base_url: https://api.anthropic.com/v1/messages
  #   api_key: sk-ant-...
  #   models:
  #     - claude-sonnet-4-7-20250514
  #     - claude-haiku-4-5-20250514
  #   timeout: 600

  # 示例 OpenAI 兼容 Provider
  # - name: openai
  #   type: openai
  #   base_url: https://api.openai.com/v1/chat/completions
  #   api_key: sk-...
  #   auth_scheme: bearer
  #   models:
  #     - gpt-4o
  #   timeout: 600

router:
  # default: "provider,model"       # 默认路由
  # fallback: "provider,model"      # 故障回退
  # background: "provider,model"     # haiku 模型路由
  # long_context: "provider,model"  # 长上下文路由 (>threshold tokens)
  # long_context_threshold: 60000
  # think: "provider,model"         # thinking enabled 路由
  # web_search: "provider,model"    # web_search tools 路由
"@

    $configContent | Out-File -FilePath $configFile -Encoding UTF8
    Write-Success "配置文件已创建: $configFile"
    Write-Info "请编辑配置文件添加你的 Provider"
}

Write-Host ""
Write-Success "安装完成！"
Write-Host ""
Write-Host "  启动: lccg serve" -ForegroundColor Green
Write-Host "  配置: $configFile" -ForegroundColor Green
Write-Host "  文档: https://github.com/whoknowszy/local-claude-code" -ForegroundColor Green
Write-Host ""
Write-Host "  设置 Claude Code 使用本 Gateway:" -ForegroundColor Cyan
Write-Host '  $env:ANTHROPIC_BASE_URL="http://127.0.0.1:8766"' -ForegroundColor Gray
Write-Host ""
