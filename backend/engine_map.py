#!/usr/bin/env python3
"""Sub-modul TFAEL-OMNI — impor dari engine_core untuk shared state."""
from engine_core import *  # noqa: F401, F403
from engine_offgrid import get_active_route  # noqa: E402

# ==============================================================================
# LAYANAN OPERASIONAL 6 PILAR (API HANDLERS)
# ==============================================================================

def get_dashboard_overview(target_offset: int = 0, target_limit: int = 50) -> Dict[str, Any]:
    conn = get_db()
    units = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM tactical_units ORDER BY CASE WHEN unit_id LIKE 'IPHONE%' THEN 0 WHEN unit_id LIKE 'MAC%' THEN 1 ELSE 2 END, unit_id ASC"
        ).fetchall()
    ]
    for u in units:
        u["trail"] = json.loads(u["trail_json"] or "[]")
        del u["trail_json"]

    tower_count = conn.execute("SELECT COUNT(*) FROM bts_towers").fetchone()[0]
    towers = []
    geofences = [dict(r) for r in conn.execute("SELECT * FROM geofences").fetchall()]
    for g in geofences:
        g["polygon"] = json.loads(g["polygon_json"])
        del g["polygon_json"]
        breaches = []
        poly = g["polygon"]
        if isinstance(poly, list) and len(poly) >= 3:
            for u in units:
                if u.get("lat") is not None and u.get("lon") is not None:
                    if point_in_polygon(u["lat"], u["lon"], poly):
                        breaches.append({"id": u["unit_id"], "type": "UNIT", "name": u["name"]})
        g["active_entities_inside"] = breaches

    target_total = conn.execute("SELECT COUNT(*) FROM target_profiles").fetchone()[0]
    target_limit  = max(1, min(target_limit, 200))
    target_offset = max(0, target_offset)
    targets = [dict(r) for r in conn.execute(
        "SELECT * FROM target_profiles ORDER BY risk_score DESC LIMIT ? OFFSET ?",
        (target_limit, target_offset),
    ).fetchall()]
    for t in targets:
        t["osint"] = json.loads(t["osint_json"] or "{}")
        t["pattern_of_life"] = json.loads(t["pattern_of_life_json"] or "{}")
        t["graph"] = json.loads(t["graph_json"] or "{}")
        del t["osint_json"], t["pattern_of_life_json"], t["graph_json"]

    _raw_alerts = [dict(r) for r in conn.execute("SELECT * FROM siem_alerts ORDER BY rowid DESC LIMIT 100").fetchall()]
    # Normalize DB column names → frontend SiemAlert interface
    alerts = []
    for a in _raw_alerts:
        alerts.append({
            "id":               a.get("alert_id") or "",
            "title":            a.get("sigma_rule", ""),
            "severity":         (a.get("severity") or "medium").lower(),
            "timestamp":        a.get("event_time", ""),
            "source_ip":        a.get("src_ip", ""),
            "dest_ip":          "",
            "mitre_id":         a.get("mitre_id", ""),
            "mitre_tactic":     a.get("mitre_tactic", ""),
            "mitre_name":       a.get("mitre_name", ""),
            "sigma_rule":       a.get("sigma_rule", ""),
            "user_or_unit":     a.get("user_or_unit", ""),
            "description":      a.get("description", ""),
            "status":           a.get("status", "OPEN"),
            "soar_action_taken": a.get("soar_action_taken", ""),
            "cyber_lat":        a.get("cyber_lat"),
            "cyber_lon":        a.get("cyber_lon"),
            "phys_lat":         a.get("phys_lat"),
            "phys_lon":         a.get("phys_lon"),
            "distance_km":      a.get("distance_km"),
            "velocity_kmh":     a.get("velocity_kmh"),
        })
    raw_evidences = [dict(r) for r in conn.execute("SELECT * FROM forensic_evidence_vault ORDER BY block_index DESC LIMIT 50").fetchall()]
    evidences = []
    chain_of_custody = []
    for e in raw_evidences:
        yara = json.loads(e["yara_matches_json"] or "[]")
        exif = json.loads(e["exif_json"] or "{}")
        extracted = json.loads(e["extracted_entities_json"] or "{}")
        carved = json.loads(e["carved_records_json"] or "[]")
        # Determine type from magic_mime
        mime = (e.get("magic_mime") or "").lower()
        if "sqlite" in mime:
            etype = "sqlite"
        elif "pcap" in mime:
            etype = "pcap"
        elif "pdf" in mime:
            etype = "pdf"
        elif "image" in mime:
            etype = "image"
        else:
            etype = "binary"
        # SQLite tables from carved records
        sqlite_tables = []
        if "sqlite" in mime and carved:
            sqlite_tables = sorted({r.get("table", "") for r in carved if r.get("table")})
        # PCAP summary from carved records
        pcap_summary = None
        if "pcap" in mime and carved:
            pcap_summary = {"packets": len(carved), "records": carved[:20]}
        # Normalize to frontend ForensicEvidence shape
        evidences.append({
            "id": e["evidence_id"],
            "filename": e["file_name"],
            "type": etype,
            "sha256": e["sha256_hash"],
            "size": e["file_size"],
            "ingested_at": e["acquired_at"],
            "analysis": {
                "ela": e.get("ela_anomaly_score"),
                "yara": yara,
                "sqlite_tables": sqlite_tables if sqlite_tables else None,
                "pcap_summary": pcap_summary,
            },
            "exif": exif,
            "extracted_entities": extracted,
            "transcript": e.get("transcript_text", ""),
        })
        # Build chain of custody entry
        chain_of_custody.append({
            "hash": e["curr_chain_hash"],
            "prev_hash": e["prev_chain_hash"],
            "timestamp": e["acquired_at"],
            "action": f"INGEST {e['file_name']}",
            "actor": e.get("examiner_id", "SYSTEM"),
        })

    audit_logs = [dict(r) for r in conn.execute("SELECT * FROM c2_audit_log ORDER BY log_id DESC LIMIT 20").fetchall()]
    annotations = [dict(r) for r in conn.execute("SELECT * FROM map_annotations ORDER BY created_at DESC LIMIT 300").fetchall()]
    conn.close()

    airgap = os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true", "TRUE", "yes")
    cell_key_present = bool(os.environ.get("OMNI_CELL_API_KEY", "").strip()) or os.path.isfile(
        os.path.join(os.path.dirname(__file__), "cell_api.key")
    )
    capabilities = {
        "osint_online": not airgap,                      # DNS/SSL/port/GeoIP butuh jaringan
        "cell_geolocation": (not airgap) and cell_key_present,
        "host_siem": True,                               # lsof/netstat lokal
        "forensics_binary": True,                        # EXIF/entropi/carving/hash-chain lokal
        "triangulation_offline": True,                   # multilaterasi Least-Squares lokal
        "gpu_inference": False,                           # tidak ada inferensi GPU di MVP ini
    }
    # Status mesin AI forensik NYATA (YARA/OCR/Whisper/YOLO) — terdeteksi dari pustaka terpasang
    fai = forensic_ai_status()
    capabilities["forensic_yara"] = fai.get("yara", False)
    capabilities["forensic_ocr"] = fai.get("ocr_tesseract", False)
    capabilities["forensic_whisper"] = fai.get("whisper", False)
    capabilities["vision_yolo"] = fai.get("yolo", False)
    active = [k for k, v in capabilities.items() if v]

    return {
        "system_time_utc": utc_now_iso(),
        "lan_ip": get_live_lan_ip(),
        "air_gapped_mode": airgap,
        "engine_status": f"CPU/stdlib engine — aktif: {', '.join(active)}",
        "capabilities": capabilities,
        "units": units,
        "bts_towers": towers,
        "bts_tower_count": tower_count,
        "geofences": geofences,
        "targets": targets,
        "targets_total": target_total,
        "targets_offset": target_offset,
        "targets_limit": target_limit,
        "siem_alerts": alerts,
        "host_siem_sockets": scan_live_host_sockets(),
        "forensic_evidences": evidences,
        "chain_of_custody": sorted(chain_of_custody, key=lambda x: x["timestamp"]),
        "audit_logs": audit_logs,
        "annotations": annotations,
        "active_route": get_active_route(),
    }


