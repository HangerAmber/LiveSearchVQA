# -*- coding: utf-8 -*-
"""One-off: backfill the perceptual-hash registry from existing images and
report near-duplicate images inside the current benchmark."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from crawler import (_dhash, _hash_registry, _save_hash_registry,
                     IMG_DIR, DATA_DIR, DEDUP_HAMMING_MAX)

for name in os.listdir(IMG_DIR):
    item_id = os.path.splitext(name)[0]
    if item_id in _hash_registry:
        continue
    with Image.open(os.path.join(IMG_DIR, name)) as im:
        _hash_registry[item_id] = _dhash(im.convert("RGB"))
_save_hash_registry()
print(f"registry now holds {len(_hash_registry)} hashes")

with open(os.path.join(DATA_DIR, "benchmark.json"), encoding="utf-8") as f:
    bench = json.load(f)
ids = sorted({os.path.splitext(os.path.basename(b["image"]))[0] for b in bench})
dups = []
for i, a in enumerate(ids):
    for b in ids[i + 1:]:
        if a in _hash_registry and b in _hash_registry and \
                bin(_hash_registry[a] ^ _hash_registry[b]).count("1") <= DEDUP_HAMMING_MAX:
            dups.append((a, b))
print(f"benchmark uses {len(ids)} unique image files; "
      f"near-duplicate pairs: {len(dups)}")
for a, b in dups[:10]:
    print("  dup:", a, b)
