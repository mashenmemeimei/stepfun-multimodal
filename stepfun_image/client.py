"""Thin wrapper around StepFun's text-to-image and image-edit endpoints.

Endpoint paths follow the Step Plan integration guide:
- text-to-image: POST {base_url}/images/generations
- image edit:    POST {base_url}/images/edits
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .ccswitch import resolve_api_key

DEFAULT_BASE_URL = "https://api.stepfun.com/step_plan/v1"
DEFAULT_MODEL = "step-image-edit-2"


@dataclass
class StepFunConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: int = 120

    @classmethod
    def auto(cls, db_path: str | os.PathLike | None = None) -> "StepFunConfig":
        return cls(api_key=resolve_api_key(db_path))


class StepFunImageClient:
    def __init__(self, config: StepFunConfig | None = None) -> None:
        self.config = config or StepFunConfig.auto()

    # ---- shared ----
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    # ---- text-to-image ----
    def text_to_image(
        self,
        prompt: str,
        *,
        response_format: str = "b64_json",
        cfg_scale: float = 1.0,
        steps: int = 8,
        seed: int = 1,
        text_mode: bool = True,
        size: str | None = None,
        n: int = 1,
        extra_body: dict[str, Any] | None = None,
    ) -> list[bytes]:
        """Generate one or more images from a text prompt.

        Returns a list of decoded PNG bytes (one per image).
        """
        url = f"{self.config.base_url}/images/generations"
        body: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "response_format": response_format,
            "cfg_scale": cfg_scale,
            "steps": steps,
            "seed": seed,
            "text_mode": text_mode,
            "n": n,
        }
        if size:
            body["size"] = size
        if extra_body:
            body.update(extra_body)

        resp = requests.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=body,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return [base64.b64decode(item["b64_json"]) for item in data["data"]]

    # ---- image edit ----
    def edit_image(
        self,
        image_path: str | os.PathLike,
        prompt: str,
        *,
        response_format: str = "b64_json",
        cfg_scale: float = 1.0,
        steps: int = 8,
        seed: int = 1,
        text_mode: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> list[bytes]:
        """Edit an existing image and return decoded PNG bytes."""
        url = f"{self.config.base_url}/images/edits"
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(path)

        mime = _guess_mime(path)
        with path.open("rb") as fh:
            files = {"image": (path.name, fh, mime)}
            data: dict[str, Any] = {
                "model": self.config.model,
                "prompt": prompt,
                "response_format": response_format,
                "cfg_scale": str(cfg_scale),
                "steps": str(steps),
                "seed": str(seed),
                "text_mode": str(text_mode).lower(),
            }
            if extra_body:
                data.update({k: str(v) for k, v in extra_body.items()})
            resp = requests.post(
                url,
                headers=self._headers(),
                files=files,
                data=data,
                timeout=self.config.timeout,
            )
        resp.raise_for_status()
        payload = resp.json()
        return [base64.b64decode(item["b64_json"]) for item in payload["data"]]


def save_bytes(blob: bytes, out_path: str | os.PathLike) -> Path:
    """Write image bytes to disk, creating parent dirs as needed."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    return out


def default_output_path(prompt: str, kind: str, ext: str = "png") -> Path:
    """Generate a deterministic, timestamped output filename."""
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in prompt)[:40].strip() or "image"
    return Path("output") / f"{kind}-{int(time.time())}-{safe}.{ext}"


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix, "application/octet-stream")
