#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Modul Panel Admin, RBAC, & Audit Log
Manajemen pengguna, peran (role-based access control), dan jejak audit aktivitas.
Berjalan 100% On-Premise di atas SQLite yang sama dengan mesin inti (engines.py).
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "tfael_omni.db")

# ------------------------------------------------------------------
# Katalog peran & izin (RBAC). Baris = peran, kolom = izin.
# Matriks dasar ini di-seed ke DB dan dapat disunting lewat panel admin.
# ------------------------------------------------------------------
ROLES = ["KOMANDAN", "ANALIS", "OPERATOR", "ADMIN", "AUDITOR"]

PERMISSIONS = [
    ("view_c4isr", "Lihat Peta C4ISR & Unit"),
    ("run_c2", "Kirim Perintah C2 / Force GPS Ping"),
    ("run_recon", "Jalankan Profiling OSINT"),
    ("view_siem", "Lihat SIEM & Soket Host"),
    ("run_soar", "Eksekusi Playbook SOAR / Isolasi"),
    ("manage_forensics", "Kelola Brankas Bukti Forensik"),
    ("print_bap", "Cetak BAP Resmi (UU ITE)"),
    ("manage_users", "Kelola Pengguna & Peran"),
    ("view_audit", "Lihat Jejak Audit"),
    ("manage_config", "Ubah Konfigurasi Sistem"),
]

