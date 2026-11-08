"""
OSINT Engine v3.0 — 100% Python stdlib, tanpa API key
Username hunt (120+ platform) + GitHub harvest + Wayback Machine +
Breach check (HIBP) + Name OSINT (dork + email permutation) + Pastebin search
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import socket
import ssl
import hashlib
import re
import time
import concurrent.futures

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def _fetch(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(131072).decode("utf-8", errors="ignore")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""

# ─────────────────────────────────────────────
# Platform list: (name, url_template, not_found_strings, skip)
# Detection logic (dalam urutan):
#   1. status == 0  → skip (timeout/network)
#   2. status >= 400 → NOT FOUND
#   3. any not_found string ada di body → NOT FOUND
#   4. username ada di body → FOUND
#   5. fallback: status 200 → FOUND (untuk platform yg tidak embed username di body)
# ─────────────────────────────────────────────
PLATFORMS = [
    ("GitHub",       "https://github.com/{u}",
     ["Not Found", "page not found", "Join GitHub today"], False),

    ("Twitter/X",    "https://twitter.com/{u}",
     ["This account doesn't exist", "Try searching for", "page doesn't exist",
      "Something went wrong"], False),

    ("Instagram",    "https://www.instagram.com/{u}/",
     ["Page Not Found", "The link you followed may be broken",
      "Sorry, this page"], False),

    ("TikTok",       "https://www.tiktok.com/@{u}",
     ["Couldn't find this account", "couldn't find this account",
      "page not found", "404"], False),

    ("Reddit",       "https://www.reddit.com/user/{u}/",
     ["page not found", "Sorry, nobody on Reddit goes by that name",
      "there doesn't seem to be", "USER_DOESNT_EXIST",
      "nobody on reddit"], False),

    ("YouTube",      "https://www.youtube.com/@{u}",
     ["This page isn't available", "404 Not Found"], False),

    ("LinkedIn",     "https://www.linkedin.com/in/{u}",
     ["Page not found", "This profile is not available",
      "Profile not found", "Join now"], False),

    ("Pinterest",    "https://www.pinterest.com/{u}/",
     ["Hmm, we couldn't find that page", "isn't on Pinterest",
      "Page Not Found"], False),

    ("Telegram",     "https://t.me/{u}",
     ["If you have Telegram, you can contact", "tgme_page_extra"], False),

    ("Steam",        "https://steamcommunity.com/id/{u}",
     ["The specified profile could not be found",
      "profile could not be found"], False),

    ("Twitch",       "https://www.twitch.tv/{u}",
     ["Sorry. Unless you've", "this is not the page", "404"], False),

    ("Spotify",      "https://open.spotify.com/user/{u}",
     ["Page not found", "User not found", "doesn't exist",
      "This content is not available"], False),

    ("SoundCloud",   "https://soundcloud.com/{u}",
     ["We can't find that user", "Oh no! Something went wrong"], False),

    ("Bandcamp",     "https://{u}.bandcamp.com",
     ["Sorry, that something isn't here",
      "There's nothing here"], False),

    ("Vimeo",        "https://vimeo.com/{u}",
     ["Sorry, we couldn't find that page", "Page not found"], False),

    ("Dailymotion",  "https://www.dailymotion.com/{u}",
     ["This channel doesn't exist", "Page not found", "404"], False),

    ("Rumble",       "https://rumble.com/user/{u}",
     ["Page not found", "User not found", "404 Not Found"], False),

    ("500px",        "https://500px.com/p/{u}",
     ["Page Not Found", "isn't on 500px"], False),

    ("ArtStation",   "https://www.artstation.com/{u}",
     ["Page Not Found", "User not found"], False),

    ("DeviantArt",   "https://www.deviantart.com/{u}",
     ["DeviantArt – 404", "Page not found"], False),

    ("Behance",      "https://www.behance.net/{u}",
     ["Page Not Found", "be.net/404"], False),

    ("Dribbble",     "https://dribbble.com/{u}",
     ["Whoops, that page is gone", "404", "Page not found"], False),

    ("Medium",       "https://medium.com/@{u}",
     ["Page not found", "404", "doesn't exist"], False),

    ("Substack",     "https://{u}.substack.com",
     ["This publication doesn't exist", "doesn't exist"], False),

    ("Ko-fi",        "https://ko-fi.com/{u}",
     ["This page doesn't exist", "404", "Page not found"], False),

    ("Patreon",      "https://www.patreon.com/{u}",
     ["Page not found", "404", "doesn't exist"], False),

    ("GitLab",       "https://gitlab.com/{u}",
     ["404", "User Not Found",
      "The page you're looking for could not be found"], False),

    ("Keybase",      "https://keybase.io/{u}",
     ["Not found", "User not found", "no such user"], False),

    ("HackerNews",   "https://news.ycombinator.com/user?id={u}",
     ["No such user.", "404"], False),

    ("ProductHunt",  "https://www.producthunt.com/@{u}",
     ["404", "Not Found", "Page not found"], False),

    ("Mastodon",     "https://mastodon.social/@{u}",
     ["The page you are looking for", "404", "not found"], False),

    ("Flickr",       "https://www.flickr.com/people/{u}/",
     ["Page Not Found", "Oops!", "user not found"], False),

    ("Last.fm",      "https://www.last.fm/user/{u}",
     ["Page not found", "User not found", "404"], False),

    ("Goodreads",    "https://www.goodreads.com/{u}",
     ["Page not found", "User not found"], False),

    ("Letterboxd",   "https://letterboxd.com/{u}/",
     ["Sorry, we can't find the page", "404"], False),

    ("Chess.com",    "https://www.chess.com/member/{u}",
     ["404", "Member not found", "page not found"], False),

    ("Lichess",      "https://lichess.org/@/{u}",
     ["404", "User not found", "doesn't exist"], False),

    ("Duolingo",     "https://www.duolingo.com/profile/{u}",
     ["No such user", "404", "not found"], False),

    ("Gravatar",     "https://en.gravatar.com/{u}",
     ["We couldn't find", "404"], False),

    ("About.me",     "https://about.me/{u}",
     ["Page Not Found", "404", "doesn't exist"], False),

    ("Wattpad",      "https://www.wattpad.com/user/{u}",
     ["Oops! That page doesn't exist", "404"], False),

    ("Quora",        "https://www.quora.com/profile/{u}",
     ["Page Not Found", "404"], False),

    ("Snapchat",     "https://www.snapchat.com/add/{u}",
     ["This profile couldn't be found", "Page Not Found",
      "This Snapchat profile doesn't exist"], False),

    ("Mix",          "https://mix.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Clubhouse",    "https://www.clubhouse.com/@{u}",
     ["404", "not found", "Page not found"], False),

    ("Foursquare",   "https://foursquare.com/{u}",
     ["Page Not Found", "404"], False),

    ("WordPress",    "https://{u}.wordpress.com",
     ["doesn't exist", "site not found", "address is not"],  False),

    ("Roblox",       "https://www.roblox.com/user.aspx?username={u}",
     ["Page cannot be found", "404", "not found"], False),

    ("Bitbucket",    "https://bitbucket.org/{u}",
     ["Page not found", "404", "doesn't exist"], False),

    # ── Developer / Tech ────────────────────────────────────────────────────
    ("npm",          "https://www.npmjs.com/~{u}",
     ["404", "Not found", "doesn't exist"], False),

    ("PyPI",         "https://pypi.org/user/{u}/",
     ["404", "Not Found", "doesn't exist"], False),

    ("Docker Hub",   "https://hub.docker.com/u/{u}/",
     ["Page Not Found", "404", "doesn't exist"], False),

    ("Codepen",      "https://codepen.io/{u}",
     ["404", "Page not found", "doesn't exist"], False),

    ("Replit",       "https://replit.com/@{u}",
     ["404", "Page not found", "doesn't exist"], False),

    ("LeetCode",     "https://leetcode.com/{u}/",
     ["404", "does not exist", "User not found"], False),

    ("Codeforces",   "https://codeforces.com/profile/{u}",
     ["404", "not found", "User not found"], False),

    ("HackerRank",   "https://www.hackerrank.com/profile/{u}",
     ["404", "User does not exist", "not found"], False),

    ("Hackaday",     "https://hackaday.io/{u}",
     ["404", "not found", "User not found"], False),

    ("Instructables","https://www.instructables.com/member/{u}/",
     ["404", "Member not found", "We couldn't find"], False),

    ("Kaggle",       "https://www.kaggle.com/{u}",
     ["404", "not found", "User not found"], False),

    ("CodeSandbox",  "https://codesandbox.io/u/{u}",
     ["404", "not found"], False),

    ("Exercism",     "https://exercism.org/profiles/{u}",
     ["404", "not found", "User not found"], False),

    # ── Gaming ──────────────────────────────────────────────────────────────
    ("Faceit",       "https://www.faceit.com/en/players/{u}",
     ["404", "not found", "Player not found"], False),

    ("Kongregate",   "https://www.kongregate.com/accounts/{u}",
     ["404", "closed", "This account doesn't exist"], False),

    ("Itch.io",      "https://{u}.itch.io",
     ["404", "not found", "This page doesn't exist"], False),

    ("Speedrun.com", "https://www.speedrun.com/user/{u}",
     ["404", "not found", "User not found"], False),

    ("GameTrack",    "https://gametrack.app/users/{u}",
     ["404", "not found"], False),

    # ── Creative / Marketplace ───────────────────────────────────────────────
    ("Fiverr",       "https://www.fiverr.com/{u}",
     ["Page Not Found", "404", "This page isn't available"], False),

    ("Etsy",         "https://www.etsy.com/people/{u}",
     ["404", "Page not found", "not found"], False),

    ("Redbubble",    "https://www.redbubble.com/people/{u}/shop",
     ["404", "not found", "Hmm, we can't find"], False),

    ("Society6",     "https://society6.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Threadless",   "https://www.threadless.com/@{u}",
     ["404", "not found"], False),

    ("Mixcloud",     "https://www.mixcloud.com/{u}/",
     ["404", "This page could not be found", "not found"], False),

    ("Audiomack",    "https://audiomack.com/{u}",
     ["404", "not found", "This profile doesn't exist"], False),

    ("ReverbNation", "https://www.reverbnation.com/{u}",
     ["404", "not found", "Page not found"], False),

    # ── Social / Blogging ───────────────────────────────────────────────────
    ("VK",           "https://vk.com/{u}",
     ["404", "Page not found", "This page was deleted"], False),

    ("Tumblr",       "https://{u}.tumblr.com",
     ["There's nothing here", "Page not found", "404"], False),

    ("Blogger",      "https://{u}.blogspot.com",
     ["Blog not found", "The blog you were looking for was not found", "404"], False),

    ("LiveJournal",  "https://www.livejournal.com/userinfo.bml?user={u}",
     ["No such user", "User not found", "404"], False),

    ("Odysee",       "https://odysee.com/@{u}",
     ["404", "not found", "Page not found"], False),

    ("Minds",        "https://www.minds.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Gab",          "https://gab.com/{u}",
     ["404", "not found", "User not found"], False),

    ("Parler",       "https://parler.com/{u}",
     ["404", "not found", "User not found"], False),

    # ── Professional ────────────────────────────────────────────────────────
    ("AngelList",    "https://wellfound.com/u/{u}",
     ["404", "not found", "Page not found"], False),

    ("ResearchGate", "https://www.researchgate.net/profile/{u}",
     ["404", "not found", "Profile not found"], False),

    ("Academia.edu", "https://independent.academia.edu/{u}",
     ["404", "not found", "Page not found"], False),

    ("SlideShare",   "https://www.slideshare.net/{u}",
     ["404", "not found", "This page doesn't exist"], False),

    ("Scribd",       "https://www.scribd.com/{u}",
     ["404", "not found", "Page not found"], False),

    # ── Indonesian ──────────────────────────────────────────────────────────
    ("Kaskus",       "https://www.kaskus.co.id/user/{u}",
     ["404", "not found", "User tidak ditemukan"], False),

    ("IDN Times",    "https://www.idntimes.com/{u}",
     ["404", "not found", "Halaman tidak ditemukan"], False),

    # ── Finance / Crypto ────────────────────────────────────────────────────
    ("CoinMarketCap","https://coinmarketcap.com/community/profile/{u}/",
     ["404", "not found", "Page not found"], False),

    ("Binance",      "https://www.binance.com/en/feed/profile/{u}",
     ["404", "not found"], False),

    # ── Misc ────────────────────────────────────────────────────────────────
    ("Trello",       "https://trello.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Linktree",     "https://linktr.ee/{u}",
     ["404", "Sorry, this page isn't available", "not found"], False),

    ("Carrd",        "https://{u}.carrd.co",
     ["404", "not found", "This site is unavailable"], False),

    ("Notion",       "https://www.notion.so/@{u}",
     ["404", "not found", "Page not found"], False),

    ("Wakelet",      "https://wakelet.com/@{u}",
     ["404", "not found", "Page not found"], False),

    ("Gumroad",      "https://app.gumroad.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Tellonym",     "https://tellonym.me/{u}",
     ["404", "User not found", "not found"], False),

    ("Ask.fm",       "https://ask.fm/{u}",
     ["404", "User not found", "This user doesn't exist"], False),

    ("Typeform",     "https://{u}.typeform.com",
     ["404", "not found", "Page not found"], False),

    ("Unsplash",     "https://unsplash.com/@{u}",
     ["404", "User not found", "not found"], False),

    ("Pexels",       "https://www.pexels.com/@{u}",
     ["404", "not found", "Page not found"], False),

    ("Giphy",        "https://giphy.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Imgur",        "https://imgur.com/user/{u}",
     ["404", "User not found", "not found"], False),

    ("Devpost",      "https://devpost.com/{u}",
     ["404", "User not found", "not found"], False),

    ("Polywork",     "https://www.polywork.com/{u}",
     ["404", "not found", "Page not found"], False),

    ("Cash.app",     "https://cash.app/${u}",
     ["404", "not found", "User not found"], False),
]


def _check_one(username, name, url_tpl, not_found_strs, skip):
    if skip:
        return None
    url = url_tpl.replace("{u}", urllib.parse.quote(username, safe="@."))
    status, body = _fetch(url, timeout=10)

    if status == 0:
        return None  # timeout — skip

    if status >= 400:
        return {"platform": name, "url": url, "found": False, "status": status}

    body_lower = body.lower()

    # Cek not_found indicators
    for nf in not_found_strs:
        if nf.lower() in body_lower:
            return {"platform": name, "url": url, "found": False, "status": status}

    # Cek apakah username ada di body (bukti kuat)
    username_found_in_body = username.lower() in body_lower

    if username_found_in_body:
        # Username ada di HTML → VERIFIED FOUND
        return {"platform": name, "url": url, "found": True,
                "status": status, "confidence": "high"}
    else:
        # Status 200 tapi username tidak ada di body.
        # Platform JS-rendered tidak embed username di server HTML.
        # Tandai sebagai UNVERIFIED — bisa false positive.
        return {"platform": name, "url": url, "found": False,
                "status": status, "confidence": "unverified",
                "unverified": True}


def username_hunt(username: str) -> dict:
    if not username:
        return {"ok": False, "error": "Username diperlukan"}

    t0 = time.time()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as ex:
        # Platform checks
        plat_futures = {
            ex.submit(_check_one, username, name, url_tpl, nf, skip): name
            for name, url_tpl, nf, skip in PLATFORMS
        }
        # GitHub harvest paralel
        gh_future = ex.submit(github_harvest, username)
        # Wayback check paralel
        wb_future = ex.submit(wayback_check, f"https://github.com/{username}")

        for fut in concurrent.futures.as_completed(plat_futures):
            try:
                r = fut.result()
                if r is not None:
                    results.append(r)
            except Exception:
                pass

        try:
            gh = gh_future.result(timeout=15)
        except Exception:
            gh = {"ok": False}

        try:
            wb = wb_future.result(timeout=15)
        except Exception:
            wb = {"ok": False}

    elapsed = round(time.time() - t0, 2)

    verified   = sorted([r for r in results if r.get("found") and r.get("confidence") == "high"],
                        key=lambda x: x["platform"])
    unverified = sorted([r for r in results if r.get("unverified")],
                        key=lambda x: x["platform"])

    return {
        "ok": True,
        "type": "username",
        "query": username,
        "username": username,
        "found_count": len(verified),
        "unverified_count": len(unverified),
        "checked": len(results),
        "elapsed_s": elapsed,
        "platforms": verified,
        "unverified": unverified,
        "all_results": results,
        "github": gh,
        "wayback": wb,
    }


# ─────────────────────────────────────────────
# EMAIL OSINT
# ─────────────────────────────────────────────
_FREE_EMAIL_PROVIDERS = {
    "gmail.com","yahoo.com","hotmail.com","outlook.com","live.com",
    "icloud.com","me.com","mac.com","aol.com","protonmail.com","proton.me",
    "zoho.com","yandex.com","mail.com","gmx.com","tutanota.com",
}
_DISPOSABLE_DOMAINS = {
    "mailinator.com","guerrillamail.com","10minutemail.com","tempmail.com",
    "throwaway.email","sharklasers.com","trashmail.com","yopmail.com",
    "fakeinbox.com","dispostable.com","maildrop.cc","spamgourmet.com",
}

def email_osint(email: str) -> dict:
    if not email or "@" not in email:
        return {"ok": False, "error": "Email tidak valid"}

    local, domain = email.rsplit("@", 1)
    result = {"ok": True, "type": "email", "query": email,
              "email": email, "local": local, "domain": domain}

    mx = _dns_query(domain, "MX")
    a_records = _dns_query(domain, "A")
    result["mx"] = mx
    result["a_records"] = a_records
    # Frontend-expected aliases
    result["mx_records"] = mx
    result["domain_ips"] = a_records

    mx_str = " ".join(mx).lower()
    if "google" in mx_str:       provider = "Google Workspace / Gmail"
    elif "outlook" in mx_str or "microsoft" in mx_str: provider = "Microsoft 365"
    elif "yahoo" in mx_str:      provider = "Yahoo Mail"
    elif "zoho" in mx_str:       provider = "Zoho Mail"
    elif "protonmail" in mx_str: provider = "ProtonMail"
    else:                        provider = "Custom / Unknown"
    result["provider"] = provider
    result["mail_server_provider"] = provider  # frontend alias

    h = hashlib.md5(email.strip().lower().encode()).hexdigest()
    result["gravatar_hash"] = h
    result["gravatar_url"] = f"https://www.gravatar.com/avatar/{h}?d=404"
    result["gravatar"] = result["gravatar_url"]  # frontend alias
    g_status, _ = _fetch(f"https://www.gravatar.com/avatar/{h}?d=404")
    result["has_gravatar"] = g_status == 200

    certs = _crtsh(domain)
    result["certs"] = certs
    result["crt_sh_subdomains"] = certs  # frontend alias

    result["username_candidates"] = list({
        local, local.replace(".", ""), local.replace("_", ""),
        local.replace("-", ""), local.split(".")[0] if "." in local else "",
    } - {""})
    result["is_plus_alias"] = "+" in local
    result["has_dots"] = "." in local

    domain_lower = domain.lower()
    result["format_analysis"] = {
        "is_free_provider": domain_lower in _FREE_EMAIL_PROVIDERS,
        "is_disposable": domain_lower in _DISPOSABLE_DOMAINS,
        "has_plus_alias": "+" in local,
        "has_dots": "." in local,
    }

    # Breach check + wayback paralel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        bf = ex.submit(breach_check, email)
        wf = ex.submit(wayback_check, f"https://{domain}")
        try:
            result["breach"] = bf.result(timeout=15)
        except Exception:
            result["breach"] = {"ok": False}
        try:
            result["wayback_domain"] = wf.result(timeout=12)
        except Exception:
            result["wayback_domain"] = {"ok": False}

    return result


# ─────────────────────────────────────────────
# DOMAIN OSINT
# ─────────────────────────────────────────────
_PORT_SERVICES = {
    21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",
    110:"POP3",143:"IMAP",443:"HTTPS",445:"SMB",3306:"MySQL",
    3389:"RDP",5432:"PostgreSQL",6379:"Redis",8080:"HTTP-Alt",
    8443:"HTTPS-Alt",8888:"HTTP-Dev",27017:"MongoDB",
}

def domain_osint(domain: str) -> dict:
    domain = domain.lower().strip().lstrip("http://").lstrip("https://").split("/")[0]
    result = {"ok": True, "type": "domain", "query": domain, "domain": domain}

    a     = _dns_query(domain, "A")
    aaaa  = _dns_query(domain, "AAAA")
    mx    = _dns_query(domain, "MX")
    ns    = _dns_query(domain, "NS")
    txt   = _dns_query(domain, "TXT")
    cname = _dns_query(domain, "CNAME")

    result["a"] = a
    result["aaaa"] = aaaa
    result["mx"] = mx
    result["ns"] = ns
    result["txt"] = txt
    result["cname"] = cname
    result["resolved_ips"] = a  # frontend alias

    # DNS dict for frontend dns section
    dns_dict = {}
    if a:     dns_dict["A"] = a
    if aaaa:  dns_dict["AAAA"] = aaaa
    if mx:    dns_dict["MX"] = mx
    if ns:    dns_dict["NS"] = ns
    if txt:   dns_dict["TXT"] = txt
    if cname: dns_dict["CNAME"] = cname
    result["dns"] = dns_dict

    if a:
        ip_info_raw = ip_osint(a[0])
        result["ip_info"] = [ip_info_raw]  # frontend expects list
    else:
        result["ip_info"] = []

    ssl_info = _ssl_info(domain)
    result["ssl"] = ssl_info
    result["ssl_cert"] = ssl_info  # frontend alias

    whois_raw = _whois(domain)
    # Normalize whois for frontend: expects {ok, parsed, raw_snippet}
    result["whois"] = {
        "ok": bool(whois_raw.get("parsed")),
        "parsed": whois_raw.get("parsed", {}),
        "raw_snippet": whois_raw.get("raw", "")[:2000],
    }

    subdomains = _crtsh(domain)
    result["subdomains"] = subdomains
    result["subdomains_crtsh"] = subdomains  # frontend alias
    result["subdomain_count"] = len(subdomains)

    target_host = a[0] if a else domain
    raw_ports = _port_scan(target_host)
    result["ports"] = raw_ports
    result["open_ports"] = [
        {"port": p["port"], "service": _PORT_SERVICES.get(p["port"], "?"), "open": True}
        for p in raw_ports if p["open"]
    ]

    result["http_headers"] = _http_headers(domain)

    # HTTP status from headers attempt
    for scheme in ["https", "http"]:
        try:
            req = urllib.request.Request(f"{scheme}://{domain}", headers=_HEADERS, method="HEAD")
            ctx = ssl.create_default_context() if scheme == "https" else None
            if ctx:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=5, **({"context": ctx} if ctx else {})) as r:
                result["http_status"] = r.status
                break
        except Exception:
            pass

    # Basic tech hints from HTTP headers
    tech_hints = []
    hdrs = result["http_headers"]
    server = hdrs.get("Server", "")
    powered = hdrs.get("X-Powered-By", "")
    if server:   tech_hints.append(server)
    if powered:  tech_hints.append(powered)
    result["tech_hints"] = tech_hints

    # VirusTotal domain reputation
    result["virustotal"] = virustotal_check(domain, kind="domain")

    # OTX AlienVault IoC (domain)
    result["otx"] = otx_check(domain, kind="domain")

    return result


# ─────────────────────────────────────────────
# IP OSINT
# ─────────────────────────────────────────────
def ip_osint(ip: str) -> dict:
    result = {"ok": True, "type": "ip", "query": ip, "ip": ip}

    status, body = _fetch(f"http://ip-api.com/json/{ip}?fields=66846719")
    if status == 200:
        try:
            d = json.loads(body)
            result["geo"]      = d
            result["country"]  = d.get("country", "")
            result["city"]     = d.get("city", "")
            result["isp"]      = d.get("isp", "")
            result["org"]      = d.get("org", "")
            result["timezone"] = d.get("timezone", "")
            result["lat"]      = d.get("lat")
            result["lon"]      = d.get("lon")
            result["is_proxy"] = d.get("proxy", False)
            result["is_vpn"]   = d.get("hosting", False)
            result["as_name"]  = d.get("as", "")
        except Exception:
            pass

    try:
        result["reverse_dns"] = socket.gethostbyaddr(ip)[0]
    except Exception:
        result["reverse_dns"] = ""

    raw_ports = _port_scan(ip)
    result["ports"] = raw_ports
    result["open_ports"] = [
        {"port": p["port"], "service": _PORT_SERVICES.get(p["port"], "?"), "open": True}
        for p in raw_ports if p["open"]
    ]

    # AbuseIPDB reputation
    result["reputation"] = abuseipdb_check(ip)

    # VirusTotal IP reputation
    result["virustotal"] = virustotal_check(ip, kind="ip")

    # ipinfo.io — ASN, org, hosting flag
    result["ipinfo"] = ipinfo_check(ip)

    # BGP/ASN prefix routing
    result["bgp"] = bgp_asn_lookup(ip)

    # OTX AlienVault IoC
    result["otx"] = otx_check(ip, kind="ip")

    return result


# ─────────────────────────────────────────────
# PHONE OSINT
# ─────────────────────────────────────────────
INDONESIA_PREFIXES = {}
for p in list(range(811,814))+list(range(821,824))+[852,853]:
    INDONESIA_PREFIXES[str(p)] = "Telkomsel"
for p in [814,815,816,856,857,858]:
    INDONESIA_PREFIXES[str(p)] = "Indosat Ooredoo"
for p in [817,818,819,877,878]:
    INDONESIA_PREFIXES[str(p)] = "XL Axiata"
for p in [895,896,897,898,899]:
    INDONESIA_PREFIXES[str(p)] = "Tri (3)"
for p in list(range(881,890)):
    INDONESIA_PREFIXES[str(p)] = "Smartfren"
INDONESIA_PREFIXES.update({"831":"Axis (XL)","832":"Axis (XL)","833":"Axis (XL)","838":"Axis (XL)"})
INDONESIA_PREFIXES.update({"851":"Telkomsel (By.U)","855":"Indosat Ooredoo"})

def phone_osint(phone: str) -> dict:
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)
    result = {"ok": True, "type": "phone", "query": phone,
              "input": phone, "cleaned": cleaned}

    if cleaned.startswith("62") or cleaned.startswith("08") or (cleaned.startswith("8") and len(cleaned) >= 9):
        result["country"] = "Indonesia"
        result["country_code"] = "+62"
        local = "0" + cleaned[2:] if cleaned.startswith("62") else \
                ("0" + cleaned if cleaned.startswith("8") else cleaned)
        result["local_format"] = local
        result["local_number"] = local  # frontend alias
        result["format_local"] = local  # frontend alias
        e164 = "+62" + local[1:]
        result["e164"] = e164
        result["format_e164"] = e164   # frontend alias
        prefix3 = local[1:4]
        prefix2 = local[1:3]
        carrier = INDONESIA_PREFIXES.get(prefix3) or INDONESIA_PREFIXES.get(prefix2) or "Unknown"
        result["carrier"] = carrier
        result["detected_carrier"] = carrier  # frontend alias
        result["length_valid"] = 9 <= len(local) <= 13
        result["possible_wa"] = True
        result["possible_carriers"] = [carrier] if carrier != "Unknown" else []
    elif cleaned.startswith("1") and len(cleaned) == 11:
        result["country"] = "United States / Canada"
        result["country_code"] = "+1"
        e164 = "+" + cleaned
        result["e164"] = e164
        result["format_e164"] = e164
        result["local_number"] = cleaned[1:]
        result["local_format"] = cleaned[1:]
        result["format_local"] = cleaned[1:]
    elif cleaned.startswith("44"):
        result["country"] = "United Kingdom"
        result["country_code"] = "+44"
        e164 = "+" + cleaned
        result["e164"] = e164
        result["format_e164"] = e164
        result["local_number"] = "0" + cleaned[2:]
        result["format_local"] = "0" + cleaned[2:]
    elif cleaned.startswith("65"):
        result["country"] = "Singapore"
        result["country_code"] = "+65"
        e164 = "+" + cleaned
        result["e164"] = e164
        result["format_e164"] = e164
        result["local_number"] = cleaned[2:]
        result["format_local"] = cleaned[2:]
    elif cleaned.startswith("60"):
        result["country"] = "Malaysia"
        result["country_code"] = "+60"
        e164 = "+" + cleaned
        result["e164"] = e164
        result["format_e164"] = e164
        result["local_number"] = "0" + cleaned[2:]
        result["format_local"] = "0" + cleaned[2:]
    else:
        result["country"] = "Unknown"
        e164 = "+" + cleaned
        result["e164"] = e164
        result["format_e164"] = e164
        result["local_number"] = cleaned
        result["format_local"] = cleaned

    return result


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _dns_query(domain, qtype):
    try:
        if qtype == "A":
            addrs = socket.getaddrinfo(domain, None, socket.AF_INET)
            return list({a[4][0] for a in addrs})
        elif qtype == "AAAA":
            try:
                addrs = socket.getaddrinfo(domain, None, socket.AF_INET6)
                return list({a[4][0] for a in addrs})
            except Exception:
                return []
        else:
            import subprocess
            r = subprocess.run(["nslookup", f"-type={qtype}", domain],
                               capture_output=True, text=True, timeout=5)
            lines = r.stdout.splitlines()
            results = []
            for line in lines:
                if "=" in line and any(k in line.lower() for k in
                    ["mail","name server","canonical","text","server"]):
                    results.append(line.split("=")[-1].strip())
            return results
    except Exception:
        return []

def _ssl_info(domain):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                return {
                    "subject": dict(x[0] for x in cert.get("subject", [])),
                    "issuer": dict(x[0] for x in cert.get("issuer", [])),
                    "not_before": cert.get("notBefore", ""),
                    "not_after": cert.get("notAfter", ""),
                    "san": [v for t, v in cert.get("subjectAltName", []) if t == "DNS"],
                }
    except Exception as e:
        return {"error": str(e)}

def _whois(domain):
    tld = domain.split(".")[-1].lower()
    servers = {
        "com":"whois.verisign-grs.com","net":"whois.verisign-grs.com",
        "org":"whois.pir.org","io":"whois.nic.io",
        "id":"whois.pandi.or.id","co":"whois.nic.co",
        "info":"whois.afilias.net","me":"whois.nic.me",
        "dev":"whois.nic.google","app":"whois.nic.google","ai":"whois.nic.ai",
    }
    server = servers.get(tld, "whois.iana.org")
    try:
        with socket.create_connection((server, 43), timeout=8) as s:
            s.sendall((domain + "\r\n").encode())
            raw = b""
            while True:
                chunk = s.recv(4096)
                if not chunk: break
                raw += chunk
            text = raw.decode("utf-8", errors="ignore")
            parsed = {}
            for line in text.splitlines():
                for key in ["Registrar:","Creation Date","Updated Date",
                            "Registry Expiry Date","Name Server","DNSSEC:","Status:"]:
                    if line.strip().startswith(key):
                        k = key.rstrip(":")
                        v = line.split(":", 1)[-1].strip()
                        if k in parsed:
                            if isinstance(parsed[k], list): parsed[k].append(v)
                            else: parsed[k] = [parsed[k], v]
                        else:
                            parsed[k] = v
            return {"parsed": parsed, "raw": text[:3000]}
    except Exception as e:
        return {"error": str(e), "raw": ""}

def _crtsh(domain):
    try:
        status, body = _fetch(f"https://crt.sh/?q=%25.{domain}&output=json", timeout=10)
        if status == 200 and body:
            data = json.loads(body)
            subs = set()
            for entry in data:
                for n in entry.get("name_value", "").splitlines():
                    n = n.strip().lstrip("*.")
                    if domain in n:
                        subs.add(n)
            return sorted(subs)
    except Exception:
        pass
    return []

def _port_scan(host, ports=None):
    if ports is None:
        ports = [21,22,23,25,53,80,110,143,443,445,
                 3306,3389,5432,6379,8080,8443,8888,27017]
    def check(port):
        try:
            with socket.create_connection((host, port), timeout=1):
                return {"port": port, "open": True}
        except Exception:
            return {"port": port, "open": False}
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        return list(ex.map(check, ports))

def _http_headers(domain):
    for scheme in ["https", "http"]:
        try:
            req = urllib.request.Request(f"{scheme}://{domain}", headers=_HEADERS, method="HEAD")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                return dict(r.headers)
        except Exception:
            continue
    return {}

# ─────────────────────────────────────────────
# GITHUB HARVEST
# ─────────────────────────────────────────────
def github_harvest(username: str) -> dict:
    """Ambil profil publik + email tersembunyi dari commit history GitHub."""
    result = {"ok": False, "username": username, "emails": [], "profile": {}}
    headers = {**_HEADERS, "Accept": "application/vnd.github+json"}

    # Profil publik
    status, body = _fetch(f"https://api.github.com/users/{urllib.parse.quote(username)}", timeout=8)
    if status == 200:
        try:
            p = json.loads(body)
            result["profile"] = {
                "name": p.get("name") or "",
                "bio": p.get("bio") or "",
                "company": p.get("company") or "",
                "location": p.get("location") or "",
                "blog": p.get("blog") or "",
                "email": p.get("email") or "",
                "followers": p.get("followers", 0),
                "following": p.get("following", 0),
                "public_repos": p.get("public_repos", 0),
                "created_at": p.get("created_at") or "",
                "avatar_url": p.get("avatar_url") or "",
                "html_url": p.get("html_url") or "",
            }
            if p.get("email"):
                result["emails"].append(p["email"])
            result["ok"] = True
        except Exception:
            pass

    # Events API — ambil email dari push events
    ev_status, ev_body = _fetch(
        f"https://api.github.com/users/{urllib.parse.quote(username)}/events/public?per_page=30",
        timeout=8
    )
    if ev_status == 200:
        try:
            events = json.loads(ev_body)
            email_pat = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
            found_emails = set(result["emails"])
            for ev in events:
                if ev.get("type") == "PushEvent":
                    for commit in ev.get("payload", {}).get("commits", []):
                        author = commit.get("author", {})
                        email = author.get("email", "")
                        if email and "noreply" not in email and email not in found_emails:
                            found_emails.add(email)
                # Also scan raw JSON for email patterns
                raw = json.dumps(ev)
                for m in email_pat.findall(raw):
                    if "noreply" not in m and m not in found_emails:
                        found_emails.add(m)
            result["emails"] = list(found_emails)
        except Exception:
            pass

    # Repos API — ambil list repo publik
    repo_status, repo_body = _fetch(
        f"https://api.github.com/users/{urllib.parse.quote(username)}/repos?per_page=10&sort=updated",
        timeout=8
    )
    if repo_status == 200:
        try:
            repos = json.loads(repo_body)
            result["repos"] = [
                {"name": r.get("name"), "description": r.get("description"),
                 "stars": r.get("stargazers_count", 0), "url": r.get("html_url")}
                for r in repos[:10]
            ]
        except Exception:
            result["repos"] = []

    return result


# ─────────────────────────────────────────────
# WAYBACK MACHINE CHECK
# ─────────────────────────────────────────────
def wayback_check(target: str) -> dict:
    """Cek riwayat snapshot di Wayback Machine."""
    # Bersihkan URL/domain
    clean = target.strip().lstrip("https://").lstrip("http://").split("/")[0]
    url_to_check = target if target.startswith("http") else f"https://{target}"

    result = {"ok": False, "target": target, "snapshots": [], "first_seen": "", "last_seen": "", "total": 0}

    # CDX API — ambil 10 snapshot terakhir
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx"
        f"?url={urllib.parse.quote(url_to_check)}&output=json&limit=10"
        f"&fl=timestamp,original,statuscode&collapse=timestamp:6&from=&to="
    )
    status, body = _fetch(cdx_url, timeout=12)
    if status == 200 and body.strip():
        try:
            rows = json.loads(body)
            if rows and len(rows) > 1:
                rows = rows[1:]  # skip header row
                snaps = []
                for row in rows:
                    if len(row) >= 3:
                        ts, orig, sc = row[0], row[1], row[2]
                        year = ts[:4]; mo = ts[4:6]; day = ts[6:8]
                        hh = ts[8:10]; mm = ts[10:12]; ss = ts[12:14]
                        dt_str = f"{year}-{mo}-{day} {hh}:{mm}:{ss}"
                        wb_url = f"https://web.archive.org/web/{ts}/{orig}"
                        snaps.append({"timestamp": dt_str, "status": sc, "url": wb_url})
                result["snapshots"] = snaps
                result["ok"] = True
        except Exception:
            pass

    # CDX API untuk count total
    count_url = (
        f"https://web.archive.org/cdx/search/cdx"
        f"?url={urllib.parse.quote(url_to_check)}&output=json&limit=1"
        f"&fl=timestamp&showNumPages=true"
    )
    cs, cb = _fetch(count_url, timeout=8)
    if cs == 200 and cb.strip():
        try:
            result["total"] = int(cb.strip())
        except Exception:
            pass

    if result["snapshots"]:
        result["first_seen"] = result["snapshots"][-1]["timestamp"]
        result["last_seen"]  = result["snapshots"][0]["timestamp"]

    return result


# ─────────────────────────────────────────────
# BREACH CHECK (HIBP)
# ─────────────────────────────────────────────
def breach_check(email: str) -> dict:
    """Cek email kena data breach via HaveIBeenPwned API."""
    result = {"ok": False, "email": email, "breaches": [], "pastes": [],
              "breach_count": 0, "note": ""}

    # Coba tanpa API key dulu (HIBP v2 endpoint lama, mungkin masih aktif)
    # Header hibp-api-key diperlukan untuk v3
    hibp_key = ""
    try:
        import os as _os
        hibp_key = _os.environ.get("HIBP_API_KEY", "").strip()
    except Exception:
        pass

    if not hibp_key:
        result["note"] = "HIBP_API_KEY tidak diset. Set env var HIBP_API_KEY untuk cek breach aktif."
        # Fallback: cek Gravatar saja (indikasi tidak langsung)
        h = hashlib.md5(email.strip().lower().encode()).hexdigest()
        g_status, _ = _fetch(f"https://www.gravatar.com/avatar/{h}?d=404")
        result["has_gravatar"] = g_status == 200
        result["gravatar_url"] = f"https://www.gravatar.com/avatar/{h}"
        result["ok"] = True
        return result

    headers = {
        **_HEADERS,
        "hibp-api-key": hibp_key,
        "User-Agent": "TFAEL-OMNI-OSINT/3.0",
    }
    try:
        req = urllib.request.Request(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.parse.quote(email)}?truncateResponse=false",
            headers=headers
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            if r.status == 200:
                data = json.loads(r.read().decode())
                result["breaches"] = [
                    {"name": b.get("Name"), "domain": b.get("Domain"),
                     "date": b.get("BreachDate"), "count": b.get("PwnCount", 0),
                     "data_classes": b.get("DataClasses", [])}
                    for b in data
                ]
                result["breach_count"] = len(data)
                result["ok"] = True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            result["ok"] = True
            result["note"] = "Email tidak ditemukan di database breach."
        elif e.code == 401:
            result["note"] = "HIBP API key tidak valid."
        else:
            result["note"] = f"HIBP error: HTTP {e.code}"
    except Exception as ex:
        result["note"] = f"Error: {ex}"

    # Paste check
    try:
        req2 = urllib.request.Request(
            f"https://haveibeenpwned.com/api/v3/pasteaccount/{urllib.parse.quote(email)}",
            headers=headers
        )
        ctx2 = ssl.create_default_context()
        with urllib.request.urlopen(req2, timeout=10, context=ctx2) as r2:
            if r2.status == 200:
                pastes = json.loads(r2.read().decode())
                result["pastes"] = [
                    {"source": p.get("Source"), "id": p.get("Id"), "date": p.get("Date")}
                    for p in (pastes or [])
                ]
    except Exception:
        pass

    return result


# ─────────────────────────────────────────────
# NAME OSINT — Dork Generator + Email Permutation
# ─────────────────────────────────────────────
def name_osint(name: str) -> dict:
    """OSINT untuk nama lengkap: dork queries + email permutations."""
    parts = name.strip().split()
    if not parts:
        return {"ok": False, "error": "Nama diperlukan"}

    first = parts[0].lower()
    last  = parts[-1].lower() if len(parts) > 1 else ""
    mid   = parts[1].lower() if len(parts) > 2 else ""
    fl    = (first[0] + last) if last else first
    lf    = (last[0] + first) if last else first
    fn_ln = (first + last)   if last else first
    fn_dot_ln = (first + "." + last) if last else first

    # ── Google Dork Queries ───────────────────────────────────────────────
    quoted = f'"{name}"'
    dorks = []

    if last:
        dorks += [
            {"label": "Social Media",
             "query": f'{quoted} site:instagram.com OR site:facebook.com OR site:linkedin.com OR site:twitter.com OR site:tiktok.com',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " site:instagram.com OR site:facebook.com OR site:linkedin.com OR site:twitter.com OR site:tiktok.com")}'},
            {"label": "LinkedIn Profile",
             "query": f'{quoted} site:linkedin.com/in',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " site:linkedin.com/in")}'},
            {"label": "Email Leak",
             "query": f'{quoted} "@gmail.com" OR "@yahoo.com" OR "@hotmail.com" OR "email"',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " email gmail yahoo")}'},
            {"label": "Dokumen Publik",
             "query": f'{quoted} filetype:pdf OR filetype:doc OR filetype:xls',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " filetype:pdf OR filetype:doc")}'},
            {"label": "Forum & Blog",
             "query": f'{quoted} site:kaskus.co.id OR site:reddit.com OR site:quora.com OR site:medium.com',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " site:kaskus.co.id OR site:reddit.com OR site:quora.com")}'},
            {"label": "Nomor Telepon",
             "query": f'{quoted} "08" OR "62" OR "phone" OR "telepon" OR "hp" OR "wa"',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " 08 62 phone telepon hp")}'},
            {"label": "Alamat / Lokasi",
             "query": f'{quoted} "alamat" OR "address" OR "tinggal di" OR "domisili" OR "RT" OR "RW"',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " alamat address tinggal domisili")}'},
            {"label": "Berita & Artikel",
             "query": f'{quoted} site:kompas.com OR site:detik.com OR site:tribunnews.com OR site:cnnindonesia.com',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " site:kompas.com OR site:detik.com OR site:tribunnews.com")}'},
            {"label": "Pastebin / Leak",
             "query": f'{quoted} site:pastebin.com OR site:paste.ee OR site:ghostbin.com',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted + " site:pastebin.com OR site:paste.ee")}'},
            {"label": "Image Search",
             "query": f'Google Images: {name}',
             "url": f'https://www.google.com/search?q={urllib.parse.quote(name)}&tbm=isch'},
        ]
    else:
        dorks.append({
            "label": "General Search",
            "query": f'{quoted}',
            "url": f'https://www.google.com/search?q={urllib.parse.quote(quoted)}'
        })

    # ── Email Permutations ────────────────────────────────────────────────
    candidates = []
    if last:
        candidates = list({
            fn_ln, fn_dot_ln, f"{first}_{last}", fl, lf,
            f"{first}{last[0]}", f"{first[0]}{last}",
            f"{first}.{last[0]}", f"{first[0]}.{last}",
        })
    else:
        candidates = [first]

    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
               "ymail.com", "icloud.com", "protonmail.com"]
    perms = [f"{c}@{d}" for d in domains for c in candidates]

    # Verifikasi Gravatar untuk setiap permutasi (cepat)
    def _check_gravatar(email_addr):
        h = hashlib.md5(email_addr.strip().lower().encode()).hexdigest()
        s, _ = _fetch(f"https://www.gravatar.com/avatar/{h}?d=404", timeout=4)
        return {"email": email_addr, "has_gravatar": s == 200,
                "gravatar_url": f"https://www.gravatar.com/avatar/{h}"}

    verified_perms = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_check_gravatar, p): p for p in perms[:30]}
        for fut in concurrent.futures.as_completed(futures):
            try:
                r = fut.result()
                if r["has_gravatar"]:
                    verified_perms.append(r)
            except Exception:
                pass

    return {
        "ok": True,
        "type": "name",
        "query": name,
        "name": name,
        "parts": {"first": first, "last": last, "middle": mid},
        "dorks": dorks,
        "email_permutations": perms[:30],
        "gravatar_hits": sorted(verified_perms, key=lambda x: x["email"]),
        "username_candidates": list({fn_ln, fn_dot_ln.replace(".", ""), fl, lf, f"{first}{last[0] if last else ''}"}),
    }


# ─────────────────────────────────────────────
# PASTEBIN SEARCH
# ─────────────────────────────────────────────
def pastebin_search(query: str) -> dict:
    """Generate dork links untuk cari target di paste sites."""
    q = urllib.parse.quote(f'"{query}"')
    sites = [
        ("Pastebin",   f"https://www.google.com/search?q={q}+site:pastebin.com"),
        ("Paste.ee",   f"https://www.google.com/search?q={q}+site:paste.ee"),
        ("Ghostbin",   f"https://www.google.com/search?q={q}+site:ghostbin.com"),
        ("Rentry",     f"https://www.google.com/search?q={q}+site:rentry.co"),
        ("Hastebin",   f"https://www.google.com/search?q={q}+site:hastebin.com"),
        ("Dpaste",     f"https://www.google.com/search?q={q}+site:dpaste.com"),
    ]
    return {
        "ok": True,
        "query": query,
        "dork_links": [{"site": s, "url": u} for s, u in sites],
        "note": "Klik link untuk buka Google dengan filter site paste. Hasil aktual tergantung indexing Google.",
    }


# ─────────────────────────────────────────────
# KNOWLEDGE GRAPH BUILDER
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# ABUSEIPDB CHECK
# ─────────────────────────────────────────────
def abuseipdb_check(ip: str) -> dict:
    """Cek reputasi IP di AbuseIPDB. Butuh env ABUSEIPDB_API_KEY; fallback ke greylist check."""
    import os
    result = {"ok": False, "ip": ip, "score": 0, "reports": 0, "country": "", "isp": "", "note": ""}
    api_key = os.environ.get("ABUSEIPDB_API_KEY", "").strip()
    if not api_key:
        _kf = os.path.join(os.path.dirname(__file__), "abuseipdb.key")
        if os.path.isfile(_kf):
            try:
                with open(_kf) as _f: api_key = _f.read().strip()
            except Exception: pass
    if api_key:
        try:
            url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={urllib.parse.quote(ip)}&maxAgeInDays=90&verbose"
            req = urllib.request.Request(url, headers={
                "Key": api_key, "Accept": "application/json",
                "User-Agent": _HEADERS["User-Agent"]
            })
            ctx = ssl.create_default_context()
            ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
                d = json.loads(r.read(65536).decode())["data"]
                result.update({
                    "ok": True, "score": d.get("abuseConfidenceScore", 0),
                    "reports": d.get("totalReports", 0), "country": d.get("countryCode", ""),
                    "isp": d.get("isp", ""), "domain": d.get("domain", ""),
                    "is_tor": d.get("isTor", False), "last_reported": d.get("lastReportedAt", ""),
                    "usage_type": d.get("usageType", ""), "source": "AbuseIPDB"
                })
        except Exception as e:
            result["note"] = f"AbuseIPDB error: {e}"
    else:
        # Fallback: GreyNoise community (no key needed)
        try:
            status, body = _fetch(f"https://api.greynoise.io/v3/community/{ip}", timeout=6)
            if status == 200 and body:
                d = json.loads(body)
                result.update({
                    "ok": True, "score": 100 if d.get("noise") else 0,
                    "reports": 0, "country": "",
                    "classification": d.get("classification", "unknown"),
                    "name": d.get("name", ""), "noise": d.get("noise", False),
                    "riot": d.get("riot", False), "source": "GreyNoise Community",
                    "note": d.get("message", "")
                })
        except Exception:
            result["note"] = "Set env ABUSEIPDB_API_KEY untuk hasil lebih akurat."
    return result


# ─────────────────────────────────────────────
# VIRUSTOTAL CHECK
# ─────────────────────────────────────────────
def virustotal_check(indicator: str, kind: str = "domain") -> dict:
    """Cek reputasi domain/IP di VirusTotal. Butuh env VIRUSTOTAL_API_KEY atau backend/virustotal.key."""
    import os, hashlib
    result = {"ok": False, "indicator": indicator, "kind": kind,
              "malicious": 0, "suspicious": 0, "harmless": 0, "undetected": 0,
              "total_engines": 0, "verdict": "unknown", "categories": [], "note": ""}

    api_key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    if not api_key:
        _kf = os.path.join(os.path.dirname(__file__), "virustotal.key")
        if os.path.isfile(_kf):
            try:
                with open(_kf) as _f: api_key = _f.read().strip()
            except Exception: pass

    if not api_key:
        result["note"] = "Set env VIRUSTOTAL_API_KEY atau simpan key di backend/virustotal.key"
        return result

    try:
        if kind == "ip":
            url = f"https://www.virustotal.com/api/v3/ip_addresses/{urllib.parse.quote(indicator)}"
        elif kind == "domain":
            url = f"https://www.virustotal.com/api/v3/domains/{urllib.parse.quote(indicator)}"
        else:
            # URL / hash
            _id = hashlib.sha256(indicator.encode()).hexdigest() if not indicator.startswith("http") else \
                  hashlib.sha256(indicator.encode()).hexdigest()
            url = f"https://www.virustotal.com/api/v3/urls/{_id}"

        req = urllib.request.Request(url, headers={
            "x-apikey": api_key,
            "Accept": "application/json",
            "User-Agent": _HEADERS["User-Agent"],
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read(131072).decode())

        stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        mal  = stats.get("malicious", 0)
        sus  = stats.get("suspicious", 0)
        har  = stats.get("harmless", 0)
        undet = stats.get("undetected", 0)
        total = mal + sus + har + undet

        cats_raw = data.get("data", {}).get("attributes", {}).get("categories", {})
        cats = list(set(cats_raw.values())) if isinstance(cats_raw, dict) else []

        if mal > 0:     verdict = "MALICIOUS"
        elif sus > 0:   verdict = "SUSPICIOUS"
        elif har > 0:   verdict = "CLEAN"
        else:           verdict = "UNKNOWN"

        result.update({
            "ok": True, "malicious": mal, "suspicious": sus,
            "harmless": har, "undetected": undet,
            "total_engines": total, "verdict": verdict,
            "categories": cats[:5], "source": "VirusTotal",
            "note": f"{mal}/{total} engine mendeteksi ancaman" if mal else f"0/{total} engine — bersih",
        })
    except urllib.error.HTTPError as e:
        result["note"] = f"VT API error {e.code}: {'Key tidak valid' if e.code == 401 else 'Limit tercapai' if e.code == 429 else str(e)}"
    except Exception as e:
        result["note"] = f"VT error: {type(e).__name__}"
    return result


# ─────────────────────────────────────────────
# IPINFO.IO — IP enrichment (gratis, no key)
# ─────────────────────────────────────────────
def ipinfo_check(ip: str) -> dict:
    """IP → ASN, org, geolokasi, hosting via ipinfo.io (gratis tanpa key)."""
    import os
    result = {"ok": False, "ip": ip, "asn": "", "org": "", "hostname": "",
              "country": "", "region": "", "city": "", "postal": "",
              "timezone": "", "is_hosting": False, "note": ""}
    token = os.environ.get("IPINFO_TOKEN", "").strip()
    if not token:
        _kf = os.path.join(os.path.dirname(__file__), "ipinfo.key")
        if os.path.isfile(_kf):
            try:
                with open(_kf) as _f: token = _f.read().strip()
            except Exception: pass
    url = f"https://ipinfo.io/{ip}/json"
    if token:
        url += f"?token={token}"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": _HEADERS["User-Agent"],
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read(65536).decode())
        org = data.get("org", "")  # "AS13335 Cloudflare, Inc."
        asn = ""
        if org and org.startswith("AS"):
            parts = org.split(" ", 1)
            asn = parts[0]
            org = parts[1] if len(parts) > 1 else org
        hosting = data.get("hosting", {})
        is_hosting = hosting.get("hosting", False) or hosting.get("vpn", False) if isinstance(hosting, dict) else False
        result.update({
            "ok": True,
            "asn": asn,
            "org": org,
            "hostname": data.get("hostname", ""),
            "country": data.get("country", ""),
            "region": data.get("region", ""),
            "city": data.get("city", ""),
            "postal": data.get("postal", ""),
            "timezone": data.get("timezone", ""),
            "is_hosting": is_hosting,
            "source": "ipinfo.io",
        })
    except urllib.error.HTTPError as e:
        result["note"] = f"ipinfo error {e.code}"
    except Exception as e:
        result["note"] = f"ipinfo error: {type(e).__name__}"
    return result


# ─────────────────────────────────────────────
# BGP / ASN LOOKUP — bgpview.io (gratis, no key)
# ─────────────────────────────────────────────
def bgp_asn_lookup(ip: str) -> dict:
    """ASN, prefix, country via Team Cymru whois (gratis, no key, via socket port 43)."""
    result = {"ok": False, "ip": ip, "asn": None, "asn_name": "",
              "prefix": "", "country_code": "", "registry": "", "note": ""}
    try:
        # Team Cymru bulk whois — format: ASN | IP | PREFIX | COUNTRY | REGISTRY | DATE | ORG
        with socket.create_connection(("whois.cymru.com", 43), timeout=8) as s:
            s.sendall(f"begin\nverbose\n{ip}\nend\n".encode())
            raw = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                raw += chunk
        lines = raw.decode(errors="replace").strip().splitlines()
        # Keep only data lines (pipe-delimited, not header/status lines)
        data_lines = [l for l in lines if "|" in l and not l.strip().startswith("AS |")]
        if data_lines:
            parts = [p.strip() for p in data_lines[0].split("|")]
            if len(parts) >= 6:
                result.update({
                    "ok": True,
                    "asn": parts[0] if parts[0] != "NA" else None,
                    "ip": parts[1] if len(parts) > 1 else ip,
                    "prefix": parts[2] if len(parts) > 2 else "",
                    "country_code": parts[3] if len(parts) > 3 else "",
                    "registry": parts[4] if len(parts) > 4 else "",
                    "asn_name": parts[6] if len(parts) > 6 else "",
                    "source": "Team Cymru Whois",
                })
        else:
            result["note"] = "Tidak ada data BGP"
    except socket.timeout:
        result["note"] = "BGP lookup timeout"
    except Exception as e:
        result["note"] = f"BGP error: {type(e).__name__}"
    return result


# ─────────────────────────────────────────────
# OTX ALIENVAULT — threat intel IoC (gratis, butuh free key)
# ─────────────────────────────────────────────
def otx_check(indicator: str, kind: str = "domain") -> dict:
    """IoC check via OTX AlienVault (gratis). Daftar di otx.alienvault.com, simpan key di backend/otx.key."""
    import os
    result = {"ok": False, "indicator": indicator, "kind": kind,
              "pulse_count": 0, "threat_score": 0, "malware_families": [],
              "adversaries": [], "tags": [], "verdict": "unknown", "note": ""}
    api_key = os.environ.get("OTX_API_KEY", "").strip()
    if not api_key:
        _kf = os.path.join(os.path.dirname(__file__), "otx.key")
        if os.path.isfile(_kf):
            try:
                with open(_kf) as _f: api_key = _f.read().strip()
            except Exception: pass
    if not api_key:
        result["note"] = "Daftar gratis di otx.alienvault.com lalu simpan key di backend/otx.key"
        return result
    try:
        if kind == "ip":
            url = f"https://otx.alienvault.com/api/v1/indicators/IPv4/{urllib.parse.quote(indicator)}/general"
        elif kind == "domain":
            url = f"https://otx.alienvault.com/api/v1/indicators/domain/{urllib.parse.quote(indicator)}/general"
        elif kind == "url":
            url = f"https://otx.alienvault.com/api/v1/indicators/url/{urllib.parse.quote(indicator, safe='')}/general"
        else:
            url = f"https://otx.alienvault.com/api/v1/indicators/domain/{urllib.parse.quote(indicator)}/general"
        req = urllib.request.Request(url, headers={
            "X-OTX-API-KEY": api_key,
            "Accept": "application/json",
            "User-Agent": _HEADERS["User-Agent"],
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read(131072).decode())
        pulse_info = data.get("pulse_info", {})
        pulses = pulse_info.get("count", 0)
        # Collect malware families and adversaries from pulse references
        refs = pulse_info.get("references", [])
        malware = list({m for m in data.get("malware_families", [])})[:5]
        adversaries = list({a for a in data.get("adversary", []) if a})[:5]
        tags_raw = []
        for tag_list in pulse_info.get("tags", []):
            if isinstance(tag_list, list):
                tags_raw.extend(tag_list)
            elif isinstance(tag_list, str):
                tags_raw.append(tag_list)
        tags = list(set(tags_raw))[:10]
        # Threat score based on pulse count
        if pulses == 0:     verdict = "CLEAN"
        elif pulses < 3:    verdict = "SUSPICIOUS"
        else:               verdict = "MALICIOUS"
        threat_score = min(100, pulses * 10)
        result.update({
            "ok": True,
            "pulse_count": pulses,
            "threat_score": threat_score,
            "malware_families": malware,
            "adversaries": adversaries,
            "tags": tags,
            "verdict": verdict,
            "source": "OTX AlienVault",
            "note": (f"{pulses} pulse IoC ditemukan" if pulses else "Tidak ada IoC ditemukan"),
        })
    except urllib.error.HTTPError as e:
        result["note"] = f"OTX error {e.code}: {'Key tidak valid' if e.code == 403 else str(e)}"
    except Exception as e:
        result["note"] = f"OTX error: {type(e).__name__}"
    return result


# ─────────────────────────────────────────────
# EMAIL HEADER ANALYZER
# ─────────────────────────────────────────────
def email_header_analyze(raw_header: str) -> dict:
    """Parse raw email header: ekstrak hop routing, IP originator, SPF/DKIM/DMARC."""
    result = {"ok": True, "type": "email_header", "hops": [], "ips": [], "spf": "", "dkim": "", "dmarc": "", "subject": "", "from": "", "to": "", "date": ""}

    # Normalize line endings
    raw = raw_header.replace("\r\n", "\n").replace("\r", "\n")

    # Extract simple headers
    for field in ["Subject", "From", "To", "Date", "Message-ID"]:
        m = re.search(rf"^{field}:\s*(.+?)(?=\n\S|\Z)", raw, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if m:
            result[field.lower()] = m.group(1).replace("\n\t", " ").replace("\n ", " ").strip()[:300]

    # SPF / DKIM / DMARC from Authentication-Results
    auth_m = re.search(r"Authentication-Results:(.+?)(?=\n\S|\Z)", raw, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if auth_m:
        auth_str = auth_m.group(1)
        for proto in ["spf", "dkim", "dmarc"]:
            pm = re.search(rf"{proto}=(\w+)", auth_str, re.IGNORECASE)
            result[proto] = pm.group(1).lower() if pm else "tidak ada"
    else:
        # Try Received-SPF
        spf_m = re.search(r"Received-SPF:\s*(\w+)", raw, re.IGNORECASE)
        result["spf"] = spf_m.group(1).lower() if spf_m else "tidak ada"

    # Parse Received headers (hops) in reverse order = oldest first
    received_blocks = re.findall(r"^Received:(.+?)(?=\nReceived:|\nFrom:|\nTo:|\nSubject:|\nDate:|\nMessage-ID:|\Z)", raw, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    hops = []
    seen_ips = set()
    for i, block in enumerate(reversed(received_blocks)):
        block_clean = block.replace("\n\t", " ").replace("\n ", " ").strip()
        # Extract IPs from block
        ips_in_block = re.findall(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", block_clean)
        # Extract "from" server name
        from_m = re.search(r"from\s+([\w\.\-]+)", block_clean, re.IGNORECASE)
        by_m   = re.search(r"by\s+([\w\.\-]+)",   block_clean, re.IGNORECASE)
        dt_m   = re.search(r";\s*(.{10,50})$",     block_clean)
        hop = {
            "hop": i + 1,
            "from": from_m.group(1) if from_m else "",
            "by":   by_m.group(1)   if by_m   else "",
            "date": dt_m.group(1).strip() if dt_m else "",
            "ips":  [ip for ip in ips_in_block if not ip.startswith(("127.", "10.", "192.168.", "172."))],
        }
        hops.append(hop)
        for ip in hop["ips"]:
            if ip not in seen_ips:
                seen_ips.add(ip)
                result["ips"].append(ip)
    result["hops"] = hops
    result["hop_count"] = len(hops)

    # Geo-resolve unique IPs (parallel, max 5)
    def _geo(ip):
        try:
            s, b = _fetch(f"http://ip-api.com/json/{ip}?fields=country,city,isp,org,lat,lon", timeout=5)
            if s == 200:
                d = json.loads(b)
                return {"ip": ip, **d}
        except Exception:
            pass
        return {"ip": ip}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        result["ip_details"] = list(ex.map(_geo, result["ips"][:8]))

    return result


# ─────────────────────────────────────────────
# METADATA EXTRACTOR (EXIF)
# ─────────────────────────────────────────────
def extract_metadata(file_bytes: bytes, filename: str) -> dict:
    """Ekstrak metadata EXIF/file tanpa library eksternal."""
    result = {"ok": False, "filename": filename, "size_bytes": len(file_bytes), "tags": {}, "gps": None, "note": ""}
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext in ("jpg", "jpeg"):
        result["format"] = "JPEG"
        try:
            # Find EXIF marker 0xFFE1
            idx = file_bytes.find(b'\xff\xe1')
            if idx == -1:
                result["note"] = "Tidak ada EXIF ditemukan"; result["ok"] = True; return result
            # Length of EXIF segment
            seg_len = int.from_bytes(file_bytes[idx+2:idx+4], "big")
            exif_data = file_bytes[idx+4:idx+2+seg_len]
            if exif_data[:4] != b"Exif":
                result["note"] = "Signature EXIF tidak valid"; result["ok"] = True; return result
            tiff = exif_data[6:]
            byte_order = tiff[:2]
            bo = "big" if byte_order == b"MM" else "little"
            def _u16(b, off): return int.from_bytes(b[off:off+2], bo)
            def _u32(b, off): return int.from_bytes(b[off:off+4], bo)
            def _rational(b, off):
                n = _u32(b, off); d = _u32(b, off+4)
                return n / d if d else 0
            ifd0_off = _u32(tiff, 4)
            tags_raw = {}
            TAG_NAMES = {
                0x010F: "Make", 0x0110: "Model", 0x0112: "Orientation",
                0x011A: "XResolution", 0x011B: "YResolution", 0x0128: "ResolutionUnit",
                0x0131: "Software", 0x0132: "DateTime", 0x013B: "Artist",
                0x8769: "ExifIFD", 0x8825: "GPSIFD",
                0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized",
                0xA420: "ImageUniqueID",
                0x0000: "GPSVersionID", 0x0001: "GPSLatitudeRef", 0x0002: "GPSLatitude",
                0x0003: "GPSLongitudeRef", 0x0004: "GPSLongitude",
                0x0005: "GPSAltitudeRef", 0x0006: "GPSAltitude",
                0x001D: "GPSDateStamp",
            }
            def _read_ifd(data, ifd_off, tag_filter=None):
                out = {}
                try:
                    n = _u16(data, ifd_off)
                    for i in range(n):
                        e = ifd_off + 2 + i*12
                        tag = _u16(data, e)
                        typ = _u16(data, e+2)
                        cnt = _u32(data, e+4)
                        val_off = e+8
                        if tag_filter and tag not in tag_filter: continue
                        try:
                            if typ == 2:  # ASCII
                                raw_len = min(cnt, 128)
                                if cnt > 4:
                                    off2 = _u32(data, val_off)
                                    val = data[off2:off2+raw_len].decode("ascii", errors="ignore").rstrip("\x00")
                                else:
                                    val = data[val_off:val_off+raw_len].decode("ascii", errors="ignore").rstrip("\x00")
                            elif typ == 5:  # RATIONAL
                                off2 = _u32(data, val_off)
                                val = [_rational(data, off2 + j*8) for j in range(min(cnt,3))]
                            elif typ in (3,4):  # SHORT/LONG
                                val = _u16(data, val_off) if typ==3 else _u32(data, val_off)
                            else:
                                val = None
                            if val is not None:
                                out[tag] = val
                        except Exception:
                            pass
                except Exception:
                    pass
                return out
            ifd_tags = _read_ifd(tiff, ifd0_off)
            for tag, val in ifd_tags.items():
                name = TAG_NAMES.get(tag, f"0x{tag:04X}")
                tags_raw[name] = val
            # ExifIFD sub-IFD
            if 0x8769 in ifd_tags:
                exif_sub = _read_ifd(tiff, ifd_tags[0x8769])
                for tag, val in exif_sub.items():
                    name = TAG_NAMES.get(tag, f"0x{tag:04X}")
                    tags_raw[name] = val
            # GPS IFD
            gps_data = None
            if 0x8825 in ifd_tags:
                gps_tags = _read_ifd(tiff, ifd_tags[0x8825])
                lat_ref = gps_tags.get(1, "N")
                lat_r   = gps_tags.get(2)
                lon_ref = gps_tags.get(3, "E")
                lon_r   = gps_tags.get(4)
                alt_r   = gps_tags.get(6)
                if lat_r and lon_r and len(lat_r) >= 3:
                    lat = lat_r[0] + lat_r[1]/60 + lat_r[2]/3600
                    lon = lon_r[0] + lon_r[1]/60 + lon_r[2]/3600
                    if lat_ref == "S": lat = -lat
                    if lon_ref == "W": lon = -lon
                    gps_data = {"lat": round(lat, 7), "lon": round(lon, 7)}
                    if alt_r: gps_data["alt_m"] = round(alt_r, 2)
                    gps_data["date"] = gps_tags.get(29, "")
            tags_clean = {k: (round(v,4) if isinstance(v, float) else v) for k, v in tags_raw.items() if isinstance(v, (str, int, float)) and k not in ("ExifIFD","GPSIFD")}
            result.update({"ok": True, "tags": tags_clean, "gps": gps_data})
        except Exception as ex:
            result["note"] = f"Parse error: {ex}"; result["ok"] = True
    elif ext == "pdf":
        result["format"] = "PDF"
        try:
            text = file_bytes[:8192].decode("latin-1", errors="ignore")
            for field in ["Title", "Author", "Subject", "Creator", "Producer", "CreationDate", "ModDate"]:
                m = re.search(rf"/{field}\s*\(([^)]+)\)", text)
                if m: result["tags"][field] = m.group(1).strip()
            result["ok"] = True
        except Exception as ex:
            result["note"] = f"PDF parse error: {ex}"; result["ok"] = True
    elif ext in ("docx", "xlsx", "pptx"):
        result["format"] = ext.upper()
        # ZIP-based Office formats: read core.xml
        import zipfile, io
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for path in ["docProps/core.xml", "docProps/app.xml"]:
                    if path in z.namelist():
                        xml = z.read(path).decode("utf-8", errors="ignore")
                        for field in ["dc:title","dc:creator","dc:description","cp:lastModifiedBy","dcterms:created","dcterms:modified","AppVersion","Application"]:
                            fm = re.search(rf"<{re.escape(field)}[^>]*>([^<]+)</{re.escape(field)}>", xml)
                            if fm: result["tags"][field.split(":")[-1]] = fm.group(1).strip()
            result["ok"] = True
        except Exception as ex:
            result["note"] = f"Office parse error: {ex}"; result["ok"] = True
    else:
        result["format"] = ext.upper() or "UNKNOWN"
        result["note"] = "Format tidak didukung untuk ekstraksi metadata mendalam."
        result["ok"] = True

    return result


def build_knowledge_graph(osint_result: dict) -> dict:
    """Bangun knowledge graph (nodes + edges) dari hasil OSINT apapun."""
    nodes = {}  # id → {id, label, type, data}
    edges = []  # {source, target, label}

    def _add_node(nid, label, ntype, data=None):
        if nid and nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "type": ntype, "data": data or {}}
        return nid

    def _add_edge(src, tgt, label):
        if src and tgt and src != tgt:
            edges.append({"source": src, "target": tgt, "label": label})

    t = osint_result.get("type", "")
    query = osint_result.get("query", "")

    # ── USERNAME ────────────────────────────────────────────────────────────
    if t == "username":
        uid = f"user:{query}"
        _add_node(uid, query, "username")

        for p in osint_result.get("platforms", []):
            pid = f"platform:{p['platform']}"
            _add_node(pid, p["platform"], "platform", {"url": p.get("url",""), "confidence": "verified"})
            _add_edge(uid, pid, "akun ditemukan")

        for p in osint_result.get("unverified", []):
            pid = f"platform_uv:{p['platform']}"
            _add_node(pid, p["platform"], "platform_unverified", {"url": p.get("url",""), "confidence": "unverified"})
            _add_edge(uid, pid, "kemungkinan akun")

        gh = osint_result.get("github", {})
        if gh.get("ok") and gh.get("profile"):
            prof = gh["profile"]
            ghid = f"platform:GitHub"
            _add_node(ghid, "GitHub", "platform", {"url": prof.get("html_url",""), "confidence": "verified"})
            _add_edge(uid, ghid, "akun ditemukan")
            for email in gh.get("emails", []):
                eid = f"email:{email}"
                _add_node(eid, email, "email")
                _add_edge(ghid, eid, "email commit")
            if prof.get("location"):
                lid = f"location:{prof['location']}"
                _add_node(lid, prof["location"], "location")
                _add_edge(uid, lid, "berlokasi di")
            if prof.get("company"):
                cid = f"org:{prof['company']}"
                _add_node(cid, prof["company"], "organization")
                _add_edge(uid, cid, "bekerja di")

    # ── EMAIL ───────────────────────────────────────────────────────────────
    elif t == "email":
        email = osint_result.get("email", query)
        eid = f"email:{email}"
        _add_node(eid, email, "email")

        domain = osint_result.get("domain", "")
        if domain:
            did = f"domain:{domain}"
            _add_node(did, domain, "domain")
            _add_edge(eid, did, "domain email")

        prov = osint_result.get("mail_server_provider", "")
        if prov:
            pvid = f"org:{prov}"
            _add_node(pvid, prov, "organization")
            _add_edge(did if domain else eid, pvid, "mail provider")

        if osint_result.get("has_gravatar"):
            gid = "service:Gravatar"
            _add_node(gid, "Gravatar", "service")
            _add_edge(eid, gid, "profil aktif")

        breach = osint_result.get("breach", {})
        for b in breach.get("breaches", []):
            bid = f"breach:{b['name']}"
            _add_node(bid, b["name"], "breach", {"date": b.get("date",""), "count": b.get("count",0)})
            _add_edge(eid, bid, f"bocor {b.get('date','')}")

        for cand in osint_result.get("username_candidates", []):
            cuid = f"user:{cand}"
            _add_node(cuid, cand, "username")
            _add_edge(eid, cuid, "kandidat username")

    # ── DOMAIN ──────────────────────────────────────────────────────────────
    elif t == "domain":
        domain = osint_result.get("domain", query)
        did = f"domain:{domain}"
        _add_node(did, domain, "domain")

        for ip in osint_result.get("resolved_ips", []):
            iid = f"ip:{ip}"
            _add_node(iid, ip, "ip")
            _add_edge(did, iid, "resolve ke")

        ssl = osint_result.get("ssl_cert", {})
        issuer = (ssl.get("issuer") or {}).get("organizationName", "")
        if issuer:
            ssid = f"org:{issuer}"
            _add_node(ssid, issuer, "organization")
            _add_edge(did, ssid, "SSL issuer")

        for sub in (osint_result.get("subdomains_crtsh") or [])[:15]:
            sid = f"domain:{sub}"
            _add_node(sid, sub, "subdomain")
            _add_edge(did, sid, "subdomain")

        for p in osint_result.get("open_ports", []):
            portid = f"service:{domain}:{p['port']}"
            _add_node(portid, f"{p['service']} :{p['port']}", "service")
            _add_edge(did, portid, "port terbuka")

        whois = (osint_result.get("whois") or {}).get("parsed", {})
        registrar = whois.get("Registrar", "")
        if registrar:
            rid = f"org:{registrar}"
            _add_node(rid, str(registrar), "organization")
            _add_edge(did, rid, "registrar")

    # ── IP ──────────────────────────────────────────────────────────────────
    elif t == "ip":
        ip = osint_result.get("ip", query)
        iid = f"ip:{ip}"
        _add_node(iid, ip, "ip")

        geo = osint_result.get("geo", {})
        if geo.get("country"):
            cid = f"location:{geo['country']}"
            _add_node(cid, geo["country"], "location")
            _add_edge(iid, cid, "berlokasi di")
        if geo.get("isp"):
            ispid = f"org:{geo['isp']}"
            _add_node(ispid, geo["isp"], "organization")
            _add_edge(iid, ispid, "ISP")
        if geo.get("org") and geo.get("org") != geo.get("isp"):
            orgid = f"org:{geo['org']}"
            _add_node(orgid, geo["org"], "organization")
            _add_edge(iid, orgid, "organisasi")

        if osint_result.get("reverse_dns"):
            rdid = f"domain:{osint_result['reverse_dns']}"
            _add_node(rdid, osint_result["reverse_dns"], "domain")
            _add_edge(iid, rdid, "reverse DNS")

        for p in osint_result.get("open_ports", []):
            portid = f"service:{ip}:{p['port']}"
            _add_node(portid, f"{p['service']} :{p['port']}", "service")
            _add_edge(iid, portid, "port terbuka")

    # ── PHONE ───────────────────────────────────────────────────────────────
    elif t == "phone":
        phone = osint_result.get("format_e164", query)
        phid = f"phone:{phone}"
        _add_node(phid, phone, "phone")

        if osint_result.get("country"):
            cid = f"location:{osint_result['country']}"
            _add_node(cid, osint_result["country"], "location")
            _add_edge(phid, cid, "negara")
        if osint_result.get("detected_carrier"):
            carid = f"org:{osint_result['detected_carrier']}"
            _add_node(carid, osint_result["detected_carrier"], "organization")
            _add_edge(phid, carid, "carrier")

    # ── NAME ────────────────────────────────────────────────────────────────
    elif t == "name":
        name = osint_result.get("name", query)
        nid = f"person:{name}"
        _add_node(nid, name, "person")

        for cand in osint_result.get("username_candidates", []):
            cuid = f"user:{cand}"
            _add_node(cuid, cand, "username")
            _add_edge(nid, cuid, "kandidat username")

        for g in osint_result.get("gravatar_hits", []):
            eid = f"email:{g['email']}"
            _add_node(eid, g["email"], "email", {"has_gravatar": True})
            _add_edge(nid, eid, "kemungkinan email")

    return {
        "ok": True,
        "nodes": list(nodes.values()),
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


# ─────────────────────────────────────────────
# SMART SEARCH
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# PLAT NOMOR OSINT
# ─────────────────────────────────────────────

# Kode wilayah plat Indonesia → (provinsi, kota/kabupaten)
_PLATE_REGIONS = {
    "A":("Banten","Banten (Serang, Cilegon, Pandeglang, Lebak)"),
    "AA":("Jawa Tengah","Magelang, Temanggung, Wonosobo, Purworejo, Kebumen"),
    "AB":("DI Yogyakarta","Seluruh DIY"),
    "AD":("Jawa Tengah","Surakarta, Boyolali, Sukoharjo, Karanganyar, Sragen, Klaten, Wonogiri"),
    "AE":("Jawa Tengah","Madiun, Ngawi, Magetan, Ponorogo, Pacitan"),
    "AG":("Jawa Timur","Kediri, Tulungagung, Blitar, Nganjuk, Trenggalek"),
    "AKB":("Kalimantan Utara","Bulungan, Tana Tidung"),
    "B":("DKI Jakarta","Jakarta"),
    "BA":("Sumatera Barat","Seluruh Sumbar"),
    "BB":("Sumatera Utara","Tapanuli & Sibolga"),
    "BD":("Bengkulu","Seluruh Bengkulu"),
    "BE":("Lampung","Seluruh Lampung"),
    "BG":("Sumatera Selatan","Palembang, Musi Banyuasin, Banyuasin"),
    "BH":("Jambi","Seluruh Jambi"),
    "BK":("Sumatera Utara","Medan, Deli Serdang, Serdang Bedagai"),
    "BL":("Aceh","Seluruh Aceh"),
    "BM":("Riau","Pekanbaru, Kampar, Pelalawan, Siak"),
    "BN":("Bangka Belitung","Seluruh Babel"),
    "BP":("Kepulauan Riau","Batam, Tanjungpinang"),
    "C":("Jawa Barat","Cirebon"),
    "D":("Jawa Barat","Bandung, Cimahi, Bandung Barat, Sumedang"),
    "DA":("Kalimantan Selatan","Banjarmasin, Banjarbaru"),
    "DB":("Sulawesi Utara","Kotamobagu, Bolaang Mongondow"),
    "DC":("Sulawesi Barat","Seluruh Sulbar"),
    "DD":("Sulawesi Selatan","Makassar, Gowa, Maros, Pangkep"),
    "DE":("Maluku","Ambon, Maluku Tengah"),
    "DG":("Sulawesi Selatan","Takalar, Jeneponto, Bantaeng"),
    "DH":("NTT","Kupang, Timor"),
    "DK":("Bali","Seluruh Bali"),
    "DL":("Sulawesi Utara","Sangihe, Sitaro, Talaud"),
    "DM":("Gorontalo","Seluruh Gorontalo"),
    "DN":("Sulawesi Tengah","Palu, Donggala, Sigi"),
    "DO":("Sulawesi Tenggara","Kendari, Konawe"),
    "DT":("Sulawesi Tenggara","Baubau, Buton"),
    "DW":("Sulawesi Selatan","Bone, Sinjai, Bulukumba, Selayar"),
    "E":("Jawa Barat","Cirebon Kab., Kuningan, Majalengka, Indramayu"),
    "EA":("NTB","Sumbawa"),
    "EB":("NTT","Ende, Flores"),
    "ED":("NTT","Sumba"),
    "F":("Jawa Barat","Bogor, Sukabumi, Cianjur"),
    "G":("Jawa Tengah","Pekalongan, Batang, Pemalang, Brebes, Tegal"),
    "H":("Jawa Tengah","Semarang, Demak, Kendal, Ungaran, Salatiga"),
    "K":("Jawa Tengah","Pati, Kudus, Jepara, Rembang, Blora, Grobogan"),
    "KB":("Kalimantan Barat","Pontianak, Kubu Raya"),
    "KH":("Kalimantan Tengah","Palangka Raya"),
    "KT":("Kalimantan Timur","Samarinda, Kutai Kartanegara"),
    "KU":("Kalimantan Utara","Tarakan"),
    "L":("Jawa Timur","Surabaya"),
    "M":("Jawa Timur","Madura (Bangkalan, Sampang, Pamekasan, Sumenep)"),
    "N":("Jawa Timur","Malang, Batu, Pasuruan, Probolinggo, Lumajang"),
    "P":("Jawa Timur","Besuki (Situbondo, Bondowoso, Jember, Banyuwangi)"),
    "PA":("Papua","Jayapura, Papua"),
    "PB":("Papua Barat","Manokwari, Sorong"),
    "R":("Jawa Tengah","Banyumas, Cilacap, Purbalingga, Banjarnegara"),
    "S":("Jawa Timur","Bojonegoro, Tuban, Lamongan"),
    "T":("Jawa Barat","Karawang, Purwakarta, Subang"),
    "V":("Sulawesi Selatan","Pare-pare, Barru, Pinrang, Sidenreng Rappang"),
    "W":("Jawa Timur","Sidoarjo, Gresik"),
    "Z":("Jawa Barat","Garut, Tasikmalaya, Ciamis, Banjar, Pangandaran"),
}

# Huruf seri → sub-wilayah (untuk DKI Jakarta sebagai contoh)
_JAKARTA_SERI = {
    "A":"Jakarta Selatan","B":"Jakarta Timur","C":"Jakarta Pusat",
    "D":"Jakarta Barat","E":"Jakarta Utara","F":"Jakarta Selatan",
    "G":"Jakarta Timur","H":"Jakarta Pusat","I":"Jakarta Barat",
    "J":"Jakarta Utara","K":"Jakarta Selatan","L":"Jakarta Timur",
    "M":"Jakarta Pusat","N":"Jakarta Barat","O":"Jakarta Utara",
    "P":"Jakarta Selatan","Q":"Jakarta Timur","R":"Jakarta Pusat",
    "S":"Jakarta Barat","T":"Jakarta Utara","U":"Jakarta Selatan",
    "V":"Jakarta Timur","W":"Jakarta Pusat","X":"Jakarta Barat",
    "Y":"Jakarta Utara","Z":"Jakarta Selatan",
}

def plate_osint(plate: str) -> dict:
    """Decode plat nomor Indonesia + generate dork links."""
    raw = plate.strip().upper().replace("-","").replace(".","")
    # Normalize spasi: pisahkan prefix huruf, angka, suffix huruf
    m = re.match(r"^([A-Z]{1,3})\s*(\d{1,4})\s*([A-Z]{1,3})$", raw)
    if not m:
        return {"ok": False, "type": "plate", "query": plate,
                "error": "Format plat tidak dikenali. Contoh: B 1234 ABC"}

    prefix, number, suffix = m.group(1), m.group(2), m.group(3)
    plate_clean = f"{prefix} {number} {suffix}"

    # Cari wilayah — coba dari terpanjang ke terpendek
    region_info = None
    region_key = None
    for ln in [3, 2, 1]:
        k = prefix[:ln]
        if k in _PLATE_REGIONS:
            region_info = _PLATE_REGIONS[k]
            region_key = k
            break

    provinsi = region_info[0] if region_info else "Tidak diketahui"
    wilayah  = region_info[1] if region_info else "Kode tidak terdaftar"

    # Sub-wilayah (hanya DKI Jakarta punya mapping suffix → kecamatan)
    sub_wilayah = ""
    if prefix == "B" and suffix:
        sub_wilayah = _JAKARTA_SERI.get(suffix[0], "")

    # Jenis kendaraan (estimasi dari panjang nomor)
    num_int = int(number)
    if num_int <= 1999:
        kendaraan = "Mobil (kemungkinan)"
    elif num_int <= 6999:
        kendaraan = "Mobil / Kendaraan bermotor"
    else:
        kendaraan = "Sepeda motor (kemungkinan)"

    # Dork links
    q = urllib.parse.quote(plate_clean)
    q2 = urllib.parse.quote(f'"{plate_clean}"')
    dorks = [
        {"label": "Google (semua)", "url": f"https://www.google.com/search?q={q2}",
         "query": f'"{plate_clean}"'},
        {"label": "OLX Kendaraan", "url": f"https://www.olx.co.id/items/q-{urllib.parse.quote(plate_clean.replace(' ','-'))}",
         "query": f"OLX: {plate_clean}"},
        {"label": "Carmudi / Mobil123", "url": f"https://www.google.com/search?q={q2}+site%3Acarmudi.co.id+OR+site%3Amobil123.com",
         "query": f'"{plate_clean}" site:carmudi.co.id OR site:mobil123.com'},
        {"label": "Berita/Kecelakaan", "url": f"https://www.google.com/search?q={q2}+kecelakaan+OR+tilang+OR+ditangkap",
         "query": f'"{plate_clean}" kecelakaan OR tilang OR ditangkap'},
        {"label": "Media Sosial", "url": f"https://www.google.com/search?q={q2}+site%3Atwitter.com+OR+site%3Ainstagram.com+OR+site%3Afacebook.com",
         "query": f'"{plate_clean}" site:twitter.com OR instagram.com OR facebook.com'},
        {"label": "Forum KASKUS", "url": f"https://www.google.com/search?q={q2}+site%3Akaskus.co.id",
         "query": f'"{plate_clean}" site:kaskus.co.id'},
        {"label": "Google Images", "url": f"https://www.google.com/search?tbm=isch&q={q}",
         "query": f"Images: {plate_clean}"},
        {"label": "Cek Pajak Online", "url": f"https://www.google.com/search?q=cek+pajak+kendaraan+{q}",
         "query": f"cek pajak kendaraan {plate_clean}"},
    ]

    return {
        "ok": True, "type": "plate", "query": plate, "plate": plate_clean,
        "prefix": prefix, "number": number, "suffix": suffix,
        "provinsi": provinsi, "wilayah": wilayah,
        "sub_wilayah": sub_wilayah, "kendaraan": kendaraan,
        "dorks": dorks,
    }


# ─────────────────────────────────────────────
# GPS KOORDINAT OSINT
# ─────────────────────────────────────────────
def gps_osint(coords: str) -> dict:
    """Reverse geocode koordinat GPS + generate dork links."""
    m = re.match(r"^(-?\d{1,3}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)$", coords.strip())
    if not m:
        return {"ok": False, "type": "gps", "query": coords,
                "error": "Format tidak dikenali. Contoh: -6.2088, 106.8456"}
    lat, lon = float(m.group(1)), float(m.group(2))

    result = {"ok": True, "type": "gps", "query": coords,
              "lat": lat, "lon": lon, "address": "", "display_name": "",
              "country": "", "city": "", "suburb": ""}

    # Nominatim reverse geocode (OpenStreetMap, no key needed)
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "TFAEL-OMNI/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read(32768).decode())
            addr = d.get("address", {})
            result["display_name"] = d.get("display_name", "")
            result["address"] = d.get("display_name", "")
            result["country"] = addr.get("country", "")
            result["state"] = addr.get("state", "")
            result["city"] = addr.get("city") or addr.get("town") or addr.get("village") or ""
            result["suburb"] = addr.get("suburb") or addr.get("neighbourhood") or ""
            result["postcode"] = addr.get("postcode", "")
            result["road"] = addr.get("road", "")
    except Exception:
        pass

    # Dork links
    lat_s, lon_s = str(lat), str(lon)
    q_coord = urllib.parse.quote(f"{lat},{lon}")
    dorks = [
        {"label": "Google Maps", "url": f"https://maps.google.com/?q={lat},{lon}"},
        {"label": "OpenStreetMap", "url": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16"},
        {"label": "Google Street View", "url": f"https://maps.google.com/?layer=c&cbll={lat},{lon}"},
        {"label": "Foto Geotagged (Google)", "url": f"https://www.google.com/search?q={urllib.parse.quote(result['display_name'][:60])}+foto+lokasi"},
        {"label": "Wikimapia", "url": f"https://wikimapia.org/#lang=id&lat={lat}&lon={lon}&z=16"},
        {"label": "Bing Maps", "url": f"https://www.bing.com/maps?cp={lat}~{lon}&lvl=16"},
        {"label": "Earth Google", "url": f"https://earth.google.com/web/@{lat},{lon},100a,500d,35y"},
    ]
    result["dorks"] = dorks
    return result


# ─────────────────────────────────────────────
# URL / LINK OSINT
# ─────────────────────────────────────────────
def url_osint(url: str) -> dict:
    """Analisis URL: redirect chain, Wayback, headers, safe browsing dork."""
    if not url.startswith(("http://","https://")):
        url = "https://" + url
    result = {"ok": True, "type": "url", "query": url, "final_url": url,
              "redirects": [], "status": 0, "headers": {}, "wayback": None}

    # Follow redirects manually (max 10)
    current = url
    visited = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    for _ in range(10):
        try:
            req = urllib.request.Request(current, headers=_HEADERS, method="HEAD")
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
            # Don't auto-follow — capture each hop
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **kw): return None
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(req, timeout=6) as r:
                visited.append({"url": current, "status": r.status})
                result["status"] = r.status
                result["headers"] = dict(r.headers)
                break
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location", "")
            visited.append({"url": current, "status": e.code})
            if e.code in (301, 302, 303, 307, 308) and loc:
                if loc.startswith("http"):
                    current = loc
                else:
                    from urllib.parse import urljoin
                    current = urljoin(current, loc)
            else:
                break
        except Exception:
            break

    result["redirects"] = visited
    result["final_url"] = current
    result["redirect_count"] = max(0, len(visited) - 1)

    # Domain dari final URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(current)
        domain = parsed.netloc
        result["domain"] = domain
        result["path"] = parsed.path
    except Exception:
        domain = ""
        result["domain"] = ""

    # Wayback check untuk final URL
    try:
        wb = wayback_check(current)
        result["wayback"] = wb
    except Exception:
        pass

    # Tech hints dari headers
    hdrs = result["headers"]
    tech = []
    if hdrs.get("Server"): tech.append(hdrs["Server"])
    if hdrs.get("X-Powered-By"): tech.append(hdrs["X-Powered-By"])
    if hdrs.get("X-Generator"): tech.append(hdrs["X-Generator"])
    result["tech"] = tech

    # Security headers check
    sec = {
        "HTTPS": current.startswith("https://"),
        "HSTS": bool(hdrs.get("Strict-Transport-Security")),
        "CSP": bool(hdrs.get("Content-Security-Policy")),
        "X-Frame-Options": bool(hdrs.get("X-Frame-Options")),
        "X-Content-Type-Options": bool(hdrs.get("X-Content-Type-Options")),
    }
    result["security"] = sec

    # Dork links
    qu = urllib.parse.quote(current)
    qd = urllib.parse.quote(domain)
    result["dorks"] = [
        {"label": "Google Safe Browsing Check", "url": f"https://transparencyreport.google.com/safe-browsing/search?url={qu}"},
        {"label": "VirusTotal URL Scan", "url": f"https://www.virustotal.com/gui/url/{urllib.parse.quote(current, safe='')}"},
        {"label": "Wayback Machine", "url": f"https://web.archive.org/web/*/{current}"},
        {"label": "URLScan.io", "url": f"https://urlscan.io/search/#page.domain:{qd}"},
        {"label": "Shodan Host", "url": f"https://www.shodan.io/search?query={qd}"},
        {"label": "Who Is", "url": f"https://www.whois.com/whois/{qd}"},
    ]

    return result


def smart_search(query: str) -> dict:
    q = query.strip()
    # URL
    if re.match(r"^https?://", q) or re.match(r"^www\.", q):
        return url_osint(q)
    # Email
    if re.match(r"^[^@]+@[^@]+\.[^@]+$", q):
        return email_osint(q)
    # IP
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", q):
        return ip_osint(q)
    # GPS koordinat: "-6.2088, 106.8456" atau "-6.2088 106.8456"
    if re.match(r"^-?\d{1,3}(\.\d+)?[\s,]+-?\d{1,3}(\.\d+)?$", q):
        return gps_osint(q)
    # Plat nomor Indonesia: "B 1234 ABC" atau "B1234ABC"
    if re.match(r"^[A-Za-z]{1,3}\s*\d{1,4}\s*[A-Za-z]{1,3}$", q):
        return plate_osint(q)
    # Telepon
    cleaned = q.replace(" ", "").replace("-", "")
    if re.match(r"^(\+|00|08|62)\d{6,14}$", cleaned):
        return phone_osint(q)
    # Domain
    if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}$", q):
        return domain_osint(q)
    # Nama lengkap: ada spasi, bukan angka
    if " " in q and not q[0].isdigit():
        return name_osint(q)
    return username_hunt(q)
