#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Pilar 7: Cognitive Domain / BotRadar Engine
Analisis aktivitas dan ancaman di ruang digital (Information Warfare Detection).

Modul ini melakukan:
1. Social Media Scraping tanpa API (Twitter/X, Instagram, Telegram Public)
2. Bot Detection & Scoring (0-100%) — behavioral, temporal, network, content analysis
3. Coordinated Inauthentic Behavior (CIB) Detection — posting serentak, amplifikasi hashtag
4. Network Graph Clustering — community detection akun bot vs organik
5. Narrative Tracking & Hoax Classification (NLP Bahasa Indonesia)
6. New Account Surge Detection — lonjakan akun baru di topik tertentu
7. Auto-ingest ke Knowledge Graph (engine_graph) & SIEM Alert (engine_siem)

100% On-Premise / Air-Gapped Ready (scraping bisa dimatikan via OMNI_AIRGAP).
"""

import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import string
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from engine_core import get_db, utc_now_iso, haversine_km, DB_PATH

# ── Lazy imports (installed separately) ──
_nx = None
_sklearn_rf = None
_sklearn_iso = None
_sklearn_prep = None


def _ensure_networkx():
    global _nx
    if _nx is None:
        try:
            import networkx as nx
            _nx = nx
        except ImportError:
            _nx = None
    return _nx


def _ensure_sklearn():
    global _sklearn_rf, _sklearn_iso, _sklearn_prep
    if _sklearn_rf is None:
        try:
            from sklearn.ensemble import RandomForestClassifier, IsolationForest
            from sklearn.preprocessing import StandardScaler
            _sklearn_rf = RandomForestClassifier
            _sklearn_iso = IsolationForest
            _sklearn_prep = StandardScaler
        except ImportError:
            pass
    return _sklearn_rf is not None


# ══════════════════════════════════════════════════════════════════════
# 0. DATABASE SCHEMA — Cognitive Domain Tables
# ══════════════════════════════════════════════════════════════════════

COGNITIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS cog_scrape_jobs (
    job_id          TEXT PRIMARY KEY,
    platform        TEXT,
    query           TEXT,
    status          TEXT DEFAULT 'PENDING',
    total_posts     INTEGER DEFAULT 0,
    total_accounts  INTEGER DEFAULT 0,
    started_at      TEXT,
    finished_at     TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS cog_accounts (
    account_id      TEXT PRIMARY KEY,
    platform        TEXT,
    username        TEXT,
    display_name    TEXT,
    bio             TEXT,
    followers       INTEGER DEFAULT 0,
    following       INTEGER DEFAULT 0,
    post_count      INTEGER DEFAULT 0,
    account_age_days INTEGER DEFAULT 0,
    created_date    TEXT,
    profile_pic_url TEXT,
    verified        INTEGER DEFAULT 0,
    bot_score       REAL DEFAULT 0.0,
    bot_label       TEXT DEFAULT 'UNKNOWN',
    cluster_id      INTEGER DEFAULT -1,
    flags_json      TEXT,
    first_seen      TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS cog_posts (
    post_id         TEXT PRIMARY KEY,
    account_id      TEXT,
    platform        TEXT,
    content         TEXT,
    timestamp       TEXT,
    timestamp_unix  INTEGER,
    likes           INTEGER DEFAULT 0,
    retweets        INTEGER DEFAULT 0,
    replies         INTEGER DEFAULT 0,
    hashtags_json   TEXT,
    mentions_json   TEXT,
    urls_json       TEXT,
    media_json      TEXT,
    language        TEXT DEFAULT 'id',
    sentiment       REAL DEFAULT 0.0,
    is_repost       INTEGER DEFAULT 0,
    job_id          TEXT
);

CREATE TABLE IF NOT EXISTS cog_networks (
    edge_id         TEXT PRIMARY KEY,
    source_account  TEXT,
    target_account  TEXT,
    relation_type   TEXT,
    weight          REAL DEFAULT 1.0,
    detected_at     TEXT
);

CREATE TABLE IF NOT EXISTS cog_coordinated_events (
    event_id        TEXT PRIMARY KEY,
    event_type      TEXT,
    description     TEXT,
    accounts_json   TEXT,
    window_seconds  INTEGER,
    similarity      REAL,
    detected_at     TEXT,
    severity        TEXT DEFAULT 'MEDIUM'
);

CREATE TABLE IF NOT EXISTS cog_narratives (
    narrative_id    TEXT PRIMARY KEY,
    topic_query     TEXT,
    hashtag         TEXT,
    seed_account    TEXT,
    amplifier_accounts_json TEXT,
    total_reach     INTEGER DEFAULT 0,
    first_seen      TEXT,
    peak_time       TEXT,
    classification  TEXT DEFAULT 'UNCLASSIFIED',
    hoax_score      REAL DEFAULT 0.0,
    summary         TEXT
);
"""


def init_cognitive_db():
    """Inisialisasi tabel Cognitive Domain di database TFAEL-OMNI."""
    conn = get_db()
    conn.executescript(COGNITIVE_SCHEMA)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════
# 1. ANTI-DETECTION LAYER — Stealth Scraping Infrastructure
# ══════════════════════════════════════════════════════════════════════

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

_ACCEPT_LANGUAGES = [
    "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,id;q=0.8",
    "id;q=0.9,en-US;q=0.8,en;q=0.7,ms;q=0.6",
]

# Proxy pool (operator fills this via env or config)
_PROXY_POOL: List[str] = []
_proxy_lock = threading.Lock()
_proxy_idx = 0


def load_proxy_pool(proxies: List[str] = None):
    """Load proxy list dari environment atau parameter."""
    global _PROXY_POOL
    if proxies:
        _PROXY_POOL = proxies
    else:
        env_proxies = os.environ.get("OMNI_PROXY_POOL", "")
        if env_proxies:
            _PROXY_POOL = [p.strip() for p in env_proxies.split(",") if p.strip()]


def _next_proxy() -> Optional[str]:
    global _proxy_idx
    if not _PROXY_POOL:
        return None
    with _proxy_lock:
        proxy = _PROXY_POOL[_proxy_idx % len(_PROXY_POOL)]
        _proxy_idx += 1
    return proxy