# Izin bawaan per peran (True = diizinkan)
DEFAULT_MATRIX = {
    "KOMANDAN":  {p[0]: True for p in PERMISSIONS},
    "ANALIS":    {"view_c4isr": True, "run_c2": False, "run_recon": True, "view_siem": True,
                  "run_soar": False, "manage_forensics": True, "print_bap": True,
                  "manage_users": False, "view_audit": True, "manage_config": False},
    "OPERATOR":  {"view_c4isr": True, "run_c2": True, "run_recon": True, "view_siem": True,
                  "run_soar": True, "manage_forensics": False, "print_bap": False,
                  "manage_users": False, "view_audit": False, "manage_config": False},
    "ADMIN":     {"view_c4isr": True, "run_c2": False, "run_recon": False, "view_siem": True,
                  "run_soar": False, "manage_forensics": False, "print_bap": False,
                  "manage_users": True, "view_audit": True, "manage_config": True},
    "AUDITOR":   {"view_c4isr": True, "run_c2": False, "run_recon": False, "view_siem": True,
                  "run_soar": False, "manage_forensics": False, "print_bap": False,
                  "manage_users": False, "view_audit": True, "manage_config": False},
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_password(password: str, salt: str = None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return salt, h.hex()


# ------------------------------------------------------------------
# Inisialisasi skema & seed
# ------------------------------------------------------------------

def admin_init() -> None:
    conn = _conn(); cur = conn.cursor()
    # WAL mode: lebih cepat, memungkinkan pembacaan paralel saat ada write.
    conn.execute("PRAGMA journal_mode=WAL")
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT,
            source_ip   TEXT,
            timestamp   TEXT,
            result      TEXT
        );
        CREATE TABLE IF NOT EXISTS rbac_users (
            user_id       TEXT PRIMARY KEY,
            username      TEXT UNIQUE,
            full_name     TEXT,
            rank_title    TEXT,
            role          TEXT,
            status        TEXT,           -- AKTIF | NONAKTIF | TERKUNCI
            salt          TEXT,
            pwd_hash      TEXT,
            must_reset    INTEGER DEFAULT 0,
            created_at    TEXT,
            last_login    TEXT
        );
        CREATE TABLE IF NOT EXISTS rbac_role_perms (
            role          TEXT,
            perm          TEXT,
            allowed       INTEGER,
            PRIMARY KEY (role, perm)
        );
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT,
            actor         TEXT,
            role          TEXT,
            category      TEXT,           -- AUTH | C2 | OSINT | SIEM | FORENSIK | ADMIN | SISTEM
            action        TEXT,
            target_ref    TEXT,
            result        TEXT,           -- SUKSES | DITOLAK | GAGAL
            source_ip     TEXT,
            detail        TEXT,
            prev_hash     TEXT,           -- hash baris sebelumnya (chain tamper-evident)
            row_hash      TEXT            -- SHA-256(ts|actor|cat|action|target|result|prev_hash)
        );
        """
    )
    # Seed matriks peran
    cur.execute("SELECT COUNT(*) AS c FROM rbac_role_perms")
    if cur.fetchone()["c"] == 0:
        for role, perms in DEFAULT_MATRIX.items():
            for perm, allowed in perms.items():
                cur.execute("INSERT OR REPLACE INTO rbac_role_perms (role, perm, allowed) VALUES (?,?,?)",
                            (role, perm, 1 if allowed else 0))
    else:
        # Tambahkan permission baru yang belum ada di DB (idempoten, tidak override custom)
        for role, perms in DEFAULT_MATRIX.items():
            for perm, allowed in perms.items():
                cur.execute(
                    "INSERT OR IGNORE INTO rbac_role_perms (role, perm, allowed) VALUES (?,?,?)",
                    (role, perm, 1 if allowed else 0),
                )
    # Seed pengguna contoh (fiktif)
    cur.execute("SELECT COUNT(*) AS c FROM rbac_users")
    if cur.fetchone()["c"] == 0:
        seed = [
            ("USR-001", "komandan", "Dr. Bagas Nurwidodo", "Kolonel Ctp.", "KOMANDAN", "AKTIF"),
            ("USR-002", "analis.intel", "Rina Hapsari", "Mayor Ctp.", "ANALIS", "AKTIF"),
            ("USR-003", "operator.c2", "Yoga Pratama", "Kapten Ctp.", "OPERATOR", "AKTIF"),
            ("USR-004", "admin.sistem", "Dewi Larasati", "PNS Gol. III", "ADMIN", "AKTIF"),
            ("USR-005", "auditor.itjen", "Hendra Gunawan", "Letkol Ctp.", "AUDITOR", "NONAKTIF"),
        ]
        for uid, un, fn, rk, role, status in seed:
            salt, ph = _hash_password("Ganti#" + secrets.token_hex(4))
            cur.execute(
                """INSERT INTO rbac_users (user_id, username, full_name, rank_title, role, status,
                   salt, pwd_hash, must_reset, created_at, last_login)
                   VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
                (uid, un, fn, rk, role, status, salt, ph, _now(), None),
            )
        conn.commit()
        _log(conn, "SISTEM", "SISTEM", "ADMIN", "Inisialisasi basis data RBAC & seed pengguna",
             "rbac_users", "SUKSES", "127.0.0.1", "5 akun awal dibuat")
    # Migrasi: tambah kolom hash-chain ke log yang sudah ada (idempoten)
    for _col in ("prev_hash TEXT", "row_hash TEXT"):
        try:
            conn.execute(f"ALTER TABLE admin_audit_log ADD COLUMN {_col}")
        except Exception:
            pass
    conn.commit(); conn.close()


# ------------------------------------------------------------------
# Audit logging (tamper-evident hash chain)
# ------------------------------------------------------------------

