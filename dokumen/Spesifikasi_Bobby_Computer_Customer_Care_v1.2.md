# Spesifikasi Sistem
## Bobby Computer Customer Care — Product Recommendation & Catalog Assistant

**Versi:** 1.2 Draft
**Status:** Menunggu persetujuan pengguna
**Basis:** v1.1, disesuaikan dengan hasil analisis implementasi `chatbot.py` terhadap katalog dummy `Katalog_Komputer_RAG.pdf`

### Ringkasan perubahan dari v1.1

| # | Perubahan | Asal temuan di `chatbot.py` |
|---|---|---|
| 1 | **Normalisasi input** wajib sebelum intent apa pun (§5A). Pencocokan hanya per token, tidak per substring. | "Terserah." dan "Halo, Kak!" tidak dikenali; "ram" cocok dengan "p**ram**ming"; "RAM-nya" gagal |
| 2 | **Urutan routing intent** ditetapkan (§5B). Resolusi referensi dilakukan **sebelum** menjawab pertanyaan produk. | "Yang kedua harganya berapa?" menjawab semua harga |
| 3 | **Jawaban atas `last_question`** yang tidak dikenali ditangani lewat klasifikasi tertutup, bukan pertanyaan ulang (§3, §5C). | "Untuk kerja" memicu pertanyaan kebutuhan lagi |
| 4 | **Leksikon kebutuhan** (§22) diperluas: kerja, kuliah, mahasiswa, skripsi, "editing video", dst. | "kerja", "kuliah", "mahasiswa" tidak menghasilkan kebutuhan |
| 5 | Tag kebutuhan **diturunkan saat ingestion**, tidak dicocokkan dari teks saat query (§16, §22). Ada tag + kualifier ("desain ringan", "gaming menengah"). | `usage_matches` melebar: design→editing, programming→"AI development", gaming hanya L05 |
| 6 | **Resolusi nama produk** (§11.1): kode, nama lengkap, varian, urutan, "yang tadi". | "Berapa harga AstraBook 15 Pro?" gagal tanpa kandidat |
| 7 | **Pertanyaan produk tidak mengubah constraint** (§11.3). | "Prosesornya Intel atau AMD?" mengunci filter prosesor |
| 8 | **Penanganan atribut tidak tersedia secara deterministik** (stok, baterai, garansi, warna, port, dst.) dan **guard kategori generik** (§18, §19). | Hanya "printer" yang diblok; baterai/stok jatuh ke LLM |
| 9 | `budget_target` **wajib dipakai** (§8.2). "Paling murah" tanpa kebutuhan tetap dijawab (§9). | Target harga disimpan tapi tidak dipakai |
| 10 | **Cakupan state**: multi-need, preferensi dibersihkan saat kebutuhan/kategori berganti, `asked_slots`, pembatalan mereset state (§3, §4, §14). | `use_case` tunggal, `cheapest` menempel, "terserah" berulang tanpa batas |
| 11 | **Nilai `category`** diperjelas: "komputer"/"pc" = laptop + desktop (§19). | "komputer" dipetakan ke desktop |
| 12 | **Testabilitas** (§26): fungsi murni tanpa global, tanpa I/O saat import, NLU dan katalog bisa disuntik, Level 1 tanpa panggilan jaringan. | Script monolit dengan `while True` dan `state` global |
| 13 | Acceptance test diperluas ke A–AM, dengan tabel keterlacakan dari bug ke tes (§23). | |

---

# 1. Tujuan Sistem

Bobby Computer Customer Care adalah sistem customer service berbasis katalog produk yang membantu pelanggan menemukan produk yang sesuai **secepat mungkin**.

Sistem bukan:

- formulir pengumpulan requirement yang harus lengkap;
- mesin filtering harga;
- chatbot yang terus-menerus bertanya;
- sekadar mesin pencarian RAG;
- LLM yang bebas memilih atau mengarang produk.

> **Memahami clue yang sudah diberikan pelanggan, segera menawarkan produk yang relevan, lalu membantu pelanggan mempersempit atau memilih produk berdasarkan informasi berikutnya.**

---

# 2. Prinsip Utama

## P1 — Offer First, Filter Later

Jika sudah ada informasi yang cukup untuk penawaran yang berguna, sistem **WAJIB menawarkan produk terlebih dahulu**. Sistem tidak boleh langsung meminta budget, RAM, prosesor, OS, merek, atau software jika belum diperlukan.

```text
Pelanggan: Butuh laptop.
CS: Laptopnya mau dipakai untuk apa, Kak?
Pelanggan: Untuk kerja.
CS: Untuk kerja, ada dua laptop yang bisa dipertimbangkan: ...
```

## P2 — Budget Bukan Prasyarat

Pelanggan tetap diberi rekomendasi walaupun belum tahu budget, belum menetapkan budget, atau mengatakan "terserah" / "belum tahu".

## P3 — Clue Awal Sudah Cukup untuk Menawarkan

Clue yang dapat langsung dipakai apabila didukung katalog: laptop + desain, programming, gaming, mahasiswa/kuliah, kerja/kantor.

> **Kebutuhan pelanggan lebih penting daripada kelengkapan requirement.**

Pernyataan identitas seperti "saya mahasiswa" **adalah clue kebutuhan** (`student`), bukan hanya `user_type`.

## P4 — Klarifikasi Hanya Jika Diperlukan

Sistem boleh mengajukan **satu pertanyaan yang paling berguna** bila belum ada clue. Jawaban pelanggan langsung dipakai. Setiap slot (`category`, `need`) ditanyakan **maksimal satu kali** (dicatat di `asked_slots`). Setelah itu, jawaban "terserah"/"belum tahu"/yang tidak dikenali dijawab dengan **sebaran pilihan** (§14), bukan pertanyaan yang sama.

## P5 — Jujur terhadap Katalog

Jika tidak ada produk yang memenuhi permintaan, sistem menyatakannya dan menawarkan alternatif terdekat (§8.4). Sistem tidak membengkokkan fakta agar produk terlihat cocok.

## P6 — Pemahaman Bahasa Bersifat Deterministik Dulu

Normalisasi, leksikon kebutuhan, parsing angka, resolusi referensi, dan atribut produk ditangani tanpa LLM. LLM hanya dipanggil bila langkah deterministik tidak menghasilkan keputusan (§20).

---

# 3. State Percakapan

```text
category
needs[]            (daftar kebutuhan aktif)
user_type
preferences        (cheapest | most_expensive | large_ram | large_processor)
constraints        (budget_max, budget_min, budget_target, processor, operating_system)
offered_products[] (berurutan)
selected_product
last_question      (slot + teks pertanyaan)
asked_slots        (slot yang sudah ditanyakan)
```

