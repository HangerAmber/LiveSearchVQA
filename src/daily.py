# -*- coding: utf-8 -*-
"""Safe daily rebuild for the paper-profile benchmark and public demo.

The published split is replaced only after a complete staging split passes
strict validation.  Failed crawls, missing credentials, or partial model runs
leave the existing demo untouched.
"""
import json
import os
import shutil
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive_v2")


def _env_has(name):
    if os.environ.get(name, "").strip():
        return True
    env_path = os.path.join(_ROOT, ".env")
    if not os.path.exists(env_path):
        return False
    with open(env_path, encoding="utf-8") as f:
        return any(line.strip().startswith(name + "=") and
                   line.split("=", 1)[1].strip() for line in f)


def require_credentials():
    missing = [name for name in ("ARK_API_KEY", "QWEN_API_KEY")
               if not _env_has(name)]
    if missing:
        print("[daily] FATAL: missing " + ", ".join(missing) +
              "; published split remains unchanged")
        raise SystemExit(1)


def archive_previous():
    benchmark = os.path.join(DATA_DIR, "benchmark_v2.json")
    if not os.path.exists(benchmark):
        return
    with open(benchmark, encoding="utf-8") as f:
        items = json.load(f)
    if not items:
        return
    build_date = items[0].get("build_date") or "unknown"
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    destination = os.path.join(ARCHIVE_DIR, f"{build_date}.json")
    if not os.path.exists(destination):
        shutil.copy2(benchmark, destination)
        print(f"[archive] previous split -> archive_v2/{build_date}.json")


def _snapshot_items():
    """Yield items from the current split and every dated public snapshot."""
    paths = [os.path.join(DATA_DIR, "benchmark_v2.json")]
    if os.path.isdir(ARCHIVE_DIR):
        paths.extend(
            os.path.join(ARCHIVE_DIR, name)
            for name in os.listdir(ARCHIVE_DIR)
            if name.endswith(".json")
        )
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                payload = payload.get("items", payload.get("questions", []))
            yield from payload
        except (OSError, ValueError, TypeError):
            print(f"[prune] warning: could not read snapshot {path}")


def prune_to_published_split():
    """Keep images needed by current and archived public splits."""
    benchmark_path = os.path.join(DATA_DIR, "benchmark_v2.json")
    article_path = os.path.join(DATA_DIR, "articles.json")
    image_dir = os.path.join(DATA_DIR, "images")
    with open(benchmark_path, encoding="utf-8") as f:
        items = json.load(f)
    keep_images = {
        os.path.basename(item["image"])
        for item in _snapshot_items()
        if item.get("image")
    }
    keep_articles = {item["article_id"] for item in items}
    removed = 0
    for name in os.listdir(image_dir):
        if name not in keep_images:
            os.remove(os.path.join(image_dir, name))
            removed += 1
    if os.path.exists(article_path):
        with open(article_path, encoding="utf-8") as f:
            articles = json.load(f)
        articles = [a for a in articles if a.get("id") in keep_articles]
        with open(article_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(articles, f, ensure_ascii=False, indent=1)
    print(f"[prune] removed {removed} images; kept {len(keep_images)} "
          "current/archive images")


def run(script, *args):
    command = [sys.executable, "-u", "-X", "utf8",
               os.path.join(_ROOT, "src", script), *args]
    print("[run]", " ".join(command))
    subprocess.run(command, check=True)


def main():
    require_credentials()
    archive_previous()
    run("crawler.py")
    run("generate_v2.py", "200", "--fresh", "--workers", "8",
        "--output", "benchmark_v2.next.json")
    run("validate_v2.py", "--input", "benchmark_v2.next.json",
        "--target", "200", "--promote")
    prune_to_published_split()
    run("build_demo.py")
    print("[daily] paper-profile v2 build complete")


if __name__ == "__main__":
    main()
