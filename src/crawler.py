# -*- coding: utf-8 -*-
"""Multi-source news crawler.

Pulls fresh (<48h) news items from RSS feeds reachable from this network,
fetches each article page, extracts main text + og:image, downloads and
normalizes the image. Output: data/articles.json + data/images/*.jpg
"""
import os
import re
import io
import json
import time
import hashlib
import html as htmllib
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import threading

import requests
from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")
IMG_DIR = os.path.join(DATA_DIR, "images")
HASH_REG_PATH = os.path.join(DATA_DIR, "image_hashes.json")
os.makedirs(IMG_DIR, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# The system proxy on this machine breaks some domestic hosts, while some
# foreign hosts (bing) require it. Try direct first, then fall back to proxy.
SESSION_DIRECT = requests.Session()
SESSION_DIRECT.trust_env = False
SESSION_PROXY = requests.Session()

FEEDS = [
    ("ithome",     "tech",          "https://www.ithome.com/rss/"),
    ("chinanews",  "general",       "https://www.chinanews.com.cn/rss/scroll-news.xml"),
    ("people",     "politics",      "http://www.people.com.cn/rss/politics.xml"),
    ("people",     "world",         "http://www.people.com.cn/rss/world.xml"),
    ("people",     "society",       "http://www.people.com.cn/rss/society.xml"),
    ("people",     "sports",        "http://www.people.com.cn/rss/sports.xml"),
    ("people",     "finance",       "http://www.people.com.cn/rss/finance.xml"),
    ("people",     "military",      "http://www.people.com.cn/rss/military.xml"),
    ("people",     "entertainment", "http://www.people.com.cn/rss/ent.xml"),
    ("people",     "education",     "http://www.people.com.cn/rss/edu.xml"),
    ("chinanews",  "important",     "https://www.chinanews.com.cn/rss/importnews.xml"),
    ("bing-news",  "technology",    "https://www.bing.com/news/search?q=technology&format=rss"),
    ("bing-news",  "business",      "https://www.bing.com/news/search?q=business&format=rss"),
    ("bing-news",  "health",        "https://www.bing.com/news/search?q=health&format=rss"),
    ("36kr",       "business",      "https://36kr.com/feed"),
    ("cnbeta",     "tech",          "https://www.cnbeta.com.tw/backend.php"),
    ("bing-news",  "world",         "https://www.bing.com/news/search?q=world+news&format=rss"),
    ("bing-news",  "sports",        "https://www.bing.com/news/search?q=sports&format=rss"),
    ("bing-news",  "science",       "https://www.bing.com/news/search?q=science&format=rss"),
    ("bing-news",  "entertainment", "https://www.bing.com/news/search?q=entertainment&format=rss"),
    ("bing-news",  "finance",       "https://www.bing.com/news/search?q=finance&format=rss"),
    ("bing-news",  "space",         "https://www.bing.com/news/search?q=space+exploration&format=rss"),
    ("bing-news",  "ai",            "https://www.bing.com/news/search?q=artificial+intelligence&format=rss"),
    ("bing-news",  "football",      "https://www.bing.com/news/search?q=football&format=rss"),
    ("bing-news",  "movies",        "https://www.bing.com/news/search?q=movie+box+office&format=rss"),
    ("sina",       "tech",          "https://rss.sina.com.cn/tech/rollnews.xml"),
    ("solidot",    "tech",          "https://www.solidot.org/index.rss"),
    ("ifanr",      "tech",          "https://www.ifanr.com/feed"),
    ("sspai",      "tech",          "https://sspai.com/feed"),
    ("huxiu",      "business",      "https://www.huxiu.com/rss/0.xml"),
    ("mydrivers",  "tech",          "https://rss.mydrivers.com/rss.aspx?Tid=1"),
]

MAX_AGE_HOURS = 48
MIN_TEXT_CHARS = 300
MIN_IMG_W, MIN_IMG_H = 260, 180


def _get_one(sess, url, timeout=15, binary=False):
    r = sess.get(url, headers={"User-Agent": UA}, timeout=timeout,
                 allow_redirects=True)
    r.raise_for_status()
    if binary:
        return r.content
    if not r.encoding or r.encoding.lower() in ("iso-8859-1",):
        r.encoding = r.apparent_encoding
    return r.text


def _get(url, timeout=15, binary=False, validator=None):
    """Fetch trying direct connection first, then the system proxy.

    Some hosts serve anti-bot JS pages on one channel and real content on
    the other, so a 200 status is not enough: `validator(result)` decides
    whether a response is usable.
    """
    last_err, fallback = None, None
    for sess in (SESSION_DIRECT, SESSION_PROXY):
        try:
            res = _get_one(sess, url, timeout=timeout, binary=binary)
            if validator is None or validator(res):
                return res
            fallback = res
        except Exception as e:
            last_err = e
    if fallback is not None:
        return fallback
    raise last_err


def _parse_pubdate(s):
    if not s:
        return None
    s = s.strip()
    fmts = ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
            return dt
        except Exception:
            continue
    return None


def _tag(block, tag):
    m = re.search(rf"<{tag}[^>]*>([\s\S]*?)</{tag}>", block, re.I)
    if not m:
        return ""
    v = m.group(1).strip()
    cd = re.match(r"<!\[CDATA\[([\s\S]*?)\]\]>", v)
    if cd:
        v = cd.group(1).strip()
    return htmllib.unescape(v)


def fetch_feed(source, category, url):
    """Regex-based RSS parsing: robust to malformed XML and trailing junk."""
    items = []
    try:
        xml_text = _get(url, timeout=25, validator=lambda t: "<item" in t)
        blocks = re.findall(r"<item[\s>][\s\S]*?</item>", xml_text, re.I)
        for block in blocks:
            title = _tag(block, "title")
            link = _tag(block, "link")
            pub = _parse_pubdate(_tag(block, "pubDate"))
            desc = re.sub(r"<[^>]+>", " ", _tag(block, "description"))
            if not title or not link.startswith("http"):
                continue
            if pub is not None:
                age = datetime.now(timezone.utc) - pub.astimezone(timezone.utc)
                if age > timedelta(hours=MAX_AGE_HOURS):
                    continue
            items.append({
                "source": source, "category": category, "title": title,
                "url": link, "pub_date": pub.isoformat() if pub else None,
                "rss_desc": desc.strip()[:500],
            })
    except Exception as e:
        print(f"[feed fail] {source}/{category}: {str(e)[:120]}")
    return items


def _extract_og_image(page):
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        page, re.I)
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            page, re.I)
    return htmllib.unescape(m.group(1)).strip() if m else None


