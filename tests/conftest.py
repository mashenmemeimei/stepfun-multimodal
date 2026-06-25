"""Shared fixtures for stepfun-multimodal tests."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Make the package importable without `pip install -e .`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def fake_ccswitch_db(tmp_path: Path) -> Path:
    """Create a CCSwitch-shaped sqlite db with both Claude and Codex StepFun rows."""
    db = tmp_path / "cc-switch.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE providers (
              id TEXT PRIMARY KEY,
              app_type TEXT NOT NULL,
              name TEXT NOT NULL,
              settings_config TEXT NOT NULL
            );
            """
        )
        claude_cfg = {
            "env": {
                "ANTHROPIC_BASE_URL": "https://api.stepfun.com/step_plan",
                "ANTHROPIC_AUTH_TOKEN": "claude-test-token-AAA",
                "ANTHROPIC_MODEL": "step-3.7-flash",
            }
        }
        codex_cfg = {
            "auth": {"OPENAI_API_KEY": "codex-test-token-BBB"},
            "config": "model = 'step-3.7-flash'\n",
        }
        conn.execute(
            "INSERT INTO providers(id, app_type, name, settings_config) VALUES (?,?,?,?)",
            ("claude-uuid", "claude", "StepFun", json.dumps(claude_cfg)),
        )
        conn.execute(
            "INSERT INTO providers(id, app_type, name, settings_config) VALUES (?,?,?,?)",
            ("codex-uuid", "codex", "StepFun", json.dumps(codex_cfg)),
        )
        conn.commit()
    finally:
        conn.close()
    return db


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    db = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE providers (
              id TEXT PRIMARY KEY,
              app_type TEXT NOT NULL,
              name TEXT NOT NULL,
              settings_config TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db
