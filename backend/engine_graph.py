#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Unified Intelligence Graph Engine
====================================================
Satu graph engine yang menyatukan seluruh data dari semua modul:
OSINT, SIEM, C2, Vision/ANPR, Forensik, Check-in Beacon, Off-Grid.

Menggantikan build_link_graph() dan build_knowledge_graph() yang terpisah
menjadi satu graf terpadu dengan kemampuan analisis:
- Neighborhood Query (BFS traversal n-hop)
- Shortest Path (jalur koneksi terpendek antar entitas)
- Betweenness Centrality (identifikasi broker/fasilitator)
- Community Detection (Label Propagation — deteksi kluster)
- Temporal Analysis (aktivitas baru dalam jendela waktu)
- Cross-Target Shared Entity Discovery

Pure Python stdlib + SQLite. Air-gap ready. Tanpa dependensi eksternal.
"""

import json
import os
import sqlite3
import time
import collections
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set

# ── Koneksi DB (mengikuti pola engine_core.py) ─────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tfael_omni.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ══════════════════════════════════════════════════════════════════════════
#  1. SCHEMA
# ══════════════════════════════════════════════════════════════════════════

def init_graph_schema() -> None:
    """Buat tabel graph_nodes dan graph_edges jika belum ada."""
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                node_id     TEXT PRIMARY KEY,
                node_type   TEXT NOT NULL,
                label       TEXT NOT NULL,
                properties  TEXT DEFAULT '{}',
                source_module TEXT DEFAULT 'manual',
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                edge_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id     TEXT NOT NULL,
                target_id     TEXT NOT NULL,
                rel_type      TEXT NOT NULL,
                properties    TEXT DEFAULT '{}',
                source_module TEXT DEFAULT 'manual',
                confidence    REAL DEFAULT 1.0,
                first_seen    TEXT NOT NULL,
                last_seen     TEXT NOT NULL,
                UNIQUE(source_id, target_id, rel_type)
            );

            CREATE INDEX IF NOT EXISTS idx_gn_type ON graph_nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_gn_source ON graph_nodes(source_module);
            CREATE INDEX IF NOT EXISTS idx_gn_last ON graph_nodes(last_seen);
            CREATE INDEX IF NOT EXISTS idx_ge_src ON graph_edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_ge_tgt ON graph_edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_ge_rel ON graph_edges(rel_type);
            CREATE INDEX IF NOT EXISTS idx_ge_last ON graph_edges(last_seen);
            CREATE INDEX IF NOT EXISTS idx_ge_mod ON graph_edges(source_module);
        """)
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  2. CORE UPSERT — INSERT OR UPDATE
# ══════════════════════════════════════════════════════════════════════════

def upsert_node(
    node_id: str,
    node_type: str,
    label: str,
    properties: dict = None,
    source_module: str = "manual",
    conn: sqlite3.Connection = None,
) -> str:
    """Tambah node baru atau perbarui last_seen + merge properties jika sudah ada."""
    now = _now_iso()
    props_json = json.dumps(properties or {}, ensure_ascii=False)
    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT properties, source_module FROM graph_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if existing:
            # Merge properties
            old_props = json.loads(existing["properties"] or "{}")
            new_props = {**old_props, **(properties or {})}
            # Gabungkan source_module jika beda
            old_sources = set(existing["source_module"].split(","))
            old_sources.add(source_module)
            merged_source = ",".join(sorted(old_sources))
            conn.execute(
                "UPDATE graph_nodes SET label=?, properties=?, source_module=?, last_seen=? WHERE node_id=?",
                (label, json.dumps(new_props, ensure_ascii=False), merged_source, now, node_id),
            )
        else:
            conn.execute(
                "INSERT INTO graph_nodes (node_id, node_type, label, properties, source_module, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (node_id, node_type, label, props_json, source_module, now, now),
            )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()
    return node_id


def upsert_edge(
    source_id: str,
    target_id: str,
    rel_type: str,
    properties: dict = None,
    source_module: str = "manual",
    confidence: float = 1.0,
    conn: sqlite3.Connection = None,
) -> None:
    """Tambah edge baru atau perbarui last_seen + merge properties jika sudah ada."""
    now = _now_iso()
    props_json = json.dumps(properties or {}, ensure_ascii=False)
    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT edge_id, properties, confidence FROM graph_edges WHERE source_id=? AND target_id=? AND rel_type=?",
            (source_id, target_id, rel_type),
        ).fetchone()
        if existing:
            old_props = json.loads(existing["properties"] or "{}")
            new_props = {**old_props, **(properties or {})}
            # Confidence: ambil yang lebih tinggi
            new_conf = max(existing["confidence"], confidence)
            conn.execute(
                "UPDATE graph_edges SET properties=?, confidence=?, last_seen=? WHERE edge_id=?",
                (json.dumps(new_props, ensure_ascii=False), new_conf, now, existing["edge_id"]),
            )
        else:
            conn.execute(
                "INSERT INTO graph_edges (source_id, target_id, rel_type, properties, source_module, confidence, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, target_id, rel_type, props_json, source_module, confidence, now, now),
            )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def delete_node(node_id: str) -> int:
    """Hapus node dan semua edge terkait. Return jumlah edge yang dihapus."""
    conn = _get_db()
    try:
        cur = conn.execute(
            "DELETE FROM graph_edges WHERE source_id=? OR target_id=?", (node_id, node_id)
        )
        edges_deleted = cur.rowcount
        conn.execute("DELETE FROM graph_nodes WHERE node_id=?", (node_id,))
        conn.commit()
        return edges_deleted
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  3. INGESTION — Dari Setiap Modul ke Graph Terpadu
# ══════════════════════════════════════════════════════════════════════════

