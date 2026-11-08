# OMNI Agent — Aplikasi Android Unit Lapangan

Aplikasi pendamping TFAEL-OMNI yang dijalankan di HP tiap unit lapangan. Ia melapor
**data nyata** ke pusat komando secara berkala:

- **Posisi GPS** (lat, lon, akurasi, ketinggian, kecepatan)
- **Baterai** perangkat
- **Kekuatan sinyal** seluler (dBm)
- **Serving cell** (radio, mcc, mnc, lac/tac, cid) untuk geolokasi sel

Unit yang tadinya data contoh di peta berubah jadi perangkat betulan yang bergerak.

Ini **agen/beacon ringan**, bukan ATAK penuh (tanpa peta/pesan CoT). Fokusnya satu:
menarik telemetri nyata dari HP ke server.

## Cara kerja

Setiap interval, service latar belakang mengirim `POST` ke:

```
POST {server}/api/v2/telemetry/live-device
Header: X-Agent-Key: <kunci agen>   (jika server mengaktifkannya)
Body  : { unit_id, name, role, lat, lon, alt_m, accuracy_m, speed_kmh,
          battery_pct, is_sos, rssi_dbm, mcc, mnc, cells:[{radio,lac,cid,mcc,mnc,signal}] }
```

Server (`backend/server.py`) sudah punya endpoint ini dan memperbarui peta C4ISR
secara real-time.

> Catatan: field `cells` sudah dikirim, tapi agar menara dipakai untuk **geolokasi
> sel**, endpoint `live-device` di backend perlu ditambah sedikit agar meneruskan
> `cells` ke `geolocate_live_cells()`. Lihat "Tindak lanjut backend" di bawah.

## Membangun APK

Laptop ini belum punya toolchain Android. Pilih salah satu:

### A. Build di cloud (disarankan — tanpa memasang apa pun)
1. Push repo ini ke GitHub.
2. Buka tab **Actions** → workflow **Build OMNI Agent APK** → **Run workflow**
   (atau otomatis jalan saat ada perubahan di `android/`).
3. Setelah hijau, unduh artifact **omni-agent-debug-apk** → berisi `app-debug.apk`.
4. Pindahkan APK ke HP dan pasang (lihat "Memasang di HP").

### B. Android Studio
1. Buka folder `android/` di Android Studio (akan mengunduh SDK/Gradle).
2. **Run** ke HP yang tersambung USB, atau **Build > Build APK(s)**.

### C. Command-line
```bash
cd android
gradle wrapper --gradle-version 8.7   # sekali, untuk membuat ./gradlew
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

## Memasang di HP

1. Di HP: **Pengaturan > Tentang ponsel** → ketuk **Nomor bentukan** 7x untuk
   membuka **Opsi pengembang**.
2. Aktifkan **USB debugging** (untuk `adb`) atau izinkan **pasang dari sumber tak
   dikenal** (untuk salin APK langsung).
3. `adb install app-debug.apk`, atau salin APK ke HP lalu ketuk untuk memasang.
4. Saat pertama dibuka, **izinkan Lokasi (Selalu izinkan), Telepon, dan Notifikasi**.

## Mengonfigurasi & menjalankan

1. Pastikan server berjalan dan **terjangkau dari HP**:
   ```bash
   OMNI_BOOTSTRAP_PASSWORD="<SANDI_ANDA>" python3 backend/server.py 8080
   ```
   Server bind ke `0.0.0.0`, jadi gunakan **IP LAN laptop** (mis. `http://192.168.1.10:8080`).
   HP dan laptop harus satu jaringan WiFi. (Alternatif jarak jauh: tunnel seperti
   `cloudflared`/`ngrok`.)
2. Di aplikasi, isi:
   - **URL server**: `http://<IP-LAN-laptop>:8080`
   - **ID unit**: mis. `ALPHA-01`
   - **Nama/peran**: mis. `Tim Tindak Cepat Alpha-1`
   - **Kunci agen**: kosongkan bila `OMNI_AGENT_KEY` tidak diset di server; kalau diset,
     isi persis sama.
   - **Interval**: detik antar laporan (mis. `15`).
3. Tekan **Mulai lapor**. Status di layar menampilkan hasil tiap kirim
   (`OK 10:03:21 · -6.2072, 106.8218 · bat 84% · -71 dBm · 3 sel`).
4. Buka **Peta C4ISR** di layar komando — unit itu kini bergerak dengan posisi nyata.

## Catatan & batasan

- **Lokasi latar belakang**: pilih "Izinkan sepanjang waktu" agar lapor saat layar mati.
  Sebagian HP (Xiaomi/Oppo/Vivo) perlu mematikan optimasi baterai untuk aplikasi ini.
- **Tanpa Google Play Services**: memakai `LocationManager` murni (AOSP), jadi jalan di
  HP polos. Fix GPS pertama bisa butuh beberapa detik di luar ruangan.
- **Serving cell** butuh izin Telepon; di beberapa HP data sel kosong saat mode pesawat
  atau tanpa SIM.
- Build **debug** (belum ditandatangani rilis) — cukup untuk uji lapangan, bukan untuk
  Play Store.

## Tindak lanjut backend (opsional, untuk geolokasi sel)

Agar `cells` yang dikirim HP dipakai menghitung posisi dari menara (bukan hanya GPS),
tambahkan di handler `live-device` server: bila `payload["cells"]` ada, panggil
`geolocate_live_cells(cells=..., attach_unit_id=unit_id)` setelah menyimpan GPS. Ini
membuat jalur geolokasi seluler nyata end-to-end.
