<!--
PETUNJUK INGESTION (bagian ini JANGAN di-embed)
- Pecah dokumen per heading "## ". Satu blok = satu chunk = satu titik di Qdrant.
- Simpan ID di heading (P01, G02, M01, dst.) sebagai payload "id"; "Tag katalog" dan "Perangkat" juga bisa dijadikan payload untuk filter.
- Dokumen ini TIDAK memuat harga, stok, atau nama produk. Semua itu hanya boleh berasal dari katalog (SQLite).
- Baris "Filter minimum" memakai nama kolom tabel products (ram_gb, ram_type) dan kolom turunan hasil migrate_derived_fields.py (cpu_tier, storage_ssd_gb, gpu_dedicated, gpu_class, vram_gb, screen_inch, refresh_hz, panel, srgb_pct, tags). Filter hanya batas bawah; nilai NULL (mis. vram_gb yang tidak tertulis) harus diperlakukan sebagai "tidak diketahui", bukan lolos atau gagal otomatis.
- Tag selain office, daily, gaming, rendering_3d adalah usulan tag baru; isi lewat raw_data["tags"] atau kolom tags.
-->

# Basis Pengetahuan Bobby Computer: Kebutuhan vs Spesifikasi Komputer (v2.0)

Dokumen ini berisi pedoman umum untuk mencocokkan kebutuhan pelanggan dengan spesifikasi komputer. Isinya adalah panduan kebutuhan, bukan daftar produk. Produk yang direkomendasikan harus selalu diambil dari katalog toko.

---

## G01 — Panduan Umum: Tingkatan Prosesor (CPU)

- **ID:** G01 | **Tipe:** panduan umum
- **Kata kunci pelanggan:** prosesor, CPU, i3 i5 i7, Ryzen, Core Ultra, kuat atau tidak, bedanya apa
- **Tingkatan (cpu_tier) agar berbagai merek bisa dibandingkan:**
  - Tier 1 (dasar): Intel Celeron/Pentium, Intel N-series (N100, N150, N305), Core i3, AMD Ryzen 3, AMD Athlon.
  - Tier 2 (menengah): Intel Core i5, Core Ultra 5, AMD Ryzen 5.
  - Tier 3 (tinggi): Intel Core i7, Core Ultra 7, AMD Ryzen 7.
  - Tier 4 (sangat tinggi): Intel Core i9, Core Ultra 9, AMD Ryzen 9.
  - Apple M-series (M1 dan seterusnya) berada di kelas Tier 2 sampai Tier 4 tergantung varian (M, Pro, Max), hanya untuk perangkat Mac.
- **Akhiran laptop:** U atau P berarti hemat daya (cocok kantor dan baterai awet); H, HS, HX berarti performa tinggi (cocok gaming, kreatif, dan teknik, tetapi lebih boros baterai dan lebih panas).
- **Catatan:** Generasi berpengaruh. Prosesor tier lebih tinggi dari generasi sangat lama bisa setara atau lebih lemah daripada tier lebih rendah dari generasi baru. Jika ragu, utamakan generasi yang lebih baru.

---

## G02 — Panduan Umum: Kartu Grafis (GPU) dan VRAM

- **ID:** G02 | **Tipe:** panduan umum
- **Kata kunci pelanggan:** kartu grafis, VGA, GPU, RTX, Nvidia, AMD Radeon, VRAM, integrated, dedicated, onboard
- **Kelas GPU:**
  - Integrated (iGPU, memakai RAM bersama): Intel UHD, Intel Iris Xe, Intel Arc Graphics (pada Core Ultra), AMD Radeon Graphics. Cukup untuk kantor, browsing, video, dan edit ringan. Varian AMD Radeon yang lebih baru cukup kuat untuk game ringan pada pengaturan rendah.
  - Dedicated entry: Nvidia MX series, GTX 1650, RTX 2050, RTX 3050, RTX 4050, RTX 5050, AMD Radeon RX 6500M.
  - Dedicated menengah: RTX 3060, RTX 4060, RTX 5060, AMD Radeon RX 7600M.
  - Dedicated tinggi: RTX 4070/5070 ke atas.
