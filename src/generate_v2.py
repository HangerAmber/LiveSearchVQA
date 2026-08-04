# -*- coding: utf-8 -*-
"""Paper-aligned benchmark construction (v2, open-ended answers).

Implements the pipeline described in the LiveSearchVQA paper draft:

Stage 2  VLM question generation -- image-grounded questions whose answers
         are event-specific facts; short open-ended answers (<=5 tokens);
         answer_type in {entity, numeric, temporal, location, outcome};
         verbatim evidence span; <=2 items per article.
Stage 3  Closed-book filter (P1, search necessity) -- the filter model
         answers with image only, n samples, "UNKNOWN" allowed; a candidate
         is DISCARDED if any sample is correct.  (Single-model panel
         approximation of the paper's 3-model panel.)
Stage 4  Oracle filter (P2, well-posedness) -- gold evidence as the sole
         context, n samples; a candidate is KEPT only if all samples are
         correct.
Stage 5  Question-level dedup (token overlap), canonical category mapping,
         per-category quota with shortage relaxation.

Output: data/benchmark_v2.json, data/stats_v2.json
"""
import os
import re
import sys
import json
import time
import base64
import random
import string
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_api import _call, _parse  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")

ANSWER_TYPES = {"entity", "numeric", "temporal", "location", "outcome"}

# canonical 8-category scheme of the paper
CATEGORY_MAP = {
    "politics": "politics", "world": "politics", "important": "politics",
    "business": "business", "finance": "business",
    "sports": "sports", "football": "sports",
    "tech": "scitech", "technology": "scitech", "ai": "scitech",
    "science": "scitech", "space": "scitech",
    "health": "health",
    "entertainment": "culture", "movies": "culture",
    "environment": "environment",
    "general": "regional", "society": "regional", "regional": "regional",
    "education": "regional", "china": "regional", "military": "politics",
}

FRESH_HOURS = 48           # P3: only articles from the last 48 h
CB_SAMPLES = 2             # closed-book samples (discard if ANY correct)
OR_SAMPLES = 2             # oracle samples (keep only if ALL correct)
MAX_Q_PER_ARTICLE = 1      # unique image per question (spares used as top-up)
QUESTION_SIM_THRESHOLD = 0.7

GEN_PROMPT = """You are constructing visual question answering items from a news
article published within the last 48 hours (benchmark for web-search agents).

INPUT article:
- headline: {title}
- source: {source} | category: {category} | published: {pub_date}
- body:
\"\"\"{text}\"\"\"

Write up to 2 question-answer pairs such that:
 1. The question is about the IMAGE: the image must be required to resolve
    the referent (use "this", "shown", "pictured"; NEVER name the entity
    that the image depicts in the question).
 2. The answer is an event-specific fact reported in THIS article (score /
    count / price / date / location / outcome / newly announced entity).
    Do NOT ask about stable background facts or anything answerable from
    the image alone or from pre-2026 world knowledge.
 3. The answer is a single short phrase (<= 5 tokens) in ENGLISH,
    objectively verifiable against the article text.
 4. Copy the minimal verbatim evidence sentence(s) (original language)
    that entail the answer.
 5. Assign answer_type in {{entity, numeric, temporal, location, outcome}}.
 6. Do not ask about text readable in the image itself.

OUTPUT strict JSON:
[{{"question": "...", "answer": "...", "evidence": "...",
   "answer_type": "..."}}]
Return [] if no valid item exists (e.g. logo/stock image, no fresh fact)."""

CB_PROMPT = """Answer the question about the image. Respond with the short answer
only. If you are not confident you know the answer, respond exactly UNKNOWN.
Do not guess.
Question: {question}"""

OR_PROMPT = """Use ONLY the evidence below to answer the question about the image.
Respond with the short answer only (in English).
EVIDENCE ({title}): {evidence}
Question: {question}"""

JUDGE_PROMPT = """Question: {q}
Gold answer: {gold}
Model answer: {pred}
Decide if the model answer is semantically equivalent to the gold answer for
this question (same entity / number / date / outcome). Output exactly CORRECT
or INCORRECT."""

_print_lock = threading.Lock()


# ---------------- answer matching ----------------
_ARTICLES_RE = re.compile(r"\b(the|a|an)\b")
_PUNCT_TABLE = str.maketrans("", "", string.punctuation + "“”‘’、，。")


def _norm(s):
    s = str(s).lower().strip()
    s = s.translate(_PUNCT_TABLE)
    s = _ARTICLES_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _nums(s):
    return re.findall(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))


