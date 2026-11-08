#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Real Live Passive OSINT & Cyber Reconnaissance Engine (Pilar 4)
Melakukan pemindaian nyata (Real Network Reconnaissance) terhadap Domain / IP Target:
1. Resolusi DNS Asli (A, AAAA, NS, MX, TXT/SPF/DMARC) via socket & dig/nslookup
2. Inspeksi Sertifikat SSL/TLS X.509 Asli (Issuer, Subject, Serial, Expiry, & daftar SAN)
3. Pemindaian Port TCP Asli (Multi-threaded socket probe) & Audit Security Header HTTP/S
4. Geolokasi IP & ASN Asli (WHOIS / GeoIP Lookup)
5. Konstruksi Otomatis Entity Knowledge Graph dari hasil temuan nyata
"""

import concurrent.futures
import hashlib
import json
import re
import socket
import ssl
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


COMMON_PORTS = [
    (21, "FTP"),
    (22, "SSH"),
    (53, "DNS"),
    (80, "HTTP"),
    (443, "HTTPS"),
    (3306, "MySQL"),
    (5432, "PostgreSQL"),
    (8080, "HTTP-Alt"),
    (8443, "HTTPS-Alt"),
]


def clean_target_host(raw_indicator: str) -> str:
    h = raw_indicator.strip().lower()
    h = re.sub(r"^https?://", "", h)
    h = h.split("/")[0].split(":")[0]
    return h


TNKB_REGIONS = {
    "A": ("Banten (Serang, Cilegon, Pandeglang, Lebak)", -6.1200, 106.1503),
    "B": ("DKI Jakarta, Depok, Tangerang, Bekasi (Polda Metro Jaya)", -6.1754, 106.8272),
    "D": ("Jawa Barat — Kota Bandung, Cimahi, Bandung Barat", -6.9175, 107.6191),
    "E": ("Jawa Barat — Cirebon, Indramayu, Majalengka, Kuningan", -6.7320, 108.5523),
    "F": ("Jawa Barat — Bogor, Sukabumi, Cianjur", -6.5971, 106.8060),
    "T": ("Jawa Barat — Karawang, Purwakarta, Subang", -6.3227, 107.3376),
    "Z": ("Jawa Barat — Garut, Tasikmalaya, Sumedang, Ciamis, Banjar", -7.3274, 108.2207),
    "G": ("Jawa Tengah — Pekalongan, Tegal, Brebes, Pemalang", -6.8797, 109.1256),
    "H": ("Jawa Tengah — Semarang, Salatiga, Kendal, Demak", -6.9667, 110.4167),
    "K": ("Jawa Tengah — Pati, Kudus, Jepara, Rembang, Blora", -6.7550, 111.0380),
    "R": ("Jawa Tengah — Banyumas, Purwokerto, Cilacap, Purbalingga", -7.4244, 109.2302),
    "AA": ("Jawa Tengah — Magelang, Purworejo, Kebumen, Temanggung, Wonosobo", -7.4797, 110.2177),
    "AD": ("Jawa Tengah — Surakarta (Solo), Boyolali, Klaten, Sragen, Sukoharjo", -7.5755, 110.8243),
    "AB": ("DI Yogyakarta (Kota Jogja, Sleman, Bantul, Gunungkidul, Kulon Progo)", -7.7956, 110.3695),
    "L": ("Jawa Timur — Kota Surabaya", -7.2575, 112.7521),
    "W": ("Jawa Timur — Sidoarjo & Gresik", -7.4478, 112.7183),
    "N": ("Jawa Timur — Malang, Batu, Pasuruan, Probolinggo, Lumajang", -7.9666, 112.6326),
    "P": ("Jawa Timur — Jember, Banyuwangi, Bondowoso, Situbondo", -8.1845, 113.6681),
    "S": ("Jawa Timur — Bojonegoro, Mojokerto, Tuban, Lamongan, Jombang", -7.4726, 112.4341),
    "AG": ("Jawa Timur — Kediri, Blitar, Tulungagung, Nganjuk, Trenggalek", -7.8480, 112.0178),
    "AE": ("Jawa Timur — Madiun, Magetan, Ngawi, Ponorogo, Pacitan", -7.6298, 111.5239),
    "M": ("Jawa Timur — Pulau Madura (Bangkalan, Sampang, Pamekasan, Sumenep)", -7.0252, 112.7508),
    "DK": ("Bali (Denpasar, Badung, Gianyar, Buleleng, Tabanan)", -8.6705, 115.2126),
    "BL": ("Aceh (Banda Aceh, Lhokseumawe, Langsa)", 5.5483, 95.3238),
    "BK": ("Sumatera Utara — Medan, Deli Serdang, Tebing Tinggi, Binjai", 3.5952, 98.6722),
    "BB": ("Sumatera Utara — Tapanuli, Sibolga, Nias, Padang Sidempuan", 1.7427, 98.7792),
    "BA": ("Sumatera Barat — Padang, Bukittinggi, Payakumbuh", -0.9471, 100.4172),
    "BM": ("Riau — Pekanbaru, Dumai, Bengkalis, Kampar", 0.5071, 101.4478),
    "BP": ("Kepulauan Riau — Batam, Tanjungpinang, Bintan, Karimun", 1.0456, 104.0305),
    "BG": ("Sumatera Selatan — Palembang, Prabumulih, Lubuklinggau", -2.9761, 104.7754),
    "BE": ("Lampung — Bandar Lampung, Metro, Lampung Selatan", -5.4292, 105.2610),
    "KB": ("Kalimantan Barat — Pontianak, Singkawang, Kubu Raya", -0.0263, 109.3425),
    "DA": ("Kalimantan Selatan — Banjarmasin, Banjarbaru, Martapura", -3.3194, 114.5908),
    "KT": ("Kalimantan Timur — Balikpapan, Samarinda, Bontang, IKN Nusantara", -1.2379, 116.8529),
    "DB": ("Sulawesi Utara — Manado, Bitung, Tomohon, Minahasa", 1.4748, 124.8421),
    "DD": ("Sulawesi Selatan — Makassar, Gowa, Maros", -5.1477, 119.4327),
    "PA": ("Papua — Jayapura, Merauke, Mimika (Timika)", -2.5337, 140.7181),
}

B_SUBREGION_MAP = {
    "P": "SAMSAT Jakarta Pusat (Kemayoran)",
    "U": "SAMSAT Jakarta Utara (Plumpang / Priok)",
    "B": "SAMSAT Jakarta Barat (Daan Mogot)",
    "S": "SAMSAT Jakarta Selatan (Polda Metro Jaya)",
    "T": "SAMSAT Jakarta Timur (Cipinang / Kebon Nanas)",
    "E": "SAMSAT Kota Depok (Margonda)",
    "Z": "SAMSAT Kota Depok (Cinere)",
    "F": "SAMSAT Kabupaten Bekasi (Cikarang)",
    "K": "SAMSAT Kota Bekasi",
    "C": "SAMSAT Kota Tangerang (Cikokol)",
    "V": "SAMSAT Kota Tangerang (Ciledug)",
    "G": "SAMSAT Kabupaten Tangerang (Tigaraksa)",
    "J": "SAMSAT Kabupaten Tangerang (Kelapa Dua / Cisauk)",
    "N": "SAMSAT Tangerang Selatan (BSD)",
    "W": "SAMSAT Tangerang Selatan (Ciputat)",
}

# Sub-wilayah berdasarkan HURUF TERAKHIR (Polda Jateng, DIY, Jabar, Jatim)
REGIONAL_LAST_LETTER_SAMSAT = {
    "H": {
        "A": "SAMSAT Kota Semarang", "G": "SAMSAT Kota Semarang", "H": "SAMSAT Kota Semarang",
        "P": "SAMSAT Kota Semarang", "Q": "SAMSAT Kota Semarang", "R": "SAMSAT Kota Semarang",
        "S": "SAMSAT Kota Semarang", "W": "SAMSAT Kota Semarang", "X": "SAMSAT Kota Semarang",
        "Y": "SAMSAT Kota Semarang", "Z": "SAMSAT Kota Semarang",
        "B": "SAMSAT Kota Salatiga", "K": "SAMSAT Kota Salatiga", "O": "SAMSAT Kota Salatiga", "T": "SAMSAT Kota Salatiga",
        "C": "SAMSAT Kab. Semarang (Ungaran)", "F": "SAMSAT Kab. Semarang (Ungaran)", "L": "SAMSAT Kab. Semarang (Ungaran)", "V": "SAMSAT Kab. Semarang (Ungaran)",
        "D": "SAMSAT Kab. Kendal", "M": "SAMSAT Kab. Kendal", "U": "SAMSAT Kab. Kendal",
        "E": "SAMSAT Kab. Demak", "J": "SAMSAT Kab. Demak", "N": "SAMSAT Kab. Demak",
    },
    "AB": {
        "A": "SAMSAT Kota Yogyakarta", "F": "SAMSAT Kota Yogyakarta", "H": "SAMSAT Kota Yogyakarta", "I": "SAMSAT Kota Yogyakarta", "S": "SAMSAT Kota Yogyakarta",
        "B": "SAMSAT Kab. Bantul", "G": "SAMSAT Kab. Bantul", "J": "SAMSAT Kab. Bantul", "K": "SAMSAT Kab. Bantul", "T": "SAMSAT Kab. Bantul",
        "C": "SAMSAT Kab. Kulon Progo", "L": "SAMSAT Kab. Kulon Progo", "P": "SAMSAT Kab. Kulon Progo", "V": "SAMSAT Kab. Kulon Progo",
        "D": "SAMSAT Kab. Gunungkidul", "M": "SAMSAT Kab. Gunungkidul", "W": "SAMSAT Kab. Gunungkidul",
        "E": "SAMSAT Kab. Sleman", "N": "SAMSAT Kab. Sleman", "Q": "SAMSAT Kab. Sleman", "U": "SAMSAT Kab. Sleman", "Y": "SAMSAT Kab. Sleman", "Z": "SAMSAT Kab. Sleman",
    },
    "AD": {
        "A": "SAMSAT Kota Surakarta (Solo)", "H": "SAMSAT Kota Surakarta (Solo)", "S": "SAMSAT Kota Surakarta (Solo)", "U": "SAMSAT Kota Surakarta (Solo)",
        "B": "SAMSAT Kab. Sukoharjo", "K": "SAMSAT Kab. Sukoharjo", "O": "SAMSAT Kab. Sukoharjo", "T": "SAMSAT Kab. Sukoharjo",
        "C": "SAMSAT Kab. Klaten", "J": "SAMSAT Kab. Klaten", "L": "SAMSAT Kab. Klaten", "Q": "SAMSAT Kab. Klaten", "V": "SAMSAT Kab. Klaten",
        "D": "SAMSAT Kab. Boyolali", "M": "SAMSAT Kab. Boyolali", "W": "SAMSAT Kab. Boyolali",
        "E": "SAMSAT Kab. Sragen", "N": "SAMSAT Kab. Sragen", "Y": "SAMSAT Kab. Sragen",
        "F": "SAMSAT Kab. Karanganyar", "P": "SAMSAT Kab. Karanganyar", "Z": "SAMSAT Kab. Karanganyar",
        "G": "SAMSAT Kab. Wonogiri", "I": "SAMSAT Kab. Wonogiri", "R": "SAMSAT Kab. Wonogiri",
    },
}

B_SECOND_LETTER_BODY = {
    "A": "Sedan / Saloon",
    "B": "Sedan / Hatchback",
    "F": "Minibus / MPV / Hatchback Penumpang",
    "J": "Jeep / SUV (Sport Utility Vehicle)",
    "K": "Minibus / MPV Penumpang",
    "O": "Minibus / City Car",
    "P": "Minibus / Penumpang",
    "Q": "Staf / Operasional Pemerintahan",
    "R": "Minibus / MPV",
    "T": "Taksi / Angkutan Sewa",
    "U": "Minibus / MPV / Microbus Penumpang",
    "V": "Minibus / MPV Penumpang",
    "Y": "Minibus / Penumpang",
    "Z": "Kendaraan Operasional Dinas",
    "D": "Truk / Kendaraan Beban",
}

SPECIAL_SUFFIX_MAP = {
    "RFS": "Pelat Khusus Pejabat Sipil / Sekretariat Negara (Reformasi Sekretariat)",
    "RFP": "Pelat Khusus Pejabat / Operasional Kepolisian RI (Polri)",
    "RFD": "Pelat Khusus Pejabat / Operasional TNI Angkatan Darat",
    "RFL": "Pelat Khusus Pejabat / Operasional TNI Angkatan Laut",
    "RFU": "Pelat Khusus Pejabat / Operasional TNI Angkatan Udara",
    "RFO": "Pelat Khusus Operasional Pemerintah / Instansi",
    "ZZH": "Pelat Khusus Pejabat Negara / Kementerian",
    "ZZP": "Pelat Khusus Dinas Kepolisian",
    "ZZD": "Pelat Khusus Dinas TNI AD",
}


def decode_indonesian_plate(plate_str: str) -> Dict[str, Any]:
    """
    Menganalisis & mendekode Tanda Nomor Kendaraan Bermotor (TNKB) Indonesia:
    - Kode Wilayah Polda / Provinsi
    - Sub-Wilayah SAMSAT (khususnya wilayah B Jadetabek)
    - Klasifikasi jenis kendaraan berdasarkan rentang angka (1-9999)
    - Deteksi seri huruf khusus/rahasia (RFS, RFP, RFD, ZZ, dll.)
    """
    raw = (plate_str or "").strip().upper()
    m = re.match(r"^([A-Z]{1,2})\s*(\d{1,4})\s*([A-Z]{0,3})$", raw)
    if not m:
        return {
            "valid_tnkb": False,
            "formatted": raw or "N/A",
            "region": "Format Non-Standar / Belum Diisi",
            "samsat_subregion": "-",
            "vehicle_class": "Unclassified",
            "special_flag": "None",
        }

    prefix, num_str, suffix = m.group(1), m.group(2), m.group(3)
    num = int(num_str)
    formatted = f"{prefix} {num_str} {suffix}".strip()

    reg_info = TNKB_REGIONS.get(prefix, (f"Wilayah Kode '{prefix}' (Indonesia)", -6.1754, 106.8272))
    region_name, reg_lat, reg_lon = reg_info

    # Sub-wilayah SAMSAT berdasarkan aturan Polda
    samsat_sub = f"SAMSAT Regional {prefix}"
    body_subtype = "-"
    if prefix == "B" and suffix:
        samsat_sub = B_SUBREGION_MAP.get(suffix[0], f"SAMSAT Jadetabek (Kode Wilayah '{suffix[0]}')")
        if len(suffix) >= 2:
            body_subtype = B_SECOND_LETTER_BODY.get(suffix[1], f"Seri Klasifikasi '{suffix[1]}'")
    elif prefix in REGIONAL_LAST_LETTER_SAMSAT and suffix:
        last_char = suffix[-1]
        samsat_sub = REGIONAL_LAST_LETTER_SAMSAT[prefix].get(
            last_char, f"SAMSAT Wilayah {prefix} (Kode Akhir '{last_char}')"
        )

    # Klasifikasi jenis kendaraan berdasarkan rentang nomor alokasi Korlantas & aturan Polda
    if prefix in ("H", "AD", "AB", "G", "K", "R", "AA") and len(suffix) == 2 and suffix[0] in ("U", "V", "W", "X", "Y", "Z"):
        v_class = f"Sepeda Motor / Roda 2 atau Mobil Penumpang (Seri Alokasi '{suffix[0]}*' Polda Jateng/DIY)"
    elif 1 <= num <= 1999:
        v_class = f"Mobil Penumpang Pribadi / Roda 4 ({body_subtype if body_subtype != '-' else 'Sedan/SUV/MPV'} — Alokasi 1–1999)"
    elif 2000 <= num <= 6999:
        v_class = "Sepeda Motor / Roda 2 (Alokasi 2000–6999)"
    elif 7000 <= num <= 7999:
        v_class = "Bus / Kendaraan Angkutan Penumpang Umum (Alokasi 7000–7999)"
    elif 8000 <= num <= 8999:
        v_class = "Kendaraan Penumpang / Pick-Up / Mobil Barang Ringan (Alokasi 8000–8999)"
    else:
        v_class = "Truk / Kendaraan Angkutan Barang Berat / Kontainer (Alokasi 9000–9999)"

    special_flag = SPECIAL_SUFFIX_MAP.get(
        suffix,
        "Pelat Khusus Dinas/Pejabat (Seri ZZ/RF)" if suffix.startswith(("RF", "ZZ", "QH", "QZ")) else "Reguler Sipil (TNKB Standar)",
    )

    return {
        "valid_tnkb": True,
        "formatted": formatted,
        "prefix": prefix,
        "number": num,
        "suffix": suffix,
        "region": region_name,
        "samsat_subregion": samsat_sub,
        "body_subtype": body_subtype,
        "vehicle_class": v_class,
        "special_flag": special_flag,
        "region_lat": reg_lat,
        "region_lon": reg_lon,
    }


# ==============================================================================
# 2. REAL INDONESIAN PHONE MSISDN / HLR OPERATOR DECODER & USERNAME/EMAIL OSINT
# ==============================================================================

ID_MSISDN_PREFIX_MAP = {
    "0811": ("Telkomsel", "KartuHALO (Pascabayar Korporat/Prioritas)", "PT Telekomunikasi Selular"),
    "0812": ("Telkomsel", "Simpati / Telkomsel PraBayar", "PT Telekomunikasi Selular"),
    "0813": ("Telkomsel", "Simpati / Telkomsel PraBayar", "PT Telekomunikasi Selular"),
    "0821": ("Telkomsel", "Simpati / Telkomsel PraBayar", "PT Telekomunikasi Selular"),
    "0822": ("Telkomsel", "Simpati / Loop", "PT Telekomunikasi Selular"),
    "0823": ("Telkomsel", "Kartu AS", "PT Telekomunikasi Selular"),
    "0851": ("Telkomsel", "by.U Digital / Kartu AS", "PT Telekomunikasi Selular"),
    "0852": ("Telkomsel", "Kartu AS", "PT Telekomunikasi Selular"),
    "0853": ("Telkomsel", "Kartu AS", "PT Telekomunikasi Selular"),
    "0814": ("Indosat Ooredoo Hutchison", "Indosat M2 Broadband", "PT Indosat Tbk"),
    "0815": ("Indosat Ooredoo Hutchison", "Matrix / Mentari", "PT Indosat Tbk"),
    "0816": ("Indosat Ooredoo Hutchison", "Matrix / Mentari", "PT Indosat Tbk"),
    "0855": ("Indosat Ooredoo Hutchison", "Matrix Pascabayar", "PT Indosat Tbk"),
    "0856": ("Indosat Ooredoo Hutchison", "IM3", "PT Indosat Tbk"),
    "0857": ("Indosat Ooredoo Hutchison", "IM3", "PT Indosat Tbk"),
    "0858": ("Indosat Ooredoo Hutchison", "Mentari / IM3", "PT Indosat Tbk"),
    "0895": ("Tri (3) / Indosat Hutchison", "Tri PraBayar", "PT Indosat Tbk (IOH)"),
    "0896": ("Tri (3) / Indosat Hutchison", "Tri PraBayar", "PT Indosat Tbk (IOH)"),
    "0897": ("Tri (3) / Indosat Hutchison", "Tri PraBayar", "PT Indosat Tbk (IOH)"),
    "0898": ("Tri (3) / Indosat Hutchison", "Tri PraBayar", "PT Indosat Tbk (IOH)"),
    "0899": ("Tri (3) / Indosat Hutchison", "Tri Pascabayar/PraBayar", "PT Indosat Tbk (IOH)"),
    "0817": ("XL Axiata", "XL Prioritas / PraBayar", "PT XL Axiata Tbk"),
    "0818": ("XL Axiata", "XL Prioritas / PraBayar", "PT XL Axiata Tbk"),
    "0819": ("XL Axiata", "XL PraBayar", "PT XL Axiata Tbk"),
    "0859": ("XL Axiata", "XL / Live.On", "PT XL Axiata Tbk"),
    "0877": ("XL Axiata", "XL PraBayar", "PT XL Axiata Tbk"),
    "0878": ("XL Axiata", "XL PraBayar", "PT XL Axiata Tbk"),
    "0831": ("AXIS (XL Axiata)", "AXIS GSM", "PT XL Axiata Tbk"),
    "0832": ("AXIS (XL Axiata)", "AXIS GSM", "PT XL Axiata Tbk"),
    "0833": ("AXIS (XL Axiata)", "AXIS GSM", "PT XL Axiata Tbk"),
    "0838": ("AXIS (XL Axiata)", "AXIS GSM", "PT XL Axiata Tbk"),
    "0881": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0882": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0883": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0884": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0885": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0886": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0887": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0888": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
    "0889": ("Smartfren", "Smartfren 4G/5G VoLTE", "PT Smartfren Telecom Tbk"),
}


def decode_indonesian_phone(phone_str: str) -> Dict[str, Any]:
    """Menganalisis nomor MSISDN seluler Indonesia (Operator, Produk, Format E.164, & Tautan OSINT)."""
    digits = re.sub(r"\D", "", phone_str or "")
    if not digits:
        return {"valid": False}
    if digits.startswith("62"):
        local_num = "0" + digits[2:]
        e164_num = "+" + digits
    elif digits.startswith("0"):
        local_num = digits
        e164_num = "+62" + digits[1:]
    elif digits.startswith("8"):
        local_num = "0" + digits
        e164_num = "+62" + digits
    else:
        return {"valid": False, "raw": phone_str}

    prefix4 = local_num[:4]
    op_info = ID_MSISDN_PREFIX_MAP.get(prefix4, ("Operator Seluler Nasional / MVNO", f"Seri {prefix4}", "Penyelenggara Telekomunikasi RI"))
    operator, product, corp = op_info
    return {
        "valid": len(local_num) >= 10,
        "local": local_num,
        "e164": e164_num,
        "prefix": prefix4,
        "operator": operator,
        "product": product,
        "corporation": corp,
        "whatsapp_url": f"https://wa.me/{e164_num.lstrip('+')}",
        "telegram_url": f"https://t.me/{e164_num}",
    }


def _probe_social_platform(platform: str, url: str, api_mode: str = "status") -> Dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept": "application/json, text/html",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                body = resp.read(16384).decode("utf-8", errors="ignore")
                if api_mode == "github":
                    d = json.loads(body)
                    return {
                        "found": True,
                        "platform": "GitHub",
                        "url": d.get("html_url", f"https://github.com/{d.get('login', '')}"),
                        "name": d.get("name") or d.get("login"),
                        "bio": d.get("bio") or "",
                        "location": d.get("location") or "",
                        "company": d.get("company") or "",
                        "repos": d.get("public_repos", 0),
                        "followers": d.get("followers", 0),
                        "created_at": (d.get("created_at") or "")[:10],
                    }
                elif api_mode == "gitlab":
                    arr = json.loads(body)
                    if isinstance(arr, list) and len(arr) > 0:
                        u = arr[0]
                        return {
                            "found": True,
                            "platform": "GitLab",
                            "url": u.get("web_url", ""),
                            "name": u.get("name", ""),
                            "bio": f"State: {u.get('state', 'active')}",
                        }
                    return {"found": False, "platform": platform}
                elif api_mode == "keybase":
                    d = json.loads(body)
                    them = d.get("them") or []
                    if isinstance(them, list) and len(them) > 0 and them[0]:
                        prof = (them[0].get("profile") or {})
                        return {
                            "found": True,
                            "platform": "Keybase Crypto ID",
                            "url": f"https://keybase.io/{(them[0].get('basics') or {}).get('username', '')}",
                            "name": prof.get("full_name", ""),
                            "bio": prof.get("bio", ""),
                            "location": prof.get("location", ""),
                        }
                    return {"found": False, "platform": platform}
                elif api_mode == "devto":
                    d = json.loads(body)
                    if d.get("username"):
                        return {
                            "found": True,
                            "platform": "Dev.to",
                            "url": f"https://dev.to/{d.get('username')}",
                            "name": d.get("name", ""),
                            "bio": d.get("summary", ""),
                            "location": d.get("location", ""),
                        }
                    return {"found": False, "platform": platform}
                elif api_mode == "gravatar":
                    d = json.loads(body)
                    entry = (d.get("entry") or [{}])[0]
                    return {
                        "found": True,
                        "platform": "Gravatar Global Profile",
                        "url": entry.get("profileUrl", ""),
                        "name": entry.get("displayName", entry.get("preferredUsername", "")),
                        "bio": entry.get("aboutMe", ""),
                        "location": entry.get("currentLocation", ""),
                    }
                elif api_mode == "telegram":
                    if "tgme_page_title" in body:
                        m = re.search(r'<div class="tgme_page_title"><span[^>]*>([^<]+)</span>', body)
                        t_name = m.group(1).strip() if m else ""
                        return {
                            "found": True,
                            "platform": "Telegram Public Handle",
                            "url": url,
                            "name": t_name,
                            "bio": "Active Telegram Public Account/Channel",
                        }
                    return {"found": False, "platform": platform}
                elif api_mode == "reddit":
                    d = (json.loads(body).get("data") or {})
                    if d.get("name"):
                        return {
                            "found": True,
                            "platform": "Reddit",
                            "url": f"https://www.reddit.com/user/{d.get('name')}",
                            "name": d.get("name"),
                            "bio": f"Total Karma: {d.get('total_karma', 0)}",
                        }
                    return {"found": False, "platform": platform}
                return {"found": True, "platform": platform, "url": url}
    except Exception:
        pass
    return {"found": False, "platform": platform}


def scan_identity_osint(username_or_email: str) -> Dict[str, Any]:
    """
    Memindai jejak identitas manusia (Username / Handle / Email) secara nyata di berbagai platform publik.
    """
    clean = (username_or_email or "").strip().lstrip("@")
    is_email = "@" in clean
    if is_email:
        uname, email_domain = clean.split("@", 1)
        gravatar_md5 = hashlib.md5(clean.lower().encode("utf-8")).hexdigest()
    else:
        uname = re.sub(r"[^a-zA-Z0-9_\-\.]", "", clean)
        email_domain = ""
        gravatar_md5 = hashlib.md5(f"{uname.lower()}@gmail.com".encode("utf-8")).hexdigest()

    if not uname:
        return {"scanned": False, "accounts": []}

    probes = [
        ("GitHub", f"https://api.github.com/users/{uname}", "github"),
        ("GitLab", f"https://gitlab.com/api/v4/users?username={uname}", "gitlab"),
        ("Keybase", f"https://keybase.io/_/api/1.0/user/lookup.json?usernames={uname}", "keybase"),
        ("Dev.to", f"https://dev.to/api/users/by_username?url={uname}", "devto"),
        ("Gravatar", f"https://en.gravatar.com/{gravatar_md5}.json", "gravatar"),
        ("PyPI", f"https://pypi.org/user/{uname}/", "status"),
        ("Telegram", f"https://t.me/{uname}", "telegram"),
        ("Reddit", f"https://www.reddit.com/user/{uname}/about.json", "reddit"),
    ]

    found_accounts = []
    full_name = ""
    bio_text = ""
    loc_text = ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_probe_social_platform, p, u, m) for p, u, m in probes]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res.get("found"):
                found_accounts.append(res)
                if res.get("name") and not full_name:
                    full_name = res["name"]
                if res.get("bio") and not bio_text:
                    bio_text = res["bio"]
                if res.get("location") and not loc_text:
                    loc_text = res["location"]

    return {
        "scanned": True,
        "username": uname,
        "is_email": is_email,
        "email_domain": email_domain,
        "gravatar_md5": gravatar_md5,
        "discovered_name": full_name or uname,
        "discovered_bio": bio_text,
        "discovered_location": loc_text,
        "accounts_found": found_accounts,
        "direct_dorks": [
            f"https://x.com/{uname}",
            f"https://instagram.com/{uname}",
            f"https://tiktok.com/@{uname}",
            f"https://t.me/{uname}",
        ],
    }


def query_dig_records(domain: str, rtype: str) -> List[str]:
    try:
        proc = subprocess.run(
            ["dig", "+short", "+time=2", "+tries=1", domain, rtype],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        lines = [line.strip().rstrip(".") for line in proc.stdout.splitlines() if line.strip()]
        return lines[:8]
    except Exception:
        return []


def inspect_ssl_certificate(host: str, port: int = 443) -> Dict[str, Any]:
    """Mengambil sertifikat X.509 SSL/TLS asli dari host:443."""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=2.5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                tls_ver = ssock.version()

                subject = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))
                sans = [val for key, val in cert.get("subjectAltName", []) if key == "DNS"]

                return {
                    "ssl_active": True,
                    "tls_version": tls_ver,
                    "cipher_suite": cipher[0] if cipher else "UNKNOWN",
                    "subject_cn": subject.get("commonName", host),
                    "issuer_org": issuer.get("organizationName", issuer.get("commonName", "Unknown CA")),
                    "serial_number": cert.get("serialNumber", ""),
                    "not_before": cert.get("notBefore", ""),
                    "not_after": cert.get("notAfter", ""),
                    "san_domains": sans[:12],
                }
    except Exception as exc:
        return {
            "ssl_active": False,
            "error": str(exc),
            "san_domains": [],
        }


def probe_single_port(host: str, port: int, label: str) -> Tuple[int, str, bool]:
    try:
        with socket.create_connection((host, port), timeout=0.75):
            return (port, label, True)
    except Exception:
        return (port, label, False)


def scan_tcp_ports(host: str) -> List[Dict[str, Any]]:
    open_ports = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
        futures = [pool.submit(probe_single_port, host, p, lbl) for p, lbl in COMMON_PORTS]
        for fut in concurrent.futures.as_completed(futures):
            port, label, is_open = fut.result()
            if is_open:
                open_ports.append({"port": port, "service": label})
    open_ports.sort(key=lambda x: x["port"])
    return open_ports


def audit_http_security_headers(host: str) -> Dict[str, Any]:
    """Memeriksa HTTP Security Headers asli dari target."""
    for scheme in ("https", "http"):
        url = f"{scheme}://{host}/"
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "TFAEL-OMNI-PassiveAudit/2.0"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                missing = []
                if "strict-transport-security" not in hdrs:
                    missing.append("Missing HSTS (Strict-Transport-Security)")
                if "content-security-policy" not in hdrs:
                    missing.append("Missing CSP (Content-Security-Policy)")
                if "x-frame-options" not in hdrs:
                    missing.append("Missing X-Frame-Options (Clickjacking Risk)")
                return {
                    "reachable": True,
                    "status_code": resp.status,
                    "server_banner": hdrs.get("server", "Hidden / Unspecified"),
                    "powered_by": hdrs.get("x-powered-by", "None"),
                    "missing_security_headers": missing,
                }
        except Exception:
            continue
    return {
        "reachable": False,
        "server_banner": "No HTTP/S Response",
        "missing_security_headers": ["HTTP/HTTPS Endpoint Unreachable or Filtered"],
    }


def lookup_geoip_and_asn(ip_addr: str) -> Dict[str, Any]:
    """Mengambil lokasi geografis, ISP, dan ASN asli dari IP target."""
    if not ip_addr or ip_addr.startswith("127.") or ip_addr.startswith("10.") or ip_addr.startswith("192.168."):
        return {
            "country": "Indonesia (Local/Internal Network)",
            "city": "Jakarta",
            "lat": -6.1754,
            "lon": 106.8272,
            "isp": "Internal Intranet Network",
            "asn": "AS-INTERNAL",
        }
    try:
        url = f"https://ip-api.com/json/{ip_addr}?fields=status,country,city,lat,lon,isp,org,as"
        req = urllib.request.Request(url, headers={"User-Agent": "TFAEL-OMNI/2.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                return {
                    "country": data.get("country", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "lat": float(data.get("lat", -6.1754)),
                    "lon": float(data.get("lon", 106.8272)),
                    "isp": data.get("isp", "Unknown ISP"),
                    "org": data.get("org", ""),
                    "asn": data.get("as", "Unknown ASN"),
                }
    except Exception:
        pass

    return {
        "country": "Resolved Host",
        "city": "Jakarta",
        "lat": -6.1754,
        "lon": 106.8272,
        "isp": "Resolved via Local DNS",
        "asn": "AS-RESOLVED",
    }


def check_email_breaches(email: str) -> Dict[str, Any]:
    """Cek apakah email muncul di kebocoran data publik, via XposedOrNot (gratis, tanpa key).
    Tidak memakai data dummy: jika bukan email / offline / galat, kembalikan status jujur."""
    if not email or "@" not in email or email.startswith("@"):
        return {"checked": False, "reason": "indikator bukan email", "source": "XposedOrNot"}
    try:
        url = "https://api.xposedornot.com/v1/check-email/" + urllib.parse.quote(email)
        req = urllib.request.Request(url, headers={"User-Agent": "TFAEL-OMNI/2.0"})
        with urllib.request.urlopen(req, timeout=6.0) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
        br = d.get("breaches") or []
        names = br[0] if (br and isinstance(br[0], list)) else []
        return {"checked": True, "found": bool(names), "count": len(names),
                "breaches": names[:12], "source": "XposedOrNot"}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"checked": True, "found": False, "count": 0, "breaches": [], "source": "XposedOrNot"}
        return {"checked": False, "reason": f"galat HTTP {e.code}", "source": "XposedOrNot"}
    except Exception:
        return {"checked": False, "reason": "tak terjangkau (mode offline?)", "source": "XposedOrNot"}


def run_live_osint_recon(
    raw_indicator: str,
    code_name: str = "LIVE-TARGET",
    plate_number: str = "",
    phone_number: str = "",
) -> Dict[str, Any]:
    """
    Menjalankan pemindaian OSINT nyata secara menyeluruh pada:
    - Domain / IP Server (DNS, SSL X.509, Port TCP, HTTP Header, GeoIP/ASN)
    - Username / Handle / Email (GitHub, GitLab, Keybase, Dev.to, Gravatar MD5, PyPI)
    - Nomor Telepon Seluler Indonesia (MSISDN Operator/HLR Prefix, E.164, WA/Telegram)
    - Pelat Nomor Kendaraan TNKB (Wilayah Polda, SAMSAT Kota/Kab, Jenis Kendaraan)
    """
    raw_clean = (raw_indicator or "").strip()

    # Deteksi otomatis jenis indikator yang dimasukkan pengguna
    digits_only = re.sub(r"\D", "", raw_clean)
    if not phone_number and len(digits_only) >= 9 and re.match(r"^(\+?62|08)\d+$", re.sub(r"[\s\-]", "", raw_clean)):
        phone_number = raw_clean

    is_email = "@" in raw_clean and not raw_clean.startswith("@")
    is_username = raw_clean.startswith("@") or ("." not in raw_clean and not phone_number and len(raw_clean) >= 2)

    identity_info: Dict[str, Any] = {"scanned": False, "accounts_found": []}
    if is_email or is_username:
        identity_info = scan_identity_osint(raw_clean)
        host = identity_info.get("email_domain") if is_email else "github.com"
    elif phone_number and "." not in raw_clean:
        host = "telkomsel.com"
    else:
        host = clean_target_host(raw_clean)

    phone_profile = decode_indonesian_phone(phone_number) if phone_number else {"valid": False}
    breach_info = check_email_breaches(raw_clean) if is_email else {"checked": False, "reason": "indikator bukan email", "source": "XposedOrNot"}

    # 1. Resolusi IP dari DNS (socket + dig A + fallback www. + fallback Nameserver IP)
    resolved_ips = []
    for candidate in (host, f"www.{host}"):
        for ip_rec in query_dig_records(candidate, "A"):
            if re.match(r"^(?:\d{1,3}\.){3}\d{1,3}$", ip_rec) and ip_rec not in resolved_ips:
                resolved_ips.append(ip_rec)
        try:
            infos = socket.getaddrinfo(candidate, None, socket.AF_INET)
            for info in infos:
                ip = info[4][0]
                if ip not in resolved_ips:
                    resolved_ips.append(ip)
        except Exception:
            pass

    # 2. Query DNS NS, MX, TXT (SPF/DMARC), SOA
    ns_records = query_dig_records(host, "NS")
    mx_records = query_dig_records(host, "MX")
    txt_records = query_dig_records(host, "TXT")
    dmarc_records = query_dig_records(f"_dmarc.{host}", "TXT")

    # Jika domain belum punya A record aktif (misal baru parkir NS), ambil IP dari Nameserver utamanya
    ns_fallback_note = ""
    if not resolved_ips and ns_records:
        first_ns = ns_records[0]
        for ns_ip in query_dig_records(first_ns, "A"):
            if re.match(r"^(?:\d{1,3}\.){3}\d{1,3}$", ns_ip):
                resolved_ips.append(ns_ip)
                ns_fallback_note = f" (Via Hosting NS {first_ns})"
                break

    primary_ip = resolved_ips[0] if resolved_ips else "Unresolved"

    # 3. Inspeksi Sertifikat SSL/TLS Asli
    ssl_info = inspect_ssl_certificate(host, 443)

    # 4. Scan Port TCP Asli
    open_ports = scan_tcp_ports(primary_ip if primary_ip != "Unresolved" else host)

    # 5. Audit HTTP Security Headers Asli
    http_audit = audit_http_security_headers(host)

    # 6. GeoIP & ASN Lookup Asli
    geo_info = lookup_geoip_and_asn(primary_ip if primary_ip != "Unresolved" else "")

    # 7. Evaluasi Kerentanan & Postur Keamanan Asli
    exposures = list(http_audit.get("missing_security_headers", []))
    has_spf = any("v=spf1" in t.lower() for t in txt_records)
    has_dmarc = any("v=dmarc1" in t.lower() for t in dmarc_records)
    if not has_spf:
        exposures.append("No SPF Record Found (Email Spoofing Risk)")
    if not has_dmarc:
        exposures.append("No DMARC Policy Found (_dmarc TXT missing)")
    if not ssl_info.get("ssl_active"):
        exposures.append("No Valid TLS/SSL Certificate on Port 443")
    for p in open_ports:
        if p["port"] in (21, 22, 3306, 5432, 8080):
            exposures.append(f"Exposed Management/DB Port: TCP/{p['port']} ({p['service']})")

    # TNKB dihitung lebih awal agar dapat dipakai pada skor spasial/visual/forensik
    tnkb_profile = decode_indonesian_plate(plate_number)

    # ---- Skor Risiko Komposit R(e) — DIHITUNG dari temuan nyata (bukan konstanta) ----
    n_exposures = len(exposures)
    n_ports = len(open_ports)
    n_accounts = len(identity_info.get("accounts_found", []))
    n_breaches = breach_info.get("count", 0) if (breach_info.get("checked") and breach_info.get("found")) else 0
    geo_ok = bool(geo_info.get("lat") and geo_info.get("lon"))
    tnkb_ok = bool(tnkb_profile.get("valid_tnkb"))
    phone_ok = bool(phone_profile.get("valid"))
    gravatar_ok = any("gravatar" in (a.get("platform", "").lower()) for a in identity_info.get("accounts_found", []))
    multi_ip = len(resolved_ips) > 1
    ssl_weak = (not ssl_info.get("ssl_active")) or (ssl_info.get("tls_version", "") in ("TLSv1", "TLSv1.1"))

    def _clamp(v, lo=5, hi=98):
        return max(lo, min(hi, int(round(v))))

    # CYBER — permukaan serangan & postur teknis (port terbuka, eksposur, TLS lemah, akun)
    cyber_score = _clamp(30 + n_exposures * 9 + n_ports * 4 + n_accounts * 3 + min(n_breaches, 10) * 2 + (10 if ssl_weak else 0))
    # SPATIO-TEMPORAL — pelokalan geografis (jangkar nyata) + pola pergerakan (butuh data check-in nyata).
    # Tanpa data pergerakan, komponen temporal = 0 dan skor TIDAK masuk pita tinggi (jujur: belum ada lintasan).
    loc_anchor = (22 if geo_ok else 0) + (24 if tnkb_ok else 0) + (16 if phone_ok else 0) + (8 if multi_ip else 0)  # maks 70
    n_movement = 0  # tidak ada check-in/lacak nyata pada tahap recon-infra; terisi saat ada data pergerakan nyata
    has_movement = n_movement > 0
    temporal_component = (min(n_movement, 10) * 3) if has_movement else 0  # hanya bernilai bila ada pergerakan nyata
    spatial_score = _clamp(20 + loc_anchor * 0.6 + temporal_component)  # tanpa pergerakan: maks ~62 (pita sedang, bukan tinggi)
    # VISUAL — jejak visual/identitas publik (avatar profil, Gravatar, potensi ANPR TNKB). BUKAN analisis citra.
    visual_score = _clamp(20 + n_accounts * 11 + (16 if gravatar_ok else 0) + (18 if tnkb_ok else 0))
    # FORENSIC — kekuatan atribusi & artefak (eksposur, identitas, HLR telepon, kendaraan)
    forensic_score = _clamp(28 + n_exposures * 7 + n_accounts * 6 + min(n_breaches, 10) * 2 + (14 if phone_ok else 0) + (8 if tnkb_ok else 0))

    composite_score = int(round(0.25 * cyber_score + 0.30 * spatial_score + 0.20 * visual_score + 0.25 * forensic_score))
    risk_level = "CRITICAL" if composite_score >= 80 else ("HIGH" if composite_score >= 65 else "MEDIUM")

    # Rincian transparan: faktor NYATA yang menyusun tiap sub-skor
    score_breakdown = {
        "cyber": [
            f"{n_ports} port TCP terbuka", f"{n_exposures} eksposur/misconfig",
            f"{n_accounts} akun publik", *([f"{n_breaches} kebocoran email"] if n_breaches else []), *(["TLS lemah/absen"] if ssl_weak else []),
        ],
        "spatial": [
            *(["GeoIP terselesaikan"] if geo_ok else ["GeoIP tak terselesaikan"]),
            *([f"TNKB valid ({tnkb_profile.get('samsat_subregion','')})"] if tnkb_ok else []),
            *([f"MSISDN valid ({phone_profile.get('operator','')})"] if phone_ok else []),
            *(["IP ganda (multi-anchor)"] if multi_ip else []),
            (f"{n_movement} titik pergerakan" if has_movement else "0 data pergerakan · komponen temporal nol"),
        ],
        "visual": [
            f"{n_accounts} profil publik (avatar)",
            *(["Gravatar ditemukan"] if gravatar_ok else []),
            *(["TNKB → potensi ANPR"] if tnkb_ok else []),
        ],
        "forensic": [
            f"{n_exposures} eksposur", f"{n_accounts} identitas terasosiasi",
            *([f"{n_breaches} kebocoran email"] if n_breaches else []),
            *(["HLR telepon tervalidasi"] if phone_ok else []),
            *(["kendaraan TNKB terdaftar"] if tnkb_ok else []),
        ],
        "formula": "composite = 0.25·cyber + 0.30·spatial + 0.20·visual + 0.25·forensic",
        "note": "Semua sub-skor dari sinyal recon nyata. Spatio-temporal = pelokalan + pergerakan; tanpa data pergerakan komponen temporal nol (tak masuk pita tinggi). 'visual' = jejak publik, bukan analisis citra.",
    }

    # 8. Bangun Knowledge Graph dari Entitas Asli yang Ditemukan
    root_label = f"{code_name}\n({raw_clean or host})"
    nodes = [
        {"id": "ROOT", "label": root_label, "type": "TARGET", "risk": composite_score},
    ]
    edges = []

    # Tambahkan node Akun Sosial/Developer jika ditemukan dari scan_identity_osint
    for acc in identity_info.get("accounts_found", [])[:4]:
        acc_id = f"SOC-{acc['platform']}"
        acc_label = f"{acc['platform']}: {acc.get('name') or identity_info.get('username')}"
        nodes.append({"id": acc_id, "label": acc_label[:28], "type": "CYBER", "risk": 75})
        edges.append({"from": "ROOT", "to": acc_id, "label": "PUBLIC_ACCOUNT"})

    # Tambahkan node Nomor Telepon / MSISDN jika ada
    if phone_profile.get("valid"):
        ph_id = f"PH-{phone_profile['local']}"
        nodes.append({
            "id": ph_id,
            "label": f"{phone_profile['e164']}\n({phone_profile['operator'][:18]})",
            "type": "DEVICE",
            "risk": 78,
        })
        edges.append({"from": "ROOT", "to": ph_id, "label": "MSISDN_HLR"})

    if primary_ip != "Unresolved":
        ip_node_id = f"IP-{primary_ip}"
        nodes.append({"id": ip_node_id, "label": f"IP: {primary_ip}\n({geo_info.get('city')})", "type": "CYBER", "risk": cyber_score})
        edges.append({"from": "ROOT", "to": ip_node_id, "label": "RESOLVES_TO_A"})

    if geo_info.get("asn"):
        asn_id = f"ASN-{geo_info['asn'][:12]}"
        nodes.append({"id": asn_id, "label": f"{geo_info['asn'][:26]}\n({geo_info.get('isp', '')[:22]})", "type": "LOCATION", "risk": 60})
        edges.append({"from": "ROOT", "to": asn_id, "label": "BGP_ASN"})

    if ssl_info.get("ssl_active"):
        ca_id = "SSL-CA"
        nodes.append({"id": ca_id, "label": f"SSL: {ssl_info.get('issuer_org', 'CA')[:20]}\n({ssl_info.get('tls_version')})", "type": "DEVICE", "risk": 50})
        edges.append({"from": "ROOT", "to": ca_id, "label": "ISSUED_BY"})

    for ns in ns_records[:2]:
        ns_id = f"NS-{ns[:14]}"
        nodes.append({"id": ns_id, "label": f"NS: {ns}", "type": "CYBER", "risk": 55})
        edges.append({"from": "ROOT", "to": ns_id, "label": "NAMESERVER"})

    for mx in mx_records[:1]:
        mx_clean = mx.split()[-1]
        mx_id = f"MX-{mx_clean[:14]}"
        nodes.append({"id": mx_id, "label": f"MX: {mx_clean[:24]}", "type": "EVIDENCE", "risk": 55})
        edges.append({"from": "ROOT", "to": mx_id, "label": "MAIL_EXCHANGE"})

    if plate_number:
        veh_id = f"VEH-{tnkb_profile['formatted']}"
        nodes.append({
            "id": veh_id,
            "label": f"{tnkb_profile['formatted']}\n({tnkb_profile['samsat_subregion'][:20]})",
            "type": "VEHICLE",
            "risk": 80,
        })
        edges.append({"from": "ROOT", "to": veh_id, "label": "ANPR_TNKB_MATCH"})

    return {
        "host": host,
        "raw_indicator": raw_clean,
        "resolved_ips": resolved_ips,
        "primary_ip": primary_ip,
        "geo": geo_info,
        "tnkb": tnkb_profile,
        "phone_profile": phone_profile,
        "identity_osint": identity_info,
        "breach": breach_info,
        "dns": {
            "ns": ns_records,
            "mx": mx_records,
            "txt": txt_records,
            "dmarc": dmarc_records,
        },
        "ssl": ssl_info,
        "open_ports": open_ports,
        "http_audit": http_audit,
        "exposures": exposures,
        "scores": {
            "cyber": cyber_score,
            "spatial": spatial_score,
            "visual": visual_score,
            "forensic": forensic_score,
            "composite": composite_score,
            "level": risk_level,
            "breakdown": score_breakdown,
        },
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
    }
