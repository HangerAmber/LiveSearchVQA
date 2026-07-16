# -*- coding: utf-8 -*-
"""Daily rebuild entry point (used by the GitHub Actions cron job).

Archives yesterday's split to data/archive/<date>.json, clears the working
files, then runs the full pipeline: crawl -> generate -> build_html.
"""
import os
import json
import shutil
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")


def archive_previous():
    bench_path = os.path.join(DATA_DIR, "benchmark.json")
    stats_path = os.path.join(DATA_DIR, "stats.json")
    if not os.path.exists(bench_path):
        return
    date = ""
    if os.path.exists(stats_path):
        with open(stats_path, encoding="utf-8") as f:
            date = json.load(f).get("build_date", "")
    if not date:
        return
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    shutil.copy(bench_path, os.path.join(ARCHIVE_DIR, f"{date}.json"))
    print(f"[archive] previous split -> archive/{date}.json")
    # clear working files so the new day starts from scratch
    for p in (bench_path, os.path.join(DATA_DIR, "articles.json")):
        if os.path.exists(p):
            os.remove(p)


def run(script, *args):
    cmd = [sys.executable, "-u", "-X", "utf8",
           os.path.join(_ROOT, "src", script), *args]
    print("[run]", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    archive_previous()
    run("crawler.py")
    run("generate.py", "200")
    run("build_html.py")
    print("[daily] done")
