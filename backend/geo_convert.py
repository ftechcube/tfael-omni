#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Konversi Koordinat Militer (Desimal / DMS / UTM / MGRS).

Memakai pustaka NGA-standard (`mgrs`, membungkus GEOTRANS) + `utm` (pure-Python).
Akurasi sub-meter, offline, deterministik — sesuai doktrin peta topografi TNI AD / NATO.
"""

import re
from typing import Any, Dict

try:
    import mgrs as _mgrs_lib  # type: ignore
    import utm as _utm_lib  # type: ignore
    _M = _mgrs_lib.MGRS()
    _AVAILABLE = True
    _ERR = None
except Exception as _e:  # pustaka tak terpasang
    _AVAILABLE = False
    _ERR = str(_e)


def _to_dms(dec: float, pos: str, neg: str) -> str:
    hemi = pos if dec >= 0 else neg
    dec = abs(dec)
    d = int(dec)
    mf = (dec - d) * 60
    mi = int(mf)
    s = (mf - mi) * 60
    return f"{d}°{mi:02d}'{s:04.1f}\"{hemi}"


def _format_mgrs(raw: str) -> str:
    """'48MYU0218317059' -> '48M YU 02183 17059'."""
    m = re.match(r"^(\d{1,2})([C-X])([A-Z]{2})(\d+)$", raw)
    if not m:
        return raw
    zone, band, sq, digits = m.groups()
    half = len(digits) // 2
    easting, northing = digits[:half], digits[half:]
    return f"{zone}{band} {sq} {easting} {northing}"


def convert_coordinates(lat: float, lon: float, precision: int = 5) -> Dict[str, Any]:
    """lat/lon desimal -> {decimal, dms, utm, mgrs}. precision 5 = presisi 1 meter."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return {"ok": False, "error": "lat/lon tidak valid"}
    if not (-80.0 <= lat <= 84.0):
        return {"ok": False, "error": "Lintang di luar cakupan UTM/MGRS (-80..84)."}
    if not _AVAILABLE:
        return {"ok": False, "error": f"Pustaka konversi tak terpasang: {_ERR}"}
    try:
        e, n, zn, zl = _utm_lib.from_latlon(lat, lon)
        raw = _M.toMGRS(lat, lon, MGRSPrecision=precision)
        return {
            "ok": True,
            "decimal": f"{lat:.6f}, {lon:.6f}",
            "dms": f"{_to_dms(lat, 'N', 'S')} {_to_dms(lon, 'E', 'W')}",
            "utm": f"{zn}{zl} {int(round(e))}E {int(round(n))}N",
            "mgrs": _format_mgrs(raw),
            "mgrs_raw": raw,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        }
    except Exception as ex:
        return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
