# stepfun-multimodal

Step Plan 多模态接入：图像（`step-image-edit-2`）+ 语音（`stepaudio-2.5-tts/asr/chat/realtime`）。

- **CLI**：
  - 图像：`python -m stepfun_image.cli {t2i,edit,whoami}`
  - 语音：`python -m stepfun_audio.cli {tts,asr,chat,tts-stream,realtime,voices}`
- **Python SDK**：`from stepfun_image import StepFunImageClient` · `from stepfun_audio import StepFunAudioClient, StepFunChatClient, ...`
- **Claude Code / Codex skills**：
  - `~/.claude/skills/stepfun-image/SKILL.md` — 图像
  - `~/.claude/skills/stepfun-audio/SKILL.md` — 语音

> GitHub 仓库原名 `stepfun-image`，已更名为 `stepfun-multimodal`（2026-06-25）。Python 包名（`stepfun_image` / `stepfun_audio`）保持不变以避免破坏现有 import。

API Key **不**写进代码、不进仓库 —— 自动从 CCSwitch (`~/.cc-switch/cc-switch.db`) 的 StepFun provider 复用，Claude Code 和 Codex 共用一份订阅。

> 调试翻车记录与依赖设计踩坑，见 [docs/incidents/](docs/incidents/)。
> 变更日志见 [CHANGELOG.md](CHANGELOG.md)。

## 项目结构

```
stepfun-image/
├── stepfun_image/
│   ├── __init__.py
│   ├── ccswitch.py     # 从 CCSwitch SQLite 读 Key
│   ├── client.py       # requests 封装的 client
│   └── cli.py          # argparse CLI 入口
├── stepfun.cmd         # Windows 直接调用
├── stepfun.sh          # POSIX 直接调用
├── pyproject.toml
├── requirements.txt
└── output/             # 默认输出目录
```

## 安装

```bash
cd D:/Projects/stepfun-image
pip install -r requirements.txt
# 可选：注册为 console_script
pip install -e .
# 安装后任意目录都可以直接 `stepfun ...`
```

## Key 来源优先级

1. `$STEP_API_KEY` 环境变量（最高优先级，CI/测试用）
2. `~/.cc-switch/cc-switch.db` 中 `name='StepFun'` 的行（默认）
   - claude provider → `settings_config.env.ANTHROPIC_AUTH_TOKEN`
   - codex provider  → `settings_config.auth.OPENAI_API_KEY`
3. 都没有 → 报错，引导去 https://platform.stepfun.com/interface-key 申请

诊断：

```bash
python -m stepfun_image.cli whoami
# env $STEP_API_KEY:    unset
# CCSwitch StepFun key: found
#   preview: 3c9IqN...BXvm
```

## CLI 示例

```bash
# 文生图
python -m stepfun_image.cli t2i "采菊东篱下，悠然见南山" -o output/nanshan.png

# 图像编辑
python -m stepfun_image.cli edit input.webp "让图中角色骑自行车" -o output/ride.png

# 多张出图
python -m stepfun_image.cli t2i "neon tokyo, rainy" \
  --n 4 --seed 42 --steps 12 --cfg-scale 1.2 --size 1024x1024
```

可选参数：`--seed` `--steps` `--cfg-scale` `--text-mode/--no-text-mode` `--size` `--n` `--model` `--base-url` `--db`。

## Python SDK

```python
from stepfun_image import StepFunImageClient

client = StepFunImageClient()  # 自动拿 Key

# 文生图
blobs = client.text_to_image("a cat astronaut", n=2, seed=7)
for i, b in enumerate(blobs):
    open(f"output/cat-{i}.png", "wb").write(b)

# 图像编辑
blobs = client.edit_image("input.webp", "给角色戴一顶红帽子")
open("output/redhat.png", "wb").write(blobs[0])

# 自定义 Key 来源
from stepfun_image import StepFunConfig, StepFunImageClient
cfg = StepFunConfig(api_key="sk-...", base_url="https://api.stepfun.com/step_plan/v1")
client = StepFunImageClient(cfg)
```

## 在 Claude Code / Codex 里用

skill 自动发现位于 `~/.claude/skills/stepfun-image/SKILL.md`，无需额外配置。直接对 CC 说：

> "用 stepfun 生成一张'赛博朋克雨夜东京'"

CC 会调用 `python -m stepfun_image.cli t2i "赛博朋克雨夜东京"` 并把输出路径展示给你。

也可以手动 `/stepfun-image` 触发 skill。

## API 端点

| 能力 | 路径 | 方法 |
| --- | --- | --- |
| 文生图 | `/step_plan/v1/images/generations` | POST（JSON） |
| 图像编辑 | `/step_plan/v1/images/edits` | POST（multipart） |

参数细节与开放平台一致：https://platform.stepfun.com/zh/api-reference/images/image

## 已知限制

- 输入图最大 4096×4096
- 单次编辑 1–2 秒；并发不要拉太高
- 计费按 Step Plan 总额度折算，避免大批量无意义重跑