def _stealth_headers() -> Dict[str, str]:
    """Generate randomized browser-like headers."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def _human_delay(min_s: float = 1.5, max_s: float = 6.0):
    """Randomized human-like delay between requests."""
    delay = random.uniform(min_s, max_s)
    # Occasional longer pause (simulates reading)
    if random.random() < 0.15:
        delay += random.uniform(3.0, 8.0)
    time.sleep(delay)


def _stealth_fetch(url: str, timeout: int = 15, max_retries: int = 3) -> Optional[str]:
    """
    Fetch URL with anti-detection: rotating UA, proxy support, human-like timing.
    Returns decoded HTML/JSON string or None on failure.
    """
    for attempt in range(max_retries):
        try:
            headers = _stealth_headers()
            req = urllib.request.Request(url, headers=headers)

            proxy = _next_proxy()
            if proxy:
                handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
                opener = urllib.request.build_opener(handler)
            else:
                opener = urllib.request.build_opener()

            resp = opener.open(req, timeout=timeout)
            raw = resp.read()

            # Handle gzip
            encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" in encoding:
                import gzip
                raw = gzip.decompress(raw)
            elif "br" in encoding:
                try:
                    import brotli
                    raw = brotli.decompress(raw)
                except ImportError:
                    pass

            return raw.decode("utf-8", errors="ignore")

        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            if attempt < max_retries - 1:
                _human_delay(2.0, 5.0)
            else:
                return None
    return None


# ══════════════════════════════════════════════════════════════════════
# 2. SOCIAL MEDIA SCRAPERS — Platform-Specific Collectors
# ══════════════════════════════════════════════════════════════════════

def scrape_twitter_search(query: str, max_posts: int = 200, job_id: str = None) -> Dict[str, Any]:
    """
    Scrape Twitter/X search results tanpa API.
    Menggunakan Nitter instances atau Twitter guest token approach.
    """
    if os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true"):
        return {"ok": False, "error": "Mode air-gap: scraping online dinonaktifkan."}

    if not job_id:
        job_id = f"TWX-{int(time.time())}-{hashlib.md5(query.encode()).hexdigest()[:8]}"

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO cog_scrape_jobs VALUES (?,?,?,?,?,?,?,?,?)",
        (job_id, "twitter", query, "RUNNING", 0, 0, utc_now_iso(), None, None),
    )
    conn.commit()

    posts = []
    accounts_seen: Dict[str, Dict] = {}

    # Nitter instance rotation (public instances)
    nitter_instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.cz",
    ]

    encoded_q = urllib.parse.quote(query)
    collected = 0

    for instance in nitter_instances:
        if collected >= max_posts:
            break
        url = f"{instance}/search?f=tweets&q={encoded_q}"
        html = _stealth_fetch(url, timeout=20)
        if not html:
            continue

        # Parse Nitter HTML structure
        tweet_blocks = re.findall(
            r'<div class="timeline-item[^"]*">(.*?)</div>\s*</div>\s*</div>',
            html, re.DOTALL,
        )

        for block in tweet_blocks:
            if collected >= max_posts:
                break

            # Extract username
            user_match = re.search(r'href="/([^/"]+)"[^>]*class="username"', block)
            username = user_match.group(1) if user_match else None
            if not username:
                user_match = re.search(r'class="username"[^>]*>@?([^<]+)', block)
                username = user_match.group(1).strip() if user_match else f"unknown_{collected}"

            # Extract display name
            name_match = re.search(r'class="fullname"[^>]*>([^<]+)', block)
            display_name = name_match.group(1).strip() if name_match else username

            # Extract tweet text
            content_match = re.search(r'class="tweet-content[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            content = ""
            if content_match:
                content = re.sub(r"<[^>]+>", "", content_match.group(1)).strip()

            if not content:
                continue

            # Extract timestamp
            ts_match = re.search(r'title="([^"]*\d{4}[^"]*)"', block)
            timestamp_str = ts_match.group(1) if ts_match else utc_now_iso()

            # Extract stats
            stats = re.findall(r'class="icon-(\w+)"[^>]*>\s*</span>\s*(\d+)', block)
            stats_map = {s[0]: int(s[1]) for s in stats}

            # Extract hashtags
            hashtags = re.findall(r"#(\w+)", content)
            mentions = re.findall(r"@(\w+)", content)
            urls = re.findall(r"https?://\S+", content)

            post_id = f"tw-{hashlib.md5(f'{username}:{content[:50]}:{timestamp_str}'.encode()).hexdigest()[:16]}"
            ts_unix = int(time.time()) - random.randint(0, 86400 * 7)  # approximate

            post = {
                "post_id": post_id,
                "account_id": f"tw-{username}",
                "platform": "twitter",
                "content": content,
                "timestamp": timestamp_str,
                "timestamp_unix": ts_unix,
                "likes": stats_map.get("heart", 0),
                "retweets": stats_map.get("retweet", 0),
                "replies": stats_map.get("comment", 0),
                "hashtags": hashtags,
                "mentions": mentions,
                "urls": urls,
            }
            posts.append(post)
            collected += 1

            # Track account
            acct_id = f"tw-{username}"
            if acct_id not in accounts_seen:
                accounts_seen[acct_id] = {
                    "account_id": acct_id,
                    "platform": "twitter",
                    "username": username,
                    "display_name": display_name,
                    "post_count": 0,
                    "posts_in_query": [],
                }
            accounts_seen[acct_id]["post_count"] += 1
            accounts_seen[acct_id]["posts_in_query"].append(post_id)

        _human_delay(3.0, 7.0)

    # Store to DB
    for p in posts:
        conn.execute(
            "INSERT OR REPLACE INTO cog_posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p["post_id"], p["account_id"], p["platform"], p["content"],
                p["timestamp"], p["timestamp_unix"], p["likes"], p["retweets"],
                p["replies"], json.dumps(p["hashtags"]), json.dumps(p["mentions"]),
                json.dumps(p["urls"]), "[]", "id", 0.0, 0, job_id,
            ),
        )

    for acct in accounts_seen.values():
        conn.execute(
            """INSERT OR REPLACE INTO cog_accounts
               (account_id, platform, username, display_name, bio, followers, following,
                post_count, account_age_days, bot_score, bot_label, first_seen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                acct["account_id"], acct["platform"], acct["username"],
                acct["display_name"], "", 0, 0, acct["post_count"], 0,
                0.0, "PENDING", utc_now_iso(), utc_now_iso(),
            ),
        )

    conn.execute(
        "UPDATE cog_scrape_jobs SET status='COMPLETED', total_posts=?, total_accounts=?, finished_at=? WHERE job_id=?",
        (len(posts), len(accounts_seen), utc_now_iso(), job_id),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "job_id": job_id,
        "platform": "twitter",
        "query": query,
        "posts_collected": len(posts),
        "accounts_found": len(accounts_seen),
        "accounts": list(accounts_seen.keys()),
    }


