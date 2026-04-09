# Implementation Plan: Claude Code 本地模型网关代理 (LCCG)

## Requirements

构建一个 Python 实现的本地模型网关代理，让 Claude Code 通过 `ANTHROPIC_BASE_URL` 指向本地代理来统一接入多个第三方 Anthropic 兼容模型厂商。

**核心目标：**
1. 完全兼容 Anthropic Messages API — Claude Code 无感切换，支持 streaming、tool_use、thinking
2. 统一多模型入口 — 支持原生 Anthropic 格式厂商直通 + OpenAI 格式厂商协议转换
3. 配置驱动 + 智能路由 + 可扩展的 Transformer 插件系统
4. 分阶段交付，参考 claude-code-router 的成熟设计

**技术约束：** Python 3.11+, ANTHROPIC_BASE_URL 接入

---

## Architecture

```
Claude Code (ANTHROPIC_BASE_URL=http://127.0.0.1:8765, ANTHROPIC_API_KEY=sk-placeholder)
        │
        │ POST /v1/messages (Anthropic 格式)
        ▼
┌──────────────────────────────────────────────┐
│          Gateway Server (FastAPI)             │
│  ┌────────────────────────────────────────┐  │
│  │  Auth Middleware (x-api-key 校验)       │  │
│  └──────────────┬─────────────────────────┘  │
│                 ▼                             │
│  ┌────────────────────────────────────────┐  │
│  │  Router (路由决策层)                     │  │
│  │  - 根据 model → provider 映射            │  │
│  │  - 默认回退到 router.default             │  │
│  │  - (Phase 3) context 长度 / 任务类型     │  │
│  └──────────────┬─────────────────────────┘  │
│                 ▼                             │
│  ┌────────────────────────────────────────┐  │
│  │  Transformer (协议转换层)                │  │
│  │  ┌──────────┐  ┌─────────────────────┐ │  │
│  │  │ Anthropic │  │ OpenAI Compatible  │ │  │
│  │  │ PassThru  │  │ Request/Response   │ │  │
│  │  │ (直通)    │  │ Transformer        │ │  │
│  │  │ +字段清理  │  │ (Phase 2)          │ │  │
│  │  └──────────┘  └─────────────────────┘ │  │
│  └──────────────┬─────────────────────────┘  │
│                 ▼                             │
│  ┌────────────────────────────────────────┐  │
│  │  Provider Client (HTTP 传输层)          │  │
│  │  - httpx 异步请求 / SSE 流式转发        │  │
│  │  - auth_scheme: x-api-key / bearer      │  │
│  └────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   MiniMax    OpenRouter   Ollama ...
   (Anthropic) (OpenAI)   (OpenAI)
```

**核心模块：**

| 模块 | 职责 | 关键文件 |
|------|------|----------|
| `server` | FastAPI 应用，/v1/messages + /v1/stats + /health | `app.py` (332 行) |
| `router` | 场景路由 + token 计数 + fallback | `engine.py` + `token_counter.py` |
| `transformer` | Anthropic↔OpenAI 双向转换 + 流式 SSE | `openai_convert.py` (552 行) |
| `provider` | Anthropic/OpenAI 客户端 + 注册 + 健康检查 | 5 个文件 |
| `middleware` | 请求统计收集 | `stats.py` |
| `config` | YAML 配置加载 + 环境变量替换 | `schema.py` + `loader.py` |
| `cli` | 命令行入口 + 会话级日志 | `main.py` (319 行) |

---

## Tech Stack

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 原生异步、SSE 友好、类型校验内置 |
| SSE 流式 | sse-starlette | FastAPI 生态标准 SSE 库 |
| HTTP 客户端 | httpx | 异步、连接池、SSE 流式读取 |
| 配置管理 | pydantic-settings + YAML | 类型安全 + 人可读 |
| CLI | click + rich | 成熟 CLI 框架 + 终端美化 |
| 日志 | structlog | 结构化日志，JSON 输出 |
| Token 计算 | tiktoken (Phase 3) | 与 claude-code-router 一致 |
| 打包发布 | uv + pyproject.toml | 现代 Python 包管理 |
| 最低 Python | 3.11+ | TaskGroup、性能改进 |

---

## Implementation Phases

