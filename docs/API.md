# 后端 API 文档

Afterglow 后端是一个 FastAPI 服务。主要集成入口是 OpenAI 兼容的
`/v1/chat/completions`；其它接口用于主动发起话题、记忆调试、本地初始化、
表情包、图片、文档提取和诊断。

默认地址：

```text
http://127.0.0.1:8000
```

默认强制 API key 鉴权。除 `/healthz` 存活检查外，其它接口都需要先在后端
`.env` 设置 `XUWEN_API_KEY`，并在请求里带以下任一鉴权头：

```http
Authorization: Bearer <XUWEN_API_KEY>
x-api-key: <XUWEN_API_KEY>
```

如果 `API_AUTH_REQUIRED=true` 但没有配置 `XUWEN_API_KEY`，受保护接口会返回
`503 xuwen.auth_config`。`API_AUTH_REQUIRED=false` 只建议纯本地开发/测试时临时使用。

所有请求都会带响应头 `x-request-id`。聊天、记忆检索和主动话题接口还会在响应体里返回
`trace_id`，用于在 `/debug/stats` 里追踪完整模型调用链路。

## 核心接口

### `POST /v1/chat/completions`

OpenAI 兼容聊天接口，也是第三方程序最应该接入的主接口。

相比普通 OpenAI Chat Completions，它额外做了这些事：

- 从 LanceDB 检索相关历史记忆。
- 注入 persona、关系记忆、真实当前时间、AI 生活状态、可选联网检索摘要和可选 URL 网页读取结果。
- 在启用视觉配置时支持图片输入。
- 传入 `conversation_id` 时，会把完整一轮对话写回 live memory。

请求示例：

```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "user", "content": "在吗"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 300,
  "conversation_id": "my-app-user-1"
}
```

响应示例：

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1779400000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "在呢，怎么啦"},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "trace_id": "..."
}
```

流式请求使用 OpenAI 风格 SSE：

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "今天有点累"}],
    "stream": true,
    "conversation_id": "demo"
  }'
```

图片输入遵循 OpenAI 多模态格式：

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "看看这张图"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }
  ]
}
```

图片相关配置：

- `VISION_ENABLED=true`
- 如果主聊天模型原生支持视觉：`CHAT_MODEL_SUPPORTS_VISION=true`
- 否则配置 `VISION_API_URL`、`VISION_API_KEY`、`VISION_MODEL`

联网与 URL 读取：

- `WEB_ACCESS_ENABLED=true` 后，用户明确要求“搜索/新闻/最新/天气/价格”等公开实时信息时，后端会调用 Tavily 或 SearXNG，并把摘要注入 prompt。
- 用户消息里包含 `http://`、`https://` 链接且 `WEB_FETCH_ENABLED=true` 时，后端会直接尝试读取网页标题和正文摘录，并把结果注入 prompt。
- 用户只写裸域名（如 `example.com`）时，不会无条件访问。后端会先用本地规则判断是否有“打开/看看/这个网站是什么”等访问意图；命中后再调用小模型确认要访问的候选 URL，确认后按 `https://example.com` 访问。这个小模型复用 `LIFE_API_URL` / `LIFE_API_KEY` / `LIFE_MODEL` 配置。
- URL 读取只支持普通文本网页，不执行 JavaScript；后端会拒绝本机、内网、链路本地等地址，并限制跳转、响应大小和正文字符数。
- 相关诊断在 `/debug/stats` 的 `calls.web.search`、`calls.web.search.skipped`、`calls.web.intent`、`calls.web.fetch`、`calls.web.fetch.skipped`。

### `POST /v1/companion/proactive`

让 AI 主动开启一个话题。这个接口适合外部调度器、机器人框架或其它程序调用，
效果类似“对方主动找用户聊天”。

请求示例：

```json
{
  "conversation_id": "my-app-user-1",
  "reason": "morning",
  "private_context": "用户昨天说今天有考试",
  "topic_hint": "轻轻问候一下"
}
```

响应示例：

