# LiveSearchVQA

**A daily-refreshed VQA benchmark for measuring the *web-search* capability of
vision-language agents.**

Every question is built from a news article published within the last 48
hours, so no model can answer from training data — answering correctly
*requires* searching the web. The pipeline is fully automated and can be run
daily.

## Why

Web search is now critical for VLM agents, but no benchmark measures it in a
contamination-free way. Static benchmarks leak into training data within
months. LiveSearchVQA is contamination-free *by construction* and additionally
diagnoses **where** a search agent fails:

| Failure mode | How we measure it |
|---|---|
| Retrieval failure (crawl not accurate/complete) | agent fails, but succeeds when given gold evidence |
| Distraction failure (drowned in retrieved noise) | agent retrieved the evidence but still answers wrong |
| Utilization failure (can't use what it found) | agent fails even in the oracle-evidence setting |

## Three-way evaluation protocol

For each of the 200 daily questions (image + 4-option MCQ + gold evidence +
source URL):

1. **Closed-book** — image + question only. By construction accuracy is ~0
   (items solvable closed-book are filtered out).
2. **With-search** — the agent may search the web. This is the headline score.
3. **Oracle-evidence** — the gold evidence snippet is provided. Upper bound.

The gap `oracle − with-search` decomposes into retrieval vs. distraction vs.
utilization error using the agent's retrieval trace.

## Pipeline

```
RSS feeds (20+ channels, CN + EN)          src/crawler.py
  └─ fresh articles (<48 h) + images        data/articles.json, data/images/
      │   · perceptual-hash (dHash) image dedup, persistent across days
      └─ VLM question generation            src/generate.py  (Stage A)
          └─ closed-book filter             (Stage B: drop if solvable w/o search)
              └─ oracle filter              (Stage C: drop if unsolvable w/ evidence)
                  │   · 1 question per image · per-category quota (40/day)
                  │   · category round-robin scheduling
                  └─ benchmark              data/benchmark.json (200 items)
                      └─ visualization      src/build_html.py → index.html
```

VLM: Doubao Seed 2.0 Pro via Volcano Engine ARK (`src/ark_api.py`).

## Daily automation

`.github/workflows/daily.yml` runs `src/daily.py` every day at 08:30 Beijing
time: it archives the previous split to `data/archive/<date>.json`, rebuilds
the benchmark from scratch from that day's news, prunes unreferenced images,
regenerates `index.html`, and pushes -- GitHub Pages then redeploys the site
automatically. Requires the `ARK_API_KEY` repository secret.

Diversity guarantees:
- **No repeated images, ever**: a persistent dHash registry
  (`data/image_hashes.json`) rejects any image within Hamming distance 6 of
  a previously used one, including re-published press photos.
- **Domain balance**: articles are scheduled round-robin across categories,
  each category is capped at 40 questions/day (relaxed only if supply runs
  short), and each image contributes at most one question.

## Run

```powershell
# put your key in .env:  ARK_API_KEY=...
python src/crawler.py        # crawl fresh articles (incremental)
python src/generate.py 200   # generate + filter until 200 items (resumable)
python src/build_html.py     # build index.html
```

Open `index.html` in a browser: stats, per-type/per-source charts, search,
filtering, click-to-answer cards with gold evidence and source links.

## Data format (`data/benchmark.json`)

```json
{
  "id": "a1b2c3d4e5f6-0",
  "image": "images/a1b2c3d4e5f6.jpg",
  "question": "...",
  "options": ["...", "...", "...", "..."],
  "answer": "B",
  "evidence": "verbatim quote from the source article",
  "qtype": "numerical",
  "source": "ithome", "category": "tech",
  "article_url": "...", "article_title": "...",
  "pub_date": "2026-07-14T18:27:59+08:00",
  "crawl_time": "2026-07-14T19:02:11+08:00",
  "closed_book_pred": "C",
  "oracle_pred": "B"
}
```

`requirements.txt`: requests, Pillow.
