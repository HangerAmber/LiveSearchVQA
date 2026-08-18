# -*- coding: utf-8 -*-
"""DashScope OpenAI-compatible wrapper for Qwen text and vision models.

The API key is read from ``QWEN_API_KEY`` (preferred), ``DASHSCOPE_API_KEY``,
or the project ``.env`` file.  No credential is stored in tracked files.
"""
import base64
import json
import os
import subprocess
import tempfile
import threading
import time

import requests

QWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
TEXT_MODEL = os.environ.get("QWEN_TEXT_MODEL", "qwen-plus")
VISION_MODEL = os.environ.get("QWEN_VISION_MODEL", "qwen3-vl-plus")
FAST_VISION_MODEL = os.environ.get("QWEN_FAST_VISION_MODEL", "qwen3.5-flash")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_key() -> str:
    for env_name in ("QWEN_API_KEY", "DASHSCOPE_API_KEY"):
        key = os.environ.get(env_name, "").strip()
        if key:
            return key
    env_path = os.path.join(_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(("QWEN_API_KEY=", "DASHSCOPE_API_KEY=")):
                    return line.split("=", 1)[1].strip()
    return ""


QWEN_KEY = _load_key()
CURL_BIN = "curl.exe" if os.name == "nt" else "curl"
_requests_broken = False
_lock = threading.Lock()
_max_concurrency = max(1, int(os.environ.get("QWEN_MAX_CONCURRENCY", "2")))
_api_slots = threading.BoundedSemaphore(_max_concurrency)
_request_timeout = max(20, int(os.environ.get("QWEN_REQUEST_TIMEOUT", "60")))
_curl_timeout = _request_timeout + 30


def _b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _post_requests(body: dict) -> dict:
    response = requests.post(
        QWEN_URL,
        headers={
            "Authorization": f"Bearer {QWEN_KEY}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=_request_timeout,
    )
    response.raise_for_status()
    return response.json()


def _post_curl(body: dict) -> dict:
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        result = subprocess.run(
            [
                CURL_BIN, "-sS", "--max-time", str(_curl_timeout),
                "-X", "POST", QWEN_URL,
                "-H", f"Authorization: Bearer {QWEN_KEY}",
                "-H", "Content-Type: application/json", "-d", f"@{tmp}",
            ],
            capture_output=True,
            timeout=_curl_timeout + 20,
        )
        return json.loads(result.stdout.decode("utf-8", errors="replace"))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _content_text(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", "")) for part in content
            if isinstance(part, dict) and part.get("text")
        )
    return str(content or "")


def _call_inner(messages, model: str, temperature=0.1, max_tokens=1024,
                retries=3, json_object=False) -> str:
    """Call a Qwen model through the OpenAI-compatible Chat API."""
    global _requests_broken
    if not QWEN_KEY:
        raise RuntimeError("QWEN_API_KEY is not configured")
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }
    if json_object:
        body["response_format"] = {"type": "json_object"}
    last_err = None
    for attempt in range(retries):
        try:
            if _requests_broken:
                data = _post_curl(body)
            else:
                try:
                    data = _post_requests(body)
                except (requests.exceptions.SSLError,
                        requests.exceptions.ConnectionError):
                    with _lock:
                        _requests_broken = True
                    data = _post_curl(body)
            if data.get("error"):
                last_err = data["error"]
            else:
                text = _content_text(data).strip()
                if text:
                    return text
        except Exception as exc:
            last_err = exc
        time.sleep(2.0 * (attempt + 1))
    print("[qwen api fail]", str(last_err)[:240])
    return ""


def _call(messages, model: str, temperature=0.1, max_tokens=1024,
          retries=3, json_object=False) -> str:
    """Call DashScope behind a small process-wide concurrency cap."""
    with _api_slots:
        return _call_inner(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, retries=retries, json_object=json_object,
        )


def call_text(prompt: str, model=TEXT_MODEL, **kwargs) -> str:
    return _call(
        [{"role": "user", "content": prompt}], model=model, **kwargs
    )


def call_image(image_path: str, prompt: str, model=VISION_MODEL,
               **kwargs) -> str:
    ext = os.path.splitext(image_path)[1].lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"
    content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{ext};base64,{_b64_file(image_path)}"
            },
        },
        {"type": "text", "text": prompt},
    ]
    return _call(
        [{"role": "user", "content": content}], model=model, **kwargs
    )


if __name__ == "__main__":
    print("key loaded:", bool(QWEN_KEY))
    print("text model:", TEXT_MODEL)
    print("api reply:", call_text("Reply with OK only", max_tokens=16))