### Phase 1: MVP — Anthropic 直通代理（核心可用）✅ COMPLETE

**目标：** 能用 Claude Code 通过代理调用原生 Anthropic 格式的厂商（如 MiniMax）

| 步骤 | 任务 | 产出 | 状态 |
|------|------|------|------|
| 1.1 | 项目初始化：pyproject.toml、目录结构、基础依赖 | 项目骨架 | ✅ |
| 1.2 | 配置系统：YAML 配置加载 + Pydantic 校验 + 环境变量替换 | `config/` 模块 | ✅ |
| 1.3 | FastAPI 服务：`POST /v1/messages` 端点 + Auth 中间件 | `server/app.py` | ✅ |
| 1.4 | Anthropic 直通 Transformer：请求转发 + 不兼容字段清理 | `transformer/anthropic_passthru.py` | ✅ |
| 1.5 | SSE 流式转发：逐事件透传上游 SSE 流 | `server/app.py` `_handle_streaming()` | ✅ |
| 1.6 | CLI 入口：`lccg serve` 启动命令 + provider 连通性验证 | `cli/main.py` | ✅ |
| 1.7 | 端到端验证：Claude Code → 代理 → MiniMax | 24 个单元测试 + 手动测试 | ✅ |

**验收标准（已满足）：** `ANTHROPIC_BASE_URL=http://127.0.0.1:8765 claude` 能正常使用 MiniMax 完成基本对话和工具调用。

**Phase 1 实现要点（超出原计划）：**
- `ProviderConfig` 增加 `auth_scheme` 字段（`x-api-key` | `bearer`），适配 MiniMax 的 Bearer 认证
- `AnthropicPassthruTransformer` 增加字段清理：移除 `output_config`/`metadata`，`system` 数组→字符串，`temperature` 整数→浮点
- 启动时自动发送 `hello world` 验证每个 provider 连通性
- 日志输出 provider API Key 状态（脱敏显示）
- SSE 流式转发内联在 `server/app.py`（而非独立模块）

### Phase 2: OpenAI 兼容转换层 ✅ COMPLETE

**目标：** 支持仅提供 OpenAI 格式的厂商（OpenAI Codex、OpenRouter、Together AI 等）

| 步骤 | 任务 | 产出 | 状态 |
|------|------|------|------|
| 2.1 | BaseTransformer 添加 transform_stream 方法 | `transformer/base.py` | ✅ |
| 2.2 | OpenAI Provider 客户端 | `provider/openai_provider.py` | ✅ |
| 2.3 | Anthropic↔OpenAI 双向转换器（请求/响应/流式） | `transformer/openai_convert.py` | ✅ |
| 2.4 | Provider 注册 + Transformer 自动选择 | `provider/registry.py` | ✅ |
| 2.5 | Server 动态 transformer + 流式转换 | `server/app.py` | ✅ |

**验收标准（待验证）：** 能通过代理使用 OpenAI Codex 的模型完成对话和工具调用。

**Phase 2 实现要点：**
- 合并为单文件 `openai_convert.py`，请求/响应/流式转换共享常量
- `transform_stream` 用状态机 `_StreamState` 实现 OpenAI SSE → Anthropic SSE
- 流式 thinking: `delta.reasoning_content` → thinking content block + signature
- 流式 tool_calls: 累积 arguments delta → `input_json_delta`
- registry 新增 `get_transformer_for_provider()` 按 provider type 返回对应 transformer

### Phase 3: 智能路由 + 多 Provider ✅ COMPLETE

| 步骤 | 任务 | 产出 | 状态 |
|------|------|------|------|
| 3.1 | Token 计算：tiktoken cl100k_base | `router/token_counter.py` | ✅ |
| 3.2 | RouterConfig 增加 fallback 字段 | `config/schema.py` | ✅ |
| 3.3 | 场景路由决策树：longContext/background/webSearch/think | `router/engine.py` | ✅ |
| 3.4 | Provider 健康检查 | `provider/health.py` | ✅ |
| 3.5 | Server fallback + health 集成 | `server/app.py` | ✅ |

### Phase 4: 增强功能 ⬜ 部分完成

