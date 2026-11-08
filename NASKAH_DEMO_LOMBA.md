# Naskah Demo Lomba — TFAEL-OMNI

Tujuan naskah ini: menampilkan platform sebagai **alat yang benar-benar bekerja**, bukan mockup.
Prinsip: satu cerita yang mengalir, tonjolkan yang **nyata (live)**, sebut data skenario sebagai **contoh**.

Login: `komandan` / `<SANDI_ANDA>`

---

## Pembukaan (15 detik) — buka dengan yang NYATA, bukan narasi

Jangan mulai dengan "aplikasi ini punya 5 pilar...". Mulai dengan bukti hidup:

> "Yang Anda lihat ini membaca mesin nyata. Panel kiri ini koneksi jaringan asli laptop ini,
> diambil langsung dari sistem operasi."

Buka **SIEM & Sockets → tab Soket host**, klik **Refresh koneksi host**.
Tunjukkan proses & IP asli yang muncul. Tekankan: *ini bukan data contoh, ini mesin ini sekarang.*

---

## Babak 1 — Gambaran operasi (45 detik) · Peta C4ISR

- Tunjuk peta: unit lapangan dengan status kanal berbeda (4G, SMS 2G, radio APRS, SOS).
- Tunjuk kolom "Terlihat ... menit lalu" → "sistem tahu kesegaran tiap unit; yang off-grid wajar lebih lama."
- Klik satu unit → panel kendali C2 di kanan.
- **Momen nyata:** klik **Lacak lokasi GPS Mac ini** → koordinat asli perangkat muncul di peta.
- Sebut: "Target dan unit di skenario ini adalah **contoh**; mekanismenya yang nyata."

## Babak 2 — Deteksi langsung (60 detik) · Kamera / CCTV

Ini kartu AS Anda. Pilih salah satu yang paling mulus di tempat lomba:

- **Opsi kamera:** tab Kamera → Aktifkan kamera Mac → **Deteksi objek pada frame**.
  Tunjukkan kotak deteksi muncul dari kamera sungguhan.
- **Opsi CCTV publik:** tab CCTV → ambil 1 frame dari stream ATCS → deteksi.

Kalau modul deteksi tidak terpasang di lokasi, lewati dengan jujur ("modul deteksi perlu diaktifkan")
dan pindah ke forensik yang pasti jalan. **Jangan memaksakan fitur yang belum siap.**

## Babak 3 — Profiling & analisis (45 detik) · OSINT Profiler

- Tunjuk **knowledge graph**: relasi target ↔ perangkat ↔ kendaraan ↔ bukti.
- Tunjuk **skor risiko komposit (estimasi model)** dengan 4 dimensi berbobot.
- Tekankan hedging: klasifikasi "**terduga/belum terbukti**", skor "indikatif, perlu verifikasi".
  "Sistem memberi estimasi, keputusan tetap di analis." — ini justru menambah kredibilitas.

## Babak 4 — Forensik nyata (60 detik) · Lab Forensik — PUNCAK

Ini pembunuh "AI slop" paling kuat karena semua dihitung di tempat:

1. **Unggah foto asli Anda** (bawa satu foto ber-EXIF GPS).
2. Tunjukkan: SHA-256/512 dihitung langsung, metadata EXIF dibaca, **ELA piksel** memperlihatkan
   area yang diedit, entropi Shannon.
3. "Semua angka ini dihitung dari file Anda barusan, bukan disiapkan sebelumnya."
4. Tunjuk **rantai hash (chain-of-custody)** → integritas bukti.
5. Klik **Cetak BAP forensik** → dokumen resmi siap.

## Penutup (20 detik)

- Satu kalimat arsitektur: "On-premise, air-gap ready; mesin forensik, SIEM host, kripto, dan
  geolokasi semuanya berjalan lokal."
- Tutup di panel **Admin → RBAC** sekilas: "ada kontrol akses berbasis peran dan jejak audit."

---

## Yang HARUS ditekankan ke juri (anti "AI slop")
- **Nyata, dihitung sekarang:** soket host (lsof), hash/EXIF/ELA/entropi, deteksi objek/OCR,
  GPS perangkat, triangulasi & Haversine, kripto HMAC/AES.
- **Jujur soal data:** target/alert/unit adalah **skenario contoh** untuk mengisi layar.
- **Hedging = fitur, bukan kelemahan:** "terduga", "estimasi", "perlu verifikasi" menunjukkan
  sistem yang dewasa, bukan vonis otomatis.

## Yang JANGAN dilakukan
- Jangan membuka dengan daftar fitur/pilar.
- Jangan mengklaim data skenario sebagai pengintaian nyata atas orang sungguhan.
- Jangan memaksakan fitur yang belum stabil di lokasi; punya rencana B (forensik selalu jalan).
- Jangan menambah fitur baru menjelang lomba — rapikan dan kuasai alur ini.

## Checklist sebelum tampil
- [ ] Server jalan: `OMNI_BOOTSTRAP_PASSWORD="<SANDI_ANDA>" python3 backend/server.py 8080`
- [ ] Login `komandan` / `<SANDI_ANDA>` berhasil.
- [ ] Siapkan 1 foto ber-EXIF untuk demo forensik.
- [ ] Uji kamera/CCTV di jaringan lokasi lomba; kalau ragu, andalkan forensik.
- [ ] Peta memuat (mode taktis gelap / jalan).
