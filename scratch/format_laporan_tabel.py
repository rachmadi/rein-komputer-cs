import json

with open("scratch/uji_p29_tabel_10_turns.json", encoding="utf-8") as f:
    items = json.load(f)

# Group by pesan_user
grouped = {}
for it in items:
    q = it["pesan_user"]
    if q not in grouped:
        grouped[q] = []
    grouped[q].append(it)

with open("scratch/laporan_tabel_10.md", "w", encoding="utf-8") as f:
    for q, rows in grouped.items():
        f.write(f"\n### Pesan: \"{q}\"\n\n")
        f.write("| Varian | Ulangan | Argumen Alat | Kode Foto Terkirim | Balasan Verbatim |\n")
        f.write("|---|---|---|---|---|\n")
        for r in rows:
            v = r["varian"]
            rep = r["ulangan"]
            arg = r["argumen_alat"].replace("|", "\\|")
            foto = ", ".join(r["kode_foto_terkirim"]) if r["kode_foto_terkirim"] else "-"
            # Balasan verbatim WAJIB disalin apa adanya dari berkas JSON hasil
            balasan = r["balasan_verbatim"].replace("|", "\\|").replace("\n", "<br>")
            f.write(f"| {v} | {rep} | `{arg}` | {foto} | {balasan} |\n")

print("Generated scratch/laporan_tabel_10.md")
