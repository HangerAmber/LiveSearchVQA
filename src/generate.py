# -*- coding: utf-8 -*-
"""VQA generation + three-stage filtering.

Stage A  (generate): VLM reads (image, fresh article) and writes up to 2
         multiple-choice questions grounded in the image whose answers
         require the article's fresh information.
Stage B  (closed-book filter): VLM answers with image+question only.
         If it answers correctly, the item is discarded -- it is solvable
         from memorized/general knowledge, so it cannot measure search.
Stage C  (oracle filter): VLM answers with the gold evidence appended.
         If it fails even with the evidence, the question is unanswerable
         or broken and is discarded.

Every kept item ships with: gold answer, gold evidence snippet, source
URL and timestamps -- enabling the closed-book / with-search / oracle
three-way evaluation protocol.
"""
import os
import sys
import json
import time
import random
import base64
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_api import _call, _parse  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")

QTYPES = {"identification", "factual_detail", "numerical",
          "temporal", "causal", "cross_modal"}

GEN_PROMPT = """You are constructing a *live* VQA benchmark that tests whether a
vision-language agent can use WEB SEARCH to answer questions about very recent
events. You are given a news image and the news article it belongs to
(published within the last 48 hours, so no model can know it from training).

Article metadata:
- title: {title}
- source: {source} | category: {category}
- published: {pub_date}

Article text:
\"\"\"{text}\"\"\"

Write up to 3 multiple-choice questions that satisfy ALL rules:
1. The question must be grounded in the IMAGE: it must refer to something
   visible ("the device shown in the image", "the ceremony in the image",
   "the chart in the image"...), so that the image is genuinely needed to
   know what entity/event is being asked about.
2. The correct answer must come from the ARTICLE's fresh information
   (a name, number, date, cause, result...). It must NOT be answerable from
   the image alone, from common sense, or from pre-2026 world knowledge.
   A capable model WITHOUT access to this article should be unable to answer.
3. Do NOT ask about anything readable as text in the image itself.
4. The question must be self-contained: never say "according to the article".
5. Exactly 4 options, mutually exclusive, same category and granularity,
   plausible to someone who has not read the article. Randomize which
   position holds the correct answer.
6. Write question and options in ENGLISH (translate names properly;
   keep well-known Chinese proper nouns in pinyin or their official English).
7. "evidence" must be a short verbatim quote from the article text
   (original language) that proves the correct answer.
8. qtype is one of: identification, factual_detail, numerical, temporal,
   causal, cross_modal.

If the image is a pure logo/stock photo/irrelevant illustration, or the
article contains no question-worthy fresh fact, output [].

Output STRICT JSON only:
[{{"question": "...",
   "options": ["...", "...", "...", "..."],
   "answer": "A|B|C|D",
   "evidence": "...",
   "qtype": "...",
   "why_search_needed": "one short sentence"}}]"""

CLOSED_BOOK_PROMPT = """Answer this multiple-choice question about the image.
Question: {question}
A. {a}
B. {b}
C. {c}
D. {d}
Reply with exactly one letter: A, B, C, or D. If unsure, give your best guess."""

ORACLE_PROMPT = """Answer this multiple-choice question about the image, using the
retrieved web evidence below.

[Retrieved evidence] (news title: {title})
{evidence}

Question: {question}
A. {a}
B. {b}
C. {c}
D. {d}
Reply with exactly one letter: A, B, C, or D."""

_print_lock = threading.Lock()


def _b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _img_content(image_abs, prompt):
    return [
        {"type": "input_image",
         "image_url": f"data:image/jpeg;base64,{_b64_file(image_abs)}"},
        {"type": "input_text", "text": prompt},
    ]


def _letter(txt):
    if not txt:
        return None
    up = txt.strip().upper()
    # first standalone A-D not followed by another latin letter
    # (\b fails around CJK chars, e.g. "答案是C")
    m = re.search(r"(?<![A-Z])([ABCD])(?![A-Z])", up)
    return m.group(1) if m else None


