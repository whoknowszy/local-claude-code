#!/bin/bash
# ⚠️ 已废弃：请改用 lccg code 命令
# lccg code 会自动启动网关并注入环境变量
# 本脚本仅保留用于向后兼容
# 在项目目录下运行此脚本，会自动使用本地 LCCG 代理
export ANTHROPIC_BASE_URL=http://127.0.0.1:8765
export ANTHROPIC_API_KEY="sk-placeholder"
claude "$@"
