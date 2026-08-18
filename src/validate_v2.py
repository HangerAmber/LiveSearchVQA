# -*- coding: utf-8 -*-
"""Strict offline validation and atomic promotion for a v2 staging split."""
import argparse
import json
import math
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone

from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")
REQUIRED = (
    "id", "image", "question", "answer", "answer_type", "evidence",
    "category", "source", "source_language", "article_url", "article_title",
    "pub_date", "build_date", "image_match_audit", "certification",
    "visual_anchor_type", "freshness_relation", "referent_grounding_audit",
)
VISUAL_RE = re.compile(
    r"\b(pictured|shown|in (?:this|the) image|visible in|depicted|photographed)\b",
    re.I,
)
EVENT_RE = re.compile(
    r"\b(event|match|game|race|launch|mission|meeting|summit|ceremony|"
    r"announcement|release|protest|trial|vote|election|deal|transaction|"
    r"incident|conference|tournament|performance|project|reported|reporting|"
    r"recorded|won|lost|scored|raised|cost|revenue|price|amount|how many|"
    r"how much|what date|what time|where did|percentage|percent|debut|"
    r"grand prix|season|series|championship|lawsuit|bill|sale|discount|"
    r"startup|program|probe|contract|episode|film|movie|album|tour|concert|"
    r"flood|storm|earthquake|wildfire|closure|layoff|funding|study)\b",
    re.I,
)
BAD_RE = re.compile(
    r"\b(what (?:is|are|was|were).{0,25} doing|who (?:is|are|was|were) "
    r"(?:shown|pictured)|what does (?:this|the) image show|identify the "
    r"(?:person|object|logo|place)|what (?:is|are) visible|article written by "
    r"(?:the )?pictured|pictured (?:author|journalist|reporter))\b",
    re.I,
)
BAD_AUDIT_NOTE_RE = re.compile(
    r"\b(not the (?:same|one described)|does not (?:match|depict)|"
    r"unrelated (?:to|image)|image (?:is|appears) (?:generic|irrelevant)|"
    r"only loosely related|decorative image|author headshot)\b",
    re.I,
)


def _clean(value):
    value = str(value).replace("\u00a0", " ")
    value = value.replace("“", '"').replace("”", '"')
    value = value.replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", value).strip().strip('"').lower()


def _dhash(path, size=8):
    with Image.open(path) as image:
        image = image.convert("L").resize((size + 1, size), Image.LANCZOS)
        pixels = list(image.getdata())
    bits = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            bits = (bits << 1) | (pixels[row + x + 1] > pixels[row + x])
    return bits


