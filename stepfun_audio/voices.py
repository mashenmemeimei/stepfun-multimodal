"""Voice preview and cloning via HTTP.

Endpoints (Step Plan):
- POST /step_plan/v1/audio/voices/preview  -> sample audio for a voice id
- POST /step_plan/v1/audio/voices          -> create a new voice from a ref clip
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from stepfun_image.ccswitch import resolve_api_key

from .audio import DEFAULT_BASE_URL
from .models import DEFAULT_TTS_VOICE, TTS_SAMPLE_RATES


@dataclass
class StepFunVoicesConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int = 120


class StepFunVoicesClient:
    def __init__(self, config: StepFunVoicesConfig | None = None) -> None:
        self.config = config or StepFunVoicesConfig(api_key=resolve_api_key())

    # ---- helpers ----
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    # ---- preview ----
    def preview(
        self,
        voice_id: str = DEFAULT_TTS_VOICE,
        *,
        text: str = "你好，我是音色试听样本。",
        sample_rate: int = 24000,
        response_format: str = "mp3",
    ) -> bytes:
        """Generate a short audio sample for a voice id and return raw bytes."""
        if sample_rate not in TTS_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate must be one of {TTS_SAMPLE_RATES}, got {sample_rate!r}"
            )
        body = {
            "voice_id": voice_id,
            "text": text,
            "sample_rate": sample_rate,
            "response_format": response_format,
        }
        resp = requests.post(
            f"{self.config.base_url}/audio/voices/preview",
            headers=self._headers(),
            json=body,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.content

    # ---- clone ----
    def clone(
        self,
        name: str,
        ref_audio_path: str | os.PathLike,
        *,
        ref_text: str | None = None,
        sample_rate: int = 24000,
        description: str | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Clone a new voice from a short reference audio clip.

        The reference audio is sent base64-encoded under ``ref_audio``.
        Returns the parsed JSON response (typically includes a new voice id).
        """
        path = Path(ref_audio_path)
        if not path.exists():
            raise FileNotFoundError(path)

        body: dict[str, Any] = {
            "name": name,
            "ref_audio": base64.b64encode(path.read_bytes()).decode(),
            "sample_rate": sample_rate,
        }
        if ref_text is not None:
            body["ref_text"] = ref_text
        if description is not None:
            body["description"] = description
        if extra_body:
            body.update(extra_body)

        resp = requests.post(
            f"{self.config.base_url}/audio/voices",
            headers=self._headers(),
            json=body,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.json()
