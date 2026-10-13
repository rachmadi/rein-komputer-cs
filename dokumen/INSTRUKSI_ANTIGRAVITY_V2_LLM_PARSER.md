# Instruksi Antigravity v2: LLM sebagai Penerjemah dan Penutur, Inti Deterministik untuk Fakta

Dokumen ini **menggantikan arah** instruksi sebelumnya tentang router niat, jalur cepat, templat jawaban, dan perbaikan berbasis pola. Butir lama yang masih berlaku ada di bagian 12. Bekerja per fase, **berhenti meminta persetujuan setelah Fase 0 dan setelah Fase 4**.

---

## 1. Latar dan alasan

Pengujian di Telegram dan audit log menunjukkan bahwa semua jawaban "natural" selama ini ternyata templat Python. Pemahaman niat dilakukan regex dan model 1B, dan hasil LLM sering ditimpa aturan. Akibatnya bot salah pada kalimat yang belum dikodekan ("Emang spek segitu cukup?", "Yang tanya HP 14 siapa?", "Buat hiburan"). Aturan bahasa tidak mungkin lengkap, karena kalimat pelanggan tidak terbatas.

**Rancangan baru:** LLM memahami dan berbicara. Kode memegang fakta dan keselamatan.

## 2. Aturan tidak boleh dilanggar

- **R1. Semua kalimat percakapan ke pelanggan ditulis LLM.** Kode tidak menulis kalimat percakapan. Kode hanya boleh menampilkan: (a) kartu produk (data dari hasil alat), dan (b) satu kalimat darurat bila LLM gagal secara teknis (lihat bagian 8). Kalimat darurat dicatat sebagai kegagalan dan dihitung di evaluasi.
- **R2. Pemahaman bahasa dan niat hanya oleh LLM.** Dilarang regex, kamus kata kunci, atau if-else untuk menentukan sapaan, persona, merek, kritik, kebutuhan, atau niat. Kode hanya **memvalidasi** keluaran terstruktur LLM (skema, enum, rentang, keberadaan di katalog).
- **R3. Keluaran parser tidak boleh ditimpa kode.** Jika tidak valid atau ragu, hasilnya `tidak_jelas`, lalu LLM bertanya kepada pelanggan.
- **R4. Perilaku baru ditambah lewat skema aksi, alat, prompt, atau contoh few-shot,** bukan dengan menambah pola bahasa di kode.
- **R5. Produk, harga, dan spesifikasi hanya dari hasil alat.** LLM tidak mengetik angka harga atau spesifikasi. Kartu produk dirakit kode.

## 3. Alur per giliran

```
Pesan pelanggan
  -> [1 PARSER LLM]    pesan + state ringkas + riwayat -> JSON {aksi, argumen, pembaruan_state}
  -> [2 VALIDATOR]     skema/enum/rentang; merek/kode produk dicek ke katalog (tanpa menimpa aksi)
  -> [3 MESIN DETERMINISTIK]  jalankan aksi: RAG, SQL, evaluasi, info toko -> FAKTA (JSON)
  -> [4 GENERATOR LLM] aksi + fakta + riwayat + gaya -> {teks, pertanyaan_diajukan}
  -> [5 PEMERIKSA]     teks vs fakta (harga/produk/istilah terlarang)
  -> kirim: kartu produk dulu (jika ada), lalu teks
```

Model: **gemma4:e4b untuk tahap 1 dan 4.** Jangan memakai `llama3.2:1b` atau model lain di jalur ini. Parser: `format` = JSON schema (structured output Ollama), `temperature` 0, `num_predict` ≤ 120, mode thinking mati. Generator: `temperature` 0.3 sampai 0.5, `num_predict` ≤ 160. Pertahankan konfigurasi Ollama yang sudah terukur terbaik (flash attention, `keep_alive` konsisten) dan satu model chat di VRAM.

## 4. Himpunan aksi (skema parser)

Keluaran parser: `{"aksi": <enum>, "argumen": {...}, "pembaruan_state": {...}}`. Argumen yang tidak disebut atau tidak jelas dibiarkan kosong, tidak ditebak.

