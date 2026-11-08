#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Mesin Inti 6 Pilar (C4ISR, Off-Grid, Visual AI, AI Target Profiling,
Converged Cyber-Physical SIEM, & Digital Forensic Toolkit / DFIR).
100% On-Premise / Air-Gapped Ready (Standar Pustaka Python Murni + SQLite).
"""

import base64
import hashlib
import json
import math
import os
import re
import socket
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from crypto_c2 import (
    CMD_FORCE_GPS_PING,
    build_c2_sms_packet,
    build_encrypted_telemetry_reply,
    verify_c2_sms_packet,
)
from real_forensics import (
    compute_shannon_entropy,
    extract_real_binary_metadata,
    generate_real_sample_pcap_bytes,
    generate_real_sample_sqlite_bytes,
    inspect_real_pcap_bytes,
    inspect_real_sqlite_bytes,
)
from real_osint import run_live_osint_recon
from real_siem import scan_live_host_sockets
from triangulation import (
    distance_to_rssi_dbm,
    estimate_position,
    haversine_m as tri_haversine_m,
)
from celltower_lookup import geolocate_cells as _geolocate_cells_real
from forensic_ai import (
    detect_objects as detect_objects_real,
    engines_status as forensic_ai_status,
    grab_stream_frame as grab_stream_frame_real,
    ocr_plate_text as ocr_plate_text_real,
    run_ocr as run_ocr_real,
    scan_yara as scan_yara_real,
    transcribe_audio as transcribe_audio_real,
)

# ── Unified Intelligence Graph Engine ──
import engine_graph

# Lantai sinyal (dBm): di bawah ini menara BTS dianggap tak terdengar perangkat.
BTS_AUDIBLE_FLOOR_DBM = -108.0

DB_PATH = os.path.join(os.path.dirname(__file__), "tfael_omni.db")

# Tabel yang HANYA berisi data contoh/peraga (bukan menara, bukan akun login).
# Dikosongkan oleh tools/clear_demo.py dan tidak diisi saat OMNI_DEMO=0.
DEMO_TABLES = (
    "tactical_units",
    "target_profiles",
    "siem_alerts",
    "forensic_evidence_vault",
    "geofences",
)


def demo_mode_enabled() -> bool:
    """Mode demo (seed data contoh) aktif kecuali OMNI_DEMO di-set 0/false/no/off."""
    return os.environ.get("OMNI_DEMO", "1").strip().lower() not in ("0", "false", "no", "off")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_live_lan_ip() -> str:
    """Mendeteksi IP Wi-Fi / LAN aktif Mac saat ini secara dinamis."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Menghitung jarak Great-Circle (km) menggunakan rumus Haversine (SRS-SIM-02)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def point_in_polygon(lat: float, lon: float, polygon: List[List[float]]) -> bool:
    """Evaluasi spasial Point-in-Polygon (Ray-Casting) untuk Geofencing (<1 ms, SRS-VIS-02)."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]
        yj, xj = polygon[j][0], polygon[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def parse_aprs_packet(raw_packet: str) -> Dict[str, Any]:
    """
    Dekoder paket radio VHF/UHF APRS AX.25 / TNC2 (SRS-OFF-01).
    Contoh format: YB0TFL-9>APRS,WIDE1-1:!0610.52S/10649.63E>180/032/A=000145 Patroli Hutan
    """
    result = {
        "raw": raw_packet,
        "valid": False,
        "callsign": "UNKNOWN",
        "lat": -6.1754,
        "lon": 106.8272,
        "speed_kmh": 0,
        "course_deg": 0,
        "alt_m": 50,
        "comment": "",
        "channel": "APRS_VHF",
    }
    try:
        if ">" in raw_packet and ":" in raw_packet:
            header, info = raw_packet.split(":", 1)
            result["callsign"] = header.split(">")[0].strip()
            m = re.search(
                r"[!=/@](\d{2})(\d{2}\.\d{2})([NS])[\/\\](\d{3})(\d{2}\.\d{2})([EW]).?",
                info,
            )
            if m:
                lat_deg, lat_min, ns, lon_deg, lon_min, ew = m.groups()
                lat = int(lat_deg) + float(lat_min) / 60.0
                if ns == "S":
                    lat = -lat
                lon = int(lon_deg) + float(lon_min) / 60.0
                if ew == "W":
                    lon = -lon
                result["lat"] = round(lat, 6)
                result["lon"] = round(lon, 6)
                result["valid"] = True
                rest = info[m.end() :]
                cs_m = re.match(r"(\d{3})/(\d{3})", rest)
                if cs_m:
                    result["course_deg"] = int(cs_m.group(1))
                    result["speed_kmh"] = int(round(int(cs_m.group(2)) * 1.852))
                alt_m = re.search(r"/A=(\d{6})", rest)
                if alt_m:
                    result["alt_m"] = int(round(int(alt_m.group(1)) * 0.3048))
                result["comment"] = re.sub(r"^(\d{3}/\d{3})?(/A=\d{6})?\s*", "", rest).strip()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def parse_meshtastic_packet(raw_payload: str) -> Dict[str, Any]:
    """
    Dekoder paket posisi LoRa Meshtastic (format JSON dari `meshtastic --listen`
    atau bridge MQTT). Mendukung dua bentuk:
      - Native: {"fromId":"!a1b2", "decoded":{"position":{"latitudeI":-61754000,
                 "longitudeI":1068272000, "altitude":50}}}  (lat/lon = int derajat ×1e7)
      - Datar : {"callsign":"NODE-7","lat":-6.17,"lon":106.82,"alt_m":50,"speed_kmh":0}
    """
    result = {
        "raw": raw_payload, "valid": False, "callsign": "MESH-UNKNOWN",
        "lat": 0.0, "lon": 0.0, "speed_kmh": 0, "course_deg": 0,
        "alt_m": 0, "comment": "", "channel": "LORA_MESH",
    }
    try:
        d = json.loads(raw_payload)
        # Callsign: fromId / from / callsign / id
        cs = d.get("fromId") or d.get("callsign") or d.get("from") or d.get("id")
        if cs is not None:
            result["callsign"] = str(cs)
        pos = (d.get("decoded", {}) or {}).get("position") if isinstance(d.get("decoded"), dict) else None
        if pos and ("latitudeI" in pos or "latitude" in pos):
            lat = pos["latitudeI"] / 1e7 if "latitudeI" in pos else float(pos["latitude"])
            lon = pos["longitudeI"] / 1e7 if "longitudeI" in pos else float(pos["longitude"])
            result["lat"], result["lon"] = round(lat, 6), round(lon, 6)
            result["alt_m"] = int(pos.get("altitude", 0) or 0)
            result["valid"] = True
        elif "lat" in d and "lon" in d:
            result["lat"], result["lon"] = round(float(d["lat"]), 6), round(float(d["lon"]), 6)
            result["alt_m"] = int(d.get("alt_m", 0) or 0)
            result["speed_kmh"] = int(d.get("speed_kmh", 0) or 0)
            result["comment"] = str(d.get("comment", ""))
            result["valid"] = True
        if result["valid"] and not (-90 <= result["lat"] <= 90 and -180 <= result["lon"] <= 180):
            result["valid"] = False
    except Exception as exc:
        result["error"] = str(exc)
    return result


def radio_unit_id(callsign: str) -> str:
    """ID unit stabil dari callsign radio (satu callsign = satu unit di peta)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "", (callsign or "").replace("!", "").strip()) or "UNKNOWN"
    return f"RADIO-{safe.upper()}"[:40]


