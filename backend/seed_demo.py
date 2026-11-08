#!/usr/bin/env python3
"""
Script seed data demo untuk Kartika Cyber Hackathon 2026.
Mengisi DB dengan data taktis fiktif yang realistis untuk demo C4ISR.

Jalankan: python3 backend/seed_demo.py
"""
import sqlite3, json, secrets, hashlib
from datetime import datetime, timezone, timedelta

DB_PATH = "backend/tfael_omni.db"

def now(offset_minutes=0):
    t = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

# ──────────────────────────────────────────────────────────────
# 1. HAPUS DATA LAMA YANG TIDAK TEPAT UNTUK DEMO
# ──────────────────────────────────────────────────────────────
def clean_old_demo_data():
    c = conn()
    # Hapus duplikat SIEM SOS (bukan target, target dijaga)
    c.execute("DELETE FROM siem_alerts")
    # Hapus geofences lama
    c.execute("DELETE FROM geofences")
    # Hapus forensic evidence lama
    c.execute("DELETE FROM forensic_evidence_vault")
    # Hapus anotasi lama
    c.execute("DELETE FROM map_annotations")
    c.commit(); c.close()
    print("[SEED] Data lama dihapus (target dipertahankan)")

# ──────────────────────────────────────────────────────────────
# 2. TARGET PROFIL FIKTIF (Intel Cyber)
# ──────────────────────────────────────────────────────────────
def seed_targets():
    c = conn()

    targets = [
        # TGT-04 FOXTROT tetap ada (dari DB)
        {
            "target_id": "TGT-05",
            "code_name": "GHOST-ALPHA",
            "real_name": "Entitas tidak dikenal (APT asal {redacted})",
            "category": "Aktor ancaman siber — persistensi jangka panjang",
            "plate_number": "N/A",
            "phone_id": "IP Dinamis / VPN Berputar",
            "primary_domain": "c2-phantom[.]net",
            "primary_ip": "185.220.101.47",
            "asn": "AS62240 Clouvider Limited (Exit Node Tor)",
            "lat": -6.1754,
            "lon": 106.8272,
            "cyber_score": 97,
            "spatial_score": 45,
            "visual_score": 10,
            "forensic_score": 82,
            "risk_score": 95,
            "risk_level": "CRITICAL",
            "osint_json": json.dumps({
                "open_ports": [22, 80, 443, 8080, 4444],
                "cve_exposures": [
                    "CVE-2024-3094 — XZ Utils Backdoor (RCE)",
                    "CVE-2024-21762 — Fortinet SSL-VPN RCE",
                    "CVE-2023-44487 — HTTP/2 Rapid Reset (DDoS)",
                ],
                "malware_indicators": ["Cobalt Strike beacon hash: 4a3b2c1d...", "C2 beaconing interval: 60s"],
                "breach_check": {"checked": True, "hits": 3, "source": "Have I Been Pwned"},
                "identity_osint": {"accounts_found": [], "scanned": True},
                "threat_intel": {
                    "actor": "APT-X (belum teridentifikasi)",
                    "ttps": ["Spear phishing", "Lateral movement via RDP", "Living off the land"],
                    "campaign": "Operasi Bayangan Digital — aktif sejak Q3 2024",
                }
            }),
            "pattern_of_life_json": json.dumps({
                "data_source": "SIGINT_CYBER_TRACING",
                "routine_summary": "Aktif 02:00–06:00 WIB (offset UTC+7), kemungkinan zona waktu Asia Timur.",
                "anomaly_flag": "Koneksi dari 7 negara dalam 48 jam — impossible travel detected",
                "hourly_activity": [30, 20, 60, 90, 80, 70, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 20, 25, 30, 35, 30],
            }),
            "graph_json": json.dumps({"nodes": [], "edges": []}),
            "loc_source": "SIGINT Triangulasi",
        },
        {
            "target_id": "TGT-06",
            "code_name": "HYDRA-BRAVO",
            "real_name": "Sindikat penipuan siber — identitas ganda terverifikasi",
            "category": "Financial cybercrime — money mule network",
            "plate_number": "B 3311 XYZ",
            "phone_id": "+62812-XXXX-XXXX (SIM prabayar tak terregistrasi)",
            "primary_domain": "investasi-cepat[.]id",
            "primary_ip": "103.142.86.1",
            "asn": "AS55685 PT Cepat Solusi Internet (Jakarta)",
            "lat": -6.9175,
            "lon": 107.6191,
            "cyber_score": 88,
            "spatial_score": 72,
            "visual_score": 65,
            "forensic_score": 76,
            "risk_score": 82,
            "risk_level": "HIGH",
            "osint_json": json.dumps({
                "open_ports": [80, 443],
                "cve_exposures": ["Phishing site terdeteksi", "Domain dibuat 3 hari lalu", "Sertifikat SSL self-signed"],
                "breach_check": {"checked": True, "hits": 0, "source": "XposedOrNot"},
                "financial_trail": {
                    "rekening_terkait": 7,
                    "transaksi_terdeteksi": "Rp 2,3 miliar (estimasi FININT)",
                    "bank": "3 bank berbeda, dirotasi setiap 2 minggu",
                }
            }),
            "pattern_of_life_json": json.dumps({
                "data_source": "HUMINT_OSINT_COMBINED",
                "routine_summary": "Lokasi primer: Bandung (perumahan). Aktif 08:00–22:00 WIB.",
                "anomaly_flag": "Check-in terakhir 2km dari lokasi biasa — kemungkinan flyaway",
                "hourly_activity": [0,0,0,0,0,0,0,5,20,30,40,50,45,40,35,30,40,50,60,70,65,55,30,10],
            }),
            "graph_json": json.dumps({"nodes": [], "edges": []}),
            "loc_source": "Cell-ID Triangulasi ±250m",
        },
        {
            "target_id": "TGT-07",
            "code_name": "OMEGA-TIGA",
            "real_name": "Penyebar propaganda terkoordinasi — akun bot terverifikasi",
            "category": "Operasi Informasi / Influence Operation (IO)",
            "plate_number": "D 9988 ZZZ",
            "phone_id": "+62877-XXXX-XXXX",
            "primary_domain": "narasi-bangsa[.]net",
            "primary_ip": "172.67.143.205",
            "asn": "AS13335 Cloudflare, Inc.",
            "lat": -7.2575,
            "lon": 112.7521,
            "cyber_score": 74,
            "spatial_score": 60,
            "visual_score": 88,
            "forensic_score": 55,
            "risk_score": 74,
            "risk_level": "HIGH",
            "osint_json": json.dumps({
                "open_ports": [80, 443],
                "social_media_network": {
                    "jumlah_akun": 43,
                    "platform": ["Twitter/X", "Telegram", "TikTok", "Instagram"],
                    "reach_estimasi": "1,2 juta akun terpapar per minggu",
                    "narasi_dominan": ["anti-pemerintah", "separatisme", "hoax bencana"],
                }
            }),
            "pattern_of_life_json": json.dumps({
                "data_source": "CYBINT_SOCMED_CRAWLER",
                "routine_summary": "Posting masif pukul 06:00–08:00 dan 17:00–20:00 WIB.",
                "anomaly_flag": "Burst aktivitas 500+ post dalam 2 jam — kemungkinan kampanye terkoordinasi",
                "hourly_activity": [0,0,0,0,0,0,80,90,70,20,10,5,5,10,5,5,10,80,95,90,40,20,10,0],
            }),
            "graph_json": json.dumps({"nodes": [], "edges": []}),
            "loc_source": "GeoIP via CDN log",
        },
    ]

    for t in targets:
        existing = c.execute("SELECT 1 FROM target_profiles WHERE target_id=?", (t["target_id"],)).fetchone()
        if existing:
            print(f"  [SKIP] {t['target_id']} sudah ada")
            continue
        c.execute("""
            INSERT INTO target_profiles
              (target_id, code_name, real_name, category, plate_number, phone_id,
               primary_domain, primary_ip, asn, lat, lon,
               cyber_score, spatial_score, visual_score, forensic_score, risk_score, risk_level,
               osint_json, pattern_of_life_json, graph_json, updated_at, loc_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            t["target_id"], t["code_name"], t["real_name"], t["category"],
            t["plate_number"], t["phone_id"], t["primary_domain"], t["primary_ip"], t["asn"],
            t["lat"], t["lon"],
            t["cyber_score"], t["spatial_score"], t["visual_score"], t["forensic_score"],
            t["risk_score"], t["risk_level"],
            t["osint_json"], t["pattern_of_life_json"], t["graph_json"],
            now(), t["loc_source"]
        ))
        print(f"  [OK] Target {t['target_id']} {t['code_name']} ditambahkan")

    c.commit(); c.close()


# ──────────────────────────────────────────────────────────────
# 3. UNIT TAKTIS TAMBAHAN
# ──────────────────────────────────────────────────────────────
def seed_units():
    c = conn()

    units = [
        {
            "unit_id": "BRAVO-02",
            "callsign": "BRAVO-02",
            "name": "Tim Penindak Khusus",
            "role": "REAL_HARDWARE_GPS",
            "channel": "NORMAL",
            "status_color": "#00ff88",
            "lat": -6.2383,
            "lon": 106.9876,
            "alt_m": 12,
            "speed_kmh": 0,
            "battery_pct": 76,
            "signal_dbm": -78,
            "mcc": "510", "mnc": "01", "lac": "5001", "cid": "12345",
            "bts_radius_m": 300,
            "last_seen": now(-5),
            "trail_json": json.dumps([
                {"lat": -6.2350, "lon": 106.9810, "ts": now(-30)},
                {"lat": -6.2360, "lon": 106.9830, "ts": now(-20)},
                {"lat": -6.2370, "lon": 106.9860, "ts": now(-10)},
                {"lat": -6.2383, "lon": 106.9876, "ts": now(-5)},
            ]),
        },
        {
            "unit_id": "CHARLIE-03",
            "callsign": "CHARLIE-03",
            "name": "Pengintai Elektronik",
            "role": "REAL_HARDWARE_GPS",
            "channel": "NORMAL",
            "status_color": "#00ff88",
            "lat": -6.1628,
            "lon": 106.8153,
            "alt_m": 8,
            "speed_kmh": 0,
            "battery_pct": 91,
            "signal_dbm": -65,
            "mcc": "510", "mnc": "08", "lac": "6002", "cid": "67890",
            "bts_radius_m": 200,
            "last_seen": now(-2),
            "trail_json": json.dumps([
                {"lat": -6.1610, "lon": 106.8120, "ts": now(-15)},
                {"lat": -6.1615, "lon": 106.8135, "ts": now(-10)},
                {"lat": -6.1620, "lon": 106.8145, "ts": now(-5)},
                {"lat": -6.1628, "lon": 106.8153, "ts": now(-2)},
            ]),
        },
        {
            "unit_id": "DELTA-04",
            "callsign": "DELTA-04",
            "name": "Pos Komando Lapangan",
            "role": "REAL_HARDWARE_GPS",
            "channel": "SOS_EMERGENCY",
            "status_color": "#ff3333",
            "lat": -6.3012,
            "lon": 107.1234,
            "alt_m": 45,
            "speed_kmh": 120,
            "battery_pct": 23,
            "signal_dbm": -92,
            "mcc": "510", "mnc": "11", "lac": "7003", "cid": "11111",
            "bts_radius_m": 600,
            "last_seen": now(-1),
            "trail_json": json.dumps([
                {"lat": -6.2800, "lon": 107.0900, "ts": now(-20)},
                {"lat": -6.2900, "lon": 107.1050, "ts": now(-10)},
                {"lat": -6.3012, "lon": 107.1234, "ts": now(-1)},
            ]),
        },
    ]

    for u in units:
        existing = c.execute("SELECT 1 FROM tactical_units WHERE unit_id=?", (u["unit_id"],)).fetchone()
        if existing:
            print(f"  [SKIP] Unit {u['unit_id']} sudah ada")
            continue
        c.execute("""
            INSERT INTO tactical_units
              (unit_id, callsign, name, role, channel, status_color,
               lat, lon, alt_m, speed_kmh, battery_pct, signal_dbm,
               mcc, mnc, lac, cid, bts_radius_m, last_seen, trail_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            u["unit_id"], u["callsign"], u["name"], u["role"], u["channel"], u["status_color"],
            u["lat"], u["lon"], u["alt_m"], u["speed_kmh"], u["battery_pct"], u["signal_dbm"],
            u["mcc"], u["mnc"], u["lac"], u["cid"], u["bts_radius_m"], u["last_seen"], u["trail_json"]
        ))
        print(f"  [OK] Unit {u['unit_id']} {u['callsign']} ditambahkan")

    c.commit(); c.close()


