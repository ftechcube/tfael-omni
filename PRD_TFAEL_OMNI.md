# DOKUMEN SPESIFIKASI KEBUTUHAN PRODUK (*PRODUCT REQUIREMENTS DOCUMENT* / PRD)
## PLATFORM KOMANDO TAKTIS MULTI-KANAL, PEMROFILAN TARGET BERBASIS AI, SIEM SIBER-FISIK, DAN LABORATORIUM FORENSIK DIGITAL TERPADU
### **"TFAEL-OMNI v2.0: PRODUCT ARCHITECTURE, UX/UI WORKSPACES, PROTOCOLS, & TECHNICAL SPECIFICATIONS"**

---

| Informasi Dokumen | Keterangan Resmi |
| :--- | :--- |
| **Kode Dokumen** | PRD/TFAEL-OMNI/X/2026/003 |
| **Dokumen Induk Terkait** | BRD/TFAEL-OMNI/X/2026/002 (*Business Requirements Document*) |
| **Versi Produk** | v2.0.0 (*Enterprise On-Premise / Air-Gapped Edition*) |
| **Tanggal Terbit** | 22 Oktober 2026 |
| **Klasifikasi** | TERBATAS (*RESTRICTED / OFFICIAL USE ONLY*) |
| **Tim Pemilik Produk** | Product Management, Core Engineering, AI/ML Research, Cyber SOC, & Digital Forensics Team |
| **Status Dokumen** | *Approved for Engineering & Sprint Execution* |

---

## DAFTAR ISI
1. **BAB I: VISI PRODUK, PRINSIP DESAIN, & PERSONA PENGGUNA**
2. **BAB II: EPICS, USER STORIES, & KRITERIA PENERIMAAN (GHERKIN)**
3. **BAB III: SPESIFIKASI ANTARMUKA PENGGUNA (UX/UI) & 4 WORKSPACE UTAMA**
4. **BAB IV: SPESIFIKASI TEKNIS PROTOKOL, ALGORITMA AI, & MESIN INTI**
5. **BAB V: KONTRAK ENDPOINT REST API & KANAL REAL-TIME WEBSOCKET**
6. **BAB VI: SKEMA BASIS DATA TERPADU (POSTGIS, TIMESCALEDB, APACHE AGE, PGVECTOR)**
7. **BAB VII: PENANGANAN SKENARIO BATAS (*EDGE CASES*) & MEKANISME *FAILOVER***
8. **BAB VIII: RENCANA RILIS PRODUK (*RELEASE ROADMAP*) & METRIK KESUKSESAN PRODUK**

---

## BAB I: VISI PRODUK, PRINSIP DESAIN, & PERSONA PENGGUNA

### 1.1 Visi Produk (*Product Vision*)
Menghadirkan satu aplikasi Pusat Komando Terpadu (*Single Pane of Glass*) berkinerja tinggi yang tetap berfungsi di tengah kondisi terputusnya jaringan internet (*Zero Blind-Spot*), mampu memprofilkan target dan jaringan ancamannya dalam hitungan detik menggunakan Kecerdasan Buatan lokal (*AI-Assisted Target Profiling*), mendeteksi serangan siber yang berkorelasi langsung dengan lokasi fisik di peta (*Converged Cyber-Physical SIEM*), serta mengunci dan membedah barang bukti digital secara sah menurut hukum (*Court-Admissible Digital Forensics*).

### 1.2 Lima Prinsip Desain Produk (*Core Product Design Principles*)
1. **Zero-Lag Tactical Clarity:** Operator tidak boleh kebingungan mencari tombol saat kondisi darurat. Seluruh aksi kritis (*Force GPS Ping*, *Isolate Host*, *Lock Evidence*, *Generate Dossier*) dapat dieksekusi maksimal dalam **2 klik**.
2. **Offline-First & Air-Gapped Native:** Tidak ada satu pun fitur produk (baik peta, AI/LLM, OCR, transkripsi suara, maupun pemetaan BTS) yang gagal berjalan ketika kabel internet keluar dicabut.
3. **Cryptographic Trust by Default:** Perangkat lapangan tidak pernah memercayai perintah tanpa tanda tangan **HMAC-SHA256**, dan laboratorium forensik tidak pernah menyimpan bukti tanpa segel berantai **SHA-256/SHA-512**.
4. **Cross-Module Intelligence Fusion:** Setiap modul saling memperkaya secara otomatis—temuan nomor telepon/koordinat di modul Forensik otomatis memperbarui *Knowledge Graph* di modul *Target Profiling* dan langsung tampil di *Peta Taktis*.
5. **Explainable AI (XAI):** Setiap skor risiko atau peringatan anomali yang dihasilkan AI wajib menyertakan rincian alasan matematis dan faktual yang dapat dipertanggungjawabkan oleh analis di hadapan pimpinan maupun pengadilan.

### 1.3 Persona Pengguna Utama (*Target User Personas*)

