import json

with open("scratch/uji_p29_live37_varian_a.json", encoding="utf-8") as f:
    va = json.load(f)
with open("scratch/uji_p29_live37_varian_b.json", encoding="utf-8") as f:
    vb = json.load(f)

for rep in [1, 2, 3]:
    ta = next((t for r in va["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 18), None)
    tb = next((t for r in vb["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 18), None)
    print(f"=== REP {rep} ===")
    print("VAR A T18:\n", ta["balasan_verbatim"])
    print("VAR B T18:\n", tb["balasan_verbatim"])
    print("-" * 50)
