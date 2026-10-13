# -*- coding: utf-8 -*-
"""
Taksonomi Beban Kerja (Workload Tiers), Persona Penerima, dan Leksikon Spesifikasi v1.2 §22
"""
from __future__ import annotations

# =============================================================================
# 1. LABEL & TAG KEBUTUHAN (§22)
# =============================================================================

NEED_LABEL: dict[str, str] = {
    "office": "kerja/office",
    "admin_kasir": "administrasi/kasir",
    "student": "kuliah/perkuliahan",
    "programming": "programming",
    "web_dev": "web development",
    "android_studio": "Android Studio",
    "docker": "Docker",
    "vm": "virtual machine",
    "data_processing": "data processing",
    "design": "desain",
    "video_editing": "editing video",
    "rendering_3d": "rendering/3D",
    "ai_dev": "AI development",
    "gaming": "gaming",
    "daily": "penggunaan harian",
    "printing": "cetak/print dokumen",
    "scan_copy": "scan dan fotokopi",
}

NEED_TAGS = set(NEED_LABEL.keys())

# Leksikon pencocokan kebutuhan dari ucapan pelanggan (§22)
NEED_LEXICON: dict[str, list[str]] = {
    "office": [
        "kerja", "kerjaan", "pekerjaan", "kantor", "kantoran", "office", "ngetik",
        "mengetik", "dokumen", "word", "excel", "administrasi", "admin",
        # Profesi umum → kebutuhan office
        "dokter", "dokter umum", "dokter gigi", "dokter spesialis", "tenaga medis",
        "perawat", "bidan", "apoteker", "nakes",
        "guru", "dosen", "pengajar", "pendidik", "tenaga pengajar",
        "hakim", "jaksa", "pengacara", "notaris", "advokat",
        "akuntan", "auditor", "finansial", "keuangan",
        "wartawan", "jurnalis", "penulis", "redaktur",
        "pegawai negeri", "pns", "asn", "aparatur"
    ],
    "admin_kasir": ["kasir"],
    "student": [
        "kuliah", "perkuliahan", "kampus", "skripsi", "tugas kuliah", "sekolah", "siswa"
    ],
    "programming": [
        "programming", "programmer", "pemrograman", "coding", "ngoding", "koding", "flutter",
        "konsultan it", "it consultant", "orang it", "anak it", "developer", "dev",
        "bikin aplikasi", "buat aplikasi", "software dev"
    ],
    "web_dev": [
        "web development", "web dev", "web developer", "web programming", "bikin web", "buat website", "website", "pengembangan web"
    ],
    "android_studio": ["android studio", "android", "android developer", "mobile dev", "aplikasi android"],
    "docker": ["docker"],
    "vm": ["virtual machine", "vm"],
    "data_processing": ["data processing", "olah data"],
    "design": [
        "desain", "design", "desainer", "desain grafis", "grafis", "grafis berat",
        "komputasi grafis", "pekerjaan grafis", "beban grafis", "gambar", "bisa gambar",
        "bikin gambar", "buat gambar", "menggambar", "drawing", "ilustrasi",
        "gambar gambar", "sketsa", "photoshop", "corel", "coreldraw", "illustrator",
        "arsitek", "arsitektur", "cad", "autocad", "sketchup", "revit", "gambar rumah",
        "desain rumah", "bikin rumah", "desain bangunan",
        "insinyur", "engineer", "engineering", "teknik", "anak teknik", "orang teknik",
        "teknik mesin", "teknik sipil", "teknik elektro", "teknik industri", "solidworks",
        "catia", "inventor", "gambar teknik", "desain teknik", "denah", "blueprint"
    ],
    "video_editing": [
        "editing video", "edit video", "video editing", "editing", "edit", "ngedit video"
    ],
    "rendering_3d": [
        "rendering", "render", "3d", "3d rendering", "grafis berat", "komputasi grafis",
        "komputasi berat", "tugas berat", "kerja berat", "arsitek", "arsitektur", "cad",
        "autocad", "sketchup", "revit", "archicad", "3ds max", "gambar rumah",
        "desain rumah", "bikin rumah", "desain bangunan",
        "insinyur", "engineer", "engineering", "teknik", "solidworks", "catia",
        "simulasi", "simulasi teknik", "ansys", "matlab", "model 3d", "pemodelan 3d",
        "konstruksi", "ngitung konstruksi", "hitung konstruksi", "analisis struktur", "ngitung", "hitung", "sap2000", "etabs"
    ],
    "ai_dev": ["ai development", "ai dev", "pengembangan ai", "buat ai", "ngembangin ai", "machine learning", "data science"],
    "gaming": [
        "gaming", "game", "main game", "gamer", "gamers", "ngegame", "nge game", "nge-game",
        "buat ngegame", "buat main game", "gaming berat", "game berat", "game aaa", "gaming aaa",
        "game online", "valorant", "dota", "genshin", "gta", "steam"
    ],
    # Aktivitas santai/harian yang dipetakan ke daily
    "daily": [
        "penggunaan harian", "harian", "sehari hari", "browsing", "nonton", "sosmed",
        "fesbuk", "fesbukan", "facebook", "youtube", "youtuban", "resep", "nanya resep",
        "chatgpt", "canva", "santai", "gemini", "google gemini", "claude", "copilot",
        "mobilitas harian", "hemat daya", "tugas ringan", "kerja ringan",
        # Masak, resep, kuliner, dan aktivitas rumahan
        "masak", "memasak", "buat masak", "untuk masak", "bikin kue", "buat kue", "baking",
        "resep masakan", "resep kue", "lihat resep", "nonton resep", "video masak", "di dapur",
        "dapur", "kuliner", "belanja", "olshop", "shopee", "tokopedia", "tiktok", "instagram",
        "drakor", "drama korea", "film", "streaming", "netflix", "santai santai",
        "nonton film", "nonton youtube", "hiburan", "putar musik", "musik", "lagu"
    ],
    "printing": [
        "cetak", "ngeprint", "print", "printer", "cetak dokumen", "cetak foto", "cetak tugas",
        "cetak berkas", "cetak struk", "cetak kasir", "print dokumen", "print warna", "ngeprint tugas"
    ],
    "scan_copy": [
        "scan", "scanner", "copy", "fotokopi", "foto copy", "fotocopy", "scan berkas",
        "scan dokumen", "fotokopi berkas", "fotokopi dokumen"
    ],
}

