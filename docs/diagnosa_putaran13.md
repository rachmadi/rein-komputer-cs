# Diagnosa Putaran 13 — ReIn Komputer

Tanggal: 2026-10-10
Baseline: tag `sebelum-putaran13` (commit `934dba8`)

---

## A1. Tempat yang Menulis/Menimpa `state["produk_tampil"]`, `"produk_terakhir_dibahas"`, `"history_produk_tampil"`

Berikut penelusuran menyeluruh seluruh berkas, fungsi, nomor baris, dan kondisi yang menulis atau menimpa ketiga field tersebut:

### 1. `services/session_pipeline.py`
- **Baris 280–283** (di dalam `process_turn`, blok pergantian kategori):
  - Kondisi: Saat `parsed.argumen.kategori` berubah berbeda dari `old_kat_str`.
  - Dampak:
    ```python
    state["produk_tampil"] = []
    state["produk_terakhir_dibahas"] = None
    state["history_produk_tampil"] = []
    ```
- **Baris 445–456** (di dalam `process_turn`, blok pasca eksekusi action):
  - Kondisi: `if action_res.produk_list:` (terjadi pada aksi `cari_produk`, `minta_rekomendasi`, `bandingkan`, dan `lanjutan_hasil` jika menghasilkan produk).
  - Dampak:
    - `state["produk_tampil"] = action_res.produk_list` (MENIMPA total set produk tampil).
    - `state["history_produk_tampil"].append(p)` (menambahkan produk baru yang belum ada di riwayat).
    - Baris 455–456: `if len(action_res.produk_list) == 1: state["produk_terakhir_dibahas"] = action_res.produk_list[0].get("kode")`.
- **Baris 457–460** (di dalam `process_turn`, blok pasca eksekusi action):
  - Kondisi: `elif action_res.fakta.get("rujukan_dipakai"):` dan `len(rujukan_list) == 1`.
  - Dampak: `state["produk_terakhir_dibahas"] = rujukan_list[0]`.

### 2. `services/action_engine.py`
- **Baris 1503–1508** (di dalam `_handle_jawab_pertanyaan_bot` saat slot `kategori` berganti):
  - Kondisi: `if old_kat and val_cat != old_kat:`.
  - Dampak:
    ```python
    state["produk_tampil"] = []
    state["produk_terakhir_dibahas"] = None
    state["history_produk_tampil"] = []
    ```
- **Baris 1607–1609** (di dalam `_handle_perbaiki_percakapan` saat slot `kategori` berganti):
  - Kondisi: `if old_kat and val_cat != old_kat:`.
  - Dampak:
    ```python
    state["produk_tampil"] = []
    state["produk_terakhir_dibahas"] = None
    state["history_produk_tampil"] = []
    ```

### 3. Perilaku Khusus per Aksi
- **`lanjutan_hasil`**:
  - `termurah_dari_tampil` (baris 1334): Mengembalikan `produk_list=[formatted_item]`. Akibatnya, pada `session_pipeline.py` baris 446, seluruh set produk lama di `state["produk_tampil"]` TERTIMPA dan hanya menyisakan 1 produk termurah tersebut. Pelanggan kehilangan akses ke produk lain yang tadinya ada di daftar.
  - `lebih_murah` (baris 1368): Mengembalikan kandidat produk baru yang lebih murah (`produk_list=matches`). Akibatnya, `state["produk_tampil"]` tertimpa produk baru. Jika tidak ada yang lebih murah (`tidak_ada_lebih_murah`), `produk_list=[]`, sehingga `state["produk_tampil"]` tidak berubah.
  - `opsi_lain` / `halaman_berikutnya`: Mengembalikan halaman berikutnya, menimpa `state["produk_tampil"]`.
- **`perbaiki_percakapan`**:
  - Jika ada kriteria produk (`C1`): Memanggil pencarian katalog (`_handle_cari_produk` / `_handle_minta_rekomendasi`), mengembalikan `produk_list` baru, menimpa `state["produk_tampil"]`.
  - Jika tidak ada kriteria produk (`jenis="keluhan"` atau `"salah_paham"` tanpa parameter): Mengembalikan `produk_list=[]`, `state["produk_tampil"]` dipertahankan.
- **`bandingkan`**:
  - Baris 1214: `return ActionResult(aksi=ActionEnum.BANDINGKAN, fakta=fakta, produk_list=prods)`.
  - Mengembalikan 2 produk yang dibandingkan dalam `produk_list`. Akibatnya `state["produk_tampil"]` tertimpa hanya 2 produk yang dibandingkan.
- **`evaluasi_kecocokan`**:
  - Baris 1010: `return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)` (`produk_list=[]`).
  - `state["produk_tampil"]` TIDAK ditimpa, tetapi `state["produk_terakhir_dibahas"]` diperbarui ke `rujukan_dipakai[0]` (jika 1 unit) via `session_pipeline.py` baris 460.

---

