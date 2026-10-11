# -*- coding: utf-8 -*-
"""
Katalog Data Terstruktur dan Query Engine (§15, §16)
Mendukung 10 Laptop, 5 Desktop, dan 5 Printer produk riil di Indonesia.
Memproses filter, ranking, dan resolusi nama/kode secara deterministik 100%.
"""
from __future__ import annotations

import re
from core.normalizer import normalize

# =============================================================================
# 1. KATALOG REAL (20 PRODUK RIIL: 10 LAPTOP, 5 DESKTOP, 5 PRINTER)
# =============================================================================
CATALOG_RAW_TEXT = """\
KB-L01 - Acer Aspire Lite 14
Jenis: Laptop
Harga: Rp5.199.000
Prosesor: Intel Processor N100
RAM: 8 GB DDR5
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics
Display: 14 inci WUXGA IPS
Sistem operasi: Windows 11 Home

KB-L02 - Lenovo IdeaPad Slim 3 14
Jenis: Laptop
Harga: Rp7.299.000
Prosesor: Intel Core i3-1215U
RAM: 8 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics
Display: 14 inci FHD
Sistem operasi: Windows 11 Home

KB-L03 - ASUS Vivobook 14 A1405
Jenis: Laptop
Harga: Rp8.799.000
Prosesor: Intel Core i5-1235U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel Iris Xe
Display: 14 inci WUXGA IPS
Sistem operasi: Windows 11 Home

KB-L04 - HP 14s-fq1036AU
Jenis: Laptop
Harga: Rp9.499.000
Prosesor: AMD Ryzen 5 7530U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: AMD Radeon Graphics
Display: 14 inci FHD IPS
Sistem operasi: Windows 11 Home

KB-L05 - Lenovo IdeaPad Slim 5 14
Jenis: Laptop
Harga: Rp11.499.000
Prosesor: AMD Ryzen 7 7730U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: AMD Radeon Graphics
Display: 14 inci WUXGA OLED
Sistem operasi: Windows 11 Home

KB-L06 - Acer Nitro V 15
Jenis: Laptop
Harga: Rp12.999.000
Prosesor: Intel Core i5-13420H
RAM: 16 GB DDR5
Storage: 512 GB NVMe SSD
GPU: NVIDIA GeForce RTX 2050 4 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home

KB-L07 - ASUS Vivobook Pro 15 OLED
Jenis: Laptop
Harga: Rp13.499.000
Prosesor: AMD Ryzen 7 7735HS
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 3050 6 GB
Display: 15,6 inci 2.8K OLED
Sistem operasi: Windows 11 Home

KB-L08 - Lenovo LOQ 15
Jenis: Laptop
Harga: Rp14.799.000
Prosesor: Intel Core i5-12450HX
RAM: 16 GB DDR5
Storage: 512 GB NVMe SSD
GPU: NVIDIA GeForce RTX 4050 6 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home

KB-L09 - ASUS TUF Gaming A15
Jenis: Laptop
Harga: Rp16.999.000
Prosesor: AMD Ryzen 7 7735HS
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4060 8 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home

KB-L10 - Lenovo Legion Pro 5 16
Jenis: Laptop
Harga: Rp23.999.000
Prosesor: Intel Core i7-14650HX
RAM: 32 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4070 8 GB
Display: 16 inci WQXGA 240 Hz
Sistem operasi: Windows 11 Home

KB-D01 - Lenovo IdeaCentre Mini 01
Jenis: Desktop
Harga: Rp6.999.000
Prosesor: Intel Core i3-13100T
RAM: 8 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics 730
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D02 - ASUS ExpertCenter D500 Tower
Jenis: Desktop
Harga: Rp9.899.000
Prosesor: Intel Core i5-12400
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics 730
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D03 - HP Pavilion Desktop TP01
Jenis: Desktop
Harga: Rp13.499.000
Prosesor: Intel Core i5-13400
RAM: 16 GB DDR4
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce GTX 1660 Super 6 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D04 - Lenovo LOQ Tower 17
Jenis: Desktop
Harga: Rp17.999.000
Prosesor: Intel Core i5-13400F
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4060 8 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D05 - ASUS ROG Strix G16CHR
Jenis: Desktop
Harga: Rp27.499.000
Prosesor: Intel Core i7-14700F
RAM: 32 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4070 12 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-P01 - Canon PIXMA TS207
Jenis: Printer
Harga: Rp699.000
Fungsi: Print Only
Teknologi: Inkjet Cartridge
Kecepatan: 7,7 ipm hitam / 4,0 ipm warna
Resolusi: 4800 x 1200 dpi
Konektivitas: USB 2.0

KB-P02 - Epson EcoTank L121
Jenis: Printer
Harga: Rp1.699.000
Fungsi: Print Only
Teknologi: Ink Tank
Kecepatan: 9,0 ipm hitam / 4,8 ipm warna
Resolusi: 720 x 720 dpi
Konektivitas: USB 2.0

KB-P03 - Epson EcoTank L3210
Jenis: Printer
Harga: Rp2.299.000
Fungsi: Print, Scan, Copy
Teknologi: Ink Tank
Kecepatan: 10,0 ipm hitam / 5,0 ipm warna
Resolusi: 5760 x 1440 dpi
Konektivitas: USB 2.0

KB-P04 - Canon PIXMA G3020
Jenis: Printer
Harga: Rp2.599.000
Fungsi: Print, Scan, Copy
Teknologi: Ink Tank
Kecepatan: 9,1 ipm hitam / 5,0 ipm warna
Resolusi: 4800 x 1200 dpi
Konektivitas: Wi-Fi, USB 2.0, Mobile Printing

KB-P05 - Brother DCP-T520W
Jenis: Printer
Harga: Rp2.999.000
Fungsi: Print, Scan, Copy
Teknologi: Ink Tank
Kecepatan: 17,0 ipm hitam / 9,5 ipm warna
Resolusi: 1200 x 6000 dpi
Konektivitas: Wi-Fi, USB 2.0, Mobile Printing
"""

