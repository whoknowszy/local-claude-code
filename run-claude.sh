#!/bin/bash
# 在项目目录下运行此脚本，会自动使用本地 LCCG 代理
export ANTHROPIC_BASE_URL=http://127.0.0.1:8765
export ANTHROPIC_API_KEY="sk-placeholder"
export ANTHROPIC_MODEL="MiniMax-M2.7"
claude "$@"