| Field | Isi |
|---|---|
| `category` | `laptop`, `desktop`, `computer` (laptop + desktop), `monitor`, atau kosong (= `computer`, tanpa aksesori). |
| `needs[]` | Satu atau lebih tag dari §22. Kebutuhan baru yang eksplisit **menggantikan** daftar lama (§4). Dua kebutuhan dalam satu kalimat dipertahankan keduanya. |
| `user_type` | `mahasiswa`, `siswa`, `pegawai`. Tidak ditebak dari sapaan. Menyebut `mahasiswa` juga menambahkan `student` ke `needs`. |
| `preferences` | Dibersihkan saat `needs` atau `category` berganti (§4). |
| `constraints` | Tetap berlaku sampai pelanggan mengoreksi atau membatalkan. |
| `offered_products` | Urutan sesuai tampilan, dipakai untuk "yang pertama/kedua". |
| `selected_product` | Produk yang secara eksplisit dipilih atau dirujuk. |
| `last_question` | Slot yang ditanyakan dan teksnya. **Dibaca oleh routing** (§5B langkah 8). |
| `asked_slots` | Mencegah pertanyaan yang sama diulang. |

---

# 4. Konteks Saat Ini vs Riwayat

Informasi eksplisit yang lebih baru menggantikan yang lama untuk konteks keputusan.

```text
Pelanggan: Laptop untuk kantor.
Pelanggan: Eh, buat programmer.
→ needs = [programming]   (bukan office)
```

**Reset parsial:** ketika `needs` atau `category` berganti secara eksplisit, `preferences` (cheapest, most_expensive, large_ram, large_processor) dikosongkan dan `selected_product`/`offered_products` diganti dengan hasil baru. `constraints` (budget, prosesor, OS) tetap, kecuali pelanggan mengoreksinya.

**Reset penuh:** pembatalan (§14A) mengosongkan seluruh state.

---

# 5. Jenis Informasi dalam Percakapan

1. New Need
2. Requirement Update
3. Constraint
4. Price Preference
5. Target Price
6. Product Question
7. Product Selection
8. Correction
9. Uncertainty
10. Cancellation
11. Answer to Last Question
12. Small Talk (salam, terima kasih, perpisahan)
13. Comparison
14. Unavailable Info Question
15. Category Availability Question
16. Purchase Intent
17. Reference ("yang pertama", "yang tadi", nama atau kode produk)

---

# 5A. Normalisasi Input

Semua pesan dinormalisasi **sebelum** intent apa pun:

1. huruf kecil;
2. buang tanda baca, kecuali titik/koma di dalam angka (`12.000.000`, `9,5 juta`);
3. tanda hubung dan underscore menjadi spasi (`ram-nya` → `ram nya`);
4. gabungkan sufiks `-nya` untuk pencocokan atribut (`ram nya` dan `ramnya` dianggap sama);
5. singkatan umum: `jt`→`juta`, `gk/gak/ga/nggak`→`tidak` (untuk negasi), `yg`→`yang`, `utk`→`untuk`, `dgn`→`dengan`, `bgt`→`banget`;
6. spasi berulang diringkas.

**Pencocokan hanya per token atau frasa utuh, tidak per substring.** `ram` tidak boleh cocok dengan `programming`; `game` tidak boleh cocok dengan kata lain yang memuatnya; `word` tidak boleh cocok dengan `password`.

---

# 5B. Urutan Routing Intent

Routing berjalan berurutan; keputusan pertama yang terpenuhi dipakai.

| Langkah | Tindakan |
|---|---|
| 1 | Normalisasi (§5A). |
| 2 | **Small talk dan pembatalan**: salam, terima kasih, perpisahan, "siapa kamu", "batal/nggak jadi". |
| 3 | **Koreksi** ("aku tanya laptop, bukan harga"): ubah bentuk respons berikutnya (§13). |
| 4 | **Resolusi referensi**: kode, nama produk, urutan, "yang tadi" → `target_products` untuk giliran ini (§11.1). Dilakukan **sebelum** menjawab harga/spesifikasi. |
| 5 | **Batas katalog**: kategori yang tidak ada, atribut yang tidak ada (§18, §19). |
| 6 | **Pertanyaan produk / perbandingan** atas `target_products` (§11, §12). Tidak mengubah constraint. |
| 7 | **Niat beli** (§18). |
| 8 | **Jawaban atas `last_question`**: tafsirkan pesan dulu sebagai nilai slot yang ditanyakan (§5C). |
| 9 | **Ekstraksi kebutuhan, constraint, preferensi** → OFFER / FILTER / RANK (§7–§10). |
| 10 | **Ketidakpastian** ("terserah", "belum tahu") → §14. |
| 11 | **Tanya satu hal** atau tawarkan sebaran (§14). |
| 12 | **LLM-NLU** (§17), hanya jika langkah 1–11 tidak menghasilkan keputusan. |

---

# 5C. Jawaban atas `last_question` yang Tidak Dikenali

Jika `last_question.slot = need` dan balasan tidak mengandung kata di leksikon §22:

1. panggil LLM-NLU dengan **klasifikasi tertutup**: pilih satu atau lebih tag dari daftar §22, atau `none`;
2. jika tag ditemukan → langsung OFFER;
3. jika `none` → jangan mengulang pertanyaan. Katakan singkat bahwa belum jelas kebutuhannya, lalu tawarkan **sebaran** (§14).

Contoh: "Buat ngerjain skripsi" → NLU memetakan ke `student`.

---

# 6. Siklus Rekomendasi

```text
NORMALIZE → ROUTE
    ↓
Apakah sudah ada clue yang cukup?
    ↓
Tidak ──→ ASK ONE USEFUL QUESTION (maks. 1x per slot) / sebaran
    │
    ↓ Ya
OFFER PRODUCT
    ↓
Pelanggan memberi informasi baru
    ↓
ANSWER / REFINE / NEW OFFER
```

---

# 7. Definisi OFFER

**OFFER bukan daftar harga.** Offer adalah CS memberikan produk yang relevan berdasarkan kebutuhan yang diketahui.

## 7.1 Isi satu penawaran

1. nama produk;
2. 2–3 spesifikasi yang relevan dengan kebutuhan;
3. **dasar pemilihan**, yaitu kutipan atau parafrase "Penggunaan yang disarankan" dari katalog, termasuk kualifikasinya (misalnya "desain ringan");
4. harga sebagai informasi pendukung.

Penawaran **disusun dari field terstruktur dan template**, bukan menempelkan teks mentah payload.