# =============================================================================
# 2. PERSONA PENERIMA (RECIPIENT PERSONAS)
# =============================================================================

PERSONA_LEXICON: dict[str, list[str]] = {
    "family_elder": [
        "papa", "papaku", "ayah", "ayahku", "bapak", "bapakku", "mama", "mamaku",
        "ibu", "ibuku", "orang tua", "kakek", "nenek", "om", "omku", "om aku",
        "paman", "pamanku", "tante", "tanteku", "bibi", "bibiku"
    ],
    "student_kid": ["anak", "anakku", "adik", "adikku", "anak sekolah", "pelajar", "anak sd", "anak smp", "anak sma"],
    "student_college": ["mahasiswa", "anak kuliah"],
    "colleague": ["karyawan", "pegawai", "rekan kantor"],
}

IDENTITY_STUDENT = ["mahasiswa", "siswa", "pelajar", "anak kuliah", "anak sekolah"]
IDENTITY_TYPE = {
    "mahasiswa": "mahasiswa", "anak kuliah": "mahasiswa",
    "siswa": "siswa", "pelajar": "siswa", "anak sekolah": "siswa",
    "pegawai": "pegawai", "karyawan": "pegawai"
}

# =============================================================================
# 3. KATEGORI PERANGKAT (§19)
# =============================================================================

CATEGORY_WORDS: dict[str, str] = {
    "laptop": "laptop",
    "notebook": "laptop",
    "desktop": "desktop",
    "komputer": "computer",
    "pc": "computer",
    "printer": "printer",
    "monitor": "monitor",
}

CATEGORY_LABEL: dict[str | None, str] = {
    "laptop": "laptop",
    "desktop": "desktop",
    "computer": "komputer",
    "printer": "printer",
    "monitor": "monitor",
    None: "komputer",
}

