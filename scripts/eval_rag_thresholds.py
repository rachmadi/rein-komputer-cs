# -*- coding: utf-8 -*-
"""
scripts/eval_rag_thresholds.py
Evaluasi ambang batas RAG (0.35, 0.40, 0.45) pada:
(a) eval/rag_probe.csv (lama, 20 probe)
(b) eval/rag_probe_conversational.csv (baru, 20 probe percakapan)
"""
import os
import sys
import csv
import json
import requests

sys.path.insert(0, os.path.abspath("."))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.catalog_service import QDRANT_URL, get_embedding
from services.knowledge_service import KNOWLEDGE_COLLECTION, normalize_query

def get_top_qdrant_score(text: str) -> tuple[float, str]:
    vec = get_embedding(normalize_query(text))
    if not vec:
        return 0.0, ""
    url = f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/search"
    payload = {
        "vector": vec,
        "limit": 5,
        "filter": {"must": [{"key": "tipe", "match": {"value": "profil"}}]},
        "with_payload": True
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    points = resp.json().get("result", [])
    valid_points = [
        p for p in points
        if p.get("payload", {}).get("tipe") == "profil"
        and str(p.get("payload", {}).get("id", "")).startswith("P")
    ]
    if not valid_points:
        return 0.0, ""
    top = valid_points[0]
    return float(top.get("score", 0.0)), str(top.get("payload", {}).get("id", ""))


def evaluate_set(filepath: str, is_conversational: bool = False):
    print(f"\n--- Evaluasi: {filepath} ---")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    results = []
    for r in rows:
        kueri = r.get("kueri", "")
        label = r.get("kategori") or r.get("label_domain")
        score, prof_id = get_top_qdrant_score(kueri)
        results.append({
            "no": r.get("no"),
            "kueri": kueri,
            "label": label,
            "score": score,
            "prof_id": prof_id
        })
        print(f"[{r.get('no')}] {kueri[:40]:<40} | label={label:<10} | score={score:.4f} ({prof_id})")

    # Hitung per ambang batas
    thresholds = [0.35, 0.40, 0.45]
    summary_table = []

    for th in thresholds:
        n = len(results)
        benar = 0
        salah = 0
        tak_terjawab = 0  # in-domain tapi ditolak karena di bawah ambang

        for item in results:
            score = item["score"]
            label = item["label"]
            if label == "in_domain":
                if score >= th:
                    benar += 1
                else:
                    tak_terjawab += 1
            elif label == "ood":
                if score < th:
                    benar += 1
                else:
                    salah += 1  # ood tapi lolos ambang (false positive)

        summary_table.append({
            "threshold": th,
            "n": n,
            "benar": benar,
            "salah": salah,
            "tak_terjawab": tak_terjawab
        })

    return results, summary_table


def main():
    res_old, summary_old = evaluate_set("eval/rag_probe.csv", is_conversational=False)
    res_new, summary_new = evaluate_set("eval/rag_probe_conversational.csv", is_conversational=True)

    print("\n" + "=" * 60)
    print("HASIL EVALUASI AMBANG RAG LAMA (eval/rag_probe.csv)")
    print("=" * 60)
    print(f"{'Threshold':<10} | {'n':<4} | {'Benar':<6} | {'Salah':<6} | {'Tak Terjawab':<12}")
    print("-" * 50)
    for s in summary_old:
        print(f"{s['threshold']:<10.2f} | {s['n']:<4} | {s['benar']:<6} | {s['salah']:<6} | {s['tak_terjawab']:<12}")

    print("\n" + "=" * 60)
    print("HASIL EVALUASI AMBANG RAG BARU PERCAKAPAN (eval/rag_probe_conversational.csv)")
    print("=" * 60)
    print(f"{'Threshold':<10} | {'n':<4} | {'Benar':<6} | {'Salah':<6} | {'Tak Terjawab':<12}")
    print("-" * 50)
    for s in summary_new:
        print(f"{s['threshold']:<10.2f} | {s['n']:<4} | {s['benar']:<6} | {s['salah']:<6} | {s['tak_terjawab']:<12}")


if __name__ == "__main__":
    main()
