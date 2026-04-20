# 安装与更新

LCCG 现在以 Git 仓库作为本地更新源安装，不再依赖 GitHub Release、pyz 包、pipx 或 uv tool。

安装脚本会把源码克隆到固定目录，然后用 editable install 安装 Python 命令：

- macOS / Linux / Git Bash: `~/.lccg/source`
- Windows PowerShell: `%USERPROFILE%\.lccg\source`

后续只需要运行 `lccg update`，它会在这个源码目录里执行 `git pull --ff-only origin main`，再重新执行 `pip install -e`。

## 前提条件

- Python 3.9 或更高版本
- Git
- 网络可访问 GitHub

## macOS / Linux

一键安装：

```bash
curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash
```

本地仓库安装：

```bash
git clone https://github.com/whoknowszy/local-claude-code.git
cd local-claude-code
bash install.sh
```

更新：

```bash
lccg update
```

也可以直接运行脚本：

```bash
bash ~/.lccg/source/tools/update.sh
```

## Windows

PowerShell 一键安装：

```powershell
irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1 | iex
```

本地仓库安装：

```powershell
git clone https://github.com/whoknowszy/local-claude-code.git
cd local-claude-code
.\install.ps1
```

更新：

```powershell
lccg update
```

也可以直接运行脚本：

```powershell
& "$HOME\.lccg\source\tools\update.ps1"
```

如果 PowerShell 执行策略阻止本地脚本，可以先运行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 配置

安装脚本会创建配置文件：

```text
~/.lccg/config.yaml
```

请编辑这个文件添加 Provider API Key。安装脚本也会把 `ANTHROPIC_BASE_URL` 指向本地网关：

```text
http://127.0.0.1:8765
```

## 使用

推荐：

```bash
lccg code
```

手动管理：

```bash
lccg serve
lccg status
lccg stop
```

启动后访问：

```text
http://127.0.0.1:8765/ui/
```