def _ask_letter(img_abs, prompt, tries=2):
    for _ in range(tries):
        out = _call(_img_content(img_abs, prompt),
                    temperature=0.0, max_tokens=64)
        letter = _letter(out)
        if letter:
            return letter
    return None


def _shuffle_options(q, seed=None):
    """Reshuffle option order to kill position bias from the generator
    (LLMs tend to put the correct answer at B). Remaps answer and the
    stored filter predictions accordingly."""
    rng = random.Random(seed if seed is not None else q["question"])
    perm = [0, 1, 2, 3]
    rng.shuffle(perm)
    letters = "ABCD"
    old_opts = q["options"]
    q["options"] = [old_opts[i] for i in perm]
    remap = {letters[old]: letters[new] for new, old in enumerate(perm)}
    q["answer"] = remap[q["answer"]]
    for k in ("closed_book_pred", "oracle_pred"):
        if q.get(k) in remap:
            q[k] = remap[q[k]]
    return q


def _sanity(q):
    if not isinstance(q, dict):
        return False
    if not q.get("question") or not isinstance(q.get("options"), list):
        return False
    opts = [str(o).strip() for o in q["options"]]
    if len(opts) != 4 or len(set(opts)) != 4:
        return False
    if str(q.get("answer", "")).strip().upper() not in "ABCD":
        return False
    if not str(q.get("evidence", "")).strip():
        return False
    q["options"] = opts
    q["answer"] = str(q["answer"]).strip().upper()
    if q.get("qtype") not in QTYPES:
        q["qtype"] = "factual_detail"
    return True


def process_article(article, stats):
    img_abs = os.path.join(DATA_DIR, article["image"])
    if not os.path.exists(img_abs):
        return []
    prompt = GEN_PROMPT.format(
        title=article["title"], source=article["source"],
        category=article["category"], pub_date=article.get("pub_date") or "today",
        text=article["text"][:2600])
    raw = _call(_img_content(img_abs, prompt), temperature=0.6, max_tokens=1600)
    qs = _parse(raw)
    if not isinstance(qs, list):
        return []
    kept = []
    for q in qs[:3]:
        if not _sanity(q):
            continue
        stats["generated"] += 1
        a, b, c, d = q["options"]

        # Stage B: closed-book (no article) -- discard if solvable
        cb_letter = _ask_letter(img_abs, CLOSED_BOOK_PROMPT.format(
            question=q["question"], a=a, b=b, c=c, d=d))
        q["closed_book_pred"] = cb_letter
        if cb_letter is None or cb_letter == q["answer"]:
            stats["drop_closed_book"] += 1
            continue

        # Stage C: oracle evidence -- must be solvable
        oc_letter = _ask_letter(img_abs, ORACLE_PROMPT.format(
            title=article["title"], evidence=q["evidence"],
            question=q["question"], a=a, b=b, c=c, d=d))
        q["oracle_pred"] = oc_letter
        if oc_letter != q["answer"]:
            stats["drop_oracle"] += 1
            continue

        stats["accepted"] += 1
        _shuffle_options(q)
        kept.append({
            "id": f"{article['id']}-{len(kept)}",
            "article_id": article["id"],
            "source": article["source"],
            "category": article["category"],
            "article_url": article["url"],
            "article_title": article["title"],
            "pub_date": article.get("pub_date"),
            "crawl_time": article["crawl_time"],
            "image": article["image"],
            "question": q["question"],
            "options": q["options"],
            "answer": q["answer"],
            "evidence": q["evidence"],
            "qtype": q["qtype"],
            "why_search_needed": q.get("why_search_needed", ""),
            "closed_book_pred": q["closed_book_pred"],
            "oracle_pred": q["oracle_pred"],
        })
    return kept


# diversity knobs
MAX_Q_PER_CATEGORY = 40   # cap questions per news category per day
MAX_Q_PER_ARTICLE = 1     # unique image per question; extras used as top-up


