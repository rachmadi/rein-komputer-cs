# -*- coding: utf-8 -*-
"""
scripts/create_parse_gold.py
Membuat dataset label evaluasi parser:
- eval/parse_gold.jsonl (150 contoh: 100 dev, 50 held-out)
- eval/parse_gold.csv (tabel mudah dibaca & diperiksa Frank/user)
"""
import os
import json
import csv

# Pastikan folder eval ada
os.makedirs("eval", exist_ok=True)

# 100 DEV EXAMPLES (40 pertama adalah dev gatekeeper set)
dev_items = [
    # --- 40 DEV GATEKEEPER SET (Termasuk kalimat log kegagalan, gaul, typo) ---
    {
        "id": "dev-001",
        "pesan": "Emang spek segitu cukup?",
        "state": {"pending_question": None, "slot_diketahui": {"kebutuhan_teks": "cari resep dan nonton YouTube"}, "produk_tampil": [{"no": 1, "kode": "KB-L01"}, {"no": 2, "kode": "KB-L02"}]},
        "label_aksi": "evaluasi_kecocokan",
        "label_argumen": {"produk": ["KB-L01", "KB-L02"], "kebutuhan_teks": "cari resep dan nonton YouTube"},
        "label_pembaruan_state": {},
        "catatan": "Log failure kalimat 1: konfirmasi kecocokan spek"
    },
    {
        "id": "dev-002",
        "pesan": "Yang tanya HP 14 siapa?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L05", "nama": "HP 14"}]},
        "label_aksi": "perbaiki_percakapan",
        "label_argumen": {"jenis": "keluhan", "rujukan": "HP 14"},
        "label_pembaruan_state": {},
        "catatan": "Log failure kalimat 2: sarkasme/keluhan bot salah tangkap"
    },
    {
        "id": "dev-003",
        "pesan": "Buat hiburan",
        "state": {"pending_question": "aktivitas", "produk_tampil": []},
        "label_aksi": "jawab_pertanyaan_bot",
        "label_argumen": {"slot": "aktivitas", "nilai": "hiburan"},
        "label_pembaruan_state": {"kebutuhan_teks": "hiburan"},
        "catatan": "Log failure kalimat 3: jawaban atas pending aktivitas"
    },
    {
        "id": "dev-004",
        "pesan": "Mana?",
        "state": {"pending_question": None, "slot_diketahui": {"kebutuhan_teks": "hiburan nonton youtube"}, "produk_tampil": []},
        "label_aksi": "minta_rekomendasi",
        "label_argumen": {"kebutuhan_teks": "hiburan nonton youtube"},
        "label_pembaruan_state": {},
        "catatan": "Log failure kalimat 4: menagih rekomendasi"
    },
    {
        "id": "dev-005",
        "pesan": "ada asus?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"merek": "asus", "kategori": "laptop"},
        "label_pembaruan_state": {},
        "catatan": "Pencarian ketersediaan merek"
    },
    {
        "id": "dev-006",
        "pesan": "yang kedua bagus nggak?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01"}, {"no": 2, "kode": "KB-L02"}]},
        "label_aksi": "evaluasi_kecocokan",
        "label_argumen": {"produk": ["2"]},
        "label_pembaruan_state": {},
        "catatan": "Evaluasi spesifik produk nomor 2"
    },
    {
        "id": "dev-007",
        "pesan": "Aku tanya kok malah dikasih spek lain",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L05"}]},
        "label_aksi": "perbaiki_percakapan",
        "label_argumen": {"jenis": "salah_paham", "rujukan": "dikasih spek lain"},
        "label_pembaruan_state": {},
        "catatan": "Log failure: teguran salah paham"
    },
    {
        "id": "dev-008",
        "pesan": "Kan sudah dibilang buat hiburan",
        "state": {"pending_question": None, "slot_diketahui": {"kebutuhan_teks": "hiburan"}, "produk_tampil": []},
        "label_aksi": "perbaiki_percakapan",
        "label_argumen": {"jenis": "koreksi", "rujukan": "buat hiburan"},
        "label_pembaruan_state": {"kebutuhan_teks": "hiburan"},
        "catatan": "Log failure: teguran amnesia bot"
    },
    {
        "id": "dev-009",
        "pesan": "halo kak",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "sapa",
        "label_argumen": {},
        "label_pembaruan_state": {},
        "catatan": "Sapaan pembuka santai"
    },
    {
        "id": "dev-010",
        "pesan": "p",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "sapa",
        "label_argumen": {},
        "label_pembaruan_state": {},
        "catatan": "Sapaan slang telegram"
    },
    {
        "id": "dev-011",
        "pesan": "siang min mau nanya2 nih",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "sapa",
        "label_argumen": {},
        "label_pembaruan_state": {},
        "catatan": "Sapaan siang santai"
    },
    {
        "id": "dev-012",
        "pesan": "jual laptop acer?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"merek": "acer", "kategori": "laptop"},
        "label_pembaruan_state": {"kategori": "laptop"},
        "catatan": "Pertanyaan ketersediaan merek acer"
    },
    {
        "id": "dev-013",
        "pesan": "laptop lenovo dibawah 10 juta ada ga?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"merek": "lenovo", "kategori": "laptop", "max_harga": 10000000},
        "label_pembaruan_state": {"budget": 10000000, "kategori": "laptop"},
        "catatan": "Pencarian merek + budget"
    },
    {
        "id": "dev-014",
        "pesan": "laptp asus ram 16gb",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"merek": "asus", "kategori": "laptop", "ram_gb_min": 16},
        "label_pembaruan_state": {"kategori": "laptop"},
        "catatan": "Typo laptp + ram 16gb"
    },
    {
        "id": "dev-015",
        "pesan": "ada printer canon ga ya",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"merek": "canon", "kategori": "printer"},
        "label_pembaruan_state": {"kategori": "printer"},
        "catatan": "Pencarian kategori printer canon"
    },
    {
        "id": "dev-016",
        "pesan": "Buat mama sih bukan buat aku",
        "state": {"pending_question": "kebutuhan", "produk_tampil": []},
        "label_aksi": "jawab_pertanyaan_bot",
        "label_argumen": {"slot": "persona", "nilai": "mama"},
        "label_pembaruan_state": {"persona": "mama", "sebutan": "mama"},
        "catatan": "Jawaban persona mama"
    },
    {
        "id": "dev-017",
        "pesan": "Paling cuma cari resep dan nonton youtube",
        "state": {"pending_question": "aktivitas", "slot_diketahui": {"persona": "mama"}, "produk_tampil": []},
        "label_aksi": "minta_rekomendasi",
        "label_argumen": {"kebutuhan_teks": "cari resep dan nonton youtube", "persona": "mama"},
        "label_pembaruan_state": {"kebutuhan_teks": "cari resep dan nonton youtube"},
        "catatan": "Kebutuhan resep & youtube"
    },
    {
        "id": "dev-018",
        "pesan": "Untuk ibu saya yang sudah sepuh",
        "state": {"pending_question": "kebutuhan", "produk_tampil": []},
        "label_aksi": "jawab_pertanyaan_bot",
        "label_argumen": {"slot": "persona", "nilai": "ibu sepuh"},
        "label_pembaruan_state": {"persona": "ibu sepuh", "sebutan": "ibu"},
        "catatan": "Jawaban persona ibu sepuh"
    },
    {
        "id": "dev-019",
        "pesan": "butuh laptop buat anak dkv semester 1",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "minta_rekomendasi",
        "label_argumen": {"kebutuhan_teks": "desain grafis dkv", "persona": "anak dkv"},
        "label_pembaruan_state": {"kebutuhan_teks": "desain grafis dkv"},
        "catatan": "Rekomendasi anak DKV"
    },
    {
        "id": "dev-020",
        "pesan": "budget maksimal 7 jutaan aja",
        "state": {"pending_question": "budget", "produk_tampil": []},
        "label_aksi": "jawab_pertanyaan_bot",
        "label_argumen": {"slot": "budget", "nilai": 7000000},
        "label_pembaruan_state": {"budget": 7000000},
        "catatan": "Jawaban budget"
    },
    {
        "id": "dev-021",
        "pesan": "ada yang lebih murah?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01", "harga": 7500000}]},
        "label_aksi": "lanjutan_hasil",
        "label_argumen": {"jenis": "lebih_murah"},
        "label_pembaruan_state": {},
        "catatan": "Lanjutan minta opsi lebih murah"
    },
    {
        "id": "dev-022",
        "pesan": "ada opsi merk lain ga selain acer?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01", "merek": "acer"}]},
        "label_aksi": "lanjutan_hasil",
        "label_argumen": {"jenis": "yang_lain"},
        "label_pembaruan_state": {},
        "catatan": "Minta opsi lain"
    },
    {
        "id": "dev-023",
        "pesan": "garansinya berapa lama min?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tanya_info_toko",
        "label_argumen": {"topik": "garansi"},
        "label_pembaruan_state": {},
        "catatan": "Info garansi toko"
    },
    {
        "id": "dev-024",
        "pesan": "tokonya ada di mana ya lokasinya?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tanya_info_toko",
        "label_argumen": {"topik": "alamat"},
        "label_pembaruan_state": {},
        "catatan": "Info alamat toko"
    },
    {
        "id": "dev-025",
        "pesan": "bisa bayar pake kartu kredit cicilan?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tanya_info_toko",
        "label_argumen": {"topik": "pembayaran"},
        "label_pembaruan_state": {},
        "catatan": "Info pembayaran cicilan"
    },
    {
        "id": "dev-026",
        "pesan": "bagusan nomor 1 apa nomor 2?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01"}, {"no": 2, "kode": "KB-L02"}]},
        "label_aksi": "bandingkan",
        "label_argumen": {"produk": ["1", "2"]},
        "label_pembaruan_state": {},
        "catatan": "Bandingkan produk 1 dan 2"
    },
    {
        "id": "dev-027",
        "pesan": "makasih banyak infonya sangat membantu",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "basa_basi",
        "label_argumen": {"jenis": "terima_kasih"},
        "label_pembaruan_state": {},
        "catatan": "Basa-basi terima kasih"
    },
    {
        "id": "dev-028",
        "pesan": "ok sip makasih ya",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "basa_basi",
        "label_argumen": {"jenis": "terima_kasih"},
        "label_pembaruan_state": {},
        "catatan": "Basa-basi terima kasih santai"
    },
    {
        "id": "dev-029",
        "pesan": "asdfghjkl",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tidak_jelas",
        "label_argumen": {"alasan": "teks acak tanpa arti"},
        "label_pembaruan_state": {},
        "catatan": "Teks gibberish/tidak jelas"
    },
    {
        "id": "dev-030",
        "pesan": "hmm gimana ya",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tidak_jelas",
        "label_argumen": {"alasan": "ragu-ragu tanpa maksud spesifik"},
        "label_pembaruan_state": {},
        "catatan": "Ungkapan ragu tidak jelas"
    },
    {
        "id": "dev-031",
        "pesan": "pc dekstop gaming rtx 4060",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"kategori": "desktop", "nama_model": "rtx 4060"},
        "label_pembaruan_state": {"kategori": "desktop"},
        "catatan": "Pencarian spesifik desktop gaming"
    },
    {
        "id": "dev-032",
        "pesan": "laptop murah buat ngetik word aja",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "minta_rekomendasi",
        "label_argumen": {"kebutuhan_teks": "ketik word office", "kategori": "laptop"},
        "label_pembaruan_state": {"kebutuhan_teks": "ketik word office", "kategori": "laptop"},
        "catatan": "Kebutuhan mengetik dokumen"
    },
    {
        "id": "dev-033",
        "pesan": "yang ram 32gb ada?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"ram_gb_min": 32},
        "label_pembaruan_state": {},
        "catatan": "Pencarian ram 32gb"
    },
    {
        "id": "dev-034",
        "pesan": "bisa buat main valorant ga laptop ini?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01"}]},
        "label_aksi": "evaluasi_kecocokan",
        "label_argumen": {"produk": ["KB-L01"], "kebutuhan_teks": "main valorant"},
        "label_pembaruan_state": {"kebutuhan_teks": "main valorant"},
        "catatan": "Evaluasi game valorant"
    },
    {
        "id": "dev-035",
        "pesan": "bukan itu yang kumaksud",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "perbaiki_percakapan",
        "label_argumen": {"jenis": "salah_paham", "rujukan": "bukan itu"},
        "label_pembaruan_state": {},
        "catatan": "Teguran bukan itu maksudku"
    },
    {
        "id": "dev-036",
        "pesan": "jam buka toko sampe jam berapa?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tanya_info_toko",
        "label_argumen": {"topik": "jam_buka"},
        "label_pembaruan_state": {},
        "catatan": "Tanya jam operasional"
    },
    {
        "id": "dev-037",
        "pesan": "apakah ada garansi resmi?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "tanya_info_toko",
        "label_argumen": {"topik": "garansi"},
        "label_pembaruan_state": {},
        "catatan": "Tanya klaim garansi resmi"
    },
    {
        "id": "dev-038",
        "pesan": "laptop layar 15.6 inch buat kakek",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "minta_rekomendasi",
        "label_argumen": {"kebutuhan_teks": "layar besar sepuh", "persona": "kakek", "kategori": "laptop"},
        "label_pembaruan_state": {"persona": "kakek", "sebutan": "kakek"},
        "catatan": "Persona kakek layar 15.6 inch"
    },
    {
        "id": "dev-039",
        "pesan": "ada printer brother?",
        "state": {"pending_question": None, "produk_tampil": []},
        "label_aksi": "cari_produk",
        "label_argumen": {"merek": "brother", "kategori": "printer"},
        "label_pembaruan_state": {"kategori": "printer"},
        "catatan": "Pencarian printer brother"
    },
    {
        "id": "dev-040",
        "pesan": "layarnya udah ips?",
        "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01"}]},
        "label_aksi": "evaluasi_kecocokan",
        "label_argumen": {"produk": ["KB-L01"], "kebutuhan_teks": "layar ips"},
        "label_pembaruan_state": {},
        "catatan": "Evaluasi layar IPS produk"
    },
]

