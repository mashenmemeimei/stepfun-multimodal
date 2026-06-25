"""WebSocket realtime voice chat for stepaudio-2.5-realtime.

Endpoint: wss://api.stepfun.com/step_plan/v1/realtime?model=stepaudio-2.5-realtime

The full Realtime API supports a long-lived bidirectional audio conversation.
For one-shot CLI usage we expose a single-turn helper that:
    1. Opens the WS, sends a ``session.update`` config event.
    2. Posts a user text message via ``conversation.item.create``.
    3. Triggers ``response.create`` and collects ``response.audio.delta``
       chunks until ``response.done`` / ``response.completed``.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Iterator

import websocket  # type: ignore[import-untyped]

from stepfun_image.ccswitch import resolve_api_key

from .audio import DEFAULT_BASE_URL
from .models import DEFAULT_CHAT_MODEL  # noqa: F401  (re-exported below)

WS_BASE_URL = "wss://api.stepfun.com/step_plan/v1"
DEFAULT_REALTIME_MODEL = "stepaudio-2.5-realtime"

_END_EVENTS = frozenset(
    {"response.done", "response.completed", "response.cancelled", "error"}
)


@dataclass
class StepFunRealtimeConfig:
    api_key: str
    base_url: str = WS_BASE_URL
    model: str = DEFAULT_REALTIME_MODEL
    timeout: int = 120


class StepFunRealtimeClient:
    def __init__(self, config: StepFunRealtimeConfig | None = None) -> None:
        if config is None:
            config = StepFunRealtimeConfig(api_key=resolve_api_key())
        self.config = config

    # ---- public streaming API ----
    def say(
        self,
        text: str,
        *,
        voice: str = "linjiajiejie",
        instructions: str | None = None,
        input_audio_format: str = "pcm16",
        output_audio_format: str = "pcm16",
    ) -> Iterator[bytes]:
        """Send ``text`` and yield the assistant's reply as audio chunks.

        Single-turn helper — opens a fresh WebSocket, drives the protocol,
        and closes. For multi-turn / interactive use, build your own client
        on top of :mod:`websocket`.
        """
        ws = websocket.create_connection(
            f"{self.config.base_url}/realtime?model={self.config.model}",
            header=[f"Authorization: Bearer {self.config.api_key}"],
            timeout=self.config.timeout,
        )
        try:
            session: dict = {
                "modalities": ["text", "audio"],
                "voice": voice,
                "input_audio_format": input_audio_format,
                "output_audio_format": output_audio_format,
            }
            if instructions:
                session["instructions"] = instructions

            ws.send(json.dumps({
                "event_id": "evt_001",
                "type": "session.update",
                "session": session,
            }))

            ws.send(json.dumps({
                "event_id": "evt_002",
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }))

            ws.send(json.dumps({
                "event_id": "evt_003",
                "type": "response.create",
            }))

            for event in self._iter_events(ws):
                etype = event.get("type")
                if etype in _END_EVENTS:
                    if etype == "error":
                        raise RuntimeError(f"realtime error: {event}")
                    return
                # response.audio.delta (and a few plausible aliases)
                delta = (
                    event.get("delta")
                    or event.get("audio")
                    or event.get("data", {}).get("delta")
                )
                if delta:
                    yield base64.b64decode(delta)
        finally:
            ws.close()

    # ---- internals ----
    @staticmethod
    def _iter_events(ws: websocket.WebSocket) -> Iterator[dict]:
        while True:
            raw = ws.recv()
            if not raw:
                return
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                continue
