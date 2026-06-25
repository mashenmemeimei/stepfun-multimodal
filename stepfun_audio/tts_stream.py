"""WebSocket streaming TTS for stepaudio-2.5-tts.

Endpoint: wss://api.stepfun.com/step_plan/v1/realtime/audio?model=stepaudio-2.5-tts

Protocol (provisional — verified against the live API on 2026-06-25 that
the handshake works; the text-submission event name was not confirmed
and may need adjustment based on the open-platform docs at
https://platform.stepfun.com/zh/api-reference/audio/ws-audio):

    1. Server sends  {"type": "tts.connection.done", "data": {"session_id": "..."}}
    2. Client sends  {"type": "tts.create", "data": {<session config, no text>}}
    3. Client sends  {"type": "tts.text", "data": {"session_id": "...", "text": "..."}}
    4. Server streams zero or more  {"type": "tts.chunk", "data": {"audio": "<b64>"}}
    5. Server sends  {"type": "tts.completion", "data": {...}}

NOTE: if the server drops the connection after step 2 with no error, the
text event name in step 3 is wrong. The probe-tested alternatives were
``tts.text.delta`` (data is required), ``tts.sentence``, and a handful of
others — all returned ``invalid event format``. Adjust here once the
authoritative event name is known.
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
from .models import DEFAULT_TTS_MODEL, DEFAULT_TTS_VOICE, TTS_SAMPLE_RATES

WS_BASE_URL = "wss://api.stepfun.com/step_plan/v1"
DEFAULT_STREAM_FORMAT = "wav"
DEFAULT_STREAM_SAMPLE_RATE = 16000

# Recognised terminal event types — accept several spellings to be safe.
_END_EVENTS = frozenset({"tts.completion", "tts.done", "done", "session.end"})


@dataclass
class StepFunTtsStreamConfig:
    api_key: str
    base_url: str = WS_BASE_URL
    model: str = DEFAULT_TTS_MODEL
    timeout: int = 120


class StepFunTtsStreamClient:
    def __init__(self, config: StepFunTtsStreamConfig | None = None) -> None:
        if config is None:
            config = StepFunTtsStreamConfig(api_key=resolve_api_key())
        self.config = config

    # ---- public streaming API ----
    def stream_tts(
        self,
        text: str,
        *,
        voice: str = DEFAULT_TTS_VOICE,
        instruction: str | None = None,
        response_format: str = DEFAULT_STREAM_FORMAT,
        sample_rate: int = DEFAULT_STREAM_SAMPLE_RATE,
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
    ) -> Iterator[bytes]:
        """Open a WebSocket, send a tts.create event, and yield audio chunks.

        The iterator stops once the server emits a terminal event.
        """
        if sample_rate not in TTS_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate must be one of {TTS_SAMPLE_RATES}, got {sample_rate!r}"
            )

        url = f"{self.config.base_url}/realtime/audio?model={self.config.model}"
        ws = websocket.create_connection(
            url,
            header=[f"Authorization: Bearer {self.config.api_key}"],
            timeout=self.config.timeout,
        )
        try:
            # 1) wait for tts.connection.done
            session_id = self._wait_for_session(ws)

            # 2) send tts.create (session config; NO text here)
            create_body: dict = {
                "session_id": session_id,
                "voice_id": voice,
                "response_format": response_format,
                "volume_ratio": volume_ratio,
                "speed_ratio": speed_ratio,
                "sample_rate": sample_rate,
            }
            if instruction:
                create_body["instruction"] = instruction
            ws.send(json.dumps({"type": "tts.create", "data": create_body}))

            # 3) send the text to synthesise (provisional event name)
            ws.send(
                json.dumps(
                    {
                        "type": "tts.text",
                        "data": {"session_id": session_id, "text": text},
                    }
                )
            )

            # 4) yield audio chunks until terminal event
            for event in self._iter_events(ws):
                etype = event.get("type")
                if etype in _END_EVENTS:
                    return
                audio_b64 = (
                    event.get("data", {}).get("audio")
                    or event.get("audio")
                )
                if audio_b64:
                    yield base64.b64decode(audio_b64)
        finally:
            ws.close()

    # ---- internals ----
    @staticmethod
    def _wait_for_session(ws: websocket.WebSocket) -> str:
        while True:
            raw = ws.recv()
            if not raw:
                raise RuntimeError("WebSocket closed before tts.connection.done")
            event = json.loads(raw)
            if event.get("type") == "tts.connection.done":
                sid = event.get("data", {}).get("session_id")
                if not sid:
                    raise RuntimeError(f"tts.connection.done missing session_id: {event}")
                return sid

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
