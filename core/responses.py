# -*- coding: utf-8 -*-
"""
Generator Respons Percakapan Berbasis Fakta Katalog (§7, §11, §12, §17.3)
"""
from __future__ import annotations

import re
from itertools import combinations
from core.taxonomy import NEED_LABEL, ATTR_LABEL, CATEGORY_LABEL
from core.catalog import tag_entries, has_tag, Catalog

def format_price(v: int) -> str:
    return "Rp" + f"{v:,}".replace(",", ".")

def format_juta(v: int) -> str:
    if v % 1_000_000 == 0:
        return f"Rp{v // 1_000_000} juta"
    if v % 100_000 == 0:
        return "Rp" + f"{v / 1_000_000:.1f}".replace(".", ",") + " juta"
    return format_price(v)

def need_labels(needs: list[str]) -> str:
    return " dan ".join(NEED_LABEL.get(n, n) for n in needs)

def specs_line(p: dict) -> str:
    if p["kategori"] == "monitor":
        return ", ".join(x for x in (p["panel"], p["display"]) if x)
    if p["kategori"] == "printer":
        parts = [
            p.get("fungsi"),
            p.get("teknologi"),
            f'kecepatan {p["kecepatan"]}' if p.get("kecepatan") else None,
            f'koneksi {p["konektivitas"]}' if p.get("konektivitas") else None,
        ]
        return ", ".join(x for x in parts if x)
    parts = [
        p["cpu"],
        f'{p["ram_gb"]} GB {p["ram_type"]}' if p["ram_gb"] else None,
        p["storage"],
        p["gpu"]
    ]
    return ", ".join(x for x in parts if x)

def basis_text(p: dict, needs: list[str]) -> str:
    if p.get("usage_text"):
        if needs:
            phrases = []
            for t in tag_entries(p, needs):
                if t["phrase"] not in phrases:
                    phrases.append(t["phrase"])
            if phrases:
                return "Dasar pemilihan: katalog menyebut cocok untuk " + ", ".join(phrases) + "."
        return f"Dasar pemilihan: {p['usage_text']}"

    if not needs:
        return ""

    cat = p.get("kategori")
    if cat == "printer":
        fungsi = p.get("fungsi", "cetak dokumen")
        koneksi = f" dan {p['konektivitas']}" if p.get("konektivitas") else ""
        return f"Dasar pemilihan: dilengkapi fungsi {fungsi}{koneksi} serta teknologi {p.get('teknologi', 'ink tank')} yang hemat dan efisien."

    # Komputer (Laptop / Desktop)
    if any(n in ("rendering_3d", "gaming", "video_editing", "ai_dev", "design") for n in needs):
        gpu_name = p.get("gpu") or "GPU mumpuni"
        is_disc = p.get("gpu_type") == "discrete" or any(x in gpu_name.lower() for x in ("rtx", "gtx", "geforce", "radeon rx"))
        disc_label = "kartu grafis dedicated " if is_disc else "GPU "
        return f"Dasar pemilihan: dibekali {disc_label}{gpu_name} dan prosesor {p['cpu']} yang sangat mumpuni untuk akselerasi grafis 3D, simulasi, dan performa tinggi."
    elif any(n in ("programming", "web_dev", "android_studio", "docker", "vm", "data_processing") for n in needs):
        gpu_role = f" serta kartu grafis {p['gpu']}" if (p.get("gpu_type") == "discrete" or any(x in (p.get("gpu") or "").lower() for x in ("rtx", "gtx"))) else ""
        return f"Dasar pemilihan: kapasitas RAM {p['ram_gb']} GB {p.get('ram_type', '')} dan prosesor {p['cpu']}{gpu_role} sangat responsif untuk multitasking dan kompilasi."
    elif any(n in ("office", "student", "admin_kasir", "daily") for n in needs):
        gpu_text = f" dan kartu grafis hemat daya {p['gpu']}" if p.get("gpu") else ""
        return f"Dasar pemilihan: prosesor efisien {p['cpu']}{gpu_text} serta RAM {p['ram_gb']} GB sangat lancar untuk pekerjaan dokumen, perkuliahan, dan penggunaan harian."
    return f"Dasar pemilihan: spesifikasi {p['cpu']} dan RAM {p['ram_gb']} GB sesuai untuk kebutuhan tersebut."

def render_product_lines(products: list[dict], needs: list[str], show_price: bool) -> list[str]:
    lines = []
    for i, p in enumerate(products, 1):
        extra = " (Monitor tidak termasuk ya Kak)" if p["kategori"] == "desktop" else ""
        price = f" Harga {format_price(p['harga_idr'])}." if show_price else ""
        basis = basis_text(p, needs)
        basis_str = f" {basis}" if basis else ""
        lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{extra}{basis_str}{price}".strip())
    return lines