CATEGORY_NOUN_NYA: dict[str | None, str] = {
    "laptop": "Laptopnya",
    "desktop": "Desktopnya",
    "computer": "Komputernya",
    "printer": "Printernya",
    "monitor": "Monitornya",
    None: "Komputernya",
}

# =============================================================================
# 3B. MEREK / BRAND PERANGKAT
# =============================================================================

BRAND_LEXICON: dict[str, list[str]] = {
    "acer": ["acer", "predator", "nitro", "aspire", "swift"],
    "asus": ["asus", "tuf", "rog", "vivobook", "zenbook", "expertcenter"],
    "lenovo": ["lenovo", "loq", "legion", "ideapad", "thinkpad", "ideacentre"],
    "hp": ["hp", "victus", "omen", "pavilion", "14s"],
    "dell": ["dell", "alienware", "inspiron", "vostro"],
    "apple": ["apple", "macbook", "mac"],
    "canon": ["canon", "pixma"],
    "epson": ["epson", "ecotank"],
    "brother": ["brother"],
    "nusatech": ["nusatech"],
    "astrabook": ["astrabook"],
    "garuda": ["garuda"],
    "rajawali": ["rajawali"],
}

# =============================================================================
# 4. ATRIBUT SPESIFIKASI & HARGA (§11.4)
# =============================================================================

HARDWARE_LEXICON: dict[str, list[str]] = {
    "cpu_vendor": ["intel", "amd", "ryzen", "core", "celeron", "athlon", "xeon"],
    "cpu_model": ["core i3", "core i5", "core i7", "core i9", "i3", "i5", "i7", "i9", "n100", "7530u", "1215u", "1235u", "13420h", "12450hx", "13400", "14700f", "14650hx", "7735hs"],
    "gpu_vendor": ["nvidia", "geforce", "rtx", "gtx", "radeon", "intel iris", "iris xe", "iris", "intel uhd", "uhd graphics", "uhd", "arc"],
    "gpu_model": ["rtx 4070", "rtx 4060", "rtx 4050", "rtx 3050", "rtx 2050", "gtx 1660", "gtx 1650"],
    "gpu_type": ["discrete", "dedicated", "integrated"],
    "memory": ["ram", "ddr4", "ddr5", "vram", "memori"],
    "storage": ["ssd", "nvme", "hdd", "storage", "penyimpanan"],
    "display": ["oled", "ips", "144 hz", "144hz", "fhd", "2.8k", "wuxga"],
}

ATTR_LEXICON: dict[str, list[str]] = {
    "price": ["harga", "berapaan", "berapa harga", "harga berapa"],
    "ram": ["ram", "memori", "memory", "ddr4", "ddr5", "vram"],
    "cpu": ["prosesor", "processor", "cpu", "intel", "amd", "ryzen", "core", "celeron", "i3", "i5", "i7", "i9", "n100"],
    "gpu": ["gpu", "vga", "kartu grafis", "kartu grafik", "nvidia", "geforce", "rtx", "gtx", "radeon", "iris", "iris xe", "uhd", "arc", "discrete", "dedicated"],
    "storage": ["storage", "ssd", "nvme", "hdd", "penyimpanan"],
    "display": ["layar", "display", "inci", "oled", "ips", "144hz", "144 hz", "fhd"],
    "os": ["windows", "os", "sistem operasi"],
    "fungsi": ["fungsi", "fitur", "all in one", "multifungsi", "print scan copy", "scan copy"],
    "teknologi": ["teknologi", "ink tank", "tangki tinta", "laser", "inkjet", "tinta"],
    "kecepatan": ["kecepatan", "kecepatan cetak", "speed", "ppm", "ipm"],
    "resolusi": ["resolusi", "dpi", "ketajaman"],
    "konektivitas": ["konektivitas", "koneksi", "wifi", "wi-fi", "wireless", "usb"],
    "spec": ["spek", "spesifikasi", "detail", "specs"],
}