def ingest_target_profile(target_row: dict, conn: sqlite3.Connection = None) -> int:
    """
    Ingest satu baris target_profiles ke graph.
    Dipanggil saat target baru dibuat atau di-update.
    Return jumlah edge yang dihasilkan.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    edge_count = 0
    try:
        tid = target_row.get("target_id", "")
        if not tid:
            return 0
        upsert_node(tid, "target", target_row.get("code_name", tid), {
            "risk_score": target_row.get("risk_score", 0),
            "risk_level": target_row.get("risk_level", "RENDAH"),
            "lat": target_row.get("lat"),
            "lon": target_row.get("lon"),
        }, "target_profile", conn)

        # Phone
        phone = (target_row.get("phone_id") or "").strip()
        if phone and phone not in ("N/A", "-", ""):
            pid = f"phone:{phone}"
            upsert_node(pid, "phone", phone, {}, "target_profile", conn)
            upsert_edge(tid, pid, "has_phone", {}, "target_profile", 1.0, conn)
            edge_count += 1

        # IP
        ip = (target_row.get("primary_ip") or "").strip()
        if ip and ip not in ("0.0.0.0", "", "N/A"):
            iid = f"ip:{ip}"
            upsert_node(iid, "ip", ip, {}, "target_profile", conn)
            upsert_edge(tid, iid, "has_ip", {}, "target_profile", 1.0, conn)
            edge_count += 1

        # Domain
        domain = (target_row.get("primary_domain") or "").strip()
        if domain and domain not in ("N/A", "", "-"):
            did = f"domain:{domain}"
            upsert_node(did, "domain", domain, {}, "target_profile", conn)
            upsert_edge(tid, did, "has_domain", {}, "target_profile", 1.0, conn)
            edge_count += 1

        # Plate
        plate = (target_row.get("plate_number") or "").strip()
        if plate and plate not in ("N/A", "", "-"):
            plid = f"plate:{plate}"
            upsert_node(plid, "plate", plate, {}, "target_profile", conn)
            upsert_edge(tid, plid, "has_plate", {}, "target_profile", 1.0, conn)
            edge_count += 1

        # Location grid
        lat, lon = target_row.get("lat"), target_row.get("lon")
        if lat and lon:
            try:
                grid_lat = round(float(lat) / 0.005) * 0.005
                grid_lon = round(float(lon) / 0.005) * 0.005
                loc_id = f"loc:{grid_lat:.4f},{grid_lon:.4f}"
                upsert_node(loc_id, "location", f"{grid_lat:.4f},{grid_lon:.4f}", {
                    "lat": grid_lat, "lon": grid_lon,
                }, "target_profile", conn)
                upsert_edge(tid, loc_id, "seen_at", {}, "target_profile", 0.8, conn)
                edge_count += 1
            except (TypeError, ValueError):
                pass

        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()
    return edge_count


def ingest_osint_result(target_id: str, osint_result: dict) -> int:
    """
    Ingest hasil OSINT scan ke graph terpadu.
    Menggantikan build_knowledge_graph() — data sekarang TERSIMPAN, bukan ephemeral.
    Return jumlah edge yang dihasilkan.
    """
    conn = _get_db()
    edge_count = 0
    try:
        t = osint_result.get("type", "")
        query = osint_result.get("query", "")

        if t == "username":
            uid = f"username:{query}"
            upsert_node(uid, "username", query, {}, "osint", conn)
            if target_id:
                upsert_edge(target_id, uid, "uses_username", {}, "osint", 1.0, conn)
                edge_count += 1

            for p in osint_result.get("platforms", []):
                pid = f"platform:{p['platform']}:{query}"
                upsert_node(pid, "account", f"{query}@{p['platform']}", {
                    "url": p.get("url", ""), "confidence": "verified",
                }, "osint", conn)
                upsert_edge(uid, pid, "has_account", {}, "osint", 1.0, conn)
                edge_count += 1

            for p in osint_result.get("unverified", []):
                pid = f"platform_uv:{p['platform']}:{query}"
                upsert_node(pid, "account", f"{query}@{p['platform']}?", {
                    "url": p.get("url", ""), "confidence": "unverified",
                }, "osint", conn)
                upsert_edge(uid, pid, "maybe_account", {}, "osint", 0.4, conn)
                edge_count += 1

            gh = osint_result.get("github", {})
            if gh.get("ok") and gh.get("profile"):
                prof = gh["profile"]
                for email in gh.get("emails", []):
                    eid = f"email:{email}"
                    upsert_node(eid, "email", email, {}, "osint", conn)
                    upsert_edge(uid, eid, "commit_email", {}, "osint", 0.9, conn)
                    edge_count += 1
                if prof.get("location"):
                    lid = f"place:{prof['location']}"
                    upsert_node(lid, "place", prof["location"], {}, "osint", conn)
                    upsert_edge(uid, lid, "located_at", {}, "osint", 0.7, conn)
                    edge_count += 1
                if prof.get("company"):
                    cid = f"org:{prof['company']}"
                    upsert_node(cid, "organization", prof["company"], {}, "osint", conn)
                    upsert_edge(uid, cid, "affiliated_with", {}, "osint", 0.7, conn)
                    edge_count += 1

        elif t == "email":
            email = osint_result.get("email", query)
            eid = f"email:{email}"
            upsert_node(eid, "email", email, {}, "osint", conn)
            if target_id:
                upsert_edge(target_id, eid, "has_email", {}, "osint", 1.0, conn)
                edge_count += 1

            domain = osint_result.get("domain", "")
            if domain:
                did = f"domain:{domain}"
                upsert_node(did, "domain", domain, {}, "osint", conn)
                upsert_edge(eid, did, "email_domain", {}, "osint", 1.0, conn)
                edge_count += 1

            breach = osint_result.get("breach", {})
            for b in breach.get("breaches", []) if isinstance(breach.get("breaches"), list) else []:
                bname = b if isinstance(b, str) else b.get("name", str(b))
                bid = f"breach:{bname}"
                upsert_node(bid, "breach", bname, {}, "osint", conn)
                upsert_edge(eid, bid, "exposed_in", {}, "osint", 0.95, conn)
                edge_count += 1

            for cand in osint_result.get("username_candidates", []):
                cuid = f"username:{cand}"
                upsert_node(cuid, "username", cand, {}, "osint", conn)
                upsert_edge(eid, cuid, "candidate_username", {}, "osint", 0.5, conn)
                edge_count += 1

        elif t == "domain":
            domain = osint_result.get("domain", query)
            did = f"domain:{domain}"
            upsert_node(did, "domain", domain, {}, "osint", conn)
            if target_id:
                upsert_edge(target_id, did, "has_domain", {}, "osint", 1.0, conn)
                edge_count += 1

            for ip in osint_result.get("resolved_ips", []):
                iid = f"ip:{ip}"
                upsert_node(iid, "ip", ip, {}, "osint", conn)
                upsert_edge(did, iid, "resolves_to", {}, "osint", 1.0, conn)
                edge_count += 1

            for sub in (osint_result.get("subdomains_crtsh") or [])[:30]:
                sid = f"domain:{sub}"
                upsert_node(sid, "domain", sub, {}, "osint", conn)
                upsert_edge(did, sid, "has_subdomain", {}, "osint", 0.9, conn)
                edge_count += 1

            for p in osint_result.get("open_ports", []):
                svc_id = f"service:{domain}:{p['port']}"
                upsert_node(svc_id, "service", f"{p['service']}:{p['port']}", {
                    "port": p["port"],
                }, "osint", conn)
                upsert_edge(did, svc_id, "exposes_service", {}, "osint", 1.0, conn)
                edge_count += 1

            ssl = osint_result.get("ssl_cert", {})
            issuer = (ssl.get("issuer") or {}).get("organizationName", "")
            if issuer:
                oid = f"org:{issuer}"
                upsert_node(oid, "organization", issuer, {}, "osint", conn)
                upsert_edge(did, oid, "ssl_issued_by", {}, "osint", 0.8, conn)
                edge_count += 1

        elif t == "ip":
            ip = osint_result.get("ip", query)
            iid = f"ip:{ip}"
            upsert_node(iid, "ip", ip, {}, "osint", conn)
            if target_id:
                upsert_edge(target_id, iid, "has_ip", {}, "osint", 1.0, conn)
                edge_count += 1

            geo = osint_result.get("geo", {})
            if geo.get("isp"):
                ispid = f"org:{geo['isp']}"
                upsert_node(ispid, "organization", geo["isp"], {}, "osint", conn)
                upsert_edge(iid, ispid, "isp", {}, "osint", 0.9, conn)
                edge_count += 1
            if geo.get("country"):
                cid = f"country:{geo['country']}"
                upsert_node(cid, "location", geo["country"], {
                    "lat": geo.get("lat"), "lon": geo.get("lon"),
                }, "osint", conn)
                upsert_edge(iid, cid, "geolocated_in", {}, "osint", 0.8, conn)
                edge_count += 1

            if osint_result.get("reverse_dns"):
                rdid = f"domain:{osint_result['reverse_dns']}"
                upsert_node(rdid, "domain", osint_result["reverse_dns"], {}, "osint", conn)
                upsert_edge(iid, rdid, "reverse_dns", {}, "osint", 0.9, conn)
                edge_count += 1

            for p in osint_result.get("open_ports", []):
                svc_id = f"service:{ip}:{p['port']}"
                upsert_node(svc_id, "service", f"{p['service']}:{p['port']}", {
                    "port": p["port"],
                }, "osint", conn)
                upsert_edge(iid, svc_id, "exposes_service", {}, "osint", 1.0, conn)
                edge_count += 1

        elif t == "phone":
            phone = osint_result.get("format_e164", query)
            phid = f"phone:{phone}"
            upsert_node(phid, "phone", phone, {
                "carrier": osint_result.get("detected_carrier", ""),
                "country": osint_result.get("country", ""),
            }, "osint", conn)
            if target_id:
                upsert_edge(target_id, phid, "has_phone", {}, "osint", 1.0, conn)
                edge_count += 1

            if osint_result.get("detected_carrier"):
                cid = f"org:{osint_result['detected_carrier']}"
                upsert_node(cid, "organization", osint_result["detected_carrier"], {}, "osint", conn)
                upsert_edge(phid, cid, "carrier", {}, "osint", 0.9, conn)
                edge_count += 1

        # Scanner results (dari run_live_osint_recon)
        scanner = osint_result.get("scanner") or {}
        if isinstance(scanner, dict):
            for scan_key, scan_val in scanner.items():
                if not isinstance(scan_val, dict):
                    continue
                for email in (scan_val.get("emails") or []):
                    eid = f"email:{email}"
                    upsert_node(eid, "email", email, {}, "osint", conn)
                    if target_id:
                        upsert_edge(target_id, eid, "has_email", {"via": scan_key}, "osint", 0.85, conn)
                        edge_count += 1
                for extra_ip in (scan_val.get("ips") or []):
                    iid2 = f"ip:{extra_ip}"
                    upsert_node(iid2, "ip", extra_ip, {}, "osint", conn)
                    if target_id:
                        upsert_edge(target_id, iid2, "has_ip", {"via": scan_key}, "osint", 0.85, conn)
                        edge_count += 1
                for sub in (scan_val.get("subdomains") or []):
                    sid = f"domain:{sub}"
                    upsert_node(sid, "domain", sub, {}, "osint", conn)
                    if target_id:
                        upsert_edge(target_id, sid, "has_domain", {"via": scan_key}, "osint", 0.8, conn)
                        edge_count += 1

        conn.commit()
    finally:
        conn.close()
    return edge_count


def ingest_siem_alert(alert_data: dict) -> int:
    """Ingest SIEM alert ke graph — hubungkan unit, IP, lokasi."""
    conn = _get_db()
    edge_count = 0
    try:
        alert_id = alert_data.get("alert_id", f"ALERT-{int(time.time())}")
        aid = f"alert:{alert_id}"
        upsert_node(aid, "siem_alert", alert_id, {
            "severity": alert_data.get("severity", ""),
            "rule": alert_data.get("rule_name", ""),
            "description": alert_data.get("description", ""),
        }, "siem", conn)

        unit_id = alert_data.get("unit_id", "")
        if unit_id:
            upsert_edge(unit_id, aid, "triggered_alert", {}, "siem", 1.0, conn)
            edge_count += 1

        src_ip = alert_data.get("source_ip", alert_data.get("remote_ip", ""))
        if src_ip and src_ip not in ("0.0.0.0", ""):
            iid = f"ip:{src_ip}"
            upsert_node(iid, "ip", src_ip, {}, "siem", conn)
            upsert_edge(aid, iid, "source_ip", {}, "siem", 1.0, conn)
            edge_count += 1

        dst_ip = alert_data.get("dest_ip", "")
        if dst_ip and dst_ip not in ("0.0.0.0", ""):
            iid2 = f"ip:{dst_ip}"
            upsert_node(iid2, "ip", dst_ip, {}, "siem", conn)
            upsert_edge(aid, iid2, "dest_ip", {}, "siem", 1.0, conn)
            edge_count += 1

        conn.commit()
    finally:
        conn.close()
    return edge_count


def ingest_checkin(checkin_data: dict) -> int:
    """Ingest check-in beacon data — fingerprint perangkat target ke graph."""
    conn = _get_db()
    edge_count = 0
    try:
        target_id = checkin_data.get("target_id", "")
        if not target_id:
            return 0

        client_ip = checkin_data.get("client_ip", "")
        if client_ip:
            iid = f"ip:{client_ip}"
            upsert_node(iid, "ip", client_ip, {}, "checkin", conn)
            upsert_edge(target_id, iid, "checkin_from_ip", {
                "user_agent": checkin_data.get("user_agent", ""),
            }, "checkin", 0.9, conn)
            edge_count += 1

        canvas_fp = checkin_data.get("canvas_fp", "")
        if canvas_fp:
            fid = f"fingerprint:canvas:{canvas_fp[:16]}"
            upsert_node(fid, "fingerprint", f"Canvas:{canvas_fp[:16]}", {
                "full_hash": canvas_fp,
            }, "checkin", conn)
            upsert_edge(target_id, fid, "has_fingerprint", {}, "checkin", 0.85, conn)
            edge_count += 1

        webgl_fp = checkin_data.get("webgl_fp", "")
        if webgl_fp:
            gid = f"fingerprint:webgl:{webgl_fp[:16]}"
            upsert_node(gid, "fingerprint", f"WebGL:{webgl_fp[:16]}", {
                "full_hash": webgl_fp,
            }, "checkin", conn)
            upsert_edge(target_id, gid, "has_fingerprint", {}, "checkin", 0.85, conn)
            edge_count += 1

        # WebRTC local IPs — sangat berharga untuk intel
        webrtc_ips = checkin_data.get("webrtc_local_ips", "")
        if webrtc_ips:
            for local_ip in str(webrtc_ips).split(","):
                local_ip = local_ip.strip()
                if local_ip:
                    lip = f"ip:local:{local_ip}"
                    upsert_node(lip, "local_ip", local_ip, {}, "checkin", conn)
                    upsert_edge(target_id, lip, "local_network_ip", {}, "checkin", 0.7, conn)
                    edge_count += 1

        # Lokasi GPS dari check-in
        lat, lon = checkin_data.get("lat"), checkin_data.get("lon")
        if lat is not None and lon is not None:
            try:
                grid_lat = round(float(lat) / 0.001) * 0.001
                grid_lon = round(float(lon) / 0.001) * 0.001
                loc_id = f"loc:{grid_lat:.4f},{grid_lon:.4f}"
                upsert_node(loc_id, "location", f"{grid_lat:.4f},{grid_lon:.4f}", {
                    "lat": grid_lat, "lon": grid_lon,
                }, "checkin", conn)
                upsert_edge(target_id, loc_id, "checkin_at", {
                    "accuracy_m": checkin_data.get("accuracy_m", ""),
                }, "checkin", 0.9, conn)
                edge_count += 1
            except (TypeError, ValueError):
                pass

        conn.commit()
    finally:
        conn.close()
    return edge_count


def ingest_anpr_hit(
    plate: str, camera_id: str, timestamp: str,
    lat: float = None, lon: float = None,
    target_id: str = "",
) -> int:
    """Ingest deteksi plat kendaraan dari ANPR/CCTV."""
    conn = _get_db()
    edge_count = 0
    try:
        if not plate:
            return 0
        plid = f"plate:{plate}"
        upsert_node(plid, "plate", plate, {}, "vision", conn)

        cam_id = f"camera:{camera_id}"
        upsert_node(cam_id, "camera", camera_id, {
            "lat": lat, "lon": lon,
        }, "vision", conn)
        upsert_edge(plid, cam_id, "detected_at", {
            "timestamp": timestamp,
        }, "vision", 1.0, conn)
        edge_count += 1

        if target_id:
            upsert_edge(target_id, plid, "has_plate", {}, "vision", 0.95, conn)
            edge_count += 1

        if lat is not None and lon is not None:
            grid_lat = round(lat / 0.001) * 0.001
            grid_lon = round(lon / 0.001) * 0.001
            loc_id = f"loc:{grid_lat:.4f},{grid_lon:.4f}"
            upsert_node(loc_id, "location", f"{grid_lat:.4f},{grid_lon:.4f}", {
                "lat": grid_lat, "lon": grid_lon,
            }, "vision", conn)
            upsert_edge(plid, loc_id, "seen_at", {"timestamp": timestamp}, "vision", 1.0, conn)
            edge_count += 1

        conn.commit()
    finally:
        conn.close()
    return edge_count


def ingest_c2_event(unit_id: str, event_data: dict) -> int:
    """Ingest event C2 (force ping, tracking, dll.) ke graph."""
    conn = _get_db()
    edge_count = 0
    try:
        if not unit_id:
            return 0
        # Pastikan unit node ada
        upsert_node(unit_id, "tactical_unit", unit_id, {
            "role": event_data.get("role", ""),
        }, "c2", conn)

        cmd = event_data.get("cmd_name", "")
        if cmd:
            evt_id = f"c2_event:{unit_id}:{int(time.time())}"
            upsert_node(evt_id, "c2_event", f"{cmd}→{unit_id}", {
                "cmd_code": event_data.get("cmd_code"),
                "result": event_data.get("result", ""),
            }, "c2", conn)
            upsert_edge(unit_id, evt_id, "received_command", {}, "c2", 1.0, conn)
            edge_count += 1

        # Lokasi dari GPS reply
        lat, lon = event_data.get("lat"), event_data.get("lon")
        if lat is not None and lon is not None:
            try:
                grid_lat = round(float(lat) / 0.001) * 0.001
                grid_lon = round(float(lon) / 0.001) * 0.001
                loc_id = f"loc:{grid_lat:.4f},{grid_lon:.4f}"
                upsert_node(loc_id, "location", f"{grid_lat:.4f},{grid_lon:.4f}", {
                    "lat": grid_lat, "lon": grid_lon,
                }, "c2", conn)
                upsert_edge(unit_id, loc_id, "positioned_at", {}, "c2", 1.0, conn)
                edge_count += 1
            except (TypeError, ValueError):
                pass

        conn.commit()
    finally:
        conn.close()
    return edge_count


def ingest_forensic_artifact(artifact_data: dict) -> int:
    """Ingest artefak forensik ke graph — hubungkan hash, case, target."""
    conn = _get_db()
    edge_count = 0
    try:
        evidence_id = artifact_data.get("evidence_id", "")
        if not evidence_id:
            return 0

        eid = f"evidence:{evidence_id}"
        upsert_node(eid, "evidence", artifact_data.get("file_name", evidence_id), {
            "sha256": artifact_data.get("sha256", ""),
            "mime": artifact_data.get("detected_mime", ""),
            "file_size": artifact_data.get("file_size_bytes", 0),
        }, "forensics", conn)

        case_id = artifact_data.get("case_id", "")
        if case_id:
            cid = f"case:{case_id}"
            upsert_node(cid, "case", case_id, {}, "forensics", conn)
            upsert_edge(eid, cid, "belongs_to_case", {}, "forensics", 1.0, conn)
            edge_count += 1

        target_id = artifact_data.get("linked_target_id", "")
        if target_id:
            upsert_edge(target_id, eid, "linked_evidence", {}, "forensics", 0.9, conn)
            edge_count += 1

        # YARA matches → edge ke rule
        for match in artifact_data.get("yara_matches", []):
            rule_name = match if isinstance(match, str) else match.get("rule", "")
            if rule_name:
                rid = f"yara:{rule_name}"
                upsert_node(rid, "yara_rule", rule_name, {}, "forensics", conn)
                upsert_edge(eid, rid, "matched_yara", {}, "forensics", 1.0, conn)
                edge_count += 1

        conn.commit()
    finally:
        conn.close()
    return edge_count


# ══════════════════════════════════════════════════════════════════════════
#  4. GRAPH ALGORITHMS — Pure Python, Air-Gap Ready
# ══════════════════════════════════════════════════════════════════════════

def _load_adjacency() -> Tuple[Dict[str, Set[str]], Dict[str, dict]]:
    """Load seluruh graph ke adjacency list in-memory untuk algoritma."""
    conn = _get_db()
    try:
        adj: Dict[str, Set[str]] = collections.defaultdict(set)
        edge_meta: Dict[str, list] = collections.defaultdict(list)

        rows = conn.execute("SELECT source_id, target_id, rel_type, confidence FROM graph_edges").fetchall()
        for r in rows:
            adj[r["source_id"]].add(r["target_id"])
            adj[r["target_id"]].add(r["source_id"])  # undirected
            edge_meta[f"{r['source_id']}|{r['target_id']}"].append({
                "rel": r["rel_type"], "conf": r["confidence"],
            })

        node_info = {}
        for r in conn.execute("SELECT node_id, node_type, label FROM graph_nodes").fetchall():
            node_info[r["node_id"]] = {"type": r["node_type"], "label": r["label"]}
            if r["node_id"] not in adj:
                adj[r["node_id"]] = set()

        return adj, node_info
    finally:
        conn.close()


def query_neighborhood(node_id: str, max_hops: int = 2, max_nodes: int = 200, rel_type: str = None) -> dict:
    """
    BFS traversal — kembalikan semua node dan edge dalam radius n-hop dari node_id.
    Ini query paling fundamental: "tunjukkan semua yang terhubung ke X."
    """
    conn = _get_db()
    try:
        visited = set()
        queue = collections.deque([(node_id, 0)])
        visited.add(node_id)
        nodes_out = {}
        edges_out = []

        # Ambil info node awal
        root = conn.execute(
            "SELECT node_id, node_type, label, properties FROM graph_nodes WHERE node_id=?",
            (node_id,),
        ).fetchone()
        if not root:
            return {"ok": False, "error": f"Node '{node_id}' tidak ditemukan"}
        nodes_out[node_id] = {
            "id": root["node_id"], "type": root["node_type"],
            "label": root["label"], "hop": 0,
            "properties": json.loads(root["properties"] or "{}"),
        }

        while queue and len(nodes_out) < max_nodes:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue

            # Ambil semua edge dari/ke current (optionally filter by rel_type)
            if rel_type:
                edge_rows = conn.execute(
                    "SELECT e.source_id, e.target_id, e.rel_type, e.confidence, e.source_module "
                    "FROM graph_edges e WHERE (e.source_id=? OR e.target_id=?) AND e.rel_type=?",
                    (current, current, rel_type),
                ).fetchall()
            else:
                edge_rows = conn.execute(
                    "SELECT e.source_id, e.target_id, e.rel_type, e.confidence, e.source_module "
                    "FROM graph_edges e WHERE e.source_id=? OR e.target_id=?",
                    (current, current),
                ).fetchall()
            for row in edge_rows:
                neighbor = row["target_id"] if row["source_id"] == current else row["source_id"]
                edges_out.append({
                    "source": row["source_id"], "target": row["target_id"],
                    "rel": row["rel_type"], "confidence": row["confidence"],
                    "module": row["source_module"],
                })
                if neighbor not in visited and len(nodes_out) < max_nodes:
                    visited.add(neighbor)
                    n_row = conn.execute(
                        "SELECT node_id, node_type, label, properties FROM graph_nodes WHERE node_id=?",
                        (neighbor,),
                    ).fetchone()
                    if n_row:
                        nodes_out[neighbor] = {
                            "id": n_row["node_id"], "type": n_row["node_type"],
                            "label": n_row["label"], "hop": depth + 1,
                            "properties": json.loads(n_row["properties"] or "{}"),
                        }
                        queue.append((neighbor, depth + 1))

        # Deduplicate edges
        seen_edges = set()
        unique_edges = []
        for e in edges_out:
            key = (e["source"], e["target"], e["rel"])
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        return {
            "ok": True,
            "center": node_id,
            "max_hops": max_hops,
            "nodes": list(nodes_out.values()),
            "edges": unique_edges,
            "stats": {
                "total_nodes": len(nodes_out),
                "total_edges": len(unique_edges),
                "truncated": len(nodes_out) >= max_nodes,
            },
        }
    finally:
        conn.close()


def find_shortest_path(node_a: str, node_b: str, max_depth: int = 8) -> dict:
    """
    BFS shortest path — temukan jalur koneksi terpendek antara dua entitas.
    Ini yang menjawab: "bagaimana target A terhubung ke target B?"
    """
    adj, node_info = _load_adjacency()

    if node_a not in adj:
        return {"ok": False, "error": f"Node '{node_a}' tidak ditemukan"}
    if node_b not in adj:
        return {"ok": False, "error": f"Node '{node_b}' tidak ditemukan"}

    # BFS dari node_a
    visited = {node_a}
    parent = {node_a: None}
    queue = collections.deque([(node_a, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        if current == node_b:
            break
        for neighbor in adj[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                parent[neighbor] = current
                queue.append((neighbor, depth + 1))

    if node_b not in parent:
        return {
            "ok": True, "found": False,
            "message": f"Tidak ada jalur antara '{node_a}' dan '{node_b}' dalam {max_depth} hop",
        }

    # Rekonstruksi jalur
    path_detail = []
    current = node_b
    while current is not None:
        info = node_info.get(current, {"type": "?", "label": current})
        path_detail.append({"id": current, "type": info["type"], "label": info["label"]})
        current = parent[current]
    path_detail.reverse()
    path_ids = [step["id"] for step in path_detail]  # string array for frontend

    # Ambil edge details sepanjang jalur
    conn = _get_db()
    path_edges = []
    try:
        for i in range(len(path_detail) - 1):
            a, b = path_detail[i]["id"], path_detail[i + 1]["id"]
            edge = conn.execute(
                "SELECT rel_type, confidence, source_module FROM graph_edges "
                "WHERE (source_id=? AND target_id=?) OR (source_id=? AND target_id=?) LIMIT 1",
                (a, b, b, a),
            ).fetchone()
            if edge:
                path_edges.append({
                    "from": a, "to": b,
                    "rel": edge["rel_type"],
                    "confidence": edge["confidence"],
                    "module": edge["source_module"],
                })
    finally:
        conn.close()

    return {
        "ok": True, "found": True,
        "hops": len(path_detail) - 1,
        "path": path_ids,          # string[] for frontend compatibility
        "path_detail": path_detail, # full objects for backend use
        "edges": path_edges,
    }


def compute_betweenness_centrality(top_n: int = 20) -> dict:
    """
    Brandes' Algorithm — identifikasi node yang paling sering menjadi
    "jembatan" di jalur terpendek antar node lain.
    Node dengan centrality tinggi = BROKER / FASILITATOR.
    Pure Python O(V*E), cocok untuk graph <10.000 node.
    """
    adj, node_info = _load_adjacency()
    all_nodes = list(adj.keys())
    n = len(all_nodes)

    if n == 0:
        return {"ok": True, "nodes": [], "total_nodes": 0}

    centrality = {v: 0.0 for v in all_nodes}

    for s in all_nodes:
        # BFS dari s
        stack = []
        pred = {v: [] for v in all_nodes}
        sigma = {v: 0 for v in all_nodes}
        sigma[s] = 1
        dist = {v: -1 for v in all_nodes}
        dist[s] = 0
        queue = collections.deque([s])

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)

        # Accumulation
        delta = {v: 0.0 for v in all_nodes}
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                centrality[w] += delta[w]

    # Normalisasi
    if n > 2:
        norm = 1.0 / ((n - 1) * (n - 2))
        for v in centrality:
            centrality[v] *= norm

    # Sort & return top N
    ranked = sorted(centrality.items(), key=lambda x: -x[1])[:top_n]
    result = []
    for node_id, score in ranked:
        info = node_info.get(node_id, {"type": "?", "label": node_id})
        result.append({
            "id": node_id,
            "type": info["type"],
            "label": info["label"],
            "centrality": round(score, 6),
            "connections": len(adj[node_id]),
        })

    return {
        "ok": True,
        "algorithm": "Brandes Betweenness Centrality",
        "total_nodes": n,
        "top": result,
    }


def detect_communities(max_iterations: int = 50) -> dict:
    """
    Label Propagation — deteksi kluster/komunitas secara otomatis.
    Setiap node mengadopsi label yang paling banyak dipakai tetangganya.
    Hasilnya: kelompok-kelompok entitas yang beroperasi bersama.
    Pure Python, konvergen dalam <20 iterasi biasanya.
    """
    adj, node_info = _load_adjacency()
    all_nodes = list(adj.keys())
    n = len(all_nodes)

    if n == 0:
        return {"ok": True, "communities": [], "total_nodes": 0}

    # Inisialisasi: setiap node = komunitasnya sendiri
    labels = {v: i for i, v in enumerate(all_nodes)}

    for iteration in range(max_iterations):
        changed = False
        order = all_nodes[:]
        random.shuffle(order)

        for v in order:
            neighbors = adj[v]
            if not neighbors:
                continue
            # Hitung frekuensi label tetangga
            label_count: Dict[int, int] = collections.defaultdict(int)
            for nb in neighbors:
                label_count[labels[nb]] += 1
            # Ambil label dengan frekuensi tertinggi
            max_freq = max(label_count.values())
            candidates = [lbl for lbl, cnt in label_count.items() if cnt == max_freq]
            best = min(candidates)  # deterministik: ambil label terkecil jika seri
            if labels[v] != best:
                labels[v] = best
                changed = True

        if not changed:
            break

    # Kelompokkan node per komunitas
    communities_raw: Dict[int, list] = collections.defaultdict(list)
    for v, lbl in labels.items():
        info = node_info.get(v, {"type": "?", "label": v})
        communities_raw[lbl].append({
            "id": v, "type": info["type"], "label": info["label"],
        })

    # Sort komunitas berdasarkan ukuran (terbesar dulu), filter yang >1 member
    sorted_comms = sorted(
        [{"community_id": k, "member_detail": v} for k, v in communities_raw.items() if len(v) > 1],
        key=lambda c: -len(c["member_detail"]),
    )

    # Beri nama/deskripsi otomatis berdasarkan komposisi
    for comm in sorted_comms:
        types = collections.Counter(m["type"] for m in comm["member_detail"])
        targets = [m for m in comm["member_detail"] if m["type"] in ("target", "person")]
        comm["members"] = [m["id"] for m in comm["member_detail"]]  # string[] for frontend
        comm["size"] = len(comm["members"])
        comm["composition"] = dict(types)
        comm["key_targets"] = [t["label"] for t in targets[:5]]

    return {
        "ok": True,
        "algorithm": "Label Propagation",
        "iterations": iteration + 1 if 'iteration' in dir() else max_iterations,
        "total_nodes": n,
        "total_communities": len(sorted_comms),
        "communities": sorted_comms[:30],  # Top 30 komunitas
    }


def temporal_edges(hours: int = 48) -> dict:
    """
    Temporal Analysis — edge mana yang baru muncul dalam N jam terakhir?
    Ini menjawab: "ada koneksi baru apa yang terbentuk?"
    """
    conn = _get_db()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = conn.execute(
            "SELECT e.source_id, e.target_id, e.rel_type, e.confidence, e.source_module, e.first_seen, "
            "ns.label AS src_label, ns.node_type AS src_type, "
            "nt.label AS tgt_label, nt.node_type AS tgt_type "
            "FROM graph_edges e "
            "LEFT JOIN graph_nodes ns ON ns.node_id = e.source_id "
            "LEFT JOIN graph_nodes nt ON nt.node_id = e.target_id "
            "WHERE e.first_seen >= ? "
            "ORDER BY e.first_seen DESC",
            (cutoff,),
        ).fetchall()

        edges = []
        for r in rows:
            edges.append({
                "source": {"id": r["source_id"], "type": r["src_type"] or "?", "label": r["src_label"] or r["source_id"]},
                "target": {"id": r["target_id"], "type": r["tgt_type"] or "?", "label": r["tgt_label"] or r["target_id"]},
                "rel": r["rel_type"],
                "confidence": r["confidence"],
                "module": r["source_module"],
                "first_seen": r["first_seen"],
            })

        return {
            "ok": True,
            "window_hours": hours,
            "cutoff": cutoff,
            "new_edges": len(edges),
            "edges": edges[:500],
        }
    finally:
        conn.close()


def find_shared_entities(min_targets: int = 2) -> dict:
    """
    Cross-Target Shared Entity Discovery — entitas mana yang menghubungkan
    dua atau lebih target? Ini inti dari link analysis yang sebenarnya.
    """
    conn = _get_db()
    try:
        # Cari semua node yang terhubung ke >1 target
        rows = conn.execute("""
            SELECT e.target_id AS entity_id, n.node_type, n.label,
                   GROUP_CONCAT(DISTINCT e.source_id) AS target_ids,
                   COUNT(DISTINCT e.source_id) AS target_count
            FROM graph_edges e
            JOIN graph_nodes ns ON ns.node_id = e.source_id AND ns.node_type = 'target'
            JOIN graph_nodes n ON n.node_id = e.target_id
            GROUP BY e.target_id
            HAVING target_count >= ?
            ORDER BY target_count DESC
        """, (min_targets,)).fetchall()

        # Juga cek arah sebaliknya (edge target→entity di source_id)
        rows2 = conn.execute("""
            SELECT e.source_id AS entity_id, n.node_type, n.label,
                   GROUP_CONCAT(DISTINCT e.target_id) AS target_ids,
                   COUNT(DISTINCT e.target_id) AS target_count
            FROM graph_edges e
            JOIN graph_nodes nt ON nt.node_id = e.target_id AND nt.node_type = 'target'
            JOIN graph_nodes n ON n.node_id = e.source_id AND n.node_type != 'target'
            GROUP BY e.source_id
            HAVING target_count >= ?
            ORDER BY target_count DESC
        """, (min_targets,)).fetchall()

        shared = {}
        for r in list(rows) + list(rows2):
            eid = r["entity_id"]
            if eid not in shared:
                shared[eid] = {
                    "entity_id": eid,
                    "type": r["node_type"],
                    "label": r["label"],
                    "connected_targets": r["target_ids"].split(","),
                    "target_count": r["target_count"],
                }
            else:
                # Merge target lists
                existing = set(shared[eid]["connected_targets"])
                existing.update(r["target_ids"].split(","))
                shared[eid]["connected_targets"] = list(existing)
                shared[eid]["target_count"] = len(existing)

        # Filter ulang berdasarkan min_targets setelah merge
        result = [v for v in shared.values() if v["target_count"] >= min_targets]
        result.sort(key=lambda x: -x["target_count"])

        return {
            "ok": True,
            "min_targets": min_targets,
            "shared_entities": len(result),
            "entities": result[:100],
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  4B. ADVANCED INTEL ANALYSIS — Offensive-Grade Graph Intelligence
# ══════════════════════════════════════════════════════════════════════════

# ── Bobot node type untuk threat scoring ──
_TYPE_WEIGHTS = {
    "target": 1.0, "person": 0.9, "organization": 0.7,
    "ip": 0.6, "domain": 0.6, "email": 0.55, "phone": 0.55,
    "username": 0.5, "service": 0.5, "port": 0.45,
    "breach": 0.8, "alert": 0.75, "c2_event": 0.85,
    "forensic_artifact": 0.7, "evidence": 0.7, "yara_rule": 0.65,
    "plate": 0.5, "location": 0.4, "ssl_cert": 0.35,
    "subdomain": 0.45, "asn": 0.4, "platform": 0.3,
    "account": 0.35, "fingerprint": 0.6, "camera": 0.4,
    "local_ip": 0.5, "place": 0.3, "country": 0.2,
    "case": 0.3, "tactical_unit": 0.8, "checkin": 0.5,
}

# ── Entry point types untuk attack path ──
_ENTRY_TYPES = {"ip", "domain", "subdomain", "service", "port", "email", "phone", "username", "account", "breach"}


def _load_full_adjacency() -> Tuple[Dict[str, Set[str]], Dict[str, dict], List[dict]]:
    """Load graf lengkap dengan edge metadata untuk advanced analysis."""
    conn = _get_db()
    try:
        adj: Dict[str, Set[str]] = collections.defaultdict(set)
        all_edges: List[dict] = []

        for r in conn.execute(
            "SELECT source_id, target_id, rel_type, confidence, source_module, first_seen, last_seen "
            "FROM graph_edges"
        ).fetchall():
            adj[r["source_id"]].add(r["target_id"])
            adj[r["target_id"]].add(r["source_id"])
            all_edges.append(dict(r))

        node_info = {}
        for r in conn.execute(
            "SELECT node_id, node_type, label, source_module, first_seen, last_seen FROM graph_nodes"
        ).fetchall():
            node_info[r["node_id"]] = {
                "type": r["node_type"], "label": r["label"],
                "source_module": r["source_module"],
                "first_seen": r["first_seen"], "last_seen": r["last_seen"],
            }
            if r["node_id"] not in adj:
                adj[r["node_id"]] = set()

        return adj, node_info, all_edges
    finally:
        conn.close()


def compute_threat_scores(top_n: int = 30) -> dict:
    """
    Multi-Factor Threat Scoring — skor ancaman komposit untuk setiap node.

    Faktor:
    1. Degree (jumlah koneksi, normalized)
    2. Type Weight (target/c2_event > domain > location)
    3. Cross-Module Presence (muncul di banyak modul = lebih signifikan)
    4. Confidence-Weighted Degree (sum confidence dari semua edge)
    5. Recency (aktivitas terbaru mendapat bobot lebih)
    6. Betweenness proxy (node yang menghubungkan banyak komponen)

    Ini yang membedakan "node penting" dari "noise" di graf besar.
    """
    adj, node_info, all_edges = _load_full_adjacency()
    all_nodes = list(adj.keys())
    n = len(all_nodes)
    if n == 0:
        return {"ok": True, "scored": [], "total_nodes": 0}

    now = datetime.now(timezone.utc)

    # Pre-compute edge confidence sums per node
    conf_sum: Dict[str, float] = collections.defaultdict(float)
    for e in all_edges:
        conf_sum[e["source_id"]] += e["confidence"]
        conf_sum[e["target_id"]] += e["confidence"]

    # Pre-compute degree
    degrees = {v: len(adj[v]) for v in all_nodes}
    max_degree = max(degrees.values()) if degrees else 1

    # Pre-compute max confidence sum
    max_conf = max(conf_sum.values()) if conf_sum else 1.0

    scores = []
    for nid in all_nodes:
        info = node_info.get(nid, {"type": "?", "label": nid, "source_module": "", "last_seen": ""})

        # Factor 1: Degree (normalized)
        degree_score = degrees.get(nid, 0) / max_degree if max_degree > 0 else 0

        # Factor 2: Type weight
        type_score = _TYPE_WEIGHTS.get(info["type"], 0.3)

        # Factor 3: Cross-module presence
        modules = set((info.get("source_module") or "").split(","))
        module_score = min(len(modules) / 4.0, 1.0)  # cap at 4 modules

        # Factor 4: Confidence-weighted degree
        conf_score = conf_sum.get(nid, 0) / max_conf if max_conf > 0 else 0

        # Factor 5: Recency (decay over 30 days)
        recency = 0.3
        ls = info.get("last_seen", "")
        if ls:
            try:
                last = datetime.strptime(ls, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age_hours = (now - last).total_seconds() / 3600
                recency = max(0.0, 1.0 - (age_hours / 720))  # 30 days decay
            except (ValueError, TypeError):
                pass

        # Factor 6: Bridge detection (simplified — nodes connecting different types)
        neighbor_types = set()
        for nb in adj[nid]:
            nb_info = node_info.get(nb, {})
            neighbor_types.add(nb_info.get("type", "?"))
        bridge_score = min(len(neighbor_types) / 5.0, 1.0)

        # Composite threat score (weighted sum)
        threat = (
            0.20 * degree_score +
            0.15 * type_score +
            0.15 * module_score +
            0.15 * conf_score +
            0.15 * recency +
            0.20 * bridge_score
        )

        scores.append({
            "id": nid,
            "node_id": nid,
            "type": info["type"],
            "label": info["label"],
            "threat_score": round(threat, 4),
            "score": round(threat, 4),
            "tier": "",  # filled below
            "factors": {
                "degree_norm": round(degree_score, 3),
                "degree": round(degree_score, 3),
                "type_weight": round(type_score, 3),
                "cross_module": round(module_score, 3),
                "confidence": round(conf_score, 3),
                "recency": round(recency, 3),
                "bridge_score": round(bridge_score, 3),
                "bridge": round(bridge_score, 3),
            },
            "connections": degrees.get(nid, 0),
        })

    scores.sort(key=lambda x: -x["threat_score"])

    # Classify into tiers
    for s in scores:
        ts = s["threat_score"]
        if ts >= 0.7:
            s["tier"] = "CRITICAL"
        elif ts >= 0.5:
            s["tier"] = "HIGH"
        elif ts >= 0.3:
            s["tier"] = "MEDIUM"
        else:
            s["tier"] = "LOW"

    return {
        "ok": True,
        "algorithm": "Multi-Factor Threat Scoring",
        "total_scored": n,
        "tier_breakdown": {
            "CRITICAL": sum(1 for s in scores if s["tier"] == "CRITICAL"),
            "HIGH": sum(1 for s in scores if s["tier"] == "HIGH"),
            "MEDIUM": sum(1 for s in scores if s["tier"] == "MEDIUM"),
            "LOW": sum(1 for s in scores if s["tier"] == "LOW"),
        },
        "scored": scores[:top_n],
    }


def compute_multi_centrality(top_n: int = 20) -> dict:
    """
    Multi-Centrality Analysis — 4 metrik sekaligus untuk identifikasi
    node-node paling berpengaruh dari berbagai sudut pandang:

    1. Degree Centrality — siapa paling banyak koneksi langsung
    2. Closeness Centrality — siapa paling "dekat" ke semua node lain
    3. Eigenvector Centrality — siapa terhubung ke node-node PENTING (PageRank-like)
    4. Combined Influence — skor gabungan dari ketiga metrik

    Setiap metrik menjawab pertanyaan berbeda:
    - Degree: siapa yang "paling sibuk"
    - Closeness: siapa yang bisa reach semua node paling cepat
    - Eigenvector: siapa yang punya "koneksi berkualitas"
    """
    adj, node_info = _load_adjacency()
    all_nodes = list(adj.keys())
    n = len(all_nodes)
    if n < 2:
        return {"ok": True, "total_nodes": n, "analysis": []}

    node_idx = {v: i for i, v in enumerate(all_nodes)}

    # ── 1. Degree Centrality ──
    degree_c = {}
    for v in all_nodes:
        degree_c[v] = len(adj[v]) / (n - 1) if n > 1 else 0

    # ── 2. Closeness Centrality (BFS from each node) ──
    closeness_c = {}
    for s in all_nodes:
        dist = {s: 0}
        queue = collections.deque([s])
        while queue:
            v = queue.popleft()
            for w in adj[v]:
                if w not in dist:
                    dist[w] = dist[v] + 1
                    queue.append(w)
        reachable = len(dist) - 1
        if reachable > 0:
            avg_dist = sum(dist.values()) / reachable
            closeness_c[s] = (reachable / (n - 1)) * (1.0 / avg_dist) if avg_dist > 0 else 0
        else:
            closeness_c[s] = 0.0

    # ── 3. Eigenvector Centrality (Power Iteration) ──
    eigen_c = {v: 1.0 / n for v in all_nodes}
    for _ in range(50):  # max iterations
        new_eigen = {}
        for v in all_nodes:
            s = sum(eigen_c[nb] for nb in adj[v])
            new_eigen[v] = s
        # Normalize
        norm = max(abs(x) for x in new_eigen.values()) or 1.0
        for v in new_eigen:
            new_eigen[v] /= norm
        # Convergence check
        diff = sum(abs(new_eigen[v] - eigen_c[v]) for v in all_nodes)
        eigen_c = new_eigen
        if diff < 1e-6:
            break

    # ── 4. Combined Influence Score ──
    # Normalize each to [0,1]
    max_deg = max(degree_c.values()) or 1
    max_cls = max(closeness_c.values()) or 1
    max_eig = max(eigen_c.values()) or 1

    analysis = []
    for v in all_nodes:
        d_norm = degree_c[v] / max_deg
        c_norm = closeness_c[v] / max_cls
        e_norm = eigen_c[v] / max_eig

        influence = 0.35 * d_norm + 0.30 * c_norm + 0.35 * e_norm
        info = node_info.get(v, {"type": "?", "label": v})

        analysis.append({
            "id": v,
            "type": info["type"],
            "label": info["label"],
            "degree_centrality": round(degree_c[v], 6),
            "closeness_centrality": round(closeness_c[v], 6),
            "eigenvector_centrality": round(eigen_c[v], 6),
            "influence_score": round(influence, 4),
            "connections": len(adj[v]),
        })

    analysis.sort(key=lambda x: -x["influence_score"])

    return {
        "ok": True,
        "algorithm": "Multi-Centrality (Degree + Closeness + Eigenvector)",
        "total_nodes": n,
        "analysis": analysis[:top_n],
    }


def find_attack_paths(target_id: str, max_paths: int = 10, max_depth: int = 6) -> dict:
    """
    Attack Path Analysis — OFFENSIVE.

    Diberikan satu target, temukan semua jalur masuk dari entry point
    (IP, domain, service, email, breach) ke target tersebut.

    Output:
    - Jalur diurutkan berdasarkan "weakness score" (semakin lemah = semakin mudah ditembus)
    - Setiap jalur ditandai dengan attack vector type
    - Pivot points yang muncul di banyak jalur = Critical Control Points
    - OPSEC assessment berdasarkan jumlah shared resources

    Weakness score = rata-rata (1 - confidence) sepanjang jalur.
    Makin rendah confidence edge = makin "lemah" link itu = makin gampang di-exploit.
    Jalur pendek dengan confidence rendah = sweet spot buat attacker.
    """
    conn = _get_db()
    try:
        # Verify target exists
        t = conn.execute("SELECT node_id, label FROM graph_nodes WHERE node_id=?", (target_id,)).fetchone()
        if not t:
            return {"ok": False, "error": f"Target '{target_id}' tidak ditemukan"}

        # Load adjacency with confidence
        adj: Dict[str, Set[str]] = collections.defaultdict(set)
        edge_conf: Dict[str, float] = {}
        edge_rel: Dict[str, str] = {}

        for r in conn.execute("SELECT source_id, target_id, rel_type, confidence FROM graph_edges").fetchall():
            adj[r["source_id"]].add(r["target_id"])
            adj[r["target_id"]].add(r["source_id"])
            key = f"{r['source_id']}|{r['target_id']}"
            key_r = f"{r['target_id']}|{r['source_id']}"
            edge_conf[key] = r["confidence"]
            edge_conf[key_r] = r["confidence"]
            edge_rel[key] = r["rel_type"]
            edge_rel[key_r] = r["rel_type"]

        node_info = {}
        for r in conn.execute("SELECT node_id, node_type, label FROM graph_nodes").fetchall():
            node_info[r["node_id"]] = {"type": r["node_type"], "label": r["label"]}

        # Find all entry point nodes
        entry_points = [
            nid for nid, info in node_info.items()
            if info["type"] in _ENTRY_TYPES and nid != target_id
        ]

        # BFS from target to find reachable entry points (reverse search)
        paths_found = []
        for entry in entry_points:
            # BFS from entry to target
            visited = {entry}
            parent = {entry: None}
            queue = collections.deque([(entry, 0)])
            found = False

            while queue:
                current, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                if current == target_id:
                    found = True
                    break
                for nb in adj[current]:
                    if nb not in visited:
                        visited.add(nb)
                        parent[nb] = current
                        queue.append((nb, depth + 1))

            if not found:
                continue

            # Reconstruct path
            path = []
            cur = target_id
            while cur is not None:
                info = node_info.get(cur, {"type": "?", "label": cur})
                path.append({"id": cur, "type": info["type"], "label": info["label"]})
                cur = parent.get(cur)
            path.reverse()

            # Calculate weakness score
            total_weakness = 0.0
            edge_details = []
            for i in range(len(path) - 1):
                key = f"{path[i]['id']}|{path[i+1]['id']}"
                conf = edge_conf.get(key, 0.5)
                weakness = 1.0 - conf
                total_weakness += weakness
                edge_details.append({
                    "from": path[i]["id"],
                    "to": path[i+1]["id"],
                    "rel": edge_rel.get(key, "?"),
                    "confidence": round(conf, 2),
                    "weakness": round(weakness, 2),
                })

            avg_weakness = total_weakness / len(edge_details) if edge_details else 0
            hops = len(path) - 1

            # Classify attack vector
            entry_type = path[0]["type"]
            if entry_type in ("ip", "service", "port"):
                vector = "NETWORK_INTRUSION"
            elif entry_type in ("domain", "subdomain"):
                vector = "DNS_EXPLOITATION"
            elif entry_type in ("email", "breach"):
                vector = "CREDENTIAL_COMPROMISE"
            elif entry_type in ("phone",):
                vector = "TELECOM_INTERCEPT"
            elif entry_type in ("username", "account"):
                vector = "IDENTITY_PIVOT"
            else:
                vector = "LATERAL_MOVEMENT"

            paths_found.append({
                "entry_point": {"id": path[0]["id"], "type": entry_type, "label": path[0]["label"]},
                "target": {"id": target_id, "label": t["label"]},
                "hops": hops,
                "weakness_score": round(avg_weakness, 4),
                "attack_vector": vector,
                "vector": vector,
                "path": [step["id"] for step in path],
                "path_detail": path,
                "edges": edge_details,
            })

        # Sort by weakness (highest = easiest to exploit) then by hops (shortest)
        paths_found.sort(key=lambda p: (-p["weakness_score"], p["hops"]))
        paths_found = paths_found[:max_paths]

        # Identify pivot points (nodes appearing in 2+ paths)
        pivot_counts: Dict[str, int] = collections.defaultdict(int)
        for p in paths_found:
            seen = set()
            for nid in p["path"]:
                if nid != target_id and nid != p["entry_point"]["id"]:
                    if nid not in seen:
                        pivot_counts[nid] += 1
                        seen.add(nid)

        pivots = []
        for nid, count in sorted(pivot_counts.items(), key=lambda x: -x[1]):
            if count >= 2:
                info = node_info.get(nid, {"type": "?", "label": nid})
                pivots.append({
                    "id": nid, "node_id": nid, "type": info["type"], "label": info["label"],
                    "appears_in_paths": count,
                    "frequency": count,
                    "criticality": "CRITICAL" if count >= 3 else "HIGH",
                })

        # Vector summary
        vector_counts = collections.Counter(p["attack_vector"] for p in paths_found)

        # Determine risk_level from path analysis
        if paths_found:
            max_weakness = paths_found[0]["weakness_score"]
            if max_weakness >= 0.6 or len(paths_found) >= 5:
                risk_level = "CRITICAL"
            elif max_weakness >= 0.4 or len(paths_found) >= 3:
                risk_level = "HIGH"
            elif max_weakness >= 0.2:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
        else:
            risk_level = "LOW"

        return {
            "ok": True,
            "target": {"id": target_id, "label": t["label"]},
            "total_paths": len(paths_found),
            "attack_vectors": dict(vector_counts),
            "paths": paths_found,
            "pivot_points": pivots[:10],
            "assessment": {
                "risk_level": risk_level,
                "easiest_path_weakness": paths_found[0]["weakness_score"] if paths_found else 0,
                "shortest_path_hops": min((p["hops"] for p in paths_found), default=0),
                "unique_vectors": len(vector_counts),
                "critical_pivots": len([p for p in pivots if p["criticality"] == "CRITICAL"]),
            },
        }
    finally:
        conn.close()


def detect_temporal_patterns(hours: int = 168) -> dict:
    """
    Temporal Pattern Analysis — deteksi pola aktivitas dalam graf.

    1. Burst Detection — lonjakan mendadak dalam jumlah edge baru per jam
    2. Activity Heatmap — pola aktivitas per jam (0-23 UTC)
    3. Edge Velocity — kecepatan pembentukan koneksi baru (per jam)
    4. Dormant-to-Active — node yang diam lalu tiba-tiba aktif lagi
    5. First Contact Timeline — urutan kronologis kapan target pertama kali
       terhubung ke entitas baru

    Ini menjawab: "kapan ada sesuatu yang BERUBAH di jaringan?"
    """
    conn = _get_db()
    try:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Load edges within window
        rows = conn.execute(
            "SELECT source_id, target_id, rel_type, confidence, source_module, first_seen, last_seen "
            "FROM graph_edges WHERE first_seen >= ? ORDER BY first_seen ASC",
            (cutoff,),
        ).fetchall()

        if not rows:
            return {"ok": True, "window_hours": hours, "total_new_edges": 0,
                    "bursts": [], "hourly_heatmap": {}, "velocity": [],
                    "dormant_reactivated": [], "first_contacts": []}

        # ── 1. Hourly bucketing ──
        hourly: Dict[str, int] = collections.defaultdict(int)
        hour_of_day: Dict[int, int] = collections.defaultdict(int)
        edge_list = []
        for r in rows:
            fs = r["first_seen"]
            edge_list.append(dict(r))
            # Bucket by hour
            hour_key = fs[:13]  # "2024-01-15T08"
            hourly[hour_key] += 1
            try:
                h = int(fs[11:13])
                hour_of_day[h] += 1
            except (ValueError, IndexError):
                pass

        # ── 2. Burst Detection ──
        # A burst = hour where edge count > 2 * rolling average
        sorted_hours = sorted(hourly.keys())
        bursts = []
        if len(sorted_hours) >= 3:
            counts = [hourly[h] for h in sorted_hours]
            for i in range(2, len(counts)):
                rolling_avg = sum(counts[max(0, i - 6):i]) / min(i, 6)
                if rolling_avg > 0 and counts[i] > 2 * rolling_avg and counts[i] >= 3:
                    bursts.append({
                        "hour": sorted_hours[i],
                        "edge_count": counts[i],
                        "rolling_avg": round(rolling_avg, 1),
                        "spike_ratio": round(counts[i] / rolling_avg, 1),
                    })

        # ── 3. Activity Heatmap (by hour of day) ──
        heatmap = {str(h).zfill(2): hour_of_day.get(h, 0) for h in range(24)}
        peak_hour = max(hour_of_day, key=hour_of_day.get) if hour_of_day else 0

        # ── 4. Edge Velocity ──
        velocity = []
        if len(sorted_hours) >= 2:
            window = min(6, len(sorted_hours))
            for i in range(0, len(sorted_hours), window):
                chunk = sorted_hours[i:i + window]
                total = sum(hourly[h] for h in chunk)
                velocity.append({
                    "period_start": chunk[0],
                    "period_end": chunk[-1],
                    "edges": total,
                    "avg_per_hour": round(total / len(chunk), 1),
                })

        # ── 5. Dormant-to-Active Detection ──
        # Nodes whose last_seen was OLD but got new edges recently
        dormant_threshold = (now - timedelta(hours=hours * 2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        recent_threshold = (now - timedelta(hours=min(hours, 48))).strftime("%Y-%m-%dT%H:%M:%SZ")

        dormant_rows = conn.execute("""
            SELECT n.node_id, n.node_type, n.label, n.first_seen, n.last_seen,
                   COUNT(e.edge_id) AS new_edges
            FROM graph_nodes n
            JOIN graph_edges e ON (e.source_id = n.node_id OR e.target_id = n.node_id)
                AND e.first_seen >= ?
            WHERE n.first_seen < ?
            GROUP BY n.node_id
            HAVING new_edges >= 2
            ORDER BY new_edges DESC
            LIMIT 15
        """, (recent_threshold, dormant_threshold)).fetchall()

        dormant_reactivated = []
        for r in dormant_rows:
            dormant_reactivated.append({
                "id": r["node_id"], "type": r["node_type"], "label": r["label"],
                "first_seen": r["first_seen"], "last_seen": r["last_seen"],
                "new_edges": r["new_edges"],
            })

        # ── 6. First Contact Timeline ──
        first_contacts = conn.execute("""
            SELECT e.source_id, e.target_id, e.rel_type, e.first_seen, e.confidence,
                   ns.label AS src_label, ns.node_type AS src_type,
                   nt.label AS tgt_label, nt.node_type AS tgt_type
            FROM graph_edges e
            JOIN graph_nodes ns ON ns.node_id = e.source_id
            JOIN graph_nodes nt ON nt.node_id = e.target_id
            WHERE (ns.node_type = 'target' OR nt.node_type = 'target')
                AND e.first_seen >= ?
            ORDER BY e.first_seen DESC
            LIMIT 30
        """, (cutoff,)).fetchall()

        contacts = []
        for r in first_contacts:
            contacts.append({
                "source": {"id": r["source_id"], "type": r["src_type"], "label": r["src_label"]},
                "target": {"id": r["target_id"], "type": r["tgt_type"], "label": r["tgt_label"]},
                "rel": r["rel_type"],
                "confidence": r["confidence"],
                "first_seen": r["first_seen"],
            })

        return {
            "ok": True,
            "window_hours": hours,
            "total_new_edges": len(rows),
            "bursts": bursts,
            "peak_activity_hour_utc": peak_hour,
            "hourly_heatmap": heatmap,
            "velocity": velocity,
            "dormant_reactivated": dormant_reactivated,
            "first_contacts": contacts,
        }
    finally:
        conn.close()


def predict_links(top_n: int = 20, min_common: int = 2) -> dict:
    """
    Link Prediction — prediksi koneksi TERSEMBUNYI yang belum terdeteksi.

    Menggunakan Jaccard Similarity + Common Neighbors:
    - Dua node yang share banyak neighbor tapi TIDAK terhubung langsung →
      kemungkinan besar ada koneksi yang belum teridentifikasi.

    Ini tools intel OFFENSIVE: menunjukkan di mana harus "menggali lebih dalam."
    Misalnya jika target A dan target B share 3 IP tapi tidak terhubung langsung,
    itu indikasi kuat mereka terkait tapi belum ada bukti langsung.

    Score = |common_neighbors(A,B)| / |union_neighbors(A,B)| (Jaccard)
    """
    adj, node_info = _load_adjacency()
    all_nodes = list(adj.keys())
    n = len(all_nodes)
    if n < 3:
        return {"ok": True, "total_predictions": 0, "predictions": []}

    # Focus on "interesting" nodes — skip low-value types
    interesting_types = {
        "target", "person", "ip", "domain", "email", "phone", "username",
        "organization", "breach", "service", "plate",
    }
    candidates = [
        v for v in all_nodes
        if node_info.get(v, {}).get("type", "") in interesting_types
    ]

    # For efficiency, only check pairs where at least one is a target or high-value
    high_value = [v for v in candidates if node_info.get(v, {}).get("type", "") in ("target", "person", "organization")]
    if not high_value:
        high_value = candidates[:50]

    predictions = []
    checked = set()

    for a in high_value:
        neighbors_a = adj[a]
        for b in candidates:
            if a == b or b in neighbors_a:
                continue  # Skip self and already-connected
            pair = tuple(sorted([a, b]))
            if pair in checked:
                continue
            checked.add(pair)

            neighbors_b = adj[b]
            common = neighbors_a & neighbors_b
            if len(common) < min_common:
                continue

            union = neighbors_a | neighbors_b
            jaccard = len(common) / len(union) if union else 0

            # Classify common neighbor types
            common_types = collections.Counter(
                node_info.get(c, {}).get("type", "?") for c in common
            )

            info_a = node_info.get(a, {"type": "?", "label": a})
            info_b = node_info.get(b, {"type": "?", "label": b})

            predictions.append({
                "node_a": {"id": a, "type": info_a["type"], "label": info_a["label"]},
                "node_b": {"id": b, "type": info_b["type"], "label": info_b["label"]},
                "jaccard_score": round(jaccard, 4),
                "common_neighbors": len(common),
                "common_types": dict(common_types),
                "common_nodes": [
                    {"id": c, "type": node_info.get(c, {}).get("type", "?"),
                     "label": node_info.get(c, {}).get("label", c)}
                    for c in list(common)[:8]
                ],
                "confidence": "HIGH" if jaccard > 0.3 else ("MEDIUM" if jaccard > 0.15 else "LOW"),
            })

    predictions.sort(key=lambda x: -x["jaccard_score"])

    return {
        "ok": True,
        "algorithm": "Jaccard Similarity + Common Neighbors",
        "total_predictions": len(predictions),
        "predictions": predictions[:top_n],
    }


def compute_target_profile(target_id: str) -> dict:
    """
    Target Profiling Score — assessment lengkap satu target.

    Mengukur:
    1. Infrastructure Exposure — berapa IP, domain, service, port yang terekspos
    2. Digital Footprint — email, username, account, breach exposure
    3. OPSEC Score — seberapa banyak shared resources (lebih banyak shared = OPSEC buruk)
    4. Network Reach — seberapa "dalam" target terhubung di graf
    5. Intelligence Gaps — area yang belum ada datanya

    Ini untuk membuat "dossier score" otomatis per target.
    """
    conn = _get_db()
    try:
        # Verify target exists
        t = conn.execute(
            "SELECT node_id, node_type, label, properties, first_seen, last_seen FROM graph_nodes WHERE node_id=?",
            (target_id,),
        ).fetchone()
        if not t:
            return {"ok": False, "error": f"Target '{target_id}' tidak ditemukan"}

        # Get all directly connected nodes
        edges = conn.execute("""
            SELECT e.target_id AS neighbor, e.rel_type, e.confidence, e.source_module,
                   n.node_type, n.label
            FROM graph_edges e
            JOIN graph_nodes n ON n.node_id = e.target_id
            WHERE e.source_id = ?
            UNION
            SELECT e.source_id AS neighbor, e.rel_type, e.confidence, e.source_module,
                   n.node_type, n.label
            FROM graph_edges e
            JOIN graph_nodes n ON n.node_id = e.source_id
            WHERE e.target_id = ?
        """, (target_id, target_id)).fetchall()

        # Categorize connected nodes
        infra = {"ip": [], "domain": [], "subdomain": [], "service": [], "port": []}
        digital = {"email": [], "username": [], "account": [], "breach": [], "platform": []}
        physical = {"phone": [], "plate": [], "location": [], "camera": []}
        intel = {"alert": [], "c2_event": [], "evidence": [], "forensic_artifact": []}
        other = []

        for e in edges:
            nt = e["node_type"]
            entry = {"id": e["neighbor"], "label": e["label"], "rel": e["rel_type"],
                     "confidence": e["confidence"], "module": e["source_module"]}
            if nt in infra:
                infra[nt].append(entry)
            elif nt in digital:
                digital[nt].append(entry)
            elif nt in physical:
                physical[nt].append(entry)
            elif nt in intel:
                intel[nt].append(entry)
            else:
                other.append({**entry, "type": nt})

        # ── 1. Infrastructure Exposure Score ──
        infra_count = sum(len(v) for v in infra.values())
        infra_score = min(infra_count / 15.0, 1.0)  # Cap at 15 infra items

        # ── 2. Digital Footprint Score ──
        digital_count = sum(len(v) for v in digital.values())
        breach_count = len(digital["breach"])
        digital_score = min(digital_count / 10.0, 1.0)

        # ── 3. OPSEC Assessment ──
        # Check how many of this target's resources are shared with other targets
        shared_count = 0
        for cat in [infra, digital, physical]:
            for items in cat.values():
                for item in items:
                    shared = conn.execute("""
                        SELECT COUNT(DISTINCT CASE WHEN e.source_id != ? THEN e.source_id END) +
                               COUNT(DISTINCT CASE WHEN e.target_id != ? THEN e.target_id END) AS others
                        FROM graph_edges e
                        WHERE (e.source_id = ? OR e.target_id = ?)
                    """, (target_id, target_id, item["id"], item["id"])).fetchone()
                    if shared and shared["others"] > 0:
                        shared_count += 1

        total_assets = infra_count + digital_count + len([v for items in physical.values() for v in items])
        opsec_ratio = shared_count / total_assets if total_assets > 0 else 0
        opsec_score = max(0, 1.0 - opsec_ratio)  # 1.0 = perfect OPSEC, 0.0 = everything shared

        if opsec_score >= 0.8:
            opsec_grade = "STRONG"
        elif opsec_score >= 0.5:
            opsec_grade = "MODERATE"
        elif opsec_score >= 0.3:
            opsec_grade = "WEAK"
        else:
            opsec_grade = "COMPROMISED"

        # ── 4. Network Reach (BFS depth) ──
        visited = {target_id}
        queue = collections.deque([(target_id, 0)])
        depth_counts = collections.defaultdict(int)
        max_reached = 0
        while queue:
            cur, d = queue.popleft()
            if d > 4:
                continue
            for row in conn.execute(
                "SELECT CASE WHEN source_id=? THEN target_id ELSE source_id END AS nb "
                "FROM graph_edges WHERE source_id=? OR target_id=?",
                (cur, cur, cur),
            ).fetchall():
                nb = row["nb"]
                if nb not in visited:
                    visited.add(nb)
                    depth_counts[d + 1] += 1
                    max_reached = max(max_reached, d + 1)
                    queue.append((nb, d + 1))

        reach_score = min(len(visited) / 50.0, 1.0)

        # ── 5. Intelligence Gaps ──
        gaps = []
        if not infra["ip"]:
            gaps.append({"area": "IP Address", "priority": "HIGH", "action": "Run IP recon / passive DNS"})
        if not infra["domain"]:
            gaps.append({"area": "Domain", "priority": "HIGH", "action": "Run domain enumeration"})
        if not digital["email"]:
            gaps.append({"area": "Email", "priority": "MEDIUM", "action": "Run email OSINT / breach check"})
        if not digital["username"]:
            gaps.append({"area": "Username", "priority": "MEDIUM", "action": "Run username enumeration"})
        if not digital["breach"]:
            gaps.append({"area": "Breach Data", "priority": "LOW", "action": "Check breach databases"})
        if not physical["phone"]:
            gaps.append({"area": "Phone Number", "priority": "MEDIUM", "action": "Run phone OSINT / HLR lookup"})
        if not physical["location"]:
            gaps.append({"area": "Geolocation", "priority": "LOW", "action": "Correlate IP geolocation / check-ins"})

        # ── Overall Profile Score ──
        profile_score = (
            0.25 * infra_score +
            0.25 * digital_score +
            0.20 * (1.0 - opsec_score) +  # Inverted — worse OPSEC = easier to profile
            0.15 * reach_score +
            0.15 * min(breach_count / 3.0, 1.0)
        )

        return {
            "ok": True,
            "target": {"id": target_id, "label": t["label"]},
            "profile_score": round(profile_score, 3),
            "profile_grade": (
                "FULLY PROFILED" if profile_score >= 0.7 else
                "WELL KNOWN" if profile_score >= 0.5 else
                "PARTIAL" if profile_score >= 0.3 else
                "MINIMAL"
            ),
            "infrastructure": {k: [{"id": i["id"], "label": i["label"]} for i in v] for k, v in infra.items()},
            "digital_footprint": {k: [{"id": i["id"], "label": i["label"]} for i in v] for k, v in digital.items()},
            "physical_indicators": {k: [{"id": i["id"], "label": i["label"]} for i in v] for k, v in physical.items()},
            "intel_items": {k: [{"id": i["id"], "label": i["label"]} for i in v] for k, v in intel.items()},
            "scores": {
                "infra_exposure": round(infra_score, 3),
                "digital_footprint": round(digital_score, 3),
                "opsec_score": round(opsec_score, 3),
                "opsec_grade": opsec_grade,
                "network_reach": round(reach_score, 3),
                "breach_exposure": breach_count,
            },
            "network_reach": {
                "total_reachable": len(visited),
                "max_depth": max_reached,
                "by_hop": dict(depth_counts),
            },
            "intelligence_gaps": gaps,
            "shared_resources": shared_count,
            "total_assets": total_assets,
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  5. UNIFIED GRAPH API — Backward Compatible
# ══════════════════════════════════════════════════════════════════════════

def build_unified_graph(target_id: str = None) -> dict:
    """
    Pengganti build_link_graph() dan build_knowledge_graph().
    Jika target_id diberikan → neighborhood 2-hop dari target itu.
    Jika tidak → seluruh graph dengan cross-target shared entities.
    """
    if target_id:
        return query_neighborhood(target_id, max_hops=2, max_nodes=300)

    # Full graph mode — mirip build_link_graph tapi dari unified store
    conn = _get_db()
    try:
        nodes = []
        for r in conn.execute("SELECT node_id, node_type, label, properties FROM graph_nodes").fetchall():
            props = json.loads(r["properties"] or "{}")
            nodes.append({
                "id": r["node_id"], "type": r["node_type"],
                "label": r["label"],
                "properties": props,
                "meta": props,
            })

        edges = []
        for r in conn.execute(
            "SELECT source_id, target_id, rel_type, confidence, source_module FROM graph_edges"
        ).fetchall():
            edges.append({
                "source": r["source_id"], "target": r["target_id"],
                "rel": r["rel_type"], "confidence": r["confidence"],
                "module": r["source_module"],
            })

        # Stats
        type_counts = collections.Counter(n["type"] for n in nodes)
        module_counts = collections.Counter(e["module"] for e in edges)

        return {
            "ok": True,
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "node_types": dict(type_counts),
                "edge_sources": dict(module_counts),
            },
        }
    finally:
        conn.close()


def graph_stats() -> dict:
    """Statistik ringkas graph — untuk dashboard overview."""
    conn = _get_db()
    try:
        total_nodes = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        total_edges = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]

        type_counts = {}
        for r in conn.execute("SELECT node_type, COUNT(*) AS c FROM graph_nodes GROUP BY node_type ORDER BY c DESC"):
            type_counts[r["node_type"]] = r["c"]

        module_counts = {}
        for r in conn.execute("SELECT source_module, COUNT(*) AS c FROM graph_edges GROUP BY source_module ORDER BY c DESC"):
            module_counts[r["source_module"]] = r["c"]

        rel_counts = {}
        for r in conn.execute("SELECT rel_type, COUNT(*) AS c FROM graph_edges GROUP BY rel_type ORDER BY c DESC LIMIT 20"):
            rel_counts[r["rel_type"]] = r["c"]

        # Nodes terbaru
        recent = []
        for r in conn.execute(
            "SELECT node_id, node_type, label, first_seen FROM graph_nodes ORDER BY first_seen DESC LIMIT 10"
        ):
            recent.append({
                "id": r["node_id"], "type": r["node_type"],
                "label": r["label"], "first_seen": r["first_seen"],
            })

        # Count person-type nodes as targets
        total_targets = type_counts.get("person", 0)

        # Convert node_types dict to top_types array for frontend
        top_types = [{"type": t, "count": c} for t, c in type_counts.items()]
        top_types.sort(key=lambda x: -x["count"])

        return {
            "ok": True,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_targets": total_targets,
            "node_types": type_counts,
            "top_types": top_types,
            "edge_modules": module_counts,
            "top_relations": rel_counts,
            "recent_nodes": recent,
        }
    finally:
        conn.close()


def rebuild_graph_from_targets() -> dict:
    """
    Bootstrap: rebuild seluruh graph dari tabel target_profiles yang sudah ada.
    Dipanggil sekali saat migrasi, atau kapan saja untuk resync.
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT target_id, code_name, phone_id, primary_ip, primary_domain, "
            "plate_number, lat, lon, risk_score, risk_level, osint_json FROM target_profiles"
        ).fetchall()
    finally:
        conn.close()

    total_edges = 0
    for row in rows:
        total_edges += ingest_target_profile(dict(row))
        # Juga ingest OSINT JSON jika ada
        try:
            osint = json.loads(row["osint_json"] or "{}")
            if osint:
                total_edges += ingest_osint_result(row["target_id"], osint)
        except Exception:
            pass

    return {
        "ok": True,
        "targets_processed": len(rows),
        "total_edges_created": total_edges,
    }


# ══════════════════════════════════════════════════════════════════════════
#  6. INIT — Panggil saat server startup
# ══════════════════════════════════════════════════════════════════════════

init_graph_schema()