- **VRAM:** memori khusus GPU. Penting untuk game resolusi tinggi, render 3D, edit video 4K, dan AI lokal.
- **Peringatan penting (laptop vs desktop):** Nama GPU yang sama bisa punya VRAM berbeda. Contoh: RTX 3060 desktop memiliki 12GB, sedangkan RTX 3060 laptop memiliki 6GB; RTX 3050 laptop umumnya 4GB sampai 6GB. Jangan menebak VRAM dari nama GPU; gunakan angka VRAM yang tertulis di katalog.
- **Aturan:** Jangan menawarkan GPU dedicated pada kebutuhan yang tidak memerlukannya (kantor, musik, trading, penggunaan sederhana). Itu menaikkan harga, bobot, dan konsumsi baterai tanpa manfaat.

---

## G03 — Panduan Umum: RAM, Penyimpanan, Laptop vs Desktop

- **ID:** G03 | **Tipe:** panduan umum
- **Kata kunci pelanggan:** RAM, memori, SSD, harddisk, HDD, NVMe, laptop atau PC, desktop, upgrade, bisa ditambah
- **RAM:** 8GB adalah batas minimal yang nyaman untuk Windows 11; 16GB adalah standar yang aman untuk multitasking dan kerja kreatif; 32GB atau lebih untuk video 4K, 3D, virtualisasi, dan AI. Banyak laptop tipis memiliki RAM yang disolder dan tidak bisa ditambah, jadi pilih kapasitas yang cukup sejak awal.
- **Penyimpanan:** Gunakan SSD (lebih disarankan NVMe) sebagai penyimpanan utama. Hindari HDD dan eMMC untuk drive utama karena lambat. Kapasitas 256GB cukup untuk kebutuhan dasar; 512GB standar; 1TB atau lebih untuk video, game, dan proyek besar.
- **Laptop vs desktop:** Laptop unggul pada portabilitas dan baterai. Desktop unggul pada performa per rupiah, pendinginan, kemudahan upgrade, dan jumlah monitor. Untuk pekerjaan berat yang tidak perlu dibawa-bawa (render, game AAA, trading multi-monitor), desktop sering lebih tepat.

---

## G04 — Panduan Umum: Jika Kebutuhan Pelanggan Belum Jelas atau Campuran

- **ID:** G04 | **Tipe:** panduan umum
- **Kata kunci pelanggan:** bingung, belum tahu, rekomendasi dong, laptop apa yang bagus, tolong pilihkan
- **Pertanyaan klarifikasi (ajukan satu per satu, jangan sekaligus):**
  1. Untuk apa komputer ini dipakai, dan aplikasi atau game apa yang paling sering dipakai?
  2. Berapa kisaran budget?
  3. Perlu laptop (dibawa-bawa) atau desktop?
- **Aturan kebutuhan campuran:** Jika pelanggan menyebut beberapa kebutuhan, gunakan spesifikasi dari profil yang paling berat sebagai acuan. Jika kebutuhannya kerja kantor ditambah game sesekali, lihat P16.
- **Aturan jawaban:** Jelaskan alasan rekomendasi secara singkat, lalu cocokkan dengan produk di katalog. Jika tidak ada produk yang memenuhi spesifikasi minimum pada budget pelanggan, katakan dengan jujur dan tawarkan opsi terdekat atau naikkan budget, tanpa mengarang produk.

---

## P01 — Pekerjaan Kantoran, Administrasi, dan Pelajar (Penggunaan Dasar)

- **ID:** P01 | **Tag katalog:** office, daily | **Perangkat:** laptop (utama), desktop
- **Kata kunci pelanggan:** kerja kantoran, admin, kuliah, sekolah, tugas, skripsi, Word, Excel, Zoom, Google Meet, YouTube, laptop murah, laptop biasa, laptop mahasiswa
- **Kebutuhan/Aktivitas:** Mengetik (Microsoft Word, Excel dasar), browsing internet (Chrome dengan beberapa tab), memutar video/YouTube, meeting online (Zoom/Meet), dan tugas sekolah/kuliah.
- **Karakteristik yang dicari:** Harga terjangkau, baterai awet (jika laptop), ringan dan portabel.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Intel N-series (mis. N100), Core i3, atau Ryzen 3 | Core i5 atau Ryzen 5 (lebih lancar dan awet bertahun-tahun) |
| RAM | 8GB | 16GB |
| Penyimpanan | SSD 256GB NVMe | SSD 512GB |
| GPU | Integrated | Integrated |
| Layar | 14 inci FHD (1920x1080) | 14 sampai 15,6 inci IPS FHD |

- **Filter minimum:** ram_gb ≥ 8; storage_ssd_gb ≥ 256; cpu_tier ≥ 1; gpu_dedicated tidak disyaratkan.
- **Catatan:** Windows 11 secara resmi dapat berjalan di RAM 4GB, tetapi 8GB adalah batas yang nyaman. Hindari HDD dan eMMC. Jangan menawarkan laptop gaming untuk profil ini (berat, baterai cepat habis, mahal). Untuk mahasiswa jurusan teknik, informatika, atau desain, lihat P06, P07, atau P02.

