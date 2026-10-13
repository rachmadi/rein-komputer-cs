import json

with open('scratch/uji_pengetahuan_20261012_190925.json', 'r', encoding='utf-8') as f:
    d2 = json.load(f)

with open('scratch/uji_pengetahuan_20261012_191254.json', 'r', encoding='utf-8') as f:
    d3 = json.load(f)

with open('scratch/uji_multigiliran_20261012_191540.json', 'r', encoding='utf-8') as f:
    d4 = json.load(f)

print("### TABEL 1: Top-3 vs Top-5 per Kueri (Butir 2 - computer_knowledge_full)\n")
print("| No | Pertanyaan | ID Harapan | ID Top-3 | Hit@3 | ID Top-5 | Hit@5 |")
print("|---|---|---|---|:---:|---|:---:|")
for it in d2['details']:
    q = it['pertanyaan']
    exp = it['id_harapan']
    t3 = ', '.join(it['by_k']['top3']['ids'])
    t5 = ', '.join(it['by_k']['top5']['ids'])
    h3 = "v" if it['by_k']['top3']['hit@3'] else "x"
    h5 = "v" if it['by_k']['top5']['hit@5'] else "x"
    print(f"| {it['no']:02d} | {q} | {exp} | {t3} | {h3} | {t5} | {h5} |")

print("\nSummary Butir 2:")
print(f"Top-3: Hit@1 = {d2['summary']['top_3']['hit@1']} ({d2['summary']['top_3']['hit@1_pct']}%), Hit@3 = {d2['summary']['top_3']['hit@3']} ({d2['summary']['top_3']['hit@3_pct']}%)")
print(f"Top-5: Hit@1 = {d2['summary']['top_5']['hit@1']} ({d2['summary']['top_5']['hit@1_pct']}%), Hit@3 = {d2['summary']['top_5']['hit@3']} ({d2['summary']['top_5']['hit@3_pct']}%), Hit@5 = {d2['summary']['top_5']['hit@5']} ({d2['summary']['top_5']['hit@5_pct']}%)")

print("\n" + "="*80)
print("### TABEL 2: Koleksi Uji Kata Kunci KB per Kueri (Butir 3 - computer_knowledge_uji, Top-3)\n")
print("| No | Pertanyaan | ID Harapan | ID Top-3 | Hit@1 | Hit@3 |")
print("|---|---|---|---|:---:|:---:|")
for it in d3['details']:
    q = it['pertanyaan']
    exp = it['id_harapan']
    t3 = ', '.join(it['by_k']['top3']['ids'])
    h1 = "v" if it['by_k']['top3']['hit@1'] else "x"
    h3 = "v" if it['by_k']['top3']['hit@3'] else "x"
    print(f"| {it['no']:02d} | {q} | {exp} | {t3} | {h1} | {h3} |")

print("\nSummary Butir 3:")
print(f"Top-3 (Koleksi Uji): Hit@1 = {d3['summary']['top_3']['hit@1']} ({d3['summary']['top_3']['hit@1_pct']}%), Hit@3 = {d3['summary']['top_3']['hit@3']} ({d3['summary']['top_3']['hit@3_pct']}%)")

print("\n" + "="*80)
print("### TABEL 3: Replay Multi-Giliran Top-3 vs Top-5 (Butir 4)\n")
print("| Varian | Perlu Dipanggil (/42) | Latensi Max (s) | Giliran >60s | Alat Mentah Diurai | Alat Mentah Gagal | Error Darurat |")
print("|---|:---:|:---:|:---:|:---:|:---:|:---:|")
for var, s in d4['summary'].items():
    print(f"| {var} | {s['panggil_perlu']} | {s['max_latensi_s']} | {s['lebih_60s']} | {s['alat_mentah_diurai']} | {s['alat_mentah_gagal']} | {s['error_darurat']} |")