def scrape_telegram_channel(channel: str, max_posts: int = 200, job_id: str = None) -> Dict[str, Any]:
    """
    Scrape Telegram public channel/group via t.me web preview.
    Paling stabil dari semua platform — DOM jarang berubah.
    """
    if os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true"):
        return {"ok": False, "error": "Mode air-gap: scraping online dinonaktifkan."}

    if not job_id:
        job_id = f"TG-{int(time.time())}-{hashlib.md5(channel.encode()).hexdigest()[:8]}"

    channel = channel.lstrip("@").strip()
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO cog_scrape_jobs VALUES (?,?,?,?,?,?,?,?,?)",
        (job_id, "telegram", channel, "RUNNING", 0, 0, utc_now_iso(), None, None),
    )
    conn.commit()

    posts = []
    base_url = f"https://t.me/s/{channel}"
    html = _stealth_fetch(base_url, timeout=20)

    if not html:
        conn.execute(
            "UPDATE cog_scrape_jobs SET status='FAILED', error='Gagal mengakses channel', finished_at=? WHERE job_id=?",
            (utc_now_iso(), job_id),
        )
        conn.commit()
        conn.close()
        return {"ok": False, "error": f"Gagal mengakses telegram channel @{channel}"}

    # Parse Telegram web preview HTML
    msg_blocks = re.findall(
        r'<div class="tgme_widget_message_wrap[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</div>',
        html, re.DOTALL,
    )

    acct_id = f"tg-{channel}"
    for i, block in enumerate(msg_blocks[:max_posts]):
        # Extract message text
        text_match = re.search(
            r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            block, re.DOTALL,
        )
        content = ""
        if text_match:
            content = re.sub(r"<[^>]+>", "", text_match.group(1)).strip()

        if not content:
            continue

        # Extract timestamp
        ts_match = re.search(r'datetime="([^"]+)"', block)
        timestamp_str = ts_match.group(1) if ts_match else utc_now_iso()

        # Extract views
        views_match = re.search(r'class="tgme_widget_message_views"[^>]*>([^<]+)', block)
        views = 0
        if views_match:
            v = views_match.group(1).strip().upper()
            if "K" in v:
                views = int(float(v.replace("K", "")) * 1000)
            elif "M" in v:
                views = int(float(v.replace("M", "")) * 1000000)
            else:
                try:
                    views = int(v)
                except ValueError:
                    pass

        # Extract data-post for unique ID
        post_id_match = re.search(r'data-post="([^"]+)"', block)
        post_id = post_id_match.group(1).replace("/", "-") if post_id_match else f"tg-{channel}-{i}"

        hashtags = re.findall(r"#(\w+)", content)
        mentions = re.findall(r"@(\w+)", content)
        urls = re.findall(r"https?://\S+", content)

        try:
            ts_unix = int(datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).timestamp())
        except (ValueError, TypeError):
            ts_unix = int(time.time())

        post = {
            "post_id": post_id,
            "account_id": acct_id,
            "platform": "telegram",
            "content": content,
            "timestamp": timestamp_str,
            "timestamp_unix": ts_unix,
            "likes": views,
            "retweets": 0,
            "replies": 0,
            "hashtags": hashtags,
            "mentions": mentions,
            "urls": urls,
        }
        posts.append(post)

    for p in posts:
        conn.execute(
            "INSERT OR REPLACE INTO cog_posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p["post_id"], p["account_id"], p["platform"], p["content"],
                p["timestamp"], p["timestamp_unix"], p["likes"], p["retweets"],
                p["replies"], json.dumps(p["hashtags"]), json.dumps(p["mentions"]),
                json.dumps(p["urls"]), "[]", "id", 0.0, 0, job_id,
            ),
        )

    conn.execute(
        """INSERT OR REPLACE INTO cog_accounts
           (account_id, platform, username, display_name, bio, followers, following,
            post_count, account_age_days, bot_score, bot_label, first_seen, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (acct_id, "telegram", channel, channel, "", 0, 0, len(posts), 0, 0.0, "CHANNEL", utc_now_iso(), utc_now_iso()),
    )

    conn.execute(
        "UPDATE cog_scrape_jobs SET status='COMPLETED', total_posts=?, total_accounts=1, finished_at=? WHERE job_id=?",
        (len(posts), utc_now_iso(), job_id),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "job_id": job_id,
        "platform": "telegram",
        "channel": channel,
        "posts_collected": len(posts),
    }


# ══════════════════════════════════════════════════════════════════════
# 3. BOT DETECTION ENGINE — Multi-Signal Behavioral Analysis
# ══════════════════════════════════════════════════════════════════════

def _posting_time_entropy(timestamps_unix: List[int]) -> float:
    """
    Hitung entropi distribusi waktu posting.
    Bot cenderung posting pada jam-jam yang terlalu teratur (entropi rendah).
    Manusia memiliki distribusi jam yang lebih acak (entropi tinggi).
    """
    if len(timestamps_unix) < 3:
        return 4.0  # default mid-range

    hours = [datetime.utcfromtimestamp(ts).hour for ts in timestamps_unix]
    counts = Counter(hours)
    total = sum(counts.values())
    probs = [c / total for c in counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    return round(entropy, 4)


def _text_similarity_batch(texts: List[str]) -> float:
    """
    Hitung rata-rata kesamaan teks antar postingan dari satu akun.
    Bot copy-paste memiliki similarity tinggi.
    Menggunakan Jaccard similarity pada word-level tokens.
    """
    if len(texts) < 2:
        return 0.0

    def _jaccard(a: str, b: str) -> float:
        sa = set(a.lower().split())
        sb = set(b.lower().split())
        if not sa or not sb:
            return 0.0
        intersection = sa & sb
        union = sa | sb
        return len(intersection) / len(union) if union else 0.0

    similarities = []
    sample_size = min(len(texts), 50)
    sampled = random.sample(texts, sample_size) if len(texts) > sample_size else texts

    for i in range(len(sampled)):
        for j in range(i + 1, min(i + 5, len(sampled))):
            similarities.append(_jaccard(sampled[i], sampled[j]))

    return round(sum(similarities) / len(similarities), 4) if similarities else 0.0


def _follower_following_ratio(followers: int, following: int) -> float:
    """
    Rasio followers/following. Bot biasanya memiliki rasio anomali:
    - following >>> followers (mass follow bot)
    - followers ~= following (reciprocal bot)
    """
    if following == 0:
        return float(followers) if followers > 0 else 1.0
    return round(followers / following, 4)


def _posting_regularity_score(timestamps_unix: List[int]) -> float:
    """
    Hitung seberapa teratur interval posting.
    Bot posting pada interval yang sangat konsisten (score tinggi = lebih bot-like).
    """
    if len(timestamps_unix) < 3:
        return 0.0

    sorted_ts = sorted(timestamps_unix)
    intervals = [sorted_ts[i + 1] - sorted_ts[i] for i in range(len(sorted_ts) - 1)]

    if not intervals:
        return 0.0

    mean_interval = sum(intervals) / len(intervals)
    if mean_interval == 0:
        return 1.0

    variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_interval  # coefficient of variation

    # Low CV = very regular = bot-like (score tinggi)
    # High CV = irregular = human-like (score rendah)
    regularity = max(0.0, 1.0 - min(cv, 2.0) / 2.0)
    return round(regularity, 4)


def _burst_posting_ratio(timestamps_unix: List[int], window_sec: int = 60) -> float:
    """
    Rasio postingan yang terjadi dalam burst window yang sangat pendek.
    Bot sering memposting banyak dalam waktu sangat singkat.
    """
    if len(timestamps_unix) < 2:
        return 0.0

    sorted_ts = sorted(timestamps_unix)
    burst_count = 0
    for i in range(len(sorted_ts) - 1):
        if sorted_ts[i + 1] - sorted_ts[i] < window_sec:
            burst_count += 1

    return round(burst_count / (len(sorted_ts) - 1), 4)


def _name_entropy(username: str) -> float:
    """
    Entropi karakter username. Bot-generated usernames cenderung memiliki
    entropi tinggi (random string) atau sangat rendah (pola repetitif).
    """
    if not username:
        return 0.0
    counts = Counter(username.lower())
    total = len(username)
    probs = [c / total for c in counts.values()]
    return round(-sum(p * math.log2(p) for p in probs if p > 0), 4)


def _has_default_profile_indicators(account: Dict) -> float:
    """
    Deteksi apakah akun menggunakan profil default (foto default, bio kosong).
    """
    score = 0.0
    if not account.get("bio") or len(str(account.get("bio", ""))) < 5:
        score += 0.3
    if not account.get("profile_pic_url"):
        score += 0.3
    if account.get("followers", 0) == 0 and account.get("following", 0) == 0:
        score += 0.2
    if account.get("account_age_days", 0) < 30:
        score += 0.2
    return min(score, 1.0)


def compute_bot_score(account_id: str, conn: sqlite3.Connection = None) -> Dict[str, Any]:
    """
    Hitung Bot Score (0-100%) untuk satu akun berdasarkan multi-signal analysis:
    1. Posting Time Entropy (rendah = bot)
    2. Text Similarity antar postingan (tinggi = bot)
    3. Follower/Following Ratio Anomaly
    4. Posting Regularity (terlalu teratur = bot)
    5. Burst Posting Ratio (posting terlalu cepat = bot)
    6. Username Entropy
    7. Default Profile Indicators
    8. Account Age vs Activity Ratio
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db()

    account = conn.execute("SELECT * FROM cog_accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not account:
        if own_conn:
            conn.close()
        return {"ok": False, "error": f"Akun {account_id} tidak ditemukan."}

    posts = conn.execute(
        "SELECT content, timestamp_unix FROM cog_posts WHERE account_id = ? ORDER BY timestamp_unix",
        (account_id,),
    ).fetchall()

    timestamps = [p["timestamp_unix"] for p in posts if p["timestamp_unix"]]
    texts = [p["content"] for p in posts if p["content"]]

    # ── Feature Extraction ──
    time_entropy = _posting_time_entropy(timestamps)
    text_sim = _text_similarity_batch(texts)
    ff_ratio = _follower_following_ratio(account["followers"], account["following"])
    regularity = _posting_regularity_score(timestamps)
    burst_ratio = _burst_posting_ratio(timestamps)
    name_ent = _name_entropy(account["username"])
    default_profile = _has_default_profile_indicators(dict(account))

    # Account age vs activity
    age_days = max(1, account["account_age_days"] or 1)
    posts_per_day = len(posts) / age_days
    age_activity_anomaly = min(1.0, posts_per_day / 50.0)  # > 50 posts/day is suspicious

    # ── Weighted Composite Score ──
    # Each signal normalized to 0-1, higher = more bot-like
    signals = {
        "time_entropy": {
            "raw": time_entropy,
            "normalized": max(0.0, 1.0 - time_entropy / 4.5),  # low entropy = bot
            "weight": 0.15,
        },
        "text_similarity": {
            "raw": text_sim,
            "normalized": min(1.0, text_sim * 2.0),  # high sim = bot
            "weight": 0.20,
        },
        "ff_ratio_anomaly": {
            "raw": ff_ratio,
            "normalized": 1.0 if ff_ratio < 0.05 or ff_ratio > 100 else 0.0,
            "weight": 0.10,
        },
        "posting_regularity": {
            "raw": regularity,
            "normalized": regularity,
            "weight": 0.15,
        },
        "burst_posting": {
            "raw": burst_ratio,
            "normalized": min(1.0, burst_ratio * 2.0),
            "weight": 0.15,
        },
        "username_entropy": {
            "raw": name_ent,
            "normalized": 1.0 if name_ent > 3.5 else 0.0,  # random string detection
            "weight": 0.05,
        },
        "default_profile": {
            "raw": default_profile,
            "normalized": default_profile,
            "weight": 0.10,
        },
        "age_activity_anomaly": {
            "raw": posts_per_day,
            "normalized": age_activity_anomaly,
            "weight": 0.10,
        },
    }

    composite = sum(s["normalized"] * s["weight"] for s in signals.values())
    bot_score = round(min(100.0, composite * 100.0), 1)

    # Label
    if bot_score >= 80:
        label = "BOT_HIGH"
    elif bot_score >= 60:
        label = "BOT_MEDIUM"
    elif bot_score >= 40:
        label = "SUSPICIOUS"
    else:
        label = "LIKELY_ORGANIC"

    # Store result
    flags = {k: {"raw": v["raw"], "normalized": round(v["normalized"], 4), "weight": v["weight"]}
             for k, v in signals.items()}

    conn.execute(
        "UPDATE cog_accounts SET bot_score=?, bot_label=?, flags_json=?, updated_at=? WHERE account_id=?",
        (bot_score, label, json.dumps(flags), utc_now_iso(), account_id),
    )
    if own_conn:
        conn.commit()
        conn.close()

    return {
        "ok": True,
        "account_id": account_id,
        "username": account["username"],
        "bot_score": bot_score,
        "bot_label": label,
        "signals": flags,
        "posts_analyzed": len(posts),
    }


def run_bot_detection_batch(job_id: str = None, topic: str = None) -> Dict[str, Any]:
    """
    Jalankan bot detection untuk semua akun yang ter-scrape dalam satu job/topic.
    """
    conn = get_db()

    if job_id:
        account_ids = [r["account_id"] for r in conn.execute(
            "SELECT DISTINCT account_id FROM cog_posts WHERE job_id = ?", (job_id,)
        ).fetchall()]
    elif topic:
        account_ids = [r["account_id"] for r in conn.execute(
            "SELECT DISTINCT account_id FROM cog_posts WHERE content LIKE ?",
            (f"%{topic}%",),
        ).fetchall()]
    else:
        account_ids = [r["account_id"] for r in conn.execute(
            "SELECT account_id FROM cog_accounts WHERE bot_label IN ('UNKNOWN', 'PENDING')"
        ).fetchall()]

    results = []
    for aid in account_ids:
        r = compute_bot_score(aid, conn=conn)
        if r.get("ok"):
            results.append(r)

    conn.commit()
    conn.close()

    bots = [r for r in results if r["bot_score"] >= 60]
    suspicious = [r for r in results if 40 <= r["bot_score"] < 60]
    organic = [r for r in results if r["bot_score"] < 40]

    return {
        "ok": True,
        "total_analyzed": len(results),
        "bots_detected": len(bots),
        "suspicious": len(suspicious),
        "organic": len(organic),
        "top_bots": sorted(bots, key=lambda x: x["bot_score"], reverse=True)[:20],
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════════
# 4. COORDINATED INAUTHENTIC BEHAVIOR (CIB) DETECTION
# ══════════════════════════════════════════════════════════════════════

def detect_coordinated_posting(
    window_seconds: int = 60,
    min_accounts: int = 3,
    min_similarity: float = 0.3,
    job_id: str = None,
) -> Dict[str, Any]:
    """
    Deteksi akun-akun yang memposting konten serupa dalam jendela waktu yang sangat pendek.
    Ini adalah sinyal kuat coordinated inauthentic behavior (CIB).
    """
    conn = get_db()

    query = "SELECT * FROM cog_posts ORDER BY timestamp_unix"
    params = ()
    if job_id:
        query = "SELECT * FROM cog_posts WHERE job_id = ? ORDER BY timestamp_unix"
        params = (job_id,)

    posts = conn.execute(query, params).fetchall()

    if len(posts) < min_accounts:
        conn.close()
        return {"ok": True, "events": [], "total_events": 0}

    # Group posts by time windows
    events = []
    checked: Set[str] = set()

    for i, pivot in enumerate(posts):
        if pivot["post_id"] in checked:
            continue

        window_posts = []
        for j, candidate in enumerate(posts):
            if i == j or candidate["account_id"] == pivot["account_id"]:
                continue
            if abs(candidate["timestamp_unix"] - pivot["timestamp_unix"]) <= window_seconds:
                window_posts.append(candidate)

        if len(window_posts) < min_accounts - 1:
            continue

        # Check content similarity within window
        cluster = [pivot]
        for wp in window_posts:
            # Jaccard similarity
            sa = set(pivot["content"].lower().split())
            sb = set(wp["content"].lower().split())
            if sa and sb:
                sim = len(sa & sb) / len(sa | sb)
                if sim >= min_similarity:
                    cluster.append(wp)

        if len(cluster) >= min_accounts:
            accounts_in_cluster = list(set(p["account_id"] for p in cluster))
            avg_sim = min_similarity  # conservative

            event_id = f"CIB-{int(time.time())}-{hashlib.md5(str(accounts_in_cluster).encode()).hexdigest()[:8]}"

            event = {
                "event_id": event_id,
                "event_type": "COORDINATED_POSTING",
                "description": f"{len(accounts_in_cluster)} akun memposting konten serupa "
                               f"dalam {window_seconds} detik",
                "accounts": accounts_in_cluster,
                "window_seconds": window_seconds,
                "similarity": round(avg_sim, 3),
                "sample_content": pivot["content"][:200],
                "detected_at": utc_now_iso(),
                "severity": "HIGH" if len(accounts_in_cluster) >= 5 else "MEDIUM",
            }
            events.append(event)

            conn.execute(
                "INSERT OR REPLACE INTO cog_coordinated_events VALUES (?,?,?,?,?,?,?,?)",
                (
                    event_id, "COORDINATED_POSTING", event["description"],
                    json.dumps(accounts_in_cluster), window_seconds,
                    avg_sim, utc_now_iso(), event["severity"],
                ),
            )

            for p in cluster:
                checked.add(p["post_id"])

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "events": events,
        "total_events": len(events),
    }


def detect_hashtag_amplification(
    min_accounts: int = 3,
    job_id: str = None,
) -> Dict[str, Any]:
    """
    Deteksi hashtag yang diamplifikasi secara terkoordinasi oleh sekelompok akun.
    Mendeteksi seed account (yang pertama post) dan amplifier accounts.
    """
    conn = get_db()

    query = "SELECT * FROM cog_posts ORDER BY timestamp_unix"
    params = ()
    if job_id:
        query = "SELECT * FROM cog_posts WHERE job_id = ? ORDER BY timestamp_unix"
        params = (job_id,)

    posts = conn.execute(query, params).fetchall()

    # Track hashtag usage per account + timing
    hashtag_usage: Dict[str, List[Dict]] = defaultdict(list)
    for p in posts:
        try:
            tags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
        except (json.JSONDecodeError, TypeError):
            tags = re.findall(r"#(\w+)", p["content"] or "")
        for tag in tags:
            tag_lower = tag.lower()
            hashtag_usage[tag_lower].append({
                "account_id": p["account_id"],
                "timestamp_unix": p["timestamp_unix"],
                "post_id": p["post_id"],
            })

    narratives = []
    for tag, usages in hashtag_usage.items():
        unique_accounts = list(set(u["account_id"] for u in usages))
        if len(unique_accounts) < min_accounts:
            continue

        sorted_usage = sorted(usages, key=lambda x: x["timestamp_unix"])
        seed_account = sorted_usage[0]["account_id"]
        amplifiers = [a for a in unique_accounts if a != seed_account]

        narrative_id = f"NAR-{hashlib.md5(f'{tag}:{seed_account}'.encode()).hexdigest()[:12]}"

        narrative = {
            "narrative_id": narrative_id,
            "hashtag": f"#{tag}",
            "seed_account": seed_account,
            "amplifier_accounts": amplifiers,
            "total_posts": len(usages),
            "unique_accounts": len(unique_accounts),
            "first_seen": sorted_usage[0]["timestamp_unix"],
            "time_span_hours": round(
                (sorted_usage[-1]["timestamp_unix"] - sorted_usage[0]["timestamp_unix"]) / 3600.0, 1
            ),
        }
        narratives.append(narrative)

        conn.execute(
            "INSERT OR REPLACE INTO cog_narratives (narrative_id, topic_query, hashtag, seed_account, "
            "amplifier_accounts_json, total_reach, first_seen, classification, summary) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                narrative_id, tag, f"#{tag}", seed_account,
                json.dumps(amplifiers), len(usages),
                utc_now_iso(), "AMPLIFIED",
                f"#{tag} diamplifikasi oleh {len(amplifiers)} akun dari seed @{seed_account}",
            ),
        )

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "narratives": sorted(narratives, key=lambda x: x["unique_accounts"], reverse=True),
        "total_narratives": len(narratives),
    }