---

## P02 — Desain Grafis 2D dan Fotografer (Creative Beginner)

- **ID:** P02 | **Tag katalog:** design | **Perangkat:** laptop, desktop
- **Kata kunci pelanggan:** desain grafis, edit foto, fotografer, Photoshop, Lightroom, Illustrator, CorelDraw, desain logo, desain kemasan, percetakan, warna akurat
- **Kebutuhan/Aktivitas:** Mengedit foto (Adobe Photoshop, Lightroom), membuat desain vektor (Adobe Illustrator, CorelDraw), dan multitasking sedang.
- **Karakteristik yang dicari:** Akurasi warna layar tinggi, memori lega untuk membuka banyak layer gambar.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 | Core i7 atau Ryzen 7 |
| RAM | 16GB | 32GB (file RAW besar dan PSD berlapis banyak) |
| Penyimpanan | SSD 512GB NVMe | SSD 1TB |
| GPU | Integrated kelas atas atau dedicated entry (RTX 2050/3050/4050) | Dedicated entry |
| Layar | IPS, akurasi warna ≥ 100% sRGB | IPS ≥ 100% sRGB; untuk cetak profesional DCI-P3 atau Adobe RGB tinggi |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2; panel = IPS; srgb_pct ≥ 100.
- **Catatan:** Prioritas pembelian: layar akurat, lalu RAM, baru GPU. Panel murah (TN, atau sRGB di bawah 100%) tidak cocok untuk kerja warna. Untuk cetak, kalibrasi layar menggunakan alat kalibrasi sangat membantu.

---

## P03 — Video Editor 4K, 3D Animator, dan Game Developer (Creative Pro)

- **ID:** P03 | **Tag katalog:** rendering_3d, video_editing | **Perangkat:** desktop (ideal), laptop performa tinggi
- **Kata kunci pelanggan:** edit video 4K, Premiere Pro, DaVinci Resolve, After Effects, Blender, Maya, 3ds Max, render, animasi 3D, motion graphic, color grading, Unity, Unreal Engine
- **Kebutuhan/Aktivitas:** Mengedit video resolusi tinggi, rendering animasi 3D, color grading, motion graphic, dan pengembangan game 3D.
- **Karakteristik yang dicari:** Performa komputasi tinggi, GPU dedicated untuk mempercepat render, penyimpanan sangat cepat.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i7 atau Ryzen 7 (laptop seri H) | Core i9/Ryzen 9 (laptop seri HX) |
| RAM | 32GB | 64GB |
| Penyimpanan | SSD 1TB NVMe Gen 4 | SSD 1 sampai 2TB, ditambah penyimpanan eksternal untuk arsip |
| GPU | RTX 4060 atau setara, VRAM ≥ 8GB | RTX 4070 atau lebih tinggi, VRAM ≥ 12GB untuk scene 3D besar |
| Layar | 2K atau 4K, DCI-P3 ≥ 95% | 4K, DCI-P3 100% |

- **Filter minimum:** ram_gb ≥ 32; storage_ssd_gb ≥ 1000; cpu_tier ≥ 3; gpu_dedicated = 1; vram_gb ≥ 8.
- **Catatan:** Render lama menghasilkan panas tinggi. Laptop tipis cenderung mengalami thermal throttling (performa turun); pilih sistem pendingin yang baik atau pertimbangkan desktop. Blender dan banyak aplikasi render sangat memanfaatkan GPU Nvidia. Untuk edit video 1080p ringan dan konten media sosial, lihat P12.

---

## P04 — Gamer Kasual dan E-Sports