# Tambah sisa dev sampai 100
for i in range(41, 101):
    idx_str = f"dev-{i:03d}"
    if i <= 50:
        dev_items.append({
            "id": idx_str,
            "pesan": f"rekomendasi laptop range harga {i % 10 + 5} jutaan",
            "state": {"pending_question": None, "produk_tampil": []},
            "label_aksi": "minta_rekomendasi",
            "label_argumen": {"budget_max": (i % 10 + 5) * 1000000, "kategori": "laptop"},
            "label_pembaruan_state": {"budget": (i % 10 + 5) * 1000000, "kategori": "laptop"},
            "catatan": f"Dev variasi budget {i % 10 + 5} juta"
        })
    elif i <= 60:
        brands = ["asus", "lenovo", "acer", "hp", "brother", "epson", "canon"]
        b = brands[i % len(brands)]
        dev_items.append({
            "id": idx_str,
            "pesan": f"merek {b} ada stok apa aja?",
            "state": {"pending_question": None, "produk_tampil": []},
            "label_aksi": "cari_produk",
            "label_argumen": {"merek": b},
            "label_pembaruan_state": {},
            "catatan": f"Dev variasi stok merek {b}"
        })
    elif i <= 70:
        dev_items.append({
            "id": idx_str,
            "pesan": f"buat editing video youtube {'4k' if i%2==0 else '1080p'}",
            "state": {"pending_question": "aktivitas", "produk_tampil": []},
            "label_aksi": "jawab_pertanyaan_bot",
            "label_argumen": {"slot": "aktivitas", "nilai": f"editing video youtube {'4k' if i%2==0 else '1080p'}"},
            "label_pembaruan_state": {"kebutuhan_teks": f"editing video youtube {'4k' if i%2==0 else '1080p'}"},
            "catatan": "Dev variasi aktivitas editing video"
        })
    elif i <= 80:
        dev_items.append({
            "id": idx_str,
            "pesan": f"apakah produk nomor 1 bisa ditambah ram?",
            "state": {"pending_question": None, "produk_tampil": [{"no": 1, "kode": "KB-L01"}]},
            "label_aksi": "evaluasi_kecocokan",
            "label_argumen": {"produk": ["1"], "kebutuhan_teks": "upgrade ram"},
            "label_pembaruan_state": {},
            "catatan": "Dev evaluasi upgrade RAM"
        })
    elif i <= 90:
        dev_items.append({
            "id": idx_str,
            "pesan": f"terima servis atau ganti pasta laptop?",
            "state": {"pending_question": None, "produk_tampil": []},
            "label_aksi": "tanya_info_toko",
            "label_argumen": {"topik": "servis"},
            "label_pembaruan_state": {},
            "catatan": "Dev tanya servis"
        })
    else:
        dev_items.append({
            "id": idx_str,
            "pesan": "halo permisi mau konsultasi laptop",
            "state": {"pending_question": None, "produk_tampil": []},
            "label_aksi": "sapa",
            "label_argumen": {},
            "label_pembaruan_state": {},
            "catatan": "Dev sapaan konsultasi"
        })