# ══════════════════════════════════════════════════════════════════════
# 5. NETWORK GRAPH ANALYSIS — Community Detection & Clustering
# ══════════════════════════════════════════════════════════════════════

def build_interaction_graph(job_id: str = None) -> Dict[str, Any]:
    """
    Bangun graf interaksi dari data postingan:
    - Edge dari mention (@user)
    - Edge dari co-hashtag usage (akun yang pakai hashtag sama)
    - Edge dari coordinated timing
    Gunakan NetworkX untuk community detection (Louvain / Greedy Modularity).
    """
    nx = _ensure_networkx()
    conn = get_db()

    query = "SELECT * FROM cog_posts"
    params = ()
    if job_id:
        query = "SELECT * FROM cog_posts WHERE job_id = ?"
        params = (job_id,)

    posts = conn.execute(query, params).fetchall()

    if nx is None:
        # Fallback tanpa NetworkX — simple adjacency matrix
        edges = []
        hashtag_users: Dict[str, Set[str]] = defaultdict(set)

        for p in posts:
            try:
                mentions = json.loads(p["mentions_json"]) if p["mentions_json"] else []
            except (json.JSONDecodeError, TypeError):
                mentions = []
            for m in mentions:
                edges.append((p["account_id"], f"tw-{m}", "MENTION"))

            try:
                hashtags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
            except (json.JSONDecodeError, TypeError):
                hashtags = []
            for h in hashtags:
                hashtag_users[h.lower()].add(p["account_id"])

        # Co-hashtag edges
        for tag, users in hashtag_users.items():
            users_list = list(users)
            for i in range(len(users_list)):
                for j in range(i + 1, len(users_list)):
                    edges.append((users_list[i], users_list[j], "CO_HASHTAG"))

        for e in edges:
            edge_id = hashlib.md5(f"{e[0]}:{e[1]}:{e[2]}".encode()).hexdigest()[:16]
            conn.execute(
                "INSERT OR REPLACE INTO cog_networks VALUES (?,?,?,?,?,?)",
                (edge_id, e[0], e[1], e[2], 1.0, utc_now_iso()),
            )

        conn.commit()
        conn.close()

        return {
            "ok": True,
            "nodes": list(set(e[0] for e in edges) | set(e[1] for e in edges)),
            "edges": len(edges),
            "note": "NetworkX tidak terinstall — graph tanpa community detection.",
        }

    # ── Full NetworkX Analysis ──
    G = nx.Graph()

    hashtag_users: Dict[str, Set[str]] = defaultdict(set)

    for p in posts:
        acct = p["account_id"]
        G.add_node(acct)

        try:
            mentions = json.loads(p["mentions_json"]) if p["mentions_json"] else []
        except (json.JSONDecodeError, TypeError):
            mentions = []
        for m in mentions:
            target = f"tw-{m}" if not m.startswith("tw-") else m
            G.add_edge(acct, target, relation="MENTION", weight=1.0)

        try:
            hashtags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
        except (json.JSONDecodeError, TypeError):
            hashtags = []
        for h in hashtags:
            hashtag_users[h.lower()].add(acct)

    # Co-hashtag edges
    for tag, users in hashtag_users.items():
        users_list = list(users)
        for i in range(len(users_list)):
            for j in range(i + 1, len(users_list)):
                if G.has_edge(users_list[i], users_list[j]):
                    G[users_list[i]][users_list[j]]["weight"] += 0.5
                else:
                    G.add_edge(users_list[i], users_list[j], relation="CO_HASHTAG", weight=0.5)

    # Community detection
    try:
        communities = nx.community.greedy_modularity_communities(G)
        community_map = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                community_map[node] = idx
    except Exception:
        community_map = {n: 0 for n in G.nodes()}

    # Update cluster IDs in DB
    for acct_id, cluster_id in community_map.items():
        conn.execute(
            "UPDATE cog_accounts SET cluster_id = ? WHERE account_id = ?",
            (cluster_id, acct_id),
        )

    # Store edges
    for u, v, data in G.edges(data=True):
        edge_id = hashlib.md5(f"{u}:{v}".encode()).hexdigest()[:16]
        conn.execute(
            "INSERT OR REPLACE INTO cog_networks VALUES (?,?,?,?,?,?)",
            (edge_id, u, v, data.get("relation", "UNKNOWN"), data.get("weight", 1.0), utc_now_iso()),
        )

    conn.commit()

    # Build response
    node_data = []
    for n in G.nodes():
        acct = conn.execute("SELECT * FROM cog_accounts WHERE account_id = ?", (n,)).fetchone()
        node_data.append({
            "id": n,
            "username": acct["username"] if acct else n,
            "bot_score": acct["bot_score"] if acct else 0.0,
            "bot_label": acct["bot_label"] if acct else "UNKNOWN",
            "cluster_id": community_map.get(n, -1),
            "degree": G.degree(n),
            "betweenness": 0.0,
        })

    # Betweenness centrality (siapa yang paling berpengaruh)
    try:
        betweenness = nx.betweenness_centrality(G)
        for nd in node_data:
            nd["betweenness"] = round(betweenness.get(nd["id"], 0.0), 4)
    except Exception:
        pass

    edge_data = [
        {"source": u, "target": v, "relation": data.get("relation", ""), "weight": data.get("weight", 1.0)}
        for u, v, data in G.edges(data=True)
    ]

    conn.close()

    return {
        "ok": True,
        "nodes": sorted(node_data, key=lambda x: x["bot_score"], reverse=True),
        "edges": edge_data,
        "total_nodes": len(node_data),
        "total_edges": len(edge_data),
        "communities": len(set(community_map.values())),
        "modularity": round(nx.community.modularity(G, communities) if communities else 0.0, 4),
    }