def _extract_text(page):
    page = re.sub(r"<script[\s\S]*?</script>", " ", page, flags=re.I)
    page = re.sub(r"<style[\s\S]*?</style>", " ", page, flags=re.I)
    paras = re.findall(r"<p[^>]*>([\s\S]*?)</p>", page, re.I)
    out = []
    for p in paras:
        t = re.sub(r"<[^>]+>", " ", p)
        t = htmllib.unescape(t)
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) >= 20:
            out.append(t)
    return "\n".join(out)


# regexes that isolate the article body per source (fallback: whole page)
CONTENT_REGION = {
    "chinanews": r'<div[^>]+class="left_zw"[\s\S]*?</div>',
    "people":    r'<div[^>]+class="rm_txt_con[\s\S]*?<!--|<div[^>]+class="rm_txt_con[\s\S]*?</div>',
    "ithome":    r'<div[^>]+id="paragraph"[\s\S]*?</div>',
}

_BAD_IMG_WORDS = ("logo", "icon", "arrow", "qrcode", "avatar", "weixin",
                  "weibo", "banner", "btn", "share", "ad_", "blank")


def _candidate_images(page, base_url, source):
    """Ordered candidate image URLs: og:image, body images, page images."""
    cands = []
    og = _extract_og_image(page)
    if og:
        cands.append(og)
    regions = [page]
    pat = CONTENT_REGION.get(source)
    if pat:
        m = re.search(pat, page, re.I)
        if m:
            regions.insert(0, m.group(0))
    for region in regions:
        for m in re.finditer(
                r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                region, re.I):
            src = htmllib.unescape(m.group(1)).strip()
            low = src.lower()
            if src.startswith("data:") or any(w in low for w in _BAD_IMG_WORDS):
                continue
            if not re.search(r"\.(jpe?g|png|webp)", src, re.I):
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                m2 = re.match(r"(https?://[^/]+)", base_url)
                if not m2:
                    continue
                src = m2.group(1) + src
            if src.startswith("http") and src not in cands:
                cands.append(src)
    return cands[:6]


# ---------- perceptual dedup (dHash) ----------
# Registry persists across days so the benchmark never repeats an image,
# even when different outlets reuse the same press photo.
DEDUP_HAMMING_MAX = 6
_hash_lock = threading.Lock()


def _load_hash_registry():
    if os.path.exists(HASH_REG_PATH):
        with open(HASH_REG_PATH, encoding="utf-8") as f:
            return {k: int(v, 16) for k, v in json.load(f).items()}
    return {}


