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

install_lccg() {
    local INSTALL_DIR="$HOME/.local/bin"
    local INSTALL_PATH="$INSTALL_DIR/lccg"

    # 提取版本号
    local VERSION
    VERSION=$(curl -sL "https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/pyproject.toml" | grep '^version' | head -1 | sed 's/.*"\(.*\)".*/\1/')
    if [[ -z "$VERSION" ]]; then
        error "无法获取版本号"
        exit 1
    fi
    info "最新版本: v${VERSION}"

    # 检测平台
    local PLATFORM
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64)  PLATFORM="linux-x64" ;;
        Darwin-arm64)  PLATFORM="macos-arm64" ;;
        Darwin-x86_64) PLATFORM="macos-arm64" ;;  # macOS x64 也使用 arm64 版本（Rosetta 兼容）
        *)
            error "不支持的平台: $(uname -s)-$(uname -m)"
            info "请使用 pip install 手动安装: pip install git+https://github.com/whoknowszy/local-claude-code.git"
            exit 1
            ;;
    esac

    # 下载 lccg.pyz
    local DOWNLOAD_URL="https://github.com/whoknowszy/local-claude-code/releases/download/v${VERSION}/lccg-${PLATFORM}.pyz"
    info "下载 lccg v${VERSION} (${PLATFORM})..."

    mkdir -p "$INSTALL_DIR"

    if command -v curl &>/dev/null; then
        if ! curl -fSL "$DOWNLOAD_URL" -o "$INSTALL_PATH"; then
            error "下载失败: $DOWNLOAD_URL"
            info "排查建议:"
            info "  1. 确保网络可以访问 GitHub"
            info "  2. 尝试使用代理: export https_proxy=http://your-proxy:port"
            info "  3. 手动下载: $DOWNLOAD_URL"
            exit 1
        fi
    elif command -v wget &>/dev/null; then
        if ! wget -q "$DOWNLOAD_URL" -O "$INSTALL_PATH"; then
            error "下载失败: $DOWNLOAD_URL"
            exit 1
        fi
    else
        error "需要 curl 或 wget"
        exit 1
    fi

    chmod +x "$INSTALL_PATH"
    success "lccg v${VERSION} 安装完成 → $INSTALL_PATH"
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

# 请在此添加你的 Provider，例如:
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
    local LOCAL_BIN="$HOME/.local/bin"

    # Determine which profile file to use
    if [[ -n "$ZSH_VERSION" ]] || [[ -f "$HOME/.zshrc" ]]; then
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

    # 检查 ~/.local/bin 是否在 PATH 中
    if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
        # 使用标记注释检查是否已配置
        if grep -q "# LCCG Gateway - PATH" "$PROFILE" 2>/dev/null; then
            info "PATH 配置已存在于 $PROFILE"
        else
            cat >> "$PROFILE" << 'EOF'

# LCCG Gateway - PATH
export PATH="$HOME/.local/bin:$PATH"
EOF
            success "已添加 ~/.local/bin 到 PATH ($PROFILE)"
            info "PATH 配置将在下次打开终端时生效"
            info "立即生效请运行: source $PROFILE"
        fi
    else
        success "~/.local/bin 已在 PATH 中"
    fi

    # 配置 ANTHROPIC_BASE_URL
    if grep -q "# LCCG Gateway - ANTHROPIC" "$PROFILE" 2>/dev/null; then
        info "ANTHROPIC_BASE_URL 已配置: $PROFILE"
    else
        cat >> "$PROFILE" << 'EOF'

# LCCG Gateway - ANTHROPIC
export ANTHROPIC_BASE_URL=http://127.0.0.1:8765
EOF
        success "已添加 ANTHROPIC_BASE_URL 到 $PROFILE"
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
    install_lccg
    create_config
    detect_and_install_claude
    configure_env

    # 验证安装
    info "验证安装..."
    if command -v lccg &>/dev/null; then
        success "验证通过: $(lccg --version 2>/dev/null || echo 'lccg 已安装')"
    else
        warn "lccg 已安装到 $HOME/.local/bin/lccg，但不在当前 PATH 中"
        warn "请运行: export PATH=\"\$HOME/.local/bin:\$PATH\""
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
