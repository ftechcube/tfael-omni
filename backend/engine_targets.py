#!/usr/bin/env python3
"""Sub-modul TFAEL-OMNI — impor dari engine_core untuk shared state."""
from engine_core import *  # noqa: F401, F403

def compute_pattern_of_life(
    hits: List[Dict[str, Any]],
    recon_summary: str = "",
    cluster_radius_m: float = 150.0,
) -> Dict[str, Any]:
    """
    Menghitung Pattern-of-Life dari jejak check-in/lacak NYATA (bukan array konstan).

    `hits`: daftar titik lacak nyata [{timestamp(UTC ISO), lat, lon, client_ip, loc_source}].
    Menghasilkan histogram aktivitas per jam (WIB), klaster dwell berbasis kedekatan
    geografis dengan durasi & frekuensi NYATA, serta ringkasan/anomali faktual.
    """
    WIB_OFFSET_H = 7

    def _parse(ts: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
        return None

    parsed = []
    for h in hits or []:
        dt = _parse(h.get("timestamp", ""))
        if dt is None or h.get("lat") is None or h.get("lon") is None:
            continue
        parsed.append({**h, "dt": dt, "wib_hour": (dt.hour + WIB_OFFSET_H) % 24})

    n = len(parsed)
    if n == 0:
        return {
            "data_source": "NO_TRACKING_DATA",
            "sample_size": 0,
            "hourly_activity": [0] * 24,
            "routine_summary": recon_summary or "Belum ada jejak pelacakan perangkat.",
            "anomaly_flag": "Belum ada data pelacakan nyata (0 check-in). Pattern-of-Life menunggu perangkat membuka link lacak.",
            "dwell_clusters": [],
            "rendezvous_events": [],
        }

    # Histogram aktivitas per jam WIB (skala 0–100 relatif puncak)
    hourly_counts = [0] * 24
    for p in parsed:
        hourly_counts[p["wib_hour"]] += 1
    peak = max(hourly_counts) or 1
    hourly_activity = [int(round(c * 100 / peak)) for c in hourly_counts]

    # Klaster dwell: greedy berbasis kedekatan (<cluster_radius_m)
    clusters: List[Dict[str, Any]] = []
    for p in sorted(parsed, key=lambda x: x["dt"]):
        placed = False
        for c in clusters:
            if haversine_km(c["lat"], c["lon"], p["lat"], p["lon"]) * 1000.0 <= cluster_radius_m:
                c["points"].append(p)
                k = len(c["points"])
                c["lat"] = round((c["lat"] * (k - 1) + p["lat"]) / k, 6)
                c["lon"] = round((c["lon"] * (k - 1) + p["lon"]) / k, 6)
                placed = True
                break
        if not placed:
            clusters.append({"lat": p["lat"], "lon": p["lon"], "points": [p]})

    dwell_clusters = []
    for i, c in enumerate(sorted(clusters, key=lambda x: len(x["points"]), reverse=True), 1):
        pts = sorted(c["points"], key=lambda x: x["dt"])
        visits = len(pts)
        span_min = (pts[-1]["dt"] - pts[0]["dt"]).total_seconds() / 60.0 if visits > 1 else 0.0
        src = pts[-1].get("loc_source", "")
        dwell_clusters.append({
            "label": f"Klaster lacak #{i} ({src})" if src else f"Klaster lacak #{i}",
            "lat": c["lat"],
            "lon": c["lon"],
            "avg_dwell_min": int(round(span_min)),
            "visits_7d": visits,
        })
    dwell_clusters = dwell_clusters[:6]

    # Statistik anomali faktual
    parsed_sorted = sorted(parsed, key=lambda x: x["dt"])
    first_dt, last_dt = parsed_sorted[0]["dt"], parsed_sorted[-1]["dt"]
    active_hours = sorted({p["wib_hour"] for p in parsed})
    night_hits = sum(1 for p in parsed if 0 <= p["wib_hour"] <= 5)
    # sebaran geografis maksimum (km)
    spread_km = 0.0
    for a in range(n):
        for b in range(a + 1, n):
            d = haversine_km(parsed[a]["lat"], parsed[a]["lon"], parsed[b]["lat"], parsed[b]["lon"])
            if d > spread_km:
                spread_km = d
    unique_ips = len({p.get("client_ip") for p in parsed if p.get("client_ip")})

    hour_range = f"{active_hours[0]:02d}:00–{active_hours[-1]:02d}:59 WIB" if active_hours else "-"
    routine_summary = (
        f"Terlacak {n} kali pada {len(dwell_clusters)} titik, jam aktif {hour_range}. "
        f"Klaster terpadat: {dwell_clusters[0]['label']} ({dwell_clusters[0]['visits_7d']}x)."
    )
    anomaly_bits = [f"sebaran {spread_km:.2f} km", f"{unique_ips} IP unik"]
    if night_hits:
        anomaly_bits.append(f"{night_hits} ping dini hari (00–05 WIB)")
    anomaly_flag = (
        f"Dihitung dari {n} check-in NYATA ({first_dt.strftime('%Y-%m-%d %H:%M')}Z–{last_dt.strftime('%H:%M')}Z): "
        + ", ".join(anomaly_bits) + "."
    )

    return {
        "data_source": "LIVE_CHECKIN_TRACKING",
        "sample_size": n,
        "hourly_activity": hourly_activity,
        "routine_summary": routine_summary,
        "anomaly_flag": anomaly_flag,
        "dwell_clusters": dwell_clusters,
        "rendezvous_events": [],
    }


def create_or_recon_target(
    code_name: str,
    indicator: str,
    plate_number: str,
    lat: float,
    lon: float,
    phone_number: str = "",
) -> Dict[str, Any]:
    """
    Menjalankan REAL Live OSINT & AI-Assisted Target Profiling dari indikator input:
    - Domain / IP Server
    - Username / Handle / Email (GitHub, GitLab, Keybase, Dev.to, Gravatar MD5)
    - Nomor Telepon Seluler Indonesia (MSISDN Operator/HLR)
    - Pelat Nomor Kendaraan TNKB (Wilayah Polda & SAMSAT Kota/Kab)
    serta menghitung Skor Risiko Komposit R(e) (Pilar 4 - SRS-PRF-01..03).
    """
    conn = get_db()
    now = utc_now_iso()
    target_id = f"TGT-0{conn.execute('SELECT COUNT(*) FROM target_profiles').fetchone()[0] + 1}"

    # Jalankan pemindaian jaringan & identitas nyata
    live_recon = run_live_osint_recon(
        raw_indicator=indicator,
        code_name=code_name.upper(),
        plate_number=plate_number,
        phone_number=phone_number,
    )

    scores = live_recon["scores"]
    cyber_s = scores["cyber"]
    spatial_s = scores["spatial"]
    visual_s = scores["visual"]
    forensic_s = scores["forensic"]
    composite = scores["composite"]
    risk_level = scores["level"]

    geo = live_recon["geo"]
    ssl_info = live_recon["ssl"]
    dns_info = live_recon["dns"]
    tnkb_info = live_recon.get("tnkb", {})
    phone_info = live_recon.get("phone_profile", {})
    id_osint = live_recon.get("identity_osint", {})

    # Prioritaskan koordinat wilayah SAMSAT jika pelat valid dan indikator domain kosong/default
    if tnkb_info.get("valid_tnkb") and (not indicator or indicator.strip() in ("", "detik.com")):
        real_lat = tnkb_info.get("region_lat", lat)
        real_lon = tnkb_info.get("region_lon", lon)
    else:
        real_lat = geo.get("lat", lat)
        real_lon = geo.get("lon", lon)

    curr_ip = get_live_lan_ip()
    checkin_url_https = f"https://{curr_ip}:8443/checkin?target={target_id}"
    checkin_url_http = f"http://{curr_ip}:8080/checkin?target={target_id}"

    osint_data = {
        "whois_registrar": f"ISP/Org: {geo.get('isp', 'Unknown')} ({geo.get('country', '')} - {geo.get('city', '')})",
        "ssl_cert_san": ssl_info.get("san_domains") or [live_recon["host"]],
        "ssl_issuer": f"{ssl_info.get('issuer_org', 'No TLS')} | Valid: {ssl_info.get('not_after', 'N/A')} | Serial: {ssl_info.get('serial_number', 'N/A')}",
        "dns_records": f"NS: {', '.join(dns_info.get('ns', [])[:3]) or 'None'} | MX: {', '.join(dns_info.get('mx', [])[:2]) or 'None'}",
        "http_banner": live_recon["http_audit"].get("server_banner", "Unknown"),
        "tnkb_profile": tnkb_info,
        "phone_profile": phone_info,
        "identity_osint": id_osint,
        "checkin_url_https": checkin_url_https,
        "checkin_url_http": checkin_url_http,
        "checkin_hits": [],
        "open_ports": [f"{p['port']}/{p['service']}" for p in live_recon["open_ports"]],
        "cve_exposures": live_recon["exposures"],
        "breach_hits": f"Resolved IPs: {', '.join(live_recon['resolved_ips']) or 'Unresolved'} | TLS Cipher: {ssl_info.get('cipher_suite', 'N/A')}",
        "breach_check": live_recon.get("breach", {"checked": False, "reason": "tidak diperiksa"}),
        "score_breakdown": live_recon["scores"].get("breakdown", {}),
    }

    # Anchor infrastruktur dari recon NYATA (GeoIP/TNKB) — estimasi wilayah, BUKAN dwell terukur.
    # Metrik durasi/kunjungan sengaja 0: belum ada jejak pelacakan perangkat.
    dwell_list = [
        {"label": f"Infrastruktur OSINT / GeoIP ({geo.get('city', 'Node')})", "lat": geo.get("lat", real_lat), "lon": geo.get("lon", real_lon), "avg_dwell_min": 0, "visits_7d": 0}
    ]
    if tnkb_info.get("valid_tnkb"):
        dwell_list.insert(
            0,
            {
                "label": f"Wilayah Registrasi TNKB {tnkb_info['formatted']} ({tnkb_info['samsat_subregion']})",
                "lat": tnkb_info.get("region_lat", real_lat),
                "lon": tnkb_info.get("region_lon", real_lon),
                "avg_dwell_min": 0,
                "visits_7d": 0,
            },
        )

    summary_parts = []
    if id_osint.get("accounts_found"):
        platforms = ", ".join(a["platform"] for a in id_osint["accounts_found"])
        summary_parts.append(f"Akun publik ditemukan di [{platforms}] atas nama '{id_osint.get('discovered_name')}'")
    if phone_info.get("valid"):
        summary_parts.append(f"MSISDN {phone_info['e164']} aktif di jaringan {phone_info['operator']} ({phone_info['product']})")
    if tnkb_info.get("valid_tnkb"):
        summary_parts.append(f"Kendaraan {tnkb_info['formatted']} terdaftar di {tnkb_info['samsat_subregion']} ({tnkb_info['region']})")
    summary_parts.append(f"Host {live_recon['host']} ({live_recon['primary_ip']}) berada di {geo.get('city', 'Jakarta')} ({geo.get('asn', 'ASN')})")

    pol_data = {
        "data_source": "RECON_INFRA_ONLY",
        "sample_size": 0,
        "routine_summary": " • ".join(summary_parts),
        "anomaly_flag": (
            f"Live Recon: {len(id_osint.get('accounts_found', []))} akun publik, "
            f"{len(live_recon['open_ports'])} port TCP terbuka, {len(live_recon['exposures'])} indikator teknis. "
            f"Pattern-of-Life menunggu data check-in NYATA (buka link /checkin target)."
        ),
        "dwell_clusters": dwell_list,
        "rendezvous_events": [],
        "hourly_activity": [0] * 24,
    }

    # Sesuaikan ID root di graph menjadi target_id
    graph_data = live_recon["graph"]
    for n in graph_data["nodes"]:
        if n["id"] == "ROOT":
            n["id"] = target_id
            n["label"] = f"{target_id}: {code_name.upper()}\n({live_recon.get('raw_indicator') or live_recon['host']})"
    for e in graph_data["edges"]:
        if e["from"] == "ROOT":
            e["from"] = target_id

    real_name_display = (
        id_osint.get("discovered_name")
        if id_osint.get("accounts_found")
        else (f"Pemilik TNKB {tnkb_info['formatted']}" if tnkb_info.get("valid_tnkb") else f"Target ({live_recon.get('raw_indicator') or live_recon['host']})")
    )
    phone_display = (
        f"{phone_info['e164']} ({phone_info['operator']})"
        if phone_info.get("valid")
        else f"DNS: {', '.join(dns_info.get('ns', [])[:2]) or live_recon['host']}"
    )

    # Tentukan sumber lokasi: SAMSAT (pelat) → plate_region, GeoIP → geoip, manual
    if tnkb_info.get("valid_tnkb") and real_lat != lat:
        new_loc_source = "plate_region"
    elif geo.get("lat") and geo.get("lon"):
        new_loc_source = f"geoip:{geo.get('city', 'Unknown')}"
    else:
        new_loc_source = "manual"

    conn.execute(
        """INSERT INTO target_profiles
           (target_id, code_name, real_name, category, plate_number, phone_id,
            primary_domain, primary_ip, asn, lat, lon,
            cyber_score, spatial_score, visual_score, forensic_score,
            risk_score, risk_level, osint_json, pattern_of_life_json, graph_json,
            updated_at, loc_source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            target_id,
            code_name.upper(),
            real_name_display,
            f"Profil OSINT multi-sumber · infra host: {geo.get('country', 'ID')}",
            tnkb_info.get("formatted") if tnkb_info.get("valid_tnkb") else (plate_number or "N/A"),
            phone_display,
            live_recon.get("raw_indicator") or live_recon["host"],
            live_recon["primary_ip"],
            geo.get("asn", "AS-UNKNOWN"),
            real_lat,
            real_lon,
            cyber_s,
            spatial_s,
            visual_s,
            forensic_s,
            composite,
            risk_level,
            json.dumps(osint_data),
            json.dumps(pol_data),
            json.dumps(graph_data),
            now,
            new_loc_source,
        ),
    )
    conn.commit()
    conn.close()

    # --- Auto-ingest ke unified intelligence graph ---
    try:
        target_row = {
            "target_id": target_id, "code_name": code_name.upper(),
            "real_name": real_name_display, "primary_domain": live_recon.get("raw_indicator") or live_recon["host"],
            "primary_ip": live_recon["primary_ip"], "asn": geo.get("asn", ""),
            "phone_id": phone_display,
            "plate_number": tnkb_info.get("formatted") if tnkb_info.get("valid_tnkb") else (plate_number or ""),
            "lat": real_lat, "lon": real_lon,
            "risk_score": composite, "risk_level": risk_level,
            "osint_json": json.dumps(osint_data),
        }
        engine_graph.ingest_target_profile(target_row)
        # Ingest OSINT result juga
        osint_result_for_graph = {
            "query": live_recon.get("raw_indicator") or live_recon["host"],
            "type": "domain", "host": live_recon["host"],
            "resolved_ips": live_recon.get("resolved_ips", []),
            "open_ports": live_recon.get("open_ports", []),
            "ssl": ssl_info, "dns": dns_info,
            "identity_osint": id_osint,
            "breach": live_recon.get("breach", {}),
        }
        engine_graph.ingest_osint_result(target_id, osint_result_for_graph)
    except Exception as _gex:
        print(f"[graph-ingest] target {target_id}: {_gex}")

    return {"ok": True, "target_id": target_id, "risk_score": composite, "live_recon": live_recon}


# ---- Jalur B: isi target dari recon NYATA (bukan seed karangan) ----
SAFE_RECON_SEEDS = [
    # (code_name netral, indikator aman, pelat, lat, lon, telepon)
    ("AUDIT-01", "scanme.nmap.org", "", -6.2000, 106.8167, ""),
    ("AUDIT-02", "testphp.vulnweb.com", "", -6.2000, 106.8167, ""),
    ("AUDIT-03", "example.com", "", -6.2000, 106.8167, ""),
]


def seed_targets_from_recon(force: bool = False) -> None:
    """
    Jalur B: isi target_profiles dari recon NYATA atas indikator aman (aset/target
    uji publik), bukan data karangan. Framing netral ('audit permukaan serangan').
    Dilewati saat OMNI_AIRGAP=1 atau bila target sudah ada (kecuali force=True).
    """
    if os.environ.get("OMNI_AIRGAP", "") == "1":
        print("[Jalur B] mode air-gap: lewati recon target; tabel dibiarkan kosong (empty-state jujur).")
        return
    conn = get_db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM target_profiles").fetchone()[0]
    finally:
        conn.close()
    if n > 0 and not force:
        return
    for code_name, indicator, plate, lat, lon, phone in SAFE_RECON_SEEDS:
        try:
            create_or_recon_target(
                code_name=code_name, indicator=indicator, plate_number=plate,
                lat=lat, lon=lon, phone_number=phone,
            )
            print(f"[Jalur B] target nyata dibuat dari {indicator}")
        except Exception as e:
            print(f"[Jalur B] recon {indicator} gagal: {e}")


def seed_targets_from_recon_async() -> None:
    """Jalankan seed_targets_from_recon di thread latar agar boot tetap cepat."""
    threading.Thread(target=seed_targets_from_recon, daemon=True).start()


# ---------------------------------------------------------------------------
# RECON ASYNC JOB QUEUE
# ---------------------------------------------------------------------------
_RECON_JOBS: Dict[str, Dict[str, Any]] = {}
_RECON_JOBS_LOCK = threading.Lock()


def create_or_recon_target_async(
    code_name: str,
    indicator: str,
    plate_number: str,
    lat: float,
    lon: float,
    phone_number: str = "",
) -> str:
    """Mulai recon di thread latar; kembalikan job_id yang bisa di-poll."""
    import secrets as _s
    job_id = "JOB-" + _s.token_hex(6).upper()
    with _RECON_JOBS_LOCK:
        _RECON_JOBS[job_id] = {"status": "running", "result": None, "error": None}

    def _run():
        try:
            res = create_or_recon_target(code_name, indicator, plate_number, lat, lon, phone_number)
            with _RECON_JOBS_LOCK:
                _RECON_JOBS[job_id]["status"] = "done"
                _RECON_JOBS[job_id]["result"] = res
        except Exception as exc:
            with _RECON_JOBS_LOCK:
                _RECON_JOBS[job_id]["status"] = "error"
                _RECON_JOBS[job_id]["error"] = str(exc)

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def get_recon_job(job_id: str) -> Dict[str, Any]:
    """Kembalikan status & hasil job recon."""
    with _RECON_JOBS_LOCK:
        job = _RECON_JOBS.get(job_id)
    if not job:
        return {"ok": False, "error": "Job tidak ditemukan"}
    return {"ok": True, "job_id": job_id, "status": job["status"],
            "result": job["result"], "error": job["error"]}


def auto_import_opencellid() -> None:
    """
    Impor otomatis menara OpenCellID saat boot bila belum ada dan file CSV tersedia
    di root proyek (510.csv.gz / 510.csv), atau di path OMNI_OPENCELLID_CSV. Idempoten:
    dilewati bila menara OPENCELLID sudah ada. Setelah impor, menara seed sintetis
    dihapus agar triangulasi memakai menara nyata.
    """
    conn = get_db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM bts_towers WHERE data_source='OPENCELLID'").fetchone()[0]
    except Exception:
        n = 0
    if n > 0:
        # OpenCellID sudah ada; pastikan menara seed sintetis tak mengotori triangulasi.
        try:
            conn.execute("DELETE FROM bts_towers WHERE data_source='SEED_SYNTHETIC'")
            conn.commit()
        except Exception:
            pass
        conn.close()
        return
    conn.close()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = []
    env_csv = os.environ.get("OMNI_OPENCELLID_CSV", "").strip()
    if env_csv:
        candidates.append(env_csv)
    candidates += [os.path.join(root, "510.csv.gz"), os.path.join(root, "510.csv")]
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if not path:
        return
    try:
        from celltower_lookup import import_opencellid_csv
        res = import_opencellid_csv(path)
        if res.get("ok"):
            conn = get_db()
            conn.execute("DELETE FROM bts_towers WHERE data_source='SEED_SYNTHETIC'")
            conn.commit()
            conn.close()
            print(f"[OpenCellID] impor otomatis: {res.get('imported')} menara nyata (menara seed dihapus).")
    except Exception as e:
        print(f"[OpenCellID] impor otomatis gagal: {e}")


def auto_import_opencellid_async() -> None:
    """Jalankan auto_import_opencellid di thread latar agar boot tetap cepat."""
    threading.Thread(target=auto_import_opencellid, daemon=True).start()


def _extract_ip_from_scanner(scanner_data: dict) -> Optional[str]:
    """Ambil IP pertama yang bisa di-GeoIP dari hasil scan OSINT."""
    t = scanner_data.get("type", "")
    if t == "ip":
        return scanner_data.get("ip") or scanner_data.get("query")
    if t in ("domain", "username", "email", "url"):
        return scanner_data.get("resolved_ip") or scanner_data.get("primary_ip")
    geo = scanner_data.get("geo", {})
    if isinstance(geo, dict) and geo.get("ip"):
        return geo["ip"]
    return None


def _recalc_risk_from_osint(osint: dict) -> dict:
    """Hitung ulang sub-skor dari akumulasi osint_json target."""
    def _clamp(v, lo=5, hi=98):
        return max(lo, min(hi, int(round(v))))

    # Kumpulkan sinyal dari semua lapisan osint yang tersimpan
    scanner = osint.get("scanner", {})
    scan_type = scanner.get("type", "")

    # Jumlah akun sosial (dari scan username atau dari recon awal)
    accounts = scanner.get("accounts", []) or scanner.get("found_accounts", []) or []
    n_accounts = len(accounts)
    # Tambah sinyal dari platform_count (field alternatif yang dipakai beberapa scanner)
    if not n_accounts:
        n_accounts = int(scanner.get("platform_count", 0) or scanner.get("accounts_found_count", 0) or 0)

    # Sinyal breach/leak
    breach = osint.get("breach") or scanner.get("breach", {}) or {}
    n_breaches = int(breach.get("count", 0) or 0) if breach.get("found") else 0

    # Port & eksposur dari recon awal
    recon = osint.get("recon", {}) or {}
    n_ports = len(recon.get("open_ports", []))
    n_exposures = len(recon.get("exposures", []))

    # SSL
    ssl_info = recon.get("ssl", {}) or {}
    ssl_weak = (not ssl_info.get("ssl_active")) or (ssl_info.get("tls_version", "") in ("TLSv1", "TLSv1.1"))

    # Lokasi
    geo_ok = bool(osint.get("geo", {}).get("lat"))
    phone_ok = bool(osint.get("phone", {}).get("valid"))
    tnkb_ok = bool(osint.get("tnkb", {}).get("valid_tnkb"))
    multi_ip = len(recon.get("resolved_ips", [])) > 1
    gravatar_ok = any("gravatar" in (a.get("platform", "").lower()) for a in accounts)

    cyber_score = _clamp(30 + n_exposures * 9 + n_ports * 4 + n_accounts * 3 + min(n_breaches, 10) * 2 + (10 if ssl_weak else 0))
    loc_anchor = (22 if geo_ok else 0) + (24 if tnkb_ok else 0) + (16 if phone_ok else 0) + (8 if multi_ip else 0)
    spatial_score = _clamp(20 + loc_anchor * 0.6)
    visual_score = _clamp(20 + n_accounts * 11 + (16 if gravatar_ok else 0) + (18 if tnkb_ok else 0))
    forensic_score = _clamp(28 + n_exposures * 7 + n_accounts * 6 + min(n_breaches, 10) * 2 + (14 if phone_ok else 0) + (8 if tnkb_ok else 0))
    composite = int(round(0.25 * cyber_score + 0.30 * spatial_score + 0.20 * visual_score + 0.25 * forensic_score))
    risk_level = "CRITICAL" if composite >= 80 else ("HIGH" if composite >= 65 else ("MEDIUM" if composite >= 40 else "RENDAH"))

    return {
        "cyber_score": cyber_score, "spatial_score": spatial_score,
        "visual_score": visual_score, "forensic_score": forensic_score,
        "risk_score": composite, "risk_level": risk_level,
        "_signals": {"n_accounts": n_accounts, "n_ports": n_ports, "n_exposures": n_exposures,
                     "n_breaches": n_breaches, "geo_ok": geo_ok, "phone_ok": phone_ok, "tnkb_ok": tnkb_ok},
    }


def save_scanner_to_profile(
    target_id: str,
    scanner_data: dict,
    graph_data: dict | None = None,
) -> dict:
    """Simpan hasil Scanner OSINT ke dalam target_profiles.osint_json (key 'scanner')
    dan opsional ke graph_json. Bila scan mengandung IP, update lat/lon target
    via GeoIP dan tandai loc_source='geoip' agar peta bisa tampilkan ikon berbeda."""
    from real_osint import lookup_geoip_and_asn

    conn = get_db()
    row = conn.execute(
        "SELECT osint_json, graph_json, lat, lon, primary_ip, asn FROM target_profiles WHERE target_id = ?",
        (target_id,),
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": f"Target {target_id} tidak ditemukan"}

    try:
        existing_osint = json.loads(row["osint_json"] or "{}")
    except Exception:
        existing_osint = {}

    existing_osint["scanner"] = scanner_data

    updates = {"osint_json": json.dumps(existing_osint, ensure_ascii=False)}

    if graph_data and (graph_data.get("nodes") or graph_data.get("edges")):
        updates["graph_json"] = json.dumps(graph_data, ensure_ascii=False)

    # Update posisi peta dari GeoIP bila scan mengandung IP
    ip = _extract_ip_from_scanner(scanner_data)
    geo_result = {}
    if ip:
        try:
            geo_result = lookup_geoip_and_asn(ip) or {}
        except Exception:
            geo_result = {}

    if geo_result.get("lat") and geo_result.get("lon"):
        updates["lat"] = round(float(geo_result["lat"]), 6)
        updates["lon"] = round(float(geo_result["lon"]), 6)
        updates["loc_source"] = f"geoip:{geo_result.get('city', 'Unknown')}"
        if geo_result.get("isp") and not row["primary_ip"]:
            updates["primary_ip"] = ip
            updates["asn"] = geo_result.get("asn", "")
    elif scanner_data.get("type") == "gps":
        # Scan GPS langsung: ambil koordinat dari hasil scan
        coords = scanner_data.get("query", "")
        try:
            parts = [x.strip() for x in coords.replace(",", " ").split() if x.strip()]
            if len(parts) >= 2:
                updates["lat"] = round(float(parts[0]), 6)
                updates["lon"] = round(float(parts[1]), 6)
                updates["loc_source"] = "gps_osint"
        except Exception:
            pass

    # Recalculate risk score dari data OSINT yang terakumulasi
    new_scores = _recalc_risk_from_osint(existing_osint)
    score_cols = ["cyber_score", "spatial_score", "visual_score", "forensic_score", "risk_score", "risk_level"]
    for col in score_cols:
        updates[col] = new_scores[col]

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [target_id]
    conn.execute(
        f"UPDATE target_profiles SET {set_clause}, updated_at = datetime('now') WHERE target_id = ?",
        values,
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "target_id": target_id,
        "saved_keys": list(updates.keys()),
        "loc_updated": "lat" in updates,
        "loc_source": updates.get("loc_source", "none"),
        "risk_updated": {k: new_scores[k] for k in score_cols},
        "signals": new_scores["_signals"],
    }


def record_target_checkin_telemetry(
    target_id: str,
    client_ip: str,
    user_agent: str,
    screen_res: str = "",
    timezone_str: str = "",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    accuracy_m: Optional[float] = None,
    # Extended fingerprint fields
    webrtc_local_ips: str = "",
    canvas_fp: str = "",
    webgl_fp: str = "",
    net_type: str = "",
    net_downlink: float = 0.0,
    net_rtt: float = 0.0,
    net_save_data: bool = False,
    cpu_cores: int = 0,
    device_mem: float = 0.0,
    touch_pts: int = 0,
    battery_level: Optional[int] = None,
    battery_charging: Optional[bool] = None,
    media_cameras: int = 0,
    media_mics: int = 0,
    media_speakers: int = 0,
    platform: str = "",
    languages: str = "",
    orientation: str = "",
    plugins: int = 0,
    dnt: str = "",
) -> Dict[str, Any]:
    """
    Mencatat telemetri perangkat nyata ketika link verifikasi/pelacak (/checkin?target=TGT-xx) dibuka
    dan langsung memutakhirkan Dossier Target (Tab 2) serta Peta GIS (Tab 1).
    """
    from real_osint import lookup_geoip_and_asn

    conn = get_db()
    now = utc_now_iso()
    row = conn.execute("SELECT * FROM target_profiles WHERE target_id = ?", (target_id,)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM target_profiles ORDER BY updated_at DESC LIMIT 1").fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Target not found"}

    actual_tid = row["target_id"]
    osint_data = json.loads(row["osint_json"] or "{}")
    pol_data = json.loads(row["pattern_of_life_json"] or "{}")
    graph_data = json.loads(row["graph_json"] or '{"nodes":[],"edges":[]}')

    geo = lookup_geoip_and_asn(client_ip)
    final_lat = round(float(lat), 6) if lat is not None else geo.get("lat", row["lat"])
    final_lon = round(float(lon), 6) if lon is not None else geo.get("lon", row["lon"])
    loc_source = f"Hardware GPS (±{int(accuracy_m or 12)}m)" if lat is not None else f"GeoIP ({geo.get('city', 'Local')})"

    hit_entry = {
        "timestamp": now,
        "client_ip": client_ip,
        "isp_asn": f"{geo.get('isp', 'Local LAN')} ({geo.get('asn', '')})",
        "user_agent": user_agent[:200],
        "screen": screen_res,
        "timezone": timezone_str,
        "lat": final_lat,
        "lon": final_lon,
        "loc_source": loc_source,
        # Extended fingerprint
        "webrtc_local_ips": webrtc_local_ips,
        "canvas_fp": canvas_fp,
        "webgl_fp": webgl_fp[:120],
        "network": {
            "type": net_type,
            "downlink_mbps": net_downlink,
            "rtt_ms": net_rtt,
            "save_data": net_save_data,
        },
        "device": {
            "platform": platform,
            "languages": languages,
            "cpu_cores": cpu_cores,
            "device_mem_gb": device_mem,
            "touch_points": touch_pts,
            "orientation": orientation,
            "plugins": plugins,
            "dnt": dnt,
        },
        "battery": {
            "level_pct": battery_level,
            "charging": battery_charging,
        },
        "media_devices": {
            "cameras": media_cameras,
            "mics": media_mics,
            "speakers": media_speakers,
        },
    }
    hits = osint_data.get("checkin_hits", [])
    hits.insert(0, hit_entry)
    hits = hits[:100]  # simpan riwayat cukup untuk analisis Pattern-of-Life
    osint_data["checkin_hits"] = hits

    # Hitung ulang Pattern-of-Life dari SELURUH jejak check-in nyata (bukan sisipan konstan)
    prev_rv = pol_data.get("rendezvous_events", [])
    pol_data = compute_pattern_of_life(hits, recon_summary=pol_data.get("routine_summary", ""))
    pol_data["rendezvous_events"] = prev_rv
    pol_data["anomaly_flag"] = (
        f"TERLACAK LIVE ({now}) pada ({final_lat}, {final_lon}) via IP {client_ip} [{timezone_str}]. "
        + pol_data["anomaly_flag"]
    )

    node_id = f"TRK-{len(hits)}"
    graph_data["nodes"].append({
        "id": node_id,
        "label": f"Tracked Device\n{client_ip} ({final_lat:.3f},{final_lon:.3f})",
        "type": "DEVICE",
        "risk": 92,
    })
    graph_data["edges"].append({
        "from": actual_tid,
        "to": node_id,
        "label": "LINK_OPENED_AT",
    })

    conn.execute(
        """
        UPDATE target_profiles
        SET lat = ?, lon = ?, loc_source = ?, spatial_score = 95,
            risk_score = MAX(risk_score, 88), risk_level = 'CRITICAL',
            osint_json = ?, pattern_of_life_json = ?, graph_json = ?, updated_at = ?
        WHERE target_id = ?
        """,
        (
            final_lat,
            final_lon,
            loc_source,
            json.dumps(osint_data),
            json.dumps(pol_data),
            json.dumps(graph_data),
            now,
            actual_tid,
        ),
    )
    conn.commit()
    conn.close()

    # --- Auto-ingest checkin ke unified intelligence graph ---
    try:
        engine_graph.ingest_checkin({
            "target_id": actual_tid, "client_ip": client_ip,
            "user_agent": user_agent, "lat": lat, "lon": lon,
            "screen_res": screen_res, "timezone": timezone_str,
            "canvas_fp": canvas_fp, "webrtc_local_ips": webrtc_local_ips,
        })
    except Exception as _gex:
        print(f"[graph-ingest] checkin {actual_tid}: {_gex}")

    return {"ok": True, "target_id": actual_tid, "hit": hit_entry}


def build_link_graph() -> dict:
    """Bangun graf relasi lintas-target: target, IP, domain, email, telepon, lokasi, plat."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT target_id, code_name, phone_id, primary_ip, primary_domain, "
            "plate_number, lat, lon, risk_score, risk_level, osint_json FROM target_profiles"
        ).fetchall()
    finally:
        conn.close()

    nodes: dict = {}
    edges: list = []
    entity_to_targets: dict = {}

    def add_node(nid, ntype, label, meta=None):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, "meta": meta or {}}

    def add_edge(src, dst, rel):
        e = {"source": src, "target": dst, "rel": rel}
        if e not in edges:
            edges.append(e)

    def register(eid, tid):
        entity_to_targets.setdefault(eid, [])
        if tid not in entity_to_targets[eid]:
            entity_to_targets[eid].append(tid)

    for row in rows:
        tid = row["target_id"]
        risk = row["risk_score"] or 0
        add_node(tid, "target", row["code_name"], {
            "risk_score": risk,
            "risk_level": row["risk_level"] or "RENDAH",
            "lat": row["lat"],
            "lon": row["lon"],
        })

        phone = (row["phone_id"] or "").strip()
        if phone and phone not in ("N/A", "-", ""):
            pid = f"phone:{phone}"
            add_node(pid, "phone", phone[:30])
            add_edge(tid, pid, "has_phone")
            register(pid, tid)

        ip = (row["primary_ip"] or "").strip()
        if ip and ip not in ("0.0.0.0", "", "N/A"):
            iid = f"ip:{ip}"
            add_node(iid, "ip", ip)
            add_edge(tid, iid, "has_ip")
            register(iid, tid)

        domain = (row["primary_domain"] or "").strip()
        if domain and domain not in ("N/A", "", "-"):
            did = f"domain:{domain}"
            add_node(did, "domain", domain[:40])
            add_edge(tid, did, "has_domain")
            register(did, tid)

        plate = (row["plate_number"] or "").strip()
        if plate and plate not in ("N/A", "", "-"):
            plid = f"plate:{plate}"
            add_node(plid, "plate", plate)
            add_edge(tid, plid, "has_plate")
            register(plid, tid)

        lat = row["lat"]
        lon = row["lon"]
        if lat and lon:
            grid_lat = round(float(lat) / 0.05) * 0.05
            grid_lon = round(float(lon) / 0.05) * 0.05
            loc_id = f"loc:{grid_lat:.3f},{grid_lon:.3f}"
            add_node(loc_id, "location", f"{grid_lat:.3f},{grid_lon:.3f}",
                     {"lat": grid_lat, "lon": grid_lon})
            add_edge(tid, loc_id, "near")
            register(loc_id, tid)

        try:
            osint = json.loads(row["osint_json"] or "{}")
        except Exception:
            osint = {}

        scanner = osint.get("scanner") or {}
        for val in scanner.values() if isinstance(scanner, dict) else []:
            if not isinstance(val, dict):
                continue
            for email in (val.get("emails") or []):
                eid = f"email:{email}"
                add_node(eid, "email", email[:40])
                add_edge(tid, eid, "has_email")
                register(eid, tid)
            for extra_ip in (val.get("ips") or []):
                iid2 = f"ip:{extra_ip}"
                add_node(iid2, "ip", extra_ip)
                add_edge(tid, iid2, "has_ip")
                register(iid2, tid)
            for sub in (val.get("subdomains") or []):
                sid = f"domain:{sub}"
                add_node(sid, "domain", sub[:40])
                add_edge(tid, sid, "has_domain")
                register(sid, tid)

    # Cross-target "shares" edges for shared entities
    for eid, tgt_list in entity_to_targets.items():
        if len(tgt_list) < 2:
            continue
        etype = eid.split(":")[0]
        for i in range(len(tgt_list)):
            for j in range(i + 1, len(tgt_list)):
                add_edge(tgt_list[i], tgt_list[j], f"shares_{etype}")

    stats = {
        "total_targets": sum(1 for n in nodes.values() if n["type"] == "target"),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "shared_entities": sum(1 for t in entity_to_targets.values() if len(t) >= 2),
    }
    return {"ok": True, "nodes": list(nodes.values()), "edges": edges, "stats": stats}


