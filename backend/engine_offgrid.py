#!/usr/bin/env python3
"""Sub-modul TFAEL-OMNI — impor dari engine_core untuk shared state."""
from engine_core import *  # noqa: F401, F403

def ingest_offgrid_packet(channel: str, raw_payload: str) -> Dict[str, Any]:
    """
    Menerima paket off-grid dan memetakan pengirimnya sebagai unit TERSENDIRI
    (berdasarkan callsign — bukan lagi satu unit tetap). Format dideteksi otomatis:
    JSON → LoRa Meshtastic, selain itu → APRS VHF AX.25/TNC2 (Satelit LEO memakai
    format APRS juga). Setiap callsign jadi satu unit biru di peta C4ISR.
    """
    raw = (raw_payload or "").strip()
    if raw.startswith("{"):
        parsed = parse_meshtastic_packet(raw)
        if channel in (None, "", "APRS_VHF"):
            channel = "LORA_MESH"
    else:
        parsed = parse_aprs_packet(raw)
        channel = channel or "APRS_VHF"

    if not parsed.get("valid"):
        return {"ok": False, "error": "Paket tidak dapat didekode", "decoded": parsed}

    conn = get_db()
    now = utc_now_iso()
    callsign = parsed["callsign"]
    unit_id = radio_unit_id(callsign)

    row = conn.execute("SELECT trail_json FROM tactical_units WHERE unit_id = ?", (unit_id,)).fetchone()
    trail = json.loads(row["trail_json"] or "[]") if row else []
    trail.append([parsed["lat"], parsed["lon"]])
    trail = trail[-12:]

    if row:
        conn.execute(
            """
            UPDATE tactical_units
            SET callsign = ?, channel = ?, status_color = 'BLUE',
                lat = ?, lon = ?, alt_m = ?, speed_kmh = ?, last_seen = ?, trail_json = ?
            WHERE unit_id = ?
            """,
            (callsign, channel, parsed["lat"], parsed["lon"], parsed["alt_m"],
             parsed["speed_kmh"], now, json.dumps(trail), unit_id),
        )
    else:
        label = "Unit Radio APRS/VHF" if channel == "APRS_VHF" else "Node LoRa Mesh"
        conn.execute(
            "INSERT INTO tactical_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (unit_id, callsign, f"{label} ({callsign})", "Off-grid (radio)", channel, "BLUE",
             parsed["lat"], parsed["lon"], parsed["alt_m"], parsed["speed_kmh"], 0,
             None, None, None, None, None, 0, now, json.dumps(trail)),
        )

    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (
            now,
            "OFFGRID-GATEWAY",
            f"INGEST_{channel}",
            unit_id,
            hashlib.sha256(raw.encode()).hexdigest()[:24].upper(),
            f"Paket {channel} dari {callsign} didekode ke ({parsed['lat']}, {parsed['lon']}) - {parsed.get('comment', '')}",
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "unit_id": unit_id, "channel": channel, "decoded": parsed}