ATTR_LABEL: dict[str, str] = {
    "price": "Harga",
    "ram": "RAM",
    "cpu": "Prosesor",
    "gpu": "GPU",
    "storage": "Storage",
    "display": "Layar",
    "os": "Sistem operasi",
    "fungsi": "Fungsi",
    "teknologi": "Teknologi",
    "kecepatan": "Kecepatan cetak",
    "resolusi": "Resolusi",
    "konektivitas": "Konektivitas",
}

# =============================================================================
# 5. ATRIBUT TIDAK TERSEDIA & INFORMASI TOKO (§18.1)
# =============================================================================

UNAVAILABLE: dict[str, list[str]] = {
    "stok": ["stok", "stock", "ready", "sisa stok", "sisa"],
    "warna": ["warna"],
    "baterai": ["baterai", "battery", "daya tahan", "wh"],
    "berat": ["berapa berat", "berat", "bobot"],
    "garansi": ["garansi", "warranty"],
    "port/konektivitas": [
        "port", "hdmi", "usb", "bluetooth", "wifi", "webcam", "konektivitas"
    ],
    "promo/bonus": ["diskon", "promo", "bonus", "cashback", "hadiah", "voucher"],
    "pembayaran dan pengiriman": [
        "cicilan", "kredit", "angsuran", "cod", "bayar", "pembayaran",
        "kirim", "pengiriman", "ongkir", "transfer"
    ],
    "operasional toko": [
        "jam buka", "jam operasional", "buka jam berapa", "buka gak", "buka tidak",
        "toko buka", "alamat", "lokasi", "cabang", "toko fisik",
        "di mana", "dimana", "di mana tokonya", "dimana tokonya", "lokasinya di mana"
    ],
}

# =============================================================================
# 6. INTENT KHUSUS (KOMPARASI, KETIDAKPASTIAN, KOREKSI, PEMBATALAN)
# =============================================================================

COMPARE_WORDS = {
    "beda", "bedanya", "perbedaan", "bandingkan", "banding", "dibanding",
    "dibandingkan", "vs", "versus", "bandingin"
}

COMPARE_PHRASES = [
    "lebih cocok", "lebih bagus", "lebih baik", "mana yang lebih", "bagus mana",
    "mending mana", "pilih mana", "bagusan mana", "mana yang bagus", "mana yang cocok",
    "cocok yang mana", "pilih yang mana", "bagus yang mana", "dari 2 itu", "dari dua itu"
]

UNCERTAIN_PHRASES = [
    "terserah", "belum tahu", "tidak tahu", "bebas", "apa saja", "apa aja",
    "belum ada", "bingung", "pusing", "kurang paham", "kurang ngerti",
    "nggak tahu", "gatau", "ngga tau", "nggak ngerti", "untuk apa ya", "buat apa ya",
    "macem2", "macem macem", "macam macam", "macam2", "apa pun", "apapun", "campur",
    "semua game", "game apa aja", "game apa saja", "semuanya"
]

# Ungkapan kritik alur percakapan (Meta-Critique)
META_CRITIQUE_PHRASES = [
    "kurang nangkap kok nawarin",
    "kurang paham kok nawarin",
    "belum ngomong buat apa",
    "belum bilang buat apa",
    "kok nawarin",
    "gitu mulu",
    "kok gitu mulu",
    "dibilang bingung",
    "belajar nangkap",
    "belajar nangkep",
    "belajar paham",
    "belajar dengerin",
    "tidak perlu kuliah",
    "gak perlu kuliah",
    "kurang nangkap mulu",
    "kurang nangkep mulu",
    "kok tidak bisa",
    "kok gak bisa",
    "kenapa tidak bisa",
    "kenapa gak bisa",
    "gitu saja tidak nangkap",
    "gitu aja gak nangkap",
    "gitu saja tidak ngerti",
    "gitu aja gak ngerti",
    "tidak ngerti konsultan",
    "cari kambing",
    "yang minta",
    "siapa yang minta",
    "tidak perlu ditangkap",
    "gak perlu ditangkap",
    "tangkap apa",
    "ditanya jual apa malah disuruh cerita",
    "malah disuruh cerita",
    "malah suruh cerita",
    "malah nanya balik",
    "malah tanya balik",
    "gak jawab",
    "tidak jawab",
    "gak menjawab",
    "tidak menjawab",
    "itu gak jawab",
    "itu tidak jawab",
    "gak nyambung",
    "tidak nyambung",
    "salah jawab",
    "malah yang lain",
    "kok malah yang lain",
    "malah bahas yang lain",
    "kok ke yang lain",
]