def _log(conn, actor, role, category, action, target_ref, result, source_ip, detail):
    prev = conn.execute(
        "SELECT row_hash FROM admin_audit_log ORDER BY audit_id DESC LIMIT 1"
    ).fetchone()
    prev_hash = (prev["row_hash"] or "0" * 64) if prev else "0" * 64
    ts = _now()
    row_data = f"{ts}|{actor}|{category}|{action}|{target_ref or ''}|{result}|{prev_hash}"
    row_hash = hashlib.sha256(row_data.encode("utf-8")).hexdigest()
    conn.execute(
        """INSERT INTO admin_audit_log
           (timestamp, actor, role, category, action, target_ref, result, source_ip, detail, prev_hash, row_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (ts, actor, role, category, action, target_ref, result, source_ip, detail, prev_hash, row_hash),
    )


def log_action(actor="SYSTEM", category="SISTEM", action="", target_ref="",
               result="SUKSES", source_ip="", detail=""):
    """Dipanggil dari server untuk mencatat aktivitas operasional lintas pilar."""
    conn = _conn()
    role = _role_of(conn, actor)
    _log(conn, actor, role, category, action, target_ref, result, source_ip, detail)
    conn.commit(); conn.close()


def _role_of(conn, actor) -> str:
    row = conn.execute("SELECT role FROM rbac_users WHERE username=? OR user_id=?", (actor, actor)).fetchone()
    return row["role"] if row else "-"


def list_audit(limit=120, category=None, actor=None, result=None):
    conn = _conn()
    q = "SELECT * FROM admin_audit_log WHERE 1=1"
    args = []
    if category and category != "SEMUA":
        q += " AND category=?"; args.append(category)
    if actor:
        q += " AND actor LIKE ?"; args.append(f"%{actor}%")
    if result and result != "SEMUA":
        q += " AND result=?"; args.append(result)
    q += " ORDER BY audit_id DESC LIMIT ?"; args.append(int(limit))
    rows = [dict(r) for r in conn.execute(q, args).fetchall()]
    # ringkasan
    stat = {}
    for r in conn.execute("SELECT category, COUNT(*) c FROM admin_audit_log GROUP BY category").fetchall():
        stat[r["category"]] = r["c"]
    total = conn.execute("SELECT COUNT(*) c FROM admin_audit_log").fetchone()["c"]
    conn.close()
    return {"ok": True, "rows": rows, "summary": stat, "total": total}


# ------------------------------------------------------------------
# Manajemen pengguna
# ------------------------------------------------------------------

def list_users():
    conn = _conn()
    rows = []
    for r in conn.execute("SELECT * FROM rbac_users ORDER BY user_id").fetchall():
        d = dict(r); d.pop("salt", None); d.pop("pwd_hash", None)
        rows.append(d)
    counts = {
        "total": len(rows),
        "aktif": sum(1 for r in rows if r["status"] == "AKTIF"),
        "nonaktif": sum(1 for r in rows if r["status"] != "AKTIF"),
    }
    conn.close()
    return {"ok": True, "rows": rows, "counts": counts, "roles": ROLES}


def _next_user_id(conn) -> str:
    row = conn.execute("SELECT user_id FROM rbac_users ORDER BY user_id DESC LIMIT 1").fetchone()
    if not row:
        return "USR-001"
    try:
        n = int(row["user_id"].split("-")[1]) + 1
    except Exception:
        n = 1
    return f"USR-{n:03d}"


def create_user(username, full_name, rank_title, role, actor="admin.sistem", source_ip=""):
    if role not in ROLES:
        return {"ok": False, "error": f"Peran tidak dikenal: {role}"}
    conn = _conn()
    exists = conn.execute("SELECT 1 FROM rbac_users WHERE username=?", (username,)).fetchone()
    if exists:
        conn.close()
        return {"ok": False, "error": f"Username '{username}' sudah dipakai"}
    uid = _next_user_id(conn)
    temp_pwd = "TNI-" + secrets.token_hex(4).upper()
    salt, ph = _hash_password(temp_pwd)
    conn.execute(
        """INSERT INTO rbac_users (user_id, username, full_name, rank_title, role, status,
           salt, pwd_hash, must_reset, created_at, last_login)
           VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
        (uid, username, full_name, rank_title, role, "AKTIF", salt, ph, _now(), None),
    )
    _log(conn, actor, _role_of(conn, actor), "ADMIN", "Buat pengguna baru", f"{uid}/{username}",
         "SUKSES", source_ip, f"Peran {role}")
    conn.commit(); conn.close()
    # kata sandi sementara hanya dikembalikan sekali untuk ditampilkan ke admin
    return {"ok": True, "user_id": uid, "temp_password": temp_pwd}


