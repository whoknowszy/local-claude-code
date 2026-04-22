# 安装与更新

LCCG 支持两种安装路径：

1. 源码安装：把 Git 仓库克隆到固定目录，然后用 editable install 安装 Python 命令。
2. wheel 安装：直接从 GitHub Release wheel 安装，不克隆源码。

默认仍然使用源码安装，便于本地更新和调试：

- macOS / Linux / Git Bash: `~/.lccg/source`
- Windows PowerShell: `%USERPROFILE%\.lccg\source`

后续只需要运行 `lccg update`，它会在这个源码目录里执行 `git pull --ff-only origin main`，再重新执行 `pip install -e`。
安装和更新结束时会打印实际源码版本，例如 `main@bb908cd`、提交时间和提交说明。

wheel 安装适合不想保留源码目录的用户。它依赖项目已发布 GitHub Release wheel，默认会自动选择最高稳定版本的 wheel；升级方式是重新运行 wheel 安装命令，或手动执行 `pip install --upgrade <wheel-url>`。

## 前提条件

- Python 3.9 或更高版本
- Git
- 网络可访问 GitHub

## macOS / Linux

一键安装：

```bash
curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash
```

wheel 安装：

```bash
curl -sL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.sh | bash -s -- --wheel
```

指定 wheel URL：

```bash
LCCG_WHEEL_URL=https://github.com/whoknowszy/local-claude-code/releases/download/v0.5.0/lccg-0.5.0-py3-none-any.whl \
  bash install.sh --wheel
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

wheel 安装：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1))) -InstallMode wheel
```

如果公司网络或执行策略不允许远程脚本直接执行，可以先下载再运行：

```powershell
irm https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/install.ps1 -OutFile install.ps1
.\install.ps1 -InstallMode wheel
```

指定 wheel URL：

```powershell
$env:LCCG_WHEEL_URL = "https://github.com/whoknowszy/local-claude-code/releases/download/v0.5.0/lccg-0.5.0-py3-none-any.whl"
.\install.ps1 -InstallMode wheel
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