## 7.2 Jumlah dan urutan

- Maksimal **3 produk**. Bila kandidat lebih banyak, sebutkan bahwa ada pilihan lain.
- Urutan tanpa preferensi: tag utama dulu, lalu harga naik. Urutan ini deterministik, bukan skor kemiripan embedding.

## 7.3 Tag utama dan tag terkait

- **Tag utama:** kebutuhan disebut langsung di katalog. Masuk penawaran.
- **Tag terkait:** tidak disebut langsung tetapi ada kecocokan tertulis (misalnya editing video/rendering untuk desain). Hanya boleh ditawarkan **dengan label jujur**:

```text
Creator 15 tidak disebut khusus untuk desain di katalog, tapi cocok untuk
editing video dan memakai GPU RTX 3050 6 GB.
```

Kecocokan tidak boleh dinaikkan. "Desain ringan" tidak menjadi "desain profesional".

## 7.4 Desktop dan aksesori

- Penawaran desktop wajib menyebut bahwa **monitor tidak termasuk**.
- Monitor adalah **aksesori** (§19) dan tidak ikut kandidat utama kecuali diminta.
- Tidak boleh mengklaim kompatibilitas port atau koneksi monitor–desktop.

## 7.5 Multi-need

Jika `needs` berisi lebih dari satu tag, kandidat adalah produk yang memiliki **semua** tag utama (AND). Jika tidak ada, tawarkan produk untuk tiap kebutuhan secara terpisah dan katakan bahwa tidak ada satu produk yang menyebut keduanya.

---

# 8. Filtering

```text
Pelanggan: Untuk desain.          → OFFER
Pelanggan: Yang di bawah 12 juta. → FILTER
Pelanggan: Yang paling murah.     → RANK
```

## 8.1 Parsing budget

| Ungkapan | Arti |
|---|---|
| "di bawah 12 juta" | `harga < 12.000.000` |
| "maksimal / maks / paling tinggi / nggak lebih dari 12 juta" | `harga ≤ 12.000.000` |
| "di atas 10 juta" | `harga > 10.000.000` |
| "sekitar / kisaran / 12 jutaan" | `budget_target = 12.000.000` |
| "12jt", "12 juta", "Rp12 juta", "12.000.000", "9,5 juta" | 12.000.000 / 9.500.000 |

Kata "budget", "dana", atau "uang" tanpa penanda lain **tidak** menentukan jenis batas. Gunakan penanda di tabel. Jika hanya ada "budget 12 juta" tanpa penanda, perlakukan sebagai `≤`.

## 8.2 Budget target (wajib dipakai)

`budget_target` harus memengaruhi hasil. Dari kandidat kebutuhan aktif, ambil maksimal 3 produk dengan selisih harga terkecil terhadap target, sebagian di bawah dan sebagian di atas bila ada. Menyimpan target tanpa memakainya adalah cacat.

## 8.3 Budget tidak mengubah kebutuhan

Filter harga diterapkan pada kandidat kebutuhan yang sedang aktif.

## 8.4 Hasil kosong

Nyatakan tidak ada, sebutkan fakta terdekat dari katalog, dan tawarkan relaksasi satu filter.

```text
Pelanggan: Laptop di bawah 5 juta.
CS: Mohon maaf, Kak, laptop termurah di katalog kami adalah NusaTech
    Student 14 di Rp7.999.000, jadi belum ada yang di bawah Rp5 juta.
    Mau saya jelaskan laptop tersebut?
```

Pesan "belum ada ... yang memenuhi" saja tanpa alternatif tidak memenuhi spesifikasi.

---

# 9. Ranking

```text
NEED → FILTER → RANK → PICK
```

- "yang paling murah" → harga terendah pada kandidat;
- "yang paling mahal" → harga tertinggi.

Jika kandidat hanya satu, sebutkan bahwa itu satu-satunya pilihan.

**Tanpa kebutuhan:** "Laptop yang paling murah" tetap dijawab langsung tanpa menanyakan kebutuhan: pilih produk termurah di kategori. Jika kategori juga belum ada ("yang paling murah aja"), tawarkan termurah per kategori utama (laptop dan desktop). Hal ini mengikuti P1 dan P4.

---

# 10. Preferensi Spesifikasi

Sistem hanya memakai angka yang ada di katalog.

| Preferensi | Perlakuan |
|---|---|
| "RAM gede" | Bandingkan `ram_gb`. Jika semua sama (semua laptop 16 GB), katakan sama dan jelaskan perbedaan lain (DDR4 vs DDR5). Tidak memaksa ranking. |
| "storage gede" | Bandingkan kapasitas. |
| "GPU kuat" | Bandingkan hanya **seri dan VRAM** yang tertulis. Tanpa skor atau FPS. |
| "prosesor gede" | Katalog tidak memuat core, clock, atau skor. **Tidak diranking.** Heuristik tier (i3/i5/i7/i9, Ryzen 3/5/7/9) **tidak boleh** dipakai sebagai ranking. Sebutkan tipe prosesor kandidat. |

---

# 11. Product Question

Pertanyaan tentang produk dijawab sebagai pertanyaan produk dan **tidak memicu rekomendasi baru**.

```text
CS: Saya tawarkan NusaTech Creator 15 ...
Pelanggan: RAM-nya berapa?
CS: RAM-nya 16 GB DDR5, Kak.
```

## 11.1 Resolusi referensi (dilakukan lebih dulu)

| Ungkapan | Dirujuk ke |
|---|---|
| kode (`KB-L02`, `kb l02`) | produk dengan kode itu, **walau belum pernah ditawarkan** |
| nama lengkap atau varian (`AstraBook 15 Pro`, `astrabook 15`, `creator 15`, `student 14`, `garuda g15`, `kencana workstation`) | produk yang cocok per token, toleran terhadap huruf besar/kecil dan kesalahan ketik kecil |
| "yang pertama / kedua / ketiga", "nomor 2" | urutan di `offered_products` |
| "yang tadi", "yang itu" | `selected_product`; bila kosong dan hanya satu produk ditawarkan, produk itu |
| "yang murah tadi" | harga terendah di `offered_products` |

- Jika nama cocok ke lebih dari satu produk (misalnya hanya "AstraBook"), jawab untuk semua yang cocok (maks. 3) atau sebutkan opsinya.
- Produk yang disebut bernama otomatis menjadi `selected_product`.
- Pertanyaan produk **tanpa** produk yang sedang dibahas dan **tanpa** nama produk → "Belum ada produk yang sedang kita bahas, Kak", disertai tawaran bantuan.

