#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Server Pusat Komando Terpadu (API Orchestrator & Static HUD Server)
Berjalan 100% On-Premise di atas pustaka standar Python (http.server + ThreadingHTTPServer).
"""

import base64
import gzip
import hashlib
import hmac
import json
import mimetypes
import os
import secrets as _sec
import ssl
import subprocess
import sys
import threading
import time as _tm
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Pastikan direktori backend ada di sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
sys.path.insert(0, BACKEND_DIR)

import engine_graph
import engine_cognitive
# Daftar origin yang diizinkan untuk CORS. Diambil dari env OMNI_ALLOWED_ORIGINS
# (dipisah koma). Kosong = tolak semua permintaan lintas-asal (default aman).
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("OMNI_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

# Kunci pra-berbagi perangkat lapangan. Wajib diset atau akan di-generate otomatis.
AGENT_KEY = os.environ.get("OMNI_AGENT_KEY", "").strip()
if not AGENT_KEY:
    AGENT_KEY = _sec.token_hex(32)
    _masked = AGENT_KEY[:8] + "****"  # jangan log key penuh ke stderr
    sys.stderr.write(
        f"\n[TFAEL-OMNI][WARNING] OMNI_AGENT_KEY tidak diset. Key sementara: {_masked}...\n"
        "  -> Setel env var OMNI_AGENT_KEY untuk kunci permanen.\n\n"
    )

# Rate limiting per IP (token bucket sederhana, in-memory).
_RATE_BUCKETS: dict = {}
_RATE_LOCK = threading.Lock()


def _rate_ok(ip: str, key: str, max_rpm: int = 60) -> bool:
    """True jika request IP+key masih dalam batas max_rpm request/menit."""
    bk = f"{ip}:{key}"
    now = _tm.time()
    with _RATE_LOCK:
        rec = _RATE_BUCKETS.get(bk, [0, now + 60.0])
        if now > rec[1]:
            rec = [0, now + 60.0]
        rec[0] += 1
        _RATE_BUCKETS[bk] = rec
        if len(_RATE_BUCKETS) > 32768:
            expired = [k for k, v in _RATE_BUCKETS.items() if now > v[1]]
            for k in expired:
                _RATE_BUCKETS.pop(k, None)
        return rec[0] <= max_rpm


def _airgap_on() -> bool:
    # 1/true/yes = matikan semua panggilan jaringan keluar (air-gapped).
    return os.environ.get("OMNI_AIRGAP", "").strip().lower() in ("1", "true", "yes")


def _f(payload: dict, key: str, default: float) -> float:
    # Konversi aman ke float; nilai None/rusak jatuh ke default (hindari 500).
    try:
        v = payload.get(key)
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _i(payload: dict, key: str, default: int) -> int:
    # Konversi aman ke int; nilai None/rusak jatuh ke default (hindari 500).
    try:
        v = payload.get(key)
        return default if v is None else int(float(v))
    except (TypeError, ValueError):
        return default

# Pastikan tipe MIME font modern dikenali (woff2 tidak selalu terdaftar bawaan).
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")

from engines import (
    create_or_recon_target,
    create_or_recon_target_async,
    get_recon_job,
    execute_force_gps_ping,
    execute_soar_action,
    get_dashboard_overview,
    ingest_forensic_artifact,
    ingest_live_device_gps,
    ingest_sms_gateway_fix,
    ingest_offgrid_packet,
    import_route_from_gpx,
    clear_active_route,
    init_db,
    add_map_annotation,
    delete_map_annotation,
    clear_map_annotations,
    seed_targets_from_recon_async,
    auto_import_opencellid_async,
    analyze_cctv_stream,
    analyze_vision_frame,
    fetch_cctv_catalog,
    run_anpr_on_cctv,
    run_anpr_on_image,
    sweep_cctv_congestion,
    geolocate_live_cells,
    get_live_lan_ip,
    record_target_checkin_telemetry,
    save_scanner_to_profile,
    get_db,
    simulate_impossible_travel_alert,
    triangulate_unit_position,
    verify_forensic_chain,
)
import admin

import osint_engine
from geo_convert import convert_coordinates


class TfaelOmniHandler(BaseHTTPRequestHandler):
    # Sembunyikan versi Python — tampil sebagai nginx biasa di response header.
    server_version = "nginx/1.24.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        # Log ringkas
        sys.stderr.write(f"[TFAEL-OMNI API] {self.address_string()} - {fmt % args}\n")

    def _apply_cors(self):
        # Hanya kirim header CORS bila Origin permintaan ada di daftar izin.
        # Daftar kosong = tolak semua lintas-asal. Permintaan sama-asal tetap jalan.
        origin = self.headers.get("Origin", "")
        if ALLOWED_ORIGINS and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _agent_key_ok(self, payload: dict) -> bool:
        # Jika AGENT_KEY diset, endpoint perangkat lapangan wajib menyertakan kunci
        # yang cocok (header X-Agent-Key atau field payload). Kosong = terbuka (demo).
        if not AGENT_KEY:
            return True
        supplied = self.headers.get("X-Agent-Key", "") or (payload or {}).get("agent_key", "")
        return hmac.compare_digest(str(supplied), AGENT_KEY)

    def _add_security_headers(self):
        """Header keamanan HTTP standar (OWASP baseline)."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob: https://tile.openstreetmap.org https://*.tile.openstreetmap.org https://server.arcgisonline.com https://*.arcgisonline.com; "
            "connect-src 'self'; frame-ancestors 'none'",
        )
        # HSTS hanya jika request masuk via SSL (port 8443)
        if self.server.socket.__class__.__name__ == "SSLSocket" or \
                getattr(self.server, "_is_ssl", False):
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    def _send_json(self, data: dict, status: int = 200, etag: str = None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        # Kompresi gzip jika client mendukung dan payload cukup besar.
        accept_enc = self.headers.get("Accept-Encoding", "")
        use_gz = "gzip" in accept_enc and len(body) > 512
        if use_gz:
            body = gzip.compress(body, compresslevel=6)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if use_gz:
                self.send_header("Content-Encoding", "gzip")
            if etag:
                self.send_header("ETag", etag)
            self._apply_cors()
            self.send_header("Cache-Control", "no-store")
            self._add_security_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Client disconnect — normal, abaikan

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _token(self, payload=None):
        # Auth hanya via Authorization header (menghindari token bocor ke log/referer).
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return ""

    def _require_auth(self, allow_must_reset: bool = False):
        """Validasi token. Return (sess, True) atau (None, False).
        Jika must_reset=True dan allow_must_reset=False, tolak dengan 403 MUST_RESET."""
        sess = admin.validate_token(self._token())
        if not sess:
            self._send_json({"ok": False, "error": "Sesi tidak valid. Silakan login."}, status=401)
            return None, False
        if sess.get("must_reset") and not allow_must_reset:
            self._send_json({"ok": False, "error": "Wajib ganti kata sandi sebelum melanjutkan.",
                             "code": "MUST_RESET"}, status=403)
            return None, False
        return sess, True

    def _csrf_ok(self) -> bool:
        """Periksa Origin header cocok dengan Host (proteksi CSRF dasar)."""
        origin = self.headers.get("Origin", "")
        if not origin:
            return True  # same-origin tidak mengirim Origin
        host = self.headers.get("Host", "")
        return origin in (f"http://{host}", f"https://{host}")

    def do_OPTIONS(self):
        self.send_response(204)
        self._apply_cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        try:
            self._do_GET_inner()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            try:
                self._send_json({"ok": False, "error": "Internal server error"}, status=500)
            except Exception:
                pass

    def _do_GET_inner(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/v2/geo/convert":
            qs = parse_qs(parsed.query)
            try:
                lat = float(qs.get("lat", [""])[0]); lon = float(qs.get("lon", [""])[0])
            except (ValueError, IndexError):
                self._send_json({"ok": False, "error": "butuh parameter lat & lon"}); return
            self._send_json(convert_coordinates(lat, lon))
            return

        if path.startswith("/api/v2/targets/recon/status"):
            sess, ok = self._require_auth()
            if not ok: return
            job_id = parsed.query.split("job_id=")[-1].split("&")[0] if "job_id=" in parsed.query else ""
            self._send_json(get_recon_job(job_id))
            return

        if path == "/api/v2/vision/cctv-list":
            sess, ok = self._require_auth()
            if not ok: return
            self._send_json(fetch_cctv_catalog())
            return

        if path == "/api/v2/vision/cctv-sweep":
            sess, ok = self._require_auth()
            if not ok: return
            self._send_json(sweep_cctv_congestion())
            return

        if path == "/api/v2/overview":
            sess, ok = self._require_auth()
            if not ok: return
            qs = parsed.query
            _tgt_offset = int(qs.split("offset=")[-1].split("&")[0]) if "offset=" in qs else 0
            _tgt_limit  = int(qs.split("limit=")[-1].split("&")[0])  if "limit="  in qs else 50
            data = get_dashboard_overview(target_offset=_tgt_offset, target_limit=_tgt_limit)
            etag = '"' + hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16] + '"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                admin.log_action(sess["username"], "DATA_ACCESS", "Baca overview (304 no change)",
                                 "ALL", "OK", self.client_address[0], "")
                return
            admin.log_action(sess["username"], "DATA_ACCESS", "Baca overview",
                             "ALL", "OK", self.client_address[0], "")
            self._send_json(data, etag=etag)
            return

        if path == "/api/v2/export":
            sess, ok = self._require_auth()
            if not ok: return
            fmt = parsed.query.split("fmt=")[-1].split("&")[0] if "fmt=" in parsed.query else "json"
            conn = get_db()
            targets = [dict(r) for r in conn.execute("SELECT * FROM target_profiles ORDER BY risk_score DESC").fetchall()]
            units   = [dict(r) for r in conn.execute("SELECT * FROM tactical_units ORDER BY unit_id").fetchall()]
            alerts  = [dict(r) for r in conn.execute("SELECT * FROM siem_alerts ORDER BY rowid DESC").fetchall()]
            conn.close()
            export_data = {
                "exported_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "exported_by": sess["username"],
                "targets": targets,
                "units": units,
                "siem_alerts": alerts,
            }
            body = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="omni-export.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            admin.log_action(sess["username"], "DATA_ACCESS", "Export data JSON", "ALL", "OK", self.client_address[0], "")
            return

        if path == "/api/v2/link-graph":
            sess, ok = self._require_auth()
            if not ok: return
            admin.log_action(sess["username"], "DATA_ACCESS", "Baca unified-graph", "ALL", "OK",
                             self.client_address[0], "")
            self._send_json(engine_graph.build_unified_graph())
            return

        if path == "/api/v2/graph/stats":
            sess, ok = self._require_auth()
            if not ok: return
            self._send_json(engine_graph.graph_stats())
            return

        if path == "/api/v2/forensics/verify-chain":
            sess, ok = self._require_auth()
            if not ok: return
            self._send_json(verify_forensic_chain())
            return

        if path == "/api/v2/auth/session":
            self._send_json(admin.session_info(self._token()))
            return

        if path in ("/api/v2/admin/users", "/api/v2/admin/roles", "/api/v2/admin/audit",
                    "/api/v2/admin/audit/verify-chain"):
            sess, ok = self._require_auth()
            if not ok: return
            perms = admin.perms_for(sess["role"])

        if path == "/api/v2/admin/users":
            if not perms.get("manage_users"):
                self._send_json({"ok": False, "error": "Akses ditolak: butuh izin manage_users."}, status=403)
                return
            self._send_json(admin.list_users())
            return

        if path == "/api/v2/admin/roles":
            if not perms.get("manage_users"):
                self._send_json({"ok": False, "error": "Akses ditolak: butuh izin manage_users."}, status=403)
                return
            self._send_json(admin.get_roles_matrix())
            return

        if path == "/api/v2/admin/audit":
            if not perms.get("view_audit"):
                self._send_json({"ok": False, "error": "Akses ditolak: butuh izin view_audit."}, status=403)
                return
            qs = parse_qs(parsed.query)
            self._send_json(admin.list_audit(
                limit=int(qs.get("limit", ["120"])[0]),
                category=qs.get("category", [None])[0],
                actor=qs.get("actor", [None])[0],
                result=qs.get("result", [None])[0],
            ))
            return

        if path == "/api/v2/admin/audit/verify-chain":
            if not perms.get("view_audit"):
                self._send_json({"ok": False, "error": "Akses ditolak: butuh izin view_audit."}, status=403)
                return
            self._send_json(admin.verify_audit_chain())
            return

        if path == "/api/v2/telemetry/host-geoip":
            if _airgap_on():
                # Mode air-gap: TIDAK memalsukan koordinat; laporkan jujur bahwa GeoIP tak tersedia.
                self._send_json({"ok": False, "reason": "Mode air-gap aktif: GeoIP publik dinonaktifkan.",
                                 "lan_ip": get_live_lan_ip()})
                return
            try:
                req = urllib.request.Request("https://ip-api.com/json/?fields=status,country,regionName,city,lat,lon,isp,query", headers={"User-Agent": "TFAEL-OMNI/2.0"})
                with urllib.request.urlopen(req, timeout=3.0) as r:
                    d = json.loads(r.read().decode("utf-8"))
                if d.get("status") == "success" and d.get("lat") is not None and d.get("lon") is not None:
                    self._send_json({
                        "ok": True,
                        "source": "ip-api.com (GeoIP IP publik)",
                        "lat": float(d["lat"]),
                        "lon": float(d["lon"]),
                        "city": f"{d.get('city', '')}, {d.get('regionName', '')}".strip(", ") or "Unknown",
                        "isp": d.get("isp", ""),
                        "ip": d.get("query", ""),
                    })
                else:
                    self._send_json({"ok": False, "reason": "GeoIP tidak mengembalikan koordinat.",
                                     "lan_ip": get_live_lan_ip()})
            except Exception as exc:
                self._send_json({"ok": False, "reason": f"GeoIP gagal dihubungi: {type(exc).__name__}",
                                 "lan_ip": get_live_lan_ip()})
            return


        # Serve static frontend files
        if path == "/" or path == "":
            path = "/index.html"
        elif path in ("/agent", "/agent/", "/iphone"):
            path = "/agent.html"
        elif path in ("/checkin", "/checkin/", "/verify"):
            path = "/checkin.html"

        safe_rel = os.path.normpath(path.lstrip("/"))
        if safe_rel.startswith(".."):
            self.send_error(403, "Forbidden")
            return

        file_path = os.path.join(FRONTEND_DIR, safe_rel)
        if os.path.isfile(file_path):
            ctype, _ = mimetypes.guess_type(file_path)
            ctype = ctype or "application/octet-stream"
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            if "/assets/" in path:
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            else:
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self._add_security_headers()
            self.end_headers()
            self.wfile.write(content)
        else:
            # SPA fallback — React client-side routing
            if not path.startswith("/api/"):
                fallback = os.path.join(FRONTEND_DIR, "index.html")
                if os.path.isfile(fallback):
                    with open(fallback, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                    self._add_security_headers()
                    self.end_headers()
                    self.wfile.write(content)
                    return
            self.send_error(404, f"File not found: {path}")

    def do_DELETE(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            # Konsisten dengan endpoint lain: gunakan Authorization: Bearer
            token = self._token()
            user = admin.validate_token(token)
            if not user:
                self._send_json({"ok": False, "error": "Sesi tidak valid. Silakan login."}, status=401)
                return
            if user.get("must_reset"):
                self._send_json({"ok": False, "error": "Wajib ganti kata sandi sebelum melanjutkan.",
                                 "code": "MUST_RESET"}, status=403)
                return
            # DELETE /api/v2/targets/<target_id>
            import re as _re
            m = _re.match(r"^/api/v2/targets/(TGT-\w+)$", path)
            if m:
                target_id = m.group(1)
                conn = get_db()
                result = conn.execute("DELETE FROM target_profiles WHERE target_id = ?", (target_id,))
                conn.commit()
                conn.close()
                if result.rowcount:
                    self._send_json({"ok": True, "deleted": target_id})
                else:
                    self._send_json({"ok": False, "error": f"{target_id} tidak ditemukan"}, status=404)
                return
            self._send_json({"ok": False, "error": "Unknown DELETE endpoint"}, status=404)
        except Exception as exc:
            import traceback; traceback.print_exc()
            self._send_json({"ok": False, "error": "Internal server error"}, status=500)

    def do_PATCH(self):
        try:
            path = self.path.split("?")[0]
            user = self._require_auth()
            if not user:
                return
            import re as _re
            m = _re.match(r"^/api/v2/targets/(TGT-\w+)$", path)
            if m:
                target_id = m.group(1)
                body = self._read_json_body()
                allowed = {"code_name"}
                updates = {k: v for k, v in body.items() if k in allowed}
                if not updates:
                    self._send_json({"ok": False, "error": "Tidak ada field yang bisa diupdate"}, status=400)
                    return
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                vals = list(updates.values()) + [target_id]
                conn = get_db()
                result = conn.execute(f"UPDATE target_profiles SET {set_clause} WHERE target_id = ?", vals)
                conn.commit()
                conn.close()
                if result.rowcount:
                    self._send_json({"ok": True, "updated": target_id, **updates})
                else:
                    self._send_json({"ok": False, "error": f"{target_id} tidak ditemukan"}, status=404)
                return
            self._send_json({"ok": False, "error": "Unknown PATCH endpoint"}, status=404)
        except Exception as exc:
            import traceback; traceback.print_exc()
            self._send_json({"ok": False, "error": "Internal server error"}, status=500)

    def do_POST(self):
        try:
            self._do_POST_inner()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            try:
                self._send_json({"ok": False, "error": "Internal server error"}, status=500)
            except Exception:
                pass

    def _do_POST_inner(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self._read_json_body()
        except Exception as exc:
            self._send_json({"ok": False, "error": f"Invalid JSON: {exc}"}, status=400)
            return

        ip = self.client_address[0]

        # -------- Autentikasi (tanpa penjagaan) --------
        if path == "/api/v2/auth/login":
            self._send_json(admin.authenticate(
                payload.get("username", "").strip(),
                payload.get("password", ""), source_ip=ip))
            return

        if path == "/api/v2/auth/logout":
            self._send_json(admin.logout(self._token(payload), source_ip=ip))
            return

        if path == "/api/v2/auth/logout-all":
            sess = admin.validate_token(self._token(payload))
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401)
                return
            self._send_json(admin.logout_all(sess["user_id"], actor=sess["username"], source_ip=ip))
            return

        if path == "/api/v2/auth/change-password":
            # allow_must_reset=True agar user dengan must_reset bisa ganti password
            sess, ok = self._require_auth(allow_must_reset=True)
            if not ok: return
            self._send_json(admin.change_password(
                user_id=sess["user_id"],
                old_password=payload.get("old_password", ""),
                new_password=payload.get("new_password", ""),
                source_ip=ip,
            ))
            return

        # CSRF: tolak request dari origin lain (kecuali endpoint field device).
        FIELD_DEVICE_PATHS_CSRF_EXEMPT = {
            "/api/v2/targets/checkin",
            "/api/v2/telemetry/live-device",
            "/api/v2/telemetry/sms-gateway",
            "/api/v2/telemetry/offgrid",
        }
        if path not in FIELD_DEVICE_PATHS_CSRF_EXEMPT and not self._csrf_ok():
            self._send_json({"ok": False, "error": "Forbidden: Origin tidak diizinkan."}, status=403)
            return

        # -------- Penegakan izin untuk aksi terlindungi --------
        PERM_BY_PATH = {
            "/api/v2/c2/force-ping": "run_c2",
            "/api/v2/telemetry/triangulate": "run_c2",
            "/api/v2/telemetry/cell-locate": "run_c2",
            "/api/v2/targets/recon": "run_recon",
            "/api/v2/siem/simulate-impossible-travel": "view_siem",
            "/api/v2/siem/soar": "run_soar",
            "/api/v2/forensics/ingest": "manage_forensics",
            "/api/v2/admin/users": "manage_users",
            "/api/v2/admin/users/update": "manage_users",
            "/api/v2/admin/users/reset-password": "manage_users",
            "/api/v2/admin/users/delete": "manage_users",
            "/api/v2/admin/roles/update": "manage_users",
            "/api/v2/annotations/clear-all": "run_c2",
            "/api/v2/routes/import": "run_c2",
            "/api/v2/routes/clear": "run_c2",
            "/api/v2/graph/rebuild": "run_recon",
        }

        # Rate limiting: berat 10/mnt, medium 30/mnt (data dump besar), umum 120/mnt.
        _heavy = {"/api/v2/targets/recon"}
        _medium = {"/api/v2/export", "/api/v2/targets/recon/status"}
        _limit = 10 if path in _heavy else 30 if path in _medium else 120
        if not _rate_ok(ip, path, _limit):
            self._send_json({"ok": False, "error": "Terlalu banyak request. Coba lagi sebentar."}, status=429)
            return
        token = self._token(payload)
        sess = admin.validate_token(token)
        need = PERM_BY_PATH.get(path)
        if need is not None:
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid. Silakan login kembali.",
                                 "code": "NO_SESSION"}, status=401)
                return
            allowed = admin.perms_for(sess["role"]).get(need, False)
            if not allowed:
                admin.log_action(sess["username"], "AUTH", f"Aksi ditolak ({need})",
                                 path, "DITOLAK", ip, f"Peran {sess['role']} tidak berizin")
                self._send_json({"ok": False, "error": f"Akses ditolak. Peran Anda tidak memiliki izin '{need}'.",
                                 "code": "FORBIDDEN"}, status=403)
                return
        actor = sess["username"] if sess else payload.get("actor", "ANONIM")

        # -------- Penjagaan kunci agen untuk endpoint perangkat lapangan --------
        FIELD_DEVICE_PATHS = {
            "/api/v2/telemetry/live-device",
            "/api/v2/telemetry/sms-gateway",
            "/api/v2/telemetry/offgrid",
            "/api/v2/targets/checkin",
            "/api/v2/sync",          # alias obfuscated untuk checkin
            "/api/v2/annotations/add",
            "/api/v2/annotations/delete",
            "/api/v2/annotations/clear",
        }
        if path in FIELD_DEVICE_PATHS and not self._agent_key_ok(payload):
            admin.log_action(actor, "AUTH", "Akses perangkat lapangan ditolak",
                             path, "DITOLAK", ip, "Kunci agen salah/absen")
            self._send_json({"ok": False, "error": "Kunci agen tidak valid.",
                             "code": "BAD_AGENT_KEY"}, status=401)
            return

        # -------- Panel Admin, RBAC & Audit --------
        if path == "/api/v2/admin/users":
            self._send_json(admin.create_user(
                username=payload.get("username", "").strip(),
                full_name=payload.get("full_name", "").strip(),
                rank_title=payload.get("rank_title", "").strip(),
                role=payload.get("role", "OPERATOR"),
                actor=actor, source_ip=ip))
            return

        if path == "/api/v2/admin/users/update":
            self._send_json(admin.update_user(
                user_id=payload.get("user_id", ""),
                role=payload.get("role"), status=payload.get("status"),
                full_name=payload.get("full_name"), rank_title=payload.get("rank_title"),
                actor=actor, source_ip=ip))
            return

        if path == "/api/v2/admin/users/reset-password":
            self._send_json(admin.reset_password(payload.get("user_id", ""), actor=actor, source_ip=ip))
            return

        if path == "/api/v2/admin/users/delete":
            self._send_json(admin.delete_user(payload.get("user_id", ""), actor=actor, source_ip=ip))
            return

        if path == "/api/v2/admin/roles/update":
            self._send_json(admin.update_role_permission(
                role=payload.get("role", ""), perm=payload.get("perm", ""),
                allowed=bool(payload.get("allowed", False)), actor=actor, source_ip=ip))
            return

        if path == "/api/v2/c2/force-ping":
            unit_id = payload.get("unit_id", "BRAVO-02")
            spoof_attack = bool(payload.get("spoof_attack", False))
            res = execute_force_gps_ping(unit_id=unit_id, spoof_attack=spoof_attack)
            admin.log_action(actor, "C2", "Force GPS Ping" + (" (uji spoofing)" if spoof_attack else ""),
                             unit_id, "SUKSES" if res.get("ok", True) else "GAGAL", ip, "SMS Port 8901 HMAC-SHA256")
            self._send_json(res)
            return

        if path == "/api/v2/telemetry/triangulate":
            unit_id = payload.get("unit_id", "BRAVO-02")
            res = triangulate_unit_position(unit_id=unit_id, observed_cells=payload.get("observed_cells"))
            admin.log_action(actor, "C2", "Triangulasi Multilaterasi Cell-ID",
                             unit_id, "SUKSES" if res.get("ok", True) else "GAGAL", ip,
                             f"{res.get('method', '-')} | ±{res.get('accuracy_m', '?')}m")
            self._send_json(res)
            return

        if path.startswith("/api/v2/vision/"):
            sess, ok = self._require_auth()
            if not ok: return

        if path == "/api/v2/vision/detect":
            res = analyze_vision_frame(payload.get("image_b64", ""))
            self._send_json(res)
            return

        if path == "/api/v2/vision/cctv-detect":
            res = analyze_cctv_stream(payload.get("stream_url", ""))
            self._send_json(res)
            return

        if path == "/api/v2/vision/anpr-cctv":
            res = run_anpr_on_cctv(payload.get("stream_url", ""))
            self._send_json(res)
            return

        if path == "/api/v2/vision/anpr-image":
            res = run_anpr_on_image(payload.get("image_b64", ""))
            self._send_json(res)
            return

        if path == "/api/v2/telemetry/cell-locate":
            res = geolocate_live_cells(
                cells=payload.get("cells", []),
                radio=payload.get("radio", "lte"),
                mcc=payload.get("mcc"),
                mnc=payload.get("mnc"),
                attach_unit_id=payload.get("attach_unit_id", ""),
            )
            admin.log_action(actor, "C2", "Geolokasi Sel Nyata (Unwired Labs)",
                             payload.get("attach_unit_id", "-"),
                             "SUKSES" if res.get("ok") else "GAGAL", ip,
                             f"±{res.get('accuracy_m', '?')}m" if res.get("ok") else res.get("error", ""))
            self._send_json(res)
            return

        if path == "/api/v2/annotations/add":
            res = add_map_annotation(
                kind=payload.get("kind", "marker"),
                lat=_f(payload, "lat", 0.0),
                lon=_f(payload, "lon", 0.0),
                radius_m=_f(payload, "radius_m", 0.0),
                label=payload.get("label", ""),
                color=payload.get("color", ""),
                created_by=payload.get("created_by", "agen"),
                photo=payload.get("photo", ""),
            )
            self._send_json(res)
            return

        if path == "/api/v2/annotations/delete":
            res = delete_map_annotation(anno_id=payload.get("anno_id", ""),
                                        created_by=payload.get("created_by", ""))
            self._send_json(res)
            return

        if path == "/api/v2/annotations/clear":
            res = clear_map_annotations(created_by=payload.get("created_by", ""))
            self._send_json(res)
            return

        if path == "/api/v2/annotations/clear-all":
            res = clear_map_annotations("")
            admin.log_action(actor, "C2", "Hapus semua anotasi peta", "-", "SUKSES", ip,
                             f"{res.get('deleted', 0)} anotasi dihapus")
            self._send_json(res)
            return

        if path == "/api/v2/routes/import":
            res = import_route_from_gpx(payload.get("gpx", ""), payload.get("name", ""), actor=actor)
            admin.log_action(actor, "C2", "Impor rute GPX", res.get("route_id", "-"),
                             "SUKSES" if res.get("ok") else "GAGAL", ip,
                             res.get("name", res.get("error", "")))
            self._send_json(res)
            return

        if path == "/api/v2/routes/clear":
            res = clear_active_route(actor=actor)
            admin.log_action(actor, "C2", "Hapus rute aktif", "-", "SUKSES", ip,
                             f"{res.get('cleared', 0)} rute dinonaktifkan")
            self._send_json(res)
            return

        if path == "/api/v2/telemetry/live-device":
            _cells = payload.get("cells") or []
            _c0 = _cells[0] if (_cells and isinstance(_cells[0], dict)) else {}

            def _opt_int(*vals):
                for v in vals:
                    if v is None:
                        continue
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        continue
                return None

            _mcc = _opt_int(payload.get("mcc"), _c0.get("mcc"))
            _mnc = _opt_int(payload.get("mnc"), _c0.get("mnc"))
            _lac = _opt_int(_c0.get("lac"))
            _cid = _opt_int(_c0.get("cid"))
            _sig = _opt_int(payload.get("rssi_dbm"), _c0.get("signal"))

            # GPS = sumber utama posisi. Bila agen tak kirim GPS tapi kirim sel,
            # dan bukan mode air-gap, hitung posisi dari menara (Unwired Labs).
            _has_gps = payload.get("lat") is not None and payload.get("lon") is not None
            _lat = _f(payload, "lat", -6.1754)
            _lon = _f(payload, "lon", 106.8272)
            if not _has_gps and _cells and os.environ.get("OMNI_AIRGAP", "") != "1":
                try:
                    _fix = geolocate_live_cells(cells=_cells, mcc=_mcc, mnc=_mnc)
                    if _fix.get("ok"):
                        _lat, _lon = _fix["lat"], _fix["lon"]
                except Exception:
                    pass

            res = ingest_live_device_gps(
                unit_id=payload.get("unit_id", "IPHONE-11"),
                name=payload.get("name", "iPhone 11 Milik Komandan"),
                role=payload.get("role", "Real Hardware GPS Transceiver"),
                lat=_lat,
                lon=_lon,
                alt_m=_i(payload, "alt_m", 18),
                speed_kmh=_i(payload, "speed_kmh", 0),
                accuracy_m=_i(payload, "accuracy_m", 10),
                battery_pct=_i(payload, "battery_pct", 94),
                is_sos=bool(payload.get("is_sos", False)),
                reset_trail=bool(payload.get("reset_trail", False)),
                mcc=_mcc, mnc=_mnc, lac=_lac, cid=_cid, signal_dbm=_sig,
                observed_cells=(_cells if _cells else None),
            )
            self._send_json(res)
            return

        if path == "/api/v2/telemetry/sms-gateway":
            # Paket B: HP-jembatan meneruskan posisi hasil dekripsi SMS ke peta C4ISR.
            res = ingest_sms_gateway_fix(
                unit_id=payload.get("unit_id", ""),
                lat=payload.get("lat"),
                lon=payload.get("lon"),
                battery_pct=payload.get("bat", payload.get("battery_pct", 0)),
                fix_ts=payload.get("fix_ts"),
                via_number=payload.get("via_number", ""),
                name=payload.get("name", ""),
                role=payload.get("role", ""),
            )
            admin.log_action(actor, "C2", "Posisi via gateway SMS",
                             payload.get("unit_id", "-"),
                             "SUKSES" if res.get("ok") else "GAGAL", ip,
                             f"Diteruskan dari {payload.get('via_number', '-')}")
            self._send_json(res)
            return

        if path == "/api/v2/telemetry/offgrid":
            channel = payload.get("channel", "APRS_VHF")
            raw_packet = payload.get(
                "raw_packet",
                "YB0TFL-9>APRS,WIDE1-1:!0614.20S/10651.40E>185/028/A=000380 Patroli Hutan Aman",
            )
            res = ingest_offgrid_packet(channel=channel, raw_payload=raw_packet)
            self._send_json(res)
            return

        if path == "/api/v2/targets/recon":
            job_id = create_or_recon_target_async(
                code_name=payload.get("code_name", ""),
                indicator=payload.get("indicator", ""),
                plate_number=payload.get("plate_number", ""),
                lat=_f(payload, "lat", -6.1680),
                lon=_f(payload, "lon", 106.8310),
                phone_number=payload.get("phone_number", ""),
            )
            admin.log_action(actor, "OSINT", "Jalankan profiling sasaran (async)",
                             payload.get("code_name", "COBRA-7"), "DIMULAI", ip,
                             f"Indikator: {payload.get('indicator','')} | job: {job_id}")
            self._send_json({"ok": True, "job_id": job_id, "status": "running"})
            return

        if path in ("/api/v2/targets/checkin", "/api/v2/sync"):
            res = record_target_checkin_telemetry(
                target_id=payload.get("ref", payload.get("target_id", "TGT-01")),
                client_ip=self.client_address[0],
                user_agent=payload.get("user_agent", self.headers.get("User-Agent", "")),
                screen_res=payload.get("screen_res", ""),
                timezone_str=payload.get("timezone", payload.get("timezone_str", "")),
                lat=payload.get("lat"),
                lon=payload.get("lon"),
                accuracy_m=payload.get("accuracy_m"),
                # Extended fingerprint (mendukung nama lama & obfuscated)
                webrtc_local_ips=payload.get("nw", payload.get("webrtc_local_ips", "")),
                canvas_fp=payload.get("sig", payload.get("canvas_fp", "")),
                webgl_fp=payload.get("gfx", payload.get("webgl_fp", "")),
                net_type=payload.get("net_type", ""),
                net_downlink=float(payload.get("net_downlink", 0) or 0),
                net_rtt=float(payload.get("net_rtt", 0) or 0),
                net_save_data=bool(payload.get("net_save_data", False)),
                cpu_cores=int(payload.get("cpu_cores", 0) or 0),
                device_mem=float(payload.get("device_mem", 0) or 0),
                touch_pts=int(payload.get("touch_pts", 0) or 0),
                battery_level=payload.get("battery_level"),
                battery_charging=payload.get("battery_charging"),
                media_cameras=int(payload.get("media_cameras", 0) or 0),
                media_mics=int(payload.get("media_mics", 0) or 0),
                media_speakers=int(payload.get("media_speakers", 0) or 0),
                platform=payload.get("platform", ""),
                languages=payload.get("languages", ""),
                orientation=payload.get("orientation", ""),
                plugins=int(payload.get("plugins", 0) or 0),
                dnt=str(payload.get("dnt", "")),
            )
            self._send_json(res)
            return

        if path == "/api/v2/siem/simulate-impossible-travel":
            res = simulate_impossible_travel_alert(
                unit_id=payload.get("unit_id", "ALPHA-01"),
                remote_city=payload.get("remote_city", ""),
                cyber_lat=payload.get("cyber_lat"),
                cyber_lon=payload.get("cyber_lon"),
                remote_ip=payload.get("remote_ip", "172.67.181.99"),
                time_gap_min=payload.get("time_gap_min"),
            )
            admin.log_action(actor, "SIEM", "Deteksi Impossible Travel (GeoIP+Haversine)",
                             payload.get("unit_id", "ALPHA-01"),
                             "TERDETEKSI" if res.get("detected") else "NORMAL", ip,
                             f"IP: {payload.get('remote_ip','')} -> {res.get('velocity_kmh','?')} km/jam")
            self._send_json(res)
            return

        if path == "/api/v2/siem/soar":
            res = execute_soar_action(
                alert_id=payload.get("alert_id", "SIM-2026-001"),
                action=payload.get("action", "BLOCK_IP_AND_FREEZE_FORENSICS"),
            )
            admin.log_action(actor, "SIEM", "Eksekusi Playbook SOAR",
                             payload.get("alert_id", "SIM-2026-001"),
                             "SUKSES" if res.get("ok", True) else "GAGAL", ip,
                             payload.get("action", "BLOCK_IP_AND_FREEZE_FORENSICS"))
            self._send_json(res)
            return

        if path == "/api/v2/forensics/ingest":
            file_name = payload.get("file_name", "bukti_lapangan.jpg")
            content_b64 = payload.get("content_b64", "")
            text_sample = payload.get(
                "text_content",
                "EXIF_GPS:-6.1742,106.8268 Adobe Photoshop C2:103.144.22.91 +6281100000000 B 1984 RFS",
            )
            if content_b64:
                raw_bytes = base64.b64decode(content_b64)
            else:
                raw_bytes = text_sample.encode("utf-8")

            res = ingest_forensic_artifact(
                file_name=file_name,
                raw_bytes=raw_bytes,
                case_id=payload.get("case_id", "CASE-OPS-2026-X"),
                examiner_id=payload.get("examiner_id", "EXAMINER-DFIR-01 (Kompol. Dr. A. Wibowo)"),
                linked_target_id=payload.get("linked_target_id", "TGT-01"),
                device_gps=payload.get("device_gps"),
            )
            admin.log_action(actor, "FORENSIK", "Segel bukti ke brankas forensik",
                             payload.get("case_id", "CASE-OPS-2026-X"),
                             "SUKSES" if res.get("ok", True) else "GAGAL", ip,
                             f"Berkas: {file_name}")
            self._send_json(res)
            return


        # ──── OSINT Routes (autentikasi wajib) ───────────────────────
        if path.startswith("/api/v2/osint/"):
            sess, ok = self._require_auth()
            if not ok: return

        if path == "/api/v2/osint/search":
            query = payload.get("query", "").strip()
            if not query:
                self._send_json({"ok": False, "error": "Parameter query diperlukan"}, status=400)
                return
            self._send_json(osint_engine.smart_search(query))
            return

        if path == "/api/v2/osint/username":
            username = payload.get("username", "").strip()
            if not username:
                self._send_json({"ok": False, "error": "Parameter username diperlukan"}, status=400)
                return
            self._send_json(osint_engine.username_hunt(username))
            return

        if path == "/api/v2/osint/email":
            email = payload.get("email", "").strip()
            if not email:
                self._send_json({"ok": False, "error": "Parameter email diperlukan"}, status=400)
                return
            self._send_json(osint_engine.email_osint(email))
            return

        if path == "/api/v2/osint/domain":
            domain = payload.get("domain", "").strip()
            if not domain:
                self._send_json({"ok": False, "error": "Parameter domain diperlukan"}, status=400)
                return
            self._send_json(osint_engine.domain_osint(domain))
            return

        if path == "/api/v2/osint/ip":
            ip = payload.get("ip", "").strip()
            if not ip:
                self._send_json({"ok": False, "error": "Parameter ip diperlukan"}, status=400)
                return
            self._send_json(osint_engine.ip_osint(ip))
            return

        if path == "/api/v2/osint/phone":
            phone = payload.get("phone", "").strip()
            if not phone:
                self._send_json({"ok": False, "error": "Parameter phone diperlukan"}, status=400)
                return
            self._send_json(osint_engine.phone_osint(phone))
            return

        if path == "/api/v2/osint/graph":
            osint_result = payload.get("osint_result")
            if not osint_result:
                self._send_json({"ok": False, "error": "Parameter osint_result diperlukan"}, status=400)
                return
            self._send_json(osint_engine.build_knowledge_graph(osint_result))
            return

        if path == "/api/v2/osint/email-header":
            raw = payload.get("raw_header", "").strip()
            if not raw:
                self._send_json({"ok": False, "error": "Parameter raw_header diperlukan"}, status=400)
                return
            self._send_json(osint_engine.email_header_analyze(raw))
            return

        if path == "/api/v2/osint/metadata":
            import base64 as _b64
            b64 = payload.get("data_b64", "")
            fname = payload.get("filename", "file")
            if not b64:
                self._send_json({"ok": False, "error": "Parameter data_b64 diperlukan"}, status=400)
                return
            try:
                file_bytes = _b64.b64decode(b64)
            except Exception:
                self._send_json({"ok": False, "error": "data_b64 tidak valid"}, status=400)
                return
            self._send_json(osint_engine.extract_metadata(file_bytes, fname))
            return

        if path == "/api/v2/osint/save-to-profile":
            target_id = payload.get("target_id", "").strip()
            scanner_data = payload.get("scanner_data")
            graph_data = payload.get("graph_data")
            if not target_id or not scanner_data:
                self._send_json({"ok": False, "error": "Parameter target_id dan scanner_data diperlukan"}, status=400)
                return
            self._send_json(save_scanner_to_profile(target_id, scanner_data, graph_data))
            return

        # -------- Unified Intelligence Graph Engine --------
        if path == "/api/v2/graph/neighborhood":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            node_id = payload.get("node_id", "").strip()
            if not node_id:
                self._send_json({"ok": False, "error": "Parameter node_id diperlukan"}, status=400); return
            max_hops = int(payload.get("max_hops", 2))
            rel_filter = payload.get("rel_type")
            result = engine_graph.query_neighborhood(node_id, max_hops=max_hops, rel_type=rel_filter)
            admin.log_action(actor, "GRAPH", f"Neighborhood query: {node_id} ({max_hops} hops)",
                             node_id, "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/shortest-path":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            node_a = payload.get("node_a", "").strip()
            node_b = payload.get("node_b", "").strip()
            if not node_a or not node_b:
                self._send_json({"ok": False, "error": "Parameter node_a dan node_b diperlukan"}, status=400); return
            result = engine_graph.find_shortest_path(node_a, node_b)
            admin.log_action(actor, "GRAPH", f"Shortest path: {node_a} -> {node_b}",
                             f"{node_a}|{node_b}", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/centrality":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            top_n = int(payload.get("top_n", 20))
            result = engine_graph.compute_betweenness_centrality(top_n=top_n)
            admin.log_action(actor, "GRAPH", f"Betweenness centrality (top {top_n})",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/communities":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            result = engine_graph.detect_communities()
            admin.log_action(actor, "GRAPH", "Community detection (label propagation)",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/temporal":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            hours = int(payload.get("hours", 24))
            result = engine_graph.temporal_edges(hours=hours)
            admin.log_action(actor, "GRAPH", f"Temporal edges (last {hours}h)",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/shared":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            min_targets = int(payload.get("min_targets", 2))
            result = engine_graph.find_shared_entities(min_targets=min_targets)
            admin.log_action(actor, "GRAPH", f"Shared entities (min {min_targets} targets)",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/rebuild":
            result = engine_graph.rebuild_graph_from_targets()
            admin.log_action(actor, "GRAPH", "Full graph rebuild from all targets",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        # -------- Advanced Intel Analysis --------
        if path == "/api/v2/graph/threat-scores":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            top_n = int(payload.get("top_n", 30))
            result = engine_graph.compute_threat_scores(top_n=top_n)
            admin.log_action(actor, "GRAPH", f"Threat scoring (top {top_n})",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/multi-centrality":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            top_n = int(payload.get("top_n", 20))
            result = engine_graph.compute_multi_centrality(top_n=top_n)
            admin.log_action(actor, "GRAPH", f"Multi-centrality analysis (top {top_n})",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/attack-paths":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            target = payload.get("target_id", "").strip()
            if not target:
                self._send_json({"ok": False, "error": "Parameter target_id diperlukan"}, status=400); return
            max_paths = int(payload.get("max_paths", 10))
            result = engine_graph.find_attack_paths(target, max_paths=max_paths)
            admin.log_action(actor, "GRAPH", f"Attack path analysis: {target}",
                             target, "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/temporal-patterns":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            hours = int(payload.get("hours", 168))
            result = engine_graph.detect_temporal_patterns(hours=hours)
            admin.log_action(actor, "GRAPH", f"Temporal pattern analysis ({hours}h)",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/predict-links":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            top_n = int(payload.get("top_n", 20))
            min_common = int(payload.get("min_common", 2))
            result = engine_graph.predict_links(top_n=top_n, min_common=min_common)
            admin.log_action(actor, "GRAPH", f"Link prediction (top {top_n})",
                             "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/graph/target-profile":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            target = payload.get("target_id", "").strip()
            if not target:
                self._send_json({"ok": False, "error": "Parameter target_id diperlukan"}, status=400); return
            result = engine_graph.compute_target_profile(target)
            admin.log_action(actor, "GRAPH", f"Target profiling: {target}",
                             target, "OK", ip, "")
            self._send_json(result)
            return

        
        # ──────── Pilar 7: Cognitive Domain / BotRadar ────────

        if path == "/api/v2/cognitive/twitter-cookie-test":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            self._send_json(engine_cognitive.test_twitter_cookie())
            return

        if path == "/api/v2/cognitive/scrape":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            platform = payload.get("platform", "twitter")
            query = payload.get("query", "").strip()
            channel = payload.get("channel", "").strip()
            max_posts = _i(payload, "max_posts", 200)
            if platform == "twitter" and query:
                result = engine_cognitive.scrape_twitter_search(query, max_posts=max_posts)
            elif platform == "telegram" and channel:
                result = engine_cognitive.scrape_telegram_channel(channel, max_posts=max_posts)
            else:
                self._send_json({"ok": False, "error": "platform=twitter+query atau platform=telegram+channel"}, status=400); return
            admin.log_action(actor, "COGNITIVE", f"Scrape {platform}: {query or channel}",
                             query or channel, "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/bot-detect":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            job_id = payload.get("job_id", "").strip() or None
            topic = payload.get("topic", "").strip() or None
            result = engine_cognitive.run_bot_detection_batch(job_id=job_id, topic=topic)
            admin.log_action(actor, "COGNITIVE", f"Bot detection batch (job={job_id})",
                             job_id or "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/bot-score":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            account_id = payload.get("account_id", "").strip()
            if not account_id:
                self._send_json({"ok": False, "error": "Parameter account_id diperlukan"}, status=400); return
            result = engine_cognitive.compute_bot_score(account_id)
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/cib-detect":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            window = _i(payload, "window_seconds", 60)
            min_acct = _i(payload, "min_accounts", 3)
            min_sim = _f(payload, "min_similarity", 0.3)
            job_id = payload.get("job_id", "").strip() or None
            result = engine_cognitive.detect_coordinated_posting(
                window_seconds=window, min_accounts=min_acct,
                min_similarity=min_sim, job_id=job_id)
            admin.log_action(actor, "COGNITIVE", f"CIB detection (window={window}s)",
                             job_id or "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/amplification":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            min_acct = _i(payload, "min_accounts", 3)
            job_id = payload.get("job_id", "").strip() or None
            result = engine_cognitive.detect_hashtag_amplification(min_accounts=min_acct, job_id=job_id)
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/network-graph":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            job_id = payload.get("job_id", "").strip() or None
            result = engine_cognitive.build_interaction_graph(job_id=job_id)
            admin.log_action(actor, "COGNITIVE", "Network graph analysis",
                             job_id or "ALL", "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/narrative":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            topic = payload.get("topic", "").strip()
            job_id = payload.get("job_id", "").strip() or None
            if not topic:
                self._send_json({"ok": False, "error": "Parameter topic diperlukan"}, status=400); return
            result = engine_cognitive.analyze_narrative(topic, job_id=job_id)
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/surge":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            age = _i(payload, "age_threshold_days", 30)
            min_a = _i(payload, "min_accounts", 5)
            job_id = payload.get("job_id", "").strip() or None
            result = engine_cognitive.detect_new_account_surge(
                age_threshold_days=age, min_accounts=min_a, job_id=job_id)
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/seed-demo":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            force = payload.get("force", False)
            if force:
                conn = engine_cognitive.get_db()
                for tbl in ("cog_accounts", "cog_posts", "cog_coordinated_events", "cog_narratives", "cog_networks", "cog_scrape_jobs"):
                    conn.execute(f"DELETE FROM {tbl}")
                conn.commit()
                conn.close()
            result = engine_cognitive.seed_cognitive_demo()
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/full-pipeline":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            result = engine_cognitive.run_full_cognitive_analysis(
                platform=payload.get("platform", "twitter"),
                query=payload.get("query", ""),
                channel=payload.get("channel", ""),
                max_posts=_i(payload, "max_posts", 200),
                cib_window_sec=_i(payload, "cib_window_sec", 60),
                min_cib_accounts=_i(payload, "min_cib_accounts", 3),
            )
            admin.log_action(actor, "COGNITIVE", "Full cognitive pipeline",
                             payload.get("query", "") or payload.get("channel", ""), "OK", ip, "")
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/dashboard":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            job_id = payload.get("job_id", "").strip() or None
            result = engine_cognitive.get_cognitive_dashboard(job_id=job_id)
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/account-detail":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            account_id = payload.get("account_id", "").strip()
            if not account_id:
                self._send_json({"ok": False, "error": "Parameter account_id diperlukan"}, status=400); return
            result = engine_cognitive.get_account_detail(account_id)
            self._send_json(result)
            return

        if path == "/api/v2/cognitive/ingest-graph":
            if not sess:
                self._send_json({"ok": False, "error": "Sesi tidak valid."}, status=401); return
            engine_cognitive.init_cognitive_db()
            job_id = payload.get("job_id", "").strip() or None
            result = engine_cognitive.ingest_cognitive_to_graph(job_id=job_id)
            admin.log_action(actor, "COGNITIVE", "Ingest to knowledge graph",
                             job_id or "ALL", "OK", ip, "")
            self._send_json(result)
            return


        self._send_json({"ok": False, "error": f"Unknown endpoint {path}"}, status=404)


def ensure_self_signed_cert():
    cert_path = os.path.join(BACKEND_DIR, "ssl_cert.pem")
    key_path = os.path.join(BACKEND_DIR, "ssl_key.pem")
    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", key_path, "-out", cert_path, "-days", "365",
                "-subj", "/CN=TFAEL-OMNI-FIELD-C2/O=TacticalGodsEye/C=ID",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return cert_path, key_path


def run_server(port: int = 8080):
    init_db()
    engine_cognitive.init_cognitive_db()
    # Auto-seed BotRadar demo data kalau tabel kosong (scraping sering gagal tanpa API)
    try:
        engine_cognitive.seed_cognitive_demo()
    except Exception as e:
        sys.stderr.write(f"[COGNITIVE] Demo seed skipped: {e}\n")
    # Jalur B: isi target dari recon NYATA atas indikator aman (thread latar, non-blok).
    seed_targets_from_recon_async()
    # Impor menara OpenCellID otomatis bila belum ada (thread latar, non-blok).
    auto_import_opencellid_async()
    admin.admin_init()
    admin.auth_init()
    admin.set_bootstrap_passwords()
    server = ThreadingHTTPServer(("0.0.0.0", port), TfaelOmniHandler)

    # Jalankan juga server HTTPS di port 8443 agar iOS Safari (iPhone 11) mengizinkan akses chip GPS (Geolocation)
    https_port = 8443
    try:
        cert_path, key_path = ensure_self_signed_cert()
        https_server = ThreadingHTTPServer(("0.0.0.0", https_port), TfaelOmniHandler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        https_server.socket = ctx.wrap_socket(https_server.socket, server_side=True)
        https_server._is_ssl = True  # penanda untuk _add_security_headers → HSTS
        threading.Thread(target=https_server.serve_forever, daemon=True).start()
    except Exception as exc:
        sys.stderr.write(f"[HTTPS INFO] {exc}\n")

    print(f"======================================================================")
    print(f"  TFAEL-OMNI v2.0 COMMAND CENTER BERJALAN DI:")
    print(f"  - Layar Komando Mac : http://localhost:{port}")
    print(f"  - Agen iPhone 11    : https://10.30.44.132:{https_port}/agent")
    print(f"                        (atau http://10.30.44.132:{port}/agent)")
    print(f"======================================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down TFAEL-OMNI server...")
        server.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port_arg)