- **ID:** P04 | **Tag katalog:** gaming | **Perangkat:** laptop gaming, desktop
- **Kata kunci pelanggan:** main game, Valorant, Dota 2, CS2, CS:GO, Mobile Legends, Free Fire, PUBG, Genshin Impact, Fortnite, EA FC, laptop gaming murah, FPS tinggi
- **Kebutuhan/Aktivitas:** Bermain game kompetitif dan game populer dengan beban menengah (Valorant, Dota 2, CS2, Genshin Impact).
- **Karakteristik yang dicari:** Frame rate (FPS) tinggi, layar responsif, harga bersahabat.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 (laptop seri H) | Core i5/i7 seri H atau Ryzen 5/7 seri H |
| RAM | 16GB (dual channel, yaitu 2 keping) | 16GB DDR5 dual channel |
| Penyimpanan | SSD 512GB NVMe | SSD 1TB |
| GPU | RTX 2050, RTX 3050, atau Radeon RX 6500M (VRAM ≥ 4GB) | RTX 3050 6GB, RTX 4050, atau RTX 4060 |
| Layar | FHD, refresh rate 120Hz atau 144Hz | FHD IPS 144Hz |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2; gpu_dedicated = 1 (disarankan); vram_gb ≥ 4.
- **Catatan:** Mobile Legends dan Free Fire adalah game Android; di komputer hanya bisa dimainkan lewat emulator (butuh RAM 16GB). Valorant, CS2, dan Dota 2 relatif ringan sehingga iGPU kuat bisa menjalankannya pada pengaturan rendah, tetapi GPU dedicated memberi FPS jauh lebih tinggi. Genshin Impact lebih berat daripada Valorant. Untuk game berat (AAA), lihat P05.

---

## P05 — Gamer Hardcore (Game AAA)

- **ID:** P05 | **Tag katalog:** gaming | **Perangkat:** desktop (ideal), laptop gaming kelas atas
- **Kata kunci pelanggan:** game berat, AAA, Cyberpunk 2077, Red Dead Redemption 2, Black Myth Wukong, Elden Ring, ray tracing, ultra setting, 2K, 4K gaming
- **Kebutuhan/Aktivitas:** Bermain game berat dengan grafis tinggi.
- **Karakteristik yang dicari:** Ray tracing, frame rate mulus di resolusi tinggi, sistem pendingin yang baik.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i7 atau Ryzen 7 | Core i7/i9 seri HX atau Ryzen 7/9 |
| RAM | 16GB | 32GB DDR5 |
| Penyimpanan | SSD 1TB NVMe Gen 4 | SSD 1 sampai 2TB |
| GPU | RTX 4060 atau setara, VRAM ≥ 8GB | RTX 4070/5070 atau lebih tinggi |
| Layar | QHD (2K), 144Hz | QHD 165Hz atau lebih |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 1000; cpu_tier ≥ 3; gpu_dedicated = 1; vram_gb ≥ 8.
- **Catatan:** GPU adalah komponen terpenting. Teknologi seperti DLSS membantu FPS tetapi bukan pengganti GPU yang kuat. Perhatikan sistem pendingin dan daya adaptor laptop. Desktop lebih unggul dalam pendinginan dan kemudahan upgrade.

---

## P06 — Programmer dan Software Developer

- **ID:** P06 | **Tag katalog:** programming | **Perangkat:** laptop, desktop
- **Kata kunci pelanggan:** coding, ngoding, programmer, developer, Docker, VM, VirtualBox, VMware, Android Studio, emulator Android, Flutter, VS Code, web developer, backend, mahasiswa informatika
- **Kebutuhan/Aktivitas:** Coding, kompilasi software, Docker/container, mesin virtual (VM), emulator Android, dan banyak aplikasi terbuka bersamaan (IDE, browser, database).
- **Karakteristik yang dicari:** Multitasking lancar, RAM lega, prosesor dengan banyak core.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 | Core i7 atau Ryzen 7 (core lebih banyak mempercepat kompilasi) |
| RAM | 16GB | 32GB (Docker, VM, dan emulator memakan RAM besar) |
| Penyimpanan | SSD 512GB NVMe | SSD 1TB |
| GPU | Integrated | Integrated (dedicated hanya jika perlu AI lokal, lihat P13) |
| Layar | FHD | FHD atau QHD, keyboard nyaman |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2; gpu_dedicated tidak disyaratkan.
- **Catatan:** Pemrograman umum (web, backend, aplikasi mobile) tidak memerlukan GPU dedicated. Pengembangan aplikasi iOS memerlukan Mac (Xcode hanya tersedia di macOS). Untuk eksperimen AI atau model bahasa lokal, GPU Nvidia dengan VRAM besar diperlukan; lihat P13.

---

## P07 — Arsitek dan Mahasiswa Teknik (CAD, SketchUp, Revit)