def _fast_match(gold, pred):
    """Cheap normalization-based equivalence; returns True/False/None
    (None = unclear, needs the LLM judge)."""
    g, p = _norm(gold), _norm(pred)
    if not p or p == "unknown":
        return False
    if g == p:
        return True
    gn, pn = _nums(gold), _nums(pred)
    if gn and pn and set(gn) == set(pn):
        return True
    if gn and pn and set(gn) != set(pn):
        return False
    if g in p or p in g:
        return True
    return None


def _judge(question, gold, pred):
    out = _call([{"type": "input_text",
                  "text": JUDGE_PROMPT.format(q=question, gold=gold, pred=pred)}],
                temperature=0.0, max_tokens=8)
    return "CORRECT" in out.upper() and "INCORRECT" not in out.upper()


def _is_correct(question, gold, pred):
    fast = _fast_match(gold, pred)
    if fast is not None:
        return fast
    return _judge(question, gold, pred)


# ---------------- VLM helpers ----------------
def _b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _img_content(image_abs, prompt):
    return [
        {"type": "input_image",
         "image_url": f"data:image/jpeg;base64,{_b64_file(image_abs)}"},
        {"type": "input_text", "text": prompt},
    ]


def _sanity(q):
    if not isinstance(q, dict):
        return False
    for k in ("question", "answer", "evidence"):
        if not str(q.get(k, "")).strip():
            return False
    if len(str(q["answer"]).split()) > 6 or len(str(q["answer"])) > 60:
        return False
    if q.get("answer_type") not in ANSWER_TYPES:
        return False
    return True


def _q_tokens(question):
    return set(_norm(question).split())


# ---------------- pipeline core ----------------
def process_article(article, stats):
    img_abs = os.path.join(DATA_DIR, article["image"])
    if not os.path.exists(img_abs):
        return []
    raw = _call(_img_content(img_abs, GEN_PROMPT.format(
        title=article["title"], source=article["source"],
        category=article["category"],
        pub_date=article.get("pub_date") or "today",
        text=article["text"][:2600])), temperature=0.7, max_tokens=1200)
    cands = _parse(raw)
    if not isinstance(cands, list):
        return []
    kept = []
    for q in cands[:2]:
        if not _sanity(q):
            continue
        stats["generated"] += 1
        question, gold = q["question"].strip(), str(q["answer"]).strip()

        # Stage 3: closed-book filter (P1) -- discard if ANY sample correct
        cb_preds, leaked = [], False
        for _ in range(CB_SAMPLES):
            pred = _call(_img_content(img_abs, CB_PROMPT.format(
                question=question)), temperature=0.7, max_tokens=48).strip()
            cb_preds.append(pred[:80])
            if _is_correct(question, gold, pred):
                leaked = True
                break
        if leaked:
            stats["drop_closed_book"] += 1
            continue

        # Stage 4: oracle filter (P2) -- keep only if ALL samples correct
        or_preds, well_posed = [], True
        for i in range(OR_SAMPLES):
            pred = _call(_img_content(img_abs, OR_PROMPT.format(
                title=article["title"], evidence=q["evidence"],
                question=question)),
                temperature=0.0 if i == 0 else 0.4, max_tokens=48).strip()
            or_preds.append(pred[:80])
            if not _is_correct(question, gold, pred):
                well_posed = False
                break
        if not well_posed:
            stats["drop_oracle"] += 1
            continue

        stats["accepted"] += 1
        kept.append({
            "id": f"{article['id']}-{len(kept)}",
            "article_id": article["id"],
            "image": article["image"],
            "question": question,
            "answer": gold,
            "answer_type": q["answer_type"],
            "evidence": q["evidence"].strip(),
            "category": article["canonical_category"],
            "source_category": article["category"],
            "source": article["source"],
            "article_url": article["url"],
            "article_title": article["title"],
            "pub_date": article.get("pub_date"),
            "crawl_time": article["crawl_time"],
            "build_date": time.strftime("%Y-%m-%d"),
            "closed_book_preds": cb_preds,
            "oracle_preds": or_preds,
        })
    return kept


def _interleave_by_category(articles):
    rng = random.Random(42)
    buckets = {}
    for a in articles:
        buckets.setdefault(a["canonical_category"], []).append(a)
    for b in buckets.values():
        rng.shuffle(b)
    order = sorted(buckets, key=lambda c: -len(buckets[c]))
    out, i = [], 0
    while i <= max(len(b) for b in buckets.values()):
        for c in order:
            if i < len(buckets[c]):
                out.append(buckets[c][i])
        i += 1
    return out


