# 安装指南

## 前提条件

- Python 3.9 或更高版本
- 网络可访问 GitHub（`github.com`）

---

## macOS / Linux

### 方式一：一键安装（推荐）

```bash
curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash
```

### 方式二：逐行执行

```bash
# 1. 确保 Python 3.9+ 已安装
python3 --version

# 2. 安装 lccg（从 GitHub 最新代码）
pip install --force-reinstall --no-cache-dir --no-deps git+https://github.com/whoknowszy/local-claude-code.git@main

# 3. 验证安装
lccg --version
```

### 方式三：pipx 安装（适合多项目隔离）

```bash
# 如果系统已安装 pipx
pipx install git+https://github.com/whoknowszy/local-claude-code.git@main

# 后续更新
pipx upgrade lccg
```

---

## Windows

### 方式一：一键安装（PowerShell，推荐）

```powershell
irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1 | iex
```

> 如果遇到执行策略限制，运行：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> 然后重新执行上述命令。

### 方式二：逐行执行（PowerShell）

```powershell
# 1. 确保 Python 3.9+ 已安装
python --version

# 2. 安装 lccg（从 GitHub 最新代码）
pip install --force-reinstall --no-cache-dir --no-deps git+https://github.com/whoknowszy/local-claude-code.git@main

# 3. 验证安装
lccg --version
```

### 方式三：Git clone 后本地安装

```bash
# clone 仓库
git clone https://github.com/whoknowszy/local-claude-code.git
cd local-claude-code

# 运行安装脚本
bash install.sh      # macOS/Linux Git Bash
.\install.ps1        # Windows PowerShell
```

---

## 首次配置

安装完成后，创建配置文件：

```bash
lccg serve
```

首次启动会自动在 `~/.lccg/config.yaml` 创建默认配置。请编辑配置文件添加你的 Provider API Key。

---

## 更新

每次代码更新后，重新执行安装命令即可覆盖更新：

```bash
# macOS/Linux
curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1 | iex
```

---

## 使用

### 推荐：一键启动

```bash
lccg code
```

自动完成以下操作：
- 检测网关是否已运行（避免端口冲突）
- 启动网关（如需要）
- 注入环境变量（无需手动 export）
- 启动 Claude Code

### 手动管理网关

```bash
# 启动网关
lccg serve

# 查看状态
lccg status

# 停止后台网关
lccg stop
```

启动后访问 http://127.0.0.1:8765/ui/ 查看仪表盘。

### 传统方式（已废弃）

如需手动设置环境变量：

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8765
```

> 注意：使用 `lccg code` 时无需手动设置环境变量，命令会自动处理。
