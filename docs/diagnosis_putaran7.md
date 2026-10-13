# LAPORAN DIAGNOSIS EMPIRIS CACAT D1–D9 (PUTARAN 7)
**Tanggal Diagnosis**: 2026-10-09 20:13:59
**Metode**: Eksekusi programatik langsung tanpa mengubah kode layanan (`services/`, `core/`).

## 1. Cacat D1: Atribut Spesifikasi Dijawab 'Belum Tersedia' Padahal Data Ada di Katalog
### Bukti Empiris:
- **Kunci Dict Produk di Katalog Asli** (`KB-D01`): `['brand', 'cpu', 'cpu_tier', 'cpu_vendor', 'created_at', 'display', 'gpu', 'gpu_class', 'gpu_dedicated', 'gpu_type', 'harga_idr', 'has_hdd', 'image_url', 'includes_monitor', 'is_accessory', 'kategori', 'kode', 'nama', 'need_tags', 'os', 'panel', 'ram', 'ram_gb', 'ram_type', 'raw_data', 'refresh_hz', 'screen_inch', 'srgb_pct', 'storage', 'storage_ssd_gb', 'tags', 'updated_at', 'usage_text', 'vram_gb']`
- **Kunci Dict Produk di `state['produk_tampil']`**: `['harga', 'harga_formatted', 'image_url', 'kategori', 'kode', 'nama', 'spesifikasi']`
- **Kunci Kritis yang Hilang di State**: `['ram_gb', 'cpu', 'gpu', 'storage_ssd_gb', 'vram_gb', 'display']`
- **Nilai di Katalog**: `{"ram_gb": 8, "cpu": "Intel Core i3-13100T", "gpu": "Intel UHD Graphics 730", "storage_ssd_gb": 512, "vram_gb": null, "display": "Tidak termasuk monitor"}`
- **Nilai di State**: `{"ram_gb": null, "cpu": null, "gpu": null, "storage_ssd_gb": null, "vram_gb": null, "display": null}`
### Alur Kode Penyebab:
Pada `services/action_engine.py` baris 647–650, handler `_handle_tanya_spesifikasi` memprioritaskan pencarian produk dari `state.get('produk_tampil')`:
```python
for pt in state.get('produk_tampil', []):
    if str(pt.get('kode', '')).upper() == str(code).strip().upper():
        p = pt; break
```
Karena `p` diambil dari `formatted_prods` (yang hanya berisi `[kode, nama, kategori, harga, harga_formatted, spesifikasi, image_url]`), maka pembacaan atribut `p.get('ram')`, `p.get('cpu')`, `p.get('gpu')` selalu menghasilkan `None`, memicu status `atribut_tidak_tersedia`.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 2. Cacat D2: Permintaan Spek Umum Tanpa Atribut Menghasilkan 'Lainnya' dan 'Belum Tersedia'
### Bukti Empiris:
- Hasil eksekusi engine dengan `args.atribut = None`: `status = atribut_tidak_tersedia`
  Fakta: `{"status": "atribut_tidak_tersedia", "atribut_ditanya": "lainnya", "pesan": "Informasi spesifikasi 'lainnya' tidak tersedia untuk produk tersebut."}`
- Hasil eksekusi engine dengan `args.atribut = AtributSpesifikasiEnum.LAINNYA`: `status = atribut_tidak_tersedia`
  Fakta: `{"status": "atribut_tidak_tersedia", "atribut_ditanya": "lainnya", "pesan": "Informasi spesifikasi 'lainnya' tidak tersedia untuk produk tersebut."}`
