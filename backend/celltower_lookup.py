#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Geolokasi Sel Seluler NYATA via Unwired Labs / OpenCellID (Pilar 1/2)

Mengubah daftar sel yang BENAR-BENAR teramati perangkat (serving + neighbor:
MCC/MNC/LAC/CID + kuat sinyal) menjadi koordinat lat/lon NYATA memakai basis data
menara global Unwired Labs (endpoint process.php). Ini menggantikan triangulasi
berbasis menara fiktif untuk jalur ONLINE.

Catatan arsitektur:
- Token "pk.*" hanya berwenang untuk geolokasi (process.php) — server Unwired yang
  melakukan fusi/multilaterasi dari basis data menaranya. Endpoint /cell/get (koordinat
  menara mentah) TIDAK diizinkan token ini, jadi mesin Least-Squares lokal kita dipakai
  untuk mode OFFLINE/air-gap, sedangkan modul ini untuk mode ONLINE nyata.
- Menghormati mode air-gap (OMNI_AIRGAP=1 -> menolak panggilan keluar).
- Hasil di-cache di tabel cell_geo_cache agar hemat kuota (balance) pada query berulang.
"""

import hashlib
import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "tfael_omni.db")
KEY_FILE = os.path.join(os.path.dirname(__file__), "cell_api.key")
ENDPOINT = "https://us1.unwiredlabs.com/v2/process.php"
VALID_RADIOS = {"gsm", "cdma", "umts", "lte", "nbiot"}


def load_api_key() -> Optional[str]:
    """Ambil token dari env OMNI_CELL_API_KEY, atau dari berkas kunci lokal."""
    key = os.environ.get("OMNI_CELL_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(KEY_FILE, "r") as f:
            k = f.read().strip()
            return k or None
    except FileNotFoundError:
        return None


def is_airgapped() -> bool:
    return os.environ.get("OMNI_AIRGAP", "").strip() in ("1", "true", "TRUE", "yes")


def _ensure_cache_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cell_geo_cache (
            cache_key TEXT PRIMARY KEY,
            request_json TEXT,
            lat REAL,
            lon REAL,
            accuracy_m REAL,
            provider TEXT,
            cached_at TEXT
        )
        """
    )


def _cache_key(radio: str, cells: List[Dict[str, Any]]) -> str:
    norm = sorted(
        (int(c["mcc"]), int(c["mnc"]), int(c["lac"]), int(c["cid"]))
        for c in cells
    )
    return hashlib.sha256(f"{radio}|{norm}".encode()).hexdigest()


