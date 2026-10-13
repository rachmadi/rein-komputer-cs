import json

d14 = json.load(open("scratch/replay_model_gemma_p14.json", encoding="utf-8"))

with open("scratch/extracted_turns.txt", "w", encoding="utf-8") as out:
    for t in d14["giliran"]:
        if 65 <= t["n"] <= 74:
            out.write(f"### Giliran {t['n']}\n")
            out.write(f"- **Pesan Pelanggan**: \"{t['user']}\"\n")
            out.write(f"- **Sebelum (Log Asli)**:\n  > {t['asli']['balasan']}\n")
            out.write(f"- **Sesudah (Putaran 14 Replay)**:\n  > {t['baru']['balasan']}\n")
            out.write(f"- **Metadata Giliran**: Aksi: `{t['baru']['aksi']}` | Status Fakta: `{t['baru']['status_fakta']}` | Kartu Produk: `{t['baru']['kartu']}` | Latensi: `{t['baru']['latensi_s']}s`\n\n")

print("Extracted successfully")
