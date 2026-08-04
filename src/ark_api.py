# -*- coding: utf-8 -*-
"""ARK API wrapper (Doubao Seed 2.0 Pro).

Reads ARK_API_KEY from environment or the project .env file.
Uses `requests` first and falls back to curl.exe on SSL failures
(this machine occasionally has SSL issues with requests).
"""
import os
import json
import base64
import time
import subprocess
import tempfile
import threading

ARK_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
MODEL = "doubao-seed-2-0-pro-260215"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_key() -> str:
    key = os.environ.get("ARK_API_KEY", "")
    if key:
        return key
    env_path = os.path.join(_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ARK_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


ARK_KEY = _load_key()

_requests_broken = False
_lock = threading.Lock()


def _b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _extract_text(d: dict) -> str:
    for it in d.get("output", []):
        if it.get("type") == "message":
            for c in it.get("content", []):
                if c.get("type") == "output_text":
                    return c["text"]
    return ""


def _post_requests(body: dict) -> dict:
    import requests
    r = requests.post(
        ARK_URL,
        headers={"Authorization": f"Bearer {ARK_KEY}",
                 "Content-Type": "application/json"},
        json=body, timeout=120,
    )
    return r.json()


CURL_BIN = "curl.exe" if os.name == "nt" else "curl"


def _post_curl(body: dict) -> dict:
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        r = subprocess.run(
            [CURL_BIN, "-s", "--max-time", "180", "-X", "POST", ARK_URL,
             "-H", f"Authorization: Bearer {ARK_KEY}",
             "-H", "Content-Type: application/json",
             "-d", f"@{tmp}"],
            capture_output=True, timeout=200,
        )
        return json.loads(r.stdout.decode("utf-8", errors="replace"))
    finally:
        os.unlink(tmp)


def _call(content, temperature=0.1, max_tokens=1024, retries=3) -> str:
    global _requests_broken
    body = {
        "model": MODEL,
        "input": [{"role": "user", "type": "message", "content": content}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    last_err = None
    for i in range(retries):
        try:
            if _requests_broken:
                d = _post_curl(body)
            else:
                try:
                    d = _post_requests(body)
                except Exception:
                    with _lock:
                        _requests_broken = True
                    d = _post_curl(body)
            if "error" in d:
                last_err = d["error"]
                # rate limit -> wait longer
                time.sleep(3.0 * (i + 1))
                continue
            txt = _extract_text(d)
            if txt:
                return txt
        except Exception as e:
            last_err = e
        time.sleep(1.5 * (i + 1))
    print("[api fail]", str(last_err)[:200])
    return ""


def _parse(txt: str):
    """Extract a JSON object/array from a model reply."""
    if not txt:
        return None
    txt = txt.replace("```json", "```")
    if "```" in txt:
        parts = txt.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("[") or p.startswith("{"):
                txt = p
                break
    for open_c, close_c in (("[", "]"), ("{", "}")):
        s, e = txt.find(open_c), txt.rfind(close_c)
        if s >= 0 and e > s:
            try:
                return json.loads(txt[s:e + 1])
            except Exception:
                continue
    return None


def call_text(prompt: str, **kwargs) -> str:
    return _call([{"type": "input_text", "text": prompt}], **kwargs)


def call_image(image_path: str, prompt: str, **kwargs) -> str:
    ext = os.path.splitext(image_path)[1].lstrip(".").lower().replace("jpg", "jpeg")
    content = [
        {"type": "input_image",
         "image_url": f"data:image/{ext};base64,{_b64_file(image_path)}"},
        {"type": "input_text", "text": prompt},
    ]
    return _call(content, **kwargs)


if __name__ == "__main__":
    print("key loaded:", bool(ARK_KEY))
    out = call_text("Reply with the single word OK", max_tokens=16)
    print("api reply:", out)
