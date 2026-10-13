import json

with open("scratch/replay_model_gemma_p13b.json", "r", encoding="utf-8") as f:
    d13b = json.load(f)

with open("scratch/replay_model_gemma_p14.json", "r", encoding="utf-8") as f:
    d14 = json.load(f)

turns_interest = [65, 66, 67, 68, 69, 70, 71, 72, 73, 74]

print("=== PERBANDINGAN GILIRAN 65-74 (MONITOR & OOD) ===")
for t14 in d14.get("giliran", []):
    n = t14.get("n")
    if n in turns_interest:
        t13b = next((x for x in d13b.get("giliran", []) if x.get("n") == n), {})
        user = t14.get("user")
        
        asli = t14.get("asli", {})
        balasan_asli = asli.get("balasan", "")
        aksi_asli = asli.get("aksi")
        
        rep14 = t14.get("baru", {})
        balasan14 = rep14.get("balasan", "")
        kartu14 = rep14.get("kartu")
        
        print(f"\n[GILIRAN {n}]")
        print(f"User: {user}")
        print(f"ASLI -> Aksi: {aksi_asli}, Balasan: {balasan_asli}")
        print(f"P14  -> Aksi: {rep14.get('aksi')}, Status: {rep14.get('status_fakta')}, Kartu: {kartu14}")
        print(f"P14  Balasan: {balasan14}")
