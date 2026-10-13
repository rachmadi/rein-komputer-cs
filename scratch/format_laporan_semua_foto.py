import json

with open("scratch/uji_p29_semua_foto_turns.json", encoding="utf-8") as f:
    items = json.load(f)

with open("scratch/laporan_semua_foto.md", "w", encoding="utf-8") as f:
    f.write("| No | Suite / Pengujian | Varian | Ulangan | Giliran | Pesan User | Argumen Alat | Kode Foto Terkirim | Balasan Verbatim |\n")
    f.write("|---|---|---|---|---|---|---|---|---|\n")
    for idx, it in enumerate(items, 1):
        s = it["suite"]
        v = it["varian"]
        rep = it["rep"]
        t = it["turn"]
        u = it["user_msg"].replace("|", "\\|")
        arg = it["argumen_alat"].replace("|", "\\|")
        foto = ", ".join(it["kode_foto_terkirim"]) if it["kode_foto_terkirim"] else "-"
        balasan = it["balasan_verbatim"].replace("|", "\\|").replace("\n", "<br>")
        f.write(f"| {idx} | {s} | Varian {v} | {rep} | T{t} | {u} | `{arg}` | {foto} | {balasan} |\n")

print(f"Generated scratch/laporan_semua_foto.md with {len(items)} rows")