| Aksi | Argumen | Arti |
|---|---|---|
| `sapa` | - | Sapaan pembuka |
| `cari_produk` | `kategori`, `merek`, `nama_model`, `min_harga`, `max_harga`, `ram_gb_min`, `storage_gb_min`, `ukuran_layar` | Pelanggan mencari produk atau spesifikasi eksplisit |
| `minta_rekomendasi` | `kebutuhan_teks`, `persona`, `kategori`, `budget_min`, `budget_max` | Kebutuhan sudah cukup jelas untuk direkomendasikan |
| `jawab_pertanyaan_bot` | `slot` (kebutuhan/aktivitas/budget/kategori/merek/persona), `nilai` | Pelanggan menjawab pertanyaan terakhir bot |
| `evaluasi_kecocokan` | `produk` (kode yang sudah tampil atau disebut), `kebutuhan_teks` | "Cukup nggak?", "yang kedua bagus nggak?" |
| `bandingkan` | `produk` | Membandingkan beberapa produk yang disebut |
| `lanjutan_hasil` | `jenis` (lebih_murah/lebih_mahal/yang_lain/filter_tambahan), `filter` | Menyempitkan atau mengubah hasil sebelumnya |
| `tanya_info_toko` | `topik` (garansi/servis/pembayaran/pengiriman/jam_buka/alamat/lainnya) | Info yang tidak ada di data, arahkan ke staf |
| `perbaiki_percakapan` | `jenis` (salah_paham/keluhan/koreksi), `rujukan` | Pelanggan menegur atau mengoreksi bot |
| `basa_basi` | `jenis` (terima_kasih/pamit/lainnya) | Obrolan di luar topik |
| `tidak_jelas` | `alasan` | Maksud tidak bisa dipastikan |

`pembaruan_state` memuat hal yang baru diketahui: `persona`, `sebutan` (ibu/bapak/kakak, persis seperti pelanggan menyebut), `kebutuhan_teks`, `budget`, `kategori`.

### Input prompt parser
Susun dari: daftar aksi beserta deskripsi satu baris, 10 sampai 14 contoh few-shot, state ringkas (JSON), 6 pesan terakhir, dan pesan baru. State ringkas memuat:
`pending_question` (slot yang terakhir ditanyakan bot, atau null), `slot_diketahui`, `produk_tampil` (daftar `{no, kode, nama, harga}`), `profil_aktif`, dan **daftar merek dan kategori yang ada di katalog** (diambil dinamis dari database).

Contoh few-shot (ambil dari **set pengembangan** saja; set held-out tidak boleh dipakai di prompt):

| State / pesan | Keluaran yang benar |
|---|---|
| (awal) "halo" | `sapa` |
| "jual laptop acer?" | `cari_produk` {kategori: laptop, merek: Acer} |
| pending=kebutuhan; "Buat mama sih bukan buat aku" | `jawab_pertanyaan_bot` {slot: persona, nilai: mama}; pembaruan_state {persona: mama, sebutan: mama} |
| pending=aktivitas; "Paling cuma cari resep dan nonton youtube" | `minta_rekomendasi` {kebutuhan_teks: "cari resep dan nonton YouTube", persona: mama} |
| tampil [3 laptop]; "Emang spek segitu cukup?" | `evaluasi_kecocokan` {produk: [ketiga kode], kebutuhan_teks: "cari resep dan nonton YouTube"} |
| tampil [3 laptop]; "yang kedua bagus nggak?" | `evaluasi_kecocokan` {produk: [kode no. 2]} |
| "Aku tanya kok malah dikasih spek lain" | `perbaiki_percakapan` {jenis: salah_paham} |
| "Yang tanya HP 14 siapa?" | `perbaiki_percakapan` {jenis: keluhan} |
| pending=aktivitas; "Buat hiburan" | `jawab_pertanyaan_bot` {slot: aktivitas, nilai: "hiburan (nonton, browsing)"} |
| kebutuhan diketahui; "Mana?" | `minta_rekomendasi` {kebutuhan_teks dari state} |
| "ada yang lebih murah?" | `lanjutan_hasil` {jenis: lebih_murah} |
| "garansinya berapa lama?" | `tanya_info_toko` {topik: garansi} |
| "laptop RAM 32GB di bawah 20 juta" | `cari_produk` {kategori: laptop, ram_gb_min: 32, max_harga: 20000000} |
| "makasih ya" | `basa_basi` {jenis: terima_kasih} |

## 5. Mesin deterministik per aksi

Semua fungsi murni dan dapat diuji. Hasilnya berupa **fakta JSON**, bukan kalimat.

- **minta_rekomendasi:** `get_usage_requirements(kebutuhan_teks)` (RAG, hanya chunk bertipe `profil`, ambang skor dari `.env`) lalu `search_catalog(profil_id, kategori, budget)`. Hasil: produk, `match_report`, dan ringkasan profil (Minimum/Direkomendasikan/Catatan dari KB). Jika tidak ada profil di atas ambang, fakta = `profil_tidak_ditemukan`.
- **cari_produk:** filter SQL berparameter (merek dan kategori divalidasi ke katalog). Kembalikan produk yang cocok, atau fakta tidak ada beserta merek/kategori yang tersedia.
- **lanjutan_hasil:** jalankan ulang pencarian terakhir dengan perubahan (patokan harga = produk ✅ atau yang tampil terakhir, batas atas eksklusif). Rotasi produk yang sudah tampil **hanya** untuk `yang_lain`.
- **evaluasi_kecocokan (alat baru):** `evaluasi(kode[], profil_id)` mengembalikan per produk: spesifikasi aktual, syarat profil yang terpenuhi, tidak terpenuhi, atau tidak diketahui, serta teks Minimum/Direkomendasikan dari KB. Tidak mencari produk baru. Jika `profil_id` kosong, ambil lewat RAG dari `kebutuhan_teks`.
- **bandingkan:** spesifikasi berdampingan untuk produk yang disebut.
- **tanya_info_toko:** fakta `{topik, data_tersedia: false, kontak_staf: dari .env}`.
- **sapa / basa_basi / perbaiki_percakapan / tidak_jelas:** fakta = state (kebutuhan diketahui, produk yang tampil, pertanyaan terakhir bot, rujukan koreksi). Tidak ada pencarian.