## 11.2 Referensi ambigu

Jika beberapa produk sedang ditawarkan dan pelanggan bertanya tanpa menyebut produk, **jawab untuk semuanya** secara ringkas.

## 11.3 Pertanyaan produk tidak mengubah constraint

Constraint (`processor`, `operating_system`, `budget_*`) hanya diperbarui oleh pernyataan atau permintaan pelanggan, **bukan** oleh pertanyaan produk.

```text
Pelanggan: Prosesornya Intel atau AMD?   → jawaban per produk; processor tetap kosong
Pelanggan: Windows-nya apa?              → jawaban per produk; os tetap kosong
Pelanggan: Yang Intel aja.               → baru boleh processor = intel
```

## 11.4 Leksikon atribut

Atribut dikenali per token (§5A): `ram`/`memori`, `prosesor`/`cpu`/`processor`, `gpu`/`vga`/`kartu grafis`, `storage`/`ssd`/`penyimpanan`, `layar`/`display`/`inci`, `windows`/`os`/`sistem operasi`, `harga`/`berapaan`. "Prosesor apa untuk programming?" menanyakan prosesor, bukan RAM.

Nilai yang tidak berlaku untuk jenis produk (RAM, storage, GPU, OS pada monitor) dijawab "tidak berlaku untuk monitor / tidak tercantum", bukan menampilkan `-`.

---

# 12. Comparison

Perbandingan dijawab dengan:

1. daftar selisih **fakta katalog** (harga, CPU, RAM, storage, GPU, layar, penggunaan yang disarankan);
2. kesimpulan singkat berdasarkan penggunaan yang disarankan dan spesifikasi tertulis.

Tidak boleh ada angka performa, benchmark, FPS, atau klaim "pasti lebih cepat". Boleh menyatakan fakta ("RTX 4060 8 GB memiliki VRAM lebih besar daripada RTX 3050 6 GB"). Jika kedua produk sama-sama tercantum cocok, katakan keduanya cocok dan jelaskan selisih fakta. Produk yang dibandingkan di-resolve lewat §11.1, bukan dari kandidat yang kebetulan ada.

---

# 13. Correction

"Aku tanya laptop, bukan harga" artinya pelanggan memperbaiki **bentuk respons**. Respons berikutnya membahas produk/spesifikasi, tidak mengulang daftar harga.

---

# 14. Uncertainty

"belum tahu", "terserah", "bebas", "nggak tahu" bukan error. Teks dinormalisasi lebih dulu (§5A), sehingga "Terserah." sama dengan "terserah".

| Situasi | Perilaku |
|---|---|
| Kebutuhan jelas, budget belum tahu | Tawarkan produk sesuai kebutuhan. |
| Kategori jelas, kebutuhan belum ada, `need` belum pernah ditanyakan | Tanya satu kali: "[Kategori]nya mau dipakai untuk apa?" (pakai nama kategori yang benar, bukan "Laptopnya" tetap). |
| Kebutuhan belum ada, `need` sudah pernah ditanyakan, pelanggan "terserah" | **Sebaran**: termurah, menengah, tertinggi dalam kategori. Tidak bertanya lagi. |
| Tidak ada clue sama sekali | Tanya satu hal, atau sebaran bila sudah pernah bertanya. |
| "Terserah" berulang setelah sebaran | Jangan menanyakan hal baru; tawarkan merinci salah satu produk. |

Sebaran laptop pada katalog dummy: NusaTech Student 14 (termurah), AstraBook 15 Pro (menengah), Garuda Gaming G15 (tertinggi).

---

# 14A. Cancellation

"batal", "nggak jadi", "tidak jadi", "bye", dan "sudah/udah" yang berdiri sendiri sebagai penutup menghentikan alur dan **mereset seluruh state** (§4). Pesan pembatalan tidak boleh tertangkap oleh jalur small talk tanpa reset. "Sudah" sebagai jawaban atas `last_question` ("Sudah punya monitor?") adalah jawaban, bukan pembatalan.

---

# 15. Katalog sebagai Sumber Fakta (RAG)

RAG/katalog adalah **sumber fakta**. Bukan conversation manager, intent classifier, pengelola state, atau penentu produk bebas.

```text
Conversation State
        ↓
Intent / Decision
        ↓
Structured Catalog Query (filter + rank)
        ↓
Catalog Facts
        ↓
Response
```

## 15.1 Pembagian tugas retrieval

| Kebutuhan | Mekanisme |
|---|---|
| Filter kategori, harga, tag; ranking harga | **Query terstruktur pada payload Qdrant** (atau katalog JSON). Deterministik. Tidak memanggil embedding. |
| Pertanyaan tentang produk tertentu | Ambil record lewat kode/nama (§11.1). |
| Pertanyaan semantik yang tidak terpetakan | Semantic search (bge-m3, cosine), hanya sebagai fallback setelah langkah deterministik gagal. |
| Kebijakan (stok, transaksi, dst.) | Record kebijakan terpisah. |

Embedding **tidak** dipakai untuk menentukan "di bawah 12 juta", "paling murah", atau urutan kecocokan kebutuhan. Urutan penawaran memakai §7.2.

## 15.2 Katalog kecil

Jika hasil filter ≤ ~20 produk, gunakan seluruh record kandidat. Jangan mengandalkan top-k.

---

# 16. Struktur Data Katalog dan Ingestion

## 16.1 Satu produk = satu record

Dibangun dari bagian **Detail Produk** di PDF, bukan dari tabel ringkasan (teks tabel terpotong: GPU "4 G", "12 ").

```json
{
  "kode": "KB-L02",
  "nama": "AstraBook 15 Pro",
  "alias": ["astrabook 15 pro", "astrabook 15", "kb l02"],
  "kategori": "laptop",
  "is_accessory": false,
  "harga_idr": 11999000,
  "cpu": "Intel Core i5-13420H",
  "cpu_vendor": "intel",
  "ram_gb": 16,
  "ram_type": "DDR5",
  "storage": "512 GB NVMe SSD",
  "gpu": "NVIDIA GeForce RTX 2050 4 GB",
  "display": "15,6 inci FHD 144 Hz",
  "os": "Windows 11 Home",
  "includes_monitor": null,
  "usage_text": "Cocok untuk programming, Android Studio, desain ringan, dan gaming menengah.",
  "need_tags": [
    {"tag": "programming"},
    {"tag": "android_studio"},
    {"tag": "design", "qualifier": "ringan"},
    {"tag": "gaming", "qualifier": "menengah"}
  ]
}
```

