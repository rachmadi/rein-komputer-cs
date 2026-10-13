import sys

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "r", encoding="utf-8") as f:
    text = f.read()

# Fix P03 filter minimum
old_p03 = "- **Filter minimum:** ram_gb >= 16; storage_ssd_gb >= 512; cpu_tier >= 2."
new_p03 = "- **Filter minimum:** ram_gb >= 32; storage_ssd_gb >= 1000; cpu_tier >= 2; gpu_dedicated = 1; vram_gb >= 8."
text = text.replace(old_p03.replace(">=", "â‰¥"), new_p03.replace(">=", "â‰¥"))
text = text.replace("- **Filter minimum:** ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2.", "- **Filter minimum:** ram_gb ≥ 32; storage_ssd_gb ≥ 1000; cpu_tier ≥ 2; gpu_dedicated = 1; vram_gb ≥ 8.")

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "w", encoding="utf-8") as f:
    f.write(text)
