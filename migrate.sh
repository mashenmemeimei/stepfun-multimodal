#!/usr/bin/env bash
# Bootstrap script: run this on the new machine after copying the project over.
#
# Usage:
#   bash migrate.sh                  # interactive
#   STEPFUN_HOME=/path bash migrate.sh
#
# What it does:
#   1. Creates a venv (optional but recommended)
#   2. pip install -e . so `python -m stepfun_image.cli` works from anywhere
#   3. Installs the SKILL.md into ~/.claude/skills/stepfun-image/
#   4. Runs `whoami` to verify key resolution

set -euo pipefail

PROJECT_DIR="${STEPFUN_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
SKILL_SRC="$PROJECT_DIR/skill/SKILL.md"
SKILL_DST_DIR="${HOME}/.claude/skills/stepfun-image"
SKILL_DST="$SKILL_DST_DIR/SKILL.md"

echo "==> project: $PROJECT_DIR"
echo "==> skill target: $SKILL_DST"

# 1. venv (best-effort, ignore if already in one)
if [[ -z "${VIRTUAL_ENV:-}" && ! -d "$PROJECT_DIR/.venv" ]]; then
  echo "==> creating venv"
  python3 -m venv "$PROJECT_DIR/.venv"
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.venv/bin/activate"
fi

# 2. install
echo "==> pip install -e ."
python -m pip install -e "$PROJECT_DIR"

# 3. drop skill file
if [[ -f "$SKILL_SRC" ]]; then
  mkdir -p "$SKILL_DST_DIR"
  cp "$SKILL_SRC" "$SKILL_DST"
  echo "==> skill installed at $SKILL_DST"
else
  echo "!! SKILL.md not found at $SKILL_SRC — copy it manually to $SKILL_DST"
fi

# 4. verify key
echo "==> whoami"
python -m stepfun_image.cli whoami

echo
echo "Done. Try:  python -m stepfun_image.cli t2i \"hello\" -o /tmp/hello.png"