def validate(input_name, target=200, english_ratio=0.85, quant_ratio=0.65):
    path = os.path.join(DATA_DIR, input_name)
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    problems = []
    warnings = []
    if len(items) != target:
        problems.append(f"size {len(items)} != target {target}")

    article_map = {}
    article_path = os.path.join(DATA_DIR, "articles.json")
    if os.path.exists(article_path):
        with open(article_path, encoding="utf-8") as f:
            article_map = {a["id"]: a for a in json.load(f)}

    seen_ids, seen_images = set(), set()
    hashes = []
    now = datetime.now(timezone.utc)
    for index, item in enumerate(items):
        tag = f"item {index} ({item.get('id', '?')})"
        for field in REQUIRED:
            if not item.get(field):
                problems.append(f"{tag}: missing {field}")
        if item.get("id") in seen_ids:
            problems.append(f"{tag}: duplicate id")
        seen_ids.add(item.get("id"))
        if item.get("image") in seen_images:
            problems.append(f"{tag}: duplicate image path")
        seen_images.add(item.get("image"))

        image_path = os.path.join(DATA_DIR, item.get("image", ""))
        if not os.path.exists(image_path):
            problems.append(f"{tag}: missing image file")
        else:
            try:
                image_hash = _dhash(image_path)
                for other_tag, other_hash in hashes:
                    if (image_hash ^ other_hash).bit_count() <= 6:
                        problems.append(f"{tag}: perceptual duplicate of {other_tag}")
                        break
                hashes.append((tag, image_hash))
            except Exception as exc:
                problems.append(f"{tag}: unreadable image ({exc})")

        question = str(item.get("question", ""))
        if not VISUAL_RE.search(question):
            problems.append(f"{tag}: no visual referent")
        if not EVENT_RE.search(question):
            problems.append(f"{tag}: no explicit event/search cue")
        if BAD_RE.search(question):
            problems.append(f"{tag}: image-only question pattern")
        if not question.endswith("?") or not 10 <= len(question.split()) <= 48:
            problems.append(f"{tag}: malformed question length/form")
        if len(str(item.get("answer", "")).split()) > 8:
            problems.append(f"{tag}: answer too long")
        if item.get("freshness_relation") not in {
                "current_event", "new_announcement", "new_result"}:
            problems.append(f"{tag}: historical/non-fresh fact relation")
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b",
                                            str(item.get("answer", "")))]
        if item.get("answer_type") == "temporal" and years and \
                max(years) < now.year:
            problems.append(f"{tag}: historical temporal answer")
        question_years = [
            int(y) for y in re.findall(r"\b(20\d{2})\b", question)
        ]
        if item.get("answer_type") == "temporal" and question_years and \
                max(question_years) < now.year:
            problems.append(f"{tag}: historical temporal question")
        if any(y < now.year for y in question_years) and re.search(
                r"\bas of (?:the )?.{0,30}\b20\d{2}\b", question, re.I):
            problems.append(f"{tag}: historical question context")

        try:
            published = datetime.fromisoformat(item["pub_date"])
            age = now - published.astimezone(timezone.utc)
            if not (-timedelta(hours=6) <= age <= timedelta(hours=48)):
                problems.append(f"{tag}: article age {age.total_seconds()/3600:.1f}h")
        except Exception:
            problems.append(f"{tag}: invalid pub_date")

        article = article_map.get(item.get("article_id"))
        if article and _clean(item.get("evidence")) not in _clean(article.get("text")):
            problems.append(f"{tag}: evidence is not verbatim")

        answer_nums = re.findall(r"\d+(?:\.\d+)?", _clean(item.get("answer")))
        evidence_nums = re.findall(r"\d+(?:\.\d+)?", _clean(item.get("evidence")))
        if answer_nums and not set(answer_nums).issubset(set(evidence_nums)):
            problems.append(f"{tag}: answer number absent from evidence")

        audit = item.get("image_match_audit") or {}
        thresholds = {"image_article_match": 4, "question_image_grounding": 2,
                      "event_specificity": 3,
                      "search_necessity": 3, "fresh_fact_centrality": 3,
                      "question_clarity": 3}
        for field, minimum in thresholds.items():
            if int(audit.get(field, 0)) < minimum:
                problems.append(f"{tag}: match audit {field}<{minimum}")
        if audit.get("explicit_event_question") is not True or \
                audit.get("image_only_answerable") is not False or \
                audit.get("visual_claim_supported") is not True:
            problems.append(f"{tag}: match audit flags failed")
        if BAD_AUDIT_NOTE_RE.search(str(audit.get("audit_note", ""))):
            problems.append(f"{tag}: audit note reports image mismatch")
        grounding = item.get("referent_grounding_audit") or {}
        if grounding.get("image_resolves_omitted_subject") is not True or \
                grounding.get("omitted_subject_is_answer_target") is not True or \
                not str(grounding.get("omitted_subject", "")).strip():
            problems.append(f"{tag}: image does not resolve an omitted subject")
        if grounding.get("profile") != "qwen-plus-all-2" or \
                len(grounding.get("samples", [])) != 2:
            problems.append(f"{tag}: referent grounding audit is incomplete")

        cert = item.get("certification") or {}
        if len(cert.get("panel", [])) != 3:
            problems.append(f"{tag}: certification panel size != 3")
        expected_samples = 4
        match = re.fullmatch(r"3-model-x-(\d+)", cert.get("profile", ""))
        if match:
            expected_samples = int(match.group(1))
        else:
            problems.append(f"{tag}: invalid certification profile")
        for condition in ("closed_book", "oracle"):
            detail = cert.get(condition) or {}
            if set(detail) != set(cert.get("panel", [])):
                problems.append(f"{tag}: {condition} panel audit incomplete")
                continue
            for member, predictions in detail.items():
                if len(predictions) != expected_samples:
                    problems.append(
                        f"{tag}: {condition}/{member} has {len(predictions)} "
                        f"samples, expected {expected_samples}"
                    )

    english_count = sum(item.get("source_language") == "en" for item in items)
    quant_count = sum(item.get("answer_type") in {"numeric", "temporal"}
                      for item in items)
    min_english = math.ceil(target * english_ratio)
    min_quant = math.ceil(target * quant_ratio)
    if english_count < min_english:
        problems.append(f"English items {english_count} < {min_english}")
    if quant_count < min_quant:
        problems.append(f"quantitative items {quant_count} < {min_quant}")

    report = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "input": input_name,
        "items": len(items),
        "english_count": english_count,
        "english_ratio": round(english_count / max(1, len(items)), 4),
        "quantitative_count": quant_count,
        "quantitative_ratio": round(quant_count / max(1, len(items)), 4),
        "sources": dict(Counter(item.get("source") for item in items)),
        "categories": dict(Counter(item.get("category") for item in items)),
        "answer_types": dict(Counter(item.get("answer_type") for item in items)),
        "problems": problems,
        "warnings": warnings,
        "status": "PASS" if not problems else "FAIL",
    }
    report_path = os.path.join(DATA_DIR, "quality_report_v2.json")
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if problems:
        raise SystemExit(1)
    return path, report_path


def promote(input_path):
    destination = os.path.join(DATA_DIR, "benchmark_v2.json")
    backup = os.path.join(DATA_DIR, "benchmark_v2.previous.json")
    if os.path.exists(destination):
        shutil.copy2(destination, backup)
    shutil.copy2(input_path, destination)
    next_stats = os.path.join(DATA_DIR, "stats_v2.next.json")
    if os.path.exists(next_stats):
        shutil.copy2(next_stats, os.path.join(DATA_DIR, "stats_v2.json"))
    print("promoted ->", destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="benchmark_v2.next.json")
    parser.add_argument("--target", type=int, default=200)
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()
    path, _ = validate(args.input, target=args.target)
    if args.promote:
        promote(path)


if __name__ == "__main__":
    main()