### Alur Kode Penyebab:
Pada `services/action_engine.py` baris 634:
`attr = args.atribut or AtributSpesifikasiEnum.LAINNYA`
Dan pada baris 723–724, cabang `elif attr == AtributSpesifikasiEnum.LAINNYA:` menetapkan `val = None` tanpa merangkum spesifikasi utama produk, sehingga langsung memicu `ada_tidak_tersedia = True`.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 3. Cacat D3: Standar Bawaan Masih Mengarang Fakta Angka
### Bukti Empiris (Grep Nomor Baris di `services/action_engine.py`):
- Baris 402: `if ram_gb_min and (p.get("ram_gb") or 0) < ram_gb_min:`
- Baris 404: `if storage_gb_min and (p.get("storage_ssd_gb") or 0) < storage_gb_min:`
- Baris 538: `p_cpu_tier = p.get("cpu_tier") or 1`
- Baris 539: `p_ram = p.get("ram_gb") or 8`
- Baris 540: `p_ssd = p.get("storage_ssd_gb") or 256`
- Baris 543: `min_cpu = 1`
- Baris 544: `min_ram = 8`
- Baris 545: `min_ssd = 256`
- Baris 546: `min_vram = 0`
### Dampak pada Replay reg-10 Turn 6:
- Pesan Pelanggan: *"Itu semua untuk kantoran?"*
- Respons Bot: *"Mohon maaf Kak, untuk detail RAM-nya, berdasarkan sistem, ASUS Vivobook 14 A1405 ini memiliki RAM 8 GB dan SSD 256 GB. Untuk kebutuhan kerja, spesifikasi ini sudah memenuhi standar minimum yang dibutuhkan ya. Kakak ingin tahu detail lain atau ada preferensi lainkah?"*
Karena data di state tidak memuat `ram_gb` aktual, `p.get('ram_gb') or 8` mengevaluasi angka bawaan 8 GB dan `storage_ssd_gb or 256` mengevaluasi 256 GB, lalu membandingkannya terhadap `min_ram = 8` sehingga menyimpulkan 'memenuhi standar' secara keliru.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 4. Cacat D4: Profil Kebutuhan Basi pada Evaluasi Kecocokan
### Bukti Empiris:
- **Probe #13**:
  * Kebutuhan pada pesan: *"rendering blender seharian"*
  * Profil aktif di state awal: `P01`
  * Profil yang dipakai engine: `P01` (P01 — Pekerjaan Kantoran, Administrasi, dan Pelajar (Penggunaan Dasar))
  * Hasil RAG baru jika di-resolve mandiri: `[('P03', None, None), ('P07', None, None)]`
- **Probe #15**:
  * Kebutuhan pada pesan: *"admin kantor biasa"*
  * Profil aktif di state awal: `P06`
  * Profil yang dipakai engine: `P06` (P06 — Programmer dan Software Developer)
  * Hasil RAG baru jika di-resolve mandiri: `[('P01', None, None)]`