def add_map_annotation(kind: str, lat: float, lon: float, radius_m: float = 0.0,
                       label: str = "", color: str = "", created_by: str = "agen",
                       photo: str = "") -> Dict[str, Any]:
    """Simpan anotasi peta (marker/lingkaran, opsional foto) dari agen lapangan agar
    dibagikan ke panel admin dan agen lain melalui overview (team awareness ala ATAK)."""
    kind = "circle" if str(kind).lower().startswith("circle") else "marker"
    anno_id = f"ANN-{int(time.time() * 1000) % 100000000}-{(created_by or 'x')[:6]}"
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO map_annotations "
        "(anno_id, kind, lat, lon, radius_m, label, color, created_by, created_at, photo) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (anno_id, kind, float(lat), float(lon), float(radius_m or 0.0),
         str(label or ""), str(color or ""), str(created_by or "agen"), utc_now_iso(),
         str(photo or "")),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "anno_id": anno_id, "kind": kind}


def delete_map_annotation(anno_id: str, created_by: str = "") -> Dict[str, Any]:
    """Hapus satu anotasi berdasarkan anno_id. Bila created_by diisi, hanya boleh
    menghapus milik agen itu (agar agen tak menghapus anotasi agen lain)."""
    conn = get_db()
    if created_by:
        cur = conn.execute("DELETE FROM map_annotations WHERE anno_id = ? AND created_by = ?",
                           (str(anno_id), str(created_by)))
    else:
        cur = conn.execute("DELETE FROM map_annotations WHERE anno_id = ?", (str(anno_id),))
    n = cur.rowcount
    conn.commit()
    conn.close()
    return {"ok": True, "deleted": n}


def clear_map_annotations(created_by: str = "") -> Dict[str, Any]:
    """Hapus anotasi dari server. Dengan created_by: hanya milik agen itu;
    tanpa created_by: semua (untuk pusat komando)."""
    conn = get_db()
    if created_by:
        cur = conn.execute("DELETE FROM map_annotations WHERE created_by = ?", (str(created_by),))
    else:
        cur = conn.execute("DELETE FROM map_annotations")
    n = cur.rowcount
    conn.commit()
    conn.close()
    return {"ok": True, "deleted": n}


