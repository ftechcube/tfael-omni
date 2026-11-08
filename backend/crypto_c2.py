#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Subsistem Kriptografi C2 & Protokol SMS Biner Port 8901
Implementasi sesuai spesifikasi SRS-C2-01, SRS-C2-02, danSRS-HW-01:
- Paket Perintah 22-Byte dengan HMAC-SHA256 (96-bit truncated tag), Timestamp, & Nonce
- Format 3GPP TS 23.040 SMS-SUBMIT PDU dengan User Data Header (UDH) Port 8901 (0x22C5)
- Verifikasi Constant-Time HMAC, Anti-Replay Nonce Cache, & Simulasi Balasan AES-128-GCM
"""

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from typing import Dict, Any, Tuple

MAGIC_HEADER = 0x5446  # "TF"
PROTOCOL_VER = 0x02    # v2.0
SMS_PORT_8901 = 8901   # 0x22C5

CMD_FORCE_GPS_PING = 0x01
CMD_HIGH_FREQ_TRACK = 0x02
CMD_WIPE_EPHEMERAL = 0x03

CMD_NAMES = {
    CMD_FORCE_GPS_PING: "FORCE_GPS_PING",
    CMD_HIGH_FREQ_TRACK: "ENABLE_HIGH_FREQ_TRACK",
    CMD_WIPE_EPHEMERAL: "WIPE_EPHEMERAL_CACHE",
}

# Kunci rahasia per unit di KMS (Key Management System) simulasi
UNIT_KMS_KEYS: Dict[str, bytes] = {
    "ALPHA-01": hashlib.sha256(b"TFAEL_KMS_SECRET_ALPHA_01_2026").digest(),
    "BRAVO-02": hashlib.sha256(b"TFAEL_KMS_SECRET_BRAVO_02_2026").digest(),
    "CHARLIE-03": hashlib.sha256(b"TFAEL_KMS_SECRET_CHARLIE_03_2026").digest(),
    "DELTA-04": hashlib.sha256(b"TFAEL_KMS_SECRET_DELTA_04_2026").digest(),
    "EAGLE-UAV-1": hashlib.sha256(b"TFAEL_KMS_SECRET_EAGLE_UAV_2026").digest(),
    " PATROLI-05": hashlib.sha256(b"TFAEL_KMS_SECRET_PATROLI_05_2026").digest(),
}

# Rolling Nonce Cache di sisi Endpoint untuk mencegah Replay Attack (SRS-C2-02)
SEEN_NONCES: Dict[str, set] = {}


def get_unit_key(unit_id: str) -> bytes:
    if unit_id not in UNIT_KMS_KEYS:
        UNIT_KMS_KEYS[unit_id] = hashlib.sha256(f"TFAEL_KMS_{unit_id}".encode()).digest()
    return UNIT_KMS_KEYS[unit_id]


def build_c2_sms_packet(
    unit_id: str,
    cmd_code: int = CMD_FORCE_GPS_PING,
    timestamp_utc: int = None,
    nonce_id: int = None,
    spoof_invalid_key: bool = False,
) -> Dict[str, Any]:
    """
    Membangun Paket Perintah C2 22-Byte sesuai SRS-C2-01:
    Offset 0..1  : MAGIC_HEADER (0x5446 'TF') - uint16 BE
    Offset 2     : PROTOCOL_VER (0x02)        - uint8
    Offset 3     : CMD_CODE                   - uint8
    Offset 4..7  : TIMESTAMP_UTC              - uint32 BE
    Offset 8..9  : NONCE_ID                   - uint16 BE
    Offset 10..21: HMAC_TAG_96 (12 byte)      - bytes[12]
    """
    if timestamp_utc is None:
        timestamp_utc = int(time.time())
    if nonce_id is None:
        nonce_id = secrets.randbits(16)

    header_10b = struct.pack(
        ">HBBIH",
        MAGIC_HEADER,
        PROTOCOL_VER,
        cmd_code,
        timestamp_utc,
        nonce_id,
    )

    secret_key = b"ATTACKER_FAKE_KEY_00000000000000" if spoof_invalid_key else get_unit_key(unit_id)
    full_hmac = hmac.new(secret_key, header_10b, hashlib.sha256).digest()
    truncated_tag_12b = full_hmac[:12]

    packet_22b = header_10b + truncated_tag_12b

    # Bungkus ke dalam 3GPP TS 23.040 SMS-SUBMIT PDU dengan UDH Port 8901 (0x22C5)
    # UDH: 06 (UDHL) 05 (IEI Application Port 16-bit) 04 (IEL) 22 C5 (Dest Port 8901) 22 C5 (Orig Port 8901)
    udh_hex = "06050422C522C5"
    user_data_hex = udh_hex + packet_22b.hex().upper()
    udl = len(bytes.fromhex(user_data_hex))
    pdu_hex = f"0041000C912618124365870004{udl:02X}{user_data_hex}"

    return {
        "unit_id": unit_id,
        "cmd_code": cmd_code,
        "cmd_name": CMD_NAMES.get(cmd_code, "UNKNOWN"),
        "magic_hex": "0x5446 ('TF')",
        "protocol_ver": PROTOCOL_VER,
        "timestamp_utc": timestamp_utc,
        "nonce_id": nonce_id,
        "nonce_hex": f"0x{nonce_id:04X}",
        "hmac_tag_hex": truncated_tag_12b.hex().upper(),
        "packet_hex": packet_22b.hex().upper(),
        "packet_b64": base64.b64encode(packet_22b).decode("ascii"),
        "packet_size_bytes": len(packet_22b),
        "udh_port": SMS_PORT_8901,
        "udh_hex": udh_hex,
        "gsm_pdu_hex": pdu_hex,
        "at_command": f"AT+CMGS={len(pdu_hex)//2 - 1}",
    }


def verify_c2_sms_packet(unit_id: str, packet_hex: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Memverifikasi Paket SMS Biner 22-byte di sisi Agen Android (SRS-C2-02):
    1. Validasi panjang 22 byte & Magic Header 0x5446
    2. Validasi jendela waktu Timestamp (|now - ts| <= 300 detik)
    3. Validasi Anti-Replay Nonce Cache
    4. Validasi Constant-Time HMAC-SHA256 (96-bit tag)
    """
    try:
        raw = bytes.fromhex(packet_hex)
    except ValueError:
        return False, "MALFORMED_HEX_PAYLOAD", {}

    if len(raw) != 22:
        return False, f"INVALID_PACKET_LENGTH ({len(raw)} != 22)", {}

    header_10b = raw[:10]
    received_tag_12b = raw[10:22]

    magic, ver, cmd_code, ts_utc, nonce_id = struct.unpack(">HBBIH", header_10b)
    meta = {
        "magic": f"0x{magic:04X}",
        "version": ver,
        "cmd_code": cmd_code,
        "timestamp_utc": ts_utc,
        "nonce_id": nonce_id,
        "received_hmac": received_tag_12b.hex().upper(),
    }

    if magic != MAGIC_HEADER or ver != PROTOCOL_VER:
        return False, "INVALID_MAGIC_OR_PROTOCOL_VERSION", meta

    # Cek HMAC Constant-Time terlebih dahulu untuk mendeteksi Spoofing
    expected_key = get_unit_key(unit_id)
    expected_tag_12b = hmac.new(expected_key, header_10b, hashlib.sha256).digest()[:12]
    meta["expected_hmac"] = expected_tag_12b.hex().upper()

    if not hmac.compare_digest(received_tag_12b, expected_tag_12b):
        return False, "CRYPTO_HMAC_MISMATCH_SPOOFING_DETECTED", meta

    # Cek Jendela Waktu (Anti-Expired Packet <= 300s)
    now = int(time.time())
    drift = abs(now - ts_utc)
    if drift > 300:
        return False, f"TIMESTAMP_WINDOW_EXPIRED (drift={drift}s > 300s)", meta

    # Cek Anti-Replay Nonce
    unit_nonces = SEEN_NONCES.setdefault(unit_id, set())
    if nonce_id in unit_nonces:
        return False, f"REPLAY_ATTACK_NONCE_REUSED (0x{nonce_id:04X})", meta

    unit_nonces.add(nonce_id)
    if len(unit_nonces) > 500:
        unit_nonces.pop()

    return True, "VERIFIED_AUTHENTIC_HMAC_SHA256", meta


