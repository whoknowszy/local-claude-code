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
    local REPO_URL="git+https://github.com/whoknowszy/local-claude-code.git@main"
    info "安装 lccg..."

    # 方式1：uv（推荐，最快）
    if command -v uv &>/dev/null; then
        info "检测到 uv，使用 uv 安装..."
        if uv tool install --force "$REPO_URL" 2>/dev/null; then
            success "lccg 安装完成（via uv）"
            info "提示: uv 安装的命令位于 ~/.local/bin，请确保该路径在 PATH 中"
            return 0
        fi
        warn "uv tool install 失败，尝试其他方式..."
    fi

    # 方式2：pipx（隔离环境，推荐）
    if command -v pipx &>/dev/null; then
        info "检测到 pipx，使用 pipx 安装..."
        if pipx install --force "$REPO_URL" 2>/dev/null; then
            success "lccg 安装完成（via pipx）"
            return 0
        fi
        warn "pipx install 失败，尝试其他方式..."
    fi

    # 方式3：pip（兼容传统环境）
    info "使用 pip 安装..."
    if $PYTHON_CMD -m pip install --force-reinstall --no-cache-dir "$REPO_URL" 2>/dev/null; then
        success "lccg 安装完成（via pip）"
        return 0
    fi

    # 方式4：pip + --break-system-packages（PEP 668 兼容）
    info "检测到受管理的 Python 环境，尝试 --break-system-packages..."
    if $PYTHON_CMD -m pip install --force-reinstall --no-cache-dir --break-system-packages "$REPO_URL" 2>/dev/null; then
        success "lccg 安装完成（via pip --break-system-packages）"
        return 0
    fi

    # 所有方式都失败
    error "lccg 安装失败"
    error "请尝试以下方式手动安装："
    error "  方式1: uv tool install $REPO_URL"
    error "  方式2: pipx install $REPO_URL"
    error "  方式3: pip install --break-system-packages $REPO_URL"
    info "排查建议:"
    info "  1. 确保网络可以访问 GitHub"
    info "  2. 尝试使用代理: export https_proxy=http://your-proxy:port"
    info "  3. 检查 Python 版本: $PYTHON_CMD --version"
    exit 1
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
            warn "npm 未找到，请先安装 Node.js"
            info "  下载地址: https://nodejs.org/"
            info "  或使用 brew: brew install node"
            info "  安装 Node.js 后，手动运行:"
            info "    npm install -g @anthropic-ai/claude-code"
        else
            if npm install -g @anthropic-ai/claude-code 2>/dev/null; then
                success "Claude Code 安装完成"
            else
                warn "Claude Code 安装失败"
                info "请手动安装:"
                info "  npm install -g @anthropic-ai/claude-code"
                info "如果权限不足，尝试:"
                info "  sudo npm install -g @anthropic-ai/claude-code"
            fi
        fi
    fi
}

configure_env() {
    info "配置环境变量..."
    # Determine which profile file to use
    if [[ -n "$ZSH_VERSION" ]]; then
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

    # 使用标记注释检查是否已配置
    if grep -q "# LCCG Gateway" "$PROFILE" 2>/dev/null; then
        info "LCCG 环境变量已配置: $PROFILE"
    else
        cat >> "$PROFILE" << 'EOF'

# LCCG Gateway
export ANTHROPIC_BASE_URL=http://127.0.0.1:8765
EOF
        success "已添加到 $PROFILE"
        info "环境变量将在下次打开终端时生效"
        info "立即生效请运行: source $PROFILE"
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

    # 验证安装
    info "验证安装..."
    if $PYTHON_CMD -m lccg --version &>/dev/null; then
        success "lccg 安装验证通过"
    else
        warn "lccg 命令验证失败，请检查 Python PATH"
    fi

    echo ""
    success "安装完成！"
    echo ""
    echo -e "  ${GREEN}推荐使用:${NC}"
    echo -e "    lccg code              一键启动网关 + Claude Code"
    echo ""
    echo -e "  ${GREEN}手动管理:${NC}"
    echo -e "    lccg serve             启动网关"
    echo -e "    lccg status            查看网关状态"
    echo -e "    lccg stop              停止后台网关"
    echo ""
    echo -e "  编辑配置:      ${GREEN}~/.lccg/config.yaml${NC}"
    echo ""
    echo -e "  ${YELLOW}重要: 请编辑 ~/.lccg/config.yaml 添加你的 Provider API Key${NC}"
    echo -e "  ${YELLOW}提示: lccg code 会自动处理 ANTHROPIC_API_KEY，无需手动设置${NC}"
    echo ""
    echo -e "  文档: https://github.com/whoknowszy/local-claude-code"
    echo ""
}

main