- `usage_text` selalu disimpan dan menjadi sumber "dasar pemilihan".
- `alias` berisi nama lengkap, varian tanpa suffix, dan kode dalam bentuk ternormalisasi.

## 16.2 Aturan ingestion

1. Field yang tidak ada diisi `null`. Respons untuk `null` selalu "informasi belum tersedia".
2. **Monitor:** "Prosesor: Panel IPS ..." menjadi `panel`, bukan `cpu`. `ram`, `storage`, `gpu`, `os` bernilai `null`.
3. **Desktop:** `includes_monitor = false`.
4. `harga_idr` integer.
5. **`need_tags` diturunkan saat ingestion** dari `usage_text` memakai §22, lalu diperiksa manual sekali. Query-time **tidak boleh** mencocokkan substring pada `usage_text`. Tag tidak boleh ditambahkan jika tidak ada di teks, dan kata umum seperti "development" tidak otomatis menjadi `programming`.
6. `kualifier` menyimpan tingkat yang tertulis ("ringan", "menengah", "berat", "kelas atas", "entry-level"). Kualifier wajib dikutip saat produk ditawarkan.
7. Negasi dicatat: "Kurang cocok untuk gaming berat" pada AstraBook 14 Core adalah `{"tag":"gaming","negated":true}`, bukan tag positif.
8. Record kebijakan dibuat terpisah.
9. Collection `computer_knowledge`, bge-m3 1024 dimensi, cosine. Payload diindeks untuk filter: `kategori`, `harga_idr`, `is_accessory`, `need_tags.tag`, `cpu_vendor`.

---

# 17. Peran LLM (gemma4:e4b)

LLM dipakai untuk:

- **LLM-NLU**: mengubah ucapan yang tidak tertangani langkah 1–11 menjadi JSON dengan **kosakata tertutup** (intent dan tag dari §22);
- menyusun kalimat natural dari fakta yang diberikan, bila template tidak cukup.

LLM **bukan** sumber fakta, bukan pemilih produk.

## 17.1 Keluaran NLU

```json
{
  "intent": "answer_to_last_question | new_need | constraint | product_question | comparison | correction | uncertainty | cancel | purchase_intent | category_availability | small_talk | unknown",
  "needs": ["student"],
  "slots": { "category": null, "budget_max": null, "budget_target": null, "preference": null },
  "references": [],
  "confidence": 0.0
}
```

- `needs` hanya boleh berisi tag dari §22; nilai di luar daftar dibuang.
- Temperature rendah dan output terstruktur (parameter `format` Ollama).
- Bila JSON tidak valid atau `confidence` rendah: ulang sekali, lalu fallback deterministik.

## 17.2 Respons berbasis LLM

LLM hanya boleh menyusun kalimat dari **fakta record produk yang relevan** (produk yang disebut atau ditawarkan). Prompt tidak boleh berisi "(tidak ada produk)" lalu membiarkan LLM menjawab bebas. Jika tidak ada fakta, gunakan template "informasi belum tersedia / belum ada produk yang dibahas" tanpa LLM.

## 17.3 Validator fakta

Sebelum respons dikirim:

1. semua nama produk ada di katalog;
2. semua harga dan angka spesifikasi sama dengan record;
3. tidak ada klaim stok, garansi, baterai, atau pembayaran.

Bila gagal, gunakan template dari record.

---

# 18. Guardrail Fakta

Tidak boleh mengarang:

- harga, RAM, prosesor, GPU, ukuran layar, warna;
- **stok** (jangan menyatakan tersedia atau habis);
- bonus, **garansi**, **baterai**, berat, port;
- **transaksi, pembayaran, pengiriman, cicilan**;
- performa, benchmark, FPS;
- kompatibilitas di luar yang tertulis.

## 18.1 Atribut tidak tersedia ditangani secara deterministik

Leksikon: `stok`, `ready`, `sisa`, `warna`, `baterai`, `berat`, `garansi`, `port`, `hdmi`, `usb`, `bonus`, `cicilan`, `kredit`, `bayar`, `kirim`, `ongkir`. Pertanyaan yang memuat kata ini dijawab "belum tersedia di katalog" **tanpa memanggil LLM**.

| Pertanyaan | Jawaban |
|---|---|
| "Apakah KB-L02 tersedia stoknya?" | "Maaf, Kak, informasi stoknya belum tersedia." |
| "Baterai AstraBook 15 Pro berapa?" | "Maaf, informasi kapasitas baterai belum tersedia di katalog." |
| "Cara bayarnya gimana?" / "Mau beli yang itu" | "Maaf, informasi pembayaran dan pengiriman belum tersedia." Lalu tawarkan ringkasan produk. |

Menawarkan produk **bukan** klaim ketersediaan. Gunakan "bisa dipertimbangkan" / "ada di katalog kami", bukan "ready".

---

# 19. Kategori Produk dan Aksesori

Kategori yang boleh disebut: **Laptop, Desktop, Monitor**.

- Monitor adalah aksesori; tidak ikut kandidat utama kecuali diminta.
- **"komputer" / "pc"** berarti `computer` (laptop dan desktop), bukan desktop.
- Pertanyaan `ada/jual/punya/menjual X` dengan X bukan laptop/desktop/komputer/pc/monitor dijawab: "Maaf, Kak, di katalog kami saat ini hanya ada laptop, desktop, dan monitor." Ini **berlaku untuk semua X** (printer, keyboard, mouse, tablet, HP, router, dst.), bukan daftar hardcoded satu kata. Kata fungsi ("yang", "apa", "lagi", "aja") dikecualikan agar "ada yang murah?" tidak tertangkap. Kasus ambigu diklasifikasikan LLM-NLU (`category_availability`) dengan kosakata tertutup.
- Tidak boleh mengasumsikan toko komputer menjual produk yang tidak ada di katalog.

Pertanyaan ketersediaan kategori yang ada ("Ada laptop?") dijawab berdasarkan keberadaan di katalog, tanpa klaim stok.

---

# 20. Kecepatan Respons

| Level | Gunakan untuk |
|---|---|
| **1 — Deterministik** | normalisasi, salam, terima kasih, perpisahan, pembatalan, jawaban atas pertanyaan terakhir, kebutuhan yang cocok dengan leksikon §22, parsing budget, resolusi referensi, pertanyaan harga/spesifikasi, perbandingan, atribut tidak tersedia, guard kategori, koreksi |
| **2 — Katalog** | query terstruktur dan record produk |
| **3 — LLM** | langkah 12 routing saja |

> **LLM tidak boleh dipanggil hanya karena sistem sebenarnya sudah tahu jawabannya.**

**Jalur Level 1 dan Level 2 tidak boleh memanggil Ollama maupun endpoint embedding.** Ini diuji (§26).