- **ID:** P07 | **Tag katalog:** cad, rendering_3d | **Perangkat:** laptop seri H, desktop
- **Kata kunci pelanggan:** arsitek, mahasiswa arsitektur, teknik sipil, teknik mesin, AutoCAD, SketchUp, Revit, ArchiCAD, SolidWorks, Lumion, Enscape, D5 Render, gambar teknik, desain 3D
- **Kebutuhan/Aktivitas:** Pemodelan 3D teknik, drafting 2D, dan rendering arsitektur (Lumion, Enscape, D5 Render).
- **Karakteristik yang dicari:** Performa single-core tinggi, RAM besar, GPU dengan VRAM memadai.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 seri H | Core i7 atau Ryzen 7 seri H (clock tinggi) |
| RAM | 16GB | 32GB |
| Penyimpanan | SSD 512GB NVMe | SSD 1TB |
| GPU | RTX 3050 atau RTX 4050 (untuk CAD dan SketchUp) | RTX 3060/4060 dengan VRAM ≥ 8GB (untuk render real-time seperti Lumion dan D5) |
| Layar | FHD, 100% sRGB | 2K, 100% sRGB |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2; gpu_dedicated = 1; vram_gb ≥ 4.
- **Catatan:** AutoCAD 2D dan SketchUp dasar tidak terlalu berat. Revit untuk model besar dan render real-time memerlukan spesifikasi lebih tinggi. Kartu grafis workstation profesional (seri RTX A) umumnya hanya untuk kebutuhan kantor yang mensyaratkan sertifikasi; mahasiswa cukup dengan GPU konsumen.

---

## P08 — Live Streamer dan VTuber

- **ID:** P08 | **Tag katalog:** streaming, gaming | **Perangkat:** desktop (ideal), laptop gaming
- **Kata kunci pelanggan:** streaming, live streaming, OBS, Twitch, YouTube Live, live TikTok, VTuber, VTube Studio, Live2D, face tracking, streamer game
- **Kebutuhan/Aktivitas:** Streaming sambil bermain game, OBS Studio, avatar VTuber dengan face tracking, dan multitasking berat.
- **Karakteristik yang dicari:** CPU multi-core tangguh dan encoder hardware pada GPU (NVENC) agar game tidak tersendat saat streaming.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i7 atau Ryzen 7 | Core i7/i9 seri H/HX atau Ryzen 7/9 |
| RAM | 16GB | 32GB |
| Penyimpanan | SSD 1TB NVMe | SSD 1TB atau lebih |
| GPU | RTX 3060 atau RTX 4060 | RTX 4060 atau lebih tinggi |
| Layar | Satu layar (cukup untuk memulai) | Dua monitor (satu untuk game, satu untuk OBS dan chat) |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 1000; cpu_tier ≥ 3; gpu_dedicated = 1.
- **Catatan:** GPU Nvidia (NVENC) paling kompatibel dengan OBS, tetapi GPU AMD dan Intel Arc juga memiliki encoder hardware. Kebutuhan lain di luar komputer: internet dengan upload stabil (sekitar 10 Mbps atau lebih untuk 1080p), webcam, mikrofon, dan capture card jika perlu. Live shopping atau live jualan tanpa game berat jauh lebih ringan; lihat P12.

---

## P09 — Music Producer dan Audio Engineer

- **ID:** P09 | **Tag katalog:** music | **Perangkat:** laptop, desktop
- **Kata kunci pelanggan:** produksi musik, DAW, FL Studio, Ableton Live, Logic Pro, Cubase, Pro Tools, Reaper, rekaman, mixing, mastering, VST, audio interface, home studio
- **Kebutuhan/Aktivitas:** Produksi musik (DAW), merekam instrumen, mixing dan mastering, memakai banyak plugin dan sample library.
- **Karakteristik yang dicari:** CPU tangguh dengan latency rendah, RAM besar, sistem senyap. GPU tidak penting.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i7 atau Ryzen 7 (atau Apple M-series) | Core i7/i9, Ryzen 7/9, atau Apple M-series Pro/Max |
| RAM | 16GB | 32GB sampai 64GB (proyek besar dan sample library) |
| Penyimpanan | SSD 1TB NVMe | SSD 1TB ditambah SSD eksternal untuk sample |
| GPU | Integrated | Integrated |
| Layar | Layar laptop/monitor biasa | Monitor eksternal ultrawide (opsional) untuk melihat timeline |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 1000; cpu_tier ≥ 3; gpu_dedicated tidak disyaratkan.
- **Catatan:** Logic Pro hanya tersedia di macOS. Pastikan port USB mencukupi untuk audio interface dan controller. Kipas yang bising bisa terekam mikrofon, jadi laptop gaming kurang ideal. Jangan menaikkan budget ke GPU; alihkan ke CPU, RAM, dan SSD.

---

## P10 — Trader Saham dan Kripto