# =============================================================================
# 2. KATALOG SINTETIS v1.2 (UNTUK KOMPATIBILITAS ACCEPTANCE TEST HISTORIS)
# =============================================================================
CATALOG_SYNTHETIC_TEXT = """\
KB-L01 — AstraBook 14 Core
Jenis: Laptop
Harga: Rp9.499.000
Prosesor: Intel Core i5-1240P
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel Iris Xe
Display: 14 inci FHD
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk kuliah, office, programming, dan web development. Kurang cocok untuk gaming berat.

KB-L02 — AstraBook 15 Pro
Jenis: Laptop
Harga: Rp11.999.000
Prosesor: Intel Core i5-13420H
RAM: 16 GB DDR5
Storage: 512 GB NVMe SSD
GPU: NVIDIA GeForce RTX 2050 4 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk programming, Android Studio, desain ringan, dan gaming menengah.

KB-L03 — NusaTech Creator 15
Jenis: Laptop
Harga: Rp13.499.000
Prosesor: AMD Ryzen 7 7840HS
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 3050 6 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk programming berat, Android Studio, Docker, editing video, dan gaming.

KB-L04 — NusaTech Student 14
Jenis: Laptop
Harga: Rp7.999.000
Prosesor: AMD Ryzen 5 7530U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: AMD Radeon Graphics
Display: 14 inci FHD
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk perkuliahan, office, web programming, dan penggunaan harian.

KB-L05 — Garuda Gaming G15
Jenis: Laptop
Harga: Rp15.999.000
Prosesor: Intel Core i7-13620H
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4060 8 GB
Display: 15,6 inci QHD 165 Hz
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk gaming berat, 3D rendering, AI development entry-level, dan editing video.

KB-D01 — Kencana Office Mini
Jenis: Desktop
Harga: Rp6.499.000
Prosesor: Intel Core i3-13100
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics 730
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk administrasi, office, kasir, browsing, dan aplikasi bisnis ringan.

KB-D02 — Kencana Workstation
Jenis: Desktop
Harga: Rp12.499.000
Prosesor: Intel Core i5-14500
RAM: 32 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 3050 6 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Pro
Penggunaan yang disarankan: Cocok untuk programming, virtual machine, data processing, editing, dan development.

KB-D03 — Rajawali Creator
Jenis: Desktop
Harga: Rp18.999.000
Prosesor: AMD Ryzen 9 7900
RAM: 32 GB DDR5
Storage: 2 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4070 12 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Pro
Penggunaan yang disarankan: Cocok untuk rendering, video editing berat, 3D, AI development, dan gaming kelas atas.

KB-M01 — Merapi Monitor 24
Jenis: Monitor
Harga: Rp1.799.000
Prosesor: Panel IPS 24 inci
RAM: -
Storage: -
GPU: -
Display: 1920 x 1080, 100 Hz
Sistem operasi: -
Penggunaan yang disarankan: Cocok untuk office, programming, multimedia, dan penggunaan harian.

KB-M02 — Merapi Monitor Pro 27
Jenis: Monitor
Harga: Rp3.299.000
Prosesor: Panel IPS 27 inci
RAM: -
Storage: -
GPU: -
Display: 2560 x 1440, 165 Hz
Sistem operasi: -
Penggunaan yang disarankan: Cocok untuk programming, desain, editing, gaming, dan multitasking.
"""

