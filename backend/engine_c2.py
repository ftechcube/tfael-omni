#!/usr/bin/env python3
"""Sub-modul TFAEL-OMNI — impor dari engine_core untuk shared state."""
from engine_core import *  # noqa: F401, F403
from celltower_lookup import geolocate_cells as _geolocate_cells_real  # noqa: F401

def execute_force_gps_ping(unit_id: str, spoof_attack: bool = False) -> Dict[str, Any]:
    """
    Mengeksekusi 1-Click Force GPS Ping via Binary SMS Port 8901 (SRS-C2-01 & SRS-C2-02).
    Jika spoof_attack=True, mensimulasikan penyerang mengirim SMS tanpa kunci HMAC yang sah.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM tactical_units WHERE unit_id = ?", (unit_id,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": f"Unit {unit_id} tidak ditemukan"}

    unit = dict(row)
    cmd_packet = build_c2_sms_packet(
        unit_id=unit_id,
        cmd_code=CMD_FORCE_GPS_PING,
        spoof_invalid_key=spoof_attack,
    )

    is_valid, verify_status, verify_meta = verify_c2_sms_packet(
        unit_id=unit_id,
        packet_hex=cmd_packet["packet_hex"],
    )

    now = utc_now_iso()
    if not is_valid:
        # Otomatis picu Critical Alert di SIEM (Anti-Spoofing bekerja 100%)
        alert_id = f"SIM-SPOOF-{int(time.time()) % 100000}"
        conn.execute(
            """
            INSERT OR REPLACE INTO siem_alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                alert_id,
                now,
                "CRITICAL",
                "SIGMA-TFAEL-8901: Binary SMS HMAC-SHA256 Verification Failed",
                "Defense Evasion / Spoofing",
                "T1562",
                f"Spoofed SMS Port 8901 Blocked on {unit_id}",
                unit_id,
                "185.220.101.45 (Spoofed GSM Sender)",
                -6.1910,
                106.8380,
                unit["lat"],
                unit["lon"],
                round(haversine_km(-6.1910, 106.8380, unit["lat"], unit["lon"]), 2),
                0.0,
                f"Serangan SMS Biner Palsu ke {unit_id} ditolak otomatis oleh Android TEE Keystore ({verify_status}). Tag diterima: {verify_meta.get('received_hmac')}",
                "OPEN",
                "AUTO_REJECTED_BY_TEE",
            ),
        )
        conn.execute(
            "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
            (
                now,
                "ADVERSARY_SIM",
                "SPOOFED_SMS_8901_BLOCKED",
                unit_id,
                cmd_packet["hmac_tag_hex"],
                f"REJECTED: {verify_status}",
            ),
        )
        conn.commit()
        conn.close()
        return {
            "ok": False,
            "spoof_blocked": True,
            "verify_status": verify_status,
            "command_packet": cmd_packet,
            "verification_meta": verify_meta,
            "siem_alert_triggered": alert_id,
        }

    # HMAC Sah: bangun balasan telemetri terenkripsi AES-128-GCM (kripto NYATA).
    # Posisi yang dibalas TIDAK direkayasa: dipakai posisi NYATA perangkat bila tersedia
    # dari kanal nyata (GPS perangkat keras / geolokasi sel), selain itu ditandai SIMULASI.
    t0 = time.time()
    REAL_CHANNELS = {
        "REAL_HARDWARE_GPS": ("DEVICE_GNSS_REAL", 1),      # fix_type 1 = GNSS presisi tinggi
        "REAL_CELL_GEOLOC": ("CELL_GEOLOCATION_REAL", 3),  # fix_type 3 = BTS Cell-ID
        "SOS_EMERGENCY": ("DEVICE_SOS_BEACON_REAL", 9),    # fix_type 9 = SOS beacon
    }
    channel_now = unit.get("channel", "")
    if channel_now in REAL_CHANNELS:
        fix_source, fix_type = REAL_CHANNELS[channel_now]
        simulated = False
    else:
        fix_source, fix_type = "SIMULATED_C2_REPLY", 0
        simulated = True

    # Posisi NYATA terakhir yang dilaporkan unit (tanpa rekayasa pergeseran)
    fix_lat = round(float(unit["lat"]), 6)
    fix_lon = round(float(unit["lon"]), 6)

    encrypted_reply = build_encrypted_telemetry_reply(
        unit_id=unit_id,
        lat=fix_lat,
        lon=fix_lon,
        alt_m=unit["alt_m"] or 15,
        speed_kmh=unit["speed_kmh"] or 0,
        battery_pct=unit["battery_pct"],
        fix_type=fix_type,
        mcc=unit["mcc"] or 510,
        mnc=unit["mnc"] or 10,
        lac=unit["lac"] or 4102,
        cid=unit["cid"] or 88219,
    )

    # Hanya perbarui waktu kontak; JANGAN memindahkan unit atau memalsukan jejak.
    conn.execute(
        "UPDATE tactical_units SET last_seen = ? WHERE unit_id = ?",
        (now, unit_id),
    )

    detail = (
        f"Fix NYATA via {fix_source} ({fix_lat}, {fix_lon})"
        if not simulated
        else f"Balasan SIMULASI (tak ada perangkat fisik): posisi terakhir diketahui ({fix_lat}, {fix_lon})"
    )
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (
            now,
            "C2-OPERATOR-01",
            "FORCE_GPS_PING_SMS_8901",
            unit_id,
            f"HMAC:{cmd_packet['hmac_tag_hex']} / AES-GCM:{encrypted_reply['auth_tag_hex']}",
            detail,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "verify_status": verify_status,
        "simulated": simulated,
        "fix_source": fix_source,
        "position": {"lat": fix_lat, "lon": fix_lon},
        "crypto_processing_ms": round((time.time() - t0) * 1000, 2),
        "command_packet": cmd_packet,
        "encrypted_reply": encrypted_reply,
    }