def update_user(user_id, role=None, status=None, full_name=None, rank_title=None,
                actor="admin.sistem", source_ip=""):
    conn = _conn()
    cur = conn.execute("SELECT * FROM rbac_users WHERE user_id=?", (user_id,)).fetchone()
    if not cur:
        conn.close(); return {"ok": False, "error": "Pengguna tidak ditemukan"}
    # Jangan biarkan KOMANDAN aktif TERAKHIR dinonaktifkan atau diturunkan perannya —
    # kalau tidak, tak ada lagi yang bisa kelola pengguna (lockout total).
    if cur["role"] == "KOMANDAN":
        deactivating = status is not None and status != "AKTIF"
        demoting = role is not None and role != "KOMANDAN"
        if deactivating or demoting:
            n = conn.execute(
                "SELECT COUNT(*) c FROM rbac_users WHERE role='KOMANDAN' AND status='AKTIF'"
            ).fetchone()["c"]
            if n <= 1:
                conn.close()
                return {"ok": False, "error": "Tidak bisa menonaktifkan atau menurunkan KOMANDAN aktif terakhir."}
    fields, args, changes = [], [], []
    if role is not None and role in ROLES:
        fields.append("role=?"); args.append(role); changes.append(f"peran→{role}")
    if status is not None:
        fields.append("status=?"); args.append(status); changes.append(f"status→{status}")
    if full_name is not None:
        fields.append("full_name=?"); args.append(full_name)
    if rank_title is not None:
        fields.append("rank_title=?"); args.append(rank_title)
    if not fields:
        conn.close(); return {"ok": False, "error": "Tidak ada perubahan"}
    args.append(user_id)
    conn.execute(f"UPDATE rbac_users SET {', '.join(fields)} WHERE user_id=?", args)
    _log(conn, actor, _role_of(conn, actor), "ADMIN", "Ubah pengguna", user_id, "SUKSES",
         source_ip, "; ".join(changes) or "data profil")
    conn.commit(); conn.close()
    return {"ok": True}


def reset_password(user_id, actor="admin.sistem", source_ip=""):
    conn = _conn()
    cur = conn.execute("SELECT username FROM rbac_users WHERE user_id=?", (user_id,)).fetchone()
    if not cur:
        conn.close(); return {"ok": False, "error": "Pengguna tidak ditemukan"}
    temp_pwd = "TNI-" + secrets.token_hex(4).upper()
    salt, ph = _hash_password(temp_pwd)
    conn.execute("UPDATE rbac_users SET salt=?, pwd_hash=?, must_reset=1 WHERE user_id=?",
                 (salt, ph, user_id))
    _log(conn, actor, _role_of(conn, actor), "ADMIN", "Reset kata sandi", user_id, "SUKSES",
         source_ip, "Kata sandi sementara diterbitkan")
    conn.commit(); conn.close()
    return {"ok": True, "temp_password": temp_pwd}


def delete_user(user_id, actor="admin.sistem", source_ip=""):
    conn = _conn()
    cur = conn.execute("SELECT role FROM rbac_users WHERE user_id=?", (user_id,)).fetchone()
    if not cur:
        conn.close(); return {"ok": False, "error": "Pengguna tidak ditemukan"}
    # Jangan biarkan komandan terakhir terhapus
    if cur["role"] == "KOMANDAN":
        n = conn.execute("SELECT COUNT(*) c FROM rbac_users WHERE role='KOMANDAN' AND status='AKTIF'").fetchone()["c"]
        if n <= 1:
            conn.close(); return {"ok": False, "error": "Tidak bisa menonaktifkan KOMANDAN aktif terakhir"}
    conn.execute("UPDATE rbac_users SET status='NONAKTIF' WHERE user_id=?", (user_id,))
    _log(conn, actor, _role_of(conn, actor), "ADMIN", "Nonaktifkan pengguna", user_id, "SUKSES",
         source_ip, "Status diubah ke NONAKTIF (soft delete)")
    conn.commit(); conn.close()
    return {"ok": True}


# ------------------------------------------------------------------
# Matriks peran–izin
# ------------------------------------------------------------------

def get_roles_matrix():
    conn = _conn()
    matrix = {role: {} for role in ROLES}
    for r in conn.execute("SELECT role, perm, allowed FROM rbac_role_perms").fetchall():
        if r["role"] in matrix:
            matrix[r["role"]][r["perm"]] = bool(r["allowed"])
    conn.close()
    return {"ok": True, "roles": ROLES, "permissions": PERMISSIONS, "matrix": matrix}