ITEM_RULES = [
    (r"^(?:kuliah|perkuliahan|mahasiswa)$", [("student", None)]),
    (r"^office$", [("office", None)]),
    (r"^(?:administrasi kantor|perkantoran|instansi bisnis)$", [("office", None)]),
    (r"^(?:umkm|umkm volume tinggi|cetak volume tinggi hemat tinta|cetak volume tinggi)$", [("office", None), ("printing", None)]),
    (r"^(?:penggunaan harian|multimedia)$", [("daily", None)]),
    (r"^(?:administrasi|kasir)$", [("admin_kasir", None)]),
    (r"^web programming$", [("web_dev", None), ("programming", "web")]),
    (r"^web development$", [("web_dev", None)]),
    (r"^programming(?: (?P<q>.+))?$", [("programming", "$q")]),
    (r"^android studio$", [("android_studio", None)]),
    (r"^docker$", [("docker", None)]),
    (r"^virtual machine$", [("vm", None)]),
    (r"^data processing$", [("data_processing", None)]),
    (r"^(?:editing video|video editing|editing)(?: (?P<q>.+))?$", [("video_editing", "$q")]),
    (r"^desain(?: (?P<q>.+))?$", [("design", "$q")]),
    (r"^gaming(?: (?P<q>.+))?$", [("gaming", "$q")]),
    (r"^(?:3d rendering|rendering|3d)$", [("rendering_3d", None)]),
    (r"^ai development(?: (?P<q>.+))?$", [("ai_dev", "$q")]),
    (r"^(?:cetak tugas sekolah|tugas sekolah|cetak tugas)$", [("student", None), ("printing", None)]),
    (r"^(?:cetak dokumen harian|cetak dokumen|penggunaan rumahan ringan)$", [("daily", None), ("printing", None)]),
    (r"^(?:cetak dokumen kasir)$", [("admin_kasir", None), ("printing", None)]),
    (r"^(?:fotokopi dokumen|fotokopi berkas|scan berkas|scan|copy)$", [("scan_copy", None)]),
    (r"^(?:cetak foto warna|cetak foto)$", [("design", None), ("printing", None)]),
    (r"^(?:cetak cepat nirkabel|cetak nirkabel smartphone)$", [("printing", None)]),
]

def derive_tags(usage_text: str) -> list[dict]:
    """Menurunkan tag kebutuhan dari teks penggunaan yang disarankan (§16, §22)."""
    tags: list[dict] = []
    seen = set()
    for sentence in re.split(r"\.\s+|\.$", usage_text or ""):
        sent = sentence.strip().lower()
        if not sent:
            continue
        m = re.match(r"^(kurang cocok|tidak cocok|cocok) untuk (.+)$", sent)
        if not m:
            continue
        negated = m.group(1) != "cocok"
        for item in re.split(r",|\bdan\b", m.group(2)):
            item = item.strip(" .")
            if not item:
                continue
            for pattern, tag_specs in ITEM_RULES:
                mm = re.match(pattern, item)
                if not mm:
                    continue
                q = mm.groupdict().get("q") if mm.groupdict() else None
                for tag, qual in tag_specs:
                    qualifier = q if qual == "$q" else qual
                    key = (tag, negated)
                    if key in seen:
                        continue
                    seen.add(key)
                    entry = {"tag": tag, "phrase": item}
                    if qualifier:
                        entry["qualifier"] = qualifier
                    if negated:
                        entry["negated"] = True
                    tags.append(entry)
                break
    return tags

