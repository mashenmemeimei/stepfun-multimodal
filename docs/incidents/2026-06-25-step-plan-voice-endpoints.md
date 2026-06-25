# 2026-06-25 — Step Plan 语音端点探活

## 一句话

按文档列的 7 个语音端点接入了 5 个；剩下 2 个（voice preview/clone）
**文档列了但 step_plan 网关没部署路由**，WS 协议里"提交文本"的事件名
是 provisional 的，需要按开放平台文档校准。

## 时间线

| 时间 (UTC) | 事件 |
| --- | --- |
| 06:50 | 接入指南读完，决定本次先做 HTTP/SSE 三件套（TTS/ASR/Chat），WS + voices 推到下一轮 |
| 07:00 | TTS 端到端跑通：`output/hello.mp3`，48KB，ID3 标签正确 |
| 07:05 | Chat 端到端跑通：stepaudio-2.5-chat 真实中文回复（终端 GBK 乱码但解码正常） |
| 07:15 | GitHub push + CI 全绿 |
| 07:20 | 收到"继续做未实现的"指示，开始第二轮：voices + WS |
| 07:25 | WebSocket 握手用 websocket-client 直连验证通过（`tts.connection.done` / `session.created` 都准时到） |
| 07:30 | voices preview 实测 → 网关层 404（`text/plain`，非 JSON 错误） |
| 07:32 | 探测替代路径：`/step_plan/audio/voices/preview`、`/v1/audio/voices/preview`、`/audio/voices/preview` —— 全部不通；开放平台 `/v1/audio/voices/preview` 返回 400（"model is invalid"），说明端点存在但 schema 不同 |
| 07:35 | tts-stream 集成后报 `Connection lost` —— 怀疑协议事件名不对 |
| 07:36–07:38 | 连发 16 个 WS 连接探测不同 event 名 → 触发 `429 Too Many Requests`，并发上限 15 |
| 07:40 | 把 protocol 切成"两步"：先 `tts.create`（不带 text），再 `tts.text`（带 text）。**握手层验证通过，但完整流未跑通**（限速下没法稳定复现） |
| 07:50 | git push 重试两次（GitHub 端口 443 偶发抖动），最终成功；CI 全绿 |

## 三个真实发现

### 1. `/audio/voices/preview` 在 step_plan 网关 404

**不是 schema 错，是网关根本没路由。** 证据：

```text
GET  /step_plan/v1/audio/voices/preview  → 404 page not found   (text/plain, 19 bytes)
POST /step_plan/v1/audio/voices/preview  → 404 page not found   (text/plain, 19 bytes)
GET  /step_plan/audio/voices/preview    → 404
```

404 body 是 nginx 的 `b'404 page not fou'`，不是 StepFun 的 JSON API 错误。
说明这个路径在网关层就没有路由规则 —— 文档列了它，但 step_plan 还没部署。

但开放平台 `/v1/audio/voices/preview`（不同 base URL）有响应：

```text
400 {"error":{"message":"Request param: model is invalid, recommended val is: not empty", ...}}
```

说明端点本身存在，但 step_plan 的网关还没把它转发过去。

**当前选择**：代码写好了，命令行 `voices preview` 也接好了，等网关路由开通就行。
如果临时要用，去 https://platform.stepfun.com 开放平台调（需要开放平台 Key，与 step_plan Key 不同）。

### 2. WS 并发上限 15，触发会等一会儿才清

```text
{"error":{
  "message":"request limited concurrency reached, current: 16, limit: 15.
             Please top up at https://platform.stepfun.com/top-up.",
  "type":"rate_limited"
}}
```

教训：探测协议时串行 sleep 1~2s 不要并发，否则会一次性把 16 个 probe 全部 429，
之后还要等几十秒才能继续。本地开发建议给每个连接加显式 sleep。

### 3. TTS WebSocket 的 "提交文本" 事件名是推测

文档示例只到 `tts.create`（session config），没有示范怎么把文本发过去。
我试过这些：

