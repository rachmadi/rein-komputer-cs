import sys

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "r", encoding="utf-8") as f:
    text = f.read()

import re

# OOD1
text = re.sub(r'(- \*\*ID:\*\* OOD1.*?)- \*\*Kata kunci pelanggan:\*\*.*?\n', r'\1- **Kata kunci pelanggan:** hari minggu, alamat toko, jam operasional, nomor wa\n', text, flags=re.DOTALL)

# OOD2
text = re.sub(r'(- \*\*ID:\*\* OOD2.*?)- \*\*Kata kunci pelanggan:\*\*.*?\n', r'\1- **Kata kunci pelanggan:** klaim garansi, servis, biaya perbaikan, pasta termal, keyboard rusak, lemot, bios, install ulang, install aplikasi, baterai\n', text, flags=re.DOTALL)

# OOD3
text = re.sub(r'(- \*\*ID:\*\* OOD3.*?)- \*\*Kata kunci pelanggan:\*\*.*?\n', r'\1- **Kata kunci pelanggan:** cicilan, gratis ongkir, tukar tambah, diskon\n', text, flags=re.DOTALL)

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "w", encoding="utf-8") as f:
    f.write(text)
