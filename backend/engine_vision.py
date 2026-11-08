#!/usr/bin/env python3
"""Sub-modul TFAEL-OMNI — impor dari engine_core untuk shared state."""
from engine_core import *  # noqa: F401, F403
from engine_c2 import _CCTV_PORTALS, _CCTV_CATALOG_CACHE, _CCTV_COORDS, _CCTV_COORDS_AREA  # noqa: F401

def fetch_cctv_catalog(portal: str = "tangerangkab", ttl_sec: int = 1800) -> Dict[str, Any]:
    """
    Ambil daftar kamera CCTV publik dari portal ATCS (nama, lokasi, URL stream HLS).
    Di-cache (default 30 mnt) agar tidak membebani server pemerintah. Hormati air-gap.
    """
    if os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true", "TRUE", "yes"):
        return {"ok": False, "error": "Mode air-gap: katalog CCTV online dinonaktifkan.", "cams": []}
    p = _CCTV_PORTALS.get(portal)
    if not p:
        return {"ok": False, "error": f"Portal '{portal}' tidak dikenal.", "cams": []}
    now_ts = time.time()
    if _CCTV_CATALOG_CACHE["cams"] and (now_ts - _CCTV_CATALOG_CACHE["fetched_at"] < ttl_sec):
        return {"ok": True, "cached": True, "portal": p["name"], "cams": _CCTV_CATALOG_CACHE["cams"]}
    try:
        req = urllib.request.Request(p["list_url"], headers={"User-Agent": "Mozilla/5.0 TFAEL-OMNI/2.0"})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    except Exception as e:
        return {"ok": False, "error": f"Gagal mengambil katalog: {type(e).__name__}: {e}", "cams": []}
    cams = []
    for b in re.split(r'wire:key="[^"]*table\.records\.', html)[1:]:
        m = re.match(r"([0-9a-z]{20,})", b)
        if not m:
            continue
        cid = m.group(1)
        labels = re.findall(r"fi-ta-text-item-label[^>]*>\s*([^<]+?)\s*<", b)
        name = labels[0].strip() if labels else cid
        loc = labels[1].strip() if len(labels) > 1 else ""
        ll = _CCTV_COORDS.get(name) or _CCTV_COORDS_AREA.get(loc.lower())
        cams.append({
            "id": cid, "name": name, "location": loc,
            "stream_url": f"{p['base']}/storage/video/{cid}/{cid}.m3u8",
            "lat": ll[0] if ll else None, "lon": ll[1] if ll else None,
            "coord_approx": True,
        })
    # dedup berdasarkan id
    seen = set(); uniq = []
    for c in cams:
        if c["id"] in seen:
            continue
        seen.add(c["id"]); uniq.append(c)
    if uniq:
        _CCTV_CATALOG_CACHE["cams"] = uniq
        _CCTV_CATALOG_CACHE["fetched_at"] = now_ts
    return {"ok": True, "cached": False, "portal": p["name"], "cams": uniq}


def _draw_detections_on_jpeg(jpg_bytes: bytes, detections: List[Dict[str, Any]]) -> bytes:
    """Gambar kotak bounding box + label objek YOLO di atas frame JPEG (via OpenCV)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return jpg_bytes
    try:
        img = cv2.imdecode(np.frombuffer(jpg_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return jpg_bytes
        for d in detections:
            bb = d.get("bbox")
            if not bb or len(bb) != 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in bb]
            label = f"{d.get('label', '?')} {int(round(float(d.get('confidence', 0)) * 100))}%"
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 220, 120), 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), (0, 220, 120), -1)
            cv2.putText(img, label, (x1 + 3, max(10, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 20, 10), 1, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes() if ok else jpg_bytes
    except Exception:
        return jpg_bytes


_VEHICLE_LABELS = {"car", "truck", "bus", "motorcycle"}


def _load_plate_watchlist() -> Dict[str, Dict[str, str]]:
    """Watchlist pelat = pelat milik target di DB (dinormalisasi tanpa spasi, huruf besar)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT target_id, code_name, plate_number FROM target_profiles WHERE plate_number IS NOT NULL AND plate_number != ''"
    ).fetchall()
    conn.close()
    wl = {}
    for r in rows:
        norm = re.sub(r"[^A-Z0-9]", "", (r["plate_number"] or "").upper())
        if norm:
            wl[norm] = {"target_id": r["target_id"], "code_name": r["code_name"], "plate": r["plate_number"]}
    return wl