# ==============================================================================
# INISIALISASI DATABASE TERPADU (SQLite untuk MVP On-Premise)
# ==============================================================================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS tactical_units (
            unit_id TEXT PRIMARY KEY,
            callsign TEXT,
            name TEXT,
            role TEXT,
            channel TEXT,
            status_color TEXT,
            lat REAL,
            lon REAL,
            alt_m INTEGER,
            speed_kmh INTEGER,
            battery_pct INTEGER,
            signal_dbm INTEGER,
            mcc INTEGER,
            mnc INTEGER,
            lac INTEGER,
            cid INTEGER,
            bts_radius_m INTEGER,
            last_seen TEXT,
            trail_json TEXT
        );

        CREATE TABLE IF NOT EXISTS bts_towers (
            tower_id TEXT PRIMARY KEY,
            operator TEXT,
            mcc INTEGER,
            mnc INTEGER,
            lac INTEGER,
            cid INTEGER,
            lat REAL,
            lon REAL,
            radius_m INTEGER,
            area_name TEXT
        );

        CREATE TABLE IF NOT EXISTS geofences (
            zone_id TEXT PRIMARY KEY,
            zone_name TEXT,
            zone_type TEXT,
            color TEXT,
            polygon_json TEXT
        );

        CREATE TABLE IF NOT EXISTS target_profiles (
            target_id TEXT PRIMARY KEY,
            code_name TEXT,
            real_name TEXT,
            category TEXT,
            plate_number TEXT,
            phone_id TEXT,
            primary_domain TEXT,
            primary_ip TEXT,
            asn TEXT,
            lat REAL,
            lon REAL,
            cyber_score INTEGER,
            spatial_score INTEGER,
            visual_score INTEGER,
            forensic_score INTEGER,
            risk_score INTEGER,
            risk_level TEXT,
            osint_json TEXT,
            pattern_of_life_json TEXT,
            graph_json TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS siem_alerts (
            alert_id TEXT PRIMARY KEY,
            event_time TEXT,
            severity TEXT,
            sigma_rule TEXT,
            mitre_tactic TEXT,
            mitre_id TEXT,
            mitre_name TEXT,
            user_or_unit TEXT,
            src_ip TEXT,
            cyber_lat REAL,
            cyber_lon REAL,
            phys_lat REAL,
            phys_lon REAL,
            distance_km REAL,
            velocity_kmh REAL,
            description TEXT,
            status TEXT,
            soar_action_taken TEXT
        );

        CREATE TABLE IF NOT EXISTS forensic_evidence_vault (
            block_index INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id TEXT UNIQUE,
            case_id TEXT,
            file_name TEXT,
            file_size INTEGER,
            magic_mime TEXT,
            sha256_hash TEXT,
            sha512_hash TEXT,
            prev_chain_hash TEXT,
            curr_chain_hash TEXT,
            exif_json TEXT,
            ela_anomaly_score REAL,
            yara_matches_json TEXT,
            extracted_entities_json TEXT,
            carved_records_json TEXT,
            transcript_text TEXT,
            linked_target_id TEXT,
            examiner_id TEXT,
            acquired_at TEXT
        );

        CREATE TABLE IF NOT EXISTS c2_audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            operator_id TEXT,
            action_type TEXT,
            target_ref TEXT,
            crypto_proof TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS map_annotations (
            anno_id TEXT PRIMARY KEY,
            kind TEXT,
            lat REAL,
            lon REAL,
            radius_m REAL,
            label TEXT,
            color TEXT,
            created_by TEXT,
            created_at TEXT,
            photo TEXT
        );

        CREATE TABLE IF NOT EXISTS unit_cells (
            unit_id TEXT PRIMARY KEY,
            cells_json TEXT
        );

        CREATE TABLE IF NOT EXISTS routes (
            route_id TEXT PRIMARY KEY,
            name TEXT,
            points_json TEXT,
            waypoints_json TEXT,
            total_km REAL,
            created_at TEXT,
            active INTEGER DEFAULT 0
        );
        """
    )

    # Seed data contoh jika kosong — hanya bila mode demo aktif (default).
    # Jalankan dengan OMNI_DEMO=0 untuk server bersih: unit/target/SIEM/forensik
    # TIDAK diisi contoh, jadi setiap panel terisi hanya oleh input nyata Anda.
    # (Menara OpenCellID & akun login di-seed terpisah dan tetap tersedia.)
    if demo_mode_enabled():
        cur.execute("SELECT COUNT(*) as c FROM tactical_units")
        if cur.fetchone()["c"] == 0:
            seed_initial_data(conn)

    # Migrasi idempoten: kolom foto anotasi untuk DB lama.
    try:
        cur.execute("ALTER TABLE map_annotations ADD COLUMN photo TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Menara BTS tidak lagi di-seed sintetis — seluruh menara berasal dari impor
    # OpenCellID nyata (auto_import_opencellid saat boot). Ini menghapus menara dummy
    # terakhir dan membuat triangulasi sepenuhnya berbasis data lapangan.

    # Kolom asal data menara (idempoten): bedakan koordinat SINTETIS (demo lama) vs NYATA (OpenCellID)
    cols = {r["name"] for r in cur.execute("PRAGMA table_info(bts_towers)").fetchall()}
    if "data_source" not in cols:
        cur.execute("ALTER TABLE bts_towers ADD COLUMN data_source TEXT DEFAULT 'SEED_SYNTHETIC'")
    cur.execute("UPDATE bts_towers SET data_source = 'SEED_SYNTHETIC' WHERE data_source IS NULL")

    # Kolom sumber lokasi target (idempoten): bedakan GPS nyata vs GeoIP vs manual
    tp_cols = {r["name"] for r in cur.execute("PRAGMA table_info(target_profiles)").fetchall()}
    if "loc_source" not in tp_cols:
        cur.execute("ALTER TABLE target_profiles ADD COLUMN loc_source TEXT DEFAULT 'manual'")
    # Backfill setiap startup: rows yang masih 'manual' → coba derive loc_source
    for row in cur.execute(
        "SELECT target_id, osint_json, primary_ip, lat, lon FROM target_profiles WHERE loc_source = 'manual' OR loc_source IS NULL"
    ).fetchall():
        try:
            osint = json.loads(row[1] or "{}")
            hits = osint.get("checkin_hits", [])
            if hits:
                # Punya checkin hit → ambil dari hit terbaru
                src = hits[0].get("loc_source", "geoip:Unknown")
                cur.execute("UPDATE target_profiles SET loc_source = ? WHERE target_id = ?",
                            (src, row[0]))
            elif row[2] and row[2] not in ("", "0.0.0.0", None):
                # Punya IP nyata tapi belum ada checkin → tandai geoip
                cur.execute("UPDATE target_profiles SET loc_source = 'geoip:IP' WHERE target_id = ?",
                            (row[0],))
        except Exception:
            pass

    conn.commit()
    conn.close()


def seed_initial_data(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    # 'Terakhir terlihat' bervariasi: roster nyata punya kesegaran berbeda, bukan serentak.
    def _ago(mins):
        return (datetime.now(timezone.utc) - timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Menara BTS sengaja TIDAK di-seed di sini — semuanya nyata dari OpenCellID.

    # 2. Zona Geofence
    geofences = [
        (
            "ZONE-RING1",
            "ZONA MERAH OBJEK VITAL NASIONAL (ISTANA / GAMBIR)",
            "RESTRICTED_RED_ZONE",
            "#EF4444",
            json.dumps([
                [-6.1670, 106.8190],
                [-6.1670, 106.8350],
                [-6.1830, 106.8350],
                [-6.1830, 106.8190],
            ]),
        ),
        (
            "ZONE-PORT",
            "ZONA PENGAWASAN PELABUHAN LOGISTIK STRATEGIS",
            "WATCH_ZONE",
            "#F59E0B",
            json.dumps([
                [-6.1120, 106.8660],
                [-6.1120, 106.8890],
                [-6.1310, 106.8890],
                [-6.1310, 106.8660],
            ]),
        ),
    ]
    conn.executemany("INSERT INTO geofences VALUES (?,?,?,?,?)", geofences)

    # 3. Unit Taktis Multi-Kanal (Hijau: 4G, Kuning: SMS 2G/BTS, Biru: Radio APRS/LoRa/Satelit, Merah: SOS)
    units = [
        (
            "ALPHA-01",
            "ALPHA-01",
            "Tim Tindak Cepat Alpha-1",
            "Tactical Assault / Patrol",
            "DATA_4G",
            "GREEN",
            -6.1782,
            106.8245,
            18,
            42,
            91,
            -67,
            510,
            10,
            4102,
            88219,
            12,
            _ago(3),
            json.dumps([[-6.1850, 106.8210], [-6.1815, 106.8230], [-6.1782, 106.8245]]),
        ),
        (
            "BRAVO-02",
            "BRAVO-02",
            "Unit Intelijen Lapangan Bravo-2 (Basement/Blank Internet)",
            "Undercover Recon",
            "SMS_2G_BTS",
            "YELLOW",
            -6.2072,
            106.8218,
            5,
            0,
            64,
            -89,
            510,
            1,
            4110,
            77310,
            420,
            _ago(17),
            json.dumps([[-6.2120, 106.8190], [-6.2095, 106.8205], [-6.2072, 106.8218]]),
        ),
        (
            "CHARLIE-03",
            "YB0TFL-9",
            "Tim SAR Hutan & Gunung Charlie-3 (Off-Grid VHF APRS)",
            "Mountain SAR & Border",
            "APRS_VHF",
            "BLUE",
            -6.2450,
            106.8650,
            410,
            14,
            78,
            -94,
            0,
            0,
            0,
            0,
            25,
            _ago(134),
            json.dumps([[-6.2520, 106.8580], [-6.2485, 106.8615], [-6.2450, 106.8650]]),
        ),
        (
            "DELTA-04",
            "MESH-DLT4",
            "Unit Patroli Pelabuhan Delta-4 (LoRa Mesh + SOS)",
            "Maritime & Port Security",
            "SOS_EMERGENCY",
            "RED",
            -6.1235,
            106.8772,
            4,
            0,
            39,
            -98,
            510,
            11,
            4205,
            65102,
            35,
            _ago(1),
            json.dumps([[-6.1290, 106.8710], [-6.1260, 106.8745], [-6.1235, 106.8772]]),
        ),
        (
            "EAGLE-UAV-1",
            "UAV-EAGLE1",
            "Drone Pengintai Taktis Eagle-1 (WebRTC YOLOv8)",
            "Aerial ISR Drone",
            "DATA_4G",
            "GREEN",
            -6.1738,
            106.8295,
            145,
            68,
            82,
            -61,
            510,
            10,
            4102,
            88219,
            5,
            _ago(2),
            json.dumps([[-6.1790, 106.8340], [-6.1765, 106.8315], [-6.1738, 106.8295]]),
        ),
    ]
    conn.executemany(
        "INSERT INTO tactical_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        units,
    )

    # 4. Profil Target AI (Pilar 4: AI-Assisted Target Profiling)
    targets = [
        (
            "TGT-01",
            "KESTREL-ALPHA",
            "Viktor K. (identitas belum terverifikasi)",
            "Terduga koordinator penyelundupan (belum terbukti)",
            "B 1984 RFS",
            "MSISDN/IMEI tidak tersedia (data simulasi)",
            "c2-relay.nusantara-sync.net",
            "103.144.22.91",
            "AS138912 (ShadowNet Transit ID)",
            -6.1725,
            106.8280,
            88,
            92,
            85,
            86,
            88,
            "CRITICAL",
            json.dumps({
                "whois_registrar": "NameCheap / PrivacyGuard Offshore",
                "ssl_cert_san": ["c2-relay.nusantara-sync.net", "api-vault.darkport-id.org"],
                "open_ports": [22, 443, 8443, 8901, 9001],
                "cve_exposures": ["CVE-2024-6387 (OpenSSH RegreSSHion)", "Weak DMARC / SPF Spoofable"],
                "breach_hits": "Terdeteksi 3 kredensial terasosiasi pada kebocoran forum gelap 2026",
            }),
            json.dumps({
                "routine_summary": "Aktif bergerak pukul 23:00–03:30 WIB antara Gudang Tanjung Priok dan Area Ring-1 Gambir.",
                "anomaly_flag": "Pola pergerakan belum dinilai — menunggu data pelacakan nyata (skenario latihan).",
                "dwell_clusters": [
                    {"label": "Safe House A (Kemayoran Sektor 4)", "lat": -6.1560, "lon": 106.8480, "avg_dwell_min": 210, "visits_7d": 6},
                    {"label": "Titik Kumpul Dermaga Priok Dermaga-3", "lat": -6.1220, "lon": 106.8765, "avg_dwell_min": 55, "visits_7d": 4},
                    {"label": "Perimeter Timur Gambir (Zona Merah)", "lat": -6.1730, "lon": 106.8285, "avg_dwell_min": 38, "visits_7d": 2},
                ],
                "rendezvous_events": [
                    {
                        "with_target": "TGT-02 (VIPER-LOGISTICS)",
                        "location": "Dermaga Priok / BTS CID 65102",
                        "timestamp": "2026-10-22 01:15 WIB",
                        "distance_m": 18,
                        "duration_min": 24,
                    }
                ],
                "hourly_activity": [85, 92, 78, 60, 20, 10, 5, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 65, 70, 80, 90, 95, 90],
            }),
            json.dumps({
                "nodes": [
                    {"id": "TGT-01", "label": "TGT-01: KESTREL", "type": "TARGET", "risk": 88},
                    {"id": "DEV-3589", "label": "IMEI 3589..9102\n(+62-812-9901-4482)", "type": "DEVICE", "risk": 75},
                    {"id": "VEH-B1984", "label": "SUV Hitam\n[B 1984 RFS]", "type": "VEHICLE", "risk": 82},
                    {"id": "DOM-C2", "label": "c2-relay.nusantara-sync.net\n(103.144.22.91)", "type": "CYBER", "risk": 91},
                    {"id": "BTS-65102", "label": "BTS Priok CID:65102", "type": "LOCATION", "risk": 60},
                    {"id": "TGT-02", "label": "TGT-02: VIPER", "type": "TARGET", "risk": 76},
                    {"id": "EVD-2026-001", "label": "EVD-001: Foto Skema\nGardu & EXIF GPS", "type": "EVIDENCE", "risk": 90},
                ],
                "edges": [
                    {"from": "TGT-01", "to": "DEV-3589", "label": "USES_DEVICE"},
                    {"from": "TGT-01", "to": "VEH-B1984", "label": "DRIVES (ANPR Hit)"},
                    {"from": "TGT-01", "to": "DOM-C2", "label": "OPERATES_C2"},
                    {"from": "DEV-3589", "to": "BTS-65102", "label": "CONNECTED_BTS"},
                    {"from": "TGT-02", "to": "BTS-65102", "label": "CO_LOCATED (24m)"},
                    {"from": "TGT-01", "to": "TGT-02", "label": "RENDEZVOUS_01:15"},
                    {"from": "EVD-2026-001", "to": "TGT-01", "label": "EXTRACTED_FROM"},
                ],
            }),
            now,
        ),
        (
            "TGT-02",
            "VIPER-LOGISTICS",
            "Hendrik S. (identitas belum terverifikasi)",
            "Terduga kurir logistik (belum terbukti)",
            "B 9021 UTX",
            "+62-811-7200-3109 (IMEI: 352091882710441)",
            "api-vault.darkport-id.org",
            "103.144.22.94",
            "AS138912 (ShadowNet Transit ID)",
            -6.1228,
            106.8780,
            72,
            80,
            78,
            70,
            76,
            "HIGH",
            json.dumps({
                "whois_registrar": "Shared SSL SAN dengan TGT-01 (c2-relay.nusantara-sync.net)",
                "ssl_cert_san": ["api-vault.darkport-id.org", "cargo-manifest.id-sync.org"],
                "open_ports": [80, 443, 8080],
                "cve_exposures": ["Shared /24 Subnet (103.144.22.0/24) dengan C2 Server TGT-01"],
                "breach_hits": "Metadata nomor telepon ditemukan pada file SQLite sitaan EVD-2026-002",
            }),
            json.dumps({
                "routine_summary": "Beroperasi di sekitar Pelabuhan Tanjung Priok dan gudang Marunda pada dini hari.",
                "anomaly_flag": "Terdeteksi Rendezvous (pertemuan fisik radius 18m) dengan TGT-01 pada pukul 01:15 WIB.",
                "dwell_clusters": [
                    {"label": "Gudang Kontainer Priok Blok C", "lat": -6.1228, "lon": 106.8780, "avg_dwell_min": 180, "visits_7d": 7},
                    {"label": "Rest Area Tol Cakung", "lat": -6.1610, "lon": 106.9410, "avg_dwell_min": 40, "visits_7d": 3},
                ],
                "rendezvous_events": [
                    {
                        "with_target": "TGT-01 (KESTREL-ALPHA)",
                        "location": "Dermaga Priok / BTS CID 65102",
                        "timestamp": "2026-10-22 01:15 WIB",
                        "distance_m": 18,
                        "duration_min": 24,
                    }
                ],
                "hourly_activity": [75, 88, 70, 50, 30, 15, 10, 10, 20, 35, 45, 50, 50, 40, 35, 40, 55, 60, 65, 70, 75, 80, 85, 80],
            }),
            json.dumps({
                "nodes": [
                    {"id": "TGT-02", "label": "TGT-02: VIPER", "type": "TARGET", "risk": 76},
                    {"id": "VEH-B9021", "label": "Box Van Putih\n[B 9021 UTX]", "type": "VEHICLE", "risk": 74},
                    {"id": "DOM-VAULT", "label": "api-vault.darkport-id.org\n(103.144.22.94)", "type": "CYBER", "risk": 78},
                    {"id": "TGT-01", "label": "TGT-01: KESTREL", "type": "TARGET", "risk": 88},
                    {"id": "EVD-2026-002", "label": "EVD-002: Dump SQLite\nPesan Terhapus", "type": "EVIDENCE", "risk": 84},
                ],
                "edges": [
                    {"from": "TGT-02", "to": "VEH-B9021", "label": "DRIVES"},
                    {"from": "TGT-02", "to": "DOM-VAULT", "label": "ADMINISTERS"},
                    {"from": "DOM-VAULT", "to": "TGT-01", "label": "SHARED_SSL_CERT"},
                    {"from": "EVD-2026-002", "to": "TGT-02", "label": "RECOVERED_CHAT"},
                ],
            }),
            now,
        ),
        (
            "TGT-03",
            "PHANTOM-SIGNAL",
            "Tidak dikenal",
            "Terduga spoofing SMS (belum terbukti)",
            "D 1109 ZXA",
            "Rogue Modem Pool (IMSI Catcher / Fake SMPP)",
            "rogue-smpp.proxynode.org",
            "185.220.101.45",
            "AS60729 (Tor Exit / Bulletproof Hosting)",
            -6.1910,
            106.8380,
            94,
            68,
            60,
            72,
            74,
            "HIGH",
            json.dumps({
                "whois_registrar": "RIPE Anonymous Allocation",
                "ssl_cert_san": ["rogue-smpp.proxynode.org"],
                "open_ports": [2775, 8901, 9050],
                "cve_exposures": ["Percobaan injeksi SMS Biner Port 8901 tanpa tanda tangan HMAC-SHA256 sah"],
                "breach_hits": "Alamat IP terdaftar pada daftar blokir Threat Intelligence BSSN",
            }),
            json.dumps({
                "routine_summary": "Berpindah-pindah di sekitar Cikini – Menteng dengan durasi berhenti singkat (<15 menit).",
                "anomaly_flag": "Mengirimkan 4 paket SMS Biner palsu ke nomor perangkat BRAVO-02 (Ditolak 100% oleh HMAC Engine).",
                "dwell_clusters": [
                    {"label": "Parkir Timur Cikini", "lat": -6.1910, "lon": 106.8380, "avg_dwell_min": 14, "visits_7d": 5}
                ],
                "rendezvous_events": [],
                "hourly_activity": [40, 30, 20, 10, 5, 5, 10, 20, 30, 45, 60, 75, 80, 85, 90, 85, 80, 70, 65, 60, 55, 50, 45, 40],
            }),
            json.dumps({
                "nodes": [
                    {"id": "TGT-03", "label": "TGT-03: PHANTOM", "type": "TARGET", "risk": 74},
                    {"id": "IP-185", "label": "185.220.101.45\n(Rogue SMPP)", "type": "CYBER", "risk": 94},
                    {"id": "VEH-D1109", "label": "Minibus Abu-abu\n[D 1109 ZXA]", "type": "VEHICLE", "risk": 65},
                ],
                "edges": [
                    {"from": "TGT-03", "to": "IP-185", "label": "SPOOFS_SMS_8901"},
                    {"from": "TGT-03", "to": "VEH-D1109", "label": "MOBILE_RIG"},
                ],
            }),
            now,
        ),
    ]
    # Jalur B: target TIDAK lagi diisi data karangan. Tabel target_profiles dibiarkan
    # kosong di sini; diisi dari recon NYATA oleh seed_targets_from_recon() yang
    # berjalan di thread latar saat server start (lihat SAFE_RECON_SEEDS). Saat
    # air-gap atau recon gagal, tabel tetap kosong dan UI menampilkan empty-state jujur.
    _ = targets  # daftar skenario lama dipertahankan sebagai referensi, tidak disisipkan

    # 5. Alert SIEM Siber-Fisik (Pilar 5: Converged Cyber-Physical SIEM)
    siem_alerts = [
        (
            "SIM-2026-001",
            now,
            "CRITICAL",
            "[CONTOH] SIGMA-C2-009: Impossible Travel (login ganda mustahil)",
            "Defense Evasion / Valid Accounts",
            "T1078",
            "Valid Accounts (Impossible Travel Detected)",
            "Akun operator (contoh)",
            "198.51.100.23 (lokasi B — contoh)",
            -7.2575,
            112.7521,
            -6.2072,
            106.8218,
            667.4,
            8008.8,
            "Contoh deteksi: satu akun login dari dua lokasi berjarak 667 km dalam 5 menit (≈8.000 km/jam), jauh di atas batas wajar — indikasi kredensial dipakai dari tempat berbeda.",
            "OPEN",
            "NONE",
        ),
        (
            "SIM-2026-002",
            now,
            "CRITICAL",
            "[CONTOH] SIGMA-TFAEL-8901: SMS biner tak terautentikasi ditolak",
            "Impair Defenses / Command & Control",
            "T1562",
            "Spoofed Binary SMS Port 8901 Rejected by HMAC-SHA256",
            "Unit lapangan (contoh)",
            "203.0.113.45 (gateway SMPP tak dikenal — contoh)",
            -6.1910,
            106.8380,
            -6.2072,
            106.8218,
            2.4,
            0.0,
            "Perangkat BRAVO-02 menerima paket SMS Biner Port 8901 dengan tag HMAC-SHA256 tidak sah (0xDEADBEEF...). Paket ditolak 100% oleh Android TEE Keystore dan memicu alarm intrusi.",
            "MITIGATED",
            "BLOCK_IP_FIREWALL",
        ),
        (
            "SIM-2026-003",
            now,
            "HIGH",
            "[CONTOH] SIGMA-UEBA-042: akses massal di luar jam dinas",
            "Collection / Exfiltration",
            "T1530",
            "Abnormal Bulk Data Access at 02:14 WIB (UEBA Score: 91)",
            "Akun tamu (contoh)",
            "10.88.14.209 (VLAN internal — contoh)",
            -6.1754,
            106.8272,
            -6.1754,
            106.8272,
            0.0,
            0.0,
            "Contoh deteksi: akun tamu mengunduh sejumlah dokumen di luar jam dinas (02:14), memicu skor anomali UEBA tinggi.",
            "MITIGATED",
            "ISOLATE_AND_FREEZE_FORENSICS",
        ),
        (
            "SIM-2026-004",
            now,
            "HIGH",
            "[CONTOH] SIGMA-NET-118: brute-force SSH & beacon keluar",
            "Credential Access",
            "T1110",
            "Brute Force SSH followed by Outbound C2 Syn",
            "Gateway jaringan (contoh)",
            "198.51.100.23 (sumber — contoh)",
            -6.1214,
            106.8753,
            -6.1214,
            106.8753,
            0.0,
            0.0,
            "Contoh deteksi: 340 percobaan login SSH gagal dari satu sumber, diikuti koneksi keluar ke alamat tak dikenal.",
            "OPEN",
            "NONE",
        ),
    ]
    conn.executemany(
        "INSERT INTO siem_alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        siem_alerts,
    )

    # 6. Brankas Barang Bukti Forensik Digital Berantai Hash (Pilar 6: DFIR)
    genesis_prev = "0" * 64
    examiner_full = "EXAMINER-DFIR-01 (contoh)"
    ev1_bytes = b"JFIF_EXIF_SAMPLE_EDITED_IMAGE_FOR_FORENSIC_DEMO"
    ev1_sha256 = hashlib.sha256(ev1_bytes).hexdigest()
    ev1_sha512 = hashlib.sha512(ev1_bytes).hexdigest()
    ev1_chain = hashlib.sha256(
        f"{genesis_prev}|{ev1_sha512}|{now}|{examiner_full}".encode()
    ).hexdigest()

    ev2_bytes = b"SQLITE3_WAL_SAMPLE_RECOVERED_ROWS_FOR_FORENSIC_DEMO"
    ev2_sha256 = hashlib.sha256(ev2_bytes).hexdigest()
    ev2_sha512 = hashlib.sha512(ev2_bytes).hexdigest()
    ev2_chain = hashlib.sha256(
        f"{ev1_chain}|{ev2_sha512}|{now}|{examiner_full}".encode()
    ).hexdigest()

    evidences = [
        (
            "EVD-2026-001",
            "CASE-CONTOH-01",
            "foto_contoh_teredit.jpg",
            len(ev1_bytes) * 1420,
            "image/jpeg (JPEG EXIF 2.31)",
            ev1_sha256,
            ev1_sha512,
            genesis_prev,
            ev1_chain,
            json.dumps({
                "CameraModel": "Samsung SM-S918B (Galaxy S23 Ultra)",
                "Software": "Adobe Photoshop 25.4 (Windows) [INDIKASI SUNTINGAN]",
                "DateTimeOriginal": "2026:10:21 23:42:19",
                "GPSLatitude": -6.1731,
                "GPSLongitude": 106.8284,
                "GPSAltitude": "19.4 m",
                "AuthorComment": "Berkas contoh untuk peragaan forensik",
            }),
            0.84,
            json.dumps([
                {"rule": "YARA_Contoh_Exif_Marker", "severity": "HIGH", "desc": "Penanda contoh pada blok komentar EXIF APP1 (data peragaan, bukan indikator nyata)"}
            ]),
            json.dumps({
                "gps": [-6.1731, 106.8284],
            }),
            json.dumps([]),
            "OCR (contoh): [BERKAS SAMPEL UNTUK MEMPERAGAKAN EKSTRAKSI TEKS & ANALISIS EXIF/ELA]",
            "",
            examiner_full,
            now,
        ),
        (
            "EVD-2026-002",
            "CASE-CONTOH-02",
            "contoh_dump.db-wal",
            len(ev2_bytes) * 3190,
            "application/vnd.sqlite3 (SQLite Write-Ahead Log v3)",
            ev2_sha256,
            ev2_sha512,
            ev1_chain,
            ev2_chain,
            json.dumps({
                "SQLiteVersion": "3.45.1",
                "WALFramesTotal": 418,
                "UnallocatedFreelistPages": 19,
                "DeviceSource": "Berkas contoh (peragaan pemulihan WAL)",
            }),
            0.12,
            json.dumps([
                {"rule": "YARA_Contoh_Artifact", "severity": "MEDIUM", "desc": "Artefak contoh pada tabel terhapus (data peragaan, bukan temuan nyata)"}
            ]),
            json.dumps({}),
            json.dumps([
                {"rowid": 8841, "status": "DELETED_RECOVERED_FROM_WAL", "timestamp": "2026-10-22 00:48:12", "sender": "(contoh)", "message": "Baris contoh yang dipulihkan dari Write-Ahead Log untuk memperagakan carving pesan terhapus."},
                {"rowid": 8842, "status": "DELETED_RECOVERED_FROM_WAL", "timestamp": "2026-10-22 00:50:03", "sender": "(contoh)", "message": "Baris contoh kedua — isi dummy untuk peragaan, bukan data nyata."},
                {"rowid": 8845, "status": "DELETED_RECOVERED_FROM_FREELIST", "timestamp": "2026-10-22 01:29:44", "sender": "(contoh)", "message": "Baris contoh dari freelist untuk memperagakan pemulihan halaman terhapus."},
            ]),
            "Transkripsi Voice Note (Faster-Whisper Offline, contoh): 'Ini rekaman sampel untuk memperagakan transkripsi suara ke teks secara lokal.'",
            "",
            examiner_full,
            now,
        ),
    ]
    for ev in evidences:
        conn.execute(
            """
            INSERT INTO forensic_evidence_vault (
                evidence_id, case_id, file_name, file_size, magic_mime,
                sha256_hash, sha512_hash, prev_chain_hash, curr_chain_hash,
                exif_json, ela_anomaly_score, yara_matches_json,
                extracted_entities_json, carved_records_json, transcript_text,
                linked_target_id, examiner_id, acquired_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            ev,
        )