| 步骤 | 任务 | 产出 | 状态 |
|------|------|------|------|
| 4.1 | 请求日志 + 用量统计 | `middleware/stats.py` | ✅ |
| 4.2 | 响应缓存（基于请求 hash） | `middleware/cache.py` | ⬜ |
| 4.3 | CLI 状态查看：`lccg status` | `cli/main.py` status() + `GET /v1/stats` | ✅ |
| 4.4 | 配置热更新（SIGHUP 重载） | `config/hot_reload.py` | ⬜ |
| 4.5 | Transformer 链式管道 | `BaseTransformer` 改为可组合链，支持多 transformer 叠加 | ⬜ |
| 4.6 | Per-Model Transformers | `ProviderConfig` 增加 `transformers` 字段，支持全局 + per-model 两级 | ⬜ |
| 4.7 | `sampling` transformer | 钳制 temperature/top_p/max_tokens/top_k/repetition_penalty | ⬜ |
| 4.8 | `clean_cache` transformer | 移除消息中的 `cache_control` 字段 | ⬜ |
| 4.9 | Per-Scenario Fallback | fallback 按场景配置（default/think/longContext 等），支持多备选按序尝试 | ⬜ |
| 4.10 | 健康检查端点 `GET /health` | `server/app.py` | ✅ |
| 4.11 | 会话级日志文件 + 自动轮转 | `cli/main.py` _setup_logging() | ✅ |

**Phase 4 实现要点：**
- `middleware/stats.py` — 线程安全的 `StatsCollector`，记录每次请求的 provider/model/latency/tokens
- `GET /v1/stats` 端点 — 返回汇总统计 + per-provider 统计 + 最近 10 条请求
- `lccg status` CLI — 通过 HTTP 查询 `/v1/stats`，Rich 表格展示
- 日志系统 — 每次启动生成 `lccg-{YYYYMMDDHHmmss}.log`，50MB 轮转，保留 3 个，JSON 格式写文件 + 彩色输出控制台
- 流式 SSE usage 提取 — `_extract_streaming_usage()` 解析 Anthropic/OpenAI 格式的 token 用量

---

## Key Technical Challenges

### 1. SSE 流式转发
- 使用 httpx `async_stream` + `aiter_bytes()` 逐 chunk 读取上游 SSE
- 通过 `sse-starlette` `EventSourceResponse` 转发给 Claude Code

### 2. OpenAI → Anthropic 流式格式转换
- 维护 `StreamState` 状态机：message_start → content_block_start → N×delta → stop → message_delta → message_stop
- 首个 chunk 发 message_start + content_block_start
- [DONE] 发 content_block_stop + message_delta + message_stop

### 3. Tool Use 格式差异
- 维护 tool_use_id 映射表
- 请求：input_schema → function.parameters，tool_choice 类型映射
- 响应：tool_calls[].function → tool_use block

### 4. Extended Thinking 转换
- Anthropic 直通：不处理
- OpenAI 兼容：reasoning_content → thinking block，signature 省略

---

## Risks

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 流式转换状态机复杂度 | HIGH | 从 text-only 开始，逐步增加 tool_use/thinking |
| 各厂商 API 行为差异 | MEDIUM | 统一错误处理，逐步增加厂商适配 |
| Claude Code API 变更 | MEDIUM | 关注 claude-code-router 兼容更新 |
| 流式 tool_use JSON 增量拼接 | MEDIUM | 增量尝试 json.loads，失败则累积 |

---

## Config Schema

```yaml
server:
  host: "127.0.0.1"
  port: 8765
  # api_key: "proxy-auth-key"  # 可选，给代理本身加认证

logging:
  level: "info"                  # debug | info | warning | error
  log_dir: "~/.lccg/logs"        # 日志目录，每次启动生成 lccg-{时间戳}.log

providers:
  - name: minimax
    type: anthropic
    base_url: "https://api.minimaxi.com/anthropic/v1/messages"
    api_key: "sk-cp-..."
    auth_scheme: "bearer"        # "x-api-key"(默认) | "bearer"
    models:
      - "MiniMax-M2.7"

  - name: openai
    type: openai
    base_url: "https://api.openai.com/v1/chat/completions"
    api_key: "sk-..."
    models:
      - "gpt-4o"

  # - name: openrouter
  #   type: openai
  #   base_url: "https://openrouter.ai/api/v1/chat/completions"
  #   api_key: "${OPENROUTER_API_KEY}"
  #   models:
  #     - "anthropic/claude-sonnet-4-5"
  #     - "deepseek/deepseek-r1"

router:
  default: "minimax,MiniMax-M2.7"
  # background: "openai,gpt-4o-mini"
  # think: "openrouter,deepseek/deepseek-r1"
  # long_context: "openai,gpt-4o"
  # long_context_threshold: 60000
  # fallback: "minimax,MiniMax-M2.7"
```