---

# 21. Golden Rule

> **Gunakan informasi yang sudah tersedia untuk membantu pelanggan secepat mungkin. Jangan meminta informasi tambahan apabila belum diperlukan untuk memberikan bantuan atau penawaran yang berguna.**

> **Pelanggan tidak harus menyelesaikan requirement terlebih dahulu untuk mendapatkan rekomendasi.**

---

# 22. Peta Kebutuhan → Katalog

Kontrak antara bahasa pelanggan dan tag katalog. Pencocokan **per token atau frasa utuh** (§5A). Kolom "Produk" diturunkan dari "Penggunaan yang disarankan" dan diperiksa saat ingestion.

| Tag | Kata pelanggan (leksikon) | Produk (tag utama) |
|---|---|---|
| `office` | kerja, kerjaan, pekerjaan, kantor, kantoran, office, ngetik, mengetik, dokumen, word, excel, administrasi, admin | KB-L01, KB-L04, KB-D01, (aksesori: KB-M01) |
| `admin_kasir` | kasir | KB-D01 |
| `student` | kuliah, perkuliahan, kampus, mahasiswa, skripsi, tugas kuliah, sekolah, siswa | KB-L01, KB-L04 |
| `programming` | programming, programmer, pemrograman, coding, ngoding, koding, flutter | KB-L01, KB-L02, KB-L03 (berat), KB-L04 (web), KB-D02, (aksesori: KB-M01, KB-M02) |
| `web_dev` | web development, web programming, bikin web, buat website, website | KB-L01, KB-L04 |
| `android_studio` | android studio, android | KB-L02, KB-L03 |
| `docker` | docker | KB-L03 |
| `vm` | virtual machine, vm | KB-D02 |
| `data_processing` | data processing, olah data | KB-D02 |
| `design` | desain, design, desainer, desain grafis | KB-L02 (**ringan**), (aksesori: KB-M02) |
| `video_editing` | editing video, edit video, video editing, editing, edit | KB-L03, KB-L05, KB-D02, KB-D03 (berat), (aksesori: KB-M02) |
| `rendering_3d` | rendering, render, 3d | KB-L05, KB-D03 |
| `ai_dev` | ai development, pengembangan ai, buat ai, ngembangin ai | KB-L05 (entry-level), KB-D03 |
| `gaming` | gaming, game, main game, gamer | KB-L02 (**menengah**), KB-L03, KB-L05 (berat), KB-D03 (kelas atas), (aksesori: KB-M02) |
| `daily` | penggunaan harian, harian, sehari-hari | KB-L04, KB-M01 |

**Aturan penting:**

- Urutan kata tidak penting: "editing video" dan "video editing" sama.
- Pernyataan identitas ("saya mahasiswa") menambahkan `student`.
- "sekolah/siswa" dipetakan ke `student` dengan penjelasan jujur bahwa katalog menyebut kecocokan untuk perkuliahan.
- Kata "development" tanpa pasangan ("web", "android", "ai") **tidak** memetakan ke tag mana pun. KB-L05 hanya `ai_dev`, bukan `programming`.
- Pemakaian layanan AI (ChatGPT, "tanya ke AI") bukan kebutuhan perangkat yang tercantum di katalog. Jangan mengarang kecocokan; tawarkan sebaran dan jelaskan bahwa katalog tidak menyebut kebutuhan itu.
- **Tag terkait (§7.3):** `design` → `video_editing`, `rendering_3d`. Ditawarkan hanya dengan label jujur.
- Kualifier ("ringan", "menengah", "berat", "kelas atas", "entry-level") dikutip apa adanya.

---

# 23. Acceptance Test

"Kategori laptop" berarti `category=laptop` sudah ada di state. Semua tes dijalankan **otomatis** (§26).

## A — Jawaban terhadap pertanyaan terakhir

```text
Pelanggan: Jual laptop ya?
CS: Laptopnya mau dipakai untuk apa, Kak?
Pelanggan: Untuk kerja.
```

Hasil: OFFER **NusaTech Student 14** dan **AstraBook 14 Core** (tag `office`), dengan dasar pemilihan. Tidak bertanya kebutuhan lagi, tidak bertanya budget.

## B — Budget belum diketahui

```text
Pelanggan: Butuh laptop.
Pelanggan: Untuk desain.
Pelanggan: Belum tahu budget.
```

Hasil: OFFER **AstraBook 15 Pro** ("desain ringan"). Creator 15 boleh disebut hanya sebagai tag terkait dengan label jujur.

## C — Budget setelah offer

```text
Pelanggan: Butuh laptop.
Pelanggan: Untuk desain.
Pelanggan: Yang di bawah 12 juta.
```

Hasil: FILTER → **AstraBook 15 Pro** (Rp11.999.000 < Rp12.000.000).

## D — Pelanggan menyerahkan pilihan

```text
Pelanggan: Untuk desain.
Pelanggan: Terserah.
```

Hasil: OFFER AstraBook 15 Pro. Tidak bertanya. Berlaku juga untuk "Terserah." dengan titik.

## E — Kebutuhan berubah

```text
Pelanggan: Untuk kantor.
Pelanggan: Eh, buat programmer.
```

Hasil: `needs = [programming]`. Kandidat laptop: NusaTech Student 14, AstraBook 14 Core, AstraBook 15 Pro, NusaTech Creator 15. **Garuda Gaming G15 tidak boleh muncul.** Tawarkan 3 sesuai §7.2 (Student 14, 14 Core, 15 Pro) dan sebutkan masih ada pilihan lain.

## F — Pertanyaan spesifikasi

```text
CS: Saya tawarkan NusaTech Creator 15 ...
Pelanggan: RAM-nya berapa?
```

Hasil: "RAM-nya 16 GB DDR5, Kak." Varian "ramnya", "RAM nya", "ram-nya", "RAM-nya berapa?" semua sama.

## G — Koreksi

```text
Pelanggan: Aku tanya laptop, bukan harga.
```

Hasil: respons berikutnya membahas laptop/spesifikasi, bukan daftar harga.

## H — Ranking harga

```text
Pelanggan: Untuk desain.
Pelanggan: Yang paling murah.
```

Hasil: kandidat komputer utama `design` hanya AstraBook 15 Pro. Jawab bahwa itu satu-satunya. **Merapi Monitor Pro 27 tidak boleh muncul.**

## I — Hasil kosong

```text
Pelanggan: Laptop di bawah 5 juta.
```

Hasil: nyatakan tidak ada, sebutkan NusaTech Student 14 (Rp7.999.000), tawarkan relaksasi (§8.4).

