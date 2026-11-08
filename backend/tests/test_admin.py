"""Unit tests for admin.py — auth, session, RBAC (uses an in-memory SQLite DB)."""

import sys
import os
import sqlite3
import tempfile
import importlib
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin_with_tmpdb():
    """Import admin.py but redirect DB_PATH to a fresh temp file, then init its schema."""
    import admin as _admin_module
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    original_path = _admin_module.DB_PATH
    _admin_module.DB_PATH = tmp.name  # _conn() reads this at call-time; init uses it too
    _admin_module.admin_init()        # rbac_users, rbac_role_perms, login_attempts, ...
    _admin_module.auth_init()         # rbac_sessions table
    return _admin_module, tmp.name, original_path


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

def test_authenticate_wrong_password():
    admin, tmpdb, orig = _make_admin_with_tmpdb()
    try:
        r = admin.create_user("testuser", "Test User", "Prajurit", "KOMANDAN")
        assert r["ok"], f"create_user failed: {r}"
        result = admin.authenticate("testuser", "salah_banget", "127.0.0.1")
        assert result["ok"] is False
        assert result.get("error")
    finally:
        admin.DB_PATH = orig
        os.unlink(tmpdb)


def test_authenticate_correct_password():
    admin, tmpdb, orig = _make_admin_with_tmpdb()
    try:
        r = admin.create_user("operator1", "Operator Satu", "Sersan", "KOMANDAN")
        assert r["ok"], f"create_user failed: {r}"
        temp_pw = r["temp_password"]
        result = admin.authenticate("operator1", temp_pw, "127.0.0.1")
        assert result["ok"] is True, f"Expected ok=True, got: {result}"
        assert "token" in result
    finally:
        admin.DB_PATH = orig
        os.unlink(tmpdb)


# ---------------------------------------------------------------------------
# validate_token
# ---------------------------------------------------------------------------

def _insert_user_and_token(tmpdb, username, role, token, expires_at):
    """Helper: insert a minimal user + session row using the real schema.
    Token disimpan sebagai SHA-256 hash sesuai skema baru (token hashing v2)."""
    import secrets as _sec
    import hashlib as _hl
    conn = sqlite3.connect(tmpdb)
    conn.row_factory = sqlite3.Row
    uid = "U-" + _sec.token_hex(4)
    conn.execute(
        """INSERT INTO rbac_users
           (user_id, username, full_name, rank_title, role, status, salt, pwd_hash, must_reset, created_at, last_login)
           VALUES (?,?,?,?,?,?,?,?,0,?,NULL)""",
        (uid, username, username, "-", role, "AKTIF", "fakesalt", "fakehash",
         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    # Simpan SHA-256 dari token (bukan plaintext) sesuai skema produksi
    token_hash = _hl.sha256(token.encode("utf-8")).hexdigest()
    conn.execute(
        """INSERT INTO rbac_sessions (token, user_id, username, role, created_at, expires_at, source_ip)
           VALUES (?,?,?,?,?,?,?)""",
        (token_hash, uid, username, role,
         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), expires_at, "127.0.0.1"),
    )
    conn.commit(); conn.close()
    return uid


def test_validate_token_expired():
    admin, tmpdb, orig = _make_admin_with_tmpdb()
    try:
        import secrets as _sec
        token = "tok-" + _sec.token_hex(8)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _insert_user_and_token(tmpdb, "expuser", "KOMANDAN", token, past)
        result = admin.validate_token(token)
        assert result is None, "Expired token should return None"
    finally:
        admin.DB_PATH = orig
        os.unlink(tmpdb)


def test_validate_token_valid_and_extends():
    admin, tmpdb, orig = _make_admin_with_tmpdb()
    try:
        import secrets as _sec
        token = "tok-" + _sec.token_hex(8)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _insert_user_and_token(tmpdb, "validuser", "KOMANDAN", token, future)

        result = admin.validate_token(token)
        assert result is not None
        assert result["username"] == "validuser"
        assert result["role"] == "KOMANDAN"

        # Sliding expiry: new expires_at must be >= original
        # Sesi disimpan dengan SHA-256(token) — gunakan hash untuk lookup
        import hashlib as _hl2
        token_hash = _hl2.sha256(token.encode()).hexdigest()
        conn2 = sqlite3.connect(tmpdb)
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT expires_at FROM rbac_sessions WHERE token=?", (token_hash,)).fetchone()
        conn2.close()
        assert row is not None, "Sesi harus masih ada setelah validate_token valid"
        assert row["expires_at"] >= future
    finally:
        admin.DB_PATH = orig
        os.unlink(tmpdb)


def test_validate_token_empty():
    admin, tmpdb, orig = _make_admin_with_tmpdb()
    try:
        assert admin.validate_token("") is None
        assert admin.validate_token(None) is None
    finally:
        admin.DB_PATH = orig
        os.unlink(tmpdb)


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