_hash_registry = _load_hash_registry()


def _save_hash_registry():
    with _hash_lock:
        with open(HASH_REG_PATH, "w", encoding="utf-8") as f:
            json.dump({k: format(v, "x") for k, v in _hash_registry.items()},
                      f, indent=0)


def _dhash(im, size=8):
    g = im.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            bits = (bits << 1) | (px[row + x + 1] > px[row + x])
    return bits


def _is_duplicate_image(im, item_id):
    h = _dhash(im)
    with _hash_lock:
        for other_id, other_h in _hash_registry.items():
            if other_id != item_id and \
                    bin(h ^ other_h).count("1") <= DEDUP_HAMMING_MAX:
                return True
        _hash_registry[item_id] = h
    return False


def _looks_like_image(raw):
    try:
        Image.open(io.BytesIO(raw)).verify()
        return True
    except Exception:
        return False


def _download_image(img_url, item_id, referer=None):
    try:
        raw = _get(img_url, timeout=20, binary=True,
                   validator=_looks_like_image)
        im = Image.open(io.BytesIO(raw))
        im.load()
        if im.width < MIN_IMG_W or im.height < MIN_IMG_H:
            return None
        if im.mode != "RGB":
            im = im.convert("RGB")
        if _is_duplicate_image(im, item_id):
            return None
        if max(im.size) > 1024:
            ratio = 1024 / max(im.size)
            im = im.resize((int(im.width * ratio), int(im.height * ratio)))
        path = os.path.join(IMG_DIR, f"{item_id}.jpg")
        im.save(path, "JPEG", quality=88)
        return f"images/{item_id}.jpg", im.size
    except Exception:
        return None


def _date_from_url(url):
    """people/chinanews style URLs embed the publish date."""
    m = re.search(r"/(20\d{2})[-/]?(\d{2})[-/]?(\d{2})/", url) or \
        re.search(r"/(20\d{2})(\d{2})/(\d{2})", url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        tzinfo=timezone(timedelta(hours=8)))
    except ValueError:
        return None


def process_item(item):
    # enforce freshness even when RSS omits pubDate (e.g. people.com.cn
    # feeds mix in years-old articles)
    if not item.get("pub_date"):
        dt = _date_from_url(item["url"])
        if dt is None:
            return None
        if datetime.now(timezone.utc) - dt.astimezone(timezone.utc) > \
                timedelta(hours=MAX_AGE_HOURS):
            return None
        item["pub_date"] = dt.isoformat()

    def _valid_page(p):
        return len(_extract_text(p)) >= MIN_TEXT_CHARS
    try:
        page = _get(item["url"], timeout=20, validator=_valid_page)
    except Exception:
        return None
    text = _extract_text(page)
    if len(text) < MIN_TEXT_CHARS:
        return None
    item_id = hashlib.md5(item["url"].encode()).hexdigest()[:12]
    res, img_url = None, None
    for cand in _candidate_images(page, item["url"], item["source"]):
        res = _download_image(cand, item_id, item["url"])
        if res:
            img_url = cand
            break
    if not res:
        return None
    img_path, (w, h) = res
    item.update({
        "id": item_id,
        "text": text[:4000],
        "image": img_path,
        "image_url": img_url,
        "image_size": [w, h],
        "crawl_time": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    })
    return item


def crawl(max_articles=400):
    out = os.path.join(DATA_DIR, "articles.json")
    existing = []
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fp:
            existing = json.load(fp)
    seen_ids = {a["id"] for a in existing}
    seen_titles = {a["title"][:30] for a in existing}

    all_items = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch_feed, s, c, u) for s, c, u in FEEDS]
        for f in as_completed(futs):
            for it in f.result():
                key = it["title"][:30]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                all_items.append(it)
    print(f"[rss] {len(all_items)} candidate items")

    all_items = [it for it in all_items
                 if hashlib.md5(it["url"].encode()).hexdigest()[:12]
                 not in seen_ids]
    articles = list(existing)
    new_count = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(process_item, it): it for it in all_items[:max_articles * 2]}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception:
                r = None
            if r and r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                articles.append(r)
                new_count += 1
                if new_count % 25 == 0:
                    print(f"[crawl] +{new_count} new articles "
                          f"(total {len(articles)})")
            if len(articles) >= max_articles:
                break
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(articles, fp, ensure_ascii=False, indent=1)
    _save_hash_registry()
    print(f"[done] +{new_count} new, {len(articles)} total -> {out}")
    return articles


if __name__ == "__main__":
    t0 = time.time()
    crawl()
    print(f"elapsed {time.time()-t0:.0f}s")
