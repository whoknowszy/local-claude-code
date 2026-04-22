#!/usr/bin/env bash
# LCCG Gateway 一键安装脚本 - macOS / Linux / Git Bash
# 用法:
#   一键安装: curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash
#   wheel 安装: curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash -s -- --wheel
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
REPO_URL="https://github.com/whoknowszy/local-claude-code.git"
RELEASE_API_URL="https://api.github.com/repos/whoknowszy/local-claude-code/releases/latest"
INSTALL_MODE="${LCCG_INSTALL_MODE:-source}"

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --wheel)
                INSTALL_MODE="wheel"
                shift
                ;;
            --source)
                INSTALL_MODE="source"
                shift
                ;;
            -h|--help)
                echo "Usage: install.sh [--source|--wheel]"
                echo "  --source  clone ~/.lccg/source and install editable package (default)"
                echo "  --wheel   install release wheel without cloning source"
                exit 0
                ;;
            *)
                error "未知参数: $1"
                exit 1
                ;;
        esac
    done
}

print_source_version() {
    local src_dir="$1"
    if [[ ! -d "$src_dir/.git" ]]; then
        warn "源码版本不可用: $src_dir 不是 Git 仓库"
        return
    fi

    local branch commit commit_time subject
    branch=$(git -C "$src_dir" rev-parse --abbrev-ref HEAD)
    commit=$(git -C "$src_dir" rev-parse --short HEAD)
    commit_time=$(git -C "$src_dir" log -1 --format='%ci')
    subject=$(git -C "$src_dir" log -1 --format='%s')

    success "源码版本: ${branch}@${commit}"
    info "提交时间: ${commit_time}"
    info "提交说明: ${subject}"
}

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
    if [[ "$INSTALL_MODE" == "wheel" ]]; then
        install_lccg_wheel
    elif [[ "$INSTALL_MODE" == "source" ]]; then
        install_lccg_source
    else
        error "未知安装模式: $INSTALL_MODE，请使用 --source 或 --wheel"
        exit 1
    fi

    install_lccg_command_shim
}

install_lccg_command_shim() {
    local LOCAL_BIN="$HOME/.local/bin"
    local SHIM="$LOCAL_BIN/lccg"
    local PYTHON_EXE

    PYTHON_EXE=$($PYTHON_CMD -c 'import sys; print(sys.executable)')
    mkdir -p "$LOCAL_BIN"
    if [[ -e "$SHIM" || -L "$SHIM" ]]; then
        rm -f "$SHIM"
    fi
    cat > "$SHIM" << EOF
#!/usr/bin/env bash
exec "$PYTHON_EXE" -m lccg "\$@"
EOF
    chmod +x "$SHIM"
    success "lccg 命令入口已更新: $SHIM"
}

install_lccg_wheel() {
    local VERSION WHEEL_URL wheel_url
    VERSION="${LCCG_VERSION:-latest}"

    if [[ -n "${LCCG_WHEEL_URL:-}" ]]; then
        WHEEL_URL="$LCCG_WHEEL_URL"
    elif [[ "$VERSION" == "latest" ]]; then
        WHEEL_URL="$(resolve_latest_wheel_url)" || {
            error "未找到 latest release wheel，请确认 GitHub Release 已发布 wheel，或设置 LCCG_WHEEL_URL"
            exit 1
        }
    else
        WHEEL_URL="https://github.com/whoknowszy/local-claude-code/releases/download/v${VERSION}/lccg-${VERSION}-py3-none-any.whl"
    fi
    wheel_url="$WHEEL_URL"

    info "使用 wheel 安装 lccg: $wheel_url"
    $PYTHON_CMD -m pip install --upgrade "$wheel_url" || {
        error "wheel 安装失败，请确认 release wheel 已发布，或改用源码安装: bash install.sh --source"
        exit 1
    }

    local INSTALLED_VERSION
    INSTALLED_VERSION=$($PYTHON_CMD -c "import importlib.metadata; print(importlib.metadata.version('lccg'))" 2>/dev/null || echo "unknown")
    success "lccg v${INSTALLED_VERSION} wheel 安装完成"
}

resolve_latest_wheel_url() {
    $PYTHON_CMD - "$RELEASE_API_URL" <<'PY'
import json
import sys
import urllib.request

api_url = sys.argv[1]
request = urllib.request.Request(
    api_url,
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "lccg-installer",
    },
)

with urllib.request.urlopen(request, timeout=30) as response:
    release = json.load(response)

for asset in release.get("assets", []):
    name = asset.get("name", "")
    if name.startswith("lccg-") and name.endswith("-py3-none-any.whl"):
        print(asset["browser_download_url"])
        raise SystemExit(0)

raise SystemExit(1)
PY
}

install_lccg_source() {
    if ! command -v git &>/dev/null; then
        error "未找到 Git，请先安装 Git 后重试"
        if [[ "$OS" == "Darwin" ]]; then
            info "macOS 推荐: xcode-select --install 或 brew install git"
        fi
        exit 1
    fi

    # 判断本地源码目录是否可用（curl 管道执行时 $0 不是真实路径）
    local SRC_DIR
    SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || SRC_DIR=""
    if [[ -z "$SRC_DIR" || ! -f "$SRC_DIR/pyproject.toml" ]]; then
        # 远程执行：clone 仓库后本地安装
        local CLONE_DIR="$HOME/.lccg/source"
        info "远程执行模式，克隆仓库到 $CLONE_DIR ..."
        if [[ -d "$CLONE_DIR/.git" ]]; then
            info "仓库已存在，拉取最新..."
            git -C "$CLONE_DIR" pull --ff-only origin main
        else
            if [[ -e "$CLONE_DIR" ]]; then
                error "$CLONE_DIR 已存在但不是 Git 仓库，请先移动或删除该目录后重试"
                exit 1
            fi
            git clone "$REPO_URL" "$CLONE_DIR"
        fi
        SRC_DIR="$CLONE_DIR"
    fi

    info "从本地源码安装 lccg: $SRC_DIR"
    $PYTHON_CMD -m pip install -e "$SRC_DIR" || {
        error "pip 安装失败，请手动运行: pip install -e ."
        exit 1
    }

    # 提取版本号用于显示
    local VERSION
    VERSION=$($PYTHON_CMD -c "import importlib.metadata; print(importlib.metadata.version('lccg'))" 2>/dev/null || echo "0.5.0")
    success "lccg v${VERSION} 安装完成"
    print_source_version "$SRC_DIR"
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
    echo ""
    echo -e "${CYAN}  _   _                       _   _             "
    echo -e " | \\ | | _____      _____ _ __| | | | ___  _   _ "
    echo -e " |  \\| |/ _ \\ \\ /\\ / / _ \\ '__| |_| |/ _ \\| | | |"
    echo -e " |_|\\  |  __/\\ V  V /  (__| |  |  _  | (_) | |_| |"
    echo -e "   |__/\\___| \\_/\\\_/ \\___|_|  |_| |_|\\___/ \\__, |"
    echo -e "                                            |___/  "
    echo -e "${NC}Local Claude Code Gateway"
    echo ""
}

main() {
    parse_args "$@"
    print_banner
    detect_python
    install_lccg
    create_config
    detect_and_install_claude
    configure_env

    # 验证安装
    info "验证安装..."
    local VERIFY_VERSION
    if VERIFY_VERSION=$($PYTHON_CMD -m lccg --version 2>/dev/null); then
        success "验证通过: ${VERIFY_VERSION}"
    elif command -v lccg &>/dev/null; then
        success "lccg 命令可用: $(command -v lccg)"
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

main "$@"