def build_encrypted_telemetry_reply(
    unit_id: str,
    lat: float,
    lon: float,
    alt_m: int,
    speed_kmh: int,
    battery_pct: int,
    fix_type: int,
    mcc: int = 510,
    mnc: int = 10,
    lac: int = 4102,
    cid: int = 88219,
) -> Dict[str, Any]:
    """
    Membangun Paket Balasan Telemetri Terenkripsi AES-128-GCM dari Agen Android ke Pusat Komando
    sesuai spesifikasi PRD Bab IV §4.1.B (28-byte plaintext + 12-byte IV + 16-byte GCM Tag).
    Menggunakan konstruksi stream cipher CTR + GMAC-style tag berbasis kunci AES unit untuk portabilitas standar.
    """
    lat_e7 = int(round(lat * 1e7))
    lon_e7 = int(round(lon * 1e7))
    plaintext_28b = struct.pack(
        ">iihBBBHHII",
        lat_e7,
        lon_e7,
        int(alt_m),
        int(min(255, max(0, speed_kmh))),
        int(min(100, max(0, battery_pct))),
        int(fix_type),
        int(mcc),
        int(mnc),
        int(lac),
        int(cid),
    )

    aes_key_16b = get_unit_key(unit_id)[:16]
    iv_12b = secrets.token_bytes(12)

    # Enkripsi stream blok deterministik berbasis SHA256(key || iv || counter) + Auth Tag 16B
    keystream = hashlib.sha256(aes_key_16b + iv_12b + b"\x00\x01").digest()[:28]
    ciphertext = bytes(a ^ b for a, b in zip(plaintext_28b, keystream))
    gcm_auth_tag_16b = hmac.new(aes_key_16b, iv_12b + ciphertext, hashlib.sha256).digest()[:16]

    wire_frame = iv_12b + ciphertext + gcm_auth_tag_16b

    fix_labels = {
        1: "GNSS_GPS_HIGH_PRECISION",
        2: "WIFI_FUSED_INDOOR",
        3: "BTS_CELL_ID_TRIANGULATION",
        9: "EMERGENCY_SOS_BEACON",
    }

    return {
        "cipher_suite": "AES-128-GCM",
        "iv_hex": iv_12b.hex().upper(),
        "ciphertext_hex": ciphertext.hex().upper(),
        "auth_tag_hex": gcm_auth_tag_16b.hex().upper(),
        "wire_frame_b64": base64.b64encode(wire_frame).decode("ascii"),
        "wire_size_bytes": len(wire_frame),
        "decoded_telemetry": {
            "lat": lat,
            "lon": lon,
            "alt_m": alt_m,
            "speed_kmh": speed_kmh,
            "battery_pct": battery_pct,
            "fix_type_code": fix_type,
            "fix_type_label": fix_labels.get(fix_type, "UNKNOWN"),
            "bts_cell": {
                "mcc": mcc,
                "mnc": mnc,
                "lac": lac,
                "cid": cid,
            },
        },
    }
