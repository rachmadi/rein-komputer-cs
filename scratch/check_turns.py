import json

with open("scratch/replay_model_gemma_p13.json", encoding="utf-8") as f:
    d13 = json.load(f)
with open("scratch/replay_model_gemma_p13b.json", encoding="utf-8") as f:
    d13b = json.load(f)

for target in [54, 55, 56, 61, 62, 63]:
    t13 = next(x for x in d13["giliran"] if x["n"] == target)
    t13b = next(x for x in d13b["giliran"] if x["n"] == target)
    print("=" * 60)
    print(f"GILIRAN {target}")
    print(f"User: {t13['user']}")
    print("-" * 30)
    print(f"P13 Aksi: {t13['baru']['aksi']} | Status: {t13['baru']['status_fakta']}")
    print(f"P13 Produk tampil: {t13.get('produk_tampil')}")
    print(f"P13 Balasan:\n{t13['baru']['balasan']}")
    print("-" * 30)
    print(f"P13b Aksi: {t13b['baru']['aksi']} | Status: {t13b['baru']['status_fakta']}")
    print(f"P13b Produk tampil: {t13b.get('produk_tampil')}")
    print(f"P13b Balasan:\n{t13b['baru']['balasan']}")
