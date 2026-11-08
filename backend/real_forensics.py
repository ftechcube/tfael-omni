#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Mesin Forensik Biner Asli (Real Digital Forensic Toolkit - Pilar 6)
Membedah byte biner sesungguhnya dari file yang diunggah pengguna:
1. Parser Biner JPEG EXIF / TIFF IFD0 / ExifIFD / GPSIFD (Merek Kamera, Software, Tanggal, Koordinat GPS Asli)
2. Parser Biner PNG IHDR / tEXt & PDF Metadata (/Author, /Creator, /Producer)
3. Kalkulator Entropi Shannon (0.00 - 8.00 bit/byte) untuk deteksi enkripsi/packing
4. Pembedah Database SQLite3 Asli (Membaca skema sqlite_master, isi tabel, & string unallocated/terhapus)
5. Pembedah Paket Jaringan PCAP Asli (Membaca header libpcap, Ethernet, IPv4, TCP/UDP)
"""

import math
import os
import re
import socket
import sqlite3
import struct
import tempfile
from collections import Counter
from typing import Any, Dict, List, Tuple


def compute_shannon_entropy(data: bytes) -> float:
    """Menghitung Entropi Shannon (0.0 - 8.0 bit/byte) dari byte file."""
    if not data:
        return 0.0
    n = len(data)
    counts = Counter(data)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return round(entropy, 4)


# ==============================================================================
# 1. REAL BINARY JPEG EXIF & GPS PARSER (TIFF IFD0 + ExifIFD + GPSIFD)
# ==============================================================================

EXIF_TAG_NAMES = {
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x013C: "HostComputer",
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8769: "ExifOffset",
    0x8825: "GPSInfoOffset",
    0x8827: "ISOSpeedRatings",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0x9010: "OffsetTime",
    0x9011: "OffsetTimeOriginal",
    0x920A: "FocalLength",
    0xA002: "ExifImageWidth",
    0xA003: "ExifImageHeight",
    0xA405: "FocalLengthIn35mmFilm",
    0xA433: "LensMake",
    0xA434: "LensModel",
}

GPS_TAG_NAMES = {
    1: "GPSLatitudeRef",
    2: "GPSLatitude",
    3: "GPSLongitudeRef",
    4: "GPSLongitude",
    5: "GPSAltitudeRef",
    6: "GPSAltitude",
}


def _read_rational(tiff_bytes: bytes, offset: int, endian: str) -> float:
    if offset + 8 > len(tiff_bytes):
        return 0.0
    num, den = struct.unpack(endian + "II", tiff_bytes[offset : offset + 8])
    return float(num) / float(den) if den != 0 else 0.0


def _parse_ifd(tiff_bytes: bytes, ifd_offset: int, endian: str, tag_map: Dict[int, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if ifd_offset + 2 > len(tiff_bytes):
        return out
    num_entries = struct.unpack(endian + "H", tiff_bytes[ifd_offset : ifd_offset + 2])[0]
    pos = ifd_offset + 2

    for _ in range(min(num_entries, 120)):
        if pos + 12 > len(tiff_bytes):
            break
        tag, fmt, count, val_raw = struct.unpack(endian + "HHII", tiff_bytes[pos : pos + 12])
        pos += 12
        tag_name = tag_map.get(tag)
        if not tag_name:
            continue

        # Format 2: ASCII String
        if fmt == 2:
            if count <= 4:
                raw_s = tiff_bytes[pos - 4 : pos - 4 + count]
            else:
                if val_raw + count <= len(tiff_bytes):
                    raw_s = tiff_bytes[val_raw : val_raw + count]
                else:
                    raw_s = b""
            out[tag_name] = raw_s.rstrip(b"\x00").decode("utf-8", errors="replace").strip()

        # Format 3: unsigned short (2 bytes)
        elif fmt == 3 and count == 1:
            short_val = struct.unpack(endian + "H", tiff_bytes[pos - 4 : pos - 2])[0]
            out[tag_name] = short_val

        # Format 4: unsigned long (4 bytes)
        elif fmt == 4 and count == 1:
            out[tag_name] = val_raw

        # Format 5: unsigned rational (8 bytes each, e.g. GPS coordinates [deg, min, sec])
        elif fmt == 5:
            if count == 1:
                out[tag_name] = round(_read_rational(tiff_bytes, val_raw, endian), 4)
            elif count == 3:
                deg = _read_rational(tiff_bytes, val_raw, endian)
                mins = _read_rational(tiff_bytes, val_raw + 8, endian)
                secs = _read_rational(tiff_bytes, val_raw + 16, endian)
                out[tag_name] = [deg, mins, secs]

    return out


def extract_real_binary_metadata(file_name: str, raw_bytes: bytes) -> Dict[str, Any]:
    """
    Mengekstrak metadata biner asli dari file JPEG (EXIF/GPS), PNG (IHDR/tEXt), atau PDF.
    """
    meta: Dict[str, Any] = {
        "FileName": file_name,
        "FileSizeBytes": len(raw_bytes),
        "ShannonEntropy": f"{compute_shannon_entropy(raw_bytes)} bits/byte",
    }

    # 1. Cek JPEG & APP1 EXIF
    if raw_bytes.startswith(b"\xff\xd8"):
        meta["ContainerFormat"] = "JPEG Image (0xFFD8)"
        idx = 2
        while idx + 4 < len(raw_bytes):
            if raw_bytes[idx] != 0xFF:
                idx += 1
                continue
            marker = raw_bytes[idx + 1]
            if marker == 0xDA or marker == 0xD9:  # SOS or EOI
                break
            seg_len = struct.unpack(">H", raw_bytes[idx + 2 : idx + 4])[0]
            seg_data = raw_bytes[idx + 4 : idx + 2 + seg_len]

            # SOF0 / SOF2 untuk dimensi piksel asli JPEG
            if marker in (0xC0, 0xC2) and len(seg_data) >= 5:
                precision, h, w = struct.unpack(">BHH", seg_data[:5])
                meta["ImageDimensions"] = f"{w} x {h} px ({precision}-bit)"

            # APP1 EXIF Header
            if marker == 0xE1 and seg_data.startswith(b"Exif\x00\x00"):
                tiff = seg_data[6:]
                if len(tiff) >= 8:
                    endian = "<" if tiff[:2] == b"II" else (">" if tiff[:2] == b"MM" else "<")
                    first_ifd = struct.unpack(endian + "I", tiff[4:8])[0]
                    ifd0 = _parse_ifd(tiff, first_ifd, endian, EXIF_TAG_NAMES)
                    for k, v in ifd0.items():
                        if k not in ("ExifOffset", "GPSInfoOffset"):
                            meta[k] = v

                    if "ExifOffset" in ifd0:
                        exif_sub = _parse_ifd(tiff, int(ifd0["ExifOffset"]), endian, EXIF_TAG_NAMES)
                        meta.update(exif_sub)

                    if "GPSInfoOffset" in ifd0:
                        gps_sub = _parse_ifd(tiff, int(ifd0["GPSInfoOffset"]), endian, GPS_TAG_NAMES)
                        if "GPSLatitude" in gps_sub and "GPSLongitude" in gps_sub:
                            lat_dms = gps_sub["GPSLatitude"]
                            lon_dms = gps_sub["GPSLongitude"]
                            if isinstance(lat_dms, list) and isinstance(lon_dms, list):
                                lat_dec = lat_dms[0] + lat_dms[1] / 60.0 + lat_dms[2] / 3600.0
                                lon_dec = lon_dms[0] + lon_dms[1] / 60.0 + lon_dms[2] / 3600.0
                                if gps_sub.get("GPSLatitudeRef", "N").upper().startswith("S"):
                                    lat_dec = -lat_dec
                                if gps_sub.get("GPSLongitudeRef", "E").upper().startswith("W"):
                                    lon_dec = -lon_dec
                                meta["GPSLatitude"] = round(lat_dec, 6)
                                meta["GPSLongitude"] = round(lon_dec, 6)
                                if "GPSAltitude" in gps_sub:
                                    meta["GPSAltitude"] = f"{gps_sub['GPSAltitude']} m"

            idx += 2 + seg_len

    # 2. Cek PNG IHDR & Text Chunks
    elif raw_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(raw_bytes) >= 24:
        w, h, bit_depth, color_type = struct.unpack(">IIBB", raw_bytes[16:26])
        meta["ContainerFormat"] = "PNG Image (0x89504E47)"
        meta["ImageDimensions"] = f"{w} x {h} px (BitDepth: {bit_depth}, ColorType: {color_type})"

    # 3. Cek PDF Metadata
    elif raw_bytes.startswith(b"%PDF-"):
        text_s = raw_bytes[:16384].decode("latin-1", errors="ignore")
        meta["ContainerFormat"] = f"PDF Document ({text_s[:8].strip()})"
        for tag in ("Author", "Creator", "Producer", "CreationDate", "ModDate", "Title"):
            m = re.search(rf"/{tag}\s*\(([^)]+)\)", text_s)
            if m:
                meta[f"PDF_{tag}"] = m.group(1)

    return meta


# ==============================================================================
# 2. REAL SQLITE3 DATABASE INSPECTOR & UNALLOCATED RECORD CARVER
# ==============================================================================

def inspect_real_sqlite_bytes(raw_bytes: bytes) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Membuka file biner SQLite3 asli menggunakan mesin sqlite3 Python,
    membaca seluruh tabel/baris aktif, dan memindai halaman biner untuk memulihkan teks terhapus.
    """
    info: Dict[str, Any] = {}
    recovered_records: List[Dict[str, Any]] = []

    if not raw_bytes.startswith(b"SQLite format 3"):
        return info, recovered_records

    # Baca page size & versi dari header 100-byte SQLite3
    page_size = struct.unpack(">H", raw_bytes[16:18])[0]
    if page_size == 1:
        page_size = 65536
    total_pages = len(raw_bytes) // max(512, page_size)
    freelist_trunk_page = struct.unpack(">I", raw_bytes[32:36])[0]
    freelist_count = struct.unpack(">I", raw_bytes[36:40])[0]

    info["SQLiteHeader"] = "SQLite format 3 (Verified Real Binary DB)"
    info["PageSizeBytes"] = page_size
    info["TotalPages"] = total_pages
    info["FreelistPagesCount"] = freelist_count

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        tf.write(raw_bytes)
        tmp_path = tf.name

    try:
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        tables = [
            r["name"]
            for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        ]
        info["DiscoveredTables"] = ", ".join(tables) if tables else "None"

        active_bytes_seen = set()
        for tbl in tables[:5]:
            rows = cur.execute(f'SELECT * FROM "{tbl}" LIMIT 15').fetchall()
            for r_idx, row in enumerate(rows):
                row_dict = dict(row)
                summary = " | ".join(f"{k}: {v}" for k, v in row_dict.items())
                for v in row_dict.values():
                    if isinstance(v, str) and len(v) > 4:
                        active_bytes_seen.add(v)
                recovered_records.append({
                    "rowid": row_dict.get("id", r_idx + 1),
                    "status": f"ACTIVE_TABLE_ROW ({tbl})",
                    "timestamp": str(row_dict.get("timestamp", row_dict.get("created_at", "DB_RECORD"))),
                    "sender": str(row_dict.get("sender", row_dict.get("user", tbl))),
                    "message": summary[:220],
                })
        conn.close()
    except Exception as exc:
        info["SQLiteParseNote"] = str(exc)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Carve string dari ruang biner yang tidak ada di baris aktif (Deleted / Unallocated Carving)
    ascii_strings = re.findall(rb"[\x20-\x7e]{14,180}", raw_bytes[100:])
    for s_bytes in ascii_strings:
        s_str = s_bytes.decode("utf-8", errors="ignore").strip()
        if s_str.startswith("CREATE TABLE") or s_str.startswith("CREATE INDEX"):
            continue
        if s_str not in active_bytes_seen and any(k in s_str.lower() for k in ("deleted", "secret", "dermaga", "c2", "+62", "http", "gardu", "priok", "chat", "token")):
            recovered_records.append({
                "rowid": "CARVED_HEX",
                "status": "CARVED_UNALLOCATED_FREELIST_BYTES",
                "timestamp": "UNALLOCATED_PAGE",
                "sender": "RAW_PAGE_CARVER",
                "message": s_str[:220],
            })

    return info, recovered_records[:20]