Label ✅ pada kartu produk hanya jika syarat diperiksa dan semuanya terpenuhi (dari `match_report`). Pencarian tanpa kebutuhan memakai judul netral dan tanpa ✅.

## 6. Generator (LLM) dan kartu produk

Keluaran generator berupa JSON `{"teks": "...", "pertanyaan_diajukan": "<slot atau null>"}`. `pertanyaan_diajukan` disimpan ke state sebagai `pending_question` giliran berikutnya.

Prompt sistem generator (boleh disempurnakan, tanpa menambah aturan kata kunci):

```
Kamu customer care Bobby Computer di Telegram. Bicara santai dan sopan dalam bahasa Indonesia,
pakai sebutan yang dipakai pelanggan (ibu, bapak, kakak) dan kata-kata mereka.
Jawab maksimal 3 kalimat dan langsung menjawab pertanyaan pelanggan.
Kamu menerima: aksi, FAKTA hasil sistem, riwayat singkat, dan state.
- Hanya gunakan angka dan produk yang ada di FAKTA. Jangan mengarang. Jangan menulis ulang daftar
  produk atau harga; kartu produk ditampilkan sistem.
- Boleh bernalar dari FAKTA (misalnya apakah spesifikasi cukup untuk aktivitas pelanggan) dengan jujur.
- Jika kebutuhan atau budget belum diketahui, tanyakan SATU hal.
- Jika pelanggan menegur atau bertanya balik, jawab dulu pertanyaannya, minta maaf secukupnya.
- Jangan mengulang salam. Jangan sebut kode internal, nama kolom, atau istilah sistem.
- Untuk garansi, servis, pembayaran, dan info toko yang datanya tidak ada, arahkan ke staf.
```

Kartu produk: nama, harga, spesifikasi singkat, label dari `match_report`; dirakit kode, format Telegram HTML dengan escape; foto hanya bila `image_url` ada; **tidak ada klaim garansi atau stok**.

## 7. State per sesi

Isolasi total antar sesi. Isi: riwayat (maks 8 pesan), `pending_question`, `slot_diketahui` (persona, sebutan, kebutuhan_teks, budget, kategori, merek), `produk_tampil` (urut, dengan nomor), `profil_aktif`. State digabung dari `pembaruan_state` terstruktur. Profil aktif berganti hanya bila `minta_rekomendasi` baru menghasilkan profil lain.

## 8. Pemeriksa dan kegagalan

Setelah generator, kode memeriksa teks: semua nominal "Rp" dan nama produk harus ada di FAKTA atau `produk_tampil`; tidak ada kode internal (P01 dan sejenisnya), nama kolom, "None/nan", klaim garansi atau stok; panjang wajar. Pelanggaran: minta generator menulis ulang **satu kali** dengan catatan pelanggarannya. Jika masih gagal, JSON parser tidak valid setelah satu ulang, atau timeout: kirim kalimat darurat tetap ("Maaf Kak, saya kurang menangkap maksudnya. Boleh diulang, atau mau saya hubungkan ke staf?"). Kalimat darurat **bukan jalur percakapan**: setiap kemunculannya dicatat `FALLBACK` dan dihitung sebagai kegagalan di evaluasi (target ≤ 2% giliran).

## 9. Yang dihapus dari jalur produksi

Pindahkan ke cabang `legacy-rule-based` (untuk pembanding, jangan dipakai di produksi): `intent_router.py` (semua pola), `detect_brand` dan `_match_legacy_query` untuk pemahaman bahasa, `forced_profiles`, templat jawaban berpersona, respons default "salam", flag `BYPASS_LLM1_ON_RAG` dan `USE_LLM_FRAMING`, panggilan `llama3.2:1b`, dan penjaga pra-RAG berbasis kata kunci. Pertahankan: SQL dan filter, RAG, `match_report`, isolasi sesi, log, umpan balik 👍/👎, dan format Telegram.

## 10. Fase kerja

