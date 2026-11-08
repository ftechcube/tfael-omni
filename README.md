# TFAEL-OMNI v2.0 — Unified C4ISR, AI Target Profiling, Cyber-Physical SIEM & Digital Forensic Platform

Platform Pusat Komando Terpadu (*Single Pane of Glass*) yang beroperasi **100% On-Premise / Air-Gapped Ready** tanpa ketergantungan pada *cloud* pihak ketiga.

## Cara Menjalankan MVP

Server MVP saat ini sudah berjalan pada port `8080`, atau dapat dijalankan kapan saja dengan perintah:

```bash
python3 backend/server.py 8080
```

Kemudian buka di browser:
👉 **`http://localhost:8080`**

---

## Struktur Proyek & Dokumen

### 1. Kode Sumber MVP
* [`backend/crypto_c2.py`](backend/crypto_c2.py) — Mesin kriptografi **SMS Biner Port 8901 (22-byte HMAC-SHA256)**, pembungkus **3GPP TS 23.040 PDU**, verifikasi *constant-time anti-spoofing*, anti-replay nonce cache, dan balasan telemetri **AES-128-GCM**.
* [`backend/engines.py`](backend/engines.py) — Mesin inti 6 Pilar: Dekoder Radio APRS AX.25/LoRa, Evaluasi Spasial Geofence, AI Target Profiling (*Knowledge Graph*, *Pattern-of-Life*, Skor Risiko 0–100), SIEM Siber-Fisik (*Sigma*, **MITRE ATT&CK v15**, deteksi *Haversine Impossible Travel*, *SOAR Lite*), dan Digital Forensic Toolkit (**SHA-256/SHA-512 Hash-Chained Evidence Vault**, *EXIF*, *ELA*, *SQLite WAL Carver*, *YARA*, & BAP PDF).
* [`backend/server.py`](backend/server.py) — Server API `/api/v2/*` & penyaji antarmuka web.
* [`frontend/index.html`](frontend/index.html), [`frontend/styles.css`](frontend/styles.css), [`frontend/app.js`](frontend/app.js) — Antarmuka **Tactical Dark HUD 4-Workspace**.

### 2. Paket Dokumen Resmi (Word `.docx` & Markdown `.md`)
1. **Proposal Proyek:** [`PROPOSAL_PROYEK_TFAEL_OMNI.docx`](PROPOSAL_PROYEK_TFAEL_OMNI.docx) | [`PROPOSAL_PROYEK_TFAEL_OMNI.md`](PROPOSAL_PROYEK_TFAEL_OMNI.md)
2. **BRD (Business Requirements Document):** [`BRD_TFAEL_OMNI.docx`](BRD_TFAEL_OMNI.docx) | [`BRD_TFAEL_OMNI.md`](BRD_TFAEL_OMNI.md)
3. **PRD (Product Requirements Document):** [`PRD_TFAEL_OMNI.docx`](PRD_TFAEL_OMNI.docx) | [`PRD_TFAEL_OMNI.md`](PRD_TFAEL_OMNI.md)
4. **SRS (Software Requirements Specification):** [`SRS_TFAEL_OMNI.docx`](SRS_TFAEL_OMNI.docx) | [`SRS_TFAEL_OMNI.md`](SRS_TFAEL_OMNI.md)

---

## Konfigurasi Keamanan (Produksi)

Secara bawaan server berjalan dalam **mode demo** (longgar, agar mudah dicoba). Untuk penempatan nyata, aktifkan penguncian lewat *environment variable* berikut:

| Variabel | Fungsi | Contoh |
|---|---|---|
| `OMNI_ALLOWED_ORIGINS` | Daftar origin yang boleh akses lintas-asal (dipisah koma). Kosong = tolak semua CORS. | `https://console.markas.local` |
| `OMNI_AGENT_KEY` | Kunci pra-berbagi untuk endpoint perangkat lapangan (`telemetry/live-device`, `telemetry/offgrid`, `targets/checkin`). Kosong = terbuka (demo). | `FIELD-KEY-7a3f...` |
| `OMNI_BOOTSTRAP_PASSWORD` | Kata sandi awal akun seed. Bila tidak diset, dibuat **acak** dan ditampilkan sekali di log boot. | `Omni#Rahasia2026` |
| `OMNI_LOGIN_MAX_FAILS` | Jumlah gagal login sebelum akun+IP terkunci sementara (default `5`). | `5` |
| `OMNI_LOGIN_LOCK_SECONDS` | Durasi kunci lockout dalam detik (default `900` = 15 menit). | `900` |
| `OMNI_AIRGAP` | `1` untuk mematikan panggilan jaringan keluar GeoIP host (`host-geoip`). | `1` |

Contoh menjalankan mode produksi:

```bash
OMNI_ALLOWED_ORIGINS="https://console.markas.local" \
OMNI_AGENT_KEY="FIELD-KEY-7a3f91c2" \
OMNI_BOOTSTRAP_PASSWORD="Omni#RahasiaAwal2026" \
OMNI_AIRGAP=1 \
python3 backend/server.py 8080
```

**Catatan kepatuhan:** fitur link pelacak (`/checkin`) dan *force GPS ping* via SMS biner bersifat *dual-use* — gunakan hanya dengan payung hukum/izin resmi (lawful intercept / perintah yang sah).
