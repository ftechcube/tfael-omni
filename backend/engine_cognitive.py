#!/usr/bin/env python3
"""
TFAEL-OMNI v2.1 — Pilar 7: Cognitive Domain / BotRadar Engine
ADVERSARIAL-HARDENED REWRITE

Perubahan dari v2.0:
- Scraper: multi-source fallback, real timestamp extraction, health checks
- Bot Scoring: adversarial-resistant signals, ensemble + anomaly detection
- CIB Detection: MinHash similarity, time-bucket indexing, adaptive windows
- Hoax Detection: structural analysis, bukan cuma keyword matching
- Error Handling: fail loud, degradation tracking, operator alerting
- Anti-Gaming: sinyal yang susah di-fake oleh bot farm operator

100% On-Premise / Air-Gapped Ready (scraping bisa dimatikan via OMNI_AIRGAP).
"""

import concurrent.futures
import hashlib
import json
import logging
import math
import os
import random
import re
import sqlite3
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from engine_core import get_db, utc_now_iso, DB_PATH

# ── Logging: no silent failures ──
_log = logging.getLogger("tfael.cognitive")
if not _log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter(
        "[%(asctime)s] COGNITIVE %(levelname)s: %(message)s", "%Y-%m-%dT%H:%M:%S"
    ))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)

# ── Lazy imports ──
_nx = None


def _ensure_networkx():
    global _nx
    if _nx is None:
        try:
            import networkx as nx
            _nx = nx
        except ImportError:
            _log.warning("NetworkX not installed — graph analysis degraded")
            _nx = False  # False = tried and failed, None = not tried
    return _nx if _nx is not False else None


# ══════════════════════════════════════════════════════════════════════
# 0. DEGRADATION TRACKER — Operator Knows What's Broken
# ══════════════════════════════════════════════════════════════════════

class _SystemHealth:
    """
    Track apa yang jalan dan apa yang degraded.
    Setiap fungsi register status-nya. Dashboard bisa query ini.
    Operator HARUS tau kalau ada yang gak bener.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._status: Dict[str, Dict] = {}
        self._failure_count: Dict[str, int] = defaultdict(int)

    def ok(self, component: str, detail: str = ""):
        with self._lock:
            self._status[component] = {
                "status": "OPERATIONAL", "detail": detail,
                "ts": utc_now_iso(), "failures": self._failure_count[component],
            }

    def degraded(self, component: str, reason: str):
        with self._lock:
            self._failure_count[component] += 1
            self._status[component] = {
                "status": "DEGRADED", "detail": reason,
                "ts": utc_now_iso(), "failures": self._failure_count[component],
            }
        _log.warning("DEGRADED %s: %s", component, reason)

    def dead(self, component: str, reason: str):
        with self._lock:
            self._failure_count[component] += 1
            self._status[component] = {
                "status": "DEAD", "detail": reason,
                "ts": utc_now_iso(), "failures": self._failure_count[component],
            }
        _log.error("DEAD %s: %s", component, reason)

    def report(self) -> Dict[str, Any]:
        with self._lock:
            dead = [k for k, v in self._status.items() if v["status"] == "DEAD"]
            degraded = [k for k, v in self._status.items() if v["status"] == "DEGRADED"]
            return {
                "overall": "DEAD" if dead else ("DEGRADED" if degraded else "OPERATIONAL"),
                "dead_components": dead,
                "degraded_components": degraded,
                "components": dict(self._status),
            }


HEALTH = _SystemHealth()


# ══════════════════════════════════════════════════════════════════════
# 0b. DATABASE SCHEMA — Extended for Adversarial Resistance
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
    error           TEXT,
    source_method   TEXT DEFAULT 'unknown',
    health_note     TEXT
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
    bot_label       TEXT DEFAULT 'UNSCORED',
    bot_confidence  REAL DEFAULT 0.0,
    cluster_id      INTEGER DEFAULT -1,
    flags_json      TEXT,
    first_seen      TEXT,
    updated_at      TEXT,
    fingerprint     TEXT DEFAULT '',
    score_version   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cog_posts (
    post_id         TEXT PRIMARY KEY,
    account_id      TEXT,
    platform        TEXT,
    content         TEXT,
    timestamp       TEXT,
    timestamp_unix  INTEGER,
    ts_confidence   TEXT DEFAULT 'unknown',
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
    job_id          TEXT,
    content_hash    TEXT DEFAULT '',
    minhash_sig     TEXT DEFAULT ''
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
    severity        TEXT DEFAULT 'MEDIUM',
    evidence_json   TEXT DEFAULT '{}'
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
    hoax_evidence   TEXT DEFAULT '{}',
    summary         TEXT
);

"""


def init_cognitive_db():
    conn = get_db()
    # Create tables first (IF NOT EXISTS won't touch existing tables)
    conn.executescript(COGNITIVE_SCHEMA)

    # ── Migrate existing tables: add new columns if missing ──
    _migrations = [
        # (table, column, definition)
        ("cog_scrape_jobs", "source_method", "TEXT DEFAULT 'unknown'"),
        ("cog_scrape_jobs", "health_note", "TEXT"),
        ("cog_accounts", "bot_confidence", "REAL DEFAULT 0.0"),
        ("cog_accounts", "fingerprint", "TEXT DEFAULT ''"),
        ("cog_accounts", "score_version", "INTEGER DEFAULT 0"),
        ("cog_posts", "ts_confidence", "TEXT DEFAULT 'unknown'"),
        ("cog_posts", "content_hash", "TEXT DEFAULT ''"),
        ("cog_posts", "minhash_sig", "TEXT DEFAULT ''"),
        ("cog_coordinated_events", "evidence_json", "TEXT DEFAULT '{}'"),
        ("cog_narratives", "hoax_evidence", "TEXT DEFAULT '{}'"),
    ]

    for table, column, definition in _migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass  # Column already exists — expected

    # Now create indexes (safe because columns exist)
    _indexes = [
        "CREATE INDEX IF NOT EXISTS idx_posts_job ON cog_posts(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_posts_account ON cog_posts(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_posts_ts ON cog_posts(timestamp_unix)",
        "CREATE INDEX IF NOT EXISTS idx_posts_hash ON cog_posts(content_hash)",
        "CREATE INDEX IF NOT EXISTS idx_accounts_score ON cog_accounts(bot_score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_networks_source ON cog_networks(source_account)",
        "CREATE INDEX IF NOT EXISTS idx_networks_target ON cog_networks(target_account)",
    ]
    for idx_sql in _indexes:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    HEALTH.ok("database", "cognitive tables initialized + migrated")

    # Auto-seed demo data if OMNI_DEMO=1 and no data exists
    if os.environ.get("OMNI_DEMO", "").strip() in ("1", "true"):
        try:
            result = seed_cognitive_demo()
            if result.get("seeded"):
                _log.info("Demo mode: cognitive data auto-seeded")
        except Exception as e:
            _log.warning("Demo seed failed (non-fatal): %s", e)


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

# Proxy pool
_PROXY_POOL: List[str] = []
_proxy_lock = threading.Lock()
_proxy_idx = 0


def load_proxy_pool(proxies: List[str] = None):
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
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate",
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
    delay = random.uniform(min_s, max_s)
    if random.random() < 0.15:
        delay += random.uniform(3.0, 8.0)
    time.sleep(delay)


def _stealth_fetch(url: str, timeout: int = 15, max_retries: int = 3) -> Optional[str]:
    """Fetch with anti-detection. Returns HTML/JSON or None."""
    last_error = None
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
            encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" in encoding:
                import gzip
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="ignore")

        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                _human_delay(2.0, 5.0)

    _log.warning("_stealth_fetch FAILED after %d retries: %s → %s", max_retries, url[:80], last_error)
    return None


# ══════════════════════════════════════════════════════════════════════
# 1b. SOURCE HEALTH CHECK — Know What's Alive Before Scraping
# ══════════════════════════════════════════════════════════════════════

_source_health: Dict[str, Dict] = {}
_source_health_lock = threading.Lock()


def _check_source_alive(url: str, tag: str) -> bool:
    """Probe apakah source masih hidup. Cache result 10 menit."""
    with _source_health_lock:
        cached = _source_health.get(tag)
        if cached and time.time() - cached["ts"] < 600:
            return cached["alive"]

    alive = False
    try:
        req = urllib.request.Request(url, headers=_stealth_headers())
        resp = urllib.request.urlopen(req, timeout=8)
        alive = resp.status < 400
    except Exception:
        pass

    with _source_health_lock:
        _source_health[tag] = {"alive": alive, "ts": time.time(), "url": url}

    if not alive:
        HEALTH.degraded(f"source:{tag}", f"unreachable: {url[:60]}")
    else:
        HEALTH.ok(f"source:{tag}")
    return alive


# ══════════════════════════════════════════════════════════════════════
# 2. CONTENT FINGERPRINTING — Anti-Evasion Core
# ══════════════════════════════════════════════════════════════════════

def _normalize_text(text: str) -> str:
    """
    Normalize text biar word-shuffle, emoji padding, leetspeak gak ngaruh.
    Ini yang bikin bot farm operator gak bisa dodge similarity check
    cuma dengan reorder kata atau tambahin emoji.
    """
    if not text:
        return ""
    t = text.lower()
    # Strip URLs
    t = re.sub(r"https?://\S+", "", t)
    # Strip mentions
    t = re.sub(r"@\w+", "", t)
    # Strip hashtags (keep the word)
    t = t.replace("#", "")
    # Strip emoji (unicode emoji ranges)
    t = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FEFF"
        r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF"
        r"\U0000200D\U00002640\U00002642]+", "", t
    )
    # Strip excessive punctuation
    t = re.sub(r"[!?.,;:\"'(){}\[\]]+", " ", t)
    # Normalize whitespace
    t = re.sub(r"\s+", " ", t).strip()
    # Sort words — makes word-shuffle useless
    words = sorted(t.split())
    return " ".join(words)


def _content_hash(text: str) -> str:
    """Semantic-resistant content hash. Same message in different order = same hash."""
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _minhash_signature(text: str, num_perm: int = 64) -> List[int]:
    """
    MinHash signature untuk LSH similarity.
    Jauh lebih robust dari Jaccard word-level karena:
    - Pakai character n-grams (3-grams), bukan whole words
    - Tahan terhadap word substitution dan reordering
    - O(1) comparison instead of O(n) set operations
    """
    normalized = _normalize_text(text)
    if len(normalized) < 3:
        return [0] * num_perm

    # Character 3-grams — tahan terhadap word-level evasion
    shingles = set()
    for i in range(len(normalized) - 2):
        shingles.add(normalized[i:i + 3])

    if not shingles:
        return [0] * num_perm

    signature = []
    for i in range(num_perm):
        min_hash = float("inf")
        # Each permutation uses different seed
        seed_a = (i * 1103515245 + 12345) & 0x7FFFFFFF
        seed_b = (i * 1664525 + 1013904223) & 0x7FFFFFFF
        for shingle in shingles:
            h = hash(shingle) & 0xFFFFFFFF
            perm_hash = ((seed_a * h + seed_b) & 0xFFFFFFFF)
            if perm_hash < min_hash:
                min_hash = perm_hash
        signature.append(min_hash)

    return signature


def _minhash_similarity(sig_a: List[int], sig_b: List[int]) -> float:
    """Estimasi Jaccard similarity dari MinHash signatures. O(k) bukan O(n)."""
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


# ══════════════════════════════════════════════════════════════════════
# 3. SOCIAL MEDIA SCRAPERS — Multi-Source with Real Timestamps
# ══════════════════════════════════════════════════════════════════════

# Twitter/X sources — operator can add custom instances via env
# OMNI_NITTER_INSTANCES="https://my-nitter.local,https://nitter.backup.org"
# OMNI_TWITTER_BEARER=<bearer token dari developer.twitter.com>
_TWITTER_BEARER = os.environ.get("OMNI_TWITTER_BEARER", "").strip()
_TWITTER_AUTH_TOKEN = os.environ.get("OMNI_TWITTER_AUTH_TOKEN", "").strip()
_TWITTER_CT0 = os.environ.get("OMNI_TWITTER_CT0", "").strip()

def _build_twitter_sources() -> List[Dict[str, str]]:
    sources = []

    # 0. Twitter API v2 — highest priority, paling reliable
    if _TWITTER_BEARER:
        sources.append({"type": "twitter_api_v2", "url": "https://api.twitter.com", "tag": "twitter-api-v2"})

    # 0b. Cookie-based GraphQL — pakai cookie browser, zero API key
    if _TWITTER_AUTH_TOKEN and _TWITTER_CT0:
        sources.append({"type": "twitter_cookie", "url": "https://x.com", "tag": "twitter-cookie"})

    # 1. Operator-configured Nitter instances
    custom = os.environ.get("OMNI_NITTER_INSTANCES", "").strip()
    if custom:
        for i, url in enumerate(custom.split(",")):
            url = url.strip().rstrip("/")
            if url:
                sources.append({"type": "nitter", "url": url, "tag": f"nitter-custom-{i}"})

    # 2. Known public instances (most are dead as of 2026 — kept as fallback)
    sources.extend([
        {"type": "nitter", "url": "https://nitter.privacydev.net", "tag": "nitter-privacy"},
        {"type": "nitter", "url": "https://nitter.poast.org", "tag": "nitter-poast"},
        {"type": "nitter", "url": "https://nitter.cz", "tag": "nitter-cz"},
        {"type": "nitter", "url": "https://xcancel.com", "tag": "xcancel"},
        {"type": "nitter", "url": "https://nitter.woodland.cafe", "tag": "nitter-woodland"},
        {"type": "nitter", "url": "https://n.opnxng.com", "tag": "nitter-opnxng"},
        {"type": "nitter", "url": "https://bird.habedieeh.re", "tag": "nitter-bird"},
        {"type": "nitter", "url": "https://nitter.1d4.us", "tag": "nitter-1d4"},
    ])

    return sources

