"""CLI for StepFun audio: ``python -m stepfun_audio.cli tts|asr|chat|...``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audio import StepFunAudioClient, StepFunAudioConfig
from .chat import StepFunChatClient, StepFunChatConfig
from .models import DEFAULT_ASR_MODEL, DEFAULT_CHAT_MODEL, DEFAULT_TTS_MODEL, DEFAULT_TTS_VOICE
from .realtime import DEFAULT_REALTIME_MODEL, StepFunRealtimeClient, StepFunRealtimeConfig
from .tts_stream import (
    DEFAULT_STREAM_FORMAT,
    DEFAULT_STREAM_SAMPLE_RATE,
    StepFunTtsStreamClient,
    StepFunTtsStreamConfig,
)
from .voices import StepFunVoicesClient, StepFunVoicesConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stepfun-audio",
        description="CLI for StepFun TTS / ASR / Chat / Voices / Realtime (Step Plan).",
    )
    p.add_argument("--db", help="Path to CCSwitch sqlite DB (auto-detected by default).")
    p.add_argument(
        "--base-url", default="https://api.stepfun.com/step_plan/v1",
        help="HTTP base URL (WebSocket clients convert https→wss automatically).",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # ---- tts ----
    tts = sub.add_parser("tts", help="Text-to-speech (HTTP non-streaming)")
    tts.add_argument("text")
    tts.add_argument("-o", "--output")
    tts.add_argument("--model", default=DEFAULT_TTS_MODEL)
    tts.add_argument("--voice", default=DEFAULT_TTS_VOICE)
    tts.add_argument("--instruction", help='e.g. "语气温柔，语速偏慢"')
    tts.add_argument("--format", dest="response_format", default="mp3",
                     choices=("mp3", "wav", "pcm", "opus"))
    tts.add_argument("--sample-rate", type=int, default=24000)
    tts.add_argument("--speed", type=float, default=1.0)
    tts.add_argument("--volume", type=float, default=1.0)

    # ---- asr ----
    asr = sub.add_parser("asr", help="Speech-to-text (HTTP + SSE)")
    asr.add_argument("audio", help="Path to input audio (pcm_s16le recommended)")
    asr.add_argument("-o", "--output", help="Output text file (default: stdout)")
    asr.add_argument("--model", default=DEFAULT_ASR_MODEL)
    asr.add_argument("--language", default="zh")
    asr.add_argument("--no-itn", dest="enable_itn", action="store_false")
    asr.add_argument("--sample-rate", type=int, default=16000)
    asr.add_argument("--bits", type=int, default=16)
    asr.add_argument("--channels", type=int, default=1)

    # ---- chat ----
    chat = sub.add_parser("chat", help="Text chat completion")
    chat.add_argument("message", help="User message (single turn)")
    chat.add_argument("-o", "--output", help="Output text file (default: stdout)")
    chat.add_argument("--model", default=DEFAULT_CHAT_MODEL)
    chat.add_argument("--system", help="Optional system prompt")
    chat.add_argument("--temperature", type=float)
    chat.add_argument("--max-tokens", type=int)

    # ---- tts-stream ----
    ttss = sub.add_parser(
        "tts-stream", help="Streaming TTS via WebSocket (yields audio chunks)"
    )
    ttss.add_argument("text")
    ttss.add_argument("-o", "--output", required=True)
    ttss.add_argument("--model", default=DEFAULT_TTS_MODEL)
    ttss.add_argument("--voice", default=DEFAULT_TTS_VOICE)
    ttss.add_argument("--instruction")
    ttss.add_argument("--format", dest="response_format",
                      default=DEFAULT_STREAM_FORMAT,
                      choices=("wav", "pcm", "mp3", "opus"))
    ttss.add_argument("--sample-rate", type=int, default=DEFAULT_STREAM_SAMPLE_RATE)
    ttss.add_argument("--speed", type=float, default=1.0)
    ttss.add_argument("--volume", type=float, default=1.0)

    # ---- realtime ----
    rt = sub.add_parser(
        "realtime", help="Single-turn realtime voice chat (text in, audio out)"
    )
    rt.add_argument("text", help="User text to send to the assistant")
    rt.add_argument("-o", "--output", required=True)
    rt.add_argument("--model", default=DEFAULT_REALTIME_MODEL)
    rt.add_argument("--voice", default="linjiajiejie")
    rt.add_argument("--instructions", help="System / persona instruction")
    rt.add_argument("--input-audio-format", default="pcm16")
    rt.add_argument("--output-audio-format", default="pcm16")

    # ---- voices ----
    voices = sub.add_parser("voices", help="Voice preview & cloning")
    vsub = voices.add_subparsers(dest="voice_cmd", required=True)

    pv = vsub.add_parser("preview", help="Generate a sample for a voice id")
    pv.add_argument("--voice", default=DEFAULT_TTS_VOICE)
    pv.add_argument("--text", default="你好，我是音色试听样本。")
    pv.add_argument("-o", "--output", required=True)
    pv.add_argument("--format", dest="response_format", default="mp3",
                    choices=("mp3", "wav", "pcm"))
    pv.add_argument("--sample-rate", type=int, default=24000)

    cl = vsub.add_parser("clone", help="Clone a new voice from a reference clip")
    cl.add_argument("name", help="Name for the new voice")
    cl.add_argument("ref_audio", help="Path to a short reference audio clip")
    cl.add_argument("--ref-text", help="Transcript of the reference clip")
    cl.add_argument("--description")
    cl.add_argument("--sample-rate", type=int, default=24000)
    cl.add_argument("-o", "--output", help="Write the JSON response here")

    return p


def _ws_base(http_base: str) -> str:
    """Convert https:// → wss:// for WebSocket clients."""
    if http_base.startswith("https://"):
        return "wss://" + http_base[len("https://") :]
    if http_base.startswith("http://"):
        return "ws://" + http_base[len("http://") :]
    return http_base


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        api_key = _resolve_key(args.db)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        # ---- tts ----
        if args.cmd == "tts":
            blob = StepFunAudioClient(
                StepFunAudioConfig(api_key=api_key, base_url=args.base_url)
            ).text_to_speech(
                args.text,
                model=args.model,
                voice=args.voice,
                instruction=args.instruction,
                response_format=args.response_format,
                sample_rate=args.sample_rate,
                speed_ratio=args.speed,
                volume_ratio=args.volume,
            )
            out = _resolve_output(args.output, "tts", args.text, args.response_format)
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_bytes(blob)
            print(out)
            return 0

        # ---- asr ----
        if args.cmd == "asr":
            text = StepFunAudioClient(
                StepFunAudioConfig(api_key=api_key, base_url=args.base_url)
            ).transcribe(
                args.audio,
                model=args.model,
                language=args.language,
                enable_itn=args.enable_itn,
                sample_rate=args.sample_rate,
                bits=args.bits,
                channels=args.channels,
            )
            if args.output:
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(text, encoding="utf-8")
                print(args.output)
            else:
                print(text)
            return 0

        # ---- chat ----
        if args.cmd == "chat":
            messages: list[dict] = []
            if args.system:
                messages.append({"role": "system", "content": args.system})
            messages.append({"role": "user", "content": args.message})
            text = StepFunChatClient(
                StepFunChatConfig(api_key=api_key, base_url=args.base_url)
            ).chat(
                messages,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            if args.output:
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(text, encoding="utf-8")
                print(args.output)
            else:
                print(text)
            return 0

        # ---- tts-stream ----
        if args.cmd == "tts-stream":
            client = StepFunTtsStreamClient(
                StepFunTtsStreamConfig(
                    api_key=api_key,
                    base_url=_ws_base(args.base_url),
                    model=args.model,
                )
            )
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("wb") as fh:
                for chunk in client.stream_tts(
                    args.text,
                    voice=args.voice,
                    instruction=args.instruction,
                    response_format=args.response_format,
                    sample_rate=args.sample_rate,
                    speed_ratio=args.speed,
                    volume_ratio=args.volume,
                ):
                    fh.write(chunk)
            print(out_path)
            return 0

        # ---- realtime ----
        if args.cmd == "realtime":
            client = StepFunRealtimeClient(
                StepFunRealtimeConfig(
                    api_key=api_key,
                    base_url=_ws_base(args.base_url),
                    model=args.model,
                )
            )
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("wb") as fh:
                for chunk in client.say(
                    args.text,
                    voice=args.voice,
                    instructions=args.instructions,
                    input_audio_format=args.input_audio_format,
                    output_audio_format=args.output_audio_format,
                ):
                    fh.write(chunk)
            print(out_path)
            return 0

        # ---- voices ----
        if args.cmd == "voices":
            return _cmd_voices(args, api_key)

    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 2  # unreachable


def _cmd_voices(args: argparse.Namespace, api_key: str) -> int:
    client = StepFunVoicesClient(
        StepFunVoicesConfig(api_key=api_key, base_url=args.base_url)
    )
    if args.voice_cmd == "preview":
        blob = client.preview(
            voice_id=args.voice,
            text=args.text,
            sample_rate=args.sample_rate,
            response_format=args.response_format,
        )
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        print(out)
        return 0
    if args.voice_cmd == "clone":
        import json
        result = client.clone(
            name=args.name,
            ref_audio_path=args.ref_audio,
            ref_text=args.ref_text,
            sample_rate=args.sample_rate,
            description=args.description,
        )
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(args.output)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return 2


def _resolve_key(db: str | None) -> str:
    from stepfun_image.ccswitch import resolve_api_key
    return resolve_api_key(db)


def _resolve_output(
    explicit: str | None, kind: str, prompt: str, ext: str
) -> str:
    if explicit:
        return explicit
    import time
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in prompt)[:40].strip() or kind
    return str(Path("output") / f"{kind}-{int(time.time())}-{safe}.{ext}")


if __name__ == "__main__":
    sys.exit(main())
