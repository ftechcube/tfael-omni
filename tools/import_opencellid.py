#!/usr/bin/env python3
"""
Impor menara BTS NYATA dari ekspor CSV OpenCellID ke TFAEL-OMNI (tabel bts_towers).

Unduh CSV dari dashboard OpenCellID Anda (per-MCC, mis. 510 = Indonesia), lalu:

    python3 tools/import_opencellid.py 510.csv.gz --bbox -6.5,106.6,-6.0,107.0 --limit 20000

--bbox min_lat,min_lon,max_lat,max_lon  menyaring wilayah (disarankan; file MCC penuh besar).
Setelah impor, triangulasi offline otomatis memakai koordinat menara NYATA (data_source=OPENCELLID).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from celltower_lookup import import_opencellid_csv  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Impor CSV OpenCellID ke bts_towers")
    ap.add_argument("csv", help="Path CSV OpenCellID (.csv atau .csv.gz)")
    ap.add_argument("--bbox", help="min_lat,min_lon,max_lat,max_lon", default=None)
    ap.add_argument("--limit", type=int, default=None, help="Batas jumlah menara diimpor")
    args = ap.parse_args()

    bbox = None
    if args.bbox:
        try:
            bbox = tuple(float(x) for x in args.bbox.split(","))
            assert len(bbox) == 4
        except Exception:
            print("bbox tidak valid; format: min_lat,min_lon,max_lat,max_lon", file=sys.stderr)
            return 2

    res = import_opencellid_csv(args.csv, bbox=bbox, limit=args.limit)
    if not res.get("ok"):
        print(f"GAGAL: {res.get('error')}", file=sys.stderr)
        return 1
    print(f"Impor selesai: {res['imported']} menara nyata (dilewati {res['skipped']}). "
          f"Total menara OPENCELLID di DB: {res['total_real_towers']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