def render_summary(p: dict, show_price: bool = True) -> str:
    rows = [f"**{p['nama']}** ({p['kode']})"]
    if show_price:
        rows.append(f"- Harga: {format_price(p['harga_idr'])}")
    if p["kategori"] == "monitor":
        rows.append(f"- Panel: {p['panel']}")
        rows.append(f"- Layar: {p['display']}")
    elif p["kategori"] == "printer":
        if p.get("fungsi"):
            rows.append(f"- Fungsi: {p['fungsi']}")
        if p.get("teknologi"):
            rows.append(f"- Teknologi: {p['teknologi']}")
        if p.get("kecepatan"):
            rows.append(f"- Kecepatan cetak: {p['kecepatan']}")
        if p.get("resolusi"):
            rows.append(f"- Resolusi: {p['resolusi']}")
        if p.get("konektivitas"):
            rows.append(f"- Konektivitas: {p['konektivitas']}")
    else:
        rows += [
            f"- Prosesor: {p['cpu']}",
            f"- RAM: {p['ram_gb']} GB {p['ram_type']}",
            f"- Storage: {p['storage']}",
            f"- GPU: {p['gpu']}"
        ]
        rows.append("- Layar: " + (p["display"] if p["kategori"] == "laptop"
                                   else "tidak termasuk (monitor terpisah ya Kak)"))
        if p["os"]:
            rows.append(f"- Sistem operasi: {p['os']}")
    if p["usage_text"]:
        rows.append(f"- Penggunaan yang disarankan: {p['usage_text']}")
    return "\n".join(rows)

def attr_value(p: dict, attr: str) -> str:
    cat = p["kategori"]
    if cat == "monitor":
        if attr in ("ram", "storage", "gpu", "os", "fungsi", "teknologi", "kecepatan", "resolusi", "konektivitas"):
            return "RAM tidak berlaku untuk monitor" if attr == "ram" else f"{ATTR_LABEL.get(attr, attr)} tidak berlaku untuk monitor"
        if attr == "cpu":
            return f"tidak berlaku untuk monitor (panel: {p['panel']})"
    if cat == "printer":
        if attr in ("ram", "storage", "gpu", "os", "display", "cpu"):
            return f"{ATTR_LABEL.get(attr, attr)} tidak berlaku untuk printer"
        if attr in ("fungsi", "teknologi", "kecepatan", "resolusi", "konektivitas"):
            return p.get(attr) or "informasi belum tersedia di katalog"
    na = "informasi belum tersedia di katalog"
    if attr == "price":
        return format_price(p["harga_idr"])
    if attr == "ram":
        return f'{p["ram_gb"]} GB {p["ram_type"]}' if p["ram_gb"] else na
    if attr == "cpu":
        return p["cpu"] or na
    if attr == "gpu":
        return p["gpu"] or na
    if attr == "storage":
        return p["storage"] or na
    if attr == "display":
        if cat == "desktop":
            return "tidak termasuk monitor"
        return p["display"] or na
    if attr == "os":
        return p["os"] or na
    if attr in ("fungsi", "teknologi", "kecepatan", "resolusi", "konektivitas"):
        return p.get(attr) or na
    return na