def infer_tags_from_specs(rec: dict) -> list[dict]:
    """
    Inferensi tag kebutuhan secara cerdas dari spesifikasi hardware riil (§16).
    Digunakan ketika katalog tidak memiliki baris artifisial 'Penggunaan yang disarankan'.
    """
    tags: list[dict] = []
    seen = set()

    def add(tag: str, phrase: str, qualifier: str | None = None, negated: bool = False):
        key = (tag, negated)
        if key not in seen:
            seen.add(key)
            entry = {"tag": tag, "phrase": phrase}
            if qualifier:
                entry["qualifier"] = qualifier
            if negated:
                entry["negated"] = True
            tags.append(entry)

    cat = rec.get("kategori", "")
    h_raw = rec.get("harga_idr")
    harga = int(h_raw) if h_raw is not None and str(h_raw).strip().isdigit() else (int(h_raw) if isinstance(h_raw, (int, float)) else 0)

    # 1. PRINTER
    if cat == "printer":
        fungsi = (rec.get("fungsi") or "").lower()
        koneksi = (rec.get("konektivitas") or "").lower()
        res = (rec.get("resolusi") or "").lower()
        
        # Semua printer dapat mencetak dokumen
        add("printing", "cetak dokumen")
        
        # Multifungsi: scan dan fotokopi
        if "scan" in fungsi or "copy" in fungsi:
            add("scan_copy", "scan dan fotokopi")
            
        # Entry-level / Murah -> Pelajar / Harian
        if harga <= 1_000_000:
            add("student", "cetak tugas sekolah")
            add("daily", "penggunaan harian")
        else:
            # Ink Tank / Volume tinggi -> Kantor, UMKM, Kasir
            add("office", "administrasi kantor")
            add("daily", "penggunaan harian")
            add("admin_kasir", "cetak dokumen kasir")
            
        if harga <= 2_500_000:
            add("student", "cetak berkas kuliah")
            
        # Wi-Fi / Cetak nirkabel / Foto
        if "wi-fi" in koneksi or "wireless" in koneksi or "mobile" in koneksi:
            add("student", "cetak berkas kuliah")
            if any(dpi in res for dpi in ("4800", "5760", "6000")):
                add("design", "cetak foto warna")
                
        return tags

    cpu = (rec.get("cpu") or "").lower()
    gpu = (rec.get("gpu") or "").lower()
    ram_gb_raw = rec.get("ram_gb")
    ram_gb = int(ram_gb_raw) if ram_gb_raw is not None and str(ram_gb_raw).strip().isdigit() else (int(ram_gb_raw) if isinstance(ram_gb_raw, (int, float)) else 0)
    display = (rec.get("display") or "").lower()
    gpu_type = rec.get("gpu_type") or ("discrete" if any(x in gpu for x in ("geforce", "rtx", "gtx", "radeon rx", "arc")) else "integrated")
    gpu_vram_raw = rec.get("gpu_vram")
    gpu_vram = int(gpu_vram_raw) if gpu_vram_raw is not None and str(gpu_vram_raw).strip().isdigit() else None

    # Identifikasi level GPU
    has_rtx_high = any(x in gpu for x in ("rtx 4070", "rtx 4080", "rtx 4090"))
    has_rtx_mid_high = any(x in gpu for x in ("rtx 4060", "rtx 3060", "rtx 3070"))
    has_rtx_entry_mid = any(x in gpu for x in ("rtx 4050", "rtx 3050"))
    has_discrete_entry = any(x in gpu for x in ("rtx 2050", "gtx 1660", "gtx 1650"))
    is_integrated_gpu = (gpu_type == "integrated") or not (has_rtx_high or has_rtx_mid_high or has_rtx_entry_mid or has_discrete_entry)

    # Identifikasi level CPU
    is_cpu_budget = any(x in cpu for x in ("n100", "celeron", "pentium", "i3", "ryzen 3"))
    is_cpu_high_tdp = any(x in cpu for x in ("13420h", "7735hs", "12450hx", "14650hx", "14700f", "13400f", "13400"))
    is_cpu_top = any(x in cpu for x in ("14650hx", "14700", "14700f", "i9", "ryzen 9"))
    cpu_tier = 3 if is_cpu_top else 2 if is_cpu_high_tdp else 1 if not is_cpu_budget else 0

    # PERTIMBANGAN GPU UNTUK BEBAN KERJA:
    # A. WORKLOAD GRAFIS BERAT & TEKNIK: 3D Rendering, Arsitektur, CAD, Insinyur, Simulasi, Konstruksi
    # -> Wajib kartu grafis dedicated!
    if has_rtx_high:
        add("rendering_3d", "3D rendering")
        add("architecture_cad", "software arsitektur & perhitungan konstruksi")
        add("gaming", "gaming berat", qualifier="kelas atas")
        add("ai_dev", "AI development")
        add("video_editing", "editing video", qualifier="berat")
        add("design", "desain grafis")
    elif has_rtx_mid_high:
        add("rendering_3d", "3D rendering")
        add("architecture_cad", "software arsitektur & perhitungan konstruksi")
        add("gaming", "gaming berat", qualifier="berat")
        add("ai_dev", "AI development entry-level", qualifier="entry-level")
        add("video_editing", "editing video")
        add("design", "desain grafis")
    elif has_rtx_entry_mid:
        add("rendering_3d", "3D rendering")
        add("architecture_cad", "software arsitektur & perhitungan konstruksi")
        add("gaming", "gaming berat", qualifier="berat")
        add("video_editing", "editing video")
        add("design", "desain grafis")
        add("android_studio", "Android Studio")
    elif has_discrete_entry:
        add("rendering_3d", "3D rendering & komputasi visual", qualifier="entry-level")
        add("architecture_cad", "software arsitektur & perhitungan teknik entry-level")
        add("gaming", "gaming menengah", qualifier="menengah")
        add("design", "desain ringan", qualifier="ringan")
        add("video_editing", "editing video")
        add("android_studio", "Android Studio")

    if is_integrated_gpu:
        # GPU terintegrasi secara teknis tidak cocok untuk 3D rendering, gaming berat, AI development, dan arsitektur/konstruksi berat
        add("gaming", "gaming berat", negated=True)
        add("rendering_3d", "3D rendering", negated=True)
        add("architecture_cad", "software arsitektur & konstruksi berat", negated=True)
        add("ai_dev", "AI development", negated=True)

    # B. LAYAR OLED / RESOLUSI TINGGI -> Desain Grafis
    if "oled" in display or "2.8k" in display or "wqxga" in display or "100% srgb" in display:
        add("design", "desain grafis")

    # C. PEMROGRAMAN, ANDROID STUDIO, DOCKER, VM
    if ram_gb >= 32 or is_cpu_top:
        add("programming", "programming")
        add("vm", "virtual machine")
        add("ai_dev", "AI development")
        add("rendering_3d", "3D rendering")
    elif ram_gb >= 16:
        add("programming", "programming")
        add("web_dev", "web development")
        add("data_processing", "olah data")
        if is_cpu_high_tdp:
            add("android_studio", "Android Studio")
            if has_discrete_entry or has_rtx_entry_mid:
                add("docker", "Docker")

    # D. KANTOR, KULIAH, KASIR, DAN HARIAN
    if ram_gb <= 16:
        add("office", "office")
        add("student", "kuliah")
        add("daily", "penggunaan harian")
        if is_cpu_budget or is_integrated_gpu:
            add("admin_kasir", "kasir")
    elif ram_gb > 16:
        add("daily", "penggunaan harian")

    return tags

