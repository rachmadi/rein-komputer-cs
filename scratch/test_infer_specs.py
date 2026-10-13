# -*- coding: utf-8 -*-
"""
Uji inferensi tag kebutuhan dari spesifikasi teknis hardware.
"""
import re

def infer_tags_from_specs(rec: dict) -> list[dict]:
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
    harga = rec.get("harga_idr", 0)

    # 1. PRINTER
    if cat == "printer":
        fungsi = (rec.get("fungsi") or "").lower()
        tek = (rec.get("teknologi") or "").lower()
        koneksi = (rec.get("konektivitas") or "").lower()
        res = (rec.get("resolusi") or "").lower()
        
        # Semua printer bisa cetak dokumen
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
            
        # Wi-Fi / Cetak nirkabel / Foto
        if "wi-fi" in koneksi or "wireless" in koneksi or "mobile" in koneksi:
            add("student", "cetak berkas kuliah")
            if any(dpi in res for dpi in ("4800", "5760", "6000")):
                add("design", "cetak foto warna")
                
        return tags

    # 2. KOMPUTER (LAPTOP & DESKTOP)
    cpu = (rec.get("cpu") or "").lower()
    gpu = (rec.get("gpu") or "").lower()
    ram_gb = rec.get("ram_gb") or 0
    display = (rec.get("display") or "").lower()

    # Identifikasi level GPU
    has_rtx_high = any(x in gpu for x in ("rtx 4070", "rtx 4080", "rtx 4090"))
    has_rtx_mid_high = any(x in gpu for x in ("rtx 4060", "rtx 3060", "rtx 3070"))
    has_rtx_entry_mid = any(x in gpu for x in ("rtx 4050", "rtx 3050"))
    has_discrete_entry = any(x in gpu for x in ("rtx 2050", "gtx 1660", "gtx 1650"))
    is_integrated_gpu = not (has_rtx_high or has_rtx_mid_high or has_rtx_entry_mid or has_discrete_entry)

    # Identifikasi level CPU
    is_cpu_budget = any(x in cpu for x in ("n100", "celeron", "pentium", "i3", "ryzen 3"))
    is_cpu_high_tdp = any(x in cpu for x in ("13420h", "7735hs", "12450hx", "14650hx", "14700f", "13400f", "13400"))
    is_cpu_top = any(x in cpu for x in ("14650hx", "14700", "14700f", "i9", "ryzen 9"))

    # A. WORKLOAD GRAFIS BERAT & TEKNIK: 3D Rendering, Arsitektur, CAD, Insinyur
    if has_rtx_high:
        add("rendering_3d", "3D rendering")
        add("gaming", "gaming berat", qualifier="kelas atas")
        add("ai_dev", "AI development")
        add("video_editing", "editing video", qualifier="berat")
        add("design", "desain grafis")
    elif has_rtx_mid_high:
        add("rendering_3d", "3D rendering")
        add("gaming", "gaming berat", qualifier="berat")
        add("ai_dev", "AI development entry-level", qualifier="entry-level")
        add("video_editing", "editing video")
        add("design", "desain grafis")
    elif has_rtx_entry_mid:
        add("rendering_3d", "3D rendering")
        add("gaming", "gaming berat", qualifier="berat")
        add("video_editing", "editing video")
        add("design", "desain grafis")
        add("android_studio", "Android Studio")
    elif has_discrete_entry:
        add("gaming", "gaming menengah", qualifier="menengah")
        add("design", "desain ringan", qualifier="ringan")
        add("video_editing", "editing video")
        add("android_studio", "Android Studio")
    elif is_integrated_gpu:
        add("gaming", "gaming berat", negated=True)
        if is_cpu_budget:
            add("rendering_3d", "3D rendering", negated=True)

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

if __name__ == "__main__":
    from core.catalog import Catalog
    cat = Catalog.from_dummy()
    print(f"Total produk dummy: {len(cat.products)}")
    for p in cat.products:
        inferred = infer_tags_from_specs(p)
        tags_only = [f"{t['tag']}{' (neg)' if t.get('negated') else ''}" for t in inferred]
        print(f"[{p['kode']}] {p['nama']}: {', '.join(tags_only)}")