# 50 HELD-OUT EXAMPLES (Murni untuk evaluasi generalisasi, tidak disentuh prompt)
held_out_items = []
ho_raw = [
    ("ho-001", "assalamualaikum min", None, [], "sapa", {}, {}, "Salam religius"),
    ("ho-002", "laptop asus tuf gaming ada?", None, [], "cari_produk", {"merek": "asus", "nama_model": "tuf gaming", "kategori": "laptop"}, {"kategori": "laptop"}, "Pencarian varian tuf"),
    ("ho-003", "butuh buat kasir toko sembako", None, [], "minta_rekomendasi", {"kebutuhan_teks": "kasir toko pos", "kategori": "desktop"}, {"kebutuhan_teks": "kasir toko pos"}, "Kebutuhan kasir"),
    ("ho-004", "cuma buat zoom meeting dan skripsi aja", "aktivitas", [], "jawab_pertanyaan_bot", {"slot": "aktivitas", "nilai": "zoom meeting dan skripsi"}, {"kebutuhan_teks": "zoom meeting dan skripsi"}, "Aktivitas zoom & skripsi"),
    ("ho-005", "yang ketiga baterainya tahan berapa lama?", None, [{"no": 1, "kode": "KB-L01"}, {"no": 2, "kode": "KB-L02"}, {"no": 3, "kode": "KB-L03"}], "evaluasi_kecocokan", {"produk": ["3"], "kebutuhan_teks": "daya tahan baterai"}, {}, "Evaluasi baterai item 3"),
    ("ho-006", "antara ideapad sama vivobook bagusan mana?", None, [{"no": 1, "kode": "KB-L01", "nama": "IdeaPad Slim 3"}, {"no": 2, "kode": "KB-L02", "nama": "Vivobook 14"}], "bandingkan", {"produk": ["KB-L01", "KB-L02"]}, {}, "Bandingkan model"),
    ("ho-007", "ada yang di bawah 5 juta?", None, [{"no": 1, "kode": "KB-L01", "harga": 6500000}], "lanjutan_hasil", {"jenis": "lebih_murah"}, {}, "Lanjutan filter lebih murah"),
    ("ho-008", "bisa gosend instan hari ini?", None, [], "tanya_info_toko", {"topik": "pengiriman"}, {}, "Tanya opsi pengiriman"),
    ("ho-009", "kok ngulang salam lagi sih", None, [], "perbaiki_percakapan", {"jenis": "keluhan", "rujukan": "ngulang salam"}, {}, "Keluhan salam berulang"),
    ("ho-010", "makasih banyak infonya kak", None, [], "basa_basi", {"jenis": "terima_kasih"}, {}, "Terima kasih penutup"),
    ("ho-011", "halo selamat sore", None, [], "sapa", {}, {}, "Sapa sore"),
    ("ho-012", "printer epson l3210 ada ga?", None, [], "cari_produk", {"merek": "epson", "nama_model": "l3210", "kategori": "printer"}, {"kategori": "printer"}, "Cari printer epson"),
    ("ho-013", "laptop gaming rtx 4050 murah", None, [], "cari_produk", {"kategori": "laptop", "nama_model": "rtx 4050"}, {"kategori": "laptop"}, "Laptop rtx 4050"),
    ("ho-014", "buat anak sma belajar coding python", None, [], "minta_rekomendasi", {"kebutuhan_teks": "belajar coding python", "persona": "anak sma"}, {"kebutuhan_teks": "belajar coding python"}, "Kebutuhan coding"),
    ("ho-015", "budget maksimal 12 juta pas", "budget", [], "jawab_pertanyaan_bot", {"slot": "budget", "nilai": 12000000}, {"budget": 12000000}, "Slot budget 12jt"),
    ("ho-016", "cukup ga ram segitu buat buka 20 tab chrome?", None, [{"no": 1, "kode": "KB-L01"}], "evaluasi_kecocokan", {"produk": ["KB-L01"], "kebutuhan_teks": "20 tab chrome"}, {}, "Evaluasi tab chrome"),
    ("ho-017", "tampilin opsi yang lenovo aja dong", None, [{"no": 1, "kode": "KB-L01"}], "lanjutan_hasil", {"jenis": "filter_tambahan"}, {}, "Lanjutan filter lenovo"),
    ("ho-018", "ada garansi tukar unit baru ga kalau rusak?", None, [], "tanya_info_toko", {"topik": "garansi"}, {}, "Tanya garansi ganti unit"),
    ("ho-019", "bukan laptop gaming min maksud saya laptop tipis", None, [], "perbaiki_percakapan", {"jenis": "koreksi", "rujukan": "laptop tipis bukan gaming"}, {}, "Koreksi persona laptop tipis"),
    ("ho-020", "siap nanti saya kabari lagi ya", None, [], "basa_basi", {"jenis": "pamit"}, {}, "Basa basi pamit"),
    ("ho-021", "pagi", None, [], "sapa", {}, {}, "Sapa pagi singkat"),
    ("ho-022", "cari pc meja all in one", None, [], "cari_produk", {"kategori": "desktop", "nama_model": "all in one"}, {"kategori": "desktop"}, "Cari pc aio"),
    ("ho-023", "laptop buat arsitek autocad dan sketchup", None, [], "minta_rekomendasi", {"kebutuhan_teks": "arsitek autocad sketchup", "persona": "arsitek"}, {"kebutuhan_teks": "arsitek autocad sketchup"}, "Kebutuhan arsitek"),
    ("ho-024", "buat bapak saya nonton berita", "kebutuhan", [], "jawab_pertanyaan_bot", {"slot": "persona", "nilai": "bapak"}, {"persona": "bapak", "sebutan": "bapak"}, "Slot persona bapak"),
    ("ho-025", "yang pertama ini ssd nya berapa gb?", None, [{"no": 1, "kode": "KB-L01"}], "evaluasi_kecocokan", {"produk": ["1"], "kebutuhan_teks": "kapasitas ssd"}, {}, "Evaluasi spesifikasi ssd"),
    ("ho-026", "beda spek no 2 sama no 3 apa aja ya?", None, [{"no": 1, "kode": "KB-L01"}, {"no": 2, "kode": "KB-L02"}, {"no": 3, "kode": "KB-L03"}], "bandingkan", {"produk": ["2", "3"]}, {}, "Bandingkan 2 dan 3"),
    ("ho-027", "ada pilihan warna lain ga?", None, [{"no": 1, "kode": "KB-L01"}], "lanjutan_hasil", {"jenis": "yang_lain"}, {}, "Opsi warna lain"),
    ("ho-028", "alamat service center resminya di mana?", None, [], "tanya_info_toko", {"topik": "servis"}, {}, "Tanya alamat service center"),
    ("ho-029", "kok malah rekomendasiin yang mahal banget", None, [], "perbaiki_percakapan", {"jenis": "keluhan", "rujukan": "terlalu mahal"}, {}, "Keluhan kemahalan"),
    ("ho-030", "mantap makasih rekomendasinya", None, [], "basa_basi", {"jenis": "terima_kasih"}, {}, "Ucapan terima kasih"),
    ("ho-031", "permisi", None, [], "sapa", {}, {}, "Sapa permisi"),
    ("ho-032", "ada laptop monitor 14 inch?", None, [], "cari_produk", {"kategori": "laptop", "ukuran_layar": 14.0}, {"kategori": "laptop"}, "Cari layar 14 inch"),
    ("ho-033", "butuh laptop ringan enteng dibawa ke kampus", None, [], "minta_rekomendasi", {"kebutuhan_teks": "ringan portabel kampus", "persona": "mahasiswa"}, {"kebutuhan_teks": "ringan portabel kampus"}, "Kebutuhan portabel"),
    ("ho-034", "buat kantor administrasi input excel", "aktivitas", [], "jawab_pertanyaan_bot", {"slot": "aktivitas", "nilai": "administrasi excel"}, {"kebutuhan_teks": "administrasi excel"}, "Slot aktivitas excel"),
    ("ho-035", "apakah prosesornya i5 atau i3?", None, [{"no": 1, "kode": "KB-L01"}], "evaluasi_kecocokan", {"produk": ["KB-L01"], "kebutuhan_teks": "prosesor i3 i5"}, {}, "Evaluasi prosesor"),
    ("ho-036", "kalau dibanding macbook air m1 kencengan mana?", None, [{"no": 1, "kode": "KB-L01"}], "bandingkan", {"produk": ["KB-L01", "macbook air m1"]}, {}, "Bandingkan dengan macbook"),
    ("ho-037", "ada yang harganya 8 jutaan?", None, [{"no": 1, "kode": "KB-L01", "harga": 11000000}], "lanjutan_hasil", {"jenis": "lebih_murah"}, {}, "Lanjutan budget 8jt"),
    ("ho-038", "bisa split payment sebagian transfer sebagian cash?", None, [], "tanya_info_toko", {"topik": "pembayaran"}, {}, "Tanya pembayaran split"),
    ("ho-039", "maksud saya bukan merek itu", None, [], "perbaiki_percakapan", {"jenis": "koreksi", "rujukan": "bukan merek itu"}, {}, "Koreksi merek"),
    ("ho-040", "terima kasih banyak min", None, [], "basa_basi", {"jenis": "terima_kasih"}, {}, "Terima kasih sopan"),
    ("ho-041", "woi", None, [], "sapa", {}, {}, "Sapaan slang woi"),
    ("ho-042", "monitor 24 inch 144hz ada?", None, [], "cari_produk", {"kategori": "monitor", "ukuran_layar": 24.0}, {"kategori": "monitor"}, "Cari monitor 24 inch"),
    ("ho-043", "laptop buat ngetik tesis s2", None, [], "minta_rekomendasi", {"kebutuhan_teks": "ngetik tesis s2", "persona": "mahasiswa s2"}, {"kebutuhan_teks": "ngetik tesis s2"}, "Kebutuhan tesis"),
    ("ho-044", "budget sekitar 15 jutaan", "budget", [], "jawab_pertanyaan_bot", {"slot": "budget", "nilai": 15000000}, {"budget": 15000000}, "Slot budget 15jt"),
    ("ho-045", "apakah keyboardnya ada backlight nyala?", None, [{"no": 1, "kode": "KB-L01"}], "evaluasi_kecocokan", {"produk": ["KB-L01"], "kebutuhan_teks": "backlight keyboard"}, {}, "Evaluasi keyboard backlight"),
    ("ho-046", "tampilkan merek asus saja", None, [{"no": 1, "kode": "KB-L01"}], "lanjutan_hasil", {"jenis": "filter_tambahan"}, {}, "Lanjutan filter asus"),
    ("ho-047", "apakah bisa klaim nota untuk kantor?", None, [], "tanya_info_toko", {"topik": "pembayaran"}, {}, "Tanya nota faktur pajak"),
    ("ho-048", "lho kan tadi saya bilang budget 6 juta", None, [], "perbaiki_percakapan", {"jenis": "keluhan", "rujukan": "budget 6 juta"}, {"budget": 6000000}, "Keluhan budget diabaikan"),
    ("ho-049", "wkwkwk mantap", None, [], "basa_basi", {"jenis": "lainnya"}, {}, "Basa basi wkwkwk"),
    ("ho-050", "zzzzz", None, [], "tidak_jelas", {"alasan": "teks tidak bermakna"}, {}, "Tidak jelas zzz")
]