| Kode Persona | Nama & Jabatan Persona | Konteks Operasional & Kebutuhan Utama | Masalah Utama yang Diselesaikan Produk (*Pain Points Solved*) |
| :---: | :--- | :--- | :--- |
| **P-01** | **Kolonel / Komandan Operasi** (*Mission Commander*) | Memimpin operasi dari ruang komando pusat atau posko taktis bergerak. Membutuhkan gambaran situasi utuh tanpa harus membaca log teknis yang rumit. | Tidak perlu lagi membuka 4 layar berbeda; cukup melihat peta utama, kartu skor risiko target, dan laporan ringkas *Executive Brief PDF*. |
| **P-02** | **Operator C2 Taktis** (*Tactical Dispatcher*) | Memantau 100–1.000 personel/aset lapangan selama *shift* 8 jam. Bertanggung jawab atas keselamatan personel di zona rawan dan *blank spot*. | Saat personel hilang sinyal internet di gedung/hutan, operator cukup klik *Force GPS Ping* (SMS Port 8901) atau memantau perpindahan otomatis ke jalur radio APRS/LoRa. |
| **P-03** | **Analis Intelijen & Profiling** (*OSINT & Target Analyst*) | Menyusun profil sasaran operasi, memetakan jaringan afiliasi, serta mencari pola pergerakan (*Pattern of Life*) dan titik pertemuan rahasia. | Mengubah proses pengumpulan OSINT dan korelasi lokasi yang biasanya memakan waktu 3 hari menjadi `< 60 detik` dengan bantuan *Knowledge Graph* dan *Local LLM*. |
| **P-04** | **Analis Keamanan Siber SOC** (*SIEM & Threat Hunter*) | Menjaga infrastruktur server komando, jaringan objek vital, dan keamanan akun personel dari serangan siber maupun ancaman orang dalam (*insider threat*). | Langsung mengetahui apabila ada akun personel yang login dari IP mencurigakan yang tidak cocok dengan lokasi GPS fisiknya (*Impossible Travel*). |
| **P-05** | **Investigator Forensik Digital** (*DFIR Examiner*) | Memeriksa barang bukti sitaan/temuan lapangan (HP, flashdisk, foto, rekaman suara, dokumen, PCAP) untuk pembuktian hukum sesuai UU ITE. | Otomatisasi perhitungan hash rantai bukti (*Chain of Custody*), deteksi foto rekayasa (*ELA*), pemulihan pesan SQLite terhapus, dan cetak otomatis BAP Forensik. |

---

## BAB II: EPICS, USER STORIES, & KRITERIA PENERIMAAN (*GHERKIN*)

| ID Story | Epic / Modul | User Story (*Sebagai... Saya ingin... Sehingga...*) | Kriteria Penerimaan Produk (*Acceptance Criteria — Given / When / Then*) |
| :---: | :--- | :--- | :--- |
| **US-01** | **Epic 1: C4ISR & SMS C2** | Sebagai **Operator C2**, saya ingin mengirim perintah *Force GPS Ping* via SMS Biner terenkripsi ketika personel kehilangan sinyal internet, sehingga posisi presisinya tetap muncul di peta dalam kondisi darurat. | **Given** unit lapangan berstatus *Data Offline* namun berada di area ber-BTS 2G,<br>**When** operator menekan tombol `Force GPS Ping` pada kartu unit,<br>**Then** server mengirim SMS Biner Port 8901 ber-HMAC-SHA256, agen Android menyalakan GPS secara senyap, membalas SMS AES-128-GCM, dan titik unit berubah menjadi **Kuning** di peta dalam `< 35 detik`. |
| **US-02** | **Epic 2: Off-Grid Telemetry** | Sebagai **Operator C2**, saya ingin paket koordinat dari radio VHF/UHF APRS, LoRa Meshtastic, dan satelit LEO otomatis tampil di peta yang sama, sehingga tim di hutan/gunung tanpa BTS tetap terpantau. | **Given** tim patroli berada di kawasan hutan tanpa BTS dan memancarkan beacon APRS/LoRa,<br>**When** gateway *Direwolf* / broker MQTT menerima paket koordinat,<br>**Then** sistem mendekode frame AX.25/Protobuf dan menampilkan ikon unit berwarna **Biru** beserta jejak lintasannya (*breadcrumb trail*) secara *real-time*. |
| **US-03** | **Epic 3: Visual AI & ANPR** | Sebagai **Analis Intelijen**, saya ingin sistem membaca pelat nomor kendaraan dan atribut pakaian dari streaming CCTV/Drone secara otomatis, sehingga saya mendapat peringatan instan saat target melewati kamera. | **Given** aliran video RTSP kamera aktif dan nomor polisi target terdaftar di *Watchlist*,<br>**When** kendaraan tersebut melintas di depan kamera,<br>**Then** modul YOLOv8 + PaddleOCR mendeteksi pelat nomor dalam `< 500 ms`, membunyikan alarm *Watchlist Hit*, menyimpan potongan gambar (*snapshot*), dan menandai lokasi kamera di peta. |
| **US-04** | **Epic 4: AI Target Profiling** | Sebagai **Analis Profiling**, saya ingin sistem menggabungkan jejak OSINT, riwayat pergerakan (*Pattern of Life*), dan relasi entitas ke dalam satu *Dossier* otomatis, sehingga saya dapat menilai tingkat ancaman target dengan cepat. | **Given** analis memasukkan indikator awal (domain/IP/nomor/ID target),<br>**When** analis menekan tombol `Generate AI Target Profile`,<br>**Then** sistem menjalankan rekognisi pasif, memetakan *Knowledge Graph*, menghitung *Dwell Clusters* (HDBSCAN), mengalkulasi Skor Risiko (0–100), dan menyusun narasi *Dossier* via Local LLM dalam `< 60 detik`. |
| **US-05** | **Epic 5: Cyber-Physical SIEM** | Sebagai **Analis SOC**, saya ingin SIEM mendeteksi ketidakcocokan antara lokasi IP login siber dengan lokasi GPS fisik personel (*Impossible Travel*), sehingga pembajakan akun dapat dihentikan seketika. | **Given** perangkat dinas Personel X terpantau via GPS/BTS berada di Bandung,<br>**When** akun Personel X tercatat melakukan login SSH/Web dari alamat IP di luar negeri/kota lain dalam selisih waktu 5 menit (kecepatan semu `> 900 km/jam`),<br>**Then** SIEM memicu *Critical Alert (MITRE T1078)*, menyorot kedua titik di peta, dan menyediakan tombol *1-Click Freeze Account*. |
| **US-06** | **Epic 6: Digital Forensics (DFIR)** | Sebagai **Investigator Forensik**, saya ingin setiap barang bukti digital yang diunggah otomatis disegel dengan SHA-256/512, dianalisis metadatanya (EXIF/ELA/YARA), dan dicetak menjadi BAP Forensik PDF. | **Given** investigator mengunggah file bukti (foto, dokumen, dump SQLite, atau PCAP) ke *Evidence Vault*,<br>**When** proses akuisisi selesai,<br>**Then** sistem mencatat entri *hash-chained ledger*, memplot koordinat EXIF foto ke peta, menampilkan peta panas manipulasi *ELA*, mengekstrak entitas ke *Knowledge Graph*, dan menghasilkan dokumen BAP PDF. |