_TWITTER_SOURCES = _build_twitter_sources()


def _twitter_api_v2_search(query: str, max_results: int = 100) -> List[Dict[str, Any]]:
    """Search tweets via Twitter API v2 Recent Search endpoint."""
    if not _TWITTER_BEARER:
        return []

    max_results = min(max_results, 100)
    params = urllib.parse.urlencode({
        "query": query,
        "max_results": max_results,
        "tweet.fields": "created_at,public_metrics,author_id,entities",
        "user.fields": "username,name,public_metrics,created_at,description",
        "expansions": "author_id",
    })
    url = f"https://api.twitter.com/2/tweets/search/recent?{params}"

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {_TWITTER_BEARER}",
        "User-Agent": "TFAEL-OMNI/2.1",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _log.warning("Twitter API v2 search failed: %s", e)
        HEALTH.degraded("source:twitter-api-v2", str(e))
        return []

    if "data" not in data:
        return []

    users_map = {}
    for u in data.get("includes", {}).get("users", []):
        users_map[u["id"]] = u

    results = []
    for tweet in data["data"]:
        author = users_map.get(tweet.get("author_id"), {})
        username = author.get("username", f"uid_{tweet.get('author_id', 'unknown')}")
        metrics = tweet.get("public_metrics", {})

        ts_unix, ts_conf = _parse_timestamp_robust(tweet.get("created_at", ""))

        entities = tweet.get("entities", {})
        hashtags = [h["tag"] for h in entities.get("hashtags", [])]
        mentions = [m["username"] for m in entities.get("mentions", [])]
        urls = [u["expanded_url"] for u in entities.get("urls", []) if "expanded_url" in u]

        content = tweet.get("text", "")
        c_hash = _content_hash(content)
        mh_sig = _minhash_signature(content)

        results.append({
            "post_id": f"tw-{tweet['id']}",
            "account_id": f"tw-{username}",
            "platform": "twitter",
            "content": content,
            "timestamp": tweet.get("created_at", ""),
            "timestamp_unix": ts_unix,
            "ts_confidence": ts_conf,
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "hashtags": hashtags,
            "mentions": mentions,
            "urls": urls,
            "content_hash": c_hash,
            "minhash_sig": mh_sig,
            "_author": {
                "username": username,
                "display_name": author.get("name", username),
                "followers": author.get("public_metrics", {}).get("followers_count", 0),
                "following": author.get("public_metrics", {}).get("following_count", 0),
                "tweet_count": author.get("public_metrics", {}).get("tweet_count", 0),
                "created_at": author.get("created_at", ""),
                "bio": author.get("description", ""),
            },
        })

    HEALTH.ok("source:twitter-api-v2")
    return results


_TWITTER_APP_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

_TWITTER_GQL_FEATURES = json.dumps({
    "rweb_video_screen_enabled": False,
    "rweb_cashtags_enabled": True,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_profile_redirect_enabled": True,
    "rweb_tipjar_consumption_enabled": False,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "rweb_cashtags_composer_attachment_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "rweb_sports_post_context_enabled": True,
    "x_elections_post_context_enabled": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "responsive_web_grok_annotations_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "rweb_conversational_replies_downvote_enabled": False,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "content_disclosure_indicator_enabled": True,
    "content_disclosure_ai_generated_indicator_enabled": True,
    "responsive_web_grok_show_grok_translated_post": True,
    "responsive_web_grok_analysis_button_from_backend": True,
    "post_ctas_fetch_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_nested_quote_preview_enabled": True,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": True,
    "responsive_web_made_on_x_label_enabled": False,
    "responsive_web_grok_community_note_auto_translation_is_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
})


