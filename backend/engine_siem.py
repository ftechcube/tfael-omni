#!/usr/bin/env python3
"""Sub-modul TFAEL-OMNI — impor dari engine_core untuk shared state."""
from engine_core import *  # noqa: F401, F403
from engine_forensics import ingest_forensic_artifact  # noqa: E402

def simulate_impossible_travel_alert(
    unit_id: str = "IPHONE-11",
    remote_city: str = "",
    cyber_lat: Optional[float] = None,
    cyber_lon: Optional[float] = None,
    remote_ip: str = "172.67.181.99",
    time_gap_min: Optional[float] = None,
    threshold_kmh: float = 900.0,
) -> Dict[str, Any]:
    """
    Detektor Siber-Fisik Impossible Travel NYATA (SRS-SIM-02).

    Lokasi 'siber' diambil dari GeoIP NYATA alamat IP login (bukan koordinat kaleng).
    Selisih waktu diambil NYATA dari jeda antara fix GPS fisik terakhir unit (last_seen)
    dan waktu login sekarang. Alert HANYA diterbitkan bila kecepatan semu melampaui ambang
    (default 900 km/jam) — bukan dipaksakan.
    """
    from real_osint import lookup_geoip_and_asn

    conn = get_db()
    unit = conn.execute("SELECT * FROM tactical_units WHERE unit_id = ?", (unit_id,)).fetchone()
    if not unit:
        unit = conn.execute(
            "SELECT * FROM tactical_units ORDER BY CASE WHEN channel LIKE 'REAL%' THEN 0 ELSE 1 END, last_seen DESC LIMIT 1"
        ).fetchone()
    if not unit:
        conn.close()
        return {"ok": False, "error": "Tidak ada unit untuk dievaluasi."}

    actual_unit_id = unit["unit_id"]
    phys_lat, phys_lon = unit["lat"], unit["lon"]

    # Lokasi siber NYATA dari GeoIP IP login (bila tak di-override manual)
    if cyber_lat is None or cyber_lon is None:
        geo = lookup_geoip_and_asn(remote_ip)
        if geo.get("lat") is None or geo.get("lon") is None:
            conn.close()
            return {"ok": False, "error": f"GeoIP gagal menyelesaikan IP {remote_ip} (mode air-gap atau IP privat?)."}
        cyber_lat, cyber_lon = geo["lat"], geo["lon"]
        if not remote_city:
            remote_city = f"{geo.get('city', '')} ({geo.get('asn', geo.get('isp', ''))})".strip()
    remote_city = remote_city or remote_ip

    # Selisih waktu NYATA: login sekarang vs fix fisik terakhir (last_seen)
    now = utc_now_iso()
    if time_gap_min is None:
        try:
            last_dt = datetime.strptime(unit["last_seen"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            gap_min = max(0.5, (datetime.now(timezone.utc) - last_dt).total_seconds() / 60.0)
        except (ValueError, TypeError):
            gap_min = 5.0
    else:
        gap_min = max(0.5, float(time_gap_min))

    dist_km = round(haversine_km(cyber_lat, cyber_lon, phys_lat, phys_lon), 2)
    velocity_kmh = round(dist_km / (gap_min / 60.0), 1)
    detected = velocity_kmh > threshold_kmh

    result = {
        "ok": True,
        "detected": detected,
        "unit_id": actual_unit_id,
        "remote_ip": remote_ip,
        "remote_city": remote_city,
        "cyber_coord": [round(cyber_lat, 4), round(cyber_lon, 4)],
        "phys_coord": [round(phys_lat, 4), round(phys_lon, 4)],
        "distance_km": dist_km,
        "time_gap_min": round(gap_min, 1),
        "velocity_kmh": velocity_kmh,
        "threshold_kmh": threshold_kmh,
    }

    if not detected:
        conn.execute(
            "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
            (now, "SIEM-HAVERSINE-ENGINE", "IMPOSSIBLE_TRAVEL_EVALUATED_OK", actual_unit_id,
             hashlib.sha256(f"{actual_unit_id}:{remote_ip}:{now}".encode()).hexdigest()[:24].upper(),
             f"Normal: {actual_unit_id} vs {remote_ip} ({remote_city}) -> {dist_km} km dalam {gap_min:.1f} mnt = {velocity_kmh} km/jam (<= {threshold_kmh})."),
        )
        conn.commit()
        conn.close()
        return result

    alert_id = f"IMPT-{int(time.time()) % 100000}"
    desc = (
        f"IMPOSSIBLE TRAVEL: Login {actual_unit_id} dari IP {remote_ip} ({remote_city}) di ({cyber_lat:.4f}, {cyber_lon:.4f}), "
        f"padahal GPS fisik terakhir di ({phys_lat:.4f}, {phys_lon:.4f}). "
        f"Haversine {dist_km:,} km dalam {gap_min:.1f} menit → {velocity_kmh:,} km/jam (> ambang {threshold_kmh:g} km/jam)."
    )
    conn.execute(
        "INSERT INTO siem_alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            alert_id, now, "CRITICAL",
            f"SIGMA-C2-009: Impossible Travel ({actual_unit_id} → {remote_city})",
            "Credential Access / Valid Accounts", "T1078",
            f"Impossible Travel ({velocity_kmh:,} km/h)",
            actual_unit_id, f"{remote_ip} ({remote_city})",
            cyber_lat, cyber_lon, phys_lat, phys_lon, dist_km, velocity_kmh,
            desc, "OPEN", "NONE",
        ),
    )
    proof = hashlib.sha256(f"{alert_id}:{actual_unit_id}:{remote_ip}:{now}".encode()).hexdigest()[:24].upper()
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (now, "SIEM-HAVERSINE-ENGINE", "HAVERSINE_IMPOSSIBLE_TRAVEL", actual_unit_id, proof,
         f"Anomali {alert_id}: {dist_km:,} km / {gap_min:.1f} mnt = {velocity_kmh:,} km/jam"),
    )
    conn.commit()
    conn.close()
    result["alert_id"] = alert_id

    # --- Auto-ingest SIEM alert ke unified intelligence graph ---
    try:
        engine_graph.ingest_siem_alert({
            "alert_id": alert_id, "severity": "CRITICAL",
            "rule_name": f"SIGMA-C2-009: Impossible Travel ({actual_unit_id})",
            "src_ip": remote_ip, "unit_id": actual_unit_id,
            "description": desc,
        })
    except Exception as _gex:
        print(f"[graph-ingest] siem {alert_id}: {_gex}")

    return result