---

## BAB III: SPESIFIKASI ANTARMUKA PENGGUNA (UX/UI) & 4 WORKSPACE UTAMA

Produk dirancang menggunakan tema visual **Tactical Dark HUD (`#090D16` Obsidian Slate)** untuk meminimalkan kelelahan mata operator di ruang komando berintensitas cahaya rendah. Navigasi utama memiliki **4 Workspace Terintegrasi** yang dapat diakses melalui *Top Command Bar* tanpa memuat ulang halaman (*Single-Page Application*):

### 3.1 Workspace 1: *Tactical C4ISR Map & Telemetry HUD*
* **Top Command & System Health Bar:** Menampilkan jam taktis (UTC & WIB), indikator status kanal (*4G Data Gateway*, *GSM Modem Port 8901*, *APRS VHF SDR*, *LoRa MQTT*, *Local AI GPU Load*), penghitung jumlah aset aktif per status warna, serta tombol darurat global.
* **Left Panel — *Unit & Layer Tree*:**
  * Daftar personel, kendaraan, drone, dan kamera CCTV dengan filter pencarian instan dan lencana status warna (**Hijau**: Data 4G, **Kuning**: SMS 2G/BTS, **Biru**: Radio/Satelit, **Merah**: SOS/Breach).
  * Pengaturan lapisan peta (*Layer Toggles*): Kontur 3D, Cakupan Menara BTS (`MCC/MNC/LAC/CID`), Poligon Geofence, Titik Kamera CCTV, Titik Insiden SIEM, dan Titik Temuan Bukti Forensik.
* **Center Canvas — *2D/3D MapLibre GL + Deck.gl Engine*:**
  * Peta vektor luring interaktif dengan dukungan kemiringan kamera 3D (*pitch/bearing*), lingkaran radius probabilitas triangulasi BTS, garis jejak pergerakan historis, dan indikator *cone of vision* kamera pengawas.
* **Right Drawer — *Unit Action & Live Video AI Inspector*:**
  * Saat sebuah unit diklik: menampilkan telemetri lengkap (Koordinat, Kecepatan, Baterai, Sinyal, Kanal Aktif), tombol **`[⚡ FORCE GPS PING (SMS 8901)]`**, dan riwayat log kriptografi HMAC/AES.
  * Saat kamera/drone diklik: menampilkan pemutar video *WebRTC* berlatensi rendah lengkap dengan kotak deteksi *YOLOv8* (Manusia, Kendaraan) dan daftar tangkapan pelat nomor (*ANPR Live Feed*).
* **Bottom Dock — *Time-Slider Mission Playback*:**
  * Kontrol pemutar ulang waktu (*Play/Pause*, kecepatan `1x`–`10x`, pemilih rentang tanggal/jam) untuk meninjau ulang kronologi operasi detik demi detik.

### 3.2 Workspace 2: *AI-Assisted Target & Entity Profiler Studio*
* **Panel Kiri — *Target Roster & Risk Leaderboard*:** Daftar target/entitas yang sedang dipantau, diurutkan berdasarkan **Skor Risiko (0–100)** beserta label klasifikasi (*Critical*, *High*, *Medium*, *Low*).
* **Panel Tengah Atas — *Interactive Entity Knowledge Graph (Cytoscape.js)*:**
  * Visualisasi simpul (*nodes*) dan garis hubung (*edges*) antara: **Individu/Target**, **Nomor Telepon/Perangkat**, **Kendaraan (Pelat Nomor)**, **Menara BTS/Lokasi**, **Infrastruktur Siber (Domain/IP/ASN/SSL)**, dan **File Barang Bukti Forensik**.
  * Fitur *1-Click Expand Node* dan penyorotan otomatis jalur hubungan terpendek (*Shortest Path Analysis*) antar dua target.