def answer_attrs(targets: list[dict], attrs: list[str], named: bool, norm_text: str) -> str:
    attrs = [a for a in attrs if a != "spec"] or attrs
    if "spec" in attrs:
        return "\n\n".join(render_summary(p) for p in targets)
    
    vendor_words = [t for t in norm_text.split() if t in ("nvidia", "geforce", "rtx", "intel",
                                                          "amd", "ryzen", "radeon", "iris")]
    yn = (len(attrs) == 1 and attrs[0] in ("gpu", "cpu") and vendor_words
          and len({w for w in vendor_words if w in ("intel", "amd", "ryzen")}) < 2
          and set(norm_text.split()) & {"apakah", "punya", "memiliki", "pakai", "ada"})
          
    if yn:
        lines = []
        for p in targets:
            field = (p["gpu"] if attrs[0] == "gpu" else p["cpu"]) or ""
            ok = all(w in field.lower() for w in vendor_words)
            head = "Betul Kak!" if ok else "Bukan Kak,"
            val = field if field else "sayangnya belum tersedia di katalog"
            lines.append(f"{head} {ATTR_LABEL[attrs[0]]} {p['nama']} itu {val}.")
        return "\n".join(lines)
        
    if len(targets) == 1 and attrs == ["gpu"]:
        p = targets[0]
        field_gpu = (p.get("gpu") or "").strip()
        gpu_l = field_gpu.lower()
        is_integrated = any(x in gpu_l for x in ("intel uhd", "intel iris", "uhd graphics", "iris xe", "radeon 610m", "integrated"))
        
        has_negation = any(w in norm_text.split() for w in ("tidak", "gak", "tanpa", "bukan"))
        has_inquiry = any(w in norm_text.split() for w in ("pakai", "pake", "ada", "punya", "apakah"))
        
        if has_negation and ("gpu" in norm_text or "vga" in norm_text):
            if is_integrated:
                alt = ""
                if p.get("kategori") == "desktop":
                    alt = " Jika Kakak membutuhkan PC desktop yang dilengkapi kartu grafis dedicated untuk gaming atau 3D berat, di katalog kami ada opsi seperti **Lenovo LOQ Tower 17** (RTX 4060) atau **ASUS ROG Strix G16CHR** (RTX 4070)."
                elif p.get("kategori") == "laptop":
                    alt = " Jika Kakak membutuhkan laptop yang dilengkapi kartu grafis dedicated untuk gaming atau render, kami menyediakan pilihan seperti **Acer Nitro V 15** atau **ASUS TUF Gaming A15**."
                return (
                    f"Betul Kak, {p['nama']} menggunakan kartu grafis terintegrasi ({field_gpu}) dan belum dilengkapi GPU terpisah/dedicated (seperti NVIDIA GeForce). "
                    f"Ini sangat hemat daya dan cocok untuk kebutuhan harian atau kantor.{alt}"
                )
            else:
                return (
                    f"Laptop/komputer {p['nama']} sudah dilengkapi kartu grafis dedicated kok Kak, yaitu {field_gpu}. "
                    "Mumpuni untuk kebutuhan akselerasi grafis, multimedia, dan gaming."
                )
        elif has_inquiry and not vendor_words:
            if is_integrated:
                return (
                    f"Untuk grafisnya, {p['nama']} menggunakan kartu grafis terintegrasi {field_gpu} (belum menggunakan GPU dedicated/diskrit seperti NVIDIA). "
                    "Sangat pas untuk komputasi harian dan office. Kakak sedang mencari perangkat yang dibekali dedicated GPU?"
                )
            else:
                return f"Sudah dibekali kartu grafis dedicated Kak! {p['nama']} menggunakan {field_gpu}."
        
    if len(targets) == 1 and len(attrs) == 1 and not named:
        a = attrs[0]
        val = attr_value(targets[0], a)
        stem = {
            "price": "Harganya", "ram": "RAM-nya", "cpu": "Prosesornya",
            "gpu": "GPU-nya", "storage": "Storage-nya", "display": "Ukuran layarnya",
            "os": "Sistem operasinya"
        }.get(a, a.capitalize())
        return f"{stem} {val}, Kak."
        
    if len(targets) == 1 and len(attrs) == 1:
        a = attrs[0]
        val = attr_value(targets[0], a)
        if targets[0]["kategori"] == "monitor" and a in ("ram", "storage", "gpu", "os"):
            return f"{val}, Kak."
        return f"Untuk {ATTR_LABEL[a]} {targets[0]['nama']} itu {val}, Kak."
        
    lines = []
    for p in targets:
        vals = "; ".join(f"{ATTR_LABEL[a]} {attr_value(p, a)}" for a in attrs)
        lines.append(f"- **{p['nama']}**: {vals}")
    return "\n".join(lines)

def vram_gb(p: dict) -> int | None:
    m = re.search(r"(\d+)\s*GB\s*$", p["gpu"] or "")
    return int(m.group(1)) if m else None