## J — Stok

"Apakah KB-L02 tersedia stoknya?" → "informasi stok belum tersedia". Tanpa LLM.

## K — Atribut tidak ada

"Berapa kapasitas baterai AstraBook 15 Pro?" → "informasi kapasitas baterai belum tersedia". Tanpa LLM.

## L — Kategori tidak ada

"Ada printer?" dan "Ada keyboard?" → katalog hanya laptop, desktop, monitor.

## M — Perbandingan

"Bedanya AstraBook 15 Pro dan NusaTech Creator 15 apa?" → selisih fakta: harga Rp11.999.000 vs Rp13.499.000; Intel Core i5-13420H vs AMD Ryzen 7 7840HS; storage 512 GB vs 1 TB; RTX 2050 4 GB vs RTX 3050 6 GB; penggunaan yang disarankan masing-masing. Tanpa angka performa. Produk di-resolve dari nama, tanpa kandidat sebelumnya.

## N — Desktop

"Butuh desktop untuk programming." → OFFER **Kencana Workstation** dengan catatan monitor tidak termasuk. Tanpa klaim port.

## O — "RAM gede" saat semua sama

"Laptop yang RAM-nya gede." → semua laptop 16 GB; jelaskan sama dan sebutkan perbedaan lain (DDR4 vs DDR5). Tanpa ranking paksaan.

## P — "Prosesor gede"

"Yang prosesornya gede." → katalog tidak memuat tingkat performa prosesor; tidak diranking; sebutkan tipe prosesor.

## Q — Referensi ordinal

```text
CS: (menawarkan NusaTech Student 14, AstraBook 14 Core, AstraBook 15 Pro)
Pelanggan: Yang kedua RAM-nya berapa?
```

Hasil: AstraBook 14 Core: 16 GB DDR4. Tanpa referensi ("RAM-nya berapa?") → jawab untuk ketiganya.

## R — Kategori belum ada, kebutuhan jelas

"Untuk desain." → OFFER AstraBook 15 Pro. Tidak bertanya kategori; tidak menawarkan monitor.

## S — Niat beli

"Oke, mau beli yang itu." → informasi transaksi/pembayaran/pengiriman belum tersedia; tawarkan ringkasan produk.

## T — Budget target

"Laptop sekitar 10 juta." → tawarkan laptop dengan selisih harga terkecil terhadap Rp10 juta: AstraBook 14 Core (Rp9.499.000), AstraBook 15 Pro (Rp11.999.000), dan NusaTech Student 14 (Rp7.999.000) sebagai ketiga, dengan dasar pemilihan. `budget_target` terbukti memengaruhi hasil.

## U — Variasi bahasa kerja

"buat kerja", "kerjaan kantor", "ngetik dokumen", "pekerjaan administrasi" (kategori laptop) → semuanya `office`. Tidak ada pertanyaan ulang.

## V — Mahasiswa sebagai clue

"Saya mahasiswa, cari laptop." → `student`. OFFER NusaTech Student 14 dan AstraBook 14 Core.

## W — Urutan kata

"Laptop buat editing video." dan "laptop untuk video editing" → `video_editing`. Kandidat laptop: NusaTech Creator 15, Garuda Gaming G15.

## X — Normalisasi tanpa LLM

"Halo, Kak!", "Terima kasih.", "Makasih!", "Bye." → ditangani Level 1. **Nol panggilan LLM/embedding.**

## Y — Atribut dengan kata pembawa

"Prosesor apa untuk programming?" → atribut `prosesor`, bukan `ram`. "Ada laptop dengan program coding?" tidak memicu atribut RAM.

## Z — Referensi sebelum atribut

```text
CS: (menawarkan NusaTech Student 14, AstraBook 14 Core, AstraBook 15 Pro)
Pelanggan: Yang kedua harganya berapa?
```

Hasil: "Harga AstraBook 14 Core Rp9.499.000, Kak." Bukan daftar harga ketiganya.

## AA — Nama produk tanpa kandidat

"Berapa harga AstraBook 15 Pro dan berapa RAM-nya?" tanpa penawaran sebelumnya → Rp11.999.000 dan 16 GB DDR5. "Apakah AstraBook 14 Core punya GPU NVIDIA?" → tidak; GPU-nya Intel Iris Xe.

## AB — Gaming dengan budget

"Laptop gaming di bawah 12 juta." → AstraBook 15 Pro dengan kualifier "gaming menengah". Bukan "belum ada".

## AC — Kata "development"

"Laptop buat development." (tanpa pasangan) tidak dipetakan ke `programming`; sistem menanyakan jenis development atau menawarkan sebaran. Garuda Gaming G15 tidak muncul untuk `programming`.

## AD — Terserah berulang

```text
Pelanggan: Butuh laptop.
CS: Laptopnya mau dipakai untuk apa, Kak?
Pelanggan: Terserah.
Pelanggan: Terserah.
```

Hasil: setelah "Terserah." pertama, tawarkan **sebaran** (Student 14, AstraBook 15 Pro, Garuda G15). Tanya "untuk apa?" **tidak diulang**. "Terserah." berikutnya tidak memunculkan pertanyaan baru.

## AE — Preferensi dibersihkan saat kebutuhan berganti

```text
Pelanggan: Laptop untuk desain, yang paling murah.
Pelanggan: Sekarang untuk gaming.
```

Hasil: `cheapest` dibersihkan. OFFER laptop `gaming` (AstraBook 15 Pro, NusaTech Creator 15, Garuda Gaming G15 urut harga), bukan satu produk.

## AF — Pertanyaan produk tidak mengunci filter

```text
CS: (menawarkan beberapa laptop)
Pelanggan: Prosesornya Intel atau AMD?
Pelanggan: Ada yang lain?
```

Hasil: jawaban per produk. `processor` tetap kosong; "ada yang lain?" tidak terfilter Intel/AMD.

## AG — "Komputer"

"Komputer untuk kantor." → kandidat `computer` (laptop + desktop): Kencana Office Mini, NusaTech Student 14, AstraBook 14 Core. Monitor tidak ikut.

## AH — Pembatalan mereset state

```text
Pelanggan: Laptop untuk desain.
Pelanggan: Nggak jadi.
Pelanggan: RAM-nya berapa?
```

Hasil: setelah "Nggak jadi.", state kosong. Pertanyaan RAM dijawab "belum ada produk yang sedang kita bahas".

## AI — Paling murah tanpa kebutuhan

"Laptop yang paling murah." → NusaTech Student 14 langsung, tanpa menanyakan kebutuhan. "Yang paling murah aja." tanpa kategori → termurah per kategori utama (Student 14 dan Kencana Office Mini).