**配置文件位置：** `~/.lccg/config.yaml`

**ProviderConfig 字段说明：**
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| name | string | 必填 | Provider 名称 |
| type | enum | 必填 | `anthropic` | `openai` |
| base_url | string | 必填 | API 端点 URL |
| api_key | string | null | API 密钥，支持 `${ENV_VAR}` 语法 |
| auth_scheme | string | "x-api-key" | 认证方式：`x-api-key`（Anthropic 标准）或 `bearer`（Authorization: Bearer） |
| models | list | [] | 该 provider 支持的模型列表 |
| headers | dict | {} | 额外请求头 |
| timeout | int | 600 | 请求超时（秒） |

**RouterConfig 字段说明：**
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| default | string | null | 默认路由 `"provider,model"` |
| background | string | null | claude-haiku 变体的路由 |
| think | string | null | thinking enabled 的路由 |
| long_context | string | null | 大上下文路由 |
| long_context_threshold | int | 60000 | 长上下文 token 阈值 |
| web_search | string | null | web_search 工具的路由 |
| fallback | string | null | 全局 fallback `"provider,model"` |

## Project Structure

```
local-claude-code/                     # ~2,200 行源码，54 个测试
├── PLAN.md                            # 本文件
├── pyproject.toml                     # 项目配置 + 依赖
├── config.example.yaml                # 示例配置
├── run-claude.sh                      # 启动 Claude Code（注入代理环境变量）
├── src/
│   └── lccg/
│       ├── __init__.py                # __version__ = "0.1.0"
│       ├── __main__.py                # python -m lccg 入口
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py                # CLI: lccg serve / lccg status（319 行）
│       ├── server/
│       │   ├── __init__.py
│       │   └── app.py                 # FastAPI: /health, /v1/stats, /v1/messages（332 行）
│       ├── router/
│       │   ├── __init__.py
│       │   ├── engine.py              # 场景路由：longContext/background/webSearch/think（128 行）
│       │   └── token_counter.py       # tiktoken cl100k_base token 估算（64 行）
│       ├── transformer/
│       │   ├── __init__.py
│       │   ├── base.py                # BaseTransformer + transform_stream（40 行）
│       │   ├── anthropic_passthru.py  # Anthropic 直通 + 字段清理（46 行）
│       │   └── openai_convert.py      # Anthropic↔OpenAI 双向转换（552 行）
│       ├── provider/
│       │   ├── __init__.py
│       │   ├── base.py                # BaseProvider（httpx 客户端管理）（67 行）
│       │   ├── anthropic_provider.py  # Anthropic provider（x-api-key/bearer）（111 行）
│       │   ├── openai_provider.py     # OpenAI provider（Bearer 认证）（107 行）
│       │   ├── registry.py            # Provider 注册 + Transformer 选择（89 行）
│       │   └── health.py              # Provider 健康检查（43 行）
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── stats.py               # 请求统计收集器（197 行）
│       └── config/
│           ├── __init__.py
│           ├── schema.py              # Pydantic 模型（55 行）
│           └── loader.py              # YAML 加载 + 环境变量替换（68 行）
└── tests/                             # 54 个测试，896 行
    ├── __init__.py
    ├── test_config.py                 # 8 个测试：配置加载、环境变量
    ├── test_provider/
    │   ├── __init__.py
    │   └── test_health.py             # 5 个测试：健康检查
    ├── test_router/
    │   ├── __init__.py
    │   ├── test_engine.py             # 6 个测试：路由逻辑
    │   └── test_token_counter.py      # 6 个测试：token 计数
    ├── test_server/
    │   ├── __init__.py
    │   └── test_messages.py           # 6 个测试：端点测试
    └── test_transformer/
        ├── __init__.py
        ├── test_openai_convert.py     # 19 个测试：请求/响应/流式转换
        └── test_passthru.py           # 4 个测试：Anthropic 直通
```

