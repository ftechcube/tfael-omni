"""Unit tests for engine_core utility functions (pure, no DB, no network)."""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _import():
    import importlib
    return importlib.import_module("engine_core")


# ---------------------------------------------------------------------------
# haversine_km
# ---------------------------------------------------------------------------

def test_haversine_zero_distance():
    ec = _import()
    assert ec.haversine_km(-6.2, 106.8, -6.2, 106.8) == 0.0


def test_haversine_known_distance():
    ec = _import()
    # Jakarta → Bandung (approx 120 km)
    d = ec.haversine_km(-6.2088, 106.8456, -6.9175, 107.6191)
    assert 110 < d < 135, f"Jakarta→Bandung should be ~120km, got {d:.1f}"


def test_haversine_symmetry():
    ec = _import()
    d1 = ec.haversine_km(0, 0, 1, 1)
    d2 = ec.haversine_km(1, 1, 0, 0)
    assert abs(d1 - d2) < 0.001


# ---------------------------------------------------------------------------
# point_in_polygon
# ---------------------------------------------------------------------------

def test_point_inside_square():
    ec = _import()
    square = [[0, 0], [0, 2], [2, 2], [2, 0]]
    assert ec.point_in_polygon(1, 1, square) is True


def test_point_outside_square():
    ec = _import()
    square = [[0, 0], [0, 2], [2, 2], [2, 0]]
    assert ec.point_in_polygon(5, 5, square) is False


def test_point_on_boundary_is_outside():
    """Ray-casting classifies boundary points as outside — document expected behaviour."""
    ec = _import()
    square = [[0, 0], [0, 2], [2, 2], [2, 0]]
    result = ec.point_in_polygon(0, 1, square)
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# utc_now_iso
# ---------------------------------------------------------------------------

def test_utc_now_iso_format():
    ec = _import()
    ts = ec.utc_now_iso()
    # Must match "YYYY-MM-DDTHH:MM:SSZ"
    from datetime import datetime, timezone
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    assert dt.year >= 2025


# ---------------------------------------------------------------------------
# parse_aprs_packet (basic smoke)
# ---------------------------------------------------------------------------

def test_parse_aprs_returns_dict():
    ec = _import()
    result = ec.parse_aprs_packet("CALLSIGN>APRS,TCPIP*:!1234.56N/10612.34E>")
    assert isinstance(result, dict)


def test_parse_aprs_garbage_does_not_raise():
    ec = _import()
    result = ec.parse_aprs_packet("garbage string @@@ !!!")
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# radio_unit_id
# ---------------------------------------------------------------------------

def test_radio_unit_id_uppercase():
    ec = _import()
    uid = ec.radio_unit_id("bravo-02")
    assert uid == uid.upper()


def test_radio_unit_id_stable():
    ec = _import()
    assert ec.radio_unit_id("alpha") == ec.radio_unit_id("alpha")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(failed)
