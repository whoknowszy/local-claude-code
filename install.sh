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

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }

OS="$(uname -s)"
PYTHON_CMD=""

detect_python() {
    info "检测 Python..."
    if [[ "$OS" == "Darwin" ]]; then
        for cmd in python3.12 python3.11 python3.9 python3; do
            if command -v $cmd &>/dev/null; then PYTHON_CMD="$cmd"; break; fi
        done
    else
        for cmd in python3 python python3.12 python3.11 python3.9; do
            if command -v $cmd &>/dev/null; then PYTHON_CMD="$cmd"; break; fi
        done
    fi

    if [[ -z "$PYTHON_CMD" ]]; then
        error "未找到 Python，请先安装: https://www.python.org/downloads/"
        if [[ "$OS" == "Darwin" ]]; then
            info "macOS 推荐: brew install python@3.12"
        fi
        exit 1
    fi

    PY_VERSION=$($PYTHON_CMD -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo "0")
    if [[ "$PY_VERSION" -lt 9 ]]; then
        error "Python 版本过低，需要 3.9+，当前: $($PYTHON_CMD --version)"
        exit 1
    fi
    success "Python: $($PYTHON_CMD --version)"
}

ensure_pip() {
    info "确保 pip 可用..."
    if ! $PYTHON_CMD -m pip --version &>/dev/null; then
        warn "pip 未安装，尝试安装..."
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || \
        $PYTHON_CMD -m pip install pip --upgrade 2>/dev/null || true
    fi
}

install_lccg() {
    info "安装 lccg..."
    $PYTHON_CMD -m pip install --force-reinstall --no-cache-dir --no-deps \
        "git+https://github.com/whoknowszy/local-claude-code.git@main#egg=lccg"
    success "lccg 安装完成"
}

create_config() {
    CONFIG_FILE="$HOME/.lccg/config.yaml"
    if [[ -f "$CONFIG_FILE" ]]; then
        info "配置文件已存在: $CONFIG_FILE"
    else
        info "创建配置文件: $CONFIG_FILE"
        mkdir -p "$HOME/.lccg"
        $PYTHON_CMD - << 'PYEOF'
import pathlib
cfg = pathlib.Path("~/.lccg/config.yaml").expanduser()
cfg.write_text("""\
# LCCG Gateway 配置文件
# 文档: https://github.com/whoknowszy/local-claude-code

server:
  host: 127.0.0.1
  port: 8765
  # api_key: "your-proxy-api-key"

logging:
  level: info
  # log_dir: ~/.lccg/logs

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
""")
print(cfg)
PYEOF
    fi
}

detect_and_install_claude() {
    info "检测 Claude Code..."
    if command -v claude &>/dev/null; then
        success "Claude Code 已安装: $(claude --version 2>/dev/null || claude --version 2>/dev/null | head -1 || echo 'OK')"
    else
        warn "Claude Code 未安装，尝试安装..."
        if ! command -v npm &>/dev/null; then
            warn "npm 未找到，请先安装 Node.js: https://nodejs.org/"
            warn "安装 Claude Code 后，手动运行: npm install -g @anthropic-ai/claude-code"
        else
            npm install -g @anthropic-ai/claude-code 2>/dev/null && \
                success "Claude Code 安装完成" || \
                warn "Claude Code 安装失败，请手动安装: npm install -g @anthropic-ai/claude-code"
        fi
    fi
}

configure_env() {
    info "配置环境变量..."
    # Determine which profile file to use
    if [[ -n "$ZSH_VERSION" ]] || [[ "$OS" == "Darwin" && -d "$HOME/.zshrc" ]]; then
        PROFILE="$HOME/.zshrc"
    elif [[ -f "$HOME/.bashrc" ]]; then
        PROFILE="$HOME/.bashrc"
    elif [[ -f "$HOME/.bash_profile" ]]; then
        PROFILE="$HOME/.bash_profile"
    else
        PROFILE="$HOME/.profile"
    fi

    # Create profile if it doesn't exist
    if [[ ! -f "$PROFILE" ]]; then
        touch "$PROFILE"
    fi

    # Lines to add
    LCCG_BASE="export ANTHROPIC_BASE_URL=http://127.0.0.1:8765"
    LCCG_KEY='export ANTHROPIC_API_KEY="sk-placeholder"'

    # Add if not already present
    ADDED=false
    if ! grep -q "ANTHROPIC_BASE_URL.*127.0.0.1:8765" "$PROFILE" 2>/dev/null; then
        echo "" >> "$PROFILE"
        echo "# LCCG Gateway" >> "$PROFILE"
        echo "$LCCG_BASE" >> "$PROFILE"
        echo "$LCCG_KEY" >> "$PROFILE"
        ADDED=true
    fi

    if [[ "$ADDED" == "true" ]]; then
        success "已添加到 $PROFILE"
        info "环境变量将在下次打开终端时生效"
        info "立即生效请运行: source $PROFILE"
    else
        info "环境变量已配置: $PROFILE"
    fi
}

print_banner() {
    INSTALL_VERSION="v0.3.0"
    if command -v curl &>/dev/null; then
        INSTALL_VERSION=$(curl -sL --max-time 5 \
            https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/pyproject.toml 2>/dev/null | \
            python3 -c "import re,sys; m=re.search(r'^version\s*=\s*\"([^\"]+)\"', sys.stdin.read(), re.M); print('v'+m.group(1) if m else 'v0.3.0')" 2>/dev/null) || true
    fi
    echo ""
    echo -e "${CYAN}  _   _                       _   _             "
    echo -e " | \\ | | _____      _____ _ __| | | | ___  _   _ "
    echo -e " |  \\| |/ _ \\ \\ /\\ / / _ \\ '__| |_| |/ _ \\| | | |"
    echo -e " |_|\\  |  __/\\ V  V /  (__| |  |  _  | (_) | |_| |"
    echo -e "   |__/\\___| \\_/\\\_/ \\___|_|  |_| |_|\\___/ \\__, |"
    echo -e "                                            |___/  "
    echo -e "${NC}Local Claude Code Gateway  ${INSTALL_VERSION}"
    echo ""
}

main() {
    print_banner
    detect_python
    ensure_pip
    install_lccg
    create_config
    detect_and_install_claude
    configure_env

    echo ""
    success "安装完成！"
    echo ""
    echo -e "  启动 Gateway:  ${GREEN}lccg serve${NC}"
    echo -e "  编辑配置:      ${GREEN}~/.lccg/config.yaml${NC}"
    echo ""
    echo -e "  ${YELLOW}重要: 请编辑 ~/.lccg/config.yaml 添加你的 Provider API Key${NC}"
    echo ""
    echo -e "  文档: https://github.com/whoknowszy/local-claude-code"
    echo ""
}

main
