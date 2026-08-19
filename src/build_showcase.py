# -*- coding: utf-8 -*-
"""Materialize the ten curated, fully certified homepage showcase cases."""

import json
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

SPECS = [
    {
        "id": "b8e031a930fd-0",
        "theme": "Public markets",
        "note": "A first-day stock surge tied to the robot manufacturer identified by the demonstration image.",
    },
    {
        "id": "bad0e26546ff-0",
        "theme": "AI & prediction markets",
        "note": "A time-sensitive launch probability that cannot be recovered from stable model knowledge.",
    },
    {
        "id": "fifa-kevin-lamour-20260818-0",
        "theme": "World Cup / FIFA governance",
        "note": "A deliberately tricky backward reference from a fresh dismissal to an earlier FIFA governance plan.",
    },
    {
        "id": "0302147dc8b8-showcase",
        "theme": "Sports medicine",
        "note": "The image identifies the player; current reporting is needed to recover the newly disclosed diagnosis.",
    },
    {
        "id": "2616d6aa9caa-0",
        "theme": "Electric mobility",
        "note": "A record fleet order whose quantity is not visible in the pictured truck.",
    },
    {
        "id": "d596e55ceca1-0",
        "theme": "Global health",
        "note": "A live outbreak statistic grounded by a public-health image and a dated UN report.",
    },
    {
        "id": "75fd63f110aa-0",
        "theme": "Climate & energy",
        "note": "A quantitative emissions consequence attached to the type of power plant shown.",
    },
    {
        "id": "ae2cbbf34462-0",
        "theme": "Consumer technology",
        "note": "The pictured laptop anchors a newly announced operating-system detail that requires current reporting.",
    },
    {
        "id": "a4c3f8d6f1e1-0",
        "theme": "Humanitarian response",
        "note": "A current funding requirement linked to the disaster represented by the temporary shelter.",
    },
    {
        "id": "166523985283-0",
        "theme": "Film & entertainment",
        "note": "The pictured actor anchors a fresh Star Wars pitch to a specific festival appearance.",
    },
]


def _read(path):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if isinstance(value, dict):
        return value.get("items", value.get("questions", [value]))
    return value


def _candidate_pool():
    pool = {}
    for name in ("benchmark_v2.next.json", "benchmark_v2.json",
                 "showcase_cases.json"):
        path = os.path.join(DATA_DIR, name)
        if os.path.exists(path):
            for item in _read(path):
                pool.setdefault(item["id"], item)
    for name in ("showcase_fifa_candidate.json", "showcase_medical_candidate.json"):
        path = os.path.join(DATA_DIR, name)
        if os.path.exists(path):
            for item in _read(path):
                pool[item["id"]] = item
    return pool


def _validate(item):
    image_path = os.path.join(DATA_DIR, item["image"])
    if not os.path.exists(image_path):
        raise ValueError(f"missing image for {item['id']}: {image_path}")
    cert = item.get("certification") or {}
    if cert.get("profile") != "3-model-x-4":
        raise ValueError(f"incomplete profile for {item['id']}")
    if len(item.get("closed_book_preds", [])) != 12:
        raise ValueError(f"expected 12 closed-book predictions for {item['id']}")
    if len(item.get("oracle_preds", [])) != 12:
        raise ValueError(f"expected 12 oracle predictions for {item['id']}")
    audit = item.get("image_match_audit") or {}
    if audit.get("image_article_match") != 4:
        raise ValueError(f"image/article audit failed for {item['id']}")
    if audit.get("question_image_grounding", 0) < 2:
        raise ValueError(f"question/image audit failed for {item['id']}")


def build():
    pool = _candidate_pool()
    output = []
    for rank, spec in enumerate(SPECS, 1):
        item = dict(pool[spec["id"]])
        _validate(item)
        item["showcase_rank"] = rank
        item["showcase_theme"] = spec["theme"]
        item["showcase_note"] = spec["note"]
        output.append(item)

    out_path = os.path.join(DATA_DIR, "showcase_cases.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(f"saved {out_path}: {len(output)} certified cases")


if __name__ == "__main__":
    build()