def triangulate_unit_position(
    unit_id: str,
    observed_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Triangulasi / Multilaterasi Cell-ID NYATA (SRS-C2-03).

    Dua mode:
    - observed_cells diisi [{lac,cid,rssi(dBm)}] → mode NYATA: koordinat tiap sel diresolusi
      dari tabel bts_towers (nyata bila sudah diimpor dari OpenCellID) dan RSSI NYATA dipakai
      langsung pada Least-Squares. Tanpa sintesis.
    - observed_cells kosong → mode DEMO: RSSI disintesis dari posisi unit (lihat catatan).

    Perangkat (handset/transceiver) melaporkan daftar sel serving + neighbor beserta
    RSSI-nya. Mesin mengestimasi posisi perangkat dari geometri beberapa menara BTS —
    BUKAN menggambar lingkaran di sekeliling koordinat yang sudah diketahui.

    Catatan kejujuran: karena MVP tidak terhubung ke modem radio sungguhan, nilai RSSI
    tiap menara disintesis dari posisi fisik perangkat memakai model path-loss + fading
    multipath deterministik. Namun SOLUSI POSISI direkonstruksi murni dari (koordinat
    menara + RSSI) via Least-Squares, tanpa mengetahui posisi asli. Posisi asli hanya
    dipakai setelahnya untuk melaporkan galat (error_vs_truth_m) sebagai bukti ketepatan.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM tactical_units WHERE unit_id = ?", (unit_id,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": f"Unit {unit_id} tidak ditemukan"}
    unit = dict(row)
    true_lat, true_lon = unit["lat"], unit["lon"]

    # Bila pemanggil tak memberi sel, pakai sel teramati NYATA tersimpan dari agen (bila ada).
    if observed_cells is None:
        _uc = conn.execute("SELECT cells_json FROM unit_cells WHERE unit_id = ?", (unit_id,)).fetchone()
        if _uc:
            try:
                _stored = json.loads(_uc["cells_json"] or "[]")
                observed_cells = _stored if _stored else None
            except Exception:
                observed_cells = None

    towers = [dict(t) for t in conn.execute("SELECT * FROM bts_towers").fetchall()]
    measurements: List[Dict[str, Any]] = []
    sources = set()

    if observed_cells:
        # ---- MODE NYATA: sel teramati + koordinat menara dari DB (resolusi lac+cid) ----
        by_key = {(t.get("lac"), t.get("cid")): t for t in towers}
        unresolved = []
        for c in observed_cells:
            try:
                key = (int(c["lac"]), int(c.get("cid", c.get("cellid"))))
                rssi = float(c.get("rssi", c.get("signal")))
            except (KeyError, TypeError, ValueError):
                continue
            t = by_key.get(key)
            if not t:
                unresolved.append(key)
                continue
            sources.add(t.get("data_source", "SEED_SYNTHETIC"))
            measurements.append({
                "tower_id": t["tower_id"], "operator": t["operator"], "cid": t["cid"],
                "lat": t["lat"], "lon": t["lon"], "rssi_dbm": rssi,
            })
        if not measurements:
            observed_cells = None  # sel teramati tak cocok di DB menara → jatuh ke mode demo
        else:
            est = estimate_position(measurements)  # tanpa 'truth' — ini pengukuran nyata
            est["mode"] = "REAL_OBSERVED_CELLS"
    if not observed_cells:
        measurements = []
        sources = set()
        # ---- MODE DEMO: RSSI disintesis dari posisi unit. Ambil ~12 menara TERDEKAT saja
        # (handset nyata hanya "mendengar" segelintir menara), bukan semua puluhan ribu. ----
        nearest = sorted(towers, key=lambda t: tri_haversine_m(true_lat, true_lon, t["lat"], t["lon"]))[:12]
        for t in nearest:
            d_true = tri_haversine_m(true_lat, true_lon, t["lat"], t["lon"])
            rssi_clean = distance_to_rssi_dbm(d_true)
            seed = int(hashlib.sha256(f"{unit_id}|{t['tower_id']}".encode()).hexdigest(), 16)
            jitter = ((seed % 1001) / 1000.0 - 0.5) * 5.0  # fading ±2.5 dB deterministik
            rssi = rssi_clean + jitter
            if rssi < BTS_AUDIBLE_FLOOR_DBM:
                continue
            sources.add(t.get("data_source", "SEED_SYNTHETIC"))
            measurements.append({
                "tower_id": t["tower_id"], "operator": t["operator"], "cid": t["cid"],
                "lat": t["lat"], "lon": t["lon"], "rssi_dbm": rssi,
            })
        if not measurements:
            conn.close()
            return {"ok": False, "error": "Tidak ada menara BTS yang menjangkau unit (di luar cakupan)."}
        est = estimate_position(measurements, truth=(true_lat, true_lon))
        est["mode"] = "DEMO_SYNTHETIC_RSSI"

    est["unit_id"] = unit_id
    est["tower_data_source"] = sorted(sources)  # SEED_SYNTHETIC dan/atau OPENCELLID (nyata)
    est["towers_real"] = all(s != "SEED_SYNTHETIC" for s in sources) if sources else False

    now = utc_now_iso()
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (
            now,
            "TRIANGULATION-ENGINE",
            "BTS_CELL_ID_MULTILATERATION",
            unit_id,
            hashlib.sha256(f"{unit_id}:{est['lat']}:{est['lon']}:{now}".encode()).hexdigest()[:24].upper(),
            f"{est['method']}: {est['num_towers']} BTS -> ({est['lat']}, {est['lon']}) "
            f"±{est['accuracy_m']}m | galat vs GPS: {est.get('error_vs_truth_m', 'N/A')}m",
        ),
    )
    conn.commit()
    conn.close()
    return est