## A2. Mengapa `tanya_beruntun` / `pilihan_konkret` Tidak Aktif pada Pertanyaan Budget Beruntun

### 1. Apa yang Dihitung oleh Penghitung Saat Ini:
Pada `services/session_pipeline.py` baris 474–493:
```python
has_clear_direction = bool(
    (action_res.produk_list and len(action_res.produk_list) > 0)
    or (parsed.argumen.kebutuhan_teks and len(parsed.argumen.kebutuhan_teks.strip()) >= 4)
    or (parsed.aksi in (ActionEnum.CARI_PRODUK, ActionEnum.MINTA_REKOMENDASI) and (parsed.argumen.merek or parsed.argumen.kategori or parsed.argumen.max_harga))
)

if has_clear_direction:
    tanya_beruntun = 0
else:
    if action_res.fakta.get("status") in ("tanya_kebutuhan", "profil_tidak_ditemukan", "tidak_jelas") or parsed.aksi in (ActionEnum.JAWAB_PERTANYAAN_BOT, ActionEnum.TIDAK_JELAS):
        tanya_beruntun += 1
    else:
        tanya_beruntun = 0
```

### 2. Akar Masalah Kegagalan:
1. **Penghitung Salah Sasaran**: `tanya_beruntun` hanya memeriksa status ketiadaan arah global (`tanya_kebutuhan`, `profil_tidak_ditemukan`, `tidak_jelas`). Ketika bot menanyakan *budget*, aksi yang berjalan di giliran sebelumnya umumnya adalah rekomendasi/pencarian yang meminta konfirmasi budget (`pertanyaan_diajukan: "budget"`). Pertanyaan slot ini tidak dihitung sebagai pertanyaan beruntun terhadap slot tersebut.
2. **Kondisi Reset Terlalu Agresif**: Ketika pelanggan sudah menyebutkan kebutuhan di awal (misal *"buat kuliah"*), `state["kebutuhan_teks"]` atau `parsed.argumen.kebutuhan_teks` terisi dengan panjang ≥ 4 karakter. Baris 476 `has_clear_direction` langsung bernilai `True`. Akibatnya, pada baris 486–487: `tanya_beruntun` **selalu di-reset ke 0** pada setiap giliran, meskipun pelanggan tidak menjawab budget dan bot terus-menerus menanyakan budget!
3. **Status Fakta Tidak Masuk Kriteria**: Saat budget ditanyakan, status fakta bisa berupa `"sukses"`, `"tidak_ada_dalam_anggaran"`, atau fakta pencarian lainnya. Tidak satu pun dari status ini cocok dengan tuple `("tanya_kebutuhan", "profil_tidak_ditemukan", "tidak_jelas")`, sehingga otomatis jatuh ke `else: tanya_beruntun = 0`.
4. **Pilihan Konkret Terbatas pada Kebutuhan**: Blok `pilihan_konkret` (baris 500–521) hanya mengambil judul profil (misal *"Kantoran, Belajar..."*, *"Desain Grafis..."*), sama sekali tidak mendukung pilihan rentang budget konkret (seperti *"< 7 juta", "7–12 juta", "> 12 juta"*).

---

## A3. Estimasi Ukuran Prompt + FAKTA dengan Lembar Spesifikasi 3 Laptop dan 3 Printer pada `num_ctx = 4096`

### 1. Rincian Ukuran Komponen:
- **`GENERATOR_SYSTEM_PROMPT`**: ~2.500 karakter (~700 token).
- **Riwayat Percakapan (8 giliran terakhir)**: ~2.000 karakter (~570 token).
- **Konteks Pendukung (produk tampil, fokus, slot pelanggan)**: ~500 karakter (~140 token).
- **Lembar Spesifikasi per Produk** (kolom non-kosong bermakna + `raw_data` ringkas label→nilai):
  - 1 unit laptop: ~350 karakter (~100 token).
  - 1 unit printer: ~260 karakter (~75 token).
- **Total FAKTA dengan 3 Laptop + 3 Printer (6 produk)**: ~1.820 karakter (~520 token).

### 2. Total dan Evaluasi Konteks:
- **Kondisi Normal (Maks 3 produk / giliran)**:
  Total karakter: ~5.980 karakter → **~1.700 token** (~**41%** dari kapasitas `num_ctx = 4096`).
- **Kondisi Maksimal (6 produk: 3 laptop + 3 printer)**:
  Total karakter: ~6.820 karakter → **~1.950 token** (~**47%** dari kapasitas `num_ctx = 4096`).

### 3. Kesimpulan:
**Sangat muat di `num_ctx = 4096`** dengan cadangan ruang (buffer) lebih dari 50%.
*Catatan teknis:* Pembuatan lembar spesifikasi wajib menyaring field internal yang berukuran besar seperti `need_tags` (463 karakter), `image_url`, dan timestamp database, sehingga hanya pasangan spesifikasi teknis dan raw_data fungsional yang dikirimkan sebagai label→nilai ringkas.
