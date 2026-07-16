# -*- coding: utf-8 -*-
"""One-off: reshuffle option positions of an existing benchmark.json to
remove the generator's position bias (correct answers piled on B)."""
import os
import sys
import json
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import _shuffle_options, DATA_DIR  # noqa: E402

path = os.path.join(DATA_DIR, "benchmark.json")
with open(path, encoding="utf-8") as f:
    bench = json.load(f)

for q in bench:
    _shuffle_options(q, seed=q["id"])

print("new answer dist:", Counter(q["answer"] for q in bench))
with open(path, "w", encoding="utf-8") as f:
    json.dump(bench, f, ensure_ascii=False, indent=1)
print("rewritten", path)
