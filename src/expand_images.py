# -*- coding: utf-8 -*-
"""Add at most one distinct, article-body alternate image per fresh article.

This is a shortage-only expansion path: it preserves one question per image
while allowing an article with two genuinely different news photos to support
two independently audited candidates.
"""
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crawler  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")


def expand(target_total=1200, workers=16):
    path = os.path.join(DATA_DIR, "articles.json")
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    originals_with_alternates = {
        a.get("alternate_image_of")
        for a in articles
        if a.get("alternate_image_of")
    }
    originals = [
        a
        for a in articles
        if not a.get("alternate_image_of")
        and a.get("id") not in originals_with_alternates
    ]
    existing_ids = {a["id"] for a in articles}

    def one(article):
        try:
            published = datetime.fromisoformat(article["pub_date"])
            age = datetime.now(timezone.utc) - published.astimezone(timezone.utc)
            if not (-timedelta(hours=6) <= age <= timedelta(hours=48)):
                return None
            page = crawler._get(
                article["url"], timeout=16,
                validator=lambda text: len(crawler._extract_text(text)) >=
                crawler.MIN_TEXT_CHARS,
            )
            current_url = article.get("image_url")
            for rank, candidate_url in enumerate(crawler._candidate_images(
                    page, article["url"], article["source"]), start=1):
                if candidate_url == current_url:
                    continue
                alt_id = hashlib.md5(
                    f"{article['url']}#alternate-{rank}".encode()
                ).hexdigest()[:12]
                if alt_id in existing_ids:
                    continue
                result = crawler._download_image(
                    candidate_url, alt_id, article["url"]
                )
                if not result:
                    continue
                image_path, (width, height) = result
                output = dict(article)
                output.update({
                    "id": alt_id,
                    "image": image_path,
                    "image_url": candidate_url,
                    "image_size": [width, height],
                    "alternate_image_of": article["id"],
                    "alternate_image_rank": rank,
                    "crawl_time": datetime.now(
                        timezone(timedelta(hours=8))
                    ).isoformat(),
                })
                return output
        except Exception:
            return None
        return None

    needed = max(0, target_total - len(articles))
    added = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = [executor.submit(one, article) for article in originals]
    try:
        for future in as_completed(futures):
            item = future.result()
            if item and item["id"] not in existing_ids:
                existing_ids.add(item["id"])
                added.append(item)
                if len(added) % 25 == 0:
                    print(f"[alternate images] +{len(added)}")
            if len(added) >= needed:
                break
    finally:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
    articles.extend(added)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=1)
    crawler._save_hash_registry()
    print(f"[alternate images] added {len(added)}; total {len(articles)}")
    return len(articles)


if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    expand(target_total=target)