def _twitter_cookie_search(query: str, max_results: int = 200) -> List[Dict[str, Any]]:
    """Search tweets via Twitter internal GraphQL API using browser cookies."""
    if not _TWITTER_AUTH_TOKEN or not _TWITTER_CT0:
        return []

    results = []
    cursor = None
    collected = 0

    while collected < max_results:
        variables = {
            "rawQuery": query,
            "count": min(max_results - collected, 20),
            "querySource": "typed_query",
            "product": "Top",
        }
        if cursor:
            variables["cursor"] = cursor

        params = urllib.parse.urlencode({
            "variables": json.dumps(variables),
            "features": _TWITTER_GQL_FEATURES,
        })

        url = f"https://x.com/i/api/graphql/vLHjqbDv7TPFMBkIIO1nOA/SearchTimeline?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {_TWITTER_APP_BEARER}",
            "Content-Type": "application/json",
            "X-Twitter-Active-User": "yes",
            "X-Twitter-Client-Language": "en",
            "X-Csrf-Token": _TWITTER_CT0,
            "X-Twitter-Auth-Type": "OAuth2Session",
            "Referer": "https://x.com/search",
            "Cookie": f"auth_token={_TWITTER_AUTH_TOKEN}; ct0={_TWITTER_CT0}; twid=u%3D2119645852876865536",
            "X-Twitter-Auth-Type": "OAuth2Session",
            "Referer": "https://x.com/search",
            "Cookie": f"auth_token={_TWITTER_AUTH_TOKEN}; ct0={_TWITTER_CT0}; twid=u%3D2119645852876865536",
            "X-Twitter-Auth-Type": "OAuth2Session",
            "Referer": "https://x.com/search",
            "Cookie": f"auth_token={_TWITTER_AUTH_TOKEN}; ct0={_TWITTER_CT0}; twid=u%3D2119645852876865536",
            "Cookie": f"auth_token={_TWITTER_AUTH_TOKEN}; ct0={_TWITTER_CT0}",
        })

        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _log.warning("Twitter cookie search rate-limited")
            else:
                _log.warning("Twitter cookie search HTTP %d", e.code)
            HEALTH.degraded("source:twitter-cookie", f"HTTP {e.code}")
            break
        except Exception as e:
            _log.warning("Twitter cookie search failed: %s", e)
            HEALTH.degraded("source:twitter-cookie", str(e))
            break

        instructions = (
            data.get("data", {})
                .get("search_by_raw_query", {})
                .get("search_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
        )

        new_cursor = None
        for instruction in instructions:
            if instruction.get("type") != "TimelineAddEntries":
                continue
            for entry in instruction.get("entries", []):
                entry_id = entry.get("entryId", "")
                if "cursor-bottom" in entry_id:
                    new_cursor = (entry.get("content", {}).get("value")
                                  or entry.get("content", {}).get("itemContent", {}).get("value"))
                    continue

                tweet = _parse_gql_tweet_entry(entry)
                if tweet:
                    results.append(tweet)
                    collected += 1
                    if collected >= max_results:
                        break

        if not new_cursor or new_cursor == cursor:
            break
        cursor = new_cursor
        _human_delay(1.0, 3.0)

    if results:
        HEALTH.ok("source:twitter-cookie")
    return results


def _parse_gql_tweet_entry(entry: dict) -> Optional[Dict[str, Any]]:
    """Parse a single tweet entry from Twitter GraphQL response."""
    try:
        result = (
            entry.get("content", {})
                 .get("itemContent", {})
                 .get("tweet_results", {})
                 .get("result", {})
        )
        if not result:
            return None

        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet", result)

        legacy = result.get("legacy", {})
        user_result = result.get("core", {}).get("user_results", {}).get("result", {})
        user_legacy = user_result.get("legacy", {})

        if not legacy or not user_legacy:
            return None

        username = user_legacy.get("screen_name", "")
        if not username:
            return None

        content = legacy.get("full_text", "")
        if not content:
            return None

        tweet_id = legacy.get("id_str", "")

        raw_ts = legacy.get("created_at", "")
        # Twitter legacy format: "Mon Nov 15 03:42:00 +0000 2024"
        ts_unix, ts_conf = 0, "failed"
        if raw_ts:
            try:
                dt = datetime.strptime(raw_ts, "%a %b %d %H:%M:%S %z %Y")
                ts_unix = int(dt.timestamp())
                ts_conf = "exact"
                raw_ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                ts_unix, ts_conf = _parse_timestamp_robust(raw_ts)

        hashtags = [h.get("text", "") for h in legacy.get("entities", {}).get("hashtags", [])]
        mentions = [m.get("screen_name", "") for m in legacy.get("entities", {}).get("user_mentions", [])]
        urls_found = [u.get("expanded_url", "") for u in legacy.get("entities", {}).get("urls", []) if u.get("expanded_url")]

        c_hash = _content_hash(content)
        mh_sig = _minhash_signature(content)

        post_id = f"tw-{tweet_id}" if tweet_id else f"tw-{hashlib.md5(f'{username}:{c_hash}'.encode()).hexdigest()[:16]}"

        followers = user_legacy.get("followers_count", 0)
        following = user_legacy.get("friends_count", 0)
        tweet_count = user_legacy.get("statuses_count", 0)
        bio = user_legacy.get("description", "")
        acct_created = user_legacy.get("created_at", "")

        return {
            "post_id": post_id,
            "account_id": f"tw-{username}",
            "platform": "twitter",
            "content": content,
            "timestamp": raw_ts,
            "timestamp_unix": ts_unix,
            "ts_confidence": ts_conf,
            "likes": legacy.get("favorite_count", 0),
            "retweets": legacy.get("retweet_count", 0),
            "replies": legacy.get("reply_count", 0),
            "hashtags": hashtags,
            "mentions": mentions,
            "urls": urls_found,
            "content_hash": c_hash,
            "minhash_sig": mh_sig,
            "_author": {
                "username": username,
                "display_name": user_legacy.get("name", username),
                "followers": followers,
                "following": following,
                "tweet_count": tweet_count,
                "created_at": acct_created,
                "bio": bio,
            },
        }
    except Exception:
        return None


def _parse_timestamp_robust(raw: str) -> Tuple[int, str]:
    """
    Parse timestamp dari berbagai format. Return (unix_ts, confidence).
    NEVER fake timestamps. Kalau gak bisa parse, return (0, "failed").
    """
    if not raw:
        return 0, "missing"

    # ISO 8601
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp()), "exact"
        except ValueError:
            continue

    # Nitter / Twitter display format: "Nov 15, 2024 · 3:42 PM UTC"
    for fmt in [
        "%b %d, %Y · %I:%M %p UTC",
        "%b %d, %Y · %H:%M UTC",
        "%d %b %Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp()), "parsed"
        except ValueError:
            continue

    # Relative time: "2h", "3d", "5m"
    rel = re.match(r"(\d+)\s*([smhdwMy])", raw.strip())
    if rel:
        n, unit = int(rel.group(1)), rel.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        if unit in multipliers:
            ts = int(time.time()) - n * multipliers[unit]
            return ts, "relative"

    # Unix timestamp langsung
    try:
        val = int(raw.strip())
        if 1000000000 < val < 2000000000:
            return val, "unix"
        if val > 2000000000:  # milliseconds
            return val // 1000, "unix_ms"
    except (ValueError, TypeError):
        pass

    _log.debug("timestamp parse failed: %r", raw[:50])
    return 0, "failed"


def scrape_twitter_search(query: str, max_posts: int = 200, job_id: str = None) -> Dict[str, Any]:
    """
    Scrape Twitter/X search — multi-source fallback.
    Tries each source in order, tracks which one actually worked.
    """
    if os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true"):
        return {"ok": False, "error": "Air-gap mode: online scraping disabled."}

    if not job_id:
        job_id = f"TWX-{int(time.time())}-{hashlib.md5(query.encode()).hexdigest()[:8]}"

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO cog_scrape_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, "twitter", query, "RUNNING", 0, 0, utc_now_iso(), None, None, "unknown", None),
    )
    conn.commit()

    posts = []
    accounts_seen: Dict[str, Dict] = {}
    source_used = "none"
    ts_stats = {"exact": 0, "parsed": 0, "relative": 0, "failed": 0}

    encoded_q = urllib.parse.quote(query)

    # Try each source until we get results
    for source in _TWITTER_SOURCES:
        if len(posts) >= max_posts:
            break

        if source["type"] == "twitter_api_v2":
            api_results = _twitter_api_v2_search(query, max_results=min(max_posts, 100))
            if api_results:
                source_used = source["tag"]
                for r in api_results:
                    if len(posts) >= max_posts:
                        break
                    posts.append(r)
                    acct_id = r["account_id"]
                    if acct_id not in accounts_seen:
                        author = r.get("_author", {})
                        accounts_seen[acct_id] = {
                            "account_id": acct_id, "platform": "twitter",
                            "username": author.get("username", acct_id.replace("tw-", "")),
                            "display_name": author.get("display_name", ""),
                            "bio": author.get("bio", ""),
                            "followers": author.get("followers", 0),
                            "following": author.get("following", 0),
                            "tweet_count": author.get("tweet_count", 0),
                            "created_at": author.get("created_at", ""),
                            "post_count": 0, "posts_in_query": [],
                        }
                    accounts_seen[acct_id]["post_count"] += 1
                    accounts_seen[acct_id]["posts_in_query"].append(r["post_id"])
                    ts_stats[r.get("ts_confidence", "exact")] = ts_stats.get(r.get("ts_confidence", "exact"), 0) + 1
                if posts:
                    break
            continue

        if source["type"] == "twitter_cookie":
            try:
                import subprocess as _sub, json as _json, urllib.parse as _up
                _auth = os.environ.get("OMNI_TWITTER_AUTH_TOKEN","")
                _ct0 = os.environ.get("OMNI_TWITTER_CT0","")
                _cf = os.environ.get("OMNI_TWITTER_CF_CLEARANCE","")
                if not _auth or not _ct0:
                    raise Exception("no cookie")
                _cookie_str = f"auth_token={_auth}; ct0={_ct0}; twid=u%3D2119645852876865536"
                if _cf:
                    _cookie_str += f"; cf_clearance={_cf}"
                _feats = {"rweb_video_screen_enabled":False,"rweb_cashtags_enabled":True,"profile_label_improvements_pcf_label_in_post_enabled":True,"responsive_web_profile_redirect_enabled":True,"rweb_tipjar_consumption_enabled":False,"verified_phone_label_enabled":False,"creator_subscriptions_tweet_preview_api_enabled":True,"responsive_web_graphql_timeline_navigation_enabled":True,"premium_content_api_read_enabled":False,"communities_web_enable_tweet_community_results_fetch":True,"c9s_tweet_anatomy_moderator_badge_enabled":True,"responsive_web_grok_analyze_button_fetch_trends_enabled":False,"responsive_web_grok_analyze_post_followups_enabled":True,"rweb_cashtags_composer_attachment_enabled":True,"responsive_web_jetfuel_frame":True,"rweb_sports_post_context_enabled":True,"x_elections_post_context_enabled":True,"responsive_web_grok_share_attachment_enabled":True,"responsive_web_grok_annotations_enabled":True,"articles_preview_enabled":True,"responsive_web_edit_tweet_api_enabled":True,"rweb_conversational_replies_downvote_enabled":False,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":True,"view_counts_everywhere_api_enabled":True,"longform_notetweets_consumption_enabled":True,"responsive_web_twitter_article_tweet_consumption_enabled":True,"content_disclosure_indicator_enabled":True,"content_disclosure_ai_generated_indicator_enabled":True,"responsive_web_grok_show_grok_translated_post":True,"responsive_web_grok_analysis_button_from_backend":True,"post_ctas_fetch_enabled":False,"freedom_of_speech_not_reach_fetch_enabled":True,"standardized_nudges_misinfo":True,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":True,"longform_notetweets_rich_text_read_enabled":True,"longform_notetweets_inline_media_enabled":False,"responsive_web_nested_quote_preview_enabled":True,"responsive_web_grok_image_annotation_enabled":True,"responsive_web_grok_imagine_annotation_enabled":True,"responsive_web_made_on_x_label_enabled":False,"responsive_web_grok_community_note_auto_translation_is_enabled":True,"responsive_web_enhance_cards_enabled":False}
                _vars = {"rawQuery":query,"count":min(max_posts-len(posts),20),"querySource":"typed_query","product":"Top","withGrokTranslatedBio":True,"withQuickPromoteEligibilityTweetFields":False}
                _url = f"https://x.com/i/api/graphql/vLHjqbDv7TPFMBkIIO1nOA/SearchTimeline?variables={_up.quote(_json.dumps(_vars))}&features={_up.quote(_json.dumps(_feats))}"
                _curl_cmd = ["curl","-s","--url",_url,
                    "-H","accept: */*",
                    "-H",f"authorization: Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                    "-H","content-type: application/json",
                    "-H",f"x-csrf-token: {_ct0}",
                    "-H","x-twitter-active-user: yes",
                    "-H","x-twitter-auth-type: OAuth2Session",
                    "-H","x-twitter-client-language: en",
                    "-H","user-agent: Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36",
                    "-H",f"referer: https://x.com/search?q={query}&src=typed_query",
                    "-H","sec-ch-ua-mobile: ?1",
                    "-H","sec-fetch-dest: empty",
                    "-H","sec-fetch-mode: cors",
                    "-H","sec-fetch-site: same-origin",
                    "-b", _cookie_str,
                ]
                _res = _sub.run(_curl_cmd, capture_output=True, text=True, timeout=20)
                if not _res.stdout or _res.stdout.strip() == "":
                    raise Exception("curl empty response")
                _data = _json.loads(_res.stdout)
                _instr = _data.get("data",{}).get("search_by_raw_query",{}).get("search_timeline",{}).get("timeline",{}).get("instructions",[])
                raw = []
                for _ins in _instr:
                    if _ins.get("type") != "TimelineAddEntries": continue
                    for _ent in _ins.get("entries",[]):
                        try:
                            _r2 = _ent.get("content",{}).get("itemContent",{}).get("tweet_results",{}).get("result",{})
                            if not _r2: continue
                            if _r2.get("__typename") == "TweetWithVisibilityResults": _r2 = _r2.get("tweet",_r2)
                            _leg = _r2.get("legacy",{})
                            _usr = _r2.get("core",{}).get("user_results",{}).get("result",{}).get("legacy",{})
                            if not _leg: continue
                            raw.append({"id":_leg.get("id_str"),"text":_leg.get("full_text",""),"username":_usr.get("screen_name",""),"name":_usr.get("name",""),"created_at":_leg.get("created_at",""),"retweet_count":_leg.get("retweet_count",0),"like_count":_leg.get("favorite_count",0),"reply_count":_leg.get("reply_count",0),"followers":_usr.get("followers_count",0),"url":f"https://x.com/{_usr.get('screen_name')}/status/{_leg.get('id_str')}","lang":_leg.get("lang",""),"is_retweet":"retweeted_status_id_str" in _leg})
                        except: pass
                _feats = {"rweb_video_screen_enabled":False,"rweb_cashtags_enabled":True,"profile_label_improvements_pcf_label_in_post_enabled":True,"responsive_web_profile_redirect_enabled":True,"rweb_tipjar_consumption_enabled":False,"verified_phone_label_enabled":False,"creator_subscriptions_tweet_preview_api_enabled":True,"responsive_web_graphql_timeline_navigation_enabled":True,"premium_content_api_read_enabled":False,"communities_web_enable_tweet_community_results_fetch":True,"c9s_tweet_anatomy_moderator_badge_enabled":True,"responsive_web_grok_analyze_button_fetch_trends_enabled":False,"responsive_web_grok_analyze_post_followups_enabled":True,"rweb_cashtags_composer_attachment_enabled":True,"responsive_web_jetfuel_frame":True,"rweb_sports_post_context_enabled":True,"x_elections_post_context_enabled":True,"responsive_web_grok_share_attachment_enabled":True,"responsive_web_grok_annotations_enabled":True,"articles_preview_enabled":True,"responsive_web_edit_tweet_api_enabled":True,"rweb_conversational_replies_downvote_enabled":False,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":True,"view_counts_everywhere_api_enabled":True,"longform_notetweets_consumption_enabled":True,"responsive_web_twitter_article_tweet_consumption_enabled":True,"content_disclosure_indicator_enabled":True,"content_disclosure_ai_generated_indicator_enabled":True,"responsive_web_grok_show_grok_translated_post":True,"responsive_web_grok_analysis_button_from_backend":True,"post_ctas_fetch_enabled":False,"freedom_of_speech_not_reach_fetch_enabled":True,"standardized_nudges_misinfo":True,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":True,"longform_notetweets_rich_text_read_enabled":True,"longform_notetweets_inline_media_enabled":False,"responsive_web_nested_quote_preview_enabled":True,"responsive_web_grok_image_annotation_enabled":True,"responsive_web_grok_imagine_annotation_enabled":True,"responsive_web_made_on_x_label_enabled":False,"responsive_web_grok_community_note_auto_translation_is_enabled":True,"responsive_web_enhance_cards_enabled":False}
                _vars = {"rawQuery":query,"count":min(max_posts-len(posts),20),"querySource":"typed_query","product":"Top","withGrokTranslatedBio":True,"withQuickPromoteEligibilityTweetFields":False}
                _resp = _sess.get("https://x.com/i/api/graphql/vLHjqbDv7TPFMBkIIO1nOA/SearchTimeline",params={"variables":_json.dumps(_vars,separators=(",",":")),"features":_json.dumps(_feats,separators=(",",":"))},timeout=15)
                if _resp.status_code != 200:
                    raise Exception(f"Gagal: {_resp.status_code}")
                _data = _resp.json()
                _instr = _data.get("data",{}).get("search_by_raw_query",{}).get("search_timeline",{}).get("timeline",{}).get("instructions",[])
                raw = []
                for _ins in _instr:
                    if _ins.get("type") != "TimelineAddEntries": continue
                    for _ent in _ins.get("entries",[]):
                        try:
                            _res = _ent.get("content",{}).get("itemContent",{}).get("tweet_results",{}).get("result",{})
                            if not _res: continue
                            if _res.get("__typename") == "TweetWithVisibilityResults": _res = _res.get("tweet",_res)
                            _leg = _res.get("legacy",{})
                            _usr = _res.get("core",{}).get("user_results",{}).get("result",{}).get("legacy",{})
                            if not _leg: continue
                            raw.append({"id":_leg.get("id_str"),"text":_leg.get("full_text",""),"username":_usr.get("screen_name",""),"name":_usr.get("name",""),"created_at":_leg.get("created_at",""),"retweet_count":_leg.get("retweet_count",0),"like_count":_leg.get("favorite_count",0),"reply_count":_leg.get("reply_count",0),"followers":_usr.get("followers_count",0),"url":f"https://x.com/{_usr.get('screen_name')}/status/{_leg.get('id_str')}","lang":_leg.get("lang",""),"is_retweet":"retweeted_status_id_str" in _leg})
                        except: pass
                cookie_results = []
                for t in raw:
                    uid = f"tw-{t.get('username','unknown')}"
                    cookie_results.append({
                        "post_id": f"twx-{t.get('id','0')}",
                        "account_id": uid,
                        "platform": "twitter",
                        "content": t.get("text",""),
                        "timestamp": 0,
                        "ts_confidence": "failed",
                        "url": t.get("url",""),
                        "retweet_count": t.get("retweet_count",0),
                        "like_count": t.get("like_count",0),
                        "reply_count": t.get("reply_count",0),
                        "likes": t.get("like_count",0),
                        "retweets": t.get("retweet_count",0),
                        "replies": t.get("reply_count",0),
                        "shares": 0,
                        "views": 0,
                        "is_retweet": t.get("is_retweet",False),
                        "lang": t.get("lang",""),
                        "timestamp_unix": 0,
                        "timestamp_human": "",
                        "quote_count": 0,
                        "view_count": 0,
                        "hashtags": [],
                        "mentions": [],
                        "media_urls": [],
                        "urls": [],
                        "images": [],
                        "videos": [],
                        "content_hash": "",
                        "minhash_sig": [],
                        "embedding": [],
                        "sentiment": 0.0,
                        "bot_score": 0.0,
                        "coordinated": False,
                        "narrative_ids": [],
                        "cluster_id": None,
                        "_author": {
                            "username": t.get("username",""),
                            "display_name": t.get("name",""),
                            "followers": t.get("followers",0),
                            "bio": "",
                            "following": 0,
                            "tweet_count": 0,
                            "created_at": "",
                        },
                    })
            except Exception as _e:
                _log.warning("twitter_stealth failed: %s", _e)
                cookie_results = []
            if cookie_results:
                source_used = source["tag"]
                for r in cookie_results:
                    if len(posts) >= max_posts:
                        break
                    posts.append(r)
                    acct_id = r["account_id"]
                    if acct_id not in accounts_seen:
                        author = r.get("_author", {})
                        accounts_seen[acct_id] = {
                            "account_id": acct_id, "platform": "twitter",
                            "username": author.get("username", acct_id.replace("tw-", "")),
                            "display_name": author.get("display_name", ""),
                            "bio": author.get("bio", ""),
                            "followers": author.get("followers", 0),
                            "following": author.get("following", 0),
                            "tweet_count": author.get("tweet_count", 0),
                            "created_at": author.get("created_at", ""),
                            "post_count": 0, "posts_in_query": [],
                        }
                    accounts_seen[acct_id]["post_count"] += 1
                    accounts_seen[acct_id]["posts_in_query"].append(r["post_id"])
                    ts_stats[r.get("ts_confidence", "exact")] = ts_stats.get(r.get("ts_confidence", "exact"), 0) + 1
                if posts:
                    break
            continue

        # Health check first — don't waste time on dead sources
        if not _check_source_alive(source["url"], source["tag"]):
            continue

        if source["type"] == "nitter":
            url = f"{source['url']}/search?f=tweets&q={encoded_q}"
            html = _stealth_fetch(url, timeout=20)
            if not html:
                continue

            source_used = source["tag"]
            tweet_blocks = re.findall(
                r'<div class="timeline-item[^"]*">(.*?)</div>\s*</div>\s*</div>',
                html, re.DOTALL,
            )

            for block in tweet_blocks:
                if len(posts) >= max_posts:
                    break

                user_match = re.search(r'href="/([^/"]+)"[^>]*class="username"', block)
                if not user_match:
                    user_match = re.search(r'class="username"[^>]*>@?([^<]+)', block)
                username = user_match.group(1).strip() if user_match else None
                if not username:
                    continue

                name_match = re.search(r'class="fullname"[^>]*>([^<]+)', block)
                display_name = name_match.group(1).strip() if name_match else username

                content_match = re.search(r'class="tweet-content[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
                content = ""
                if content_match:
                    content = re.sub(r"<[^>]+>", "", content_match.group(1)).strip()
                if not content:
                    continue

                # REAL timestamp extraction — NEVER fake
                ts_match = re.search(r'title="([^"]*\d{4}[^"]*)"', block)
                raw_ts = ts_match.group(1) if ts_match else ""
                ts_unix, ts_conf = _parse_timestamp_robust(raw_ts)
                ts_stats[ts_conf] = ts_stats.get(ts_conf, 0) + 1

                stats = re.findall(r'class="icon-(\w+)"[^>]*>\s*</span>\s*(\d+)', block)
                stats_map = {s[0]: int(s[1]) for s in stats}

                hashtags = re.findall(r"#(\w+)", content)
                mentions = re.findall(r"@(\w+)", content)
                urls_found = re.findall(r"https?://\S+", content)

                c_hash = _content_hash(content)
                mh_sig = _minhash_signature(content)

                post_id = f"tw-{hashlib.md5(f'{username}:{c_hash}'.encode()).hexdigest()[:16]}"

                post = {
                    "post_id": post_id,
                    "account_id": f"tw-{username}",
                    "platform": "twitter",
                    "content": content,
                    "timestamp": raw_ts or utc_now_iso(),
                    "timestamp_unix": ts_unix,
                    "ts_confidence": ts_conf,
                    "likes": stats_map.get("heart", 0),
                    "retweets": stats_map.get("retweet", 0),
                    "replies": stats_map.get("comment", 0),
                    "hashtags": hashtags,
                    "mentions": mentions,
                    "urls": urls_found,
                    "content_hash": c_hash,
                    "minhash_sig": mh_sig,
                }
                posts.append(post)

                acct_id = f"tw-{username}"
                if acct_id not in accounts_seen:
                    accounts_seen[acct_id] = {
                        "account_id": acct_id, "platform": "twitter",
                        "username": username, "display_name": display_name,
                        "post_count": 0, "posts_in_query": [],
                    }
                accounts_seen[acct_id]["post_count"] += 1
                accounts_seen[acct_id]["posts_in_query"].append(post_id)

            if posts:
                break  # Got data, stop trying other sources
            _human_delay(3.0, 7.0)

        elif source["type"] == "syndication":
            # Twitter syndication endpoint — search.json
            syndication_url = f"{source['url']}/srv/timeline-profile/screen-name/{encoded_q}"
            html = _stealth_fetch(syndication_url, timeout=15)
            if html:
                source_used = source["tag"]
                # Syndication returns embedded tweet HTML — parse similarly
                # This is a fallback, format varies
                _log.info("syndication source responded, parsing...")
            # Continue to next if no usable data

    # ── Timestamp quality report ──
    total_ts = sum(ts_stats.values())
    ts_quality = "GOOD" if ts_stats.get("exact", 0) + ts_stats.get("parsed", 0) > total_ts * 0.7 else (
        "PARTIAL" if ts_stats.get("failed", 0) < total_ts * 0.5 else "POOR"
    )
    if ts_quality == "POOR":
        HEALTH.degraded("timestamp_quality", f"Only {total_ts - ts_stats.get('failed', 0)}/{total_ts} timestamps parsed")

    health_note = json.dumps({"source": source_used, "ts_quality": ts_quality, "ts_stats": ts_stats})

    # ── Store to DB ──
    for p in posts:
        conn.execute(
            """INSERT OR REPLACE INTO cog_posts
               (post_id, account_id, platform, content, timestamp, timestamp_unix,
                ts_confidence, likes, retweets, replies, hashtags_json, mentions_json,
                urls_json, media_json, language, sentiment, is_repost, job_id,
                content_hash, minhash_sig)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["post_id"], p["account_id"], p["platform"], p["content"],
                p["timestamp"], p["timestamp_unix"], p["ts_confidence"],
                p["likes"], p["retweets"], p["replies"],
                json.dumps(p["hashtags"]), json.dumps(p["mentions"]),
                json.dumps(p["urls"]), "[]", "id", 0.0, 0, job_id,
                p["content_hash"], json.dumps(p["minhash_sig"]),
            ),
        )

    for acct in accounts_seen.values():
        age_days = 0
        if acct.get("created_at"):
            try:
                created = datetime.fromisoformat(acct["created_at"].replace("Z", "+00:00"))
                age_days = max(0, (datetime.now(timezone.utc) - created).days)
            except Exception:
                pass
        conn.execute(
            """INSERT OR REPLACE INTO cog_accounts
               (account_id, platform, username, display_name, bio, followers, following,
                post_count, account_age_days, bot_score, bot_label, bot_confidence,
                first_seen, updated_at, fingerprint, score_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                acct["account_id"], acct["platform"], acct["username"],
                acct["display_name"], acct.get("bio", ""),
                acct.get("followers", 0), acct.get("following", 0),
                acct.get("tweet_count", acct["post_count"]), age_days,
                0.0, "UNSCORED", 0.0, utc_now_iso(), utc_now_iso(), "", 0,
            ),
        )

    conn.execute(
        """UPDATE cog_scrape_jobs
           SET status='COMPLETED', total_posts=?, total_accounts=?,
               finished_at=?, source_method=?, health_note=?
           WHERE job_id=?""",
        (len(posts), len(accounts_seen), utc_now_iso(), source_used, health_note, job_id),
    )
    conn.commit()
    conn.close()

    if not posts:
        hint = "Semua source Twitter gagal."
        if not _TWITTER_AUTH_TOKEN or not _TWITTER_CT0:
            hint += " Set env OMNI_TWITTER_AUTH_TOKEN + OMNI_TWITTER_CT0 (dari cookie browser x.com), atau OMNI_TWITTER_BEARER, atau gunakan Telegram."
        HEALTH.degraded("scraper:twitter", f"0 posts for '{query[:30]}' — {hint}")

    return {
        "ok": len(posts) > 0,
        "job_id": job_id,
        "platform": "twitter",
        "query": query,
        "posts_collected": len(posts),
        "accounts_found": len(accounts_seen),
        "accounts": list(accounts_seen.keys()),
        "source_used": source_used,
        "timestamp_quality": ts_quality,
        "_health": health_note,
        **({"error": hint} if not posts else {}),
    }


def scrape_telegram_channel(channel: str, max_posts: int = 200, job_id: str = None) -> Dict[str, Any]:
    """
    Scrape Telegram public channel — with pagination via ?before= parameter.
    """
    if os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true"):
        return {"ok": False, "error": "Air-gap mode: online scraping disabled."}

    if not job_id:
        job_id = f"TG-{int(time.time())}-{hashlib.md5(channel.encode()).hexdigest()[:8]}"

    channel = channel.lstrip("@").strip()
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO cog_scrape_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, "telegram", channel, "RUNNING", 0, 0, utc_now_iso(), None, None, "t.me/s", None),
    )
    conn.commit()

    posts = []
    acct_id = f"tg-{channel}"
    base_url = f"https://t.me/s/{channel}"

    # ── Paginated fetch — follow "Load more" / before= parameter ──
    next_url = base_url
    pages_fetched = 0
    max_pages = (max_posts // 20) + 2  # ~20 per page estimate

    while len(posts) < max_posts and pages_fetched < max_pages:
        html = _stealth_fetch(next_url, timeout=20)
        if not html:
            if pages_fetched == 0:
                conn.execute(
                    "UPDATE cog_scrape_jobs SET status='FAILED', error=?, finished_at=? WHERE job_id=?",
                    (f"Cannot access @{channel}", utc_now_iso(), job_id),
                )
                conn.commit()
                conn.close()
                HEALTH.degraded("scraper:telegram", f"Cannot access @{channel}")
                return {"ok": False, "error": f"Cannot access telegram channel @{channel}"}
            break

        pages_fetched += 1

        # Parse messages
        msg_blocks = re.findall(
            r'<div class="tgme_widget_message_wrap[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</div>',
            html, re.DOTALL,
        )

        if not msg_blocks:
            break  # No more content

        earliest_id = None
        for block in msg_blocks:
            if len(posts) >= max_posts:
                break

            text_match = re.search(
                r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                block, re.DOTALL,
            )
            content = ""
            if text_match:
                content = re.sub(r"<[^>]+>", "", text_match.group(1)).strip()
            if not content:
                continue

            # REAL timestamp
            ts_match = re.search(r'datetime="([^"]+)"', block)
            raw_ts = ts_match.group(1) if ts_match else ""
            ts_unix, ts_conf = _parse_timestamp_robust(raw_ts)

            # Views
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

            # Post ID for pagination
            post_id_match = re.search(r'data-post="([^"]+)"', block)
            raw_post_id = post_id_match.group(1) if post_id_match else None
            post_id = raw_post_id.replace("/", "-") if raw_post_id else f"tg-{channel}-{len(posts)}"

            # Track earliest for pagination
            if raw_post_id:
                msg_num = re.search(r"/(\d+)$", raw_post_id)
                if msg_num:
                    num = int(msg_num.group(1))
                    if earliest_id is None or num < earliest_id:
                        earliest_id = num

            hashtags = re.findall(r"#(\w+)", content)
            mentions = re.findall(r"@(\w+)", content)
            urls_found = re.findall(r"https?://\S+", content)

            c_hash = _content_hash(content)
            mh_sig = _minhash_signature(content)

            posts.append({
                "post_id": post_id,
                "account_id": acct_id,
                "platform": "telegram",
                "content": content,
                "timestamp": raw_ts or utc_now_iso(),
                "timestamp_unix": ts_unix,
                "ts_confidence": ts_conf,
                "likes": views,
                "retweets": 0,
                "replies": 0,
                "hashtags": hashtags,
                "mentions": mentions,
                "urls": urls_found,
                "content_hash": c_hash,
                "minhash_sig": mh_sig,
            })

        # Pagination: load older messages
        if earliest_id and earliest_id > 1:
            next_url = f"{base_url}?before={earliest_id}"
            _human_delay(2.0, 5.0)
        else:
            break

    # Store
    for p in posts:
        conn.execute(
            """INSERT OR REPLACE INTO cog_posts
               (post_id, account_id, platform, content, timestamp, timestamp_unix,
                ts_confidence, likes, retweets, replies, hashtags_json, mentions_json,
                urls_json, media_json, language, sentiment, is_repost, job_id,
                content_hash, minhash_sig)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["post_id"], p["account_id"], p["platform"], p["content"],
                p["timestamp"], p["timestamp_unix"], p["ts_confidence"],
                p["likes"], p["retweets"], p["replies"],
                json.dumps(p["hashtags"]), json.dumps(p["mentions"]),
                json.dumps(p["urls"]), "[]", "id", 0.0, 0, job_id,
                p["content_hash"], json.dumps(p["minhash_sig"]),
            ),
        )

    conn.execute(
        """INSERT OR REPLACE INTO cog_accounts
           (account_id, platform, username, display_name, bio, followers, following,
            post_count, account_age_days, bot_score, bot_label, bot_confidence,
            first_seen, updated_at, fingerprint, score_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (acct_id, "telegram", channel, channel, "", 0, 0, len(posts), 0,
         0.0, "CHANNEL", 0.0, utc_now_iso(), utc_now_iso(), "", 0),
    )

    conn.execute(
        """UPDATE cog_scrape_jobs
           SET status='COMPLETED', total_posts=?, total_accounts=1,
               finished_at=?, source_method=?, health_note=?
           WHERE job_id=?""",
        (len(posts), utc_now_iso(), "t.me/s+pagination",
         json.dumps({"pages": pages_fetched}), job_id),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True, "job_id": job_id, "platform": "telegram",
        "channel": channel, "posts_collected": len(posts),
        "pages_fetched": pages_fetched,
    }


# ══════════════════════════════════════════════════════════════════════
# 4. BOT DETECTION ENGINE — Adversarial-Resistant Multi-Signal
# ══════════════════════════════════════════════════════════════════════

# Current scoring algorithm version — increment when logic changes
# so we know which accounts need re-scoring
BOT_SCORE_VERSION = 2


def _posting_time_entropy(timestamps_unix: List[int]) -> Tuple[float, str]:
    """
    Entropi distribusi jam posting.
    Returns (entropy, confidence).
    Confidence "low" kalau timestamps terlalu sedikit atau banyak yang failed.
    """
    valid_ts = [t for t in timestamps_unix if t > 0]
    if len(valid_ts) < 5:
        return 4.0, "low"

    hours = [datetime.utcfromtimestamp(ts).hour for ts in valid_ts]
    counts = Counter(hours)
    total = sum(counts.values())
    probs = [c / total for c in counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    return round(entropy, 4), "high" if len(valid_ts) >= 20 else "medium"


def _text_similarity_minhash(posts_data: List[Dict]) -> float:
    """
    Similarity via MinHash — resistant to word shuffle, emoji padding, synonym swap.
    """
    sigs = []
    for p in posts_data:
        if p.get("minhash_sig"):
            try:
                sig = json.loads(p["minhash_sig"]) if isinstance(p["minhash_sig"], str) else p["minhash_sig"]
                if sig and sig != [0] * len(sig):
                    sigs.append(sig)
            except (json.JSONDecodeError, TypeError):
                pass

    if len(sigs) < 2:
        return 0.0

    # Compare consecutive + random pairs
    similarities = []
    for i in range(min(len(sigs) - 1, 30)):
        sim = _minhash_similarity(sigs[i], sigs[i + 1])
        similarities.append(sim)

    # Also some random pairs for thoroughness
    if len(sigs) > 5:
        for _ in range(min(20, len(sigs))):
            i, j = random.sample(range(len(sigs)), 2)
            similarities.append(_minhash_similarity(sigs[i], sigs[j]))

    return round(sum(similarities) / len(similarities), 4) if similarities else 0.0


def _content_hash_duplicates(posts_data: List[Dict]) -> float:
    """
    Ratio of posts with duplicate content hashes.
    Content hash is normalization-resistant — word shuffle doesn't help.
    """
    hashes = [p.get("content_hash", "") for p in posts_data if p.get("content_hash")]
    if len(hashes) < 2:
        return 0.0
    counts = Counter(hashes)
    duplicated = sum(c - 1 for c in counts.values() if c > 1)
    return round(duplicated / len(hashes), 4)


def _posting_regularity_score(timestamps_unix: List[int]) -> Tuple[float, str]:
    """Regularity of posting intervals. Returns (score, confidence)."""
    valid_ts = sorted(t for t in timestamps_unix if t > 0)
    if len(valid_ts) < 5:
        return 0.0, "low"

    intervals = [valid_ts[i + 1] - valid_ts[i] for i in range(len(valid_ts) - 1)]
    intervals = [iv for iv in intervals if iv > 0]  # Remove 0-intervals
    if not intervals:
        return 0.0, "low"

    mean_iv = sum(intervals) / len(intervals)
    if mean_iv == 0:
        return 1.0, "high"

    variance = sum((x - mean_iv) ** 2 for x in intervals) / len(intervals)
    cv = math.sqrt(variance) / mean_iv
    regularity = max(0.0, 1.0 - min(cv, 2.0) / 2.0)
    conf = "high" if len(valid_ts) >= 20 else "medium"
    return round(regularity, 4), conf


def _burst_posting_ratio(timestamps_unix: List[int], window_sec: int = 60) -> float:
    """Ratio of posts within burst window."""
    valid_ts = sorted(t for t in timestamps_unix if t > 0)
    if len(valid_ts) < 2:
        return 0.0
    burst = sum(1 for i in range(len(valid_ts) - 1) if valid_ts[i + 1] - valid_ts[i] < window_sec)
    return round(burst / (len(valid_ts) - 1), 4)


def _username_analysis(username: str) -> Dict[str, float]:
    """
    Multi-signal username analysis — harder to game than single entropy check.
    """
    if not username:
        return {"entropy": 0.0, "digit_ratio": 0.0, "has_pattern": 0.0, "score": 0.0}

    u = username.lower()

    # Entropy
    counts = Counter(u)
    total = len(u)
    probs = [c / total for c in counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)

    # Digit ratio — bot names often end with random digits
    digit_ratio = sum(1 for c in u if c.isdigit()) / max(len(u), 1)

    # Common bot patterns
    bot_patterns = [
        r"^[a-z]{3,8}\d{4,}$",          # word + numbers
        r"^[a-z]+_[a-z]+_?\d*$",         # word_word_123
        r"^\d+[a-z]+\d+$",              # 123abc456
        r"^[a-z]{1,3}\d{6,}$",          # ab123456
        r"^(bot|fake|spam|test|user)\d*", # obvious bot names
    ]
    has_pattern = 1.0 if any(re.match(p, u) for p in bot_patterns) else 0.0

    # Combined — but NOT binary
    score = 0.0
    if entropy > 3.8:
        score += 0.3  # high entropy = random string
    if digit_ratio > 0.4:
        score += 0.3  # too many digits
    if has_pattern:
        score += 0.4
    if len(u) > 15 and digit_ratio > 0.3:
        score += 0.2  # long name with lots of digits

    return {
        "entropy": round(entropy, 4),
        "digit_ratio": round(digit_ratio, 4),
        "has_pattern": has_pattern,
        "score": round(min(1.0, score), 4),
    }


def _profile_completeness(account: Dict) -> float:
    """
    How complete the profile is. Returns 0-1 where 1 = likely bot (empty profile).
    Gradual scoring — not binary.
    """
    score = 0.0
    penalties = 0
    total_checks = 5

    bio = str(account.get("bio", "") or "")
    if len(bio) < 5:
        score += 1.0
    elif len(bio) < 20:
        score += 0.5  # Suspiciously short but not empty
    penalties += 1

    if not account.get("profile_pic_url"):
        score += 1.0
    penalties += 1

    followers = account.get("followers", 0) or 0
    following = account.get("following", 0) or 0
    if followers == 0 and following == 0:
        score += 1.0
    elif followers < 5 and following < 5:
        score += 0.5
    penalties += 1

    age = account.get("account_age_days", 0) or 0
    if age == 0:
        score += 0.3  # Unknown age ≠ new account. Just unknown.
    elif age < 7:
        score += 0.8
    elif age < 30:
        score += 0.4
    penalties += 1

    if not account.get("verified"):
        score += 0.2  # Very light signal
    penalties += 1

    return round(min(1.0, score / total_checks), 4)


def _follower_ratio_score(followers: int, following: int) -> float:
    """
    Gradual scoring — not binary 0/1.
    """
    if following == 0 and followers == 0:
        return 0.3  # Unknown, not conclusive

    if following == 0:
        return 0.1  # Has followers but follows nobody — could be celebrity

    ratio = followers / following

    # Gradual sigmoid-like scoring
    if ratio < 0.01:
        return 0.9   # follows 10000 people, 10 followers
    elif ratio < 0.05:
        return 0.7
    elif ratio < 0.1:
        return 0.5
    elif ratio > 200:
        return 0.6   # Extreme ratio suspicious but could be celeb
    elif ratio > 50:
        return 0.3
    else:
        return 0.0   # Normal range


def _behavioral_fingerprint(account: Dict, posts: List[Dict]) -> str:
    """
    Generate behavioral fingerprint — hard to fake because it requires
    consistent long-term behavioral changes.
    """
    components = []

    # Posting hour distribution pattern
    valid_ts = [p["timestamp_unix"] for p in posts if p.get("timestamp_unix", 0) > 0]
    if valid_ts:
        hours = [datetime.utcfromtimestamp(ts).hour for ts in valid_ts]
        hour_dist = [0] * 24
        for h in hours:
            hour_dist[h] += 1
        total = sum(hour_dist)
        if total > 0:
            pattern = "".join("H" if c / total > 0.08 else "L" for c in hour_dist)
            components.append(f"hr:{pattern}")

    # Content length distribution
    lengths = [len(p.get("content", "")) for p in posts]
    if lengths:
        avg_len = sum(lengths) / len(lengths)
        components.append(f"len:{int(avg_len)}")

    # Hashtag usage rate
    ht_count = sum(1 for p in posts if p.get("hashtags_json") and p["hashtags_json"] != "[]")
    if posts:
        components.append(f"ht:{round(ht_count / len(posts), 2)}")

    return "|".join(components)


def compute_bot_score(account_id: str, conn: sqlite3.Connection = None) -> Dict[str, Any]:
    """
    Bot Score v2 — adversarial-resistant.

    Key differences from v1:
    - MinHash similarity instead of word-level Jaccard
    - Content hash dedup detection (word shuffle immune)
    - Gradual scoring instead of binary thresholds
    - Confidence bands on every signal
    - Timestamps with quality tracking
    - Behavioral fingerprinting
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db()

    account = conn.execute("SELECT * FROM cog_accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not account:
        if own_conn:
            conn.close()
        return {"ok": False, "error": f"Account {account_id} not found."}

    posts = conn.execute(
        "SELECT * FROM cog_posts WHERE account_id = ? ORDER BY timestamp_unix",
        (account_id,),
    ).fetchall()

    posts_data = [dict(p) for p in posts]
    timestamps = [p["timestamp_unix"] for p in posts_data]
    valid_timestamps = [t for t in timestamps if t > 0]

    # ── Timestamp quality gate ──
    ts_quality = "usable"
    if posts_data:
        failed_ts = sum(1 for p in posts_data if p.get("ts_confidence") == "failed")
        if failed_ts > len(posts_data) * 0.5:
            ts_quality = "unreliable"
            HEALTH.degraded("bot_scoring:timestamps",
                            f"{account_id}: {failed_ts}/{len(posts_data)} timestamps failed")

    # ── Feature Extraction ──
    time_entropy, time_conf = _posting_time_entropy(timestamps)
    text_sim = _text_similarity_minhash(posts_data)
    hash_dupes = _content_hash_duplicates(posts_data)
    regularity, reg_conf = _posting_regularity_score(timestamps)
    burst = _burst_posting_ratio(timestamps)
    username_analysis = _username_analysis(account["username"])
    profile_score = _profile_completeness(dict(account))
    ff_score = _follower_ratio_score(account["followers"] or 0, account["following"] or 0)

    # Behavioral fingerprint
    fingerprint = _behavioral_fingerprint(dict(account), posts_data)

    # Age vs activity
    age_days = max(1, account["account_age_days"] or 1)
    posts_per_day = len(posts_data) / age_days
    age_activity = min(1.0, posts_per_day / 50.0)

    # ── Weighted Composite — with confidence-adjusted weights ──
    # If timestamp data is unreliable, reduce weight of timing signals
    ts_weight_mult = 1.0 if ts_quality == "usable" else 0.3

    signals = {
        "time_entropy": {
            "raw": time_entropy, "confidence": time_conf,
            "normalized": max(0.0, 1.0 - time_entropy / 4.5),
            "weight": 0.10 * ts_weight_mult,
        },
        "text_similarity_minhash": {
            "raw": text_sim, "confidence": "high",
            "normalized": min(1.0, text_sim * 2.5),
            "weight": 0.20,  # High weight — hard to game
        },
        "content_hash_duplicates": {
            "raw": hash_dupes, "confidence": "high",
            "normalized": min(1.0, hash_dupes * 3.0),
            "weight": 0.15,  # Word shuffle immune
        },
        "ff_ratio": {
            "raw": ff_score, "confidence": "high",
            "normalized": ff_score,
            "weight": 0.08,
        },
        "posting_regularity": {
            "raw": regularity, "confidence": reg_conf,
            "normalized": regularity,
            "weight": 0.10 * ts_weight_mult,
        },
        "burst_posting": {
            "raw": burst, "confidence": "medium" if ts_quality == "usable" else "low",
            "normalized": min(1.0, burst * 2.0),
            "weight": 0.10 * ts_weight_mult,
        },
        "username": {
            "raw": username_analysis["score"], "confidence": "high",
            "normalized": username_analysis["score"],
            "weight": 0.07,
        },
        "profile_completeness": {
            "raw": profile_score, "confidence": "high",
            "normalized": profile_score,
            "weight": 0.10,
        },
        "age_activity_anomaly": {
            "raw": posts_per_day, "confidence": "medium",
            "normalized": age_activity,
            "weight": 0.10,
        },
    }

    # Normalize weights to sum to 1.0
    total_weight = sum(s["weight"] for s in signals.values())
    if total_weight > 0:
        for s in signals.values():
            s["effective_weight"] = round(s["weight"] / total_weight, 4)
    else:
        for s in signals.values():
            s["effective_weight"] = 0.0

    composite = sum(s["normalized"] * s["effective_weight"] for s in signals.values())
    bot_score = round(min(100.0, composite * 100.0), 1)

    # ── Confidence band ──
    # How confident are we in this score?
    high_conf_signals = sum(1 for s in signals.values() if s["confidence"] == "high")
    confidence = round(high_conf_signals / len(signals), 2)

    # ── Labels — more aggressive, no "LIKELY_ORGANIC" bullshit ──
    if bot_score >= 75:
        label = "BOT_CONFIRMED"
    elif bot_score >= 55:
        label = "BOT_PROBABLE"
    elif bot_score >= 35:
        label = "SUSPICIOUS"
    elif bot_score >= 20:
        label = "UNCONFIRMED"
    else:
        label = "LOW_SIGNAL"

    # ── Store ──
    flags = {k: {
        "raw": v["raw"], "normalized": round(v["normalized"], 4),
        "weight": v["effective_weight"], "confidence": v["confidence"],
    } for k, v in signals.items()}

    conn.execute(
        """UPDATE cog_accounts
           SET bot_score=?, bot_label=?, bot_confidence=?, flags_json=?,
               updated_at=?, fingerprint=?, score_version=?
           WHERE account_id=?""",
        (bot_score, label, confidence, json.dumps(flags),
         utc_now_iso(), fingerprint, BOT_SCORE_VERSION, account_id),
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
        "confidence": confidence,
        "signals": flags,
        "posts_analyzed": len(posts_data),
        "timestamp_quality": ts_quality,
        "score_version": BOT_SCORE_VERSION,
    }


def run_bot_detection_batch(job_id: str = None, topic: str = None) -> Dict[str, Any]:
    """Run bot detection for all accounts in a job/topic."""
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
            "SELECT account_id FROM cog_accounts WHERE bot_label IN ('UNSCORED', 'PENDING') "
            "OR score_version < ?", (BOT_SCORE_VERSION,)
        ).fetchall()]

    results = []
    errors = 0
    for aid in account_ids:
        try:
            r = compute_bot_score(aid, conn=conn)
            if r.get("ok"):
                results.append(r)
            else:
                errors += 1
        except Exception as e:
            errors += 1
            _log.error("bot_score failed for %s: %s", aid, e)

    conn.commit()
    conn.close()

    if errors > 0:
        HEALTH.degraded("bot_detection", f"{errors}/{len(account_ids)} accounts failed scoring")

    bots = [r for r in results if r["bot_score"] >= 55]
    suspicious = [r for r in results if 35 <= r["bot_score"] < 55]
    low = [r for r in results if r["bot_score"] < 35]

    return {
        "ok": True,
        "total_analyzed": len(results),
        "errors": errors,
        "bots_detected": len(bots),
        "suspicious": len(suspicious),
        "low_signal": len(low),
        "top_bots": sorted(bots, key=lambda x: x["bot_score"], reverse=True)[:20],
        "results": results,
        "score_version": BOT_SCORE_VERSION,
    }


# ══════════════════════════════════════════════════════════════════════
# 5. CIB DETECTION — MinHash + Time Buckets (Scalable)
# ══════════════════════════════════════════════════════════════════════

def detect_coordinated_posting(
    window_seconds: int = 120,
    min_accounts: int = 2,   # Lowered from 3 — 2 is enough to flag
    min_similarity: float = 0.25,
    job_id: str = None,
) -> Dict[str, Any]:
    """
    CIB detection v2:
    - MinHash similarity (word-shuffle resistant)
    - Time-bucket indexing (O(n) instead of O(n²))
    - Content-hash exact-match layer
    - Adaptive window based on posting velocity
    - min_accounts=2 (was 3 — bot farms adapt to stay at 2)
    """
    conn = get_db()

    query = "SELECT * FROM cog_posts WHERE timestamp_unix > 0 ORDER BY timestamp_unix"
    params: tuple = ()
    if job_id:
        query = "SELECT * FROM cog_posts WHERE job_id = ? AND timestamp_unix > 0 ORDER BY timestamp_unix"
        params = (job_id,)

    posts = [dict(p) for p in conn.execute(query, params).fetchall()]

    if len(posts) < min_accounts:
        conn.close()
        return {"ok": True, "events": [], "total_events": 0}

    events = []

    # ── Layer 1: Exact content hash match (catches word-shuffle) ──
    hash_groups: Dict[str, List[Dict]] = defaultdict(list)
    for p in posts:
        h = p.get("content_hash", "")
        if h:
            hash_groups[h].append(p)

    for h, group in hash_groups.items():
        unique_accounts = list(set(p["account_id"] for p in group))
        if len(unique_accounts) >= min_accounts:
            event_id = f"CIB-HASH-{h[:8]}-{int(time.time())}"
            event = {
                "event_id": event_id,
                "event_type": "EXACT_CONTENT_MATCH",
                "description": f"{len(unique_accounts)} accounts posted identical content (normalized)",
                "accounts": unique_accounts,
                "window_seconds": 0,
                "similarity": 1.0,
                "sample_content": group[0]["content"][:200],
                "detected_at": utc_now_iso(),
                "severity": "CRITICAL" if len(unique_accounts) >= 5 else "HIGH",
                "evidence": {
                    "content_hash": h,
                    "post_ids": [p["post_id"] for p in group[:10]],
                },
            }
            events.append(event)

    # ── Layer 2: Time-bucket + MinHash similarity ──
    # Bucket posts by time window for O(n) comparison
    bucket_size = window_seconds
    buckets: Dict[int, List[Dict]] = defaultdict(list)
    for p in posts:
        bucket_key = p["timestamp_unix"] // bucket_size
        buckets[bucket_key].append(p)
        # Also add to adjacent bucket to catch boundary-spanning coordination
        buckets[bucket_key + 1].append(p)

    checked_pairs: Set[str] = set()

    for bucket_key, bucket_posts in buckets.items():
        if len(bucket_posts) < min_accounts:
            continue

        # Group by different accounts only
        by_account: Dict[str, List[Dict]] = defaultdict(list)
        for p in bucket_posts:
            by_account[p["account_id"]].append(p)

        if len(by_account) < min_accounts:
            continue

        # Compare across accounts using MinHash
        account_list = list(by_account.keys())
        for i in range(len(account_list)):
            for j in range(i + 1, len(account_list)):
                pair_key = f"{min(account_list[i], account_list[j])}:{max(account_list[i], account_list[j])}"
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                # Compare best posts between the two accounts
                for p1 in by_account[account_list[i]][:5]:
                    for p2 in by_account[account_list[j]][:5]:
                        sig1 = None
                        sig2 = None
                        try:
                            sig1 = json.loads(p1["minhash_sig"]) if isinstance(p1.get("minhash_sig"), str) else p1.get("minhash_sig")
                            sig2 = json.loads(p2["minhash_sig"]) if isinstance(p2.get("minhash_sig"), str) else p2.get("minhash_sig")
                        except (json.JSONDecodeError, TypeError):
                            continue

                        if not sig1 or not sig2:
                            continue

                        sim = _minhash_similarity(sig1, sig2)
                        if sim >= min_similarity:
                            time_diff = abs(p1["timestamp_unix"] - p2["timestamp_unix"])
                            event_id = f"CIB-MH-{hashlib.md5(pair_key.encode()).hexdigest()[:8]}-{int(time.time())}"
                            event = {
                                "event_id": event_id,
                                "event_type": "COORDINATED_SIMILAR_CONTENT",
                                "description": (
                                    f"{account_list[i]} and {account_list[j]} posted "
                                    f"similar content (sim={sim:.2f}) within {time_diff}s"
                                ),
                                "accounts": [account_list[i], account_list[j]],
                                "window_seconds": time_diff,
                                "similarity": round(sim, 3),
                                "sample_content": p1["content"][:200],
                                "detected_at": utc_now_iso(),
                                "severity": "HIGH" if sim >= 0.6 else "MEDIUM",
                                "evidence": {
                                    "post_ids": [p1["post_id"], p2["post_id"]],
                                    "minhash_similarity": round(sim, 4),
                                },
                            }
                            events.append(event)

    # Store events
    for ev in events:
        conn.execute(
            "INSERT OR REPLACE INTO cog_coordinated_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                ev["event_id"], ev["event_type"], ev["description"],
                json.dumps(ev["accounts"]), ev["window_seconds"],
                ev["similarity"], ev["detected_at"], ev["severity"],
                json.dumps(ev.get("evidence", {})),
            ),
        )

    conn.commit()
    conn.close()

    HEALTH.ok("cib_detection", f"{len(events)} events detected")

    return {
        "ok": True,
        "events": events,
        "total_events": len(events),
        "detection_layers": ["exact_hash", "minhash_temporal"],
    }


def detect_hashtag_amplification(min_accounts: int = 2, job_id: str = None) -> Dict[str, Any]:
    """Detect coordinated hashtag amplification."""
    conn = get_db()

    query = "SELECT * FROM cog_posts ORDER BY timestamp_unix"
    params: tuple = ()
    if job_id:
        query = "SELECT * FROM cog_posts WHERE job_id = ? ORDER BY timestamp_unix"
        params = (job_id,)

    posts = conn.execute(query, params).fetchall()

    hashtag_usage: Dict[str, List[Dict]] = defaultdict(list)
    for p in posts:
        try:
            tags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
        except (json.JSONDecodeError, TypeError):
            tags = re.findall(r"#(\w+)", p["content"] or "")
        for tag in tags:
            hashtag_usage[tag.lower()].append({
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

        time_span = 0
        if len(sorted_usage) > 1 and sorted_usage[0]["timestamp_unix"] > 0 and sorted_usage[-1]["timestamp_unix"] > 0:
            time_span = sorted_usage[-1]["timestamp_unix"] - sorted_usage[0]["timestamp_unix"]

        narrative = {
            "narrative_id": narrative_id,
            "hashtag": f"#{tag}",
            "seed_account": seed_account,
            "amplifier_accounts": amplifiers,
            "total_posts": len(usages),
            "unique_accounts": len(unique_accounts),
            "first_seen": sorted_usage[0]["timestamp_unix"],
            "time_span_hours": round(time_span / 3600.0, 1) if time_span > 0 else 0,
        }
        narratives.append(narrative)

        conn.execute(
            """INSERT OR REPLACE INTO cog_narratives
               (narrative_id, topic_query, hashtag, seed_account,
                amplifier_accounts_json, total_reach, first_seen, classification, summary)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                narrative_id, tag, f"#{tag}", seed_account,
                json.dumps(amplifiers), len(usages),
                utc_now_iso(), "AMPLIFIED",
                f"#{tag} amplified by {len(amplifiers)} accounts from seed @{seed_account}",
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
# 6. NARRATIVE & HOAX DETECTION — Structural, Not Just Keywords
# ══════════════════════════════════════════════════════════════════════

# Hoax keyword layer (still useful as ONE signal, not the ONLY signal)
_HOAX_KEYWORDS_ID = [
    "sebarkan", "viralkan", "share sebelum dihapus", "pemerintah sembunyikan",
    "media mainstream", "terungkap", "terbongkar", "breaking news",
    "wajib baca", "ketahuan", "bukti nyata", "rahasia terbongkar",
    "jangan percaya", "bangun indonesia", "kritis",
    "darurat", "bahaya", "waspada", "awas", "hati-hati",
]


def _compute_hoax_score_v2(text: str) -> Tuple[float, List[str], Dict]:
    """
    Hoax scoring v2 — multi-layer:
    1. Keyword matching (weak signal, easy to evade)
    2. Structural analysis (harder to evade)
    3. Source citation analysis (medium difficulty to evade)
    4. Emotional manipulation patterns
    5. Claim density analysis

    Returns (score, indicators, breakdown).
    """
    if not text:
        return 0.0, [], {}

    text_lower = text.lower()
    indicators = []
    breakdown = {}

    # ── Layer 1: Keywords (weight reduced — this is the easy-to-game one) ──
    keyword_hits = sum(1 for kw in _HOAX_KEYWORDS_ID if kw in text_lower)
    keyword_score = min(1.0, keyword_hits * 0.1)
    if keyword_hits > 0:
        indicators.append(f"keywords:{keyword_hits}")
    breakdown["keywords"] = {"score": keyword_score, "weight": 0.15}

    # ── Layer 2: Structural patterns (hard to game) ──
    struct_score = 0.0
    words = text.split()
    word_count = len(words)

    # ALL CAPS ratio — emotional manipulation
    if words:
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 2)
        caps_ratio = caps_words / len(words)
        if caps_ratio > 0.2:
            struct_score += 0.3
            indicators.append(f"caps_ratio:{caps_ratio:.2f}")

    # Exclamation/question mark density
    excl_count = text.count("!") + text.count("⚠") + text.count("‼")
    if word_count > 0 and excl_count / max(len(text), 1) > 0.015:
        struct_score += 0.2
        indicators.append(f"exclamation_density:{excl_count}")

    # Very short + imperative = chain message
    if word_count < 30 and any(kw in text_lower for kw in ["sebarkan", "share", "forward", "kirim"]):
        struct_score += 0.3
        indicators.append("short_imperative")

    # No paragraph structure (wall of text with no breaks)
    if word_count > 100 and text.count("\n") < 2:
        struct_score += 0.1
        indicators.append("wall_of_text")

    breakdown["structure"] = {"score": min(1.0, struct_score), "weight": 0.25}

    # ── Layer 3: Source citation (tricky — hoaxers fake sources too) ──
    source_score = 0.0
    has_url = bool(re.search(r"https?://\S+", text))
    has_source_mention = any(kw in text_lower for kw in [
        "sumber:", "referensi:", "dikutip dari", "menurut ", "berdasarkan ",
    ])

    # Having "menurut penelitian" WITHOUT a URL is SUSPICIOUS, not credible
    if has_source_mention and not has_url:
        source_score += 0.4
        indicators.append("fake_attribution_no_url")
    elif not has_source_mention and not has_url:
        source_score += 0.2
        indicators.append("no_source")
    # If has URL, check if it's a known credible domain (could be expanded)
    elif has_url:
        urls = re.findall(r"https?://([^/\s]+)", text)
        sketchy_tlds = [".xyz", ".top", ".click", ".link", ".info"]
        for url_domain in urls:
            if any(url_domain.endswith(tld) for tld in sketchy_tlds):
                source_score += 0.3
                indicators.append(f"sketchy_domain:{url_domain}")

    breakdown["source_citation"] = {"score": min(1.0, source_score), "weight": 0.25}

    # ── Layer 4: Emotional manipulation ──
    emotion_score = 0.0
    fear_words = ["bahaya", "waspada", "darurat", "mati", "korban", "krisis", "ancaman"]
    urgency_words = ["segera", "sekarang", "sebelum terlambat", "jangan tunda", "harus sekarang"]

    fear_hits = sum(1 for w in fear_words if w in text_lower)
    urgency_hits = sum(1 for w in urgency_words if w in text_lower)

    if fear_hits >= 2:
        emotion_score += 0.3
        indicators.append(f"fear_language:{fear_hits}")
    if urgency_hits >= 1:
        emotion_score += 0.3
        indicators.append(f"urgency_language:{urgency_hits}")

    # "Mereka tidak mau kamu tahu" pattern
    conspiracy_patterns = [
        r"mereka\s+(tidak|tak)\s+(mau|ingin)",
        r"(dirahasiakan|disembunyikan)\s+dari",
        r"media\s+(tidak|tak)\s+(mau|akan)\s+(memberitakan|memberitahu)",
        r"pemerintah\s+(sembunyikan|tutup|rahasiakan)",
    ]
    for pat in conspiracy_patterns:
        if re.search(pat, text_lower):
            emotion_score += 0.3
            indicators.append(f"conspiracy_pattern")
            break

    breakdown["emotional_manipulation"] = {"score": min(1.0, emotion_score), "weight": 0.20}

    # ── Layer 5: Claim density (many unverifiable claims per sentence) ──
    claim_score = 0.0
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if len(sentences) > 0:
        # Count superlatives and absolute claims
        absolutes = sum(1 for s in sentences if any(
            w in s.lower() for w in [
                "semua", "seluruh", "pasti", "tidak pernah", "selalu",
                "100%", "terbukti", "fakta", "dijamin",
            ]
        ))
        claim_ratio = absolutes / len(sentences)
        if claim_ratio > 0.3:
            claim_score += 0.4
            indicators.append(f"absolute_claims:{absolutes}/{len(sentences)}")

    breakdown["claim_density"] = {"score": min(1.0, claim_score), "weight": 0.15}

    # ── Weighted composite ──
    total_score = sum(
        layer["score"] * layer["weight"]
        for layer in breakdown.values()
    )

    return round(min(1.0, total_score), 3), indicators, breakdown


def analyze_narrative(topic: str, job_id: str = None) -> Dict[str, Any]:
    """Narrative analysis with v2 hoax detection."""
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

    timestamps = [p["timestamp_unix"] for p in posts if p["timestamp_unix"] > 0]
    accounts = list(set(p["account_id"] for p in posts))

    # Hoax analysis v2
    hoax_scores = []
    all_indicators = []
    all_breakdowns = []
    for p in posts:
        score, indicators, breakdown = _compute_hoax_score_v2(p["content"])
        hoax_scores.append(score)
        all_indicators.extend(indicators)
        all_breakdowns.append(breakdown)

    avg_hoax = round(sum(hoax_scores) / len(hoax_scores), 3) if hoax_scores else 0.0
    max_hoax = max(hoax_scores) if hoax_scores else 0.0

    # Spread velocity
    if len(timestamps) > 1:
        time_span = max(timestamps) - min(timestamps)
        spread_velocity = round(len(posts) / max(time_span / 3600.0, 0.1), 2)
    else:
        spread_velocity = 0.0

    # Top spreaders
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
    indicator_summary = [{"indicator": k, "count": v} for k, v in Counter(all_indicators).most_common(15)]

    # Classification — use max score too, not just average
    if max_hoax >= 0.7 or avg_hoax >= 0.5:
        classification = "HIGH_RISK_DISINFORMATION"
    elif max_hoax >= 0.5 or avg_hoax >= 0.3:
        classification = "SUSPICIOUS_NARRATIVE"
    elif avg_hoax >= 0.15:
        classification = "MONITOR"
    else:
        classification = "LOW_RISK"

    conn.close()

    return {
        "ok": True,
        "topic": topic,
        "posts_found": len(posts),
        "unique_accounts": len(accounts),
        "avg_hoax_score": avg_hoax,
        "max_hoax_score": max_hoax,
        "classification": classification,
        "spread_velocity_per_hour": spread_velocity,
        "time_span_hours": round((max(timestamps) - min(timestamps)) / 3600.0, 1) if len(timestamps) > 1 else 0,
        "top_spreaders": top_spreaders,
        "top_hashtags": top_hashtags,
        "hoax_indicators": indicator_summary,
    }


# ══════════════════════════════════════════════════════════════════════
# 7. NETWORK GRAPH — Community Detection with Error Reporting
# ══════════════════════════════════════════════════════════════════════

def build_interaction_graph(job_id: str = None) -> Dict[str, Any]:
    """Build interaction graph with proper error reporting."""
    nx = _ensure_networkx()
    conn = get_db()

    query = "SELECT * FROM cog_posts"
    params: tuple = ()
    if job_id:
        query = "SELECT * FROM cog_posts WHERE job_id = ?"
        params = (job_id,)

    posts = conn.execute(query, params).fetchall()

    if nx is None:
        # ── Fallback without NetworkX — explicit about limitations ──
        HEALTH.degraded("graph_analysis", "NetworkX not available — no community detection")
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
            "communities": -1,  # -1 = not computed, not "1 big community"
            "degraded": True,
            "degraded_reason": "NetworkX not installed — community detection unavailable",
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
            if G.has_edge(acct, target):
                G[acct][target]["weight"] = G[acct][target].get("weight", 1.0) + 1.0
            else:
                G.add_edge(acct, target, relation="MENTION", weight=1.0)

        try:
            hashtags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
        except (json.JSONDecodeError, TypeError):
            hashtags = []
        for h in hashtags:
            hashtag_users[h.lower()].add(acct)

    for tag, users in hashtag_users.items():
        users_list = list(users)
        for i in range(len(users_list)):
            for j in range(i + 1, len(users_list)):
                if G.has_edge(users_list[i], users_list[j]):
                    G[users_list[i]][users_list[j]]["weight"] += 0.5
                else:
                    G.add_edge(users_list[i], users_list[j], relation="CO_HASHTAG", weight=0.5)

    # Community detection with EXPLICIT error handling
    communities = None
    community_map = {}
    community_error = None

    try:
        communities = list(nx.community.greedy_modularity_communities(G))
        for idx, comm in enumerate(communities):
            for node in comm:
                community_map[node] = idx
        HEALTH.ok("community_detection", f"{len(communities)} communities found")
    except Exception as e:
        community_error = str(e)
        community_map = {}  # EMPTY, not "all in 0" — we don't know
        HEALTH.dead("community_detection", f"Algorithm failed: {e}")
        _log.error("Community detection FAILED: %s", e)

    # Update cluster IDs (only if detection succeeded)
    if community_map:
        for acct_id, cluster_id in community_map.items():
            conn.execute(
                "UPDATE cog_accounts SET cluster_id = ? WHERE account_id = ?",
                (cluster_id, acct_id),
            )

    # Store edges
    stored_edges = 0
    for u, v, data in G.edges(data=True):
        edge_id = hashlib.md5(f"{u}:{v}".encode()).hexdigest()[:16]
        conn.execute(
            "INSERT OR REPLACE INTO cog_networks VALUES (?,?,?,?,?,?)",
            (edge_id, u, v, data.get("relation", "UNKNOWN"), data.get("weight", 1.0), utc_now_iso()),
        )
        stored_edges += 1

    conn.commit()

    # Node data
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
        })

    # Betweenness — with error reporting
    betweenness_computed = False
    try:
        if G.number_of_nodes() <= 5000:
            betweenness = nx.betweenness_centrality(G)
            for nd in node_data:
                nd["betweenness"] = round(betweenness.get(nd["id"], 0.0), 4)
            betweenness_computed = True
        else:
            # Approximate for large graphs
            betweenness = nx.betweenness_centrality(G, k=min(100, G.number_of_nodes()))
            for nd in node_data:
                nd["betweenness"] = round(betweenness.get(nd["id"], 0.0), 4)
            betweenness_computed = True
            HEALTH.ok("betweenness", f"approximated (k=100) for {G.number_of_nodes()} nodes")
    except Exception as e:
        HEALTH.degraded("betweenness", f"Failed: {e}")
        _log.warning("Betweenness centrality failed: %s", e)
        for nd in node_data:
            nd["betweenness"] = -1.0  # -1 = not computed, not "zero influence"

    modularity_val = -1.0
    if communities:
        try:
            modularity_val = round(nx.community.modularity(G, communities), 4)
        except Exception:
            pass

    conn.close()

    return {
        "ok": True,
        "nodes": sorted(node_data, key=lambda x: x["bot_score"], reverse=True),
        "edges": [
            {"source": u, "target": v, "relation": data.get("relation", ""), "weight": data.get("weight", 1.0)}
            for u, v, data in G.edges(data=True)
        ],
        "total_nodes": len(node_data),
        "total_edges": stored_edges,
        "communities": len(communities) if communities else -1,
        "modularity": modularity_val,
        "betweenness_computed": betweenness_computed,
        "community_error": community_error,
    }