def _interleave_by_category(articles):
    """Round-robin across categories so no single domain dominates the
    front of the processing queue."""
    rng = random.Random(42)
    buckets = {}
    for a in articles:
        buckets.setdefault(a["category"], []).append(a)
    for b in buckets.values():
        rng.shuffle(b)
    order = sorted(buckets, key=lambda c: -len(buckets[c]))
    out, i = [], 0
    while any(buckets.values()):
        for c in order:
            if i < len(buckets[c]):
                out.append(buckets[c][i])
        i += 1
        if i > max(len(b) for b in buckets.values()):
            break
    return out


def main(target=200, workers=5):
    with open(os.path.join(DATA_DIR, "articles.json"), encoding="utf-8") as f:
        articles = json.load(f)
    articles = _interleave_by_category(articles)

    # top-up mode: keep previously accepted items, skip their articles
    bench_path = os.path.join(DATA_DIR, "benchmark.json")
    bench = []
    if os.path.exists(bench_path):
        with open(bench_path, encoding="utf-8") as f:
            bench = json.load(f)
        used = {b["article_id"] for b in bench}
        articles = [a for a in articles if a["id"] not in used]
        print(f"[resume] {len(bench)} existing items, "
              f"{len(articles)} unused articles")
    if len(bench) >= target:
        print("target already reached")
        return

    stats = {"generated": 0, "drop_closed_book": 0,
             "drop_oracle": 0, "accepted": 0, "articles_used": 0,
             "drop_category_quota": 0}
    stop = threading.Event()
    cat_counts = {}
    for b in bench:
        cat_counts[b["category"]] = cat_counts.get(b["category"], 0) + 1
    cat_lock = threading.Lock()

    quota_skipped = []

    def worker(article, enforce_quota=True):
        if stop.is_set():
            return []
        if enforce_quota:
            with cat_lock:
                if cat_counts.get(article["category"], 0) >= MAX_Q_PER_CATEGORY:
                    stats["drop_category_quota"] += 1
                    quota_skipped.append(article)
                    return []
        return process_article(article, stats)

    t0 = time.time()
    extras = []  # 2nd question per article, used only if supply runs short

    def run_pass(pool, enforce_quota=True):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(worker, a, enforce_quota): a for a in pool}
            for f in as_completed(futs):
                try:
                    items = f.result()
                except Exception as e:
                    with _print_lock:
                        print("[worker err]", str(e)[:150])
                    continue
                if items:
                    stats["articles_used"] += 1
                    kept = items[:MAX_Q_PER_ARTICLE]
                    extras.extend(items[MAX_Q_PER_ARTICLE:])
                    bench.extend(kept)
                    with cat_lock:
                        cat = futs[f]["category"]
                        cat_counts[cat] = cat_counts.get(cat, 0) + len(kept)
                    with _print_lock:
                        print(f"[{len(bench):>3}/{target}] +{len(kept)} "
                              f"({futs[f]['source']}/{futs[f]['category']}) "
                              f"{futs[f]['title'][:40]}")
                if len(bench) >= target and not stop.is_set():
                    stop.set()

    run_pass(articles, enforce_quota=True)

    if len(bench) < target and extras:
        # top-up with second questions per article, still under quota
        for q in extras:
            if len(bench) >= target:
                break
            if cat_counts.get(q["category"], 0) >= MAX_Q_PER_CATEGORY:
                continue
            bench.append(q)
            cat_counts[q["category"]] = cat_counts.get(q["category"], 0) + 1
        print(f"[top-up] {len(bench)} after adding spare questions")

    if len(bench) < target and quota_skipped:
        # supply ran short: relax the category quota rather than under-fill
        print(f"[relax] quota relaxed, reprocessing "
              f"{len(quota_skipped)} skipped articles")
        run_pass(list(quota_skipped), enforce_quota=False)

    bench = bench[:target]
    out = bench_path
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(bench, fp, ensure_ascii=False, indent=1)
    stats["elapsed_sec"] = round(time.time() - t0)
    stats["final_size"] = len(bench)
    stats["build_date"] = time.strftime("%Y-%m-%d")
    with open(os.path.join(DATA_DIR, "stats.json"), "w", encoding="utf-8") as fp:
        json.dump(stats, fp, indent=1)
    print(json.dumps(stats, indent=1))
    print("saved ->", out)


if __name__ == "__main__":
    tgt = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    main(target=tgt)