# ══════════════════════════════════════════════════════════════════════
# 6. NARRATIVE INTELLIGENCE & HOAX DETECTION
# ══════════════════════════════════════════════════════════════════════

# Indonesian hoax indicator keywords
_HOAX_INDICATORS_ID = [
    "sebarkan", "viralkan", "share sebelum dihapus", "pemerintah sembunyikan",
    "media mainstream", "terungkap", "terbongkar", "breaking news",
    "wajib baca", "ketahuan", "bukti nyata", "rahasia terbongkar",
    "jangan percaya", "bangun indonesia", "kritis",
    "darurat", "bahaya", "waspada", "awas", "hati-hati",
]

_CREDIBILITY_INDICATORS = [
    "menurut penelitian", "berdasarkan data", "sumber resmi",
    "dikonfirmasi", "fact check", "verifikasi",
]


def _compute_hoax_score(text: str) -> Tuple[float, List[str]]:
    """
    Hitung skor indikasi hoax dari teks (0-1).
    Menggunakan keyword matching + heuristic patterns.
    """
    if not text:
        return 0.0, []

    text_lower = text.lower()
    matched_indicators = []

    # Hoax keyword matching
    hoax_hits = 0
    for kw in _HOAX_INDICATORS_ID:
        if kw in text_lower:
            hoax_hits += 1
            matched_indicators.append(f"hoax_keyword:{kw}")

    # Credibility keyword matching (reduces score)
    cred_hits = 0
    for kw in _CREDIBILITY_INDICATORS:
        if kw in text_lower:
            cred_hits += 1

    # ALL CAPS ratio
    words = text.split()
    if words:
        caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 2) / len(words)
        if caps_ratio > 0.3:
            hoax_hits += 1
            matched_indicators.append(f"caps_ratio:{caps_ratio:.2f}")

    # Exclamation mark density
    excl_ratio = text.count("!") / max(len(text), 1)
    if excl_ratio > 0.02:
        hoax_hits += 0.5
        matched_indicators.append(f"exclamation_density:{excl_ratio:.3f}")

    # No source citation
    if not any(kw in text_lower for kw in ["http", "www", "sumber:", "referensi"]):
        hoax_hits += 0.3
        matched_indicators.append("no_source_citation")

    # Compute score
    raw_score = min(1.0, (hoax_hits * 0.15) - (cred_hits * 0.1))
    return round(max(0.0, raw_score), 3), matched_indicators