- **ID:** P10 | **Tag katalog:** trading | **Perangkat:** desktop (ideal untuk multi-monitor), laptop
- **Kata kunci pelanggan:** trading, trader, saham, kripto, forex, TradingView, MetaTrader, banyak tab, banyak monitor, multi monitor, pantau chart
- **Kebutuhan/Aktivitas:** Membaca grafik, aplikasi trading, puluhan tab browser, memantau berita secara bersamaan.
- **Karakteristik yang dicari:** Stabilitas, dukungan banyak monitor, RAM lega.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i3/i5 atau Ryzen 3/5 | Core i5 atau Ryzen 5 |
| RAM | 16GB | 32GB (jika monitor lebih dari 3 atau tab sangat banyak) |
| Penyimpanan | SSD 512GB NVMe | SSD 512GB sampai 1TB |
| GPU | Integrated atau dedicated entry | GPU dengan banyak port output (HDMI/DisplayPort) |
| Layar | 2 monitor | 2 sampai 4 monitor |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 1.
- **Catatan:** Jumlah monitor dibatasi oleh port output dan kemampuan GPU. Cek jumlah port HDMI, DisplayPort, atau USB-C (DisplayPort Alt Mode). Laptop umumnya mendukung 1 sampai 2 monitor eksternal; untuk 4 monitor, desktop dengan GPU yang punya banyak output lebih tepat. Koneksi internet yang stabil dan UPS membantu menjaga kontinuitas.

---

## P11 — Pengguna Sederhana dan Orang Tua (Penggunaan Ringan)

- **ID:** P11 | **Tag katalog:** daily | **Perangkat:** laptop 15,6 inci, desktop All-in-One
- **Kata kunci pelanggan:** untuk mama, untuk papa, orang tua, kakek nenek, simpel, mudah dipakai, nonton YouTube, video call, WhatsApp Web, Facebook, email, belajar anak SD, harian
- **Kebutuhan/Aktivitas:** Menonton video, video call, WhatsApp Web, media sosial, e-mail, dan mengetik ringan.
- **Karakteristik yang dicari:** Mudah dipakai, layar besar dan jelas, ringan, tahan lama, harga terjangkau.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Intel N-series, Core i3, atau Ryzen 3 | Core i3/i5 atau Ryzen 3/5 |
| RAM | 8GB | 8GB sampai 16GB |
| Penyimpanan | SSD 256GB | SSD 512GB |
| GPU | Integrated | Integrated |
| Layar | 15,6 inci FHD (huruf lebih besar), keyboard dengan numpad | 15,6 inci IPS FHD, anti-silau |

- **Filter minimum:** ram_gb ≥ 8; storage_ssd_gb ≥ 256; cpu_tier ≥ 1; gpu_dedicated tidak disyaratkan.
- **Catatan:** Hindari laptop gaming (berat, kipas bising, baterai pendek). Utamakan layar besar, bobot ringan, baterai awet, dan garansi. Ukuran teks dan ikon dapat diperbesar lewat pengaturan Windows.

---

## P12 — Content Creator Ringan (Media Sosial dan Video 1080p)

- **ID:** P12 | **Tag katalog:** video_editing, daily | **Perangkat:** laptop, desktop
- **Kata kunci pelanggan:** content creator, konten TikTok, Reels, CapCut, Canva, Filmora, edit video, vlog, YouTuber pemula, podcast, live shopping, live jualan
- **Kebutuhan/Aktivitas:** Mengedit video hingga 1080p (CapCut PC, Filmora, Premiere dasar), desain di Canva, podcast, dan live jualan.
- **Karakteristik yang dicari:** Render cukup cepat, penyimpanan lega, harga masih terjangkau.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 | Core i7 atau Ryzen 7 |
| RAM | 16GB | 32GB |
| Penyimpanan | SSD 512GB NVMe | SSD 1TB |
| GPU | Integrated kelas menengah (Iris Xe, Radeon) | RTX 3050 atau RTX 4050 (render lebih cepat) |
| Layar | FHD, sRGB baik | FHD IPS, sRGB ≥ 100% |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2.
- **Catatan:** File video cepat memenuhi penyimpanan; sarankan SSD eksternal untuk arsip. Untuk video 4K dan 3D, gunakan P03.

---

## P13 — Data Scientist, AI/Machine Learning, dan LLM Lokal