### Alur Kode Penyebab:
Pada `services/action_engine.py` baris 472–474:
```python
profil_id = state.get('profil_aktif')
prof_data = None
if not profil_id and kebutuhan_teks:
    reqs = get_usage_requirements(kebutuhan_teks)
```
Pengecekan `if not profil_id and kebutuhan_teks` menyebabkan kebutuhan baru pada pesan saat ini DIABAIKAN apabila sesi sudah memiliki `profil_aktif` lama.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 5. Cacat D5: Salah Rute Permintaan Baru vs Lanjutan Murni
### Bukti Empiris dari Replay Putaran 6:
| Conv & Turn | Pesan Pelanggan | Aksi Terprediksi | Status Fakta | Respons Bot (Potongan) |
|---|---|---|---|---|
| reg-04 T16 | *"Kalo acer nitro ada?"* | `lanjutan_hasil` | `sukses` | Mohon maaf Kak, saat ini pencarian kami tidak menemukan produk la... |
| reg-04 T22 | *"Merek asus ada tipe apa aja??"* | `lanjutan_hasil` | `sukses` | Mohon maaf, Kak, saat ini belum ada hasil pencarian produk laptop... |
| reg-09 T10 | *"Lenovo gak ada yang cocok?"* | `lanjutan_hasil` | `sukses` | Mohon maaf Kak, saat ini belum ada produk Acer yang masuk dalam k... |
| reg-01 T7 | *"Merek lain yang setara apa?"* | `tidak_jelas` | `tidak_jelas` | Mohon maaf Kak, maksud Kakak masih kurang spesifik ya. Untuk memb... |
| reg-01 T12 | *"Pilihan lain ada?"* | `tidak_jelas` | `tidak_jelas` | Mohon maaf Kak, maksud dari pesan Kakak belum terlalu jelas. Agar... |
| reg-02 T5 | *"Kalo yang di atas itu?"* | `tidak_jelas` | `tidak_jelas` | Mohon maaf Kak, maksud Kakak tadi masih kurang jelas nih. Boleh t... |
### Analisis:
- Permintaan spesifik produk/merek ('acer nitro', 'merek asus', 'lenovo') salah dirutekan ke `lanjutan_hasil` karena prompt menginstruksikan jika produk sedang tampil dan user menyebut kriteria, maka masuk lanjutan. Engine lanjutan_hasil mencari produk relatif terhadap filter sebelumnya sehingga gagal.
- Permintaan lanjutan murni ('merek lain', 'pilihan lain', 'yang di atas itu') dirutekan ke `tidak_jelas` karena parser tidak mengenali entitas merek/kategori.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 6. Cacat D6 & D7: Slot Terbawa ke Kategori Baru dan Batas Anggaran Dilanggar
### Bukti Empiris:
- **D6 (Slot Terbawa)**:
  * `reg-09 T20`: Pesan: *"Ya pokoknya monitor eksternal buat dipakai sama laptop"* -> Aksi: `perbaiki_percakapan` -> Respons: *"Mohon maaf Kak, tadi saya salah menangkap kebutuhan Kakak. Untuk monit"*
  * `reg-09 T21`: Pesan: *"Kan aku minta monitor, bukan desktop?"* -> Aksi: `perbaiki_percakapan` -> Respons: *"Baik Kak, terima kasih atas koreksinya. Jadi, Kakak mencari monitor ek"*
  * `reg-08 T9`: Pesan: *"Jangan terlalu mahal. Dananya cuma 14 juta"* -> Aksi: `lanjutan_hasil` -> Respons: *"Kakak mencari laptop di bawah Rp14.000.000, dan ada dua pilihan yang l"*
  * `reg-08 T11`: Pesan: *"Yakin itu speknya?"* -> Aksi: `perbaiki_percakapan` -> Respons: *"Mohon maaf Kak, karena Kakak menyebutkan merek Asus, apakah Kakak ingi"*
  * Penyebab: State session tidak mereset slot `budget`, `merek`, atau filter saat kategori berubah (misal dari printer ke monitor).
- **D7 (Batas Anggaran Dilanggar)**:
  * `reg-02 T9`: Pesan: *"Yang di bawah 1 juta"* -> Aksi: `lanjutan_hasil` -> Respons: *"Kak, berdasarkan budget sekitar Rp2.299.000, ada 3 pilihan printer yan"*
  * `reg-02 T6`: Pesan: *"Yang lebih mahal dikit"* -> Aksi: `lanjutan_hasil` -> Respons: *"Produk yang ditampilkan sebelumnya itu sudah merupakan opsi tertinggi "*
  * `reg-04 T6`: Pesan: *"Mama bilang kemahalan"* -> Aksi: `lanjutan_hasil` -> Respons: *"Mohon maaf Kak, untuk memastikan rekomendasi terbaik, kami perlu tahu "*
  * Pada `reg-02 T9`, permintaan 'di bawah 1 juta' dijawab bot dengan mengklaim 'budget sekitar Rp2.299.000' dan menampilkan produk di atas Rp2.000.000, melanggar batas anggaran yang diminta pelanggan.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 7. Cacat D8: Inkonsistensi Filter Spesifikasi vs Katalog Nyata
