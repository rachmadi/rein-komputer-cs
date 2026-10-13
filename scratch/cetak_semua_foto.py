import json

with open("scratch/uji_p29_semua_foto_turns.json", encoding="utf-8") as f:
    items = json.load(f)

print(f"Total giliran memuat kata foto/gambar: {len(items)}")
for it in items:
    print(f"[{it['suite']:<17} | {it['varian']} | R{it['rep']} | T{it['turn']:02d}] foto={it['kode_foto_terkirim']} | msg={it['user_msg'][:30]}")