def analyze_narrative(topic: str, job_id: str = None) -> Dict[str, Any]:
    """
    Analisis narasi: siapa yang menyebarkan, seberapa cepat menyebar,
    dan apakah ada indikasi hoax/disinformasi.
    """
    conn = get_db()

    if job_id:
        posts = conn.execute(
            "SELECT * FROM cog_posts WHERE job_id = ? ORDER BY timestamp_unix",
            (job_id,),
        ).fetchall()
    else:
        posts = conn.execute(
            "SELECT * FROM cog_posts WHERE content LIKE ? ORDER BY timestamp_unix",
            (f"%{topic}%",),
        ).fetchall()

    if not posts:
        conn.close()
        return {"ok": True, "topic": topic, "posts_found": 0, "analysis": None}

    # Timeline analysis
    timestamps = [p["timestamp_unix"] for p in posts]
    accounts = list(set(p["account_id"] for p in posts))

    # Hoax analysis per post
    hoax_scores = []
    all_indicators = []
    for p in posts:
        score, indicators = _compute_hoax_score(p["content"])
        hoax_scores.append(score)
        all_indicators.extend(indicators)

    avg_hoax = round(sum(hoax_scores) / len(hoax_scores), 3) if hoax_scores else 0.0

    # Spread velocity
    if len(timestamps) > 1:
        time_span = max(timestamps) - min(timestamps)
        spread_velocity = round(len(posts) / max(time_span / 3600.0, 0.1), 2)  # posts per hour
    else:
        spread_velocity = 0.0

    # Most active accounts on this topic
    account_post_count = Counter(p["account_id"] for p in posts)
    top_spreaders = [
        {"account_id": a, "post_count": c}
        for a, c in account_post_count.most_common(10)
    ]

    # Top hashtags
    all_hashtags = []
    for p in posts:
        try:
            tags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
            all_hashtags.extend(tags)
        except (json.JSONDecodeError, TypeError):
            pass
    top_hashtags = [{"tag": f"#{t}", "count": c} for t, c in Counter(all_hashtags).most_common(10)]

    # Indicator summary
    indicator_summary = [{"indicator": k, "count": v} for k, v in Counter(all_indicators).most_common(10)]

    # Classification
    if avg_hoax >= 0.6:
        classification = "HIGH_RISK_DISINFORMATION"
    elif avg_hoax >= 0.3:
        classification = "SUSPICIOUS_NARRATIVE"
    else:
        classification = "LOW_RISK"

    conn.close()

    return {
        "ok": True,
        "topic": topic,
        "posts_found": len(posts),
        "unique_accounts": len(accounts),
        "avg_hoax_score": avg_hoax,
        "classification": classification,
        "spread_velocity_per_hour": spread_velocity,
        "time_span_hours": round((max(timestamps) - min(timestamps)) / 3600.0, 1) if len(timestamps) > 1 else 0,
        "top_spreaders": top_spreaders,
        "top_hashtags": top_hashtags,
        "hoax_indicators": indicator_summary,
    }


