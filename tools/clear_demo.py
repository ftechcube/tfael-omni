#!/usr/bin/env python3
"""
Kosongkan SEMUA data contoh/peraga dari database TFAEL-OMNI, supaya setiap panel
mulai kosong dan hanya terisi oleh input NYATA Anda (tambah target → OSINT live,
unggah berkas → forensik live, HP agent lapor → unit & triangulasi live).

Yang DIHAPUS (tabel data peraga):
  - tactical_units          (unit demo di peta)
  - target_profiles         (target OSINT demo TGT-01..03)
  - siem_alerts             (alert SIEM contoh)
  - forensic_evidence_vault (kasus DFIR contoh)
  - geofences               (zona demo)

Yang DIPERTAHANKAN:
  - bts_towers              (63.800 menara OpenCellID — DATA NYATA)
  - rbac_users / sesi       (akun login termasuk komandan)
  - unit_cells, map_annotations, cache, log audit

Pakai:
  python3 tools/clear_demo.py            # hapus data contoh (minta konfirmasi)
  python3 tools/clear_demo.py --yes      # tanpa konfirmasi

Lalu jalankan server dalam mode bersih agar contoh TIDAK terisi ulang saat boot:
  OMNI_DEMO=0 python3 backend/server.py
"""
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "tfael_omni.db")
DEMO_TABLES = (
    "tactical_units",
    "target_profiles",
    "siem_alerts",
    "forensic_evidence_vault",
    "geofences",
)


def main() -> int:
    db = os.path.abspath(DB_PATH)
    if not os.path.exists(db):
        print(f"DB tidak ditemukan: {db}")
        return 1

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    def count(table: str) -> int:
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            return -1  # tabel belum ada

    print("Data contoh yang akan dihapus:")
    total = 0
    for t in DEMO_TABLES:
        c = count(t)
        if c >= 0:
            print(f"  - {t:<24} {c} baris")
            total += c
    towers = count("bts_towers")
    users = count("rbac_users")
    print(f"\nDipertahankan: bts_towers {towers} (OpenCellID nyata), rbac_users {users} (login).")

    if total == 0:
        print("\nSudah bersih — tidak ada data contoh tersisa.")
        return 0

    if "--yes" not in sys.argv and "-y" not in sys.argv:
        ans = input(f"\nHapus {total} baris data contoh? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Dibatalkan.")
            return 0

    for t in DEMO_TABLES:
        if count(t) >= 0:
            conn.execute(f"DELETE FROM {t}")
    conn.commit()

    print("\nSelesai. Semua panel akan mulai KOSONG.")
    print("Jalankan server bersih (tanpa seed ulang):")
    print("  OMNI_DEMO=0 python3 backend/server.py")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