def parse_product_text(text: str) -> dict | None:
    text = (text or "").replace("\r", "")
    code_m = re.search(r"\bKB-[A-Z]\d+\b", text)
    if not code_m:
        return None
    code = code_m.group(0)
    fields = {}
    for line in text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fields.setdefault(k.strip().lower(), v.strip())
            
    name = None
    hm = re.search(rf"{re.escape(code)}\s*[—–\-:?]+\s*(.+)", text)
    if hm:
        name = hm.group(1).strip()
    name = name or fields.get("nama")
    if not name:
        return None
        
    jenis = (fields.get("jenis") or "").lower()
    if jenis not in ("laptop", "desktop", "monitor", "printer"):
        low = text.lower()
        jenis = next((k for k in ("laptop", "desktop", "monitor", "printer") if k in low), "")
    if not jenis:
        return None
        
    price = None
    if fields.get("harga"):
        digits = re.sub(r"\D", "", fields["harga"])
        price = int(digits) if digits else None
    if price is None:
        return None
        
    um = re.search(r"penggunaan yang disarankan:\s*(.+?)(?=\n\s*KB-[A-Z]\d|\Z)", text, re.I | re.S)
    usage = re.sub(r"\s+", " ", um.group(1)).strip() if um else ""
    
    def clean_val(v):
        if not v:
            return None
        s = v.strip()
        return None if s in ("", "-", "—") else s
        
    cpu = clean_val(fields.get("prosesor")) if jenis not in ("monitor", "printer") else None
    panel = clean_val(fields.get("prosesor")) if jenis == "monitor" else None
    ram_raw = clean_val(fields.get("ram")) if jenis not in ("monitor", "printer") else None
    ram_gb = ram_type = None
    if ram_raw:
        rm = re.search(r"(\d+)\s*GB\s*(DDR\d)?", ram_raw, re.I)
        if rm:
            ram_gb = int(rm.group(1))
            ram_type = (rm.group(2) or "").upper() or None
            
    display = clean_val(fields.get("display")) if jenis != "printer" else None
    vendor = None
    if cpu:
        low = cpu.lower()
        vendor = "intel" if "intel" in low else "amd" if ("amd" in low or "ryzen" in low) else None
        
        # Gunakan regex sama dengan migrate_derived_fields.py agar konsisten dengan database
        def _parse_cpu_tier(s: str) -> int:
            m = re.search(r"core\s+ultra\s+([579])", s)
            if m:
                return {"5": 2, "7": 3, "9": 4}[m.group(1)]
            m = re.search(r"core\s+i([3579])", s)
            if m:
                return {"3": 1, "5": 2, "7": 3, "9": 4}[m.group(1)]
            m = re.search(r"core\s+([579])\s+\d", s)
            if m:
                return {"5": 2, "7": 3, "9": 4}[m.group(1)]
            m = re.search(r"ryzen\s+(?:ai\s+)?([3579])", s)
            if m:
                return {"3": 1, "5": 2, "7": 3, "9": 4}[m.group(1)]
            if re.search(r"\bn\d{2,3}\b|celeron|pentium|athlon", s):
                return 1
            if "apple" in s or re.search(r"\bm[1-9]\b", s):
                if re.search(r"\bmax\b", s):
                    return 4
                elif re.search(r"\bpro\b", s):
                    return 3
                elif re.search(r"\bultra\b", s):
                    return 1
                elif re.search(r"\bm[1-9]\b", s):
                    return 2
            return 1  # default ke tier 1 jika tidak dikenali
        cpu_tier = _parse_cpu_tier(low)

    # Khusus GPU (Identifikasi discrete vs integrated dan VRAM)
    gpu = clean_val(fields.get("gpu")) if jenis not in ("monitor", "printer") else None
    gpu_type = None
    gpu_vram = None
    if gpu:
        low_g = gpu.lower()
        if any(x in low_g for x in ("geforce", "rtx", "gtx", "radeon rx", "arc")):
            gpu_type = "discrete"
        elif any(x in low_g for x in ("intel uhd", "iris xe", "radeon graphics", "integrated", "intel graphics")):
            gpu_type = "integrated"
        else:
            gpu_type = "discrete" if "gb" in low_g else "integrated"
            
        vm = re.search(r"(\d+)\s*GB", gpu, re.I)
        if vm:
            gpu_vram = int(vm.group(1))

    # Khusus printer
    fungsi = clean_val(fields.get("fungsi")) if jenis == "printer" else None
    teknologi = clean_val(fields.get("teknologi")) if jenis == "printer" else None
    kecepatan = (clean_val(fields.get("kecepatan")) or clean_val(fields.get("kecepatan cetak"))) if jenis == "printer" else None
    resolusi = clean_val(fields.get("resolusi")) if jenis == "printer" else None
    konektivitas = clean_val(fields.get("konektivitas")) if jenis == "printer" else None

    rec = {
        "kode": code,
        "nama": name,
        "kategori": jenis,
        "is_accessory": jenis == "monitor",
        "harga_idr": price,
        "cpu": cpu,
        "cpu_vendor": vendor,
        "ram_gb": ram_gb,
        "ram_type": ram_type,
        "storage": clean_val(fields.get("storage")) if jenis != "printer" else None,
        "storage_ssd_gb": int(re.search(r"(\d+)\s*(GB|TB)", clean_val(fields.get("storage")) or "").group(1)) * (1024 if re.search(r"(\d+)\s*(GB|TB)", clean_val(fields.get("storage")) or "").group(2).upper() == "TB" else 1) if re.search(r"(\d+)\s*(GB|TB)", clean_val(fields.get("storage")) or "", re.I) else None,
        "gpu": gpu,
        "gpu_type": gpu_type,
        "gpu_dedicated": 1 if gpu_type == "discrete" else 0,
        "gpu_vram": gpu_vram,
        "vram_gb": gpu_vram,
        "cpu_tier": cpu_tier if cpu else None,
        "display": display,
        "os": clean_val(fields.get("sistem operasi")) if jenis != "printer" else None,
        "panel": panel,
        "includes_monitor": False if jenis == "desktop" else None,
        "fungsi": fungsi,
        "teknologi": teknologi,
        "kecepatan": kecepatan,
        "resolusi": resolusi,
        "konektivitas": konektivitas,
        "usage_text": usage,
        "text": text.strip()
    }
    rec["need_tags"] = derive_tags(usage) if usage else infer_tags_from_specs(rec)
    return rec