def update_role_permission(role, perm, allowed, actor="admin.sistem", source_ip=""):
    if role not in ROLES:
        return {"ok": False, "error": "Peran tidak dikenal"}
    # Jaga agar KOMANDAN tetap bisa kelola pengguna (hindari lockout)
    if role == "KOMANDAN" and perm == "manage_users" and not allowed:
        return {"ok": False, "error": "KOMANDAN harus tetap memiliki izin kelola pengguna"}
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO rbac_role_perms (role, perm, allowed) VALUES (?,?,?)",
                 (role, perm, 1 if allowed else 0))
    _log(conn, actor, _role_of(conn, actor), "ADMIN", "Ubah izin peran", f"{role}.{perm}",
         "SUKSES", source_ip, f"allowed={bool(allowed)}")
    conn.commit(); conn.close()
    return {"ok": True}


# ==============================================================================
# AUTENTIKASI, SESI, & PENEGAKAN IZIN (LOGIN)
# ==============================================================================
import secrets as _secrets
import sys as _sys
import threading as _threading
import time as _time
from datetime import timedelta

SESSION_TTL_HOURS = 8
# Kata sandi awal untuk semua akun seed (wajib diganti). Dilaporkan ke admin sekali.
# Diambil dari env OMNI_BOOTSTRAP_PASSWORD; bila kosong, dibangkitkan acak dan
# ditampilkan satu kali di log boot (tidak pernah di-hardcode lagi).
BOOTSTRAP_PASSWORD = os.environ.get("OMNI_BOOTSTRAP_PASSWORD") or _secrets.token_urlsafe(12)
_BOOTSTRAP_IS_RANDOM = not os.environ.get("OMNI_BOOTSTRAP_PASSWORD")

# Kebijakan lockout login (anti brute-force), dapat diatur lewat env.
LOGIN_MAX_FAILS = int(os.environ.get("OMNI_LOGIN_MAX_FAILS", "5"))
LOGIN_LOCK_SECONDS = int(os.environ.get("OMNI_LOGIN_LOCK_SECONDS", "900"))
# Jejak percobaan gagal di memori: {(username, ip): [jumlah_gagal, epoch_buka_kunci]}
# Dilindungi lock karena server multithread (ThreadingHTTPServer).
_FAILED_LOGINS: dict = {}
_FAILED_LOCK = _threading.Lock()


def auth_init() -> None:
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rbac_sessions (
            token       TEXT PRIMARY KEY,  -- SHA-256(token_asli), bukan token plaintext
            user_id     TEXT,
            username    TEXT,
            role        TEXT,
            created_at  TEXT,
            expires_at  TEXT,
            source_ip   TEXT
        );
        CREATE TABLE IF NOT EXISTS system_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    # Migrasi ke penyimpanan token ter-hash (v2): hapus sesi lama yang plaintext.
    ver = conn.execute("SELECT value FROM system_meta WHERE key='token_storage_version'").fetchone()
    if not ver or ver["value"] != "2":
        conn.execute("DELETE FROM rbac_sessions")
        conn.execute("INSERT OR REPLACE INTO system_meta (key, value) VALUES ('token_storage_version', '2')")
    conn.commit(); conn.close()