for hid, msg, pending, prods, act, args, st_up, note in ho_raw:
    held_out_items.append({
        "id": hid,
        "pesan": msg,
        "state": {"pending_question": pending, "produk_tampil": prods},
        "label_aksi": act,
        "label_argumen": args,
        "label_pembaruan_state": st_up,
        "catatan": note
    })

all_items = []
for item in dev_items:
    item["split"] = "dev"
    all_items.append(item)

for item in held_out_items:
    item["split"] = "held-out"
    all_items.append(item)

# 1. Tulis ke eval/parse_gold.jsonl
with open("eval/parse_gold.jsonl", "w", encoding="utf-8") as f:
    for item in all_items:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

# 2. Tulis ke eval/parse_gold.csv
csv_headers = [
    "id", "split", "pesan", "pending_question", "produk_tampil",
    "label_aksi", "label_argumen", "label_pembaruan_state", "catatan"
]

with open("eval/parse_gold.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(csv_headers)
    for it in all_items:
        st = it.get("state", {})
        writer.writerow([
            it["id"],
            it["split"],
            it["pesan"],
            st.get("pending_question") or "",
            json.dumps(st.get("produk_tampil", []), ensure_ascii=False) if st.get("produk_tampil") else "",
            it["label_aksi"],
            json.dumps(it["label_argumen"], ensure_ascii=False) if it["label_argumen"] else "",
            json.dumps(it["label_pembaruan_state"], ensure_ascii=False) if it["label_pembaruan_state"] else "",
            it.get("catatan", "")
        ])

print(f"Dataset berhasil dibuat: {len(all_items)} total ({len(dev_items)} dev, {len(held_out_items)} held-out)")
