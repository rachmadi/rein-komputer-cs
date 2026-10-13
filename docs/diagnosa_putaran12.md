# Diagnosa Putaran 12 — ReIn Komputer

Tanggal: 2026-10-10
Baseline: tag `sebelum-putaran12` (commit 66d830f)

---

## A1. Pesan "Tanya Ketersediaan Kategori Lain" Saat State Sudah Terisi Kategori/Merek Lain Berakhir di perbaiki_percakapan Lalu Tidak Ada Pencarian

### 1. Mengapa pencarian tidak jalan:
- **Lokasi Kode:** `services/action_engine.py`, baris 1558–1563 & 1593 pada metode `_handle_perbaiki_percakapan`:
  ```python
  if jenis == "koreksi" and has_criteria:
      if state.get("kebutuhan_teks"):
          search_res = self._handle_minta_rekomendasi(args, state)
      else:
          search_res = self._handle_cari_produk(args, state)
  ...
  return ActionResult(aksi=ActionEnum.PERBAIKI_PERCAKAPAN, fakta=fakta, produk_list=[])
  ```
- **Penyebab:** Ketika pesan pelanggan mengandung nada keberatan/keluhan atau nada bingung (contoh log nyata `99b9b3f6adc7`: *"Ada apa gak laptop? Capek deh"* atau *"Weleh. Payah nih si mbak. Yang merek epson, ada printer apa?"*), parser LLM mengklasifikasikan aksi sebagai `perbaiki_percakapan` dengan `jenis="keluhan"` atau `jenis="salah_paham"`.
- Karena kondisi baris 1558 mensyaratkan `jenis == "koreksi"`, maka jenis `"keluhan"` atau `"salah_paham"` mengabaikan seluruh pemanggilan pencarian katalog (`_handle_cari_produk` / `_handle_minta_rekomendasi`), lalu langsung jatuh ke baris 1593 yang mengembalikan `produk_list=[]` tanpa pencarian sama sekali.

### 2. Dari mana merek lama ikut terbawa:
- **Lokasi Kode 1 (Reset Kategori Terlewat):** `services/session_pipeline.py`, baris 192–205:
  ```python
  if parsed.argumen.kategori:
      new_kat_str = str(parsed.argumen.kategori).strip().lower()
      old_kat_str = str(state.get("kategori", "")).strip().lower() if state.get("kategori") else None
      if old_kat_str and new_kat_str != old_kat_str:
          state["kategori"] = new_kat_str
          state["budget"] = None
          state["merek"] = None
          ...
  ```
  Blok reset di atas HANYA dijalankan jika `parsed.argumen.kategori` terisi. Bila parser mengembalikan `perbaiki_percakapan` dan mengisi kategori pada `pembaruan_state.kategori` atau tidak mengisinya di argumen, blok reset ini dilewati.
- **Lokasi Kode 2 (Tanpa Pembersihan Merek di State Update):** `services/action_engine.py`, baris 1524–1525 & 1536–1537:
  Ketika kategori di-update (`state["kategori"] = state_up.kategori` atau `state["kategori"] = args.kategori`), nilai `state["merek"]` dan `state["kriteria_pelanggan"]["merek"]` tidak di-reset sama sekali.
- **Lokasi Kode 3 (Merek Lama Menimpa Pencarian Baru):** `services/action_engine.py`, baris 314 & baris 529:
  ```python
  merek = args.merek or state.get("merek") or kriteria_pelanggan.get("merek")
  ```
  Saat pencarian produk dipanggil, `merek` mengambil fallback dari `state.get("merek")` yang masih menyimpan merek lama (misal `"epson"` dari giliran printer sebelumnya). Ketika pengguna bertanya ketersediaan laptop, filter mencari laptop dengan merek `"epson"` yang tentunya tidak ada di katalog, sehingga seluruh kandidat tersaring habis.

---

## A2. Jalur jawab_pertanyaan_bot (Slot Kebutuhan) Berstatus belum_ada_yang_memenuhi Padahal Produknya Ada di Katalog

### 1. Penelusuran Filter & Ambang:
- **Lokasi Kode:** `services/action_engine.py`, baris 1491–1492:
  ```python
  if slot in ("kebutuhan", "aktivitas") and state.get("kebutuhan_teks"):
      return self._handle_minta_rekomendasi(args, state)
  ```
  Metode `_handle_jawab_pertanyaan_bot` mengarahkan slot kebutuhan ke `_handle_minta_rekomendasi(args, state)`.
- **Ambang RAG:** Di `services/knowledge_service.py` baris 43–45, ambang `RAG_SCORE_THRESHOLD = 0.40`.

### 2. Penyebab Pasti Status `belum_ada_yang_memenuhi`:
1. **Penyebab Utama (Pencemaran State):** Nilai `kategori` atau `merek` di session state tercemar nilai tidak valid. Pada log nyata sesi `99b9b3f6adc7`, parser memetakan teks pertanyaan pengguna *"Ecotank itu apa?"* menjadi `slot="kategori", nilai="Ecotank"`. Validator saat itu tidak menolak kategori non-katalog ini, sehingga `state["kategori"] = "ecotank"`. Saat slot kebutuhan diproses, loop `for p in self.catalog.products:` menyaring produk dengan `p.get("kategori") == "ecotank"`, yang menghasilkan 0 kandidat (`candidates = []`). Karena mereknya ada di katalog global, baris 429 mengembalikan status `belum_ada_yang_memenuhi`.
2. **Penyebab Kedua (Kombinasi Kategori & Merek Lintas Giliran):** Jika pelanggan sebelumnya membahas printer merek Epson, lalu menjawab slot kebutuhan untuk laptop, `state["merek"] = "epson"` tetap aktif. Saat mencari laptop dengan merek Epson, hasilnya 0 produk.
3. **Penyebab Ketiga (Filter Profil Terlalu Ketat):** Pada baris 446 `if candidates and all(not c["passed"] for c in candidates):`, jika teks kebutuhan memetakan ke profil teknis tertentu (misal P02 dengan syarat `srgb_pct >= 100` atau P03 dengan `vram_gb >= 8`), produk laptop biasa di katalog gagal memenuhi syarat minimum hard filter di `apply_filters`, sehingga ActionEngine menyatakan `belum_ada_yang_memenuhi` walau unit laptop tersedia di stok.

---

## A3. Pemeriksaan Basis Pengetahuan (KB) Mengenai "tangki tinta/EcoTank"

- **Penjelasan Umum "tangki tinta (ink tank)": ADA.**
  Di berkas `data/knowledge/panduan_kebutuhan_v2.md` baris 408:
  > *- Inkjet tangki tinta (ink tank): biaya cetak per lembar rendah; cocok untuk cetak dokumen dan foto volume menengah sampai sering, serta usaha kecil.*
  Serta baris 409 membandingkan biaya per halaman dengan inkjet kartrid.
- **Penjelasan Merek Dagang "EcoTank": TIDAK ADA.**
  Istilah spesifik "EcoTank" sama sekali tidak terdapat dalam seluruh isi dokumen KB (`panduan_kebutuhan_v2.md`).
  Istilah "EcoTank" hanya ada di katalog produk SQLite/CSV pada nama produk Epson (`KB-P02 Epson EcoTank L121` dan `KB-P03 Epson EcoTank L3210`) dengan spesifikasi atribut `teknologi: "Ink Tank"`.
- **Status:** Sesuai instruksi, dokumen KB dibiarkan utuh dan tidak ditambah.