def execute_soar_action(alert_id: str, action: str) -> Dict[str, Any]:
    """
    Mengeksekusi Playbook SOAR Lite pada Alert SIEM (Pilar 5 -> Pilar 6 Auto-Freeze).
    """
    conn = get_db()
    alert = conn.execute("SELECT * FROM siem_alerts WHERE alert_id = ?", (alert_id,)).fetchone()
    if not alert:
        conn.close()
        return {"ok": False, "error": "Alert tidak ditemukan"}

    now = utc_now_iso()
    conn.execute(
        "UPDATE siem_alerts SET status = 'MITIGATED', soar_action_taken = ? WHERE alert_id = ?",
        (action, alert_id),
    )

    # Jika aksi menyertakan pembekuan forensik, otomatis segel artefak log ke Evidence Vault (Pilar 6)
    frozen_ev_id = None
    if "FREEZE" in action or "ISOLATE" in action:
        snapshot_bytes = json.dumps(dict(alert), sort_keys=True).encode("utf-8")
        res = ingest_forensic_artifact(
            file_name=f"soar_frozen_incident_{alert_id}.json",
            raw_bytes=snapshot_bytes,
            case_id=f"CASE-SIEM-{alert_id}",
            examiner_id="SOAR-AUTO-RESPONDER",
            linked_target_id="TGT-01",
            existing_conn=conn,
        )
        frozen_ev_id = res.get("evidence_id")

    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (
            now,
            "SOC-ANALYST-01",
            f"SOAR_{action}",
            alert_id,
            hashlib.sha256(f"{alert_id}:{action}:{now}".encode()).hexdigest()[:24].upper(),
            f"Playbook {action} dieksekusi pada {alert_id}. Forensic Evidence: {frozen_ev_id or 'N/A'}",
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "alert_id": alert_id, "action": action, "frozen_evidence_id": frozen_ev_id}


