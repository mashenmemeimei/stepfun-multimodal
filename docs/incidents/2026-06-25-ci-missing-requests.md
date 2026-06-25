# 2026-06-25 — CI fails on first run (missing `requests`)

## 一句话

`requirements.txt` 写了 `-r requirements-dev.txt`，而 CI 只装了 `requirements-dev.txt`，
结果 `requests` 根本没装，`pytest` 一调 `stepfun_image.client` 就 `ModuleNotFoundError`。

## 时间线

| 时间 (UTC) | 事件 |
| --- | --- |
| 06:40 | push `e55fe38`：加了 tests/、CI workflow、pytest 配置 |
| 06:40 | CI 在三个 Python 版本（3.10/3.11/3.12）上同时失败，步骤 `Run pytest` 红 |
| 06:42 | 拉 jobs：`Install dependencies` 步骤 ✅，`Run pytest` 步骤 ❌ —— 说明包是装上了的，缺的是 `requests` 这种"运行时"依赖 |
| 06:44 | 重建依赖关系并 push `a172168` |
| 06:46 | CI ✅，三个版本全绿 |

## 失败的根因

我在初始 `requirements.txt` 里写了：

```text
requests>=2.31
-r requirements-dev.txt
```

我当时的意图是"开发装 `requirements.txt` 就一并装好 dev 依赖，方便本地"。
但 CI workflow 里写的却是：

```yaml
- run: pip install -r requirements-dev.txt
```

而 `requirements-dev.txt` 只列了 `pytest>=7.4`，**没有反向引用 `requirements.txt`**。
所以 CI 装完只有 pytest，运行时依赖 `requests` 全无。

复盘：本意是"用 dev 包含 prod" 的关系，但在 dev 文件里**没有反向指回 prod**，
于是 CI 这条路径上 prod 完全没装。

## 怎么修的

把依赖关系倒过来，符合"dev 依赖 prod"的真实方向：

```text
# requirements.txt
requests>=2.31
```

```text
# requirements-dev.txt
-r requirements.txt
pytest>=7.4
```

CI 一行命令就够了：

```yaml
- run: pip install -r requirements-dev.txt
```

这条命令现在等价于"装 prod + 装 dev"，无论谁跑都一致。

## 教训（写给未来的自己）

1. **依赖关系只能单向**：prod 不知道 dev 的存在，dev 知道 prod。
   `requirements.txt` 里出现 `-r requirements-dev.txt` 是反模式。

2. **CI 装包命令要复现真实路径**，不要假设"反正 pip 会自己解决"。
   本地 `pip install -e .` 因为 `pyproject.toml` 里 `dependencies = ["requests>=2.31"]` 已经隐式装了，
   让我误以为 `pip install -r requirements-dev.txt` 也够。

3. **第一时间看 job 日志里的 step 状态**，比翻代码快。
   这次看到 "Install dependencies ✅ / Run pytest ❌" 一秒定位是运行时依赖缺了，
   不是测试本身写错。

4. **CI 第一次失败不要紧**，关键是修完的 commit 信息要写清楚"为什么失败 → 为什么这么修"，
   避免三个月后看到 git log 不记得前因。

## 验证

```text
local: pytest -v → 13 passed
CI:    pytest (3.10/3.11/3.12) → 3 jobs success
URL:   https://github.com/mashenmemeimei/stepfun-multimodal/actions/runs/28151977486
```
