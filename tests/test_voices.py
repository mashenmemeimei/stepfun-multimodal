"""Tests for voices.py — voice preview + clone (HTTP)."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from stepfun_audio.voices import StepFunVoicesClient, StepFunVoicesConfig
from stepfun_audio.models import TTS_SAMPLE_RATES


@pytest.fixture
def client() -> StepFunVoicesClient:
    return StepFunVoicesClient(
        StepFunVoicesConfig(api_key="test-key", base_url="https://x.example/v1")
    )


def test_preview_posts_and_returns_bytes(client):
    fake_mp3 = b"\xff\xfb" + b"\x00" * 32
    resp = MagicMock()
    resp.content = fake_mp3
    resp.raise_for_status.return_value = None

    with patch("stepfun_audio.voices.requests.post", return_value=resp) as post:
        out = client.preview(voice_id="cixingnansheng", text="嗨", sample_rate=24000)

    assert out == fake_mp3
    args, kwargs = post.call_args
    assert args[0] == "https://x.example/v1/audio/voices/preview"
    body = kwargs["json"]
    assert body == {
        "voice_id": "cixingnansheng",
        "text": "嗨",
        "sample_rate": 24000,
        "response_format": "mp3",
    }
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_preview_rejects_invalid_sample_rate(client):
    with pytest.raises(ValueError, match="sample_rate"):
        client.preview(sample_rate=11025)


def test_clone_sends_b64_audio_and_returns_json(client, tmp_path):
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFF" + b"\x00" * 64)

    payload = {"voice_id": "v_new_123", "name": "我的音色"}
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None

    with patch("stepfun_audio.voices.requests.post", return_value=resp) as post:
        result = client.clone(
            name="我的音色",
            ref_audio_path=ref,
            ref_text="这是一段参考文本",
            description="测试用",
            sample_rate=24000,
        )

    assert result == payload
    args, kwargs = post.call_args
    assert args[0] == "https://x.example/v1/audio/voices"
    body = kwargs["json"]
    assert body["name"] == "我的音色"
    assert body["ref_text"] == "这是一段参考文本"
    assert body["description"] == "测试用"
    assert body["sample_rate"] == 24000
    assert base64.b64decode(body["ref_audio"]) == ref.read_bytes()


def test_clone_missing_file_raises(client):
    with pytest.raises(FileNotFoundError):
        client.clone(name="x", ref_audio_path="/no/such/file.wav")


def test_clone_drops_optional_fields_when_none(client, tmp_path):
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x")
    resp = MagicMock()
    resp.json.return_value = {"voice_id": "v"}
    resp.raise_for_status.return_value = None

    with patch("stepfun_audio.voices.requests.post", return_value=resp) as post:
        client.clone(name="n", ref_audio_path=ref)

    body = post.call_args.kwargs["json"]
    assert "ref_text" not in body
    assert "description" not in body


def test_sample_rates_include_24000():
    assert 24000 in TTS_SAMPLE_RATES