### Hasil Kueri Langsung ke Katalog (`data/katalog.db`):
- **Total Produk di Katalog**: 20 unit
- **Produk dengan RTX 3050**: 1 unit (`[('KB-L07', 'ASUS Vivobook Pro 15 OLED', 'NVIDIA GeForce RTX 3050 6 GB')]`)
- **Total Produk NVIDIA/GeForce**: 8 unit (GeForce: 8 unit)
- **Total Produk RAM DDR5**: 8 unit (`[('KB-D04', 'Lenovo LOQ Tower 17', '16 GB DDR5'), ('KB-D05', 'ASUS ROG Strix G16CHR', '32 GB DDR5'), ('KB-L01', 'Acer Aspire Lite 14', '8 GB DDR5'), ('KB-L06', 'Acer Nitro V 15', '16 GB DDR5'), ('KB-L07', 'ASUS Vivobook Pro 15 OLED', '16 GB DDR5'), ('KB-L08', 'Lenovo LOQ 15', '16 GB DDR5'), ('KB-L09', 'ASUS TUF Gaming A15', '16 GB DDR5'), ('KB-L10', 'Lenovo Legion Pro 5 16', '32 GB DDR5')]`)
- **Total Produk RAM DDR4**: 7 unit
- **Distribusi Merek**: `{'lenovo': 6, 'asus': 5, 'hp': 2, 'acer': 2, 'canon': 2, 'epson': 2, 'brother': 1}`
### Temuan Krusial:
- RTX 3050 **BENAR ADA** di katalog (`KB-L07 ASUS Vivobook Pro 15 OLED`). Pernyataan bot pada `reg-04 T20` bahwa tidak ada RTX 3050 adalah SALAH, sedangkan pernyataan pada `reg-05 T12` yang menawarkan RTX 3050 adalah BENAR.
- RAM DDR5 **BENAR ADA** di katalog (8 unit). Namun `action_engine.py` hanya memfilter `ram_gb` angka tanpa mencocokkan string tipe RAM DDR5, sehingga permintaan DDR5 diabaikan diam-diam.
### Kesimpulan:
**Akar masalah terbukti sepenuhnya.**

## 8. Cacat D9: Uji Stabilitas Parser pada Input yang Dibekukan
### Hasil Pengujian 3x Pemanggilan pada 134 Giliran Input Beku:
- **Total Giliran Diuji ($n$)**: 134
- **Giliran dengan Aksi Persis Sama (Identik 3x)**: 133 / 134 (**99.3%**)
- **Giliran dengan Aksi Bervariasi (Nondeterminisme Murni)**: 1 / 134 (**0.7%**)

### Pembanding terhadap Putaran 6:
- Pada Replay Putaran 6 (end-to-end multi-run), konsistensi hanya **70.9%**.
- Pada input yang dibekukan (input yang persis sama), konsistensi parser mencapai **99.3%**.
- **Artinya**: Sebagian besar ketidakkonsistenan pada Putaran 6 (sekitar 70.9% vs 99.3%) disebabkan oleh **DIVERGENSI STATE** (perbedaan kecil pada turn awal menyebabkan riwayat percakapan dan slot state berbeda, sehingga memicu rantai jawaban berbeda di turn berikutnya). Namun, terdapat pula **nondeterminisme murni LLM** pada giliran tertentu yang pendek/ambigu.

### Contoh Giliran dengan Nondeterminisme Murni LLM:
- `reg-05_T13`: *"RTX 3050 bukan geforce?"* -> Prediksi 3x: `['perbaiki_percakapan', 'tidak_jelas', 'tidak_jelas']`

### Kesimpulan:
**Akar masalah terbukti: Ketidakstabilan disebabkan oleh divergensi state multi-giliran dikombinasikan dengan nondeterminisme parser pada kueri pendek/ambigu.**