# ══════════════════════════════════════════════════════════════════════
# 8. SURGE DETECTION
# ══════════════════════════════════════════════════════════════════════

def detect_new_account_surge(
    age_threshold_days: int = 30,
    min_accounts: int = 3,
    job_id: str = None,
) -> Dict[str, Any]:
    """Detect surge of new accounts on a topic."""
    conn = get_db()

    if job_id:
        accounts = conn.execute(
            """SELECT DISTINCT a.* FROM cog_accounts a
               JOIN cog_posts p ON a.account_id = p.account_id
               WHERE p.job_id = ?""", (job_id,),
        ).fetchall()
    else:
        accounts = conn.execute("SELECT * FROM cog_accounts").fetchall()

    new_accounts = [a for a in accounts if (a["account_age_days"] or 0) <= age_threshold_days]

    conn.close()

    surge_detected = len(new_accounts) >= min_accounts
    surge_ratio = round(len(new_accounts) / max(len(accounts), 1), 3)

    if surge_ratio >= 0.5 and len(new_accounts) >= 10:
        severity = "CRITICAL"
    elif surge_ratio >= 0.3 and len(new_accounts) >= min_accounts:
        severity = "HIGH"
    elif surge_detected:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "ok": True,
        "surge_detected": surge_detected,
        "total_accounts": len(accounts),
        "new_accounts": len(new_accounts),
        "new_account_ratio": surge_ratio,
        "severity": severity,
        "new_account_list": [
            {
                "account_id": a["account_id"], "username": a["username"],
                "account_age_days": a["account_age_days"], "bot_score": a["bot_score"],
            }
            for a in sorted(new_accounts, key=lambda x: x["bot_score"], reverse=True)[:20]
        ],
    }


