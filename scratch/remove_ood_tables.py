import sys
import re

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "r", encoding="utf-8") as f:
    text = f.read()

# Replace all fake tables with tipe: di_luar_topik
text = re.sub(r'\| Komponen \| Minimum \| Direkomendasikan \|\n\|---\|---\|---\|\n\| CPU \| Tidak disyaratkan \| Tidak disyaratkan \|', '- **Tipe:** di_luar_topik', text)

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "w", encoding="utf-8") as f:
    f.write(text)