## AJ — Jawaban kebutuhan yang tidak dikenali

```text
CS: Laptopnya mau dipakai untuk apa, Kak?
Pelanggan: Buat ngerjain skripsi.
```

- NLU (stub) mengembalikan `student` → OFFER Student 14 dan 14 Core.
- NLU (stub) mengembalikan `none` → tawarkan sebaran; pertanyaan tidak diulang.

## AK — Nol jaringan di Level 1

Tes A–I, N–R, T–AI dijalankan dengan klien Ollama/embedding yang melempar error bila dipanggil. Semua harus lulus.

## AL — Kata `-nya` dan nama

"Harganya AstraBook 15 Pro?", "harga astrabook 15", "harga kb-l02" → semuanya resolve ke AstraBook 15 Pro.

## AM — Atribut monitor

"Merapi Monitor 24 RAM-nya berapa?" → "RAM tidak berlaku untuk monitor". Bukan "RAM: -".

## Tabel keterlacakan

| Temuan di `chatbot.py` | Tes |
|---|---|
| "kerja" tidak dikenali | A, U |
| "mahasiswa/kuliah" bukan kebutuhan | V |
| "ram-nya" gagal | F |
| "Terserah." / "Halo, Kak!" gagal | D, X |
| design→editing melebar | B, D, H, R |
| monitor menjadi hasil desain termurah | H |
| gaming hanya L05 | AB |
| "development" cocok ke L05 | E, AC |
| `budget_target` tidak dipakai | T |
| "ram" cocok "programming" | Y |
| ordinal diproses setelah atribut | Q, Z |
| nama produk tidak di-resolve | AA, AL, M |
| stok/baterai/garansi ke LLM | J, K, S |
| guard hanya "printer" | L |
| "komputer" → desktop | AG |
| preferensi menempel | AE |
| pertanyaan produk mengunci filter | AF |
| "terserah" berulang | AD |
| `last_question` tidak dibaca | AJ |
| "nggak jadi" tidak mereset | AH |
| "paling murah" memaksa tanya kebutuhan | AI |
| "editing video" urutan kata | W |
| nilai `-` pada monitor | AM |

---

# 24. Kriteria Keberhasilan Implementasi

Sistem berhasil jika:

1. **Cepat menawarkan produk** ketika clue cukup.
2. Tidak menjadikan budget sebagai syarat.
3. Tidak terus meminta requirement; bertanya maksimal sekali per slot.
4. Memahami jawaban atas pertanyaan terakhir, termasuk yang tidak ada di leksikon.
5. Mempertahankan state (termasuk urutan `offered_products`, `asked_slots`, multi-need) dan membersihkan preferensi saat kebutuhan berganti.
6. Memprioritaskan informasi terbaru dan koreksi.
7. Memisahkan OFFER, FILTER, RANK.
8. Menjawab pertanyaan produk dan perbandingan langsung, dengan referensi di-resolve lebih dulu.
9. Memakai katalog sebagai sumber fakta; filter/rank terstruktur tanpa embedding.
10. Tidak membiarkan LLM mengarang fakta; semua respons lolos validator fakta.
11. Tidak menawarkan kategori yang tidak ada dalam katalog (berlaku generik).
12. Memakai LLM hanya ketika Level 1 dan 2 gagal; jalur Level 1/2 tanpa panggilan jaringan.
13. Tetap membantu walaupun budget belum diketahui.
14. Menyatakan hasil kosong dan informasi tidak tersedia dengan jujur dan tanpa LLM.
15. Mengutamakan pengalaman customer service di atas kelengkapan requirement.
16. Seluruh acceptance test A–AM lulus otomatis tanpa Ollama dan Qdrant.

---

# 25. Prinsip Implementasi

Implementasi **tidak boleh dilakukan dengan tambal-sulam terhadap bug satu per satu**. Struktur program mengikuti spesifikasi sejak awal.

```text
SPECIFICATION
     ↓
CATALOG INGESTION (record terstruktur, tag + kualifier, alias, §16)
     ↓
NORMALIZATION (§5A)
     ↓
CONVERSATION STATE
     ↓
ROUTING / INTENT (§5B: deterministik dulu, LLM-NLU tertutup jika perlu)
     ↓
DECISION (ASK / OFFER / FILTER / RANK / ANSWER / COMPARE / DECLINE)
     ↓
CATALOG RETRIEVAL (query terstruktur, semantic hanya fallback)
     ↓
RECOMMENDATION
     ↓
RESPONSE GENERATION (template atau LLM + validator fakta)
```

---

# 26. Testabilitas dan Struktur Kode

## 26.1 Fungsi inti murni

```text
step(state, user_text, catalog, nlu) -> (new_state, reply, route)
```

- Tidak ada variabel `state` global.
- Tidak ada I/O (input, print, jaringan) saat modul di-import.
- `catalog` berupa objek (daftar record §16) yang dimuat dari JSON atau dari Qdrant oleh modul terpisah.
- `nlu` adalah fungsi yang disuntikkan. Di tes diganti stub; di produksi memanggil Ollama.
- `route` mencatat jalur keputusan (misalnya `DIRECT`, `OFFER`, `ATTR`, `NLU`) untuk pengujian dan debugging.

## 26.2 Modul

| Modul | Tanggung jawab |
|---|---|
| `ingest` | PDF/teks → record terstruktur → JSON/Qdrant |
| `normalize` | §5A |
| `lexicon` | §22, atribut §11.4, unavailable §18.1 |
| `state` | struktur state, reset parsial dan penuh |
| `router` | §5B |
| `catalog` | filter, ranking, resolusi nama (§11.1) |
| `respond` | template, validator fakta |
| `nlu_ollama`, `retrieval_qdrant` | adaptor I/O, hanya dipanggil oleh langkah 12 atau fallback |
| `cli` | REPL; satu-satunya tempat `input()`/`print()` |

## 26.3 Aturan pengujian

- Acceptance test A–AM adalah tes otomatis yang memakai `catalog` JSON dummy dan `nlu` stub.
- Tes AK memasang klien jaringan yang melempar exception; jalur Level 1/2 tidak boleh memicunya.
- Setiap tes menegaskan **route** dan **isi respons** (produk, harga, kutipan "dasar pemilihan"), bukan hanya "tidak crash".
- Regresi: bug baru yang ditemukan di percakapan nyata harus ditambahkan sebagai tes baru, bukan diperbaiki dengan penambalan regex.

**Spesifikasi ini menjadi kontrak sebelum implementasi dimulai.**
