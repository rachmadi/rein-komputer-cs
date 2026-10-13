import json

with open("scratch/uji_p29_live37_varian_a.json", encoding="utf-8") as f:
    va = json.load(f)
with open("scratch/uji_p29_live37_varian_b.json", encoding="utf-8") as f:
    vb = json.load(f)

print("--- LATENSI LIVE 37 ---")
print(f"Varian A: Median={va['latensi_median_s']}s, P95={va['latensi_p95_s']}s, Max={va['latensi_max_s']}s")
print(f"Varian B: Median={vb['latensi_median_s']}s, P95={vb['latensi_p95_s']}s, Max={vb['latensi_max_s']}s")

target_queries = [
    "Kasih aku spek ROG tadi deh sama gambarnya",
    "Gambarnya mana?",
    "Mana? Gak ada",
    "Aku kan mau lihat gambarnya dulu",
    "Kalo desktop untuk desain 3D, apa rekomendasimu?",
    "Gak ada yang ram 32 GB?",
    "Lihat spek ecotank deh. Kalo ada sama gambarnya",
    "Gak ada fotonya?"
]

print("\n--- PERBANDINGAN TARGET TURNS (REP 1) ---")
for q in target_queries:
    t_a = next((t for r in va["runs"] if r["rep"] == 1 for t in r["turns"] if t["user_msg"] == q), None)
    t_b = next((t for r in vb["runs"] if r["rep"] == 1 for t in r["turns"] if t["user_msg"] == q), None)
    print(f"\nPesan: \"{q}\"")
    if t_a:
        print(f"  [Var A] Tools={t_a['tools_called']} Foto={t_a['foto_dikirim']}")
        print(f"          Balasan: {t_a['balasan_verbatim'][:120]}...")
    if t_b:
        print(f"  [Var B] Tools={t_b['tools_called']} Foto={t_b['foto_dikirim']}")
        print(f"          Balasan: {t_b['balasan_verbatim'][:120]}...")
