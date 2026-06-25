---
name: stepfun-audio
version: 0.2.0
description: "调用 StepFun 语音模型（Step Plan）：TTS（HTTP / WebSocket 流式）、ASR（SSE）、Chat、Voice preview/clone、Realtime voice chat。Key 自动从 CCSwitch 复用。"
metadata:
  requires:
    bins: ["python"]
    env_optional: ["STEP_API_KEY", "STEPFUN_HOME"]
    python_packages: ["requests", "websocket-client"]
  source: "pip install -e <project>"
---

# StepFun 语音模型 Skill

调用 `python -m stepfun_audio.cli ...`，使用 StepAudio 2.5 家族。

## 端点 + 实现状态（2026-06-25 探活）

| 能力 | 模型 | 端点 | 状态 |
| --- | --- | --- | --- |
| TTS（HTTP 非流） | `stepaudio-2.5-tts` | `POST /step_plan/v1/audio/speech` | ✅ E2E 验证 |
| ASR（SSE） | `stepaudio-2.5-asr` | `POST /step_plan/v1/audio/asr/sse` | ✅ 单元测试覆盖 |
| Chat（文本） | `stepaudio-2.5-chat` | `POST /step_plan/v1/chat/completions` | ✅ E2E 验证 |
| TTS（WS 流式） | `stepaudio-2.5-tts` | `wss://.../step_plan/v1/realtime/audio` | ⚠️ 握手通，text 事件名 provisional |
| Realtime voice | `stepaudio-2.5-realtime` | `wss://.../step_plan/v1/realtime` | ⚠️ 握手通，单轮对话封装 |
| Voice preview | — | `POST /step_plan/v1/audio/voices/preview` | ❌ step_plan 网关 404（未部署） |
| Voice clone | — | `POST /step_plan/v1/audio/voices` | ⚠️ 存在但需不同 schema |

Key 复用：同 [[stepfun-image]]，自动从 `~/.cc-switch/cc-switch.db` 读，`$STEP_API_KEY` 可覆盖。

## 何时触发

- "用 stepfun 把这段文字转成语音 / 念给我听" → `tts` 或 `tts-stream`
- "把这段录音转成文字 / 转录" → `asr`
- "用 stepaudio 陪我聊聊 / 角色扮演对话" → `chat` 或 `realtime`
- 用户给了一段 wav/pcm/mp3 文件，要求转写 → `asr`
- 实时语音交互（双向）→ `realtime`

## CLI 用法

```bash
# 1. TTS（HTTP，简单）
python -m stepfun_audio.cli tts "今天天气不错" \
  --voice cixingnansheng --instruction "语气温柔，语速偏慢" \
  -o out/hello.mp3

# 2. TTS 流式（WS，更低延迟，可中断）
python -m stepfun_audio.cli tts-stream "今天天气不错" -o out/hello.wav

# 3. ASR
python -m stepfun_audio.cli asr recording.pcm -o transcript.txt
# 录音必须是 pcm_s16le / 16kHz / mono：
#   ffmpeg -i in.wav -f s16le -ar 16000 -ac 1 out.pcm

# 4. Chat（单轮）
python -m stepfun_audio.cli chat "陪我聊聊" \
  --system "你是有耐心的陪伴搭子" -o reply.txt

# 5. Realtime（单轮）
python -m stepfun_audio.cli realtime "陪我聊聊" \
  --voice linjiajiejie --instructions "你是有耐心的陪伴搭子" \
  -o reply.pcm

# 6. Voice preview（如果网关可用）
python -m stepfun_audio.cli voices preview \
  --voice cixingnansheng -o out/preview.mp3

# 7. Voice clone
python -m stepfun_audio.cli voices clone "我的音色" ref.wav \
  --ref-text "参考文本" -o out/voice.json
```

## TTS 参数（HTTP / 流式 通用）

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--voice` | `cixingnansheng` | 音色 id |
| `--instruction` | — | 风格指令，如 "语气温柔" |
| `--format` | `mp3`(HTTP) / `wav`(WS) | 输出格式 |
| `--sample-rate` | `24000`(HTTP) / `16000`(WS) | 采样率 |
| `--speed` / `--volume` | `1.0` | 语速/音量倍率 |

## ASR 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--language` | `zh` | `zh` / `en` |
| `--no-itn` | 关 | 关闭数字归一化 |
| `--sample-rate` / `--bits` / `--channels` | `16000` / `16` / `1` | 与音频一致 |

## Realtime 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--voice` | `linjiajiejie` | 音色 id |
| `--instructions` | — | 人设/系统指令 |
| `--input-audio-format` / `--output-audio-format` | `pcm16` | 音频格式 |

## Python SDK

```python
from stepfun_audio import (
    StepFunAudioClient,    # TTS + ASR
    StepFunChatClient,     # Chat (text)
    StepFunTtsStreamClient,# TTS WS stream
    StepFunRealtimeClient, # Realtime voice
    StepFunVoicesClient,   # Voice preview/clone
)

# 一次性
client = StepFunAudioClient()
open("out.mp3", "wb").write(client.text_to_speech("你好"))

# 流式（节省首字延迟）
for chunk in StepFunTtsStreamClient().stream_tts("你好", voice="cixingnansheng"):
    # pipe to audio sink
    ...
```

## 已知限制（2026-06-25）

1. **Voice preview/clone 在 step_plan 网关 404**——文档列了这两个端点，但实际未部署。代码已就绪，等网关开放即可用。可暂时绕过：访问 https://platform.stepfun.com 的开放平台 `/v1/audio/voices/preview`（需开放平台 Key，与 step_plan Key 不同）。

2. **TTS WebSocket 的 text 事件名是 provisional**——握手 + `tts.create` + 流式 chunk 已验证，但 "提交文本" 事件名（`tts.text` vs `tts.text.delta` vs 其他）在写 skill 时未确认。如果运行 `tts-stream` 出现 Connection lost，请参考 https://platform.stepfun.com/zh/api-reference/audio/ws-audio 校准 `stepfun_audio/tts_stream.py` 里的事件名。

3. **Realtime 单轮封装**——CLI 只做单轮（text in → audio out）。多轮对话需要在 Python 里直接用 `websocket.WebSocketApp`。

## 失败排查

| 现象 | 处理 |
| --- | --- |
| `No StepFun API key found` | `python -m stepfun_image.cli whoami` 验证 |
| ASR 返回空 | 确认音频是 pcm_s16le / 16kHz / mono；用 ffmpeg 预转 |
| TTS 输出异常小 | 检查 `--instruction` 长度，或换 voice id |
| `tts-stream` Connection lost | 调整 `tts_stream.py` 里的 text 事件名（见上文） |
| `voices preview` 404 | 网关暂未部署，等开放 |
| WebSocket 429 | 并发上限 15，避免短时间开多个连接 |

## 跨项目复用

与 [[stepfun-image]] 共享 `stepfun_image.ccswitch` 的 Key 加载器。
一次 CCSwitch 订阅同时支持图像 + 语音。