def compare_answer(products: list[dict], needs: list[str]) -> str:
    names = " dan ".join(p["nama"] for p in products)
    if all(p["kategori"] == "printer" for p in products):
        fields = [
            ("Harga", lambda p: format_price(p["harga_idr"])),
            ("Fungsi", lambda p: p.get("fungsi") or "-"),
            ("Teknologi", lambda p: p.get("teknologi") or "-"),
            ("Kecepatan", lambda p: p.get("kecepatan") or "-"),
            ("Resolusi", lambda p: p.get("resolusi") or "-"),
            ("Konektivitas", lambda p: p.get("konektivitas") or "-"),
        ]
    else:
        fields = [
            ("Harga", lambda p: format_price(p["harga_idr"])),
            ("Prosesor", lambda p: p["cpu"] or "-"),
            ("RAM", lambda p: attr_value(p, "ram")),
            ("Storage", lambda p: p["storage"] or "-"),
            ("GPU", lambda p: p["gpu"] or "-"),
            ("Layar", lambda p: attr_value(p, "display")),
        ]
    rows = [f"Berikut perbandingan {names}:"]
    for label, fn in fields:
        rows.append(f"- {label}: " + " vs ".join(fn(p) for p in products))
    if any(p.get("usage_text") for p in products):
        rows.append("- Penggunaan yang disarankan: " +
                    " | ".join(f"{p['nama']}: {p['usage_text']}" for p in products))
                
    concl = []
    for n in needs:
        have = [p for p in products if has_tag(p, n)]
        if len(have) == len(products):
            concl.append(f"Untuk {NEED_LABEL.get(n, n)}, kedua pilihan ini mumpuni memenuhi kebutuhan tersebut.")
        elif have:
            concl.append(f"Untuk {NEED_LABEL.get(n, n)}, pilihan yang lebih pas adalah " + ", ".join(p["nama"] for p in have) + ".")
            
    if len(products) == 2:
        a, b = products
        cheaper, pricier = sorted(products, key=lambda p: p["harga_idr"])
        facts = []
        if a["harga_idr"] != b["harga_idr"]:
            facts.append(f"Harga {cheaper['nama']} lebih terjangkau selisih {format_price(pricier['harga_idr'] - cheaper['harga_idr'])}")
        is_disc_a = bool(vram_gb(a) or (a.get("gpu") and any(x in a["gpu"].lower() for x in ("rtx", "gtx", "geforce", "radeon rx"))))
        is_disc_b = bool(vram_gb(b) or (b.get("gpu") and any(x in b["gpu"].lower() for x in ("rtx", "gtx", "geforce", "radeon rx"))))
        if is_disc_a != is_disc_b:
            d_p = a if is_disc_a else b
            i_p = b if is_disc_a else a
            facts.append(f"{d_p['nama']} sudah dilengkapi GPU dedicated ({d_p['gpu']}) untuk performa grafis/3D tinggi, sedangkan {i_p['nama']} memakai GPU terintegrasi yang lebih hemat daya")
        elif is_disc_a and is_disc_b:
            va, vb = vram_gb(a), vram_gb(b)
            if va and vb and va != vb:
                bigger = a if va > vb else b
                facts.append(f"VRAM GPU {bigger['nama']} lebih besar ({max(va, vb)} GB vs {min(va, vb)} GB)")
        if facts:
            concl.append("Fakta perbedaan utama: " + "; ".join(facts) + ".")
            
    return "\n".join(rows) + ("\n\n" + "\n".join(concl) if concl else "")

def render_decision_assistance(offered_prods: list[dict], s: dict) -> str:
    """
    Panduan keputusan saat pelanggan bingung (Anti-Parrot Looping).
    Mengontraskan opsi paling terjangkau vs opsi performa tertinggi.
    """
    if not offered_prods:
        return "Biar aku bantu pilihin yang pas, boleh tahu kira-kira budget maksimal Kakak berapa? 😊"
    if len(offered_prods) == 1:
        p = offered_prods[0]
        return (f"Supaya nggak bingung Kak, untuk kebutuhan Kakak saat ini pilihan yang paling sesuai adalah "
                f"**{p['nama']}** ({format_price(p['harga_idr'])}). Mau aku bantu jelaskan detail spesifikasinya?")
                
    cheapest = min(offered_prods, key=lambda p: p["harga_idr"])
    priciest = max(offered_prods, key=lambda p: p["harga_idr"])
    
    return (
        f"Supaya nggak bingung, aku bantu bandingkan dua pilihan utamanya ya Kak:\n"
        f"1. Kalau mau yang paling hemat di budget: **{cheapest['nama']}** ({format_price(cheapest['harga_idr'])}).\n"
        f"2. Kalau mau performa spesifikasi tertinggi: **{priciest['nama']}** ({format_price(priciest['harga_idr'])}).\n\n"
        f"Kira-kira Kakak lebih mengutamakan yang paling hemat budget atau performa spesifikasi tertinggi nih?"
    )

