---
name: stepfun-image
version: 0.1.0
description: "调用 StepFun 图像模型（Step Plan）：文生图、图像编辑。API Key 自动从 CCSwitch SQLite 复用，无需手动配置。适用于用户需要生成图片、编辑/改图、批量出图、或在 Claude Code / Codex 中以 skill 形式调用 StepFun 模型的场景。"
metadata:
  requires:
    bins: ["python"]
    env_optional: ["STEP_API_KEY", "STEPFUN_HOME"]
    python_packages: ["requests"]
  source: "pip install -e <project>"  # or set $STEPFUN_HOME
---

# StepFun 图像模型 Skill

调用 `python -m stepfun_image.cli ...` 即可。包路径通过 `pip install -e .`（推荐）或环境变量 `STEPFUN_HOME` 指定：

- 装了 `pip install -e .` → 任意目录直接 `python -m stepfun_image.cli`
- 没装 → 在 `${STEPFUN_HOME}` 下执行 `python -m stepfun_image.cli`

- **模型**：`step-image-edit-2`（同时支持文生图与图像编辑）
- **端点**：`https://api.stepfun.com/step_plan/v1/images/{generations,edits}`
- **认证**：自动从 `~/.cc-switch/cc-switch.db` 复用 StepFun provider 的 Key（Claude/Codex 同一份）。可用 `STEP_API_KEY` 环境变量覆盖。

## 何时触发

- "用 stepfun / StepFun 生成一张图..."
- "把这张图用 stepfun 改成..."、"给图片加个 XX 元素"
- "用我订阅的 Step Plan 跑一下文生图"
- 用户粘贴了图片并要求改图 / 重绘 / 风格化

> 如果用户没有指定供应商是 StepFun，但 Claude Code 当前 Provider 是 StepFun，也优先使用本 skill，因为底层 key 已经配在 CCSwitch 里。

## CLI 用法

```bash
# 1. 诊断：确认 Key 来源（不发请求）
python -m stepfun_image.cli whoami

# 2. 文生图
python -m stepfun_image.cli t2i "采菊东篱下，悠然见南山" -o out/nanshan.png

# 3. 图像编辑（multipart/form-data，input.webp 最大 4096x4096）
python -m stepfun_image.cli edit input.webp "让图中角色骑自行车" -o out/ride.png

# 4. 多张 + 精细控制
python -m stepfun_image.cli t2i "neon tokyo street, rainy" -o out/tokyo.png \
  --n 4 --seed 42 --steps 12 --cfg-scale 1.2 --size 1024x1024
```

输出默认落在 `./output/`，可被 Claude Code 直接 `Read` 显示。

## 参数说明

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--seed` | 1 | 随机种子，复现用 |
| `--steps` | 8 | 推理步数，越大越慢越精细 |
| `--cfg-scale` | 1.0 | 提示词遵循度 |
| `--text-mode` | true | 启用文字渲染（中文也支持） |
| `--size` | — | 仅 t2i：`1024x1024` / `2048x2048` 等 |
| `--n` | 1 | 仅 t2i：一次生成张数 |
| `--model` | `step-image-edit-2` | 留默认即可 |

## Key 复用机制

```
1. 环境变量 $STEP_API_KEY        ← 显式覆盖（最高优先级）
2. ~/.cc-switch/cc-switch.db     ← 自动读取 StepFun 行（默认）
```

CCSwitch 中 StepFun provider 同时挂载在 `claude` 与 `codex` 两个 app_type 下，cli 会自动识别。**不要**把 Key 写进项目代码或仓库。

## Python SDK 用法（在 Claude Code 生成的脚本里）

```python
from stepfun_image import StepFunImageClient
client = StepFunImageClient()  # 自动从 CCSwitch 拿 Key
images = client.text_to_image("a cat astronaut, cinematic", n=2)
for i, blob in enumerate(images):
    Path(f"output/cat-{i}.png").write_bytes(blob)
```

## 计费 / 限速

按开放平台实际金额折算 Step Plan 总额度，详见 https://platform.stepfun.com/zh/guides/pricing/details 。一次编辑 1–2 秒，单次生成单张图即可，不建议在工具链里无脑循环出几百张。

## 失败排查

| 现象 | 处理 |
| --- | --- |
| `No StepFun API key found` | 跑一次 `whoami`；若两项都 unset/unfound，打开 CCSwitch 添加 StepFun provider |
| HTTP 401 | Key 失效或订阅过期，去 https://platform.stepfun.com/interface-key 重置 |
| HTTP 429 | 触发限速，加 `--seed` 复现失败请求，或降低并发 |
| `FileNotFoundError`（edit） | 用绝对路径或先 `ls` 确认输入图存在；最大 4096x4096 |

调用成功后把输出路径回给用户，让他们在资源管理器/编辑器里看效果。
