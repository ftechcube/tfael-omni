#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Mesin Triangulasi / Multilaterasi Cell-ID NYATA (Pilar 1/2)

Modul ini menentukan ESTIMASI posisi perangkat dari pengukuran radio beberapa
menara BTS (serving + neighbor cells), BUKAN sekadar menggambar lingkaran di
sekeliling koordinat yang sudah diketahui.

Pipeline:
  1. RSSI (dBm) tiap menara  ->  estimasi jarak (m) via model Log-Distance Path Loss.
  2. Proyeksi lat/lon -> bidang meter lokal (ENU equirectangular).
  3. >=3 menara: Least-Squares Multilateration (linearisasi lingkaran + normal equations).
     2 menara  : Weighted Centroid (bobot ~ 1/d^2).
     1 menara  : Cell-ID tunggal (pusat sel, akurasi = radius estimasi).
  4. Hitung residu RMS fit -> estimasi akurasi (radius ketidakpastian).

Hanya memakai pustaka standar Python (math) — tanpa numpy — agar tetap
100% on-premise/air-gapped.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

EARTH_R_M = 6371008.8

# --- Model radio makro-sel urban (mis. 1800 MHz), dikalibrasi agar:
#     ~300 m -> -80 dBm, ~1 km -> -90 dBm, ~8–9 km -> ambang jangkauan.
DEFAULT_REF_RSSI_DBM = -28.0   # RSSI pada jarak referensi 1 m
DEFAULT_PATH_LOSS_EXP = 2.05   # eksponen path-loss efektif (urban makrosel)
AUDIBLE_FLOOR_DBM = -110.0     # di bawah ini menara dianggap tak terdengar perangkat
MIN_RANGE_M = 1.0
MAX_RANGE_M = 25000.0


# ==============================================================================
# MODEL PROPAGASI RADIO
# ==============================================================================

def rssi_to_distance_m(
    rssi_dbm: float,
    ref_rssi_dbm: float = DEFAULT_REF_RSSI_DBM,
    path_loss_exp: float = DEFAULT_PATH_LOSS_EXP,
) -> float:
    """
    Log-Distance Path Loss:  RSSI = ref - 10*n*log10(d)  =>  d = 10^((ref - RSSI)/(10*n)).
    """
    exponent = (ref_rssi_dbm - rssi_dbm) / (10.0 * path_loss_exp)
    d = math.pow(10.0, exponent)
    return max(MIN_RANGE_M, min(d, MAX_RANGE_M))


def distance_to_rssi_dbm(
    distance_m: float,
    ref_rssi_dbm: float = DEFAULT_REF_RSSI_DBM,
    path_loss_exp: float = DEFAULT_PATH_LOSS_EXP,
) -> float:
    """Kebalikan model di atas: prediksi RSSI dari jarak (dipakai sintesis pengukuran)."""
    d = max(MIN_RANGE_M, distance_m)
    return ref_rssi_dbm - 10.0 * path_loss_exp * math.log10(d)