SPEC_OBJECTION_PHRASES = [
    "tanggung", "tanggung banget", "nanggung", "nanggung banget",
    "kok nanggung", "kok tanggung", "speknya nanggung", "vramnya nanggung",
    "vram nanggung", "terlalu nanggung", "kurang nendang", "kurang greget",
    "tanggung amat", "nanggung amat",
]

CAPABILITY_PHRASES = [
    "bisa bantu apa", "emang bisa bantu apa", "bisa bantu apa saja", "bisa bantu apa aja",
    "bantu apa", "bantu apa saja", "bantu apa aja", "kamu bisa apa", "bisa apa",
    "bisa apa saja", "bisa apa aja", "bisa apa sih", "emang bisa apa", "layanan apa",
    "bantu apa sih"
]

BANTER_PHRASES = [
    "cari kamu", "mau kamu", "kamu saja", "kamu aja", "cari jodoh", "cari pacar",
    "cari teman", "suka kamu", "sama kamu"
]

INSULT_WORDS = {
    "bego", "tolol", "goblok", "bodoh", "ngeselin", "payah", "geblek", "idiot",
    "tidak guna", "gak guna", "capek", "capek deh", "bego amat"
}

CATALOG_DOUBT_PHRASES = [
    "gak liat katalog", "tidak liat katalog", "gak lihat katalog", "tidak lihat katalog",
    "gak baca katalog", "tidak baca katalog", "baca katalog", "liat katalog", "lihat katalog",
    "buka katalog", "gak ada di katalog", "tidak ada di katalog"
]

META_EXPLANATION_PHRASES = [
    "tadi kan nanya", "kan tadi nanya", "aku jawab", "saya jawab", "lah tadi", "kan nanya",
    "kan dibilang", "kan sudah dibilang", "lah kan", "kan saya bilang", "kan aku bilang",
    "sudah dibilang", "sudah berkali-kali bilang", "sudah bilang", "kan sudah bilang"
]

META_NARRATIVE_WORDS = {
    "tadi", "kan", "nanya", "ngomong", "bilang", "jawab", "jawaban", "maksud", "maksudku",
    "maksudnya", "dibilang", "ditanya", "nyuruh", "katanya", "liat", "katalog", "baca", "lah",
    "sudah", "udah", "berkali", "kali", "capek"
}

# Ketidaksesuaian rekomendasi dengan ekspektasi pelanggan (Recommendation Mismatch)
MISMATCH_PHRASES = [
    "gak tepat", "tidak tepat", "kurang tepat", "keknya gak tepat", "kayaknya gak tepat",
    "kurang cocok", "gak cocok", "tidak cocok", "kurang pas", "gak pas", "tidak pas",
    "bukan itu", "bukan yang ini", "bukan maksudnya", "salah rekomendasi", "salah pilih",
    "mana bisa", "mana mungkin", "masa sih", "gak kuat", "tidak kuat", "kurang kuat",
    "kurang sanggup", "gak sanggup", "tidak sanggup"
]