- **Fase 0 (baca saja):** periksa `.env` dan jelaskan model apa yang dipakai di tiap tahap sekarang; peta file yang akan dihapus atau diubah; buat cabang `llm-parser` dari HEAD dan `legacy-rule-based` sebagai arsip; tulis rencana singkat. **Berhenti, tunggu persetujuan.**
- **Fase 1:** skema aksi (Pydantic atau JSON schema), state, parser (prompt, few-shot, structured output), validator, dan tes validator.
- **Fase 2:** mesin deterministik per aksi termasuk alat `evaluasi`, beserta tes deterministik (filter, patokan harga, rotasi, NULL).
- **Fase 3:** generator, pemeriksa, kartu produk, integrasi Telegram (kartu lebih dulu, indikator mengetik, umpan balik), dan log setiap tahap (parse JSON, fakta, teks, pelanggaran).
- **Fase 4:** dataset label dan alat evaluasi (bagian 11), jalankan, laporkan. **Berhenti, tunggu persetujuan.**
- **Fase 5:** iterasi **hanya** lewat prompt, skema, contoh few-shot, dan konteks. Dilarang menambah regex bahasa.
- **Fase 6:** pembersihan jalur produksi, dokumentasi (arsitektur, cara menambah aksi), README.

## 11. Evaluasi

1. **Set label parser** `eval/parse_gold.jsonl` (≥ 150 contoh: state ringkas, pesan, aksi dan argumen yang benar). Sumber: log sesi (dianonimkan), percakapan di laporan, dan variasi buatan (bahasa gaul, typo, persona lain, sindiran, kritik). Bagi **dev (≈100)** dan **held-out (≥50)**. Few-shot hanya dari dev. **Frank memeriksa minimal 30 label** sebelum dipakai (label buatan agen yang sama tidak boleh dijadikan satu-satunya acuan).
2. **Metrik parser (held-out):** akurasi aksi, F1 argumen per slot, % JSON valid, % `tidak_jelas`, latensi.
3. **Percakapan held-out:** 15 sampai 20 percakapan multi-giliran dengan rubrik per giliran (menjawab pertanyaan yang diajukan; tidak ada daftar tanpa kebutuhan; tidak ✅ tanpa syarat; tidak mengulang salam; tidak ada klaim tanpa data). Jalankan tiap percakapan 3 kali. Sertakan lima percakapan dari tangkapan layar ("Ada asus?" sampai "Kan sudah dibilang buat hiburan", serta percakapan "Emang spek segitu cukup?").
4. **Grounding:** persentase jawaban dengan pelanggaran pemeriksa, dan persentase kalimat darurat.
5. **Latensi:** p50 dan p95 per tahap (parse, mesin, generate, kirim), dingin dan hangat, kalimat baru tanpa cache.
6. **Pembanding:** (i) cabang `legacy-rule-based`; (ii) gemma4:e4b; (iii) satu model yang jauh lebih kuat sebagai batas atas (hanya percakapan uji, **tanpa data pelanggan asli**). Laporkan sebagai tabel.
7. **Kriteria penerimaan (held-out):** akurasi aksi parser ≥ 90%; JSON valid ≥ 98%; rubrik lolos ≥ 85% giliran; pelanggaran grounding yang sampai ke pelanggan = 0; kalimat darurat ≤ 2%. Jika tidak tercapai, laporkan angka sebenarnya dan usulkan perbaikan prompt/skema/contoh. Jangan menyetel pada held-out.
8. **Tes:** komponen deterministik (validator, filter, evaluasi, pemeriksa) tetap `pytest` dengan asersi. Evaluasi percakapan dan parser berupa skrip yang melaporkan tingkat lolos. Tes lama yang menegaskan frasa templat dipensiunkan. Daftarkan tes mana yang dipensiunkan dan alasannya.

## 12. Butir lama yang tetap berlaku

HMAC-SHA256 berkunci (`.env`) untuk pseudonim log, anonimkan atau jadwalkan penghapusan `chat_history.jsonl`, kebijakan retensi di README dan pemberitahuan pencatatan di `/start`; daftar merek dinamis dari katalog; bukti isolasi sesi dengan dua `chat_id`; audit sesi bermasalah sebagai pembanding sebelum dan sesudah; format Telegram HTML bebas `**` mentah; tidak ada klaim garansi atau stok; **katalog real belum diimpor sampai ada persetujuan** (rencana impor menyusul setelah Fase 4); penjaga `conftest` yang melarang tes menyentuh `catalog.db` asli.

## 13. Aturan pelaporan

Satu commit per langkah. Hanya angka dari keluaran perintah, dengan nama berkas sumbernya. Dilarang angka proyeksi, simulasi, atau kata "100%/mutlak" tanpa bukti. Tulis eksplisit apa yang belum teruji. Laporan ringkas (di bawah 25 baris), kecuali tabel hasil evaluasi.