# ==============================================================================
# GEOMETRI
# ==============================================================================

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def _project(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Proyeksi equirectangular ke meter lokal (x=Timur, y=Utara) relatif (lat0, lon0)."""
    x = math.radians(lon - lon0) * math.cos(math.radians(lat0)) * EARTH_R_M
    y = math.radians(lat - lat0) * EARTH_R_M
    return x, y


def _unproject(x: float, y: float, lat0: float, lon0: float) -> Tuple[float, float]:
    lat = math.degrees(y / EARTH_R_M) + lat0
    lon = math.degrees(x / (EARTH_R_M * math.cos(math.radians(lat0)))) + lon0
    return lat, lon


# ==============================================================================
# ESTIMATOR POSISI
# ==============================================================================

def weighted_centroid(measurements: List[Dict[str, Any]]) -> Tuple[float, float]:
    """Centroid berbobot 1/d^2 (menara dengan sinyal kuat/jarak dekat menarik estimasi)."""
    sw = slat = slon = 0.0
    for m in measurements:
        d = max(MIN_RANGE_M, m["distance_m"])
        w = 1.0 / (d * d)
        sw += w
        slat += w * m["lat"]
        slon += w * m["lon"]
    if sw == 0:
        return measurements[0]["lat"], measurements[0]["lon"]
    return slat / sw, slon / sw


def _solve_2x2(a: float, b: float, c: float, d: float, e: float, f: float):
    """Selesaikan [[a,b],[c,d]]·[x,y]=[e,f]. Kembalikan None jika singular."""
    det = a * d - b * c
    if abs(det) < 1e-9:
        return None
    x = (e * d - b * f) / det
    y = (a * f - e * c) / det
    return x, y


def least_squares_multilateration(
    measurements: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Linearisasi lingkaran (x-xi)^2+(y-yi)^2 = ri^2 terhadap menara jangkar
    (sinyal terkuat / jarak terdekat), lalu selesaikan Least-Squares via
    normal equations (A^T A)x = A^T b. Butuh >= 3 menara non-kolinear.
    """
    if len(measurements) < 3:
        return None

    lat0 = sum(m["lat"] for m in measurements) / len(measurements)
    lon0 = sum(m["lon"] for m in measurements) / len(measurements)

    pts = []
    for m in measurements:
        x, y = _project(m["lat"], m["lon"], lat0, lon0)
        pts.append((x, y, max(MIN_RANGE_M, m["distance_m"])))

    # Jangkar = menara dengan jarak estimasi terkecil (paling andal)
    k = min(range(len(pts)), key=lambda i: pts[i][2])
    xk, yk, rk = pts[k]

    # Susun sistem linear A·[x,y] = b
    m00 = m01 = m11 = v0 = v1 = 0.0
    rows = 0
    for i, (xi, yi, ri) in enumerate(pts):
        if i == k:
            continue
        ax = 2.0 * (xk - xi)
        ay = 2.0 * (yk - yi)
        bb = (ri * ri - rk * rk) - (xi * xi - xk * xk) - (yi * yi - yk * yk)
        # Akumulasi normal equations A^T A dan A^T b
        m00 += ax * ax
        m01 += ax * ay
        m11 += ay * ay
        v0 += ax * bb
        v1 += ay * bb
        rows += 1

    if rows < 2:
        return None

    sol = _solve_2x2(m00, m01, m01, m11, v0, v1)
    if sol is None:
        return None
    sx, sy = sol
    est_lat, est_lon = _unproject(sx, sy, lat0, lon0)

    # Residu fit: |jarak(estimasi, menara) - jarak_RSSI|
    sq = 0.0
    for xi, yi, ri in pts:
        pred = math.hypot(sx - xi, sy - yi)
        sq += (pred - ri) ** 2
    residual_rms = math.sqrt(sq / len(pts))

    return {
        "lat": est_lat,
        "lon": est_lon,
        "residual_rms_m": residual_rms,
        "anchor_index": k,
    }


def estimate_position(
    measurements: List[Dict[str, Any]],
    truth: Optional[Tuple[float, float]] = None,
    ref_rssi_dbm: float = DEFAULT_REF_RSSI_DBM,
    path_loss_exp: float = DEFAULT_PATH_LOSS_EXP,
) -> Dict[str, Any]:
    """
    Orkestrator utama. `measurements`: list {tower_id, lat, lon, rssi_dbm, ...}.
    Jarak diturunkan DARI RSSI (bukan dari `truth`), sehingga posisi benar-benar
    direkonstruksi dari geometri. `truth` hanya dipakai untuk melaporkan galat.
    """
    meas = [dict(m) for m in measurements]
    for m in meas:
        m["distance_m"] = rssi_to_distance_m(m["rssi_dbm"], ref_rssi_dbm, path_loss_exp)

    if not meas:
        return {"ok": False, "error": "Tidak ada pengukuran menara BTS yang terdengar."}

    meas.sort(key=lambda m: m["rssi_dbm"], reverse=True)
    n = len(meas)

    method = ""
    est_lat = est_lon = 0.0
    residual_rms = None

    if n == 1:
        method = "CELL_ID_SINGLE"
        est_lat, est_lon = meas[0]["lat"], meas[0]["lon"]
        accuracy_m = meas[0]["distance_m"]  # tak ada arah: akurasi = radius sel
    elif n == 2:
        method = "WEIGHTED_CENTROID_2BTS"
        est_lat, est_lon = weighted_centroid(meas)
        # akurasi ~ separasi geometrik
        sep = haversine_m(meas[0]["lat"], meas[0]["lon"], meas[1]["lat"], meas[1]["lon"])
        accuracy_m = max(80.0, sep * 0.35)
    else:
        ls = least_squares_multilateration(meas)
        centroid = weighted_centroid(meas)
        if ls is None:
            method = "WEIGHTED_CENTROID_FALLBACK"
            est_lat, est_lon = centroid
            accuracy_m = 350.0
        else:
            method = f"LEAST_SQUARES_MULTILATERATION_{n}BTS"
            est_lat, est_lon = ls["lat"], ls["lon"]
            residual_rms = ls["residual_rms_m"]
            nearest_range = min(m["distance_m"] for m in meas)
            # Jika solusi LS meleset jauh dari centroid (geometri buruk/outlier),
            # jatuhkan ke centroid agar tetap robust.
            drift = haversine_m(est_lat, est_lon, centroid[0], centroid[1])
            if drift > 5000.0 or residual_rms > 8000.0:
                method = "WEIGHTED_CENTROID_FALLBACK_POOR_GEOMETRY"
                est_lat, est_lon = centroid
                accuracy_m = max(400.0, residual_rms * 0.6)
            else:
                # Radius kepercayaan Cell-ID: gabungan residu fit + ketidakpastian
                # jarak sel terdekat (galat RSSI bias, bukan sekadar noise fit).
                accuracy_m = max(150.0, residual_rms * 3.0, nearest_range * 0.5)

    used = [
        {
            "tower_id": m.get("tower_id", "BTS"),
            "lat": m["lat"],
            "lon": m["lon"],
            "rssi_dbm": round(m["rssi_dbm"], 1),
            "est_distance_m": round(m["distance_m"], 1),
            "operator": m.get("operator", ""),
            "cid": m.get("cid"),
        }
        for m in meas
    ]

    result = {
        "ok": True,
        "method": method,
        "lat": round(est_lat, 6),
        "lon": round(est_lon, 6),
        "accuracy_m": round(accuracy_m, 1),
        "residual_rms_m": round(residual_rms, 1) if residual_rms is not None else None,
        "num_towers": n,
        "towers": used,
        "model": {
            "ref_rssi_dbm": ref_rssi_dbm,
            "path_loss_exp": path_loss_exp,
        },
    }

    if truth is not None:
        err = haversine_m(est_lat, est_lon, truth[0], truth[1])
        result["ground_truth"] = {"lat": round(truth[0], 6), "lon": round(truth[1], 6)}
        result["error_vs_truth_m"] = round(err, 1)
        result["within_accuracy"] = err <= accuracy_m

    return result