- **ID:** P13 | **Tag katalog:** ai_ml, programming | **Perangkat:** desktop (ideal), laptop dengan GPU Nvidia
- **Kata kunci pelanggan:** AI, machine learning, deep learning, data science, Python, Jupyter, TensorFlow, PyTorch, Ollama, LM Studio, LLM lokal, Stable Diffusion, skripsi AI
- **Kebutuhan/Aktivitas:** Pengolahan data, melatih model skala kecil, menjalankan model bahasa lokal (Ollama, LM Studio), dan menghasilkan gambar dengan Stable Diffusion.
- **Karakteristik yang dicari:** GPU Nvidia dengan VRAM sebesar mungkin, RAM besar, penyimpanan lega untuk dataset dan model.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i7 atau Ryzen 7 | Core i7/i9 atau Ryzen 7/9 |
| RAM | 16GB (lebih baik 32GB) | 32GB sampai 64GB |
| Penyimpanan | SSD 1TB NVMe | SSD 1 sampai 2TB |
| GPU | Nvidia RTX, VRAM ≥ 8GB | Nvidia RTX, VRAM 12 sampai 16GB atau lebih |
| Layar | FHD | FHD atau QHD |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 1000; cpu_tier ≥ 3; gpu_dedicated = 1 (Nvidia, cek kolom gpu); vram_gb ≥ 8.
- **Perkiraan kebutuhan VRAM model bahasa lokal (kuantisasi 4-bit):** model 7B sampai 8B parameter sekitar 5 sampai 6GB; model 13B sekitar 9 sampai 10GB; model 70B memerlukan puluhan GB sehingga membutuhkan workstation atau server, bukan laptop biasa.
- **Catatan:** Ekosistem CUDA milik Nvidia paling luas didukung pustaka AI; dukungan GPU AMD lebih terbatas. Perhatikan perbedaan VRAM laptop dan desktop (lihat G02). Perangkat Apple M-series dengan memori terpadu besar (32GB atau lebih) juga dapat menjalankan LLM lokal. Pelatihan model besar sebaiknya memakai layanan cloud.

---

## P14 — Akuntan, Analis Data, dan Pengguna Excel Berat

- **ID:** P14 | **Tag katalog:** office | **Perangkat:** laptop, desktop
- **Kata kunci pelanggan:** akuntan, akuntansi, analis data, Excel berat, pivot table, macro VBA, Power BI, SPSS, Accurate, Zahir, laporan keuangan, data ribuan baris
- **Kebutuhan/Aktivitas:** Mengolah file Excel besar, pivot table, macro, Power BI, aplikasi akuntansi, dan statistik.
- **Karakteristik yang dicari:** RAM lega, CPU dengan performa single-core baik, keyboard dengan numpad, layar nyaman.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 | Core i5/i7 atau Ryzen 5/7 |
| RAM | 16GB | 32GB (file besar dan Power BI) |
| Penyimpanan | SSD 512GB NVMe | SSD 512GB sampai 1TB |
| GPU | Integrated | Integrated |
| Layar | 15,6 inci FHD dengan numpad | Ditambah monitor kedua |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2; gpu_dedicated tidak disyaratkan.
- **Catatan:** Excel 64-bit memanfaatkan RAM besar untuk data banyak. GPU dedicated tidak diperlukan.

---

## P15 — UMKM, Kasir, dan Perangkat Toko (POS)

- **ID:** P15 | **Tag katalog:** office, daily | **Perangkat:** desktop atau All-in-One (utama), laptop
- **Kata kunci pelanggan:** kasir, POS, aplikasi kasir, toko, warung, kafe, restoran, UMKM, printer struk, barcode scanner, stok barang, komputer untuk usaha
- **Kebutuhan/Aktivitas:** Menjalankan aplikasi kasir dan stok, mencetak struk, membaca barcode, dan administrasi toko.
- **Karakteristik yang dicari:** Awet dan stabil untuk dipakai seharian, harga terjangkau, port lengkap.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Intel N-series, Core i3, atau Ryzen 3 | Core i3/i5 atau Ryzen 3/5 |
| RAM | 8GB | 8GB sampai 16GB |
| Penyimpanan | SSD 256GB | SSD 256GB sampai 512GB |
| GPU | Integrated | Integrated |
| Layar | 14 sampai 15,6 inci, atau All-in-One layar sentuh | All-in-One layar sentuh |

- **Filter minimum:** ram_gb ≥ 8; storage_ssd_gb ≥ 256; cpu_tier ≥ 1; gpu_dedicated tidak disyaratkan.
- **Catatan:** Pastikan jumlah port USB cukup untuk printer struk, barcode scanner, dan perangkat lain. Desktop atau All-in-One biasanya lebih awet untuk meja kasir. Untuk printer struk dan printer lain, lihat M02.