# ══════════════════════════════════════════════════════════════════════
# 9. GRAPH INTEGRATION — With Error Counting
# ══════════════════════════════════════════════════════════════════════

def ingest_cognitive_to_graph(job_id: str = None) -> Dict[str, Any]:
    """Push results to Intelligence Graph. Reports every failure."""
    import engine_graph

    conn = get_db()
    ingested = {"nodes": 0, "edges": 0, "alerts": 0}
    errors = {"nodes": 0, "edges": 0, "alerts": 0}

    bots = conn.execute(
        "SELECT * FROM cog_accounts WHERE bot_score >= 55 ORDER BY bot_score DESC"
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
        except Exception as e:
            errors["nodes"] += 1
            _log.warning("graph ingest node failed %s: %s", bot["account_id"], e)

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
        except Exception as ex:
            errors["edges"] += 1

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
        except Exception as ex:
            errors["alerts"] += 1

    conn.commit()
    conn.close()

    total_errors = sum(errors.values())
    if total_errors > 0:
        HEALTH.degraded("graph_ingest", f"{total_errors} items failed to ingest")

    return {
        "ok": True,
        "ingested": ingested,
        "errors": errors,
    }


# ══════════════════════════════════════════════════════════════════════
# 10. FULL PIPELINE
# ══════════════════════════════════════════════════════════════════════

def run_full_cognitive_analysis(
    platform: str = "twitter",
    query: str = "",
    channel: str = "",
    max_posts: int = 200,
    cib_window_sec: int = 120,
    min_cib_accounts: int = 2,
) -> Dict[str, Any]:
    """
    Full pipeline. Each stage reports its own health.
    Partial results are returned even if later stages fail.
    """
    init_cognitive_db()

    results: Dict[str, Any] = {"pipeline_stages": {}}
    job_id = f"COGFULL-{int(time.time())}-{hashlib.md5((query or channel).encode()).hexdigest()[:6]}"

    # Stage 1: Scrape
    if platform == "twitter" and query:
        scrape_result = scrape_twitter_search(query, max_posts=max_posts, job_id=job_id)
    elif platform == "telegram" and channel:
        scrape_result = scrape_telegram_channel(channel, max_posts=max_posts, job_id=job_id)
    else:
        return {"ok": False, "error": "Specify platform=twitter + query, or platform=telegram + channel."}

    results["pipeline_stages"]["1_scrape"] = {
        "status": "OK" if scrape_result.get("ok") else "FAILED",
        "posts": scrape_result.get("posts_collected", 0),
        "source": scrape_result.get("source_used", "none"),
        "ts_quality": scrape_result.get("timestamp_quality", "unknown"),
    }

    if not scrape_result.get("ok") or scrape_result.get("posts_collected", 0) == 0:
        results["ok"] = False
        results["error"] = scrape_result.get("error", "Scraping failed or returned 0 posts")
        results["health"] = HEALTH.report()
        return results

    # Stage 2-7: Run remaining stages, capturing errors individually
    stages = [
        ("2_bot_detection", lambda: run_bot_detection_batch(job_id=job_id)),
        ("3_coordinated_behavior", lambda: detect_coordinated_posting(
            window_seconds=cib_window_sec, min_accounts=min_cib_accounts, job_id=job_id)),
        ("4_hashtag_amplification", lambda: detect_hashtag_amplification(
            min_accounts=min_cib_accounts, job_id=job_id)),
        ("5_network_graph", lambda: build_interaction_graph(job_id=job_id)),
        ("6_narrative_analysis", lambda: analyze_narrative(query or channel, job_id=job_id)),
        ("7_surge_detection", lambda: detect_new_account_surge(job_id=job_id)),
    ]

    stage_results = {}
    for stage_name, stage_fn in stages:
        try:
            result = stage_fn()
            stage_results[stage_name] = result
            results["pipeline_stages"][stage_name] = {"status": "OK", "summary": _summarize_stage(stage_name, result)}
        except Exception as e:
            _log.error("Pipeline stage %s FAILED: %s", stage_name, e)
            results["pipeline_stages"][stage_name] = {"status": "FAILED", "error": str(e)}
            HEALTH.dead(f"pipeline:{stage_name}", str(e))

    # Stage 8: Graph ingest
    try:
        ingest_result = ingest_cognitive_to_graph(job_id=job_id)
        results["pipeline_stages"]["8_graph_ingest"] = {
            "status": "OK", "ingested": ingest_result.get("ingested", {}),
            "errors": ingest_result.get("errors", {}),
        }
    except Exception as e:
        results["pipeline_stages"]["8_graph_ingest"] = {"status": "FAILED", "error": str(e)}

    results["ok"] = True
    results["job_id"] = job_id
    results["health"] = HEALTH.report()

    bot_result = stage_results.get("2_bot_detection", {})
    cib_result = stage_results.get("3_coordinated_behavior", {})
    narrative_result = stage_results.get("6_narrative_analysis", {})
    surge_result = stage_results.get("7_surge_detection", {})

    results["summary"] = {
        "posts_collected": scrape_result.get("posts_collected", 0),
        "bots_detected": bot_result.get("bots_detected", 0),
        "cib_events": cib_result.get("total_events", 0),
        "narratives_tracked": stage_results.get("4_hashtag_amplification", {}).get("total_narratives", 0),
        "hoax_classification": narrative_result.get("classification", "UNKNOWN"),
        "surge_severity": surge_result.get("severity", "UNKNOWN"),
    }

    return results


def _summarize_stage(name: str, result: Dict) -> Dict:
    """Extract key metrics from a stage result for the pipeline summary."""
    if "bot_detection" in name:
        return {"bots": result.get("bots_detected", 0), "suspicious": result.get("suspicious", 0)}
    elif "coordinated" in name:
        return {"events": result.get("total_events", 0)}
    elif "amplification" in name:
        return {"narratives": result.get("total_narratives", 0)}
    elif "graph" in name:
        return {"nodes": result.get("total_nodes", 0), "communities": result.get("communities", -1)}
    elif "narrative" in name:
        return {"hoax_score": result.get("avg_hoax_score", 0), "class": result.get("classification", "?")}
    elif "surge" in name:
        return {"detected": result.get("surge_detected", False), "severity": result.get("severity", "?")}
    return {}


# ══════════════════════════════════════════════════════════════════════
# 11. DASHBOARD & QUERY ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

def get_cognitive_dashboard(job_id: str = None) -> Dict[str, Any]:
    conn = get_db()

    if job_id:
        accounts = conn.execute(
            """SELECT a.* FROM cog_accounts a
               JOIN cog_posts p ON a.account_id = p.account_id
               WHERE p.job_id = ? GROUP BY a.account_id
               ORDER BY a.bot_score DESC""", (job_id,),
        ).fetchall()
    else:
        accounts = conn.execute(
            "SELECT * FROM cog_accounts ORDER BY bot_score DESC"
        ).fetchall()

    bot_count = sum(1 for a in accounts if a["bot_score"] >= 55)
    suspicious_count = sum(1 for a in accounts if 35 <= a["bot_score"] < 55)
    low_count = sum(1 for a in accounts if a["bot_score"] < 35)

    top_flagged = [
        {
            "account_id": a["account_id"], "username": a["username"],
            "platform": a["platform"], "bot_score": a["bot_score"],
            "bot_label": a["bot_label"],
            "bot_confidence": a["bot_confidence"] if "bot_confidence" in a.keys() else 0,
            "cluster_id": a["cluster_id"],
        }
        for a in accounts[:20]
    ]

    events = conn.execute(
        "SELECT * FROM cog_coordinated_events ORDER BY detected_at DESC LIMIT 10"
    ).fetchall()

    narratives = conn.execute(
        "SELECT * FROM cog_narratives ORDER BY total_reach DESC LIMIT 10"
    ).fetchall()

    edge_count = conn.execute("SELECT COUNT(*) as c FROM cog_networks").fetchone()["c"]

    conn.close()

    return {
        "ok": True,
        "summary": {
            "total_accounts": len(accounts),
            "bots": bot_count,
            "suspicious": suspicious_count,
            "low_signal": low_count,
            "bot_ratio": round(bot_count / max(len(accounts), 1), 3),
            "network_edges": edge_count,
        },
        "top_flagged_accounts": top_flagged,
        "recent_cib_events": [dict(e) for e in events],
        "top_narratives": [dict(n) for n in narratives],
        "system_health": HEALTH.report(),
    }


def get_account_detail(account_id: str) -> Dict[str, Any]:
    conn = get_db()
    account = conn.execute("SELECT * FROM cog_accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not account:
        conn.close()
        return {"ok": False, "error": "Account not found."}

    posts = conn.execute(
        "SELECT * FROM cog_posts WHERE account_id = ? ORDER BY timestamp_unix DESC LIMIT 50",
        (account_id,),
    ).fetchall()

    connections = conn.execute(
        "SELECT * FROM cog_networks WHERE source_account = ? OR target_account = ?",
        (account_id, account_id),
    ).fetchall()

    conn.close()

    account_d = dict(account)
    return {
        "ok": True,
        "account": account_d,
        "posts": [dict(p) for p in posts],
        "connections": [dict(c) for c in connections],
        "signals": json.loads(account_d["flags_json"]) if account_d.get("flags_json") else {},
        "score_version": account_d.get("score_version", 0),
    }


def get_system_health() -> Dict[str, Any]:
    """Endpoint for operator to check what's working and what's broken."""
    return HEALTH.report()


# ══════════════════════════════════════════════════════════════════════
# 12. DEMO SEED DATA — Realistic data when scraping is unavailable
# ══════════════════════════════════════════════════════════════════════

def seed_cognitive_demo() -> Dict[str, Any]:
    """
    Populate cognitive tables with realistic demo data.
    Called when OMNI_DEMO=1 and tables are empty.
    Gives operators something to see on the dashboard without live scraping.
    """
    init_cognitive_db()
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) as c FROM cog_accounts").fetchone()["c"]
    if existing > 0:
        conn.close()
        return {"ok": True, "seeded": False, "reason": "data already exists"}

    job_id = f"DEMO-{int(time.time())}"
    now_ts = int(time.time())
    now_iso = utc_now_iso()

    # ── Demo accounts: mix of bots, suspicious, and organic ──
    demo_accounts = [
        # Bots
        {"id": "tw-patriot_nkri_2024", "user": "patriot_nkri_2024", "display": "PATRIOT NKRI 🇮🇩",
         "bio": "", "followers": 12, "following": 4300, "age": 15, "score": 82.0, "label": "BOT_CONFIRMED"},
        {"id": "tw-berita_fakta99", "user": "berita_fakta99", "display": "Berita Fakta",
         "bio": "Info terkini", "followers": 45, "following": 3800, "age": 22, "score": 76.0, "label": "BOT_CONFIRMED"},
        {"id": "tw-info_rakyat_id", "user": "info_rakyat_id", "display": "INFO RAKYAT",
         "bio": "", "followers": 8, "following": 2100, "age": 10, "score": 71.0, "label": "BOT_PROBABLE"},
        {"id": "tw-jkw4ever2024", "user": "jkw4ever2024", "display": "JKW Forever",
         "bio": "Dukung terus", "followers": 33, "following": 5000, "age": 7, "score": 68.0, "label": "BOT_PROBABLE"},
        # Suspicious
        {"id": "tw-warga_biasa01", "user": "warga_biasa01", "display": "Warga Biasa",
         "bio": "Rakyat jelata", "followers": 150, "following": 600, "age": 90, "score": 44.0, "label": "SUSPICIOUS"},
        {"id": "tw-nusantara_info", "user": "nusantara_info", "display": "Nusantara Info",
         "bio": "Berita nusantara terpercaya", "followers": 800, "following": 400, "age": 180, "score": 38.0, "label": "SUSPICIOUS"},
        # Organic
        {"id": "tw-sinta_dewi_r", "user": "sinta_dewi_r", "display": "Sinta Dewi",
         "bio": "Mom of 2 | Foodie | Bandung", "followers": 1200, "following": 350, "age": 1400, "score": 12.0, "label": "LOW_SIGNAL"},
        {"id": "tw-andri_tech", "user": "andri_tech", "display": "Andri Setiawan",
         "bio": "Software engineer @tokopedia | Open source", "followers": 3400, "following": 280, "age": 2800, "score": 8.0, "label": "LOW_SIGNAL"},
        {"id": "tg-kabarterkini2024", "user": "kabarterkini2024", "display": "Kabar Terkini Channel",
         "bio": "", "followers": 0, "following": 0, "age": 45, "score": 0.0, "label": "CHANNEL"},
    ]

    def _demo_flags(score: float) -> str:
        """Derive plausible per-signal breakdown from the demo score so the
        account-detail Signal Breakdown panel renders realistic bars."""
        base = max(0.0, min(1.0, score / 100.0))
        # Per-signal multipliers relative to overall score (deterministic).
        profile = {
            "time_entropy":            base * 1.05,
            "text_similarity_minhash": base * 1.15,
            "content_hash_duplicates": base * 1.10,
            "ff_ratio":                base * 1.20,
            "posting_regularity":      base * 1.00,
            "burst_posting":           base * 1.25,
            "username":                base * 0.85,
            "profile_completeness":    base * 0.95,
            "age_activity_anomaly":    base * 0.90,
        }
        flags = {}
        for k, val in profile.items():
            norm = round(max(0.0, min(1.0, val)), 4)
            flags[k] = {"raw": norm, "normalized": norm, "weight": 0.11, "confidence": "high"}
        return json.dumps(flags)

    for a in demo_accounts:
        # Channel accounts have no behavioral signals.
        flags_json = "" if a["label"] == "CHANNEL" else _demo_flags(a["score"])
        conn.execute(
            """INSERT OR REPLACE INTO cog_accounts
               (account_id, platform, username, display_name, bio, followers, following,
                post_count, account_age_days, bot_score, bot_label, bot_confidence,
                flags_json, first_seen, updated_at, fingerprint, score_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (a["id"], "twitter" if a["id"].startswith("tw-") else "telegram",
             a["user"], a["display"], a["bio"], a["followers"], a["following"],
             random.randint(10, 200), a["age"], a["score"], a["label"], 0.7,
             flags_json, now_iso, now_iso, "", BOT_SCORE_VERSION),
        )

    # ── Demo posts ──
    demo_posts = [
        # Coordinated bot posts (similar content, close timing)
        {"acct": "tw-patriot_nkri_2024", "content": "WASPADA! Pemerintah sembunyikan data ekonomi yang sebenarnya. Rakyat harus tau! Sebarkan sebelum dihapus!! #BongkarKebohongan",
         "ts_offset": -3600, "likes": 5, "rt": 120},
        {"acct": "tw-berita_fakta99", "content": "Data ekonomi yang sebenarnya disembunyikan pemerintah! Rakyat wajib tau kebenarannya! SEBARKAN!! #BongkarKebohongan",
         "ts_offset": -3550, "likes": 3, "rt": 98},
        {"acct": "tw-info_rakyat_id", "content": "Pemerintah sembunyikan data ekonomi sebenarnya dari rakyat!! Waspada! Share sebelum dihapus! #BongkarKebohongan",
         "ts_offset": -3520, "likes": 2, "rt": 87},
        {"acct": "tw-jkw4ever2024", "content": "RAKYAT HARUS TAU! Data ekonomi disembunyikan! Sebarkan info ini sebelum terlambat!! #BongkarKebohongan #IndonesiaBangkit",
         "ts_offset": -3490, "likes": 1, "rt": 65},
        # Organic posts
        {"acct": "tw-sinta_dewi_r", "content": "Hari ini masak rendang buat keluarga. Resep dari almarhum mama, selalu bikin kangen 💕",
         "ts_offset": -7200, "likes": 45, "rt": 2},
        {"acct": "tw-andri_tech", "content": "Baru push PR untuk fix race condition di payment service. Code review welcome 🙏 https://github.com/example/pr/123",
         "ts_offset": -5400, "likes": 12, "rt": 3},
        {"acct": "tw-sinta_dewi_r", "content": "Ada yang tau tempat makan sunda enak di daerah Dago? Mau ajak temen kantor makan siang besok",
         "ts_offset": -1800, "likes": 8, "rt": 0},
        # Suspicious account posts
        {"acct": "tw-warga_biasa01", "content": "Menurut penelitian terbaru, kebijakan X sudah terbukti gagal. Berdasarkan data resmi yang dikonfirmasi sumber terpercaya.",
         "ts_offset": -900, "likes": 22, "rt": 15},
        {"acct": "tw-nusantara_info", "content": "BREAKING: Terungkap fakta baru soal proyek infrastruktur yang merugikan negara triliunan! Thread 🧵👇",
         "ts_offset": -600, "likes": 88, "rt": 340},
        # More bot activity
        {"acct": "tw-patriot_nkri_2024", "content": "Bukti nyata korupsi terbongkar! Media mainstream diam saja! RT jika kamu peduli Indonesia! #BongkarKebohongan",
         "ts_offset": -300, "likes": 4, "rt": 55},
        {"acct": "tw-berita_fakta99", "content": "Media mainstream tutup mata soal korupsi ini! Bukti sudah ada tapi tidak diberitakan! #BongkarKebohongan",
         "ts_offset": -280, "likes": 2, "rt": 43},
    ]

    for p in demo_posts:
        ts_unix = now_ts + p["ts_offset"]
        content = p["content"]
        c_hash = _content_hash(content)
        mh_sig = _minhash_signature(content)
        acct_name = p["acct"]
        post_id = f"demo-{hashlib.md5(f'{acct_name}:{c_hash}'.encode()).hexdigest()[:12]}"

        hashtags = re.findall(r"#(\w+)", content)
        mentions = re.findall(r"@(\w+)", content)
        urls = re.findall(r"https?://\S+", content)

        conn.execute(
            """INSERT OR REPLACE INTO cog_posts
               (post_id, account_id, platform, content, timestamp, timestamp_unix,
                ts_confidence, likes, retweets, replies, hashtags_json, mentions_json,
                urls_json, media_json, language, sentiment, is_repost, job_id,
                content_hash, minhash_sig)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (post_id, p["acct"], "twitter", content,
             datetime.utcfromtimestamp(ts_unix).isoformat() + "Z", ts_unix, "exact",
             p["likes"], p["rt"], 0,
             json.dumps(hashtags), json.dumps(mentions), json.dumps(urls),
             "[]", "id", 0.0, 0, job_id, c_hash, json.dumps(mh_sig)),
        )

    # ── Demo CIB event ──
    conn.execute(
        "INSERT OR REPLACE INTO cog_coordinated_events VALUES (?,?,?,?,?,?,?,?,?)",
        ("CIB-DEMO-001", "COORDINATED_SIMILAR_CONTENT",
         "4 akun memposting konten hampir identik soal #BongkarKebohongan dalam 110 detik",
         json.dumps(["tw-patriot_nkri_2024", "tw-berita_fakta99", "tw-info_rakyat_id", "tw-jkw4ever2024"]),
         110, 0.82, now_iso, "CRITICAL",
         json.dumps({"detection_layer": "minhash_temporal", "demo": True})),
    )

    # ── Demo narrative ──
    conn.execute(
        """INSERT OR REPLACE INTO cog_narratives
           (narrative_id, topic_query, hashtag, seed_account,
            amplifier_accounts_json, total_reach, first_seen, classification, summary)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("NAR-DEMO-001", "BongkarKebohongan", "#BongkarKebohongan", "tw-patriot_nkri_2024",
         json.dumps(["tw-berita_fakta99", "tw-info_rakyat_id", "tw-jkw4ever2024"]),
         11, now_iso, "AMPLIFIED",
         "#BongkarKebohongan amplified by 3 accounts from seed @patriot_nkri_2024"),
    )

    # ── Demo network edges ──
    bot_accounts = ["tw-patriot_nkri_2024", "tw-berita_fakta99", "tw-info_rakyat_id", "tw-jkw4ever2024"]
    for i in range(len(bot_accounts)):
        for j in range(i + 1, len(bot_accounts)):
            edge_id = hashlib.md5(f"{bot_accounts[i]}:{bot_accounts[j]}".encode()).hexdigest()[:16]
            conn.execute(
                "INSERT OR REPLACE INTO cog_networks VALUES (?,?,?,?,?,?)",
                (edge_id, bot_accounts[i], bot_accounts[j], "CO_HASHTAG", 2.0, now_iso),
            )

    conn.execute(
        "INSERT OR REPLACE INTO cog_scrape_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, "demo", "seed_data", "COMPLETED", len(demo_posts), len(demo_accounts),
         now_iso, now_iso, None, "demo_seed", '{"demo": true}'),
    )

    conn.commit()
    conn.close()

    _log.info("Demo cognitive data seeded: %d accounts, %d posts", len(demo_accounts), len(demo_posts))

    return {
        "ok": True, "seeded": True,
        "accounts": len(demo_accounts), "posts": len(demo_posts),
        "job_id": job_id,
    }