def ingest_live_device_gps(
    unit_id: str,
    name: str,
    role: str,
    lat: float,
    lon: float,
    alt_m: int = 15,
    speed_kmh: int = 0,
    accuracy_m: int = 8,
    battery_pct: int = 92,
    is_sos: bool = False,
    reset_trail: bool = False,
    mcc: Optional[int] = None,
    mnc: Optional[int] = None,
    lac: Optional[int] = None,
    cid: Optional[int] = None,
    signal_dbm: Optional[int] = None,
    observed_cells: Optional[List[Dict[str, Any]]] = None,
    channel_override: Optional[str] = None,
    status_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Menerima koordinat GPS perangkat keras ASLI (dari iPhone 11 atau Mac pengguna)
    dan memperbarui peta C4ISR secara real-time. Bila agen lapangan mengirim data
    serving cell nyata (mcc/mnc/lac/cid/signal), nilai itu menimpa menara seed.
    `channel_override`/`status_override` dipakai jalur SMS-gateway agar unit yang
    posisinya tiba lewat SMS ditandai kanal SMS_2G_BTS (amber), bukan GPS langsung.
    """
    conn = get_db()
    now = utc_now_iso()
    row = conn.execute("SELECT lat, lon, trail_json FROM tactical_units WHERE unit_id = ?", (unit_id,)).fetchone()
    prev_lat = row["lat"] if row else None
    prev_lon = row["lon"] if row else None
    if row and not reset_trail:
        trail = json.loads(row["trail_json"] or "[]")
    else:
        trail = []

    # Tolak GOYANGAN GPS (jitter): perangkat yang DIAM tetap melaporkan fix yang
    # bergeser beberapa meter tiap detik — tanpa filter, jejak jadi zigzag padahal
    # tak ke mana-mana. Anggap "pindah" hanya bila geraknya melebihi radius jitter
    # (minimal 15 m, atau seukuran akurasi fix bila lebih kasar).
    jitter_m = max(15.0, float(accuracy_m or 0))
    moved_m = (haversine_km(prev_lat, prev_lon, lat, lon) * 1000.0
               if (prev_lat is not None and prev_lon is not None and not reset_trail) else None)

    if moved_m is not None and moved_m > 1500:
        # Lompatan jauh (mis. ganti sumber lokasi) → mulai jejak baru di titik ini.
        trail = [[round(lat, 6), round(lon, 6)]]
    elif moved_m is not None and moved_m <= jitter_m:
        # Masih dalam jitter → TAHAN posisi & jejak (jangan gambar pergerakan palsu).
        lat, lon = prev_lat, prev_lon
    else:
        # Benar-benar bergerak (atau fix pertama) → perbarui posisi & tambah jejak.
        trail.append([round(lat, 6), round(lon, 6)])
        trail = trail[-25:]

    if is_sos:
        channel, status_color = "SOS_EMERGENCY", "RED"
    elif channel_override:
        channel, status_color = channel_override, (status_override or "AMBER")
    else:
        channel, status_color = "REAL_HARDWARE_GPS", "GREEN"
    callsign = unit_id

    if row:
        conn.execute(
            """
            UPDATE tactical_units
            SET name = ?, role = ?, channel = ?, status_color = ?,
                lat = ?, lon = ?, alt_m = ?, speed_kmh = ?, battery_pct = ?,
                bts_radius_m = ?, last_seen = ?, trail_json = ?
            WHERE unit_id = ?
            """,
            (
                name,
                role,
                channel,
                status_color,
                round(lat, 6),
                round(lon, 6),
                int(alt_m),
                int(speed_kmh),
                int(battery_pct),
                max(3, int(accuracy_m)),
                now,
                json.dumps(trail),
                unit_id,
            ),
        )
    else:
        conn.execute(
            "INSERT INTO tactical_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                unit_id,
                callsign,
                name,
                role,
                channel,
                status_color,
                round(lat, 6),
                round(lon, 6),
                int(alt_m),
                int(speed_kmh),
                int(battery_pct),
                -62,
                510,
                10,
                4101,
                88101,
                max(3, int(accuracy_m)),
                now,
                json.dumps(trail),
            ),
        )

    # Simpan serving cell NYATA dari agen lapangan (menimpa nilai menara seed).
    _cell_sets, _cell_vals = [], []
    for _col, _val in (("mcc", mcc), ("mnc", mnc), ("lac", lac), ("cid", cid), ("signal_dbm", signal_dbm)):
        if _val is not None:
            _cell_sets.append(f"{_col} = ?")
            _cell_vals.append(int(_val))
    if _cell_sets:
        _cell_vals.append(unit_id)
        conn.execute(f"UPDATE tactical_units SET {', '.join(_cell_sets)} WHERE unit_id = ?", _cell_vals)

    # Simpan daftar sel teramati (serving + neighbor) untuk triangulasi NYATA on-demand.
    if observed_cells is not None:
        conn.execute("INSERT OR REPLACE INTO unit_cells (unit_id, cells_json) VALUES (?, ?)",
                     (unit_id, json.dumps(observed_cells)))

    sos_alert_id = None
    if is_sos:
        proof = hashlib.sha256(f"{unit_id}:{lat}:{lon}:{now}".encode()).hexdigest()[:24].upper()
        conn.execute(
            "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
            (
                now,
                unit_id,
                "REAL_DEVICE_SOS_BEACON",
                unit_id,
                proof,
                f"[DARURAT SOS PERANGKAT ASLI] {name} mengirim titik GPS darurat ({lat:.6f}, {lon:.6f}) ±{accuracy_m}m!",
            ),
        )
        sos_alert_id = f"SOS-{int(time.time()) % 100000}"
        conn.execute(
            "INSERT INTO siem_alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sos_alert_id,
                now,
                "CRITICAL",
                f"PANIC-SOS-01: Sinyal Darurat Personel Lapangan ({unit_id})",
                "Physical Tactical Emergency / SOS Beacon",
                "T1499",
                f"SOS Darurat ({lat:.5f}, {lon:.5f})",
                unit_id,
                f"Hardware GPS ±{accuracy_m}m (Alt: {alt_m}m)",
                round(lat, 6),
                round(lon, 6),
                round(lat, 6),
                round(lon, 6),
                0.0,
                0.0,
                f"DARURAT LAPANGAN: Perangkat {name} ({unit_id}) menekan tombol panik SOS pada koordinat ({lat:.6f}, {lon:.6f}) dengan radius akurasi ±{accuracy_m}m. Segel HMAC: {proof}.",
                "OPEN",
                "NONE",
            ),
        )

    last_cmd = conn.execute(
        "SELECT timestamp, action_type, crypto_proof, details FROM c2_audit_log WHERE target_ref = ? AND operator_id != ? ORDER BY rowid DESC LIMIT 1",
        (unit_id, unit_id),
    ).fetchone()
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "unit_id": unit_id,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "accuracy_m": accuracy_m,
        "channel": channel,
        "sos_alert_id": sos_alert_id,
        "last_c2_command": dict(last_cmd) if last_cmd else None,
        "updated_at": now,
    }


def ingest_sms_gateway_fix(
    unit_id: str,
    lat: float,
    lon: float,
    battery_pct: int = 0,
    fix_ts: Optional[int] = None,
    via_number: str = "",
    name: str = "",
    role: str = "",
) -> Dict[str, Any]:
    """
    Jalur GATEWAY SMS (Paket B): sebuah HP-jembatan di pos komando menerima SMS
    posisi terenkripsi dari agen lapangan (tanpa internet), mendekripsinya, lalu
    meneruskan koordinatnya ke sini lewat jaringan lokal. Unit ditandai kanal
    SMS_2G_BTS (amber) agar jelas posisinya tiba via SMS, bukan GPS data langsung.
    """
    uid = (unit_id or "").strip()
    if not uid:
        return {"ok": False, "error": "unit_id wajib diisi"}
    try:
        flat, flon = float(lat), float(lon)
    except (TypeError, ValueError):
        return {"ok": False, "error": "lat/lon tidak valid"}
    if not (-90 <= flat <= 90 and -180 <= flon <= 180):
        return {"ok": False, "error": "lat/lon di luar rentang"}

    res = ingest_live_device_gps(
        unit_id=uid,
        name=name or uid,
        role=role or "Agen (via SMS)",
        lat=flat,
        lon=flon,
        battery_pct=int(battery_pct) if str(battery_pct).lstrip("-").isdigit() else 0,
        channel_override="SMS_2G_BTS",
        status_override="AMBER",
    )

    # Jejak audit: catat bahwa posisi ini tiba lewat gateway SMS (bukti rantai C2).
    try:
        conn = get_db()
        now = utc_now_iso()
        age_s = ""
        if fix_ts:
            try:
                age_s = f", umur fix ~{max(0, int(time.time()) - int(fix_ts) // 1000)}s"
            except (TypeError, ValueError):
                age_s = ""
        proof = hashlib.sha256(f"{uid}:{flat}:{flon}:{now}".encode()).hexdigest()[:24].upper()
        conn.execute(
            "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
            (now, "SMS_GATEWAY", "SMS_GATEWAY_POS_RELAY", uid, proof,
             f"Posisi {uid} ({flat:.6f}, {flon:.6f}) diteruskan via gateway SMS dari {via_number or 'nomor tak dikenal'}{age_s}."),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    res["source"] = "SMS_GATEWAY"
    res["via_number"] = via_number
    return res


# ==============================================================================
# RUTE GPX (panduan jalur ala Coros/Garmin — impor track untuk diikuti offline)
# ==============================================================================

def parse_gpx(gpx_text: str) -> Dict[str, Any]:
    """
    Dekode GPX (XML) jadi daftar titik jalur + waypoint. Mendukung track (trkpt),
    route (rtept), dan waypoint (wpt), tahan-namespace (GPX 1.0/1.1).
    """
    import xml.etree.ElementTree as ET

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    root = ET.fromstring(gpx_text)
    trkpts: List[List[float]] = []
    rtepts: List[List[float]] = []
    wpts: List[Dict[str, Any]] = []
    name = ""
    for el in root.iter():
        t = local(el.tag)
        if t in ("trk", "rte", "metadata") and not name:
            for ch in el:
                if local(ch.tag) == "name" and ch.text and ch.text.strip():
                    name = ch.text.strip()
                    break
        la, lo = el.get("lat"), el.get("lon")
        if la is None or lo is None:
            continue
        try:
            pt = [round(float(la), 6), round(float(lo), 6)]
        except (TypeError, ValueError):
            continue
        if not (-90 <= pt[0] <= 90 and -180 <= pt[1] <= 180):
            continue
        if t == "trkpt":
            trkpts.append(pt)
        elif t == "rtept":
            rtepts.append(pt)
        elif t == "wpt":
            nm = ""
            for ch in el:
                if local(ch.tag) == "name" and ch.text:
                    nm = ch.text.strip()
                    break
            wpts.append({"lat": pt[0], "lon": pt[1], "name": nm})

    points = trkpts or rtepts
    total = 0.0
    for i in range(1, len(points)):
        total += haversine_km(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
    return {"name": name, "points": points, "waypoints": wpts, "total_km": round(total, 3)}


def import_route_from_gpx(gpx_text: str, name: str = "", actor: str = "operator") -> Dict[str, Any]:
    """Impor GPX → simpan sebagai rute AKTIF (hanya satu aktif) untuk ditampilkan & diikuti."""
    try:
        parsed = parse_gpx(gpx_text)
    except Exception as exc:
        return {"ok": False, "error": f"GPX tidak valid: {exc}"}
    points = parsed["points"]
    if len(points) < 2:
        return {"ok": False, "error": "GPX tidak berisi jalur (butuh minimal 2 titik track/route)."}
    rid = f"RTE-{int(time.time()) % 1000000}"
    rname = (name or "").strip() or parsed["name"] or rid
    conn = get_db()
    conn.execute("UPDATE routes SET active = 0")  # hanya satu rute aktif pada satu waktu
    conn.execute(
        "INSERT OR REPLACE INTO routes (route_id, name, points_json, waypoints_json, total_km, created_at, active) "
        "VALUES (?,?,?,?,?,?,1)",
        (rid, rname, json.dumps(points), json.dumps(parsed["waypoints"]), parsed["total_km"], utc_now_iso()),
    )
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (utc_now_iso(), actor, "ROUTE_IMPORT", rid,
         hashlib.sha256(gpx_text.encode()).hexdigest()[:24].upper(),
         f"Impor rute '{rname}': {len(points)} titik, {len(parsed['waypoints'])} waypoint, {parsed['total_km']} km."),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "route_id": rid, "name": rname, "num_points": len(points),
            "num_waypoints": len(parsed["waypoints"]), "total_km": parsed["total_km"]}


def get_active_route() -> Optional[Dict[str, Any]]:
    conn = get_db()
    r = conn.execute("SELECT * FROM routes WHERE active = 1 ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    if not r:
        return None
    return {
        "route_id": r["route_id"],
        "name": r["name"],
        "points": json.loads(r["points_json"] or "[]"),
        "waypoints": json.loads(r["waypoints_json"] or "[]"),
        "total_km": r["total_km"],
    }


def clear_active_route(actor: str = "operator") -> Dict[str, Any]:
    conn = get_db()
    n = conn.execute("UPDATE routes SET active = 0 WHERE active = 1").rowcount
    conn.commit()
    conn.close()
    return {"ok": True, "cleared": n}

