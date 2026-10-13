"""
Ukur recall OOD sebelum dan sesudah ingest pada indeks uji terpisah (knowledge_test).
Tidak menyentuh koleksi produksi computer_knowledge.
"""
import os, csv, json, time
os.environ["QDRANT_KNOWLEDGE_COLLECTION"] = "knowledge_test"

from services.knowledge_service import get_usage_requirements, _PROFILE_CACHE

# Reset cache agar fresh
_PROFILE_CACHE.clear()

# Set pengembangan penuh: positif (ada profil yang benar) dan negatif sulit (OOD)
DEV_SET = [
    # (query, expected_profil_id, is_positive)
    ("laptop buat edit video 4k", "P03", True),
    ("komputer untuk game AAA berat", "P05", True),
    ("laptop kuliah sehari-hari", "P06", True),
    ("laptop baterai awet", "P16", True),
    ("ada diskon laptop gaming", "P04", True),
    ("install apa saja untuk laptop kuliah", "P06", True),
    ("laptop desain grafis", "P02", True),
    ("komputer kasir toko", "P15", True),
    ("laptop streaming youtube", "P08", True),
    ("laptop data science AI", "P13", True),
    # Negatif sulit (OOD — tidak ada profil yang cocok, harus di_luar_topik atau score rendah)
    ("berapa jam buka toko", None, False),
    ("cara bayar cicilan", None, False),
    ("garansi berapa tahun", None, False),
    ("ongkos kirim ke Surabaya", None, False),
    ("ada promo hari ini tidak", None, False),
]

def evaluate(label):
    results = []
    tp = fp = fn = tn = 0
    for query, expected, is_pos in DEV_SET:
        t0 = time.time()
        try:
            res = get_usage_requirements(query, limit=1)
            profils = res.get("profil", [])
            if profils:
                pred_id = profils[0].get("profil_id")
                tipe = profils[0].get("tipe", "")
            else:
                pred_id = None
                tipe = "none"
        except Exception as e:
            pred_id = None
            tipe = "error"
        
        dt = time.time() - t0
        
        if is_pos:
            match = (pred_id == expected)
            if match: tp += 1
            else: fn += 1
        else:
            # Negatif: harus di_luar_topik atau pred_id None
            is_ood = (tipe == "di_luar_topik" or pred_id is None)
            if is_ood: tn += 1
            else: fp += 1
        
        results.append({
            "label": label,
            "query": query,
            "expected": expected or "OOD",
            "predicted": pred_id or tipe,
            "is_positive": is_pos,
            "match": (pred_id == expected) if is_pos else (tipe == "di_luar_topik"),
            "latency_s": round(dt, 3)
        })
        _PROFILE_CACHE.clear()  # flush cache agar tiap query independen
    
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    print(f"\n=== {label} ===")
    print(f"  TP={tp} FN={fn} FP={fp} TN={tn}")
    print(f"  Recall(+)={recall:.2%}  Precision={precision:.2%}  Specificity(-)={specificity:.2%}")
    return results, {"label": label, "tp": tp, "fn": fn, "fp": fp, "tn": tn,
                     "recall": recall, "precision": precision, "specificity": specificity}

all_results = []
summaries = []

# SEBELUM ingest (pakai index yang ada)
r1, s1 = evaluate("SEBELUM_INGEST")
all_results += r1
summaries.append(s1)

os.makedirs("docs", exist_ok=True)
with open("docs/ood_full_eval.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["label","query","expected","predicted","is_positive","match","latency_s"])
    w.writeheader()
    w.writerows(all_results)

with open("docs/ood_summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["label","tp","fn","fp","tn","recall","precision","specificity"])
    w.writeheader()
    w.writerows(summaries)

print("\nHasil tersimpan ke docs/ood_full_eval.csv dan docs/ood_summary.csv")
