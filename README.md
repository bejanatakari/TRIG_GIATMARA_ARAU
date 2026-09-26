# TRIG PROFESSIONAL
### Auto Workshop Management & POS System (GM GEAR ARAU)

Sistem Pengurusan Bengkel Automotif & Sistem Titik Jualan (POS) profesional dan sedia-produksi (*production-ready*) yang dibangunkan khusus untuk **GM GEAR ARAU (GIATMARA ARAU)**.

Sistem ini mempunyai pemisahan modul bagi 3 kategori operasi utama bengkel:
1. 🚗 **Servis Kenderaan Auto** (Mekanikal enjin, servis minyak & cecair, brek, diagnostik)
2. 🎨 **Mengetuk & Mengecat** (Body & Paint, simen putty, cat oven 2K, kod warna kilang, visual panel)
3. 🏍 **Servis Motosikal** (Minyak 4T/2T, sprocket & rantai, talaan Fi/karburator)

---

## 🛠 Ciri-Ciri Utama Sistem

- **Platform Pemilihan Kategori Servis**: Pengasingan penuh data invois, kad kerja, alat ganti dan laporan mengikut kategori pilihan.
- **Butang Tukar Mod Servis**: Memudahkan pengguna beralih antara Servis Auto, Ketuk & Cat, atau Servis Motosikal pada bila-bila masa.
- **Transaksi Kewangan & Inventori Atomik**: Pengurangan stok lejar secara atomik (`BEGIN IMMEDIATE`), pengesanan idempotensi, dan pemulangan stok automatik jika invois dibatalkan.
- **Sokongan Bayaran Deposit & Pelbagai Kaedah**: Tunai, DuitNow QR, Pindahan Bank, Kad & E-Wallet.
- **Format Cetakan Standard Industri**:
  - Cetakan Dokumen A4 (Invois Rasmi, Sebut Harga, Kad Kerja).
  - Cetakan Resit Terma 80mm (*POS Thermal Printer*).
  - Cetakan Label Kod QR Alat Ganti.
- **Kawalan Keselamatan & Log Audit**: Pemisahan peranan (Admin, Juruwang, Mekanik) dan penjejakan log audit penuh.
- **Sifar Kebergantungan Pihak Ketiga (Zero External Dependencies)**: Menggunakan Python 3 Standard Library dan JavaScript tulen (*Vanilla JS*), tanpa perlu `npm install` atau `pip install`.

---

## 🚀 Panduan Menjalankan Sistem

### 1. Keperluan Sistem
- Python 3.8 ke atas (Standard Library sahaja).
- Sebarang Pelayar Web moden (Google Chrome, Microsoft Edge, Safari, Firefox).

### 2. Mulakan Pangkalan Data (Pertama Kali Sahaja)
Untuk menjana pangkalan data SQLite bersama data awal (Admin, Juruwang, Mekanik, Inventori dan Kenderaan demo):
```bash
python3 seed_data.py
```

### 3. Jalankan Pelayan Aplikasi
```bash
python3 app.py 8080
```
Atau menggunakan skrip bash:
```bash
chmod +x start_server.sh
./start_server.sh
```

### 4. Buka Sistem di Pelayar Web
Buka alamat berikut di pelayar web anda:
```
http://localhost:8080
```

---

## 🔑 Akaun Lalai (Default Logins)

| Peranan | Emel | Kata Laluan | Akses |
| :--- | :--- | :--- | :--- |
| **Admin / Pengurus** | `gmgearkubangpasu@gmail.com` | `Admin@GMGear2026!` | Akses Penuh (Tetapan, Pengguna, Audit Log) |
| **Juruwang** | `juruwang@gmgear.my` | `Cashier@123` | POS, Bayaran, Resit, Penutupan Harian |
| **Mekanik** | `mekanik@gmgear.my` | `Mechanic@123` | Kad Kerja, Diagnosis, Imbasan Alat Ganti |

---

## 🧪 Pengesahan & Ujian Automasi

Sistem ini dilengkapi dengan 23 ujian penerimaan (*acceptance tests*) automatik:
```bash
python3 verify_app.py
```
Dan ujian konkurensi multi-thread:
```bash
python3 test_concurrency.py
```

---

## 📁 Struktur Fail Projek

```text
├── app.py                 # Pelayan Web REST API HTTP Multi-threaded
├── business_logic.py      # Logik transaksi atomik, nombor turutan & inventori
├── database.py            # Skema pangkalan data SQLite WAL & indeks
├── seed_data.py           # Skrip penjanaan data permulaan & pengguna
├── verify_app.py          # Suite ujian penerimaan (23 Acceptance Tests)
├── test_concurrency.py    # Ujian integriti stok konkurensi
├── start_server.sh        # Skrip permulaan pantas
├── trig_pos.db            # Fail pangkalan data SQLite
├── .gitignore             # Tetapan pengabaian fail sementara git
└── static/
    ├── index.html         # Frontend SPA (Single Page Application)
    ├── app.js             # Pengawal aplikasi JavaScript SPA & routing
    ├── style.css          # Tema industri gelap & susun atur cetakan A4/80mm
    └── qr.js              # Penjana Kod QR berasaskan SVG/Canvas
```
