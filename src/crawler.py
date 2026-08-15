# -*- coding: utf-8 -*-
"""English-first multi-source news crawler.

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

# Direct English outlets come first.  Chinese feeds are retained only as a
# shortage fallback; the admission stage enforces the final language mix.
# tuple: (source, canonical-ish category, RSS URL, source language)
FEEDS = [
    ("bbc", "world", "https://feeds.bbci.co.uk/news/world/rss.xml", "en"),
    ("bbc", "business", "https://feeds.bbci.co.uk/news/business/rss.xml", "en"),
    ("bbc", "technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "en"),
    ("bbc", "science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "en"),
    ("bbc", "health", "https://feeds.bbci.co.uk/news/health/rss.xml", "en"),
    ("bbc", "entertainment", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "en"),
    ("bbc-sport", "sports", "https://feeds.bbci.co.uk/sport/rss.xml", "en"),
    ("guardian", "world", "https://www.theguardian.com/world/rss", "en"),
    ("guardian", "business", "https://www.theguardian.com/business/rss", "en"),
    ("guardian", "technology", "https://www.theguardian.com/technology/rss", "en"),
    ("guardian", "science", "https://www.theguardian.com/science/rss", "en"),
    ("guardian", "environment", "https://www.theguardian.com/environment/rss", "en"),
    ("guardian", "sports", "https://www.theguardian.com/sport/rss", "en"),
    ("guardian", "culture", "https://www.theguardian.com/culture/rss", "en"),
    ("nyt", "world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en"),
    ("nyt", "business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "en"),
    ("nyt", "technology", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "en"),
    ("nyt", "science", "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", "en"),
    ("nyt", "health", "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml", "en"),
    ("nyt", "sports", "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml", "en"),
    ("nyt", "culture", "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml", "en"),
    ("sky-news", "world", "https://feeds.skynews.com/feeds/rss/world.xml", "en"),
    ("sky-news", "business", "https://feeds.skynews.com/feeds/rss/business.xml", "en"),
    ("sky-news", "technology", "https://feeds.skynews.com/feeds/rss/technology.xml", "en"),
    ("aljazeera", "world", "https://www.aljazeera.com/xml/rss/all.xml", "en"),
    ("abc-au", "world", "https://www.abc.net.au/news/feed/51120/rss.xml", "en"),
    ("cbc", "world", "https://www.cbc.ca/webfeed/rss/rss-world", "en"),
    ("cbs", "world", "https://www.cbsnews.com/latest/rss/main", "en"),
    ("nbc", "world", "https://feeds.nbcnews.com/nbcnews/public/world", "en"),
    ("politico", "politics", "https://rss.politico.com/politics-news.xml", "en"),
    ("cnbc", "business", "https://www.cnbc.com/id/10001147/device/rss/rss.html", "en"),
    ("techcrunch", "technology", "https://techcrunch.com/feed/", "en"),
    ("ars-technica", "technology", "https://feeds.arstechnica.com/arstechnica/index", "en"),
    ("nasa", "space", "https://www.nasa.gov/news-release/feed/", "en"),
    ("space-news", "space", "https://spacenews.com/feed/", "en"),
    ("science-daily", "science", "https://www.sciencedaily.com/rss/top/science.xml", "en"),
    ("espn", "sports", "https://www.espn.com/espn/rss/news", "en"),
    ("the-verge", "technology", "https://www.theverge.com/rss/index.xml", "en"),
    ("wired", "technology", "https://www.wired.com/feed/rss", "en"),
    ("engadget", "technology", "https://www.engadget.com/rss.xml", "en"),
    ("venturebeat", "technology", "https://venturebeat.com/feed/", "en"),
    ("electrek", "technology", "https://electrek.co/feed/", "en"),
    ("9to5mac", "technology", "https://9to5mac.com/feed/", "en"),
    ("macrumors", "technology", "https://feeds.macrumors.com/MacRumors-All", "en"),
    ("phys-org", "science", "https://phys.org/rss-feed/", "en"),
    ("medicalxpress", "health", "https://medicalxpress.com/rss-feed/", "en"),
    ("space-com", "space", "https://www.space.com/feeds/all", "en"),
    ("motorsport", "sports", "https://www.motorsport.com/rss/all/news/", "en"),
    ("variety", "culture", "https://variety.com/feed/", "en"),
    ("deadline", "culture", "https://deadline.com/feed/", "en"),
    ("rolling-stone", "culture", "https://www.rollingstone.com/music/music-news/feed/", "en"),
    ("coindesk", "business", "https://www.coindesk.com/arc/outboundfeeds/rss/", "en"),
    ("marketwatch", "business", "https://feeds.marketwatch.com/marketwatch/topstories/", "en"),
    ("un-news", "world", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "en"),
    ("white-house", "politics", "https://www.whitehouse.gov/briefing-room/feed/", "en"),
    ("yahoo-news", "world", "https://news.yahoo.com/rss/", "en"),
    ("fox-news", "world", "https://moxie.foxnews.com/google-publisher/world.xml", "en"),
    ("fox-news", "politics", "https://moxie.foxnews.com/google-publisher/politics.xml", "en"),
    ("fox-news", "business", "https://moxie.foxnews.com/google-publisher/economy.xml", "en"),
    ("fox-news", "science", "https://moxie.foxnews.com/google-publisher/science.xml", "en"),
    ("fox-news", "health", "https://moxie.foxnews.com/google-publisher/health.xml", "en"),
    ("fox-news", "sports", "https://moxie.foxnews.com/google-publisher/sports.xml", "en"),
    ("fox-news", "entertainment", "https://moxie.foxnews.com/google-publisher/entertainment.xml", "en"),
    ("newsweek", "world", "https://www.newsweek.com/rss", "en"),
    ("time", "world", "https://time.com/feed/", "en"),
    ("new-york-post", "world", "https://nypost.com/feed/", "en"),
    ("france24", "world", "https://www.france24.com/en/rss", "en"),
    ("dw", "world", "https://rss.dw.com/rdf/rss-en-all", "en"),
    ("euronews", "world", "https://www.euronews.com/rss?level=theme&name=news", "en"),
    ("global-news", "world", "https://globalnews.ca/feed/", "en"),
    ("national-post", "world", "https://nationalpost.com/feed/", "en"),
    ("the-conversation", "science", "https://theconversation.com/us/articles.atom", "en"),
    ("mit-news", "science", "https://news.mit.edu/rss/feed", "en"),
    ("harvard-gazette", "science", "https://news.harvard.edu/gazette/feed/", "en"),
    ("nature", "science", "https://www.nature.com/nature.rss", "en"),
    ("scientific-american", "science", "https://www.scientificamerican.com/feed/", "en"),
    ("live-science", "science", "https://www.livescience.com/feeds/all", "en"),
    ("futurism", "technology", "https://futurism.com/feed", "en"),
    ("gizmodo", "technology", "https://gizmodo.com/rss", "en"),
    ("tomshardware", "technology", "https://www.tomshardware.com/feeds/all", "en"),
    ("android-authority", "technology", "https://www.androidauthority.com/feed", "en"),
    ("mashable", "technology", "https://mashable.com/feeds/rss/all", "en"),
    ("polygon", "culture", "https://www.polygon.com/rss/index.xml", "en"),
    ("gamespot", "culture", "https://www.gamespot.com/feeds/mashup/", "en"),
    ("billboard", "culture", "https://www.billboard.com/feed/", "en"),
    ("hollywood-reporter", "culture", "https://www.hollywoodreporter.com/feed/", "en"),
    ("npr", "world", "https://feeds.npr.org/1004/rss.xml", "en"),
    ("npr", "business", "https://feeds.npr.org/1006/rss.xml", "en"),
    ("npr", "science", "https://feeds.npr.org/1007/rss.xml", "en"),
    ("npr", "health", "https://feeds.npr.org/1128/rss.xml", "en"),
    ("npr", "culture", "https://feeds.npr.org/1008/rss.xml", "en"),
    ("pbs", "world", "https://www.pbs.org/newshour/feeds/rss/headlines", "en"),
    ("propublica", "politics", "https://www.propublica.org/feeds/propublica/main", "en"),
    ("fortune", "business", "https://fortune.com/feed/", "en"),
    ("cointelegraph", "business", "https://cointelegraph.com/rss", "en"),
    ("decrypt", "business", "https://decrypt.co/feed", "en"),
    ("cbs-sports", "sports", "https://www.cbssports.com/rss/headlines/", "en"),
    ("sky-sports", "sports", "https://www.skysports.com/rss/12040", "en"),
    ("defense-news", "politics", "https://www.defensenews.com/arc/outboundfeeds/rss/", "en"),
    ("google-news", "world", "https://news.google.com/rss/search?q=world+news+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("google-news", "business", "https://news.google.com/rss/search?q=business+earnings+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("google-news", "technology", "https://news.google.com/rss/search?q=technology+launch+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("google-news", "science", "https://news.google.com/rss/search?q=science+discovery+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("google-news", "health", "https://news.google.com/rss/search?q=health+study+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("google-news", "sports", "https://news.google.com/rss/search?q=sports+score+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("google-news", "entertainment", "https://news.google.com/rss/search?q=box+office+music+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
    ("bing-news", "world", "https://www.bing.com/news/search?q=world+news&format=rss", "en"),
    ("bing-news", "business", "https://www.bing.com/news/search?q=business&format=rss", "en"),
    ("bing-news", "technology", "https://www.bing.com/news/search?q=technology&format=rss", "en"),
    ("bing-news", "science", "https://www.bing.com/news/search?q=science&format=rss", "en"),
    ("bing-news", "health", "https://www.bing.com/news/search?q=health&format=rss", "en"),
    ("bing-news", "sports", "https://www.bing.com/news/search?q=sports&format=rss", "en"),
    ("bing-news", "entertainment", "https://www.bing.com/news/search?q=entertainment&format=rss", "en"),
    ("chinanews", "general", "https://www.chinanews.com.cn/rss/scroll-news.xml", "zh"),
    ("chinanews", "important", "https://www.chinanews.com.cn/rss/importnews.xml", "zh"),
    ("ithome", "technology", "https://www.ithome.com/rss/", "zh"),
    ("mydrivers", "technology", "https://rss.mydrivers.com/rss.aspx?Tid=1", "zh"),
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
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
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


def fetch_feed(source, category, url, language="en"):
    """Regex-based RSS parsing: robust to malformed XML and trailing junk."""
    items = []
    try:
        xml_text = _get(
            url, timeout=14,
            validator=lambda t: "<item" in t or "<entry" in t,
        )
        blocks = [(b, False) for b in re.findall(
            r"<item[\s>][\s\S]*?</item>", xml_text, re.I
        )]
        blocks += [(b, True) for b in re.findall(
            r"<entry[\s>][\s\S]*?</entry>", xml_text, re.I
        )]
        for block, is_atom in blocks:
            title = _tag(block, "title")
            if is_atom:
                link_match = re.search(
                    r'<link[^>]+(?:rel=["\']alternate["\'][^>]+)?href=["\']([^"\']+)',
                    block, re.I,
                )
                link = htmllib.unescape(link_match.group(1)) if link_match else ""
                pub = _parse_pubdate(_tag(block, "published") or _tag(block, "updated"))
                desc = re.sub(
                    r"<[^>]+>", " ",
                    _tag(block, "summary") or _tag(block, "content"),
                )
            else:
                link = _tag(block, "link")
                pub = _parse_pubdate(_tag(block, "pubDate"))
                desc = re.sub(r"<[^>]+>", " ", _tag(block, "description"))
            if not title or not link.startswith("http"):
                continue
            if pub is not None:
                age = datetime.now(timezone.utc) - pub.astimezone(timezone.utc)
                if age > timedelta(hours=MAX_AGE_HOURS) or \
                        age < -timedelta(hours=6):
                    continue
            items.append({
                "source": source, "category": category, "title": title,
                "url": link, "pub_date": pub.isoformat() if pub else None,
                "rss_desc": desc.strip()[:500], "source_language": language,
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
    """Ordered candidates: article-body images, og:image, then page images."""
    cands = []
    regions = []
    pat = CONTENT_REGION.get(source)
    if pat:
        m = re.search(pat, page, re.I)
        if m:
            regions.append(m.group(0))
    # Generic news pages usually place the article before recommendations.
    article = re.search(r"<article[\s\S]*?</article>", page, re.I)
    if article:
        regions.append(article.group(0))
    og = _extract_og_image(page)
    regions.append(page)
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
        # Place og:image after body candidates but before generic page images.
        if region is not page and og and og not in cands:
            cands.append(og)
    if og and og not in cands:
        cands.insert(0, og)
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


def _fresh_article(article):
    try:
        dt = datetime.fromisoformat(article.get("pub_date") or "")
        age = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        return -timedelta(hours=6) <= age <= timedelta(hours=MAX_AGE_HOURS)
    except Exception:
        return False


def crawl(max_articles=1400):
    out = os.path.join(DATA_DIR, "articles.json")
    existing = []
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fp:
            existing = [a for a in json.load(fp) if _fresh_article(a)]
    seen_ids = {a["id"] for a in existing}
    seen_titles = {a["title"][:30] for a in existing}

    all_items = []
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = [ex.submit(fetch_feed, s, c, u, lang)
                for s, c, u, lang in FEEDS]
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
    # English direct sources first, followed by English aggregation and only
    # then the Chinese fallback pool.
    all_items.sort(key=lambda it: (
        it.get("source_language") != "en",
        it.get("source") == "bing-news",
        it.get("pub_date") or "",
    ))
    articles = list(existing)
    new_count = 0
    ex = ThreadPoolExecutor(max_workers=20)
    futs = {ex.submit(process_item, it): it for it in all_items[:max_articles * 2]}
    try:
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
    finally:
        for future in futs:
            future.cancel()
        # Cancel queued URLs after the target is reached; wait only for the
        # small set that had already started.
        ex.shutdown(wait=True, cancel_futures=True)
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(articles, fp, ensure_ascii=False, indent=1)
    _save_hash_registry()
    print(f"[done] +{new_count} new, {len(articles)} total -> {out}")
    return articles


if __name__ == "__main__":
    t0 = time.time()
    crawl()
    print(f"elapsed {time.time()-t0:.0f}s")