* **Panel Tengah Bawah — *Pattern-of-Life & Rendezvous Matrix*:**
  * Grafik *Heatmap Jam-vs-Hari* aktivitas target, daftar titik kumpul utama (*Dwell Clusters* hasil algoritma HDBSCAN), serta daftar deteksi pertemuan (*Co-Location / Rendezvous Events*) ketika dua target berada di lokasi/BTS yang sama.
* **Panel Kanan — *Explainable Risk Card & Local LLM Dossier Generator*:**
  * Rincian komponen penyusun Skor Risiko (kontribusi skor Siber, Spasial, Visual, dan Forensik).
  * Asisten Analis AI (*Local LLM Chat & Summary*) dengan tombol **`[📄 GENERATE TARGET DOSSIER PDF]`**.

### 3.3 Workspace 3: *Converged Cyber-Physical SIEM & SOC Console*
* **Top Ribbon — *SOC KPIs & Threat Level*:** Menampilkan *Events Per Second (EPS)*, jumlah *Active Critical Alerts*, *Mean Time to Detect (MTTD)*, dan status kepatuhan keamanan SPBE/BSSN.
* **Center-Left — *Real-Time Alert Queue & Sigma Detection Stream*:** Tabel aliran peringatan keamanan *real-time* lengkap dengan tingkat keparahan, aturan *Sigma* yang terpicu, sumber IP/perangkat, dan korelasi lokasi fisik.
* **Center-Right — *MITRE ATT&CK Enterprise & Mobile Matrix*:** Peta panas taktik dan teknik serangan yang sedang aktif (*Initial Access*, *Persistence*, *Privilege Escalation*, *Credential Access*, *Command & Control*, *Exfiltration*).
* **Bottom Panel — *Cyber-Physical Correlation & SOAR Playbook Bar*:**
  * Visualisasi khusus **Impossible Travel & Anti-Spoofing Inspector** (membandingkan titik IP login siber dengan titik koordinat GPS/BTS personel di peta).
  * Tombol eksekusi respons cepat (*SOAR Lite*): **`[🛡️ BLOCK IP IN FIREWALL]`**, **`[🔒 REVOKE DEVICE TOKEN]`**, dan **`[❄️ FREEZE ARTIFACTS TO FORENSIC VAULT]`**.

### 3.4 Workspace 4: *Digital Forensic Toolkit (DFIR) & Evidence Vault*
* **Panel Akuisisi & *Immutable Chain-of-Custody Ledger*:**
  * Area unggah bukti digital (*Drag-and-Drop Evidence Intake*) yang otomatis menghitung **SHA-256**, **SHA-512**, ukuran byte, *magic header*, dan menyimpannya ke dalam buku besar berantai hash (`Block #N`, `Prev Hash`, `Current Evidence Hash`, `Examiner ID`, `Timestamp`).
  * Fitur **`[✅ VERIFY VAULT INTEGRITY]`** untuk membuktikan di hadapan hukum bahwa tidak ada satu bit pun barang bukti atau log yang diubah sejak diakuisisi.
* **Tab Pemeriksaan Spesialis (*Forensic Analysis Workbenches*):**
  1. **Image & Document Forensics Tab:** Penampil metadata EXIF lengkap (tombol *Plot GPS Photo to C4ISR Map*), serta komparator berdampingan antara foto asli dan hasil **Error Level Analysis (ELA)** untuk mendeteksi area tempelan/manipulasi piksel.
  2. **Mobile, SQLite & YARA Triage Tab:** Pemindai artefak perangkat Android, pemulih baris database `.sqlite` / `-wal` yang terhapus (*Deleted Record Carver*), serta hasil pemindaian aturan **YARA** untuk deteksi *malware/stalkerware*.
  3. **Audio Whisper & OCR Intelligence Tab:** Pemutar rekaman audio bukti dengan transkripsi teks otomatis (via *Faster-Whisper*) dan hasil ekstraksi teks dokumen foto (via *PaddleOCR*) disertai pencari entitas otomatis (NIK, Nomor HP, Rekening, Email, Koordinat).
  4. **Network PCAP & Unified Super-Timeline Tab:** Tabel kronologi gabungan (*Super-Timeline*) yang menyatukan log peristiwa dari seluruh barang bukti, serta tombol **`[⚖️ CETAK BAP FORENSIK RESMI (PDF)]`**.

---

## BAB IV: SPESIFIKASI TEKNIS PROTOKOL, ALGORITMA AI, & MESIN INTI

### 4.1 Spesifikasi Protokol SMS Biner Terenkripsi (Port 8901)
Untuk menjamin keamanan perintah *Force GPS Ping* pada jaringan 2G/GSM dengan batasan ukuran 140 byte per *User Data* SMS Biner (PDU Mode):

#### A. Struktur Paket Perintah (*C2 Command Packet*: Server $\rightarrow$ Android Agent)
Total panjang payload biner: **22 Byte** (dikodekan ke Base64 atau dikirim sebagai *raw binary SMS* ke Port `8901`):

