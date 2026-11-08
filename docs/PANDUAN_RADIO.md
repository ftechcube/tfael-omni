# Panduan Rakit Jalur Radio — TFAEL-OMNI

Lacak tim **tanpa internet dan tanpa pulsa** lewat radio. Posisi agen dipancarkan
RF, diterima satu "jembatan" di pos komando, lalu muncul di peta C4ISR.

```
 AGEN (lapangan)              POS KOMANDO
┌──────────────┐  RF         ┌───────────────────┐  USB/   ┌──────────────┐
│ Node + GPS   │ ──────────▶ │ Node penerima +   │  lokal  │ Server+Peta  │
│ (di saku)    │  (tanpa     │ radio_gateway.py  │ ──────▶ │ C4ISR (biru) │
└──────────────┘  pulsa/net) └───────────────────┘         └──────────────┘
```

Software-nya **sudah siap & teruji** (`tools/radio_gateway.py` + decoder di server).
Dokumen ini soal **merakit alat fisiknya**.

---

## Pilih jalur

| | **LoRa Meshtastic** ✅ disarankan | **APRS / VHF** |
|---|---|---|
| Izin | **Bebas izin** (band ISM 923 MHz) | **Wajib izin amatir (ORARI/IAR)** untuk memancar |
| Biaya/unit | Rp 150–350rb | penerima Rp 200–400rb + HT Rp 250rb+ |
| GPS | Built-in (T-Beam) | perlu HP/tracker terpisah |
| Jarak | 2–10+ km, mesh estafet | puluhan km (tergantung daya/antena) |
| Kesulitan | Rendah (flash via web) | Menengah (setel direwolf) |

Kalau ragu: **Meshtastic**. Legal, murah, GPS menyatu, langsung didukung daemon.

---

## Jalur 1 — LoRa Meshtastic (disarankan)

### 1.1 Belanja
- **Node agen:** `LilyGO T-Beam` (ada **GPS** + holder baterai 18650).
- **Node pos komando:** `Heltec LoRa 32 V3` atau T-Beam lagi (tak wajib GPS).
- Baterai **18650**, kabel **USB-C**, antena LoRa (biasanya ikut).
- ⚠️ **Beli varian 915 MHz** (SKU sub-GHz 902–928 MHz, yang sudah mencakup 923).
  Di Meshtastic nanti set **Region = AS923** (±920–923 MHz, standar Indonesia).
  **Jangan** beli varian **433 MHz** (band beda, bukan region AS923) atau
  **868 MHz** (itu Eropa). **Antena harus seband 915** — jangan campur 433.

> Bukti konsep minimal: **1 T-Beam (agen) + 1 board (pos) ≈ Rp 500rb.**

### 1.2 Flash firmware (tanpa koding)
1. Colok board ke PC via USB.
2. Buka **https://flasher.meshtastic.org** di Google Chrome/Edge.
3. Pilih model board → versi stabil → **Flash**. Tunggu sampai selesai.
4. Ulangi untuk tiap board.

### 1.3 Setel region & nama
Pakai app **Meshtastic** (Android/iOS, sambung via Bluetooth) atau client web:
- **Region = `AS923`** (wajib, Indonesia).
- Beri nama tiap node, mis. `FOX-07`, `POS-KOMANDO`. Nama ini jadi callsign di peta.

### 1.4 Node agen (T-Beam)
1. Di app Meshtastic → **Settings → Position**:
   - `GPS = Enabled`
   - `Broadcast interval` = mis. 120 dtk (makin sering makin boros baterai).
2. Pasang baterai 18650, masukkan ke pouch/tas. Selesai — otomatis memancar posisi.

### 1.5 Node pos komando + jembatan
1. Colok node pos ke **komputer server** via USB.
2. Cari nama port serial:
   - macOS/Linux: `ls /dev/tty.*` atau `ls /dev/ttyUSB* /dev/ttyACM*`
   - Windows: lihat **Device Manager → Ports (COM & LPT)**, mis. `COM5`
3. **Opsi A — langsung dari serial** (butuh `pip install pyserial`):
   ```bash
   python3 tools/radio_gateway.py \
     --server http://localhost:8080 \
     --source serial --path /dev/tty.usbserial-0001 --baud 115200
   ```
4. **Opsi B — lewat CLI Meshtastic** (JSON):
   ```bash
   pip install meshtastic
   meshtastic --listen | python3 tools/radio_gateway.py \
     --server http://localhost:8080 --source stdin
   ```