def main(target=200, workers=5):
    with open(os.path.join(DATA_DIR, "articles.json"), encoding="utf-8") as f:
        articles = json.load(f)

    # P3: enforce freshness at build time, not just crawl time
    now = datetime.now(timezone.utc)
    fresh = []
    for a in articles:
        if not a.get("pub_date"):
            continue
        try:
            dt = datetime.fromisoformat(a["pub_date"])
        except ValueError:
            continue
        if now - dt.astimezone(timezone.utc) <= timedelta(hours=FRESH_HOURS):
            a["canonical_category"] = CATEGORY_MAP.get(a["category"], "regional")
            fresh.append(a)
    print(f"[fresh] {len(fresh)}/{len(articles)} articles within "
          f"{FRESH_HOURS}h window")
    articles = _interleave_by_category(fresh)

    quota = max(25, target // 8 + 5)   # per canonical category
    bench, extras, quota_skipped = [], [], []
    out_path = os.path.join(DATA_DIR, "benchmark_v2.json")
    if os.path.exists(out_path):   # resume: keep accepted, skip used articles
        with open(out_path, encoding="utf-8") as f:
            bench = json.load(f)
        used = {b["article_id"] for b in bench}
        articles = [a for a in articles if a["id"] not in used]
        print(f"[resume] {len(bench)} existing items, "
              f"{len(articles)} unused fresh articles")
    stats = {"generated": 0, "drop_closed_book": 0, "drop_oracle": 0,
             "drop_dup_question": 0, "accepted": 0, "articles_used": 0}
    cat_counts, accepted_qtokens = {}, []
    for b in bench:
        cat_counts[b["category"]] = cat_counts.get(b["category"], 0) + 1
        accepted_qtokens.append(_q_tokens(b["question"]))
    stop = threading.Event()
    lock = threading.Lock()

    def try_admit(items, enforce_quota=True):
        """Serialize admission: quota + question-level dedup."""
        admitted = []
        with lock:
            for q in items:
                if len(bench) >= target:
                    stop.set()
                    break
                cat = q["category"]
                if enforce_quota and cat_counts.get(cat, 0) >= quota:
                    extras.append(q)
                    continue
                toks = _q_tokens(q["question"])
                dup = any(len(toks & t) / max(1, len(toks | t)) >
                          QUESTION_SIM_THRESHOLD for t in accepted_qtokens)
                if dup:
                    stats["drop_dup_question"] += 1
                    continue
                accepted_qtokens.append(toks)
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
                bench.append(q)
                admitted.append(q)
        return admitted

    def worker(article, enforce_quota=True):
        if stop.is_set():
            return 0
        if enforce_quota and \
                cat_counts.get(article["canonical_category"], 0) >= quota:
            quota_skipped.append(article)
            return 0
        items = process_article(article, stats)
        if not items:
            return 0
        stats["articles_used"] += 1
        kept = try_admit(items[:MAX_Q_PER_ARTICLE], enforce_quota)
        with lock:
            extras.extend(items[MAX_Q_PER_ARTICLE:])
        if kept:
            with _print_lock:
                print(f"[{len(bench):>3}/{target}] "
                      f"({article['source']}/{article['canonical_category']}) "
                      f"{article['title'][:40]}")
        return len(kept)

    t0 = time.time()

    def run_pass(pool, enforce_quota=True):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(worker, a, enforce_quota) for a in pool]
            for f in as_completed(futs):
                try:
                    f.result()
                except Exception as e:
                    with _print_lock:
                        print("[worker err]", str(e)[:150])

    run_pass(articles, enforce_quota=True)
    if len(bench) < target and extras:
        pool = list(extras); extras.clear()
        try_admit(pool, enforce_quota=False)
        print(f"[top-up] {len(bench)} after spare questions")
    if len(bench) < target and quota_skipped:
        print(f"[relax] reprocessing {len(quota_skipped)} quota-skipped articles")
        run_pass(list(quota_skipped), enforce_quota=False)

    bench = bench[:target]
    out = out_path
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(bench, fp, ensure_ascii=False, indent=1)
    stats.update({"elapsed_sec": round(time.time() - t0),
                  "final_size": len(bench),
                  "build_date": time.strftime("%Y-%m-%d"),
                  "category_counts": cat_counts})
    with open(os.path.join(DATA_DIR, "stats_v2.json"), "w",
              encoding="utf-8") as fp:
        json.dump(stats, fp, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("saved ->", out)


if __name__ == "__main__":
    tgt = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    main(target=tgt)