| Offset Byte | Nama Field | Ukuran | Tipe Data | Keterangan Spesifikasi |
| :---: | :--- | :---: | :---: | :--- |
| `0 .. 1` | `MAGIC_HEADER` | 2 Byte | `uint16` | Konstanta `0x5446` (`"TF"` — penanda paket protokol TFAEL). |
| `2` | `PROTOCOL_VER` | 1 Byte | `uint8` | Versi protokol (`0x02` untuk v2.0). |
| `3` | `CMD_CODE` | 1 Byte | `uint8` | `0x01` = *Force GPS Ping*, `0x02` = *Enable High-Freq Track*, `0x03` = *Wipe Ephemeral Cache*. |
| `4 .. 7` | `TIMESTAMP_UTC` | 4 Byte | `uint32` | *Unix Epoch Timestamp* (detik). Ditolak oleh perangkat jika selisih waktu `> 300 detik`. |
| `8 .. 9` | `NONCE_ID` | 2 Byte | `uint16` | Angka acak unik per perintah. Disimpan di *rolling cache* perangkat untuk mencegah *Replay Attack*. |
| `10 .. 21` | `HMAC_TAG_96` | 12 Byte | `bytes[12]` | 96-bit pertama dari `HMAC-SHA256(Device_Secret_Key, Byte[0..9])`. |

#### B. Struktur Paket Balasan Telemetri (*Encrypted Reply Packet*: Android Agent $\rightarrow$ Server)
Payload telemetri dienkripsi menggunakan **AES-128-GCM** dengan kunci unik perangkat (`Device_AES_Key`):
* **IV / Nonce:** 12 Byte.
* **Plaintext Telemetry Struct (28 Byte sebelum enkripsi):**
  * `LATITUDE_E7` (`int32`, 4 Byte): Lintang $\times 10^7$ (presisi hingga ~1,1 cm).
  * `LONGITUDE_E7` (`int32`, 4 Byte): Bujur $\times 10^7$.
  * `ALTITUDE_M` (`int16`, 2 Byte): Ketinggian dalam meter.
  * `SPEED_KMH` (`uint8`, 1 Byte): Kecepatan gerak dalam km/jam.
  * `BATTERY_PCT` (`uint8`, 1 Byte): Persentase baterai (`0–100`) + bit ke-8 sebagai penanda status *charging*.
  * `FIX_TYPE` (`uint8`, 1 Byte): `1` = GNSS/GPS Presisi, `2` = Wi-Fi/Fused, `3` = Fallback Cell-ID BTS, `9` = SOS Triggered.
  * `MCC` (`uint16`, 2 Byte), `MNC` (`uint16`, 2 Byte), `LAC/TAC` (`uint32`, 4 Byte), `CID` (`uint64`, 8 Byte — dipadatkan 7 byte): Identitas menara BTS yang sedang melayani perangkat.
* **GCM Authentication Tag:** 16 Byte.

### 4.2 Formula AI-Assisted Target Threat Scoring (Skor Risiko 0–100)
Setiap entitas target $e$ diberikan skor risiko komposit $R(e) \in [0, 100]$ yang dihitung secara *real-time* dengan bobot terkalibrasi:

$$R(e) = \min\left(100, \; w_{\text{cyber}} \cdot S_{\text{cyber}}(e) + w_{\text{spatial}} \cdot S_{\text{spatial}}(e) + w_{\text{visual}} \cdot S_{\text{visual}}(e) + w_{\text{forensic}} \cdot S_{\text{forensic}}(e)\right)$$

Dengan pembobotan standar (dapat disesuaikan oleh Komandan/Analis):
* **$S_{\text{cyber}}(e)$ (Bobot $w_{\text{cyber}} = 0.25$):** Dihitung dari jumlah port rawan terbuka, kelemahan sertifikat SSL/DNS, keterkaitan dengan infrastruktur berbahaya di *Knowledge Graph*, dan jumlah *alert* SIEM terkait entitas.
* **$S_{\text{spatial}}(e)$ (Bobot $w_{\text{spatial}} = 0.30$):** Dihitung dari skor anomali *Isolation Forest* pada pola pergerakan (*Pattern-of-Life*), kedekatan dengan zona terlarang (*Geofence proximity*), dan frekuensi pertemuan tersembunyi (*Rendezvous/Co-location*).
* **$S_{\text{visual}}(e)$ (Bobot $w_{\text{visual}} = 0.20$):** Dihitung dari kecocokan pelat nomor (*ANPR Watchlist Hit*) atau kemunculan atribut visual target pada kamera CCTV/Drone di sekitar objek vital.
* **$S_{\text{forensic}}(e)$ (Bobot $w_{\text{forensic}} = 0.25$):** Dihitung dari kemunculan identitas target di dalam barang bukti digital yang terverifikasi, kecocokan aturan *YARA/IoC*, atau bukti manipulasi dokumen/citra.

### 4.3 Algoritma Deteksi *Impossible Travel* (Korelasi Siber-Fisik SIEM)
Setiap kali terjadi peristiwa autentikasi/akses jaringan oleh akun personel $u$ pada waktu $t_{\text{cyber}}$ dari alamat IP yang dipetakan ke koordinat $(\phi_1, \lambda_1)$, mesin SIEM mengambil posisi fisik terakhir perangkat personel $u$ dari tabel telemetri (GPS/BTS/APRS) pada waktu $t_{\text{phys}}$ di koordinat $(\phi_2, \lambda_2)$:
1. Hitung jarak lingkaran besar (*Great-Circle Distance* $d$ dalam km) menggunakan rumus **Haversine**.
2. Hitung kecepatan perpindahan semu:
   $$v_{\text{apparent}} = \frac{d}{\max\left(\frac{|t_{\text{cyber}} - t_{\text{phys}}|}{3600}, \; 0.05\right)} \quad (\text{km/jam})$$