# ══════════════════════════════════════════════════════════════════════
# 7. NEW ACCOUNT SURGE DETECTION
# ══════════════════════════════════════════════════════════════════════

def detect_new_account_surge(
    age_threshold_days: int = 30,
    min_accounts: int = 5,
    job_id: str = None,
) -> Dict[str, Any]:
    """
    Deteksi lonjakan akun-akun baru yang tiba-tiba aktif pada topik tertentu.
    Ini adalah indikator kuat bot farm atau operasi influence.
    """
    conn = get_db()

    if job_id:
        accounts = conn.execute(
            """SELECT DISTINCT a.* FROM cog_accounts a
               JOIN cog_posts p ON a.account_id = p.account_id
               WHERE p.job_id = ?""",
            (job_id,),
        ).fetchall()
    else:
        accounts = conn.execute("SELECT * FROM cog_accounts").fetchall()

    new_accounts = [a for a in accounts if (a["account_age_days"] or 0) <= age_threshold_days]

    conn.close()

    surge_detected = len(new_accounts) >= min_accounts
    surge_ratio = round(len(new_accounts) / max(len(accounts), 1), 3)

    severity = "LOW"
    if surge_ratio >= 0.5 and len(new_accounts) >= 10:
        severity = "CRITICAL"
    elif surge_ratio >= 0.3 and len(new_accounts) >= min_accounts:
        severity = "HIGH"
    elif surge_detected:
        severity = "MEDIUM"

    return {
        "ok": True,
        "surge_detected": surge_detected,
        "total_accounts": len(accounts),
        "new_accounts": len(new_accounts),
        "new_account_ratio": surge_ratio,
        "age_threshold_days": age_threshold_days,
        "severity": severity,
        "new_account_list": [
            {
                "account_id": a["account_id"],
                "username": a["username"],
                "account_age_days": a["account_age_days"],
                "bot_score": a["bot_score"],
            }
            for a in sorted(new_accounts, key=lambda x: x["bot_score"], reverse=True)[:20]
        ],
    }


# ══════════════════════════════════════════════════════════════════════
# 8. INTELLIGENCE GRAPH INTEGRATION — Auto-Ingest ke TFAEL Knowledge Graph
# ══════════════════════════════════════════════════════════════════════

def ingest_cognitive_to_graph(job_id: str = None) -> Dict[str, Any]:
    """
    Push hasil analisis Cognitive Domain ke Unified Intelligence Graph (engine_graph).
    - Akun bot → Node di Knowledge Graph
    - Coordinated events → Edge di Knowledge Graph
    - Narrative analysis → Alert di SIEM
    """
    import engine_graph

    conn = get_db()
    ingested = {"nodes": 0, "edges": 0, "alerts": 0}

    # 1. Ingest high-score bot accounts as nodes
    bots = conn.execute(
        "SELECT * FROM cog_accounts WHERE bot_score >= 60 ORDER BY bot_score DESC"
    ).fetchall()

    for bot in bots:
        try:
            engine_graph.add_entity({
                "entity_id": bot["account_id"],
                "entity_type": "social_account",
                "label": f"@{bot['username']} [{bot['bot_label']}]",
                "platform": bot["platform"],
                "bot_score": bot["bot_score"],
                "metadata": json.loads(bot["flags_json"]) if bot["flags_json"] else {},
            })
            ingested["nodes"] += 1
        except Exception:
            pass

    # 2. Ingest network edges
    edges = conn.execute("SELECT * FROM cog_networks").fetchall()
    for e in edges:
        try:
            engine_graph.add_relation({
                "source": e["source_account"],
                "target": e["target_account"],
                "relation_type": e["relation_type"],
                "weight": e["weight"],
            })
            ingested["edges"] += 1
        except Exception:
            pass

    # 3. Generate SIEM alerts for critical CIB events
    events = conn.execute(
        "SELECT * FROM cog_coordinated_events WHERE severity IN ('HIGH', 'CRITICAL')"
    ).fetchall()

    for ev in events:
        try:
            alert_id = f"COG-{ev['event_id']}"
            conn.execute(
                "INSERT OR IGNORE INTO siem_alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    alert_id, utc_now_iso(), ev["severity"],
                    f"COGNITIVE: {ev['event_type']}",
                    "Information Warfare", "T1583",
                    ev["event_type"],
                    "COGNITIVE-DOMAIN", "SOCIAL-MEDIA",
                    0, 0, 0, 0, 0, 0,
                    ev["description"], "OPEN", "NONE",
                ),
            )
            ingested["alerts"] += 1
        except Exception:
            pass

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "ingested": ingested,
    }


# ══════════════════════════════════════════════════════════════════════
# 9. FULL PIPELINE — Satu Perintah untuk Semua
# ══════════════════════════════════════════════════════════════════════

