# -*- coding: utf-8 -*-
"""
scratch/uji_pengetahuan.py
Pengujian dan Pemilihan Cara Pencarian Pengetahuan (Putaran 24 Butir 2b dan Butir 3b).

Mengukur hit@1, hit@3, dan hit@5 untuk konfigurasi pencarian pengetahuan C1.
Mendukung pengujian top-k (top-3 dan top-5) serta pemilihan koleksi Qdrant.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from services.catalog_service import QDRANT_URL, get_embedding
from services.agent_tools import _search_kb_markdown_all


def query_qdrant(collection: str, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Mencari titik di Qdrant berdasarkan embedding teks query."""
    vec = get_embedding(query_text.lower())
    if not vec:
        return []
    url = f"{QDRANT_URL}/collections/{collection}/points/search"
    payload = {
        "vector": vec,
        "limit": limit,
        "with_payload": True
    }
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code != 200:
        return []
    pts = resp.json().get("result", [])
    results = []
    for pt in pts:
        pld = pt.get("payload", {})
        cid = pld.get("id") or ""
        raw_title = pld.get("judul") or ""
        clean_title = re.sub(r"^[PGMK]\d+\s*[-—]\s*", "", raw_title).strip()
        results.append({
            "id": cid,
            "judul": clean_title,
            "score": pt.get("score", 0.0),
            "tipe": pld.get("tipe")
        })
    return results


def load_dataset(csv_path: str = "eval/uji_pengetahuan.csv") -> List[Dict[str, Any]]:
    items = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            q = r["pertanyaan"].strip()
            exp = r["id_harapan"].strip()
            exp_set = {x.strip() for x in exp.split("|") if x.strip()}
            items.append({
                "pertanyaan": q,
                "id_harapan_raw": exp,
                "expected_ids": exp_set
            })
    return items


def run_benchmark(collection: str = "computer_knowledge_full", top_k_list: List[int] | None = None):
    dataset = load_dataset()
    top_ks = top_k_list or [3, 5]
    max_k = max(top_ks)

    print(f"Loaded {len(dataset)} pertanyaan dari eval/uji_pengetahuan.csv")
    print(f"Koleksi: {collection} | Evaluasi top-k: {top_ks}")

    detailed_results = []
    total_q = len(dataset)

    # Inisialisasi hit counters
    hit1_counts = {k: 0 for k in top_ks}
    hit3_counts = {k: 0 for k in top_ks if k >= 3}
    hit5_counts = {k: 0 for k in top_ks if k >= 5}

    print("\n" + "=" * 110)
    print("### RINCIAN PENCARIAN PENGETAHUAN PER KUERI")
    print("=" * 110)
    print(f"{'No':<3} | {'Pertanyaan':<40} | {'Harapan':<8} | {'Top-3 ID':<18} | {'Top-5 ID':<28}")
    print("-" * 110)

    for idx, item in enumerate(dataset, start=1):
        q = item["pertanyaan"]
        exp_ids = item["expected_ids"]

        pts = query_qdrant(collection, q, limit=max_k)
        all_ids = [p["id"] for p in pts]

        q_record = {
            "no": idx,
            "pertanyaan": q,
            "id_harapan": item["id_harapan_raw"],
            "top_ids_all": all_ids,
            "items": [{"id": p["id"], "judul": p["judul"]} for p in pts],
            "by_k": {}
        }

        for k in top_ks:
            k_ids = all_ids[:k]
            h1 = bool(k_ids and k_ids[0] in exp_ids)
            h3 = any(tid in exp_ids for tid in k_ids[:3]) if k >= 3 else None
            h5 = any(tid in exp_ids for tid in k_ids[:5]) if k >= 5 else None

            if h1:
                hit1_counts[k] += 1
            if h3:
                hit3_counts[k] += 1
            if h5:
                hit5_counts[k] += 1

            q_record["by_k"][f"top{k}"] = {
                "ids": k_ids,
                "hit@1": h1,
                "hit@3": h3,
                "hit@5": h5
            }

        detailed_results.append(q_record)

        top3_str = ", ".join(all_ids[:3]) if len(all_ids) >= 3 else ", ".join(all_ids)
        top5_str = ", ".join(all_ids[:5])
        print(f"{idx:02d}  | {q[:40]:<40} | {item['id_harapan_raw']:<8} | {top3_str:<18} | {top5_str:<28}")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = f"scratch/uji_pengetahuan_{timestamp_str}.json"

    summary: Dict[str, Any] = {}
    for k in top_ks:
        k_summary = {
            "hit@1": f"{hit1_counts[k]}/{total_q}",
            "hit@1_num": hit1_counts[k],
            "hit@1_pct": round((hit1_counts[k] / total_q) * 100, 1),
        }
        if k >= 3:
            k_summary["hit@3"] = f"{hit3_counts[k]}/{total_q}"
            k_summary["hit@3_num"] = hit3_counts[k]
            k_summary["hit@3_pct"] = round((hit3_counts[k] / total_q) * 100, 1)
        if k >= 5:
            k_summary["hit@5"] = f"{hit5_counts[k]}/{total_q}"
            k_summary["hit@5_num"] = hit5_counts[k]
            k_summary["hit@5_pct"] = round((hit5_counts[k] / total_q) * 100, 1)
        summary[f"top_{k}"] = k_summary

    payload = {
        "timestamp": timestamp_str,
        "collection": collection,
        "total_pertanyaan": total_q,
        "top_ks": top_ks,
        "summary": summary,
        "details": detailed_results
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"### HASIL BENCHMARK PENCARIAN PENGETAHUAN ({total_q} PERTANYAAN, KOLEKSI: {collection})")
    print("=" * 80)
    print(f"| Konfigurasi | Hit@1 (/{total_q}) | Hit@1 (%) | Hit@3 (/{total_q}) | Hit@3 (%) | Hit@5 (/{total_q}) | Hit@5 (%) |")
    print("|---|---|---|---|---|---|---|")
    for k in top_ks:
        s = summary[f"top_{k}"]
        h1 = f"{s.get('hit@1', '-')} ({s.get('hit@1_pct', '-') }%)"
        h3 = f"{s.get('hit@3', '-')} ({s.get('hit@3_pct', '-') }%)" if "hit@3" in s else "-"
        h5 = f"{s.get('hit@5', '-')} ({s.get('hit@5_pct', '-') }%)" if "hit@5" in s else "-"
        print(f"| Top-{k:<4} | {s.get('hit@1', '-'):<7} | {s.get('hit@1_pct', '-'):<5}% | {s.get('hit@3', '-'):<7} | {s.get('hit@3_pct', '-'):<5}% | {s.get('hit@5', '-'):<7} | {s.get('hit@5_pct', '-'):<5}% |")
    print("=" * 80)
    print(f"Hasil lengkap disimpan ke: {out_json}\n")

    return summary, out_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark pencarian pengetahuan")
    parser.add_argument("--collection", default="computer_knowledge_full", help="Nama koleksi Qdrant")
    parser.add_argument("--topk", default="3,5", help="Daftar top-k dipisah koma (default: 3,5)")
    args = parser.parse_args()

    top_ks = [int(k.strip()) for k in args.topk.split(",") if k.strip()]
    run_benchmark(collection=args.collection, top_k_list=top_ks)