def generate_real_sample_sqlite_bytes() -> bytes:
    """Membangun file biner SQLite3 asli lengkap dengan tabel pesan & jejak byte terhapus."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        tmp_path = tf.name
    try:
        conn = sqlite3.connect(tmp_path)
        conn.execute("PRAGMA secure_delete = OFF;")
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, timestamp TEXT, sender TEXT, message TEXT);"
        )
        conn.execute(
            "INSERT INTO messages VALUES (101, '2026-10-22 00:45:10', 'Pengirim A (contoh)', 'Pesan contoh pertama untuk memperagakan basis data pesan.');"
        )
        conn.execute(
            "INSERT INTO messages VALUES (102, '2026-10-22 01:12:44', 'Pengirim B (contoh)', 'Pesan contoh kedua — isi dummy untuk peragaan, bukan data nyata.');"
        )
        conn.execute(
            "INSERT INTO messages VALUES (103, '2026-10-22 01:28:00', 'Pengirim A (contoh)', '[CONTOH] Baris ini sengaja dihapus untuk memperagakan pemulihan byte dari halaman terhapus.');"
        )
        conn.commit()
        # Hapus baris 103 dengan secure_delete=OFF sehingga byte-nya tetap tertinggal di halaman biner!
        conn.execute("DELETE FROM messages WHERE id = 103;")
        conn.commit()
        conn.close()
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==============================================================================
# 3. REAL PCAP NETWORK PACKET PARSER (libpcap Binary Header + Ethernet/IPv4/TCP)
# ==============================================================================

def inspect_real_pcap_bytes(raw_bytes: bytes) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Membedah file biner .pcap (libpcap) asli dan mengekstrak sesi paket IPv4/TCP/UDP."""
    info: Dict[str, Any] = {}
    packets: List[Dict[str, Any]] = []

    if len(raw_bytes) < 24:
        return info, packets

    magic = raw_bytes[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        return info, packets

    ver_maj, ver_min, _, _, snaplen, network = struct.unpack(endian + "HHIIII", raw_bytes[4:24])
    info["PCAPFormat"] = f"libpcap v{ver_maj}.{ver_min} (SnapLen: {snaplen}, LinkType: {network})"

    pos = 24
    pkt_num = 0
    while pos + 16 <= len(raw_bytes) and pkt_num < 30:
        ts_sec, ts_usec, incl_len, orig_len = struct.unpack(endian + "IIII", raw_bytes[pos : pos + 16])
        pos += 16
        pkt_data = raw_bytes[pos : pos + incl_len]
        pos += incl_len
        pkt_num += 1

        # Ethernet (14 bytes) + IPv4 (20 bytes)
        if network == 1 and len(pkt_data) >= 34:
            eth_proto = struct.unpack(">H", pkt_data[12:14])[0]
            if eth_proto == 0x0800:  # IPv4
                ip_hdr = pkt_data[14:34]
                proto = ip_hdr[9]
                src_ip = socket.inet_ntoa(ip_hdr[12:16])
                dst_ip = socket.inet_ntoa(ip_hdr[16:20])
                ihl = (ip_hdr[0] & 0x0F) * 4
                l4_data = pkt_data[14 + ihl :]

                sport, dport = 0, 0
                if proto in (6, 17) and len(l4_data) >= 4:
                    sport, dport = struct.unpack(">HH", l4_data[:4])
                proto_name = {6: "TCP", 17: "UDP", 1: "ICMP"}.get(proto, f"IP/{proto}")
                payload_ascii = re.sub(rb"[^\x20-\x7e]", b".", l4_data[8:88]).decode("ascii", errors="ignore")

                packets.append({
                    "rowid": pkt_num,
                    "status": f"PCAP_{proto_name}_PACKET ({orig_len}B)",
                    "timestamp": f"EPOCH+{ts_sec}.{ts_usec:06d}",
                    "sender": f"{src_ip}:{sport} -> {dst_ip}:{dport}",
                    "message": f"Payload: {payload_ascii}",
                })

    info["TotalPacketsParsed"] = pkt_num
    return info, packets


def generate_real_sample_pcap_bytes() -> bytes:
    """Membangun file biner libpcap (.pcap) asli dengan frame Ethernet + IPv4 + TCP C2."""
    global_hdr = struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    chunks = [global_hdr]

    sample_flows = [
        ("198.51.100.23", "10.88.14.20", 8901, 49152, b"SAMPLE_TCP_PAYLOAD_UNTUK_PERAGAAN_PCAP_FORENSIK"),
        ("203.0.113.45", "10.88.14.22", 2775, 8901, b"SAMPLE_FLOW_KEDUA_PAYLOAD_DUMMY_PERAGAAN"),
    ]
    ts = 1792660000
    for src_s, dst_s, sp, dp, payload in sample_flows:
        eth = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\x08\x00"
        ip = struct.pack(
            ">BBHHHBBH4s4s",
            0x45,
            0,
            20 + 20 + len(payload),
            1234,
            0,
            64,
            6,
            0,
            socket.inet_aton(src_s),
            socket.inet_aton(dst_s),
        )
        tcp = struct.pack(">HHIIBBHHH", sp, dp, 1, 1, 0x50, 0x18, 8192, 0, 0)
        frame = eth + ip + tcp + payload
        pkt_hdr = struct.pack("<IIII", ts, 120000, len(frame), len(frame))
        chunks.append(pkt_hdr + frame)
        ts += 2

    return b"".join(chunks)