def has_tag(p: dict, tag: str) -> bool:
    return any(t["tag"] == tag and not t.get("negated") for t in p["need_tags"])

def tag_entries(p: dict, tags: list[str] | tuple[str, ...]) -> list[dict]:
    return [t for t in p["need_tags"] if t["tag"] in tags and not t.get("negated")]

GENERIC_ALIAS_TOKENS = {
    "pro", "core", "mini", "office", "gaming", "student", "creator", "monitor", "laptop", "desktop", "printer", "tower",
    "acer", "asus", "lenovo", "hp", "canon", "epson", "brother"
}

class Catalog:
    def __init__(self, records: list[dict]):
        self.products = sorted(records, key=lambda r: r["kode"])
        self.by_code = {p["kode"]: p for p in self.products}
        self.prices = {p["harga_idr"] for p in self.products}
        self._build_aliases()

    def get_by_code(self, code: str) -> dict | None:
        if not code:
            return None
        c_str = str(code).strip()
        return self.by_code.get(c_str.upper()) or self.by_code.get(c_str)

    @classmethod
    def from_qdrant(cls, url: str = "http://localhost:6333", collection: str = "computer_knowledge") -> Catalog:
        import requests
        records: dict[str, dict] = {}
        offset = None
        while True:
            body = {"limit": 100, "with_payload": True, "with_vector": False}
            if offset is not None:
                body["offset"] = offset
            r = requests.post(f"{url}/collections/{collection}/points/scroll", json=body, timeout=30)
            r.raise_for_status()
            res = r.json()["result"]
            for pt in res["points"]:
                payload = pt.get("payload") or {}
                rec = payload.get("record")
                if not rec and payload.get("text"):
                    rec = parse_product_text(payload.get("text", ""))
                if rec and rec.get("kode"):
                    usage = rec.get("usage_text", "")
                    if not rec.get("need_tags"):
                        rec["need_tags"] = derive_tags(usage) if usage else infer_tags_from_specs(rec)
                    records[rec["kode"]] = rec
            offset = res.get("next_page_offset")
            if offset is None:
                break
        if not records:
            raise RuntimeError(f"Koleksi '{collection}' di Qdrant tidak berisi produk yang valid.")
        return cls(list(records.values()))

    @classmethod
    def from_dummy(cls) -> Catalog:
        records = []
        for block in re.split(r"(?m)^(?=KB-[A-Z]\d+\s*[-—–:])", CATALOG_RAW_TEXT.replace("\r", "")):
            rec = parse_product_text(block)
            if rec:
                records.append(rec)
        return cls(records)

    @classmethod
    def from_synthetic_v1_2(cls) -> Catalog:
        records = []
        for block in re.split(r"(?m)^(?=KB-[A-Z]\d+\s*[-—–:])", CATALOG_SYNTHETIC_TEXT.replace("\r", "")):
            rec = parse_product_text(block)
            if rec:
                records.append(rec)
        return cls(records)

    @classmethod
    def from_db(cls, db_path: str | None = None) -> Catalog:
        if db_path is None:
            import os
            db_path = os.getenv("DB_PATH", "data/catalog.db")
        from core.db import get_all_products
        records = get_all_products(db_path=db_path)
        if not records:
            # Seed from dummy / synthetic if empty
            dummy_cat = cls.from_synthetic_v1_2()
            from core.db import seed_db_from_catalog
            seed_db_from_catalog(dummy_cat.products, db_path=db_path)
            records = get_all_products(db_path=db_path)
        return cls(records)

    @classmethod
    def load(cls, source: str = "qdrant", url: str = "http://localhost:6333", collection: str = "computer_knowledge") -> Catalog:
        if source == "db":
            return cls.from_db()
        if source == "qdrant":
            try:
                return cls.from_qdrant(url, collection)
            except Exception as e:
                # Fallback ke DB lokal jika Qdrant offline
                try:
                    return cls.from_db()
                except Exception:
                    pass
        return cls.from_dummy()

    def _build_aliases(self):
        idx: dict[tuple, set] = {}
        for p in self.products:
            name_toks = normalize(p["nama"]).split()
            for n in range(1, len(name_toks) + 1):
                for i in range(len(name_toks) - n + 1):
                    sub = tuple(name_toks[i:i + n])
                    if n == 1 and (sub[0] in GENERIC_ALIAS_TOKENS or sub[0].isdigit()):
                        continue
                    idx.setdefault(sub, set()).add(p["kode"])
            low = p["kode"].lower()
            idx.setdefault(tuple(normalize(low).split()), set()).add(p["kode"])
            idx.setdefault((low.replace("-", ""),), set()).add(p["kode"])
        self.alias_list = list(idx.items())

    def find_named(self, norm_text: str) -> tuple[list[str], str]:
        toks = norm_text.split()
        spans = []
        for alias, codes in self.alias_list:
            n = len(alias)
            for i in range(len(toks) - n + 1):
                if tuple(toks[i:i + n]) == alias:
                    spans.append((i, i + n, codes))
        keep = [sp for sp in spans
                if not any(o[0] <= sp[0] and sp[1] <= o[1] and (o[1] - o[0]) > (sp[1] - sp[0])
                           for o in spans)]
        keep.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        codes_out: list[str] = []
        masked = toks[:]
        for a, b, cs in keep:
            for c in sorted(cs):
                if c not in codes_out:
                    codes_out.append(c)
            for k in range(a, b):
                masked[k] = ""
            masked[a] = "xprodukx"
        return codes_out, " ".join(t for t in masked if t)

    def pool(self, category: str | None) -> list[dict]:
        if category in ("laptop", "desktop", "printer", "monitor"):
            return [p for p in self.products if p["kategori"] == category]
        return [p for p in self.products if not p["is_accessory"]]

    def printers(self) -> list[dict]:
        return [p for p in self.products if p["kategori"] == "printer"]

    def monitors(self) -> list[dict]:
        return [p for p in self.products if p["kategori"] == "monitor"]
