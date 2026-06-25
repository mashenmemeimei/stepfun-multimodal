"""Tests for the WebSocket streaming clients (mocked)."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import pytest

from stepfun_audio.realtime import StepFunRealtimeClient, StepFunRealtimeConfig
from stepfun_audio.tts_stream import StepFunTtsStreamClient, StepFunTtsStreamConfig
from stepfun_audio.models import TTS_SAMPLE_RATES


# ---- helpers ----

class FakeWS:
    """Minimal stand-in for websocket.WebSocket."""

    def __init__(self, scripted: list[str]) -> None:
        self._scripted = list(scripted)
        self.sent: list[str] = []
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def recv(self) -> str:
        if not self._scripted:
            return ""
        return self._scripted.pop(0)

    def close(self) -> None:
        self.closed = True


def _evt(type_: str, **fields) -> str:
    return json.dumps({"type": type_, "data": fields})


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


# ---- TTS stream ----

@pytest.fixture
def tts_client() -> StepFunTtsStreamClient:
    return StepFunTtsStreamClient(
        StepFunTtsStreamConfig(
            api_key="k",
            base_url="wss://x.example/v1",
            model="stepaudio-2.5-tts",
        )
    )


def test_tts_stream_yields_chunks_and_stops_at_completion(tts_client):
    script = [
        _evt("tts.connection.done", session_id="sid-1"),
        _evt("tts.chunk", audio=_b64(b"AAAA")),
        _evt("tts.chunk", audio=_b64(b"BBBB")),
        _evt("tts.completion"),
        # extra events after completion should never be reached
        _evt("tts.chunk", audio=_b64(b"NEVER")),
    ]
    fake = FakeWS(script)

    with pytest.MonkeyPatch.context() as mp:
        import stepfun_audio.tts_stream as mod
        mp.setattr(mod.websocket, "create_connection", lambda *a, **kw: fake)
        chunks = list(tts_client.stream_tts("你好", voice="cixingnansheng"))

    assert chunks == [b"AAAA", b"BBBB"]
    assert fake.closed is True

    # Client sends tts.create (config) then tts.text (input)
    assert len(fake.sent) == 2
    create = json.loads(fake.sent[0])
    text_evt = json.loads(fake.sent[1])
    assert create["type"] == "tts.create"
    assert create["data"]["session_id"] == "sid-1"
    assert create["data"]["voice_id"] == "cixingnansheng"
    assert create["data"]["sample_rate"] == 16000
    assert create["data"]["response_format"] == "wav"
    assert "text" not in create["data"]  # text goes in a separate event

    assert text_evt["type"] == "tts.text"
    assert text_evt["data"]["session_id"] == "sid-1"
    assert text_evt["data"]["text"] == "你好"


def test_tts_stream_rejects_bad_sample_rate(tts_client):
    with pytest.raises(ValueError, match="sample_rate"):
        list(tts_client.stream_tts("hi", sample_rate=11025))


def test_tts_stream_closes_on_error(tts_client):
    fake = FakeWS([_evt("tts.connection.done", session_id="sid")])
    with pytest.MonkeyPatch.context() as mp:
        import stepfun_audio.tts_stream as mod
        mp.setattr(mod.websocket, "create_connection", lambda *a, **kw: fake)
        # Inject a failure mid-stream
        fake._scripted.extend([
            _evt("tts.chunk", audio=_b64(b"hi")),
        ])
        # Make recv raise after first chunk
        original_recv = fake.recv
        calls = {"n": 0}

        def recv_then_fail():
            calls["n"] += 1
            if calls["n"] > 2:
                raise RuntimeError("boom")
            return original_recv()

        fake.recv = recv_then_fail
        with pytest.raises(RuntimeError, match="boom"):
            list(tts_client.stream_tts("x"))
    assert fake.closed is True


# ---- Realtime ----

@pytest.fixture
def rt_client() -> StepFunRealtimeClient:
    return StepFunRealtimeClient(
        StepFunRealtimeConfig(api_key="k", base_url="wss://x.example/v1")
    )


def test_realtime_say_runs_protocol_and_yields_deltas(rt_client):
    script = [
        _evt("session.created", session_id="sess"),
        _evt("response.audio.delta", delta=_b64(b"PCM-1")),
        _evt("response.audio.delta", delta=_b64(b"PCM-2")),
        _evt("response.audio.done"),
        _evt("response.done"),
        _evt("response.audio.delta", delta=_b64(b"NEVER")),
    ]
    fake = FakeWS(script)

    with pytest.MonkeyPatch.context() as mp:
        import stepfun_audio.realtime as mod
        mp.setattr(mod.websocket, "create_connection", lambda *a, **kw: fake)
        chunks = list(
            rt_client.say(
                "陪我聊聊",
                voice="linjiajiejie",
                instructions="你是温暖搭子",
            )
        )

    assert chunks == [b"PCM-1", b"PCM-2"]
    assert fake.closed is True

    # 3 events sent: session.update, conversation.item.create, response.create
    sent_types = [json.loads(s)["type"] for s in fake.sent]
    assert sent_types == [
        "session.update",
        "conversation.item.create",
        "response.create",
    ]
    sess = json.loads(fake.sent[0])["session"]
    assert sess["modalities"] == ["text", "audio"]
    assert sess["voice"] == "linjiajiejie"
    assert sess["instructions"] == "你是温暖搭子"

    item = json.loads(fake.sent[1])["item"]
    assert item["role"] == "user"
    assert item["content"] == [{"type": "input_text", "text": "陪我聊聊"}]


def test_realtime_raises_on_error_event(rt_client):
    script = [
        json.dumps({"type": "error", "error": {"message": "nope"}}),
    ]
    fake = FakeWS(script)
    with pytest.MonkeyPatch.context() as mp:
        import stepfun_audio.realtime as mod
        mp.setattr(mod.websocket, "create_connection", lambda *a, **kw: fake)
        with pytest.raises(RuntimeError, match="realtime error"):
            list(rt_client.say("hi"))
    assert fake.closed is True


def test_realtime_skips_garbled_messages(rt_client):
    # Empty string from recv() means the WS closed — that's a real terminator,
    # so the only "garbled" case we tolerate in-flight is non-JSON.
    script = [
        "not-json",
        "{also-not-json",
        _evt("response.audio.delta", delta=_b64(b"only-good")),
        _evt("response.done"),
    ]
    fake = FakeWS(script)
    with pytest.MonkeyPatch.context() as mp:
        import stepfun_audio.realtime as mod
        mp.setattr(mod.websocket, "create_connection", lambda *a, **kw: fake)
        chunks = list(rt_client.say("x"))
    assert chunks == [b"only-good"]


def test_sample_rates_includes_16k():
    assert 16000 in TTS_SAMPLE_RATES