**CLI 命令：**
- `lccg serve [-c config] [--host] [--port] [--log-level]` — 启动网关服务
- `lccg status [--host] [--port]` — 查看运行状态和统计

**API 端点：**
- `GET /health` — 健康检查
- `GET /v1/stats` — 请求统计（汇总 + per-provider + 最近请求）
- `POST /v1/messages` — Anthropic Messages API（主端点）

---

## Changelog

- 2026-04-07: 初始方案创建，Phase 1 开始实施
- 2026-04-07: Phase 1 完成（24 个测试通过，MiniMax 端到端验证通过）
- 2026-04-07: 新增 `auth_scheme` 配置字段，适配 Bearer 认证
- 2026-04-07: 新增请求字段清理（output_config/metadata/system 数组→字符串）
- 2026-04-07: 新增 provider 连通性启动验证 + API Key 脱敏日志
- 2026-04-07: 分析 claude-code-router 源码，记录 9 个值得借鉴的设计模式
- 2026-04-07: Phase 2 完成 — OpenAI Provider + Anthropic↔OpenAI 双向转换（请求/响应/流式）
- 2026-04-07: Phase 3 完成 — 场景路由 + Token 计数 + Provider 健康检查 + Fallback
- 2026-04-07: 54 个测试全部通过（原 24 + 新增 30）
- 2026-04-07: Phase 4 部分完成 — 请求统计 (`middleware/stats.py`) + `lccg status` CLI + `GET /v1/stats` + 流式 usage 提取
- 2026-04-07: 日志系统 — 会话级日志文件 `lccg-{timestamp}.log`，50MB 轮转，保留 3 个，双输出（控制台彩色 + 文件 JSON）
- 2026-04-07: 文档全面更新，对齐 2,200 行源码实际实现
- 2026-04-08: Web UI 配置页面 — Server/Logging/Providers + Router 两列布局
- 2026-04-08: Web UI 配置页面 — 编辑/保存按钮移至顶部 header
- 2026-04-08: Web UI 配置页面 — Providers 表格 Base URL 字段压缩显示
- 2026-04-08: Web UI 配置页面 — 默认不可编辑，点击"编辑"进入编辑模式
- 2026-04-08: 日志输出优化（请求/响应增加 client_ip, scenario, latency, tokens 等字段）
- 2026-04-08: 请求追踪链路（request_id 贯穿 gateway/router/provider）、fallback 日志、payload 摘要
- 2026-04-08: 动态版本号（banner + --version 从 importlib.metadata 读取）
- 2026-04-08: 安装脚本（bash + PowerShell）、INSTALL.md 安装文档
- 2026-04-09: 首次启动自动创建默认配置，无需手动创建

---

## claude-code-router 源码分析：值得借鉴的设计

> 来源：/Users/zhangyi/myProject/claude-code-router (monorepo: core/server/cli/shared/ui)

### 1. Transformer 链式管道架构

claude-code-router 的 transformer 不是单个变换，而是**链式管道**，每个 transformer 独立职责：

```
请求方向（Inbound to Provider）：
  Anthropic格式 → transformRequestOut(格式转换) → provider级transformers → model级transformers → 发送

响应方向（Outbound to Client）：
  接收 → model级transformers(反序) → provider级transformers(反序) → transformResponseIn(格式还原) → Anthropic格式
```

**Transformer 接口定义：**
```typescript
type Transformer = {
  transformRequestIn?: (request, provider, context) => Promise<Record>;  // 统一格式 → provider格式
  transformRequestOut?: (request, context) => Promise<UnifiedChatRequest>; // 原始 → 统一格式
  transformResponseIn?: (response, context) => Promise<Response>;          // 统一格式 → 原始格式
  transformResponseOut?: (response, context) => Promise<Response>;         // provider → 统一格式
  endPoint?: string;    // 如 "/v1/messages"
  auth?: (request, provider, context) => Promise<any>;
};
```

**对我们的启示：** 当前 `AnthropicPassthruTransformer` 是单一变换，应改为支持链式组合。每个 transformer 只做一件事（清理字段、采样参数、token 限制等），通过配置串联。