def run_anpr(jpeg_bytes: bytes, conf: float = 0.25, scan_whole: bool = False) -> Dict[str, Any]:
    """
    ANPR NYATA: deteksi kendaraan (YOLO) → crop → baca pelat (Tesseract) → regex TNKB
    Indonesia → cocokkan watchlist pelat target. Menggambar pelat + tandai HIT watchlist.
    `scan_whole`: bila True, OCR seluruh frame juga (untuk foto pelat dekat tanpa kendaraan).
    """
    try:
        import cv2
        import numpy as np
    except Exception as e:
        return {"ok": False, "error": f"OpenCV tak terpasang: {e}"}

    det = detect_objects_real(jpeg_bytes, conf=conf)
    if not det.get("available"):
        return {"ok": False, "error": f"YOLO tak aktif: {det.get('reason')}"}

    img = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "error": "Frame tak dapat didecode."}

    watchlist = _load_plate_watchlist()
    plate_re = re.compile(r"[A-Z]{1,2}\s?\d{1,4}\s?[A-Z]{0,3}")
    vehicles = [d for d in det.get("detections", []) if d.get("label") in _VEHICLE_LABELS]
    plates: List[Dict[str, Any]] = []

    for v in vehicles:
        bb = v.get("bbox")
        if not bb or len(bb) != 4:
            continue
        x1, y1, x2, y2 = [max(0, int(c)) for c in bb]
        crop = img[y1:y2, x1:x2]
        if crop.size == 0 or (x2 - x1) < 24 or (y2 - y1) < 24:
            continue
        ok, buf = cv2.imencode(".jpg", crop)
        if not ok:
            continue
        ocr = ocr_plate_text_real(buf.tobytes())
        raw = ocr.get("text", "")
        m = plate_re.search(raw)
        if not m:
            continue
        plate_text = m.group(0).strip()
        norm = re.sub(r"[^A-Z0-9]", "", plate_text)
        if len(norm) < 4:
            continue
        hit = watchlist.get(norm)
        plates.append({
            "plate": plate_text, "normalized": norm, "vehicle": v["label"],
            "bbox": [x1, y1, x2, y2], "confidence": v.get("confidence"),
            "watchlist_hit": bool(hit), "target": hit,
        })

    # Fallback: OCR seluruh frame (untuk foto pelat dekat tanpa kendaraan terdeteksi)
    if scan_whole and not plates:
        full = run_ocr_real(jpeg_bytes)
        for m in plate_re.finditer(full.get("text", "").upper()):
            norm = re.sub(r"[^A-Z0-9]", "", m.group(0))
            if len(norm) < 4:
                continue
            hit = watchlist.get(norm)
            plates.append({
                "plate": m.group(0).strip(), "normalized": norm, "vehicle": "(frame penuh)",
                "bbox": None, "confidence": None, "watchlist_hit": bool(hit), "target": hit,
            })

    # Anotasi: kotak kendaraan + teks pelat; MERAH bila cocok watchlist
    for p in plates:
        if not p.get("bbox"):
            continue
        x1, y1, x2, y2 = p["bbox"]
        hit = p["watchlist_hit"]
        color = (0, 0, 255) if hit else (0, 200, 255)
        label = f"{p['plate']}" + (f" !WATCHLIST {p['target']['code_name']}" if hit else "")
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3 if hit else 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(img, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), color, -1)
        cv2.putText(img, label, (x1 + 4, max(12, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    ok, out = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    hits = [p for p in plates if p["watchlist_hit"]]

    now = utc_now_iso()
    conn = get_db()
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (now, "ANPR-ENGINE", "ANPR_PLATE_READ", f"{len(plates)} plat",
         hashlib.sha256(f"{[p['normalized'] for p in plates]}:{now}".encode()).hexdigest()[:24].upper(),
         f"{len(vehicles)} kendaraan, {len(plates)} pelat terbaca, {len(hits)} HIT watchlist: {[p['plate'] for p in hits]}"),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "vehicles": len(vehicles),
        "plates_read": len(plates),
        "watchlist_size": len(watchlist),
        "hits": hits,
        "plates": plates,
        "frame_b64": "data:image/jpeg;base64," + base64.b64encode(out.tobytes()).decode("ascii"),
        "note": "Pelat dari CCTV jauh sering tak terbaca; paling andal pada pelat dekat/jelas.",
    }


def run_anpr_on_cctv(stream_url: str) -> Dict[str, Any]:
    """Ambil 1 frame CCTV lalu jalankan ANPR. HIT watchlist → alert SIEM + lokasi kamera."""
    url = (stream_url or "").strip()
    if not url.startswith(("http://", "https://", "rtsp://")):
        return {"ok": False, "error": "URL stream tidak valid."}
    grab = grab_stream_frame_real(url)
    if not grab.get("ok"):
        return {"ok": False, "error": grab.get("error", "Gagal ambil frame")}
    res = run_anpr(grab["jpeg"])

    # Kenali kamera dari URL (untuk lokasi di peta)
    cam = None
    cat = fetch_cctv_catalog()
    if cat.get("ok"):
        cam = next((c for c in cat["cams"] if c["stream_url"] == url), None)
    if cam:
        res["camera"] = {"name": cam["name"], "location": cam["location"], "lat": cam["lat"], "lon": cam["lon"]}

    # Tiap HIT watchlist → terbitkan alert SIEM Siber-Fisik di lokasi kamera
    hits = res.get("hits", []) if res.get("ok") else []
    if hits and cam and cam.get("lat") is not None:
        conn = get_db()
        now = utc_now_iso()
        for h in hits:
            alert_id = f"ANPR-{int(time.time() * 1000) % 1000000}"
            tgt = h.get("target", {})
            conn.execute(
                "INSERT INTO siem_alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (alert_id, now, "CRITICAL",
                 f"ANPR-WATCHLIST: Pelat {h['plate']} terdeteksi ({cam['name']})",
                 "Target Acquisition / ANPR Hit", "T1200",
                 f"Kendaraan watchlist {tgt.get('code_name', '?')} terlihat CCTV",
                 tgt.get("code_name", "UNKNOWN"),
                 f"CCTV {cam['name']} ({cam['location']})",
                 cam["lat"], cam["lon"], cam["lat"], cam["lon"], 0.0, 0.0,
                 f"Kendaraan {h['plate']} (target {tgt.get('target_id', '?')} / {tgt.get('code_name', '?')}) "
                 f"terdeteksi ANPR di CCTV {cam['name']} ({cam['location']}) pada {now}.",
                 "OPEN", "NONE"),
            )
            time.sleep(0.001)
        conn.commit()
        conn.close()
        res["siem_alerts_created"] = len(hits)
    return res


def run_anpr_on_image(image_b64: str) -> Dict[str, Any]:
    """Jalankan ANPR pada gambar base64 (frame webcam / unggahan foto pelat jelas)."""
    try:
        raw = base64.b64decode((image_b64 or "").split(",")[-1])
    except Exception as e:
        return {"ok": False, "error": f"Gambar base64 tak valid: {e}"}
    if len(raw) < 64:
        return {"ok": False, "error": "Gambar kosong."}
    return run_anpr(raw, scan_whole=True)


_CCTV_SWEEP_CACHE: Dict[str, Any] = {"ts": 0.0, "cams": []}


def _congestion_level(n: int) -> str:
    return "PADAT" if n >= 12 else ("SEDANG" if n >= 5 else "LANCAR")


def sweep_cctv_congestion(ttl_sec: int = 60) -> Dict[str, Any]:
    """
    Pindai SEMUA kamera (yang punya koordinat), hitung kendaraan per kamera via YOLO,
    tetapkan level kepadatan → untuk heatmap di peta GIS. Di-cache agar hemat.
    """
    now_ts = time.time()
    if _CCTV_SWEEP_CACHE["cams"] and (now_ts - _CCTV_SWEEP_CACHE["ts"] < ttl_sec):
        return {"ok": True, "cached": True, "cams": _CCTV_SWEEP_CACHE["cams"]}
    cat = fetch_cctv_catalog()
    if not cat.get("ok"):
        return {"ok": False, "error": cat.get("error", "katalog gagal"), "cams": []}
    out = []
    for c in cat["cams"]:
        if c.get("lat") is None:
            continue
        grab = grab_stream_frame_real(c["stream_url"])
        if not grab.get("ok"):
            out.append({**_cam_brief(c), "vehicles": None, "level": "OFFLINE", "error": grab.get("error")})
            continue
        det = detect_objects_real(grab["jpeg"], conf=0.25)
        veh = sum(1 for d in det.get("detections", []) if d.get("label") in _VEHICLE_LABELS) if det.get("available") else 0
        out.append({**_cam_brief(c), "vehicles": veh, "level": _congestion_level(veh)})
    _CCTV_SWEEP_CACHE["cams"] = out
    _CCTV_SWEEP_CACHE["ts"] = now_ts
    return {"ok": True, "cached": False, "cams": out}


def _cam_brief(c: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": c["id"], "name": c["name"], "location": c["location"],
            "lat": c["lat"], "lon": c["lon"], "stream_url": c["stream_url"]}


def analyze_cctv_stream(stream_url: str, conf: float = 0.25) -> Dict[str, Any]:
    """
    Ambil 1 frame dari CCTV publik (HLS/RTSP) lalu jalankan YOLOv8 NYATA.
    Mengembalikan deteksi + ringkasan per-kelas + frame BERANOTASI (kotak objek) base64.
    """
    url = (stream_url or "").strip()
    if not url.startswith(("http://", "https://", "rtsp://")):
        return {"ok": False, "error": "URL stream tidak valid (harus http/https/rtsp)."}
    grab = grab_stream_frame_real(url)
    if not grab.get("ok"):
        return {"ok": False, "error": grab.get("error", "Gagal mengambil frame")}
    jpg = grab["jpeg"]
    det = detect_objects_real(jpg, conf=conf)
    now = utc_now_iso()
    summary: Dict[str, int] = {}
    for o in det.get("detections", []):
        summary[o["label"]] = summary.get(o["label"], 0) + 1
    # Gambar kotak bounding box pada frame bila ada deteksi
    out_jpg = _draw_detections_on_jpeg(jpg, det.get("detections", [])) if det.get("detections") else jpg
    conn = get_db()
    conn.execute(
        "INSERT INTO c2_audit_log (timestamp, operator_id, action_type, target_ref, crypto_proof, details) VALUES (?,?,?,?,?,?)",
        (now, "VISION-YOLO", "CCTV_YOLO_DETECTION", url[:80],
         hashlib.sha256(f"{url}:{now}".encode()).hexdigest()[:24].upper(),
         (f"{det.get('count', 0)} objek: {summary}" if det.get("available") else f"YOLO tak aktif: {det.get('reason')}")),
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "available": det.get("available", False),
        "reason": det.get("reason"),
        "frame_wh": [grab["width"], grab["height"]],
        "count": det.get("count", 0),
        "summary": summary,
        "detections": det.get("detections", []),
        "frame_b64": "data:image/jpeg;base64," + base64.b64encode(out_jpg).decode("ascii"),
    }


def analyze_vision_frame(image_b64: str) -> Dict[str, Any]:
    """Deteksi objek NYATA (YOLOv8) pada satu frame gambar (base64). Graceful bila YOLO tak terpasang."""
    try:
        raw = base64.b64decode((image_b64 or "").split(",")[-1])
    except Exception as e:
        return {"ok": False, "error": f"Gambar base64 tak valid: {e}"}
    if len(raw) < 64:
        return {"ok": False, "error": "Frame kosong/terlalu kecil."}
    res = detect_objects_real(raw)
    return {"ok": True, **res}