5. Setiap node yang memancar posisi akan muncul **biru** di peta sebagai
   `RADIO-<NAMA>` (mis. `RADIO-FOX-07`).

---

## Jalur 2 — APRS / VHF (perlu izin amatir)

> ⚠️ **Memancar** di band amatir (144 MHz / APRS) **wajib izin amatir radio
> (IAR, ORARI)**. **Menerima** bebas. Tanpa lisensi, pakai Jalur 1.

### 2.1 Belanja
- **Pos komando (terima):** dongle **RTL-SDR** + antena VHF.
- **Agen (pancar):** HT (mis. Baofeng UV-5R) + HP ber-**APRSdroid** + kabel audio,
  atau HT ber-APRS bawaan (Yaesu FT3DR / Kenwood TH-D74).

### 2.2 Pos komando: RTL-SDR → direwolf → jembatan
1. Install **direwolf** dan **rtl-sdr**:
   - macOS: `brew install direwolf rtl-sdr`
   - Linux: `sudo apt install direwolf rtl-sdr`
2. Umpan audio 144.390 MHz ke direwolf (contoh pipa):
   ```bash
   rtl_fm -f 144.39M -s 22050 -g 40 - | direwolf -c direwolf.conf -r 22050 -
   ```
3. Di `direwolf.conf`, aktifkan keluaran teks TNC2 ke TCP (port mis. 8001).
4. Jalankan jembatan:
   ```bash
   python3 tools/radio_gateway.py \
     --server http://localhost:8080 \
     --source tcp --host 127.0.0.1 --port 8001
   ```
5. Agen APRS yang tertangkap muncul biru di peta sebagai `RADIO-<CALLSIGN>`.

### 2.3 Agen: HT + APRSdroid
- Install **APRSdroid** di HP, hubungkan ke HT lewat kabel audio (mode VOX/PTT).
- Set callsign + aktifkan beacon posisi. HP meng-encode posisi → audio AFSK →
  HT memancar.

---

## Uji dulu TANPA hardware

Pastikan server + jembatan jalan sebelum alat datang:

```bash
# 1) Jalankan server
python3 backend/server.py

# 2) Di terminal lain, suntik paket contoh (APRS + Meshtastic) ke jembatan:
printf '%s\n' \
 'YB0TFL-9>APRS,WIDE1-1:!0610.52S/10649.63E>180/032/A=000145 Patroli Hutan' \
 '{"fromId":"!a1b2c3d4","decoded":{"position":{"latitudeI":-62000000,"longitudeI":1068500000,"altitude":42}}}' \
 | python3 tools/radio_gateway.py --server http://localhost:8080 --source stdin
```

Hasil yang benar: dua baris `✓ RADIO-...` dan dua unit biru baru di peta komando.

---

## Sumber paket yang didukung jembatan (`tools/radio_gateway.py`)

| `--source` | Untuk apa | Argumen |
|---|---|---|
| `stdin` | uji / pipa dari tool lain (mis. `meshtastic --listen`) | — |
| `file` | ikuti file log (`tail -f`) | `--path berkas.log` |
| `tcp` | keluaran teks TNC/direwolf | `--host`, `--port` |
| `serial` | TNC/Meshtastic langsung via USB | `--path`, `--baud` |

Format dideteksi otomatis: diawali `{` → **LoRa Meshtastic**, selain itu → **APRS**.
Jika server pakai kunci agen, tambahkan `--agent-key <KUNCI>`.

---

## Masalah umum

| Gejala | Kemungkinan sebab / solusi |
|---|---|
| `Connection refused` | server belum jalan / salah `--server` URL/port |
| `ditolak: Paket tidak dapat didekode` | format paket tak dikenal (bukan APRS TNC2 / JSON Meshtastic valid) |
| Unit tak muncul di peta | salah region (bukan AS923), node belum broadcast posisi, GPS belum fix |
| Mode serial error `butuh pyserial` | `pip install pyserial` |
| Port serial tak ada | cek kabel data (bukan kabel charge), driver USB-serial (CP210x/CH340) |

---

## Ringkas biaya (bukti konsep)

| Item | Perkiraan |
|---|---|
| 1× T-Beam (agen, GPS) | Rp 250–350rb |
| 1× Heltec/T-Beam (pos) | Rp 150–300rb |
| 2× baterai 18650 | Rp 60–120rb |
| **Total mulai** | **± Rp 500–700rb** |

Tambah node agen sesuai jumlah tim. Semua mesh-nya **bebas izin & bebas pulsa**.