# Kata-kata tata bahasa Indonesia yang bukan merupakan produk (Grammar Stopwords)
GRAMMAR_WORDS = {
    "kalau", "kalo", "kl", "jika", "bila", "terus", "lalu", "dan", "atau", "tapi", "tetapi",
    "namun", "karena", "soalnya", "supaya", "agar", "padahal", "kata", "katanya", "kan",
    "pun", "kok", "loh", "lah", "dong", "deh", "sih", "ya", "kenapa", "mengapa", "gimana",
    "bagaimana", "ngapain", "siapa", "sapa", "mana", "kapan", "bisa", "bisaan", "pinter",
    "pintar", "dasar", "cuma", "hanya", "apa", "apanya", "apaan", "tidak", "gak", "nggak",
    "belum", "sudah", "udah", "mau", "akan", "ingin", "boleh", "sama", "dengan", "buat",
    "untuk", "yang", "itu", "ini", "begitu", "gitu", "begini", "gini", "tahu", "tau",
    "info", "informasi", "punya", "ada", "bikin", "kuat", "sanggup", "kencang",
    "kenceng", "pas", "cocok", "tepat", "banget", "bener", "benar", "keknya", "kayaknya",
    "kayak", "kek", "pikir", "kira", "kurang", "lebih", "amat", "sangat", "kali", "berkali",
    "bilang", "ngomong", "dibilang", "tanya", "nanya", "jawab", "maksud", "maksudnya",
    "emang", "emangnya", "memang", "memangnya", "nih", "tuh", "aja", "saja", "masa"
}

# Permintaan jasa / di luar penjualan komputer (Service Out-of-Domain)
SERVICE_REQUEST_PHRASES = [
    "bikin pr", "bantuin bikin pr", "ngerjain pr", "buat pr", "bikin tugas", "ngerjain tugas",
    "buat tugas", "pijit", "pijat", "bantuin pijit", "cari jodoh", "makanan", "pesan makan"
]

PURCHASE_TOKENS = {
    "beli", "membeli", "pesan", "memesan", "order", "checkout", "booking", "ambil",
    "beliin", "belikan", "bayar", "bayarin", "pesankan"
}

CANCEL_SET = {
    "batal", "batal beli", "batalkan", "tidak jadi", "tidak jadi deh",
    "tidak jadi kak", "tidak usah", "tidak usah deh", "tidak jadi beli"
}

CLOSING_SET = {
    "sudah", "sudah saja", "sudah cukup", "cukup", "stop", "sudah kak",
    "sudah ah", "sudah deh"
}

AFFIRM_WORDS = {
    "ya", "iya", "boleh", "mau", "oke", "ok", "silakan", "tolong", "sip", "siap",
    "yuk", "baik", "tentu", "jelaskan", "bisa", "ada", "butuh"
}

NONPRODUCT_WORDS = {
    "murah", "mahal", "lebih", "lain", "lainnya", "rekomendasi", "saran", "pilihan",
    "produk", "barang", "tipe", "jenis", "model", "merek", "merk", "brand", "ukuran",
    "varian", "versi", "harga", "spek", "spesifikasi", "cara", "kabar", "orang", "cs",
    "admin", "hari", "bagus", "cocok", "baru", "bekas", "kabar", "info", "informasi",
    "xprodukx", "bagusan", "dikit", "sedikit", "opsi", "beliin", "belikan", "bayar", "bayarin",
    "tepat", "pas", "amat", "sangat", "bego", "capek", "mana", "kata"
}

AVAIL_VERBS = {
    "ada", "jual", "punya", "menjual", "jualan", "tersedia", "sedia", "menyediakan",
    "nawarkan", "menawarkan", "tawarkan", "layanan", "jasa", "service", "servis",
    "bantu", "bantuin", "bisa", "cari", "mencari"
}
AVAIL_SKIP = {
    "yang", "apa", "lagi", "saja", "juga", "tidak", "kak", "ya", "dong", "dikit", "sedikit",
    "emang", "apakah", "di", "sini", "toko", "ini", "kah", "kok", "itu", "nya", "deh", "sih",
    "bikin", "buat", "minta", "tolong", "nih", "gan", "min", "aku", "saya", "kamu",
    "beliin", "belikan", "bayar", "bayarin", "pesan", "kalau", "kalo", "kl", "jika", "bila",
    "terus", "lalu", "dan", "atau", "tapi", "tetapi", "namun", "karena", "soalnya", "supaya",
    "agar", "padahal", "kata", "katanya", "kan", "pun", "loh", "lah", "kenapa", "mengapa",
    "gimana", "bagaimana", "ngapain", "siapa", "sapa", "mana", "kapan", "bisa", "pinter",
    "pintar", "dasar", "cuma", "hanya", "info", "informasi", "tahu", "tau", "punya", "ada"
}