3. Jika $d > 15\text{ km}$ dan $v_{\text{apparent}} > 900\text{ km/jam}$ (melebihi kecepatan pesawat komersial), sistem langsung memicu **Critical Cyber-Physical Alert (`MITRE T1078 - Valid Accounts / Impossible Travel`)**.

### 4.4 Algoritma Forensik Citra (*Error Level Analysis / ELA*) & Rantai Hash Bukti
1. **Error Level Analysis (ELA):** Saat foto bukti (`JPEG/PNG`) diunggah, mesin forensik menyimpan ulang gambar pada tingkat kompresi referensi (90%), menghitung selisih absolut per kanal piksel $|I_{\text{orig}}(x,y) - I_{\text{recomp}}(x,y)|$, dan meningkatkan skala kecerahan selisih ($\times 15$). Area foto yang ditempel atau diedit secara digital akan tampak menyala terang karena memiliki tingkat degradasi kuantisasi yang berbeda dari latar belakang aslinya.
2. **Hash-Chained Evidence Ledger:** Setiap barang bukti ke-$k$ yang masuk ke brankas diikat dengan rumus rantai kriptografi:
   $$H_{\text{chain}}^{(k)} = \text{SHA256}\left(H_{\text{chain}}^{(k-1)} \;\|\; \text{SHA512}(\text{FileBytes}_k) \;\|\; \text{Timestamp}_k \;\|\; \text{ExaminerID}_k\right)$$
   Sehingga perubahan 1 byte pun pada bukti masa lalu akan merusak seluruh rantai hash berikutnya dan langsung terdeteksi.

---

## BAB V: KONTRAK ENDPOINT REST API & KANAL REAL-TIME WEBSOCKET

Seluruh komunikasi API menggunakan awalan `/api/v2` dengan autentikasi `Bearer JWT` dan otorisasi `RBAC`:

| Kategori Modul | Metode & Path Endpoint | Fungsi Utama Endpoint | Contoh Ringkas Payload / Respons |
| :--- | :--- | :--- | :--- |
| **1. C4ISR & SMS C2** | `GET /api/v2/units` | Mengambil daftar seluruh unit lapangan beserta posisi, kanal aktif, baterai, dan status terbaru. | `[{"unit_id": "ALPHA-01", "channel": "SMS_2G", "lat": -6.1754, "lon": 106.8272, "battery": 84}]` |
| **1. C4ISR & SMS C2** | `POST /api/v2/c2/force-ping` | Mengirim perintah *Force GPS Ping* melalui SMS Biner Port 8901 ber-tanda tangan HMAC-SHA256. | Req: `{"unit_id": "ALPHA-01", "reason": "Lost 4G Signal"}`<br>Res: `{"packet_hex": "54460201...", "hmac_valid": true, "status": "DISPATCHED"}` |
| **1. C4ISR & SMS C2** | `POST /api/v2/telemetry/ingest` | Menerima telemetri dari Data 4G, Balasan SMS AES-GCM, Dekoder APRS AX.25, LoRa MQTT, & Satelit. | Req: `{"source": "APRS_VHF", "callsign": "YB0TFL-9", "raw_packet": "..."}` |
| **2. AI Target Profiling** | `GET /api/v2/targets` | Mengambil daftar profil target lengkap dengan Skor Risiko (0–100) dan ringkasan ancaman. | `[{"target_id": "TGT-09", "code_name": "Kestrel", "risk_score": 88, "risk_level": "CRITICAL"}]` |
| **2. AI Target Profiling** | `GET /api/v2/targets/{id}/graph` | Mengambil struktur simpul (*nodes*) dan relasi (*edges*) *Knowledge Graph* beserta *Pattern-of-Life*. | `{"nodes": [...], "edges": [...], "dwell_clusters": [...], "rendezvous_events": [...]}` |
| **2. AI Target Profiling** | `POST /api/v2/targets/{id}/dossier` | Memicu *Local LLM* untuk menyusun narasi *Target Dossier* dan mengekspor laporan PDF. | `{"target_id": "TGT-09", "executive_summary": "...", "recommended_actions": [...]}` |
| **3. Cyber-Physical SIEM** | `GET /api/v2/siem/alerts` | Mengambil antrean *alert* SIEM yang telah dipetakan ke matriks **MITRE ATT&CK** dan koordinat fisik. | `[{"alert_id": "SIM-402", "mitre_id": "T1078", "type": "IMPOSSIBLE_TRAVEL", "severity": "CRITICAL"}]` |
| **3. Cyber-Physical SIEM** | `POST /api/v2/siem/soar/execute` | Mengeksekusi *Playbook SOAR* (*Block IP*, *Isolate Endpoint*, atau *Freeze Forensic Snapshot*). | Req: `{"alert_id": "SIM-402", "action": "ISOLATE_AND_FREEZE"}` |
| **4. Digital Forensics** | `POST /api/v2/forensics/evidence` | Mengunggah barang bukti digital, menghitung SHA-256/512, menjalankan EXIF/ELA/YARA, dan mengunci rantai bukti. | Res: `{"evidence_id": "EVD-2026-001", "sha256": "9f86d08...", "chain_hash": "4b2277...", "ela_score": 0.78}` |
| **4. Digital Forensics** | `GET /api/v2/forensics/verify-chain` | Memverifikasi keutuhan seluruh rantai hash pada *Immutable Evidence Vault*. | `{"vault_intact": true, "total_blocks": 42, "verified_at": "2026-10-22T10:50:00Z"}` |
| **4. Digital Forensics** | `POST /api/v2/forensics/bap-export` | Menghasilkan dokumen resmi **Berita Acara Pemeriksaan (BAP) Forensik Digital** siap cetak. | `{"bap_number": "BAP/DFIR/X/2026/014", "court_admissible": true}` |
| **5. Real-Time Bus** | `WS /ws/v2/tactical-stream` | Kanal WebSocket *full-duplex* untuk mendorong perubahan posisi peta, *alert* SIEM, dan status C2 secara instan. | Event types: `UNIT_MOVED`, `SMS_PING_ACK`, `GEOFENCE_BREACH`, `SIEM_ALERT`, `EVIDENCE_LOCKED` |