def _hash_token(token: str) -> str:
    """Kembalikan SHA-256 hex dari token. Token asli hanya disimpan di sisi client."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_audit_chain() -> dict:
    """Verifikasi integritas hash-chain pada admin_audit_log."""
    conn = _conn()
    rows = conn.execute(
        "SELECT audit_id, timestamp, actor, category, action, target_ref, result, prev_hash, row_hash "
        "FROM admin_audit_log ORDER BY audit_id ASC"
    ).fetchall()
    conn.close()
    prev_hash = "0" * 64
    broken_at = []
    for r in rows:
        if not r["row_hash"]:  # baris lama sebelum migrasi hash-chain
            prev_hash = "0" * 64
            continue
        row_data = f"{r['timestamp']}|{r['actor']}|{r['category']}|{r['action']}|{r['target_ref'] or ''}|{r['result']}|{r['prev_hash'] or '0'*64}"
        expected = hashlib.sha256(row_data.encode()).hexdigest()
        if r["row_hash"] != expected:
            broken_at.append(r["audit_id"])
        prev_hash = r["row_hash"]
    return {"ok": len(broken_at) == 0, "chain_length": len(rows), "broken_at": broken_at}


def _verify(password: str, salt: str, pwd_hash: str) -> bool:
    if not salt or not pwd_hash:
        return False
    _, h = _hash_password(password, salt)
    return hmac_compare(h, pwd_hash)


def hmac_compare(a: str, b: str) -> bool:
    # perbandingan waktu-konstan
    import hmac as _hmac
    return _hmac.compare_digest(str(a), str(b))


def perms_for(role: str) -> dict:
    conn = _conn()
    out = {}
    for r in conn.execute("SELECT perm, allowed FROM rbac_role_perms WHERE role=?", (role,)).fetchall():
        out[r["perm"]] = bool(r["allowed"])
    conn.close()
    # lengkapi izin yang belum ada sebagai False
    for p in PERMISSIONS:
        out.setdefault(p[0], False)
    return out


def authenticate(username: str, password: str, source_ip: str = ""):
    conn = _conn()

    # --- Lockout anti brute-force — persistent di SQLite + in-memory fallback ---
    _key = (username, source_ip)
    now_ts = _time.time()
    # Cek in-memory dulu (lebih cepat)
    with _FAILED_LOCK:
        if len(_FAILED_LOGINS) > 4096:
            for _k in [k for k, v in _FAILED_LOGINS.items() if v[1] <= now_ts]:
                _FAILED_LOGINS.pop(_k, None)
        _rec = _FAILED_LOGINS.get(_key)
        locked_until = _rec[1] if _rec else 0.0
    # Jika tidak ada di memori, periksa DB (tahan restart)
    if locked_until <= now_ts:
        window_start = datetime.fromtimestamp(now_ts - LOGIN_LOCK_SECONDS, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fail_count = conn.execute(
            "SELECT COUNT(*) c FROM login_attempts WHERE username=? AND source_ip=? AND result='GAGAL' AND timestamp > ?",
            (username, source_ip, window_start),
        ).fetchone()["c"]
        if fail_count >= LOGIN_MAX_FAILS:
            locked_until = now_ts + LOGIN_LOCK_SECONDS
            with _FAILED_LOCK:
                _FAILED_LOGINS[_key] = [0, locked_until]
    if locked_until > now_ts:
        _sisa = int(locked_until - now_ts)
        _log(conn, username or "-", "-", "AUTH", f"Login ditolak (terkunci {_sisa}s)", username,
             "DITOLAK", source_ip, "lockout")
        conn.commit(); conn.close()
        return {"ok": False, "error": f"Terkunci sementara. Coba lagi dalam {_sisa} detik."}

    def _catat_gagal():
        conn.execute(
            "INSERT INTO login_attempts (username, source_ip, timestamp, result) VALUES (?,?,?,?)",
            (username, source_ip, _now(), "GAGAL"),
        )
        with _FAILED_LOCK:
            rec = _FAILED_LOGINS.get(_key, [0, 0.0])
            rec[0] += 1
            if rec[0] >= LOGIN_MAX_FAILS:
                rec[1] = _time.time() + LOGIN_LOCK_SECONDS
                rec[0] = 0
            _FAILED_LOGINS[_key] = rec

    u = conn.execute("SELECT * FROM rbac_users WHERE username=?", (username,)).fetchone()
    if not u:
        _catat_gagal()
        _log(conn, username or "-", "-", "AUTH", "Login gagal (pengguna tidak ada)", username,
             "DITOLAK", source_ip, "")
        conn.commit(); conn.close()
        return {"ok": False, "error": "Username atau kata sandi salah"}
    if u["status"] != "AKTIF":
        _catat_gagal()
        _log(conn, username, u["role"], "AUTH", "Login gagal (akun nonaktif)", u["user_id"],
             "DITOLAK", source_ip, f"status={u['status']}")
        conn.commit(); conn.close()
        return {"ok": False, "error": "Akun tidak aktif. Hubungi admin."}
    if not _verify(password, u["salt"], u["pwd_hash"]):
        _catat_gagal()
        _log(conn, username, u["role"], "AUTH", "Login gagal (kata sandi salah)", u["user_id"],
             "DITOLAK", source_ip, "")
        conn.commit(); conn.close()
        return {"ok": False, "error": "Username atau kata sandi salah"}
    # sukses — bersihkan jejak gagal & terbitkan token
    with _FAILED_LOCK:
        _FAILED_LOGINS.pop(_key, None)
    conn.execute(
        "INSERT INTO login_attempts (username, source_ip, timestamp, result) VALUES (?,?,?,?)",
        (u["username"], source_ip, _now(), "SUKSES"),
    )
    # Batas concurrent session: hapus sesi terlama jika sudah >= 3
    MAX_SESSIONS = 3
    existing = conn.execute(
        "SELECT token FROM rbac_sessions WHERE user_id=? ORDER BY created_at ASC", (u["user_id"],)
    ).fetchall()
    while len(existing) >= MAX_SESSIONS:
        conn.execute("DELETE FROM rbac_sessions WHERE token=?", (existing[0]["token"],))
        existing.pop(0)
    # Token asli dikirim ke client; hanya SHA-256-nya yang disimpan di DB
    token = _secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=SESSION_TTL_HOURS)
    conn.execute(
        "INSERT INTO rbac_sessions (token, user_id, username, role, created_at, expires_at, source_ip) VALUES (?,?,?,?,?,?,?)",
        (token_hash, u["user_id"], u["username"], u["role"],
         now.strftime("%Y-%m-%dT%H:%M:%SZ"), exp.strftime("%Y-%m-%dT%H:%M:%SZ"), source_ip),
    )
    conn.execute("UPDATE rbac_users SET last_login=? WHERE user_id=?",
                 (now.strftime("%Y-%m-%dT%H:%M:%SZ"), u["user_id"]))
    _log(conn, u["username"], u["role"], "AUTH", "Login berhasil", u["user_id"], "SUKSES", source_ip, "")
    conn.commit(); conn.close()
    return {
        "ok": True, "token": token,
        "user": {"user_id": u["user_id"], "username": u["username"], "full_name": u["full_name"],
                 "rank_title": u["rank_title"], "role": u["role"], "must_reset": bool(u["must_reset"])},
        "permissions": perms_for(u["role"]),
    }


def validate_token(token: str):
    if not token:
        return None
    token_hash = _hash_token(token)
    conn = _conn()
    s = conn.execute("SELECT * FROM rbac_sessions WHERE token=?", (token_hash,)).fetchone()
    if not s:
        conn.close(); return None
    now_dt = datetime.now(timezone.utc)
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if s["expires_at"] < now:
        conn.execute("DELETE FROM rbac_sessions WHERE token=?", (token_hash,))
        conn.commit(); conn.close(); return None
    # pastikan akun masih aktif, baca also must_reset
    u = conn.execute("SELECT status, role, must_reset FROM rbac_users WHERE user_id=?", (s["user_id"],)).fetchone()
    if not u or u["status"] != "AKTIF":
        conn.close(); return None
    # sliding expiry: perpanjang sesi setiap kali dipakai
    new_exp = (now_dt + timedelta(hours=SESSION_TTL_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE rbac_sessions SET expires_at=? WHERE token=?", (new_exp, token_hash))
    conn.commit(); conn.close()
    return {"user_id": s["user_id"], "username": s["username"], "role": u["role"],
            "must_reset": bool(u["must_reset"])}


def session_info(token: str):
    sess = validate_token(token)
    if not sess:
        return {"ok": False, "error": "Sesi tidak valid"}
    conn = _conn()
    u = conn.execute("SELECT * FROM rbac_users WHERE user_id=?", (sess["user_id"],)).fetchone()
    conn.close()
    return {
        "ok": True,
        "user": {"user_id": u["user_id"], "username": u["username"], "full_name": u["full_name"],
                 "rank_title": u["rank_title"], "role": u["role"], "must_reset": bool(u["must_reset"])},
        "permissions": perms_for(sess["role"]),
    }


def logout(token: str, source_ip: str = ""):
    if not token:
        return {"ok": True}
    token_hash = _hash_token(token)
    conn = _conn()
    s = conn.execute("SELECT username, role FROM rbac_sessions WHERE token=?", (token_hash,)).fetchone()
    conn.execute("DELETE FROM rbac_sessions WHERE token=?", (token_hash,))
    if s:
        _log(conn, s["username"], s["role"], "AUTH", "Logout", s["username"], "SUKSES", source_ip, "")
    conn.commit(); conn.close()
    return {"ok": True}


def logout_all(user_id: str, actor: str = "SISTEM", source_ip: str = "") -> dict:
    """Hapus semua sesi aktif milik user_id (logout dari semua device)."""
    conn = _conn()
    u = conn.execute("SELECT username, role FROM rbac_users WHERE user_id=?", (user_id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) c FROM rbac_sessions WHERE user_id=?", (user_id,)).fetchone()["c"]
    conn.execute("DELETE FROM rbac_sessions WHERE user_id=?", (user_id,))
    if u:
        _log(conn, u["username"], u["role"], "AUTH", "Logout semua sesi", user_id,
             "SUKSES", source_ip, f"{count} sesi dihapus oleh {actor}")
    conn.commit(); conn.close()
    return {"ok": True, "sessions_cleared": count}


def change_password(user_id: str, old_password: str, new_password: str, source_ip: str = "") -> dict:
    """Ganti kata sandi dan reset flag must_reset. Minimal 10 karakter."""
    if len(new_password) < 10:
        return {"ok": False, "error": "Kata sandi baru minimal 10 karakter"}
    conn = _conn()
    u = conn.execute("SELECT * FROM rbac_users WHERE user_id=?", (user_id,)).fetchone()
    if not u:
        conn.close(); return {"ok": False, "error": "Pengguna tidak ditemukan"}
    if not _verify(old_password, u["salt"], u["pwd_hash"]):
        _log(conn, u["username"], u["role"], "AUTH", "Ganti kata sandi gagal", user_id,
             "DITOLAK", source_ip, "Kata sandi lama salah")
        conn.commit(); conn.close()
        return {"ok": False, "error": "Kata sandi lama salah"}
    salt, ph = _hash_password(new_password)
    conn.execute("UPDATE rbac_users SET salt=?, pwd_hash=?, must_reset=0 WHERE user_id=?", (salt, ph, user_id))
    _log(conn, u["username"], u["role"], "AUTH", "Kata sandi berhasil diubah", user_id,
         "SUKSES", source_ip, "must_reset di-reset ke 0")
    conn.commit(); conn.close()
    return {"ok": True}


def authorize(token: str, perm: str):
    """Kembalikan (diizinkan, sesi). Jika perm kosong, cukup perlu sesi valid."""
    sess = validate_token(token)
    if not sess:
        return False, None, "NO_SESSION"
    if not perm:
        return True, sess, "OK"
    allowed = perms_for(sess["role"]).get(perm, False)
    return (allowed, sess, "OK" if allowed else "FORBIDDEN")


def set_bootstrap_passwords():
    """Jadikan kata sandi semua akun seed = BOOTSTRAP_PASSWORD.
    Bila OMNI_BOOTSTRAP_PASSWORD di-set: reset SEMUA user must_reset=1 (termasuk yang sudah pernah login).
    Bila tidak di-set (acak): hanya yang belum pernah login.
    """
    conn = _conn()
    if _BOOTSTRAP_IS_RANDOM:
        rows = conn.execute("SELECT user_id FROM rbac_users WHERE must_reset=1 AND last_login IS NULL").fetchall()
    else:
        rows = conn.execute("SELECT user_id FROM rbac_users WHERE must_reset=1").fetchall()
    for r in rows:
        salt, ph = _hash_password(BOOTSTRAP_PASSWORD)
        conn.execute("UPDATE rbac_users SET salt=?, pwd_hash=? WHERE user_id=?", (salt, ph, r["user_id"]))
    conn.commit(); conn.close()
    if rows and _BOOTSTRAP_IS_RANDOM:
        _sys.stderr.write(
            "\n[TFAEL-OMNI][BOOTSTRAP] Kata sandi awal akun seed (acak, TAMPIL SEKALI): "
            f"{BOOTSTRAP_PASSWORD}\n"
            "  -> Segera login lalu ganti. Setel OMNI_BOOTSTRAP_PASSWORD untuk menetapkan sendiri.\n\n"
        )