### 2. Provider 配置支持 per-model transformers

```json
{
  "name": "openrouter",
  "transformer": {
    "use": ["openrouter"],                       // 全局 transformer
    "anthropic/claude-sonnet-4": {                // 特定 model 的 transformer
      "use": ["tooluse"]
    }
  }
}
```

**对我们的启示：** `ProviderConfig` 应增加 `transformers` 字段，支持全局 + per-model 两级配置。

### 3. 智能路由决策树

路由不仅按模型名，还按**请求特征**自动选择：

```
1. 解析 sessionId（metadata.user_id 中提取）
2. 检查项目级路由配置（per-project override）
3. 解析 provider,model 格式的模型名
4. 用 tiktoken 计算 token 数
5. 路由规则按优先级：
   a. token数 > longContextThreshold(默认60K) → longContext 路由
   b. system 含 CCR-SUBAGENT-MODEL 标签 → 指定模型
   c. claude-haiku 变体 → background 路由
   d. 含 web_search tools → webSearch 路由
   e. thinking enabled → think 路由
   f. 否则 → default 路由
```

**Token 计算：** 使用 tiktoken `cl100k_base` 编码，统计 messages + system + tools 的 token 数。

### 4. SSE 流式处理的关键模式

**Buffer 管理：**
```typescript
buffer += decoder.decode(value, { stream: true });
const lines = buffer.split("\n");
buffer = lines.pop() || "";  // 保留最后一个不完整行
```

**Safe Enqueue（防 controller 关闭后入队崩溃）：**
```typescript
const safeEnqueue = (data: Uint8Array) => {
  if (!isClosed) {
    try { controller.enqueue(data); }
    catch (e) { if (e.message.includes("closed")) isClosed = true; }
  }
};
```

**Content Block Index 原子递增：**
```typescript
let contentIndex = 0;
const assignIndex = (): number => contentIndex++;
```

### 5. Thinking/Reasoning 转换的三种策略

| 策略 | 适用场景 | 实现方式 |
|------|----------|----------|
| `reasoning_content` → `thinking` | OpenAI 格式 provider（主流） | 响应中 delta.reasoning_content 转为 thinking block |
| ForceReasoning | 不支持 reasoning 的 provider | prompt 注入 `<reasoning_content>` 标签，从响应中解析 |
| Anthropic 直通 | 原生 Anthropic provider | 原样透传 thinking block + signature |

### 6. Tool Use 转换细节

**请求方向：**
- Anthropic `tool_use` content block → OpenAI `tool_calls[].function`
- Anthropic `tool_result` content block → OpenAI `role: "tool"` + `tool_call_id`
- Anthropic `input_schema` → OpenAI `function.parameters`

**流式场景：**
- 累积 tool call 的 `arguments` delta 片段
- 完成时拼接并尝试 `json.loads`，发送完整 tool call

**ExitTool 机制：** 自动添加 `ExitTool` 给 Claude Code，用于安全退出 tool_use 模式。

### 7. 不兼容字段清理

第三方 Anthropic 兼容 provider 通常不支持的字段：
- `system` 为数组格式 → 需转为字符串
- `output_config`（含 json_schema）→ 需移除
- `metadata` → 需移除
- `cache_control` → 需移除（非 Claude 模型）
- `temperature` 整数 → 需转为 float

### 8. Fallback 机制

每个路由场景（default/background/think 等）可配置 fallback 模型。主模型失败时按顺序尝试 fallback，记录所有尝试日志。

### 9. Transformer 清单（按优先级）

| Transformer | 职责 | 优先级 | 状态 |
|-------------|------|--------|------|
| `anthropic_passthru` | Anthropic 直通 + 不兼容字段清理 | P0 | ✅ 已实现 |
| `openai_convert` | Anthropic ↔ OpenAI 双向转换（含 thinking + tool_use） | P0 | ✅ 已实现（合并为单文件） |
| `sampling` | 温度/top_p/max_tokens 钳制 | P1 | ⬜ |
| `clean_cache` | 移除 cache_control | P1 | ⬜ |
| `force_reasoning` | prompt 注入式 thinking | P3 | ⬜ |