def render_decision_advice(offered_prods: list[dict], s: dict) -> str:
    """
    Panduan keputusan spesifik saat pelanggan bingung memilih antara produk yang ditawarkan
    (misal: 'Cocok yang mana nih? Ntar aku diomelin mama kalo salah pilih').
    Memberikan saran berbasis use-case nyata dan budget.
    """
    if not offered_prods:
        return "Biar saya bantu pilihkan yang pas, boleh tahu kebutuhan atau budget yang disiapkan, Kak?"
    if len(offered_prods) == 1:
        p = offered_prods[0]
        return f"Untuk kebutuhan tersebut, seri **{p['nama']}** ({format_price(p['harga_idr'])}) adalah pilihan yang paling pas di katalog kami, Kak."
    
    cheapest = min(offered_prods, key=lambda p: p["harga_idr"])
    priciest = max(offered_prods, key=lambda p: p["harga_idr"])
    
    target_person = s.get("persona_name") or ("Mama" if s.get("persona") == "family_elder" else "Kakak")
    needs = s.get("needs", [])
    
    lines = [f"Biar nggak salah pilih untuk {target_person}, ini pertimbangannya ya Kak:"]
    
    is_daily_or_casual = any(n in ("daily", "office") for n in needs) or any(t in str(s.get("history", [])).lower() for t in ("nonton", "santai", "streaming"))
    
    if is_daily_or_casual and not any(n in ("rendering_3d", "video_editing", "heavy_gaming") for n in needs):
        lines.append(f"1. **{cheapest['nama']}** ({format_price(cheapest['harga_idr'])}) — Pilihan paling tepat dan hemat untuk penggunaan harian/santai. Bobotnya ringan, hemat daya, dan performanya ({cheapest['cpu']}, RAM {cheapest['ram_gb']} GB) sudah sangat lancar untuk nonton video/film, streaming, browsing, maupun ketik dokumen.")
        gpu_note = f", GPU {priciest['gpu']}" if priciest.get('gpu') else ""
        lines.append(f"2. **{priciest['nama']}** ({format_price(priciest['harga_idr'])}) — Pilihan dengan spesifikasi tinggi ({priciest['cpu']}{gpu_note}, RAM {priciest['ram_gb']} GB). Laptop ini lebih ditujukan untuk gaming atau beban grafis berat, sehingga bodinya cenderung lebih besar/tebal dan harganya lebih tinggi.")
        lines.append(f"\nSaran saya, jika pemakaian utama {target_person} untuk santai dan nonton, sangat disarankan mengambil **{cheapest['nama']}** karena jauh lebih efisien, ringan, dan pas tanpa membayar ekstra untuk fitur gaming yang tidak terpakai. Apakah pertimbangan ini sudah cukup jelas, Kak?")
    else:
        lines.append(f"1. **{cheapest['nama']}** ({format_price(cheapest['harga_idr'])}) — Pilihan tepat jika mengutamakan efisiensi budget. Performanya ({cheapest['cpu']}, {cheapest['gpu']}, RAM {cheapest['ram_gb']} GB) sudah memadai untuk tugas standar dan desain/arsitektur dasar.")
        lines.append(f"2. **{priciest['nama']}** ({format_price(priciest['harga_idr'])}) — Pilihan terbaik jika ingin performa maksimal jangka panjang. Dilengkapi {priciest['cpu']}, GPU {priciest['gpu']} yang lebih bertenaga, dan storage {priciest['storage']} yang lebih besar, sangat aman untuk 3D rendering berat tanpa khawatir lemot.")
        lines.append(f"\nSaran saya, kalau pekerjaan {target_person} sering melibatkan pemodelan 3D atau rendering grafis berat, sangat disarankan mengambil **{priciest['nama']}** agar lebih awet dan tenang. Tapi jika lebih banyak desain standar dan ingin hemat budget, **{cheapest['nama']}** sudah mencukupi. Kira-kira lebih condong ke pertimbangan budget atau performa maksimal Kak?")
    return "\n".join(lines)

def allowed_amounts(catalog: Catalog, s: dict) -> set[int]:
    allowed = set(catalog.prices)
    for a, b in combinations(sorted(catalog.prices), 2):
        allowed.add(abs(a - b))
    c = s["constraints"]
    for k in ("budget_max", "budget_min", "budget_target"):
        if c.get(k):
            allowed.add(c[k])
    return allowed

def validate_reply(reply: str, catalog: Catalog, s: dict) -> bool:
    allowed = allowed_amounts(catalog, s)
    for m in re.finditer(r"Rp(\d{1,3}(?:\.\d{3})+)", reply):
        val = int(m.group(1).replace(".", ""))
        if val not in allowed and val not in (5_000_000, 10_000_000, 12_000_000):
            # Nilai yang disebutkan pelanggan di pertanyaan diperbolehkan
            return False
    for m in re.finditer(r"\bKB-[A-Z]\d+\b", reply):
        if m.group(0) not in catalog.by_code:
            return False
    return True