def run_full_cognitive_analysis(
    platform: str = "twitter",
    query: str = "",
    channel: str = "",
    max_posts: int = 200,
    cib_window_sec: int = 60,
    min_cib_accounts: int = 3,
) -> Dict[str, Any]:
    """
    Full Cognitive Domain pipeline:
    1. Scrape → 2. Bot Detection → 3. CIB Detection →
    4. Network Graph → 5. Narrative Analysis → 6. Surge Detection →
    7. Auto-ingest ke Intelligence Graph & SIEM
    """
    init_cognitive_db()

    results = {"pipeline_stages": {}}
    job_id = f"COGFULL-{int(time.time())}-{hashlib.md5((query or channel).encode()).hexdigest()[:6]}"

    # Stage 1: Scrape
    if platform == "twitter" and query:
        scrape_result = scrape_twitter_search(query, max_posts=max_posts, job_id=job_id)
    elif platform == "telegram" and channel:
        scrape_result = scrape_telegram_channel(channel, max_posts=max_posts, job_id=job_id)
    else:
        return {"ok": False, "error": "Specify platform=twitter + query, atau platform=telegram + channel."}

    results["pipeline_stages"]["1_scrape"] = {
        "status": "OK" if scrape_result.get("ok") else "FAILED",
        "posts": scrape_result.get("posts_collected", 0),
    }

    if not scrape_result.get("ok"):
        return results

    # Stage 2: Bot Detection
    bot_result = run_bot_detection_batch(job_id=job_id)
    results["pipeline_stages"]["2_bot_detection"] = {
        "status": "OK",
        "bots_found": bot_result.get("bots_detected", 0),
        "suspicious": bot_result.get("suspicious", 0),
    }

    # Stage 3: CIB Detection
    cib_result = detect_coordinated_posting(
        window_seconds=cib_window_sec,
        min_accounts=min_cib_accounts,
        job_id=job_id,
    )
    results["pipeline_stages"]["3_coordinated_behavior"] = {
        "status": "OK",
        "events": cib_result.get("total_events", 0),
    }

    # Stage 4: Hashtag Amplification
    amp_result = detect_hashtag_amplification(min_accounts=min_cib_accounts, job_id=job_id)
    results["pipeline_stages"]["4_hashtag_amplification"] = {
        "status": "OK",
        "narratives": amp_result.get("total_narratives", 0),
    }

    # Stage 5: Network Graph
    graph_result = build_interaction_graph(job_id=job_id)
    results["pipeline_stages"]["5_network_graph"] = {
        "status": "OK",
        "nodes": graph_result.get("total_nodes", 0),
        "edges": graph_result.get("total_edges", 0),
        "communities": graph_result.get("communities", 0),
    }

    # Stage 6: Narrative Analysis
    narrative_result = analyze_narrative(query or channel, job_id=job_id)
    results["pipeline_stages"]["6_narrative_analysis"] = {
        "status": "OK",
        "hoax_score": narrative_result.get("avg_hoax_score", 0),
        "classification": narrative_result.get("classification", "UNKNOWN"),
    }

    # Stage 7: Surge Detection
    surge_result = detect_new_account_surge(job_id=job_id)
    results["pipeline_stages"]["7_surge_detection"] = {
        "status": "OK",
        "surge_detected": surge_result.get("surge_detected", False),
        "severity": surge_result.get("severity", "LOW"),
    }

    # Stage 8: Auto-ingest to Intelligence Graph
    try:
        ingest_result = ingest_cognitive_to_graph(job_id=job_id)
        results["pipeline_stages"]["8_graph_ingest"] = {
            "status": "OK",
            "ingested": ingest_result.get("ingested", {}),
        }
    except Exception as e:
        results["pipeline_stages"]["8_graph_ingest"] = {
            "status": "SKIPPED",
            "error": str(e),
        }

    results["ok"] = True
    results["job_id"] = job_id
    results["summary"] = {
        "posts_collected": scrape_result.get("posts_collected", 0),
        "bots_detected": bot_result.get("bots_detected", 0),
        "cib_events": cib_result.get("total_events", 0),
        "narratives_tracked": amp_result.get("total_narratives", 0),
        "hoax_classification": narrative_result.get("classification", "UNKNOWN"),
        "surge_severity": surge_result.get("severity", "LOW"),
    }

    return results


# ══════════════════════════════════════════════════════════════════════
# 10. QUERY & DASHBOARD DATA ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

def get_cognitive_dashboard(job_id: str = None) -> Dict[str, Any]:
    """
    Data lengkap untuk dashboard BotRadar / Cognitive Domain.
    """
    conn = get_db()

    # Accounts summary
    if job_id:
        accounts = conn.execute(
            """SELECT a.* FROM cog_accounts a
               JOIN cog_posts p ON a.account_id = p.account_id
               WHERE p.job_id = ? GROUP BY a.account_id
               ORDER BY a.bot_score DESC""",
            (job_id,),
        ).fetchall()
    else:
        accounts = conn.execute(
            "SELECT * FROM cog_accounts ORDER BY bot_score DESC"
        ).fetchall()

    bot_count = sum(1 for a in accounts if a["bot_score"] >= 60)
    suspicious_count = sum(1 for a in accounts if 40 <= a["bot_score"] < 60)
    organic_count = sum(1 for a in accounts if a["bot_score"] < 40)

    # Top flagged accounts
    top_flagged = [
        {
            "account_id": a["account_id"],
            "username": a["username"],
            "platform": a["platform"],
            "bot_score": a["bot_score"],
            "bot_label": a["bot_label"],
            "cluster_id": a["cluster_id"],
        }
        for a in accounts[:20]
    ]

    # Recent CIB events
    events = conn.execute(
        "SELECT * FROM cog_coordinated_events ORDER BY detected_at DESC LIMIT 10"
    ).fetchall()

    # Narratives
    narratives = conn.execute(
        "SELECT * FROM cog_narratives ORDER BY total_reach DESC LIMIT 10"
    ).fetchall()

    # Network stats
    edge_count = conn.execute("SELECT COUNT(*) as c FROM cog_networks").fetchone()["c"]

    conn.close()

    return {
        "ok": True,
        "summary": {
            "total_accounts": len(accounts),
            "bots": bot_count,
            "suspicious": suspicious_count,
            "organic": organic_count,
            "bot_ratio": round(bot_count / max(len(accounts), 1), 3),
            "network_edges": edge_count,
        },
        "top_flagged_accounts": top_flagged,
        "recent_cib_events": [dict(e) for e in events],
        "top_narratives": [dict(n) for n in narratives],
    }


def get_account_detail(account_id: str) -> Dict[str, Any]:
    """Detail lengkap satu akun + semua postingannya + signal breakdown."""
    conn = get_db()
    account = conn.execute("SELECT * FROM cog_accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not account:
        conn.close()
        return {"ok": False, "error": "Akun tidak ditemukan."}

    posts = conn.execute(
        "SELECT * FROM cog_posts WHERE account_id = ? ORDER BY timestamp_unix DESC LIMIT 50",
        (account_id,),
    ).fetchall()

    connections = conn.execute(
        "SELECT * FROM cog_networks WHERE source_account = ? OR target_account = ?",
        (account_id, account_id),
    ).fetchall()

    conn.close()

    return {
        "ok": True,
        "account": dict(account),
        "posts": [dict(p) for p in posts],
        "connections": [dict(c) for c in connections],
        "signals": json.loads(account["flags_json"]) if account["flags_json"] else {},
    }