```json
{
  "message": "醒了吗，今天是不是要考试来着",
  "life": {
    "date": "2026-05-22",
    "time_slot": "上午",
    "current_activity": "刚醒一会儿",
    "recent_meal": "喝了水",
    "mood": "普通",
    "availability": "available",
    "topic_seed": "问问今天安排",
    "next_update_at": "2026-05-22 11:30",
    "reply_delay_seconds": 0,
    "reply_delay_reason": "",
    "day_plan_summary": "...",
    "recent_timeline_summary": "..."
  },
  "relationship_memory": "...",
  "trace_id": "..."
}
```

`private_context` 是内部触发背景，不会作为用户消息写入历史。生成的 AI 消息会在传入
`conversation_id` 时写入 live memory。

## 记忆接口

### `GET /memory/stats`

查看向量库和回写队列状态。

```json
{
  "friend_messages": 1000,
  "dialogue_windows": 400,
  "response_pairs": 300,
  "live_messages": 20,
  "relationship_memories": 5,
  "writeback_enabled": true,
  "writeback_paused": false
}
```

### `POST /memory/search`

调试用检索接口，只跑检索，不调用聊天模型。前端诊断面板可以用它看“到底召回了什么”。

请求示例：

```json
{
  "query": "你在干嘛",
  "conversation_id": "my-app-user-1",
  "top_k": 12
}
```

响应字段：

- `fused`：最终融合后的结果，最接近主 prompt 使用的记忆。
- `response_pairs`：用户输入到历史中对方回复的样例。
- `friend_examples`：单条对方消息样例。
- `dialogue_windows`：多轮上下文片段。
- `recent_live`：当前会话最近 live 记忆。
- `trace_id`：本次请求追踪 ID。

### `POST /memory/writeback/pause`

暂停 live memory 回写。

```json
{"status": "paused"}
```

### `POST /memory/writeback/resume`

恢复 live memory 回写。

```json
{"status": "running"}
```

### `DELETE /memory/{table}/{memory_id}`

软删除某条记忆。允许的表：

- `friend_messages`
- `live_messages`
- `response_pairs`

## 元信息接口

### `GET /healthz`

基础进程健康检查。

```json
{"status": "ok", "version": "0.1.0"}
```

### `GET /readyz`

检查必要配置、向量库和 persona 是否准备好。

```json
{"ready": true, "issues": []}
```

### `GET /info` 和 `GET /v1/info`

返回前端需要的应用名、模型名、关系类型和 persona 卡片状态。

## 文档提取接口

### `GET /v1/documents/formats`

列出当前支持的文档扩展名。

### `POST /v1/documents/extract`

上传文档并提取纯文本。支持 `txt`、`md`、`json`、`csv`、`log`、`yaml`、
`xml`、`ini`、`pdf`、`docx`、`xlsx`、`html`。

```bash
curl -F "file=@notes.pdf" http://127.0.0.1:8000/v1/documents/extract
```

响应示例：

```json
{
  "filename": "notes.pdf",
  "extension": "pdf",
  "text": "...",
  "char_count": 1200,
  "estimated_tokens": 300
}
```

## 表情包与图片接口

### `GET /v1/stickers?owner=shared`

列出表情包。`owner` 可选。

### `POST /v1/stickers`

通过 data URL 新建表情包。

```json
{
  "name": "ok",
  "description": "点头",
  "data_url": "data:image/png;base64,...",
  "owner": "shared",
  "tags": ["agree"]
}
```

### `PATCH /v1/stickers/{name}`

更新 `description`、`owner` 或 `tags`。

### `DELETE /v1/stickers/{name}`

删除表情包。

### `GET /v1/stickers/{name}/image`

返回表情包图片字节。

### `GET /images/{sha}`

通过 sha256 读取已持久化的聊天图片。

## 调试接口

仅在 `DEBUG_ENDPOINTS_ENABLED=true` 时挂载。

### `GET /debug/stats`

详细运行诊断，包括：

- 记忆表数量
- LanceDB 操作耗时
- 回写队列状态
- 模型请求完整链路
- life 状态和模型决策
- 联网检索指标

### `GET /debug/config`

脱敏配置快照。API key 只显示是否已配置，不返回具体值。

### `POST /debug/metrics/reset`

清空内存里的运行指标，不删除 LanceDB 数据。

## 错误格式

业务错误通常返回：

```json
{
  "error": {
    "code": "xuwen.some_code",
    "message": "可读错误信息",
    "request_id": "..."
  }
}
```

FastAPI 参数校验错误使用标准 `422` 响应。