---

## P16 — Serbaguna: Kerja/Kuliah dan Game Sesekali

- **ID:** P16 | **Tag katalog:** gaming, office | **Perangkat:** laptop
- **Kata kunci pelanggan:** serbaguna, bisa semuanya, kerja dan main game, kuliah sambil main game, laptop all-round, edit sesekali, multitasking
- **Kebutuhan/Aktivitas:** Pekerjaan kantor atau kuliah sehari-hari, ditambah game ringan hingga menengah dan editing sesekali.
- **Karakteristik yang dicari:** Keseimbangan antara performa, bobot, baterai, dan harga.

| Komponen | Minimum | Direkomendasikan |
|---|---|---|
| CPU | Core i5 atau Ryzen 5 | Core i5 seri H atau Ryzen 5 seri H, atau lebih tinggi |
| RAM | 16GB | 16GB sampai 32GB |
| Penyimpanan | SSD 512GB NVMe | SSD 1TB |
| GPU | Integrated kelas menengah untuk game ringan | Dedicated entry (RTX 2050/3050/4050) |
| Layar | FHD IPS | FHD IPS, 60 sampai 144Hz |

- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2.
- **Catatan:** Setiap kemampuan tambahan mengorbankan baterai dan bobot. Jika game kompetitif adalah prioritas utama, gunakan P04; jika pekerjaan kreatif yang berat, gunakan profil yang sesuai (P02, P03, P12).

---

## M01 — Panduan Memilih Monitor

- **ID:** M01 | **Tipe:** panduan kategori | **Kategori katalog:** monitor
- **Kata kunci pelanggan:** monitor, layar, LED, IPS, 144Hz, 4K, ultrawide, monitor kerja, monitor gaming, monitor desain
- **Ukuran dan resolusi:** 24 inci FHD untuk kantor dan penggunaan umum; 27 inci QHD (2K) nyaman untuk multitasking dan kerja kreatif; 4K bermanfaat pada 27 inci ke atas untuk desain dan video; ultrawide 34 inci cocok untuk timeline video, trading, dan musik.
- **Jenis panel:** IPS untuk warna akurat dan sudut pandang luas (desain, umum); VA untuk kontras tinggi (film, gaming santai); TN murah dan cepat tetapi warna kurang baik.
- **Refresh rate:** 60Hz sampai 75Hz untuk kantor; 120Hz sampai 144Hz untuk gaming; 165Hz atau lebih untuk gaming kompetitif.
- **Akurasi warna:** sRGB ≥ 99% untuk desain dan foto; DCI-P3 tinggi untuk video.
- **Port dan kompatibilitas:** Pastikan port monitor (HDMI, DisplayPort, USB-C) sesuai dengan output komputer atau laptop. USB-C dengan DisplayPort Alt Mode memungkinkan satu kabel untuk video dan pengisian daya pada laptop yang mendukung.
- **Pemetaan cepat:** kantor, IPS 24 inci FHD; desain, IPS sRGB 100% (27 inci); gaming, 144Hz atau lebih; trading, 2 sampai 4 monitor 24 inci.

---

## M02 — Panduan Memilih Printer

- **ID:** M02 | **Tipe:** panduan kategori | **Kategori katalog:** printer
- **Kata kunci pelanggan:** printer, cetak, print, scan, fotokopi, tinta, toner, printer struk, cetak foto, printer kantor
- **Jenis printer:**
  - Inkjet tangki tinta (ink tank): biaya cetak per lembar rendah; cocok untuk cetak dokumen dan foto volume menengah sampai sering, serta usaha kecil.
  - Inkjet kartrid: harga awal murah, tetapi biaya per halaman lebih tinggi; cocok jika jarang mencetak. Tinta bisa mengering jika lama tidak dipakai.
  - Laser monokrom: cepat dan hemat untuk dokumen teks hitam putih volume tinggi (kantor, sekolah).
  - Laser warna: untuk kantor yang membutuhkan cetak warna cepat.
  - Printer thermal: untuk struk kasir (lihat P15); tidak memakai tinta.
- **Fitur tambahan:** Multifungsi (print, scan, copy), duplex (cetak bolak-balik), ADF (pemindai dokumen otomatis), Wi-Fi.
- **Pertanyaan klarifikasi:** Berapa volume cetak per bulan? Hitam putih atau warna? Perlu cetak foto? Perlu scan atau fotokopi?