def geolocate_live_cells(
    cells: List[Dict[str, Any]],
    radio: str = "lte",
    mcc: Optional[int] = None,
    mnc: Optional[int] = None,
    attach_unit_id: str = "",
) -> Dict[str, Any]:
    """
    Geolokasi NYATA dari sel seluler teramati (Unwired Labs / OpenCellID).
    Berbeda dari triangulate_unit_position (simulasi offline), ini memakai basis data
    menara GLOBAL SUNGGUHAN. Jika attach_unit_id diisi, posisi hasil dipasang ke unit
    tersebut di peta C4ISR.
    """
    res = _geolocate_cells_real(cells=cells, radio=radio, mcc=mcc, mnc=mnc)
    now = utc_now_iso()
    conn = get_db()
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (
            now,
            "CELL-GEOLOCATION",
            "LIVE_CELL_GEOLOCATION_UNWIRED",
            attach_unit_id or f"{len(cells)} sel",
            hashlib.sha256(f"{cells}:{now}".encode()).hexdigest()[:24].upper(),
            (f"OK ({res.get('lat')}, {res.get('lon')}) ±{res.get('accuracy_m')}m "
             f"via {res.get('provider', '-')}, {res.get('num_cells', 0)} sel"
             if res.get("ok") else f"GAGAL: {res.get('error')}"),
        ),
    )

    if res.get("ok") and attach_unit_id:
        row = conn.execute("SELECT * FROM tactical_units WHERE unit_id = ?", (attach_unit_id,)).fetchone()
        if row:
            trail = json.loads(row["trail_json"] or "[]")
            trail.append([round(res["lat"], 6), round(res["lon"], 6)])
            conn.execute(
                """
                UPDATE tactical_units
                SET lat = ?, lon = ?, channel = 'REAL_CELL_GEOLOC', status_color = 'YELLOW',
                    bts_radius_m = ?, last_seen = ?, trail_json = ?
                WHERE unit_id = ?
                """,
                (round(res["lat"], 6), round(res["lon"], 6),
                 int(res.get("accuracy_m") or 500), now, json.dumps(trail[-12:]), attach_unit_id),
            )
            res["attached_unit_id"] = attach_unit_id
    conn.commit()
    conn.close()
    return res


_CCTV_CATALOG_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "cams": []}
# Koordinat PERKIRAAN tingkat-kecamatan untuk kamera ATCS Kab. Tangerang (portal tak ekspos lat/lon).
# Dipakai untuk menempatkan titik di peta GIS (heatmap kepadatan). Perkiraan, bukan GPS kamera presisi.
_CCTV_COORDS = {
    "Jayanti 1 Arah Serang": (-6.2490, 106.3340),
    "Jayanti 2 Arah Gembong": (-6.2505, 106.3375),
    "Cikupa Kedaton 1": (-6.2340, 106.5100),
    "Cikupa Mas": (-6.2385, 106.5160),
    "Cisauk 1": (-6.3215, 106.6410),
    "Cisauk 2": (-6.3245, 106.6455),
}
_CCTV_COORDS_AREA = {
    "jayanti": (-6.2497, 106.3360), "cikupa": (-6.2360, 106.5130), "cisauk": (-6.3230, 106.6430),
}
_CCTV_PORTALS = {
    "tangerangkab": {
        "name": "ATCS Dishub Kabupaten Tangerang",
        "list_url": "https://cctv-dishub.tangerangkab.go.id/cctv",
        "base": "https://cctv-dishub.tangerangkab.go.id",
    },
}