---

## BAB VI: SKEMA BASIS DATA TERPADU (*UNIFIED DATABASE SCHEMA*)

Seluruh data disimpan di dalam satu klaster **PostgreSQL 16** yang diperkuat dengan 4 ekstensi tingkat enterprise (`PostGIS`, `TimescaleDB`, `Apache AGE`, dan `pgvector`):

| Nama Tabel / Koleksi | Ekstensi / Mesin | Kolom Utama (*Primary Attributes*) | Peran dalam Produk |
| :--- | :--- | :--- | :--- |
| `tactical_units` | `PostGIS` | `unit_id (PK)`, `callsign`, `role`, `device_imei`, `hmac_key_ref`, `aes_key_ref`, `active_channel`, `last_geom (POINTZ)`, `battery_pct`, `status` | Menyimpan status terkini seluruh personel, kendaraan, drone, dan radio lapangan. |
| `telemetry_history` | `TimescaleDB` + `PostGIS` | `time (Hypertable PK)`, `unit_id`, `channel`, `geom (POINTZ)`, `speed_kmh`, `mcc`, `mnc`, `lac`, `cid`, `rssi`, `raw_signature` | Menyimpan jutaan titik riwayat pergerakan untuk fitur *Mission Playback* dan *Pattern-of-Life ML*. |
| `bts_cell_towers` | `PostGIS` | `cell_pk (PK)`, `mcc`, `mnc`, `lac`, `cid`, `geom (POINT)`, `coverage_radius_m`, `azimuth_deg` | Basis data luring lokasi menara BTS seluruh Indonesia untuk triangulasi saat GPS terhalang. |
| `target_profiles` | `pgvector` + Relational | `target_id (PK)`, `code_name`, `category`, `risk_score`, `risk_breakdown (JSONB)`, `osint_summary (JSONB)`, `appearance_embedding (VECTOR)` | Menyimpan profil sasaran, skor ancaman dinamis, hasil rekognisi OSINT, dan vektor atribut visual. |
| `entity_knowledge_graph` | `Apache AGE` (Graph) | **Vertices:** `Person`, `Device`, `Vehicle`, `Domain`, `IP`, `Location`, `Evidence`<br>**Edges:** `USES_DEVICE`, `DRIVES`, `VISITED`, `RESOLVES_TO`, `CO_LOCATED_WITH`, `EXTRACTED_FROM` | Menyimpan grafik keterkaitan multi-dimensi untuk analisis jaringan dan *Entity Resolution*. |
| `siem_security_events` | `TimescaleDB` | `event_time (PK)`, `event_id`, `source_type`, `src_ip`, `src_geom (POINT)`, `user_id`, `sigma_rule_id`, `mitre_tactic`, `mitre_technique`, `severity`, `raw_log` | Menyimpan log keamanan terpusat, deteksi aturan *Sigma*, dan korelasi *Impossible Travel*. |
| `forensic_evidence_vault` | Relational + Crypto Ledger | `block_index (PK)`, `evidence_id`, `case_id`, `file_name`, `file_size`, `magic_mime`, `sha256_hash`, `sha512_hash`, `prev_chain_hash`, `curr_chain_hash`, `exif_json`, `ela_anomaly_score`, `yara_matches (JSONB)`, `examiner_id`, `acquired_at` | Menyimpan barang bukti digital dengan rantai hash tak terubah (*Chain of Custody*) dan hasil pemeriksaan forensik. |

---

## BAB VII: PENANGANAN SKENARIO BATAS (*EDGE CASES*) & MEKANISME *FAILOVER*