def normalize_cells(cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bakukan field sel ke format Unwired Labs; buang sel tak lengkap."""
    out: List[Dict[str, Any]] = []
    for c in cells or []:
        try:
            cell = {
                "lac": int(c["lac"]),
                "cid": int(c.get("cid", c.get("cellid"))),
            }
        except (KeyError, TypeError, ValueError):
            continue
        # mcc/mnc boleh di level atas request; sertakan per-sel bila ada
        if c.get("mcc") is not None:
            cell["mcc"] = int(c["mcc"])
        if c.get("mnc") is not None:
            cell["mnc"] = int(c["mnc"])
        if c.get("signal") is not None:
            cell["signal"] = int(c["signal"])  # dBm (negatif), opsional tapi menaikkan akurasi
        out.append(cell)
    return out


def import_opencellid_csv(
    csv_path: str,
    bbox: Optional[tuple] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Impor menara NYATA dari ekspor CSV OpenCellID ke tabel bts_towers (air-gap friendly).

    Format kolom OpenCellID: radio,mcc,net,area,cell,unit,lon,lat,range,samples,...
    (net=MNC, area=LAC, cell=CID). Mendukung .csv maupun .csv.gz.
    `bbox`=(min_lat,min_lon,max_lat,max_lon) untuk menyaring wilayah (hemat ukuran).
    """
    import csv
    import gzip

    if not os.path.isfile(csv_path):
        return {"ok": False, "error": f"Berkas tak ditemukan: {csv_path}"}

    opener = gzip.open if csv_path.endswith(".gz") else open
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(bts_towers)").fetchall()}
    if "data_source" not in cols:
        conn.execute("ALTER TABLE bts_towers ADD COLUMN data_source TEXT DEFAULT 'SEED_SYNTHETIC'")

    imported = skipped = 0
    try:
        with opener(csv_path, "rt", newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            # Deteksi header OpenCellID; bila tak ada header, asumsikan urutan standar
            idx = {"radio": 0, "mcc": 1, "net": 2, "area": 3, "cell": 4, "lon": 6, "lat": 7, "range": 8}
            if header and "mcc" in [h.strip().lower() for h in header]:
                low = [h.strip().lower() for h in header]
                idx = {k: low.index(k) for k in ("radio", "mcc", "net", "area", "cell", "lon", "lat") if k in low}
                idx["range"] = low.index("range") if "range" in low else None
            else:
                if header:  # baris pertama ternyata data
                    reader = _chain_first(header, reader)
            rows = []
            for row in reader:
                try:
                    mcc = int(row[idx["mcc"]]); net = int(row[idx["net"]])
                    area = int(row[idx["area"]]); cell = int(row[idx["cell"]])
                    lon = float(row[idx["lon"]]); lat = float(row[idx["lat"]])
                    rng = int(float(row[idx["range"]])) if idx.get("range") is not None and row[idx["range"]] else 500
                    radio = row[idx["radio"]] if idx.get("radio") is not None else "LTE"
                except (ValueError, IndexError, KeyError):
                    skipped += 1
                    continue
                if bbox and not (bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]):
                    continue
                tower_id = f"OCID-{mcc}-{net}-{area}-{cell}"
                area_name = f"OpenCellID {radio} {mcc}-{net}"
                rows.append((tower_id, f"MNC {net}", mcc, net, area, cell, lat, lon, rng, area_name, "OPENCELLID"))
                imported += 1
                if limit and imported >= limit:
                    break
            conn.executemany(
                "INSERT OR REPLACE INTO bts_towers (tower_id,operator,mcc,mnc,lac,cid,lat,lon,radius_m,area_name,data_source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()
    except Exception as e:
        conn.close()
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "imported": imported}
    total = conn.execute("SELECT COUNT(*) FROM bts_towers WHERE data_source='OPENCELLID'").fetchone()[0]
    conn.close()
    return {"ok": True, "imported": imported, "skipped": skipped, "total_real_towers": total}


def _chain_first(first_row, reader):
    yield first_row
    for r in reader:
        yield r


def geolocate_cells(
    cells: List[Dict[str, Any]],
    radio: str = "lte",
    mcc: Optional[int] = None,
    mnc: Optional[int] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Geolokasi NYATA dari daftar sel teramati. `cells`: [{mcc,mnc,lac,cid,signal?}].
    `mcc`/`mnc` opsional sebagai default level-request (operator yang sama).
    """
    if is_airgapped():
        return {"ok": False, "error": "Mode air-gap aktif (OMNI_AIRGAP=1): panggilan geolokasi keluar ditolak."}

    token = load_api_key()
    if not token:
        return {"ok": False, "error": "Token API sel belum diset (backend/cell_api.key atau env OMNI_CELL_API_KEY)."}

    radio = (radio or "lte").lower()
    if radio not in VALID_RADIOS:
        radio = "lte"

    norm_cells = normalize_cells(cells)
    if not norm_cells:
        return {"ok": False, "error": "Tidak ada sel valid (butuh minimal lac & cid)."}

    # Cek cache
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_cache_table(conn)
    ck = _cache_key(radio, [{**c, "mcc": c.get("mcc", mcc), "mnc": c.get("mnc", mnc)} for c in norm_cells])
    if use_cache:
        row = conn.execute("SELECT * FROM cell_geo_cache WHERE cache_key = ?", (ck,)).fetchone()
        if row:
            conn.close()
            return {
                "ok": True, "lat": row["lat"], "lon": row["lon"],
                "accuracy_m": row["accuracy_m"], "provider": row["provider"],
                "num_cells": len(norm_cells), "radio": radio,
                "cached": True, "source": "LIVE_CELL_GEOLOCATION",
            }

    body: Dict[str, Any] = {"token": token, "radio": radio, "cells": norm_cells, "address": 0}
    if mcc is not None:
        body["mcc"] = int(mcc)
    if mnc is not None:
        body["mnc"] = int(mnc)

    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        conn.close()
        return {"ok": False, "error": f"HTTP {e.code} dari penyedia geolokasi.", "detail": e.read().decode()[:200]}
    except Exception as e:
        conn.close()
        return {"ok": False, "error": f"Gagal menghubungi penyedia geolokasi: {type(e).__name__}: {e}"}
    latency_ms = int((time.time() - t0) * 1000)

    if data.get("status") != "ok":
        conn.close()
        return {"ok": False, "error": f"Penyedia menolak: {data.get('message', data.get('status', 'unknown'))}", "raw": data}

    lat = data.get("lat")
    lon = data.get("lon")
    acc = float(data.get("accuracy", 0) or 0)

    conn.execute(
        "INSERT OR REPLACE INTO cell_geo_cache VALUES (?,?,?,?,?,?,?)",
        (ck, json.dumps(norm_cells), lat, lon, acc, "UnwiredLabs/OpenCellID",
         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "source": "LIVE_CELL_GEOLOCATION",
        "provider": "UnwiredLabs/OpenCellID",
        "lat": lat,
        "lon": lon,
        "accuracy_m": acc,
        "num_cells": len(norm_cells),
        "radio": radio,
        "balance_remaining": data.get("balance"),
        "latency_ms": latency_ms,
        "cached": False,
    }
