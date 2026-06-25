"""Command-line entry point: ``stepfun t2i ...`` / ``stepfun edit ...`` / ``stepfun whoami``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __init__  # noqa: F401  (ensure package import)
from .client import (
    DEFAULT_MODEL,
    StepFunConfig,
    StepFunImageClient,
    default_output_path,
    save_bytes,
)
from .ccswitch import KEY_ENV_VAR, load_api_key_from_ccswitch, resolve_api_key


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stepfun",
        description="CLI for StepFun text-to-image / image-edit (Step Plan).",
    )
    p.add_argument("--db", help="Path to CCSwitch sqlite DB (auto-detected by default).")
    p.add_argument("--base-url", default="https://api.stepfun.com/step_plan/v1")
    p.add_argument("--model", default=DEFAULT_MODEL)

    sub = p.add_subparsers(dest="cmd", required=True)

    t2i = sub.add_parser("t2i", help="text-to-image generation")
    t2i.add_argument("prompt")
    t2i.add_argument("-o", "--output")
    t2i.add_argument("--seed", type=int, default=1)
    t2i.add_argument("--steps", type=int, default=8)
    t2i.add_argument("--cfg-scale", type=float, default=1.0)
    t2i.add_argument("--text-mode", action="store_true", default=True)
    t2i.add_argument("--no-text-mode", dest="text_mode", action="store_false")
    t2i.add_argument("--n", type=int, default=1)
    t2i.add_argument("--size")

    edit = sub.add_parser("edit", help="image edit")
    edit.add_argument("image", help="Path to input image")
    edit.add_argument("prompt")
    edit.add_argument("-o", "--output")
    edit.add_argument("--seed", type=int, default=1)
    edit.add_argument("--steps", type=int, default=8)
    edit.add_argument("--cfg-scale", type=float, default=1.0)
    edit.add_argument("--text-mode", action="store_true", default=True)
    edit.add_argument("--no-text-mode", dest="text_mode", action="store_false")

    sub.add_parser("whoami", help="Print which API key source is being used (no API call).")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "whoami":
        return _cmd_whoami(args)
    try:
        cfg = StepFunConfig(
            api_key=resolve_api_key(args.db),
            base_url=args.base_url,
            model=args.model,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    client = StepFunImageClient(cfg)

    try:
        if args.cmd == "t2i":
            blobs = client.text_to_image(
                args.prompt,
                seed=args.seed,
                steps=args.steps,
                cfg_scale=args.cfg_scale,
                text_mode=args.text_mode,
                size=args.size,
                n=args.n,
            )
            kind = "t2i"
        elif args.cmd == "edit":
            blobs = client.edit_image(
                args.image,
                args.prompt,
                seed=args.seed,
                steps=args.steps,
                cfg_scale=args.cfg_scale,
                text_mode=args.text_mode,
            )
            kind = "edit"
        else:  # pragma: no cover
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    written: list[Path] = []
    for i, blob in enumerate(blobs):
        if args.output:
            target = Path(args.output)
            if len(blobs) > 1:
                stem = target.stem
                target = target.with_name(f"{stem}-{i}{target.suffix or '.png'}")
        else:
            target = default_output_path(args.prompt, kind=kind)
        written.append(save_bytes(blob, target))

    for p in written:
        print(p.resolve())
    return 0


def _cmd_whoami(args: argparse.Namespace) -> int:
    import os
    env_key = os.getenv(KEY_ENV_VAR)
    db_key = load_api_key_from_ccswitch(args.db)
    print(f"env $STEP_API_KEY:    {'set' if env_key else 'unset'}")
    print(f"CCSwitch StepFun key: {'found' if db_key else 'not found'}")
    if db_key:
        masked = db_key[:6] + "..." + db_key[-4:]
        print(f"  preview: {masked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
