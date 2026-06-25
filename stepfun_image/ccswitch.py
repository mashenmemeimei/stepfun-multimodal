"""Read the StepFun API key from the CCSwitch SQLite database.

CCSwitch (`~/.cc-switch/cc-switch.db`) keeps provider entries that hold
the raw API key. Both the `claude` and `codex` StepFun providers reuse
the same token, so we just grab whichever is there.

Resolution order for the API key:
  1. ``STEP_API_KEY`` environment variable
  2. CCSwitch SQLite database (auto-detected)
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

KEY_ENV_VAR = "STEP_API_KEY"
DEFAULT_DBS = [
    Path.home() / ".cc-switch" / "cc-switch.db",
    Path("C:/Users") / os.getenv("USERNAME", "") / ".cc-switch" / "cc-switch.db",
]


def load_api_key_from_ccswitch(db_path: str | os.PathLike | None = None) -> str | None:
    """Return the StepFun API key stored in CCSwitch, or ``None`` if not found."""
    candidate = Path(db_path) if db_path else _find_db()
    if candidate is None or not candidate.exists():
        return None

    conn = sqlite3.connect(str(candidate))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT settings_config FROM providers WHERE name = ? AND app_type IN ('claude','codex')",
            ("StepFun",),
        )
        for (settings_blob,) in cur.fetchall():
            try:
                data = json.loads(settings_blob)
            except (TypeError, json.JSONDecodeError):
                continue
            # claude provider stores token under env.ANTHROPIC_AUTH_TOKEN;
            # codex provider stores it under auth.OPENAI_API_KEY.
            for path in (("env", "ANTHROPIC_AUTH_TOKEN"), ("auth", "OPENAI_API_KEY")):
                cur2 = data
                for k in path:
                    if not isinstance(cur2, dict) or k not in cur2:
                        cur2 = None
                        break
                    cur2 = cur2[k]
                if isinstance(cur2, str) and cur2.strip():
                    return cur2.strip()
    finally:
        conn.close()
    return None


def _find_db() -> Path | None:
    for p in DEFAULT_DBS:
        if p and p.exists():
            return p
    return None


def resolve_api_key(db_path: str | os.PathLike | None = None) -> str:
    """Return the API key from env or CCSwitch. Raise ``RuntimeError`` if absent."""
    env_key = os.getenv(KEY_ENV_VAR)
    if env_key:
        return env_key.strip()
    db_key = load_api_key_from_ccswitch(db_path)
    if db_key:
        return db_key
    raise RuntimeError(
        "No StepFun API key found. Set $STEP_API_KEY, or add a StepFun "
        "provider in CCSwitch (https://platform.stepfun.com/interface-key)."
    )
