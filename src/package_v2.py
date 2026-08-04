# -*- coding: utf-8 -*-
"""Validate benchmark_v2.json and package it (json + images + README) as zip."""
import os
import json
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")

REQUIRED = ("id", "image", "question", "answer", "answer_type", "evidence",
            "category", "source", "article_url", "article_title", "pub_date",
            "build_date")
ANSWER_TYPES = {"entity", "numeric", "temporal", "location", "outcome"}


def main():
    with open(os.path.join(DATA_DIR, "benchmark_v2.json"), encoding="utf-8") as f:
        bench = json.load(f)

    # ---- validation ----
    problems = []
    now = datetime.now(timezone.utc)
    seen_img, seen_id = set(), set()
    for i, q in enumerate(bench):
        for k in REQUIRED:
            if not str(q.get(k, "")).strip():
                problems.append(f"item {i}: missing field {k}")
        if q["id"] in seen_id:
            problems.append(f"item {i}: duplicate id {q['id']}")
        seen_id.add(q["id"])
        if q["image"] in seen_img:
            problems.append(f"item {i}: duplicate image {q['image']}")
        seen_img.add(q["image"])
        if not os.path.exists(os.path.join(DATA_DIR, q["image"])):
            problems.append(f"item {i}: image file missing {q['image']}")
        if q["answer_type"] not in ANSWER_TYPES:
            problems.append(f"item {i}: bad answer_type {q['answer_type']}")
        if len(str(q["answer"]).split()) > 6:
            problems.append(f"item {i}: answer too long: {q['answer']}")
        try:
            dt = datetime.fromisoformat(q["pub_date"])
            age_h = (now - dt.astimezone(timezone.utc)).total_seconds() / 3600
            if age_h > 72:
                problems.append(f"item {i}: article older than 72h ({age_h:.0f}h)")
        except Exception:
            problems.append(f"item {i}: unparseable pub_date {q.get('pub_date')}")

    print(f"items: {len(bench)}")
    print("answer_type:", dict(Counter(q["answer_type"] for q in bench)))
    print("category:", dict(Counter(q["category"] for q in bench)))
    print("source:", dict(Counter(q["source"] for q in bench)))
    if problems:
        print(f"\n{len(problems)} PROBLEMS:")
        for p in problems[:30]:
            print(" -", p)
        raise SystemExit(1)
    print("validation: OK")

    # ---- README ----
    build_date = bench[0]["build_date"]
    readme = f"""LiveSearchVQA v2 benchmark ({build_date} build)
================================================

{len(bench)} open-ended visual question answering items built from news
articles published within 48 hours of the build, following the paper's
dual-filter admission protocol:

  Stage 2  VLM question generation  - image-grounded questions; answers are
           event-specific facts; short open-ended answers (<= 5 tokens);
           answer_type in {{entity, numeric, temporal, location, outcome}};
           verbatim evidence span copied from the article.
  Stage 3  Closed-book filter (P1, search necessity) - candidate DISCARDED
           if the filter model answers correctly without search (UNKNOWN
           allowed, any-correct-of-n discards).
  Stage 4  Oracle filter (P2, well-posedness) - candidate KEPT only if the
           model answers correctly with the gold evidence as sole context
           in all n samples.
  Stage 5  Image perceptual-hash dedup, question-level dedup, per-category
           quota (relaxed on shortage).

Files
-----
  benchmark_v2.json   the {len(bench)} items
  images/             one JPEG per item (referenced by the "image" field)

Item schema
-----------
  id                  unique item id (article hash + index)
  image               relative path to the image (images/<id>.jpg)
  question            English question; refers to the image ("shown", "pictured")
  answer              gold short answer (English, <= 5 tokens)
  answer_type         entity | numeric | temporal | location | outcome
  evidence            verbatim evidence span (original language)
  category            canonical category (8-way scheme of the paper)
  source / source_category   news outlet and its native category
  article_url / article_title / pub_date   provenance
  build_date          benchmark build date
  closed_book_preds   filter-model closed-book predictions (audit trail)
  oracle_preds        filter-model oracle predictions (audit trail)

Evaluation conditions (paper Section 4)
---------------------------------------
  Closed-book: image + question only.
  With-search: agent may search the web; log retrievals.
  Oracle:      "evidence" field as the sole context.

Note: single-model filter panel and Chinese-tech-heavy source pool are
build-time approximations of the paper's 3-model panel / 42-outlet design;
see PROPOSAL.md in the repository for the roadmap.
"""

    # ---- zip ----
    zip_path = os.path.join(_ROOT, f"LiveSearchVQA_v2_{build_date}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", readme)
        zf.write(os.path.join(DATA_DIR, "benchmark_v2.json"), "benchmark_v2.json")
        for q in bench:
            zf.write(os.path.join(DATA_DIR, q["image"]), q["image"])
    size_mb = os.path.getsize(zip_path) / 1e6
    print(f"zip -> {zip_path} ({size_mb:.1f} MB, {len(bench)} images)")


if __name__ == "__main__":
    main()