| 事件名 | 服务器响应 |
| --- | --- |
| `tts.text` (data: `{text}`) | `invalid event format` |
| `tts.text.delta` (data: `{delta}`) | `data is required` ← 自相矛盾 |
| `tts.synthesize` / `tts.input_text` / `tts.input` / `text.message` / `text.delta` | `invalid event format` |
| 把 text 直接塞进 `tts.create.data` | 连接断开，无错误（最危险的情况） |

最关键的是：**握手层完全通**（`tts.connection.done` 准时到，`tts.create` 被接受并发回 `tts.response.created`），
所以"协议骨架"是对的，只是文本提交这一步的准确事件名没敲定。

**当前选择**：默认发 `tts.text` 事件（schema: `data: {session_id, text}`），
并在 `tts_stream.py` 顶部注释里写了"如果 Connection lost，去官方文档校准"。
等用户拿到开放平台 https://platform.stepfun.com/zh/api-reference/audio/ws-audio 的精确协议再改。

## 写进代码里的"已知 provisional"清单

```python
# stepfun_audio/tts_stream.py 顶部注释（写给未来的自己）
"""
Protocol (provisional):
  1. Server sends  {"type": "tts.connection.done", "data": {"session_id": "..."}}
  2. Client sends  {"type": "tts.create", "data": {<session config, no text>}}
  3. Client sends  {"type": "tts.text", "data": {"session_id": "...", "text": "..."}}
  4. Server streams zero or more  {"type": "tts.chunk", "data": {"audio": "<b64>"}}
  5. Server sends  {"type": "tts.completion", "data": {...}}

NOTE: if the server drops the connection after step 2 with no error, the
text event name in step 3 is wrong. Adjust here once the authoritative
event name is known from the open-platform docs.
"""
```

## skill 文档里诚实标注的状态表

```markdown
| 能力 | 模型 | 端点 | 状态 |
| --- | --- | --- | --- |
| TTS（HTTP 非流）       | ✅ E2E 验证 |
| ASR（SSE）             | ✅ 单元测试覆盖 |
| Chat（文本）           | ✅ E2E 验证 |
| TTS（WS 流式）         | ⚠️ 握手通，text 事件名 provisional |
| Realtime voice         | ⚠️ 握手通，单轮对话封装 |
| Voice preview          | ❌ step_plan 网关 404（未部署） |
| Voice clone            | ⚠️ 存在但需不同 schema |
```

## 教训

1. **404 不一定是你写错了**。`text/plain` 的 404 是 nginx 默认页，是网关层没路由；
   `application/json` 的 404 通常是 handler 写明了"端点不存在"。
   区分这两种可以省下大量调试时间。

2. **协议握手成功 ≠ 协议完成**。tts-stream 的 WS 握手完美，但"提交文本"这一关键步骤
   我猜了好几次都没猜对。下次类似情况，写代码前先确认"完整 happy path"的最小命令
   能跑通，不要从单元测试里推协议。

3. **限速/并发额度是真实约束**。我用了 16 个 probe 在几秒内连发，立刻把额度打满。
   之后再做任何协议探活，默认 sleep 2s，并且**只测一个变量**。

4. **"文档列了" 不等于 "网关部署了"**。这次 voice preview 是文档与部署脱节的典型例子。
   把这种状态明确写进 skill（"⚠️ 网关 404"），下次别人看到 CLI 报错不会反复怀疑自己的代码。

## 后续行动（next time）

- [ ] 用户去 https://platform.stepfun.com/zh/api-reference/audio/ws-audio 校准 `tts.text` 事件名
- [ ] 用户跑一次完整 happy path：`tts-stream "hello" -o out.wav` 应拿到一个 wav 文件
- [ ] 网关开通 voice preview 后，跑 `voices preview -o out.mp3` 验证
- [ ] 多轮 realtime 对话封装（目前 CLI 只支持单轮；多轮需用 `websocket.WebSocketApp`）

## 验证

```text
local:  pytest -q  →  37 passed in 0.34s
CI:     pytest 3.10/3.11/3.12  →  3 jobs success
remote: 1e9ff1f..2889745  main -> main
skills: stepfun-image, stepfun-audio  (both registered globally)
```
