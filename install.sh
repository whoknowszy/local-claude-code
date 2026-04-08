#!/usr/bin/env bash
# LCCG Gateway 一键安装脚本 - macOS / Linux / Git Bash
# 用法:
#   一键安装: curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash
#   或下载后运行: bash install.sh

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
die()     { error "$1"; exit 1; }

# 检测 OS
OS="$(uname -s)"
PYTHON_CMD=""
PIP_CMD=""

detect_python() {
    info "检测 Python..."

    # macOS
    if [[ "$OS" == "Darwin" ]]; then
        if command -v python3.12 &>/dev/null; then
            PYTHON_CMD="python3.12"
        elif command -v python3.11 &>/dev/null; then
            PYTHON_CMD="python3.11"
        elif command -v python3.9 &>/dev/null; then
            PYTHON_CMD="python3.9"
        elif command -v python3 &>/dev/null; then
            PYTHON_CMD="python3"
        else
            error "未找到 Python，请先安装: https://www.python.org/downloads/"
            info "macOS 推荐使用 Homebrew 安装: brew install python@3.12"
            exit 1
        fi
    # Linux / Git Bash / WSL
    else
        for cmd in python3 python python3.12 python3.11 python3.9; do
            if command -v $cmd &>/dev/null; then
                PYTHON_CMD="$cmd"
                break
            fi
        done
        if [[ -z "$PYTHON_CMD" ]]; then
            error "未找到 Python，请先安装: https://www.python.org/downloads/"
            exit 1
        fi
    fi

    # 验证版本 >= 3.9
    PY_VERSION=$($PYTHON_CMD -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo "0")
    if [[ "$PY_VERSION" -lt 9 ]]; then
        error "Python 版本过低，需要 Python 3.9+，当前: $($PYTHON_CMD --version)"
        exit 1
    fi

    success "使用 Python: $($PYTHON_CMD --version)"
}

ensure_pip() {
    info "确保 pip 可用..."
    if ! $PYTHON_CMD -m pip --version &>/dev/null; then
        warn "pip 未安装，尝试安装..."
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || \
        $PYTHON_CMD -m pip install pip --upgrade 2>/dev/null || true
    fi
    PIP_CMD="$PYTHON_CMD -m pip"
}

install_package() {
    info "安装 lccg..."
    $PIP_CMD install --upgrade "git+https://github.com/whoknowszy/local-claude-code.git@v0.2.0#egg=lccg"
    success "lccg 安装完成！"
}

create_config() {
    CONFIG_DIR="$HOME/.lccg"
    CONFIG_FILE="$CONFIG_DIR/config.yaml"

    if [[ -f "$CONFIG_FILE" ]]; then
        warn "配置文件已存在: $CONFIG_FILE，跳过创建"
        return
    fi

    info "创建配置文件: $CONFIG_FILE"
    mkdir -p "$CONFIG_DIR"

    # shellcheck disable=SC2016
    $PYTHON_CMD - << 'PYEOF'
import os, pathlib

config_dir = pathlib.Path(os.path.expanduser("~/.lccg"))
config_file = config_dir / "config.yaml"

config_content = """\
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
  # fallback: "provider,model"       # 故障回退
  # background: "provider,model"     # haiku 模型路由
  # long_context: "provider,model"   # 长上下文路由 (>threshold tokens)
  # long_context_threshold: 60000
  # think: "provider,model"          # thinking enabled 路由
  # web_search: "provider,model"     # web_search tools 路由
"""

config_file.write_text(config_content)
print(config_file)
PYEOF

    if [[ -f "$CONFIG_FILE" ]]; then
        success "配置文件已创建: $CONFIG_FILE"
        info "请编辑配置文件添加你的 Provider"
    fi
}

print_banner() {
    echo ""
    echo -e "${CYAN}  _   _                       _   _             "
    echo -e " | \\ | | _____      _____ _ __| | | | ___  _   _ "
    echo -e " |  \\| |/ _ \\ \\ /\ / / _ \ '__| |_| |/ _ \\| | | |"
    echo -e " |_|\\  |  __/\\ V  V /  __/ |  |  _  | (_) | |_| |"
    echo -e "   |__/\\___| \\_/\\_/ \\___|_|  |_| |_|\\___/ \\__, |"
    echo -e "                                            |___/  "
    echo -e "${NC}Local Claude Code Gateway v0.2.0"
    echo ""
}

main() {
    print_banner
    detect_python
    ensure_pip
    install_package
    create_config

    echo ""
    success "安装完成！"
    echo ""
    echo -e "  启动: ${GREEN}lccg serve${NC}"
    echo -e "  配置: ${GREEN}~/.lccg/config.yaml${NC}"
    echo -e "  文档: ${GREEN}https://github.com/whoknowszy/local-claude-code${NC}"
    echo ""
    echo -e "  设置 Claude Code 使用本 Gateway:"
    echo -e "  ${YELLOW}export ANTHROPIC_BASE_URL=http://127.0.0.1:8765${NC}"
    echo ""
}

main