# ──────────────────────────────────────────────────────────────
# 4. SIEM ALERTS BERAGAM
# ──────────────────────────────────────────────────────────────
def seed_siem_alerts():
    c = conn()
    c.execute("DELETE FROM siem_alerts")

    alerts = [
        {
            "event_time": now(-180),
            "severity": "CRITICAL",
            "sigma_rule": "Sigma.Win.Threat.ImpossibleTravel",
            "mitre_tactic": "Initial Access / Credential Theft",
            "mitre_id": "T1078",
            "mitre_name": "Valid Accounts — Impossible Travel",
            "user_or_unit": "admin.sistem",
            "src_ip": "185.220.101.47",
            "cyber_lat": 55.7558,
            "cyber_lon": 37.6173,
            "phys_lat": -6.2,
            "phys_lon": 106.8,
            "distance_km": 9187,
            "velocity_kmh": 3061,
            "description": "Impossible travel: login dari Moskow (Rusia) dan Jakarta dalam 3 jam — kecepatan fisik tidak mungkin 3.061 km/jam",
            "status": "OPEN",
            "soar_action_taken": "Sesi dibekukan otomatis. Akun dikunci sementara.",
        },
        {
            "event_time": now(-120),
            "severity": "HIGH",
            "sigma_rule": "Sigma.Cyber.LateralMovement.RDP",
            "mitre_tactic": "Lateral Movement",
            "mitre_id": "T1021.001",
            "mitre_name": "Remote Services — RDP Brute Force",
            "user_or_unit": "GHOST-ALPHA",
            "src_ip": "103.142.86.1",
            "cyber_lat": -6.9175,
            "cyber_lon": 107.6191,
            "phys_lat": -6.9175,
            "phys_lon": 107.6191,
            "distance_km": 0,
            "velocity_kmh": 0,
            "description": "Brute force RDP terdeteksi: 1.247 percobaan gagal dalam 10 menit dari IP 103.142.86.1 menuju server C2 internal",
            "status": "INVESTIGATING",
            "soar_action_taken": "IP diblokir firewall otomatis. Alert ke admin.",
        },
        {
            "event_time": now(-90),
            "severity": "CRITICAL",
            "sigma_rule": "Sigma.Win.Malware.CobaltStrike",
            "mitre_tactic": "Command and Control",
            "mitre_id": "T1071.001",
            "mitre_name": "Application Layer Protocol — C2 Beacon",
            "user_or_unit": "GHOST-ALPHA",
            "src_ip": "185.220.101.47",
            "cyber_lat": 51.5074,
            "cyber_lon": -0.1278,
            "phys_lat": -6.1754,
            "phys_lon": 106.8272,
            "distance_km": 11737,
            "velocity_kmh": 0,
            "description": "Cobalt Strike beacon terdeteksi: komunikasi C2 ke 185.220.101.47:443 interval 60 detik — hash payload cocok dengan GHOST-ALPHA TTPs",
            "status": "OPEN",
            "soar_action_taken": "Proses di-quarantine. Memory dump diinisiasi.",
        },
        {
            "event_time": now(-60),
            "severity": "HIGH",
            "sigma_rule": "Sigma.Phys.SOS.FieldUnit",
            "mitre_tactic": "Physical Tactical Emergency / SOS Beacon",
            "mitre_id": "T1499",
            "mitre_name": "SOS Emergency — Field Unit",
            "user_or_unit": "DELTA-04",
            "src_ip": "10.30.44.132",
            "cyber_lat": -6.3012,
            "cyber_lon": 107.1234,
            "phys_lat": -6.3012,
            "phys_lon": 107.1234,
            "distance_km": 0,
            "velocity_kmh": 120,
            "description": "DARURAT LAPANGAN: Unit DELTA-04 (Pos Komando Lapangan) mengaktifkan SOS — baterai kritis 23%, kontak terputus",
            "status": "OPEN",
            "soar_action_taken": "Notifikasi KOMANDAN. Tim SAR disiagakan.",
        },
        {
            "event_time": now(-45),
            "severity": "MEDIUM",
            "sigma_rule": "Sigma.IO.SocMed.CoordinatedInauthentic",
            "mitre_tactic": "Influence Operations / Information Warfare",
            "mitre_id": "T1585",
            "mitre_name": "Establish Accounts — Coordinated Inauthentic Behavior",
            "user_or_unit": "OMEGA-TIGA",
            "src_ip": "172.67.143.205",
            "cyber_lat": -7.2575,
            "cyber_lon": 112.7521,
            "phys_lat": -7.2575,
            "phys_lon": 112.7521,
            "distance_km": 0,
            "velocity_kmh": 0,
            "description": "Operasi informasi terdeteksi: 43 akun bot menyebarkan narasi negatif — burst 500+ post dalam 2 jam. Target: platform X dan Telegram.",
            "status": "INVESTIGATING",
            "soar_action_taken": "Laporan dikirim ke Satgas BSSN. URL di-flag untuk takedown.",
        },
        {
            "event_time": now(-20),
            "severity": "CRITICAL",
            "sigma_rule": "Sigma.Cyber.Exfil.DNSTunnel",
            "mitre_tactic": "Exfiltration",
            "mitre_id": "T1048.001",
            "mitre_name": "Exfiltration Over Alternative Protocol — DNS Tunneling",
            "user_or_unit": "GHOST-ALPHA",
            "src_ip": "10.30.44.50",
            "cyber_lat": -6.1754,
            "cyber_lon": 106.8272,
            "phys_lat": -6.1754,
            "phys_lon": 106.8272,
            "distance_km": 0,
            "velocity_kmh": 0,
            "description": "DNS tunneling terdeteksi: 287 query anomali ke c2-phantom.net dalam 5 menit — diduga eksfiltrasi data via DNS TXT records",
            "status": "OPEN",
            "soar_action_taken": "DNS resolver diblokir. Capture PCAP aktif.",
        },
    ]

    for a in alerts:
        c.execute("""
            INSERT INTO siem_alerts
              (event_time, severity, sigma_rule, mitre_tactic, mitre_id, mitre_name,
               user_or_unit, src_ip, cyber_lat, cyber_lon, phys_lat, phys_lon,
               distance_km, velocity_kmh, description, status, soar_action_taken)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            a["event_time"], a["severity"], a["sigma_rule"], a["mitre_tactic"],
            a["mitre_id"], a["mitre_name"], a["user_or_unit"], a["src_ip"],
            a["cyber_lat"], a["cyber_lon"], a["phys_lat"], a["phys_lon"],
            a["distance_km"], a["velocity_kmh"], a["description"], a["status"],
            a["soar_action_taken"]
        ))

    c.commit(); c.close()
    print(f"  [OK] {len(alerts)} SIEM alerts di-seed")


# ──────────────────────────────────────────────────────────────
# 5. GEOFENCES TAKTIS
# ──────────────────────────────────────────────────────────────
def seed_geofences():
    c = conn()
    cols = [r["name"] for r in c.execute("PRAGMA table_info(geofences)").fetchall()]
    print(f"  Geofences columns: {cols}")

    geofences = [
        {
            "name": "ZONA MERAH — Area Operasi Aktif",
            "color": "#ff3333",
            "polygon": json.dumps([
                [-6.2100, 106.7900],
                [-6.2100, 106.8400],
                [-6.2600, 106.8400],
                [-6.2600, 106.7900],
                [-6.2100, 106.7900],
            ]),
        },
        {
            "name": "ZONA KUNING — Area Pengawasan",
            "color": "#ffaa00",
            "polygon": json.dumps([
                [-6.1500, 106.7500],
                [-6.1500, 106.9000],
                [-6.3000, 106.9000],
                [-6.3000, 106.7500],
                [-6.1500, 106.7500],
            ]),
        },
        {
            "name": "ZONA HIJAU — Area Aman",
            "color": "#00ff88",
            "polygon": json.dumps([
                [-6.0800, 106.7000],
                [-6.0800, 107.0000],
                [-6.1200, 107.0000],
                [-6.1200, 106.7000],
                [-6.0800, 106.7000],
            ]),
        },
    ]

    c.execute("DELETE FROM geofences")
    for g in geofences:
        if "name" in cols and "color" in cols and "polygon" in cols:
            c.execute("INSERT INTO geofences (name, color, polygon) VALUES (?,?,?)",
                      (g["name"], g["color"], g["polygon"]))
        else:
            print(f"  [WARN] Skipping geofence — kolom tidak cocok: {cols}")
            break

    c.commit(); c.close()
    print(f"  [OK] {len(geofences)} geofences di-seed")


# ──────────────────────────────────────────────────────────────
# 6. FORENSIC EVIDENCE (DFIR)
# ──────────────────────────────────────────────────────────────
def seed_forensic():
    c = conn()
    cols = [r["name"] for r in c.execute("PRAGMA table_info(forensic_evidence_vault)").fetchall()]
    print(f"  Forensic vault columns: {cols}")

    if "file_name" not in cols:
        print("  [WARN] forensic_evidence_vault tidak punya kolom yang diharapkan, skip")
        c.close()
        return

    samples = [
        {
            "file_name": "c2_beacon_payload.bin",
            "file_hash_sha256": "4a3b2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2",
            "file_size_bytes": 45312,
            "mime_type": "application/octet-stream",
            "analysis_json": json.dumps({
                "verdict": "MALWARE",
                "family": "CobaltStrike Beacon",
                "entropy": 7.82,
                "strings_of_interest": ["ReflectiveDll", "wininet.dll", "HttpSendRequest"],
                "yara_matches": ["YARA.Win.CobaltStrike.Beacon.v4", "YARA.Win.APT.GhostAlpha"],
            }),
        },
        {
            "file_name": "pcap_dns_tunnel_2026-10-28.pcap",
            "file_hash_sha256": "9f8e7d6c5b4a3928170605040302010090807060504030201009f8e7d6c5b4a39",
            "file_size_bytes": 2847392,
            "mime_type": "application/vnd.tcpdump.pcap",
            "analysis_json": json.dumps({
                "verdict": "SUSPICIOUS",
                "anomaly": "DNS tunneling",
                "total_queries": 287,
                "unique_domains": 3,
                "data_volume_bytes": 184320,
                "suspects": ["c2-phantom.net", "beacon.xn--q9jyb4c.io"],
            }),
        },
        {
            "file_name": "mem_dump_server_ops.raw",
            "file_hash_sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2",
            "file_size_bytes": 4294967296,
            "mime_type": "application/octet-stream",
            "analysis_json": json.dumps({
                "verdict": "CRITICAL",
                "findings": [
                    "Proses inject ke lsass.exe terdeteksi",
                    "Token privilege SYSTEM ditemukan di heap",
                    "Decrypted C2 URL: https://c2-phantom.net/gate.php",
                ],
                "credentials_extracted": 3,
            }),
        },
    ]

    c.execute("DELETE FROM forensic_evidence_vault")
    ts = now()
    for s in samples:
        # Try to insert with available columns
        try:
            if "file_name" in cols and "file_hash_sha256" in cols:
                insert_cols = [col for col in cols if col in s or col in ("created_at", "updated_at")]
                c.execute("""
                    INSERT INTO forensic_evidence_vault
                      (file_name, file_hash_sha256, file_size_bytes, mime_type, analysis_json)
                    VALUES (?,?,?,?,?)
                """, (s["file_name"], s["file_hash_sha256"], s["file_size_bytes"], s["mime_type"], s["analysis_json"]))
                print(f"  [OK] Forensic: {s['file_name']}")
        except Exception as e:
            print(f"  [ERR] {s['file_name']}: {e}")

    c.commit(); c.close()


# ──────────────────────────────────────────────────────────────
# 7. MAP ANNOTATIONS
# ──────────────────────────────────────────────────────────────
def seed_annotations():
    c = conn()
    cols = [r["name"] for r in c.execute("PRAGMA table_info(map_annotations)").fetchall()]
    print(f"  Map annotations columns: {cols}")

    c.execute("DELETE FROM map_annotations")
    annotations = [
        {"type": "marker", "lat": -6.1754, "lon": 106.8272, "label": "📍 Pos Komando Pusat", "color": "#00e5ff", "created_at": now(), "actor": "komandan"},
        {"type": "marker", "lat": -6.2100, "lon": 106.8000, "label": "⚠️ Titik Pantau GHOST-ALPHA", "color": "#ff3333", "created_at": now(-30), "actor": "analis.intel"},
        {"type": "marker", "lat": -6.9175, "lon": 107.6191, "label": "🎯 Lokasi HYDRA-BRAVO terakhir", "color": "#ffaa00", "created_at": now(-60), "actor": "analis.intel"},
        {"type": "marker", "lat": -6.3012, "lon": 107.1234, "label": "🚨 DELTA-04 SOS — bantuan segera!", "color": "#ff0000", "created_at": now(-5), "actor": "komandan"},
    ]

    for a in annotations:
        try:
            c.execute("""
                INSERT INTO map_annotations (type, lat, lon, label, color, created_at, actor)
                VALUES (?,?,?,?,?,?,?)
            """, (a["type"], a["lat"], a["lon"], a["label"], a["color"], a["created_at"], a["actor"]))
            print(f"  [OK] Anotasi: {a['label']}")
        except Exception as e:
            # Try without color column
            try:
                c.execute("INSERT INTO map_annotations (type, lat, lon, label, created_at, actor) VALUES (?,?,?,?,?,?)",
                          (a["type"], a["lat"], a["lon"], a["label"], a["created_at"], a["actor"]))
                print(f"  [OK] Anotasi (no color): {a['label']}")
            except Exception as e2:
                print(f"  [ERR] Anotasi: {e2}")

    c.commit(); c.close()


if __name__ == "__main__":
    print("\n=== SEED DEMO DATA TFAEL-OMNI v2.0 ===\n")
    print("[1] Hapus data lama yang tidak tepat untuk demo...")
    clean_old_demo_data()
    print("\n[2] Tambah target profil fiktif taktis...")
    seed_targets()
    print("\n[3] Tambah unit taktis lapangan...")
    seed_units()
    print("\n[4] Seed SIEM alerts beragam...")
    seed_siem_alerts()
    print("\n[5] Seed geofences taktis...")
    seed_geofences()
    print("\n[6] Seed forensic evidence (DFIR)...")
    seed_forensic()
    print("\n[7] Seed map annotations...")
    seed_annotations()
    print("\n=== SELESAI ===")
    print("Data demo siap. Restart server untuk melihat perubahan.")