| No. | Skenario Kondisi Batas (*Edge Case*) | Perilaku Otomatis Produk (*System Fallback & Handling*) |
| :-: | :--- | :--- |
| 1. | **Perangkat dinas kehilangan internet 4G DAN berada di basement tanpa sinyal satelit GPS** | Saat menerima perintah SMS Port 8901, agen Android mendeteksi bahwa *GNSS Fix* gagal diperoleh setelah `15 detik`. Agen otomatis beralih mengambil identitas menara BTS (`MCC/MNC/LAC/CID`) dan `RSSI` yang tertangkap antena GSM, mengenkripsinya dengan AES-128-GCM, lalu membalas SMS. Peta Pusat Komando menampilkan **lingkaran estimasi radius BTS** berwarna kuning. |
| 2. | **Penyerang mencoba mengirim SMS Biner palsu (*Spoofed Command*) ke nomor perangkat dinas** | Agen Android menghitung ulang `HMAC-SHA256` dan memeriksa `Timestamp` serta `Nonce`. Karena tanda tangan tidak cocok, perintah **diabaikan 100%** tanpa menyalakan GPS, dan agen mengirimkan laporan *Security Tamper Alert* ke modul **SIEM** begitu koneksi pulih. |
| 3. | **Kabel internet utama Pusat Komando terputus total (*Total National/ISP Outage*)** | Peta otomatis disajikan dari *Local Vector Tile Server*, pemeriksaan AI (YOLOv8, OCR, Whisper, dan Local LLM Dossier) tetap berjalan di GPU lokal, komunikasi lapangan tetap berjalan melalui **Modem GSM Lokal, Radio VHF/UHF APRS, dan LoRa**, serta seluruh fungsi SIEM dan Forensik beroperasi penuh tanpa degradasi. |
| 4. | **Upaya manipulasi file bukti di penyimpanan disk server oleh pihak tidak bertanggung jawab** | Saat investigator atau auditor menjalankan pemeriksaan `Verify Vault Integrity`, sistem menghitung ulang hash file di disk terhadap `sha256_hash`, `sha512_hash`, dan `curr_chain_hash` di buku besar. Jika ada selisih 1 bit, sistem langsung menandai blok bukti tersebut dengan peringatan **CRITICAL TAMPER DETECTED** dan memicu alarm SIEM. |

---

## BAB VIII: RENCANA RILIS PRODUK (*RELEASE ROADMAP*) & METRIK KESUKSESAN PRODUK

### 8.1 Tahapan Rilis Produk (*Product Release Train — 16 Minggu*)
1. **Rilis v1.0 (Minggu Ke-4) — *Core C4ISR & Encrypted SMS C2 MVP*:**
   * Peta Taktis 2D/3D Luring, *1-Click Force GPS Ping* via SMS Biner Port 8901 (HMAC-SHA256 + AES-128-GCM), Fallback Triangulasi BTS, dan Aplikasi Android Endpoint Agent.
2. **Rilis v1.5 (Minggu Ke-8) — *Off-Grid Telemetry, Video AI, & AI Target Profiling*:**
   * Integrasi Radio VHF/UHF APRS (AX.25), LoRa MQTT, Satelit LEO, *Live Video AI (YOLOv8 + ANPR)*, *Entity Knowledge Graph*, *Pattern-of-Life Clustering*, dan *Local LLM Target Dossier Generator*.
3. **Rilis v1.8 (Minggu Ke-12) — *Converged Cyber-Physical SIEM & SOAR Lite*:**
   * Ingesti log multi-sumber, mesin deteksi *Sigma*, visualisasi matriks **MITRE ATT&CK**, deteksi *Impossible Travel*, analitik perilaku *UEBA*, dan aksi mitigasi *1-Click SOAR*.
4. **Rilis v2.0 GA (Minggu Ke-16) — *Digital Forensic Toolkit (DFIR) & Full System Hardening*:**
   * *Immutable Evidence Vault* (SHA-256/512), forensik citra/dokumen (*EXIF-to-Map & ELA*), *triage* perangkat mobile/SQLite, pemindai *YARA*, transkripsi *Whisper/OCR* luring, *Super-Timeline*, generator **BAP Forensik PDF**, serta uji beban 1.000 unit serentak.

### 8.2 Metrik Telemetri Keberhasilan Produk (*Product North-Star Metrics*)
* **Time-to-Fix on Blackout (`TTF-B`):** Median waktu akuisisi lokasi via SMS Port 8901 $\le 22\text{ detik}$ (batas maksimum $< 35\text{ detik}$).
* **Time-to-Dossier (`TTD`):** Waktu rata-rata kompilasi profil target lengkap beserta *Knowledge Graph* dan narasi *Local LLM* $\le 15\text{ detik}$ (batas maksimum $< 60\text{ detik}$).
* **Cyber-Physical Alert Latency (`CPAL`):** Waktu sejak log akses anomali diterima hingga alarm *Impossible Travel* menyala di peta 3D $\le 1,2\text{ detik}$.
* **Forensic Chain Verification Speed (`FCVS`):** Kecepatan verifikasi ulang 1.000 blok rantai hash barang bukti di bawah $2\text{ detik}$ dengan tingkat keutuhan kriptografi $100\%$.

---

## LEMBAR PENGESAHAN DOKUMEN KEBUTUHAN PRODUK (PRD)

**Disusun di:** Jakarta  
**Pada Tanggal:** 22 Oktober 2026  

| Disusun Oleh, | Diperiksa Oleh, | Disetujui Oleh, |
| :---: | :---: | :---: |
| **Lead Product Manager & Principal System Architect** | **Kepala Tim Rekayasa AI, SOC SIEM & Laboratorium DFIR** | **Pejabat Pembuat Komitmen / Komandan Satuan Kerja** |
| <br><br><br>*( .................................................. )*<br>NIP/NRP. ......................................... | <br><br><br>*( .................................................. )*<br>NIP/NRP. ......................................... | <br><br><br>*( .................................................. )*<br>NIP/NRP. ......................................... |
