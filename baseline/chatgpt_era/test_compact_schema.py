# -*- coding: utf-8 -*-
"""
scripts/test_compact_schema.py
Eksperimen latensi parse: membandingkan skema standar vs skema kompak (nama field pendek, tanpa field kosong).
"""
import sys
import os
import json
import time
import math
import urllib.request
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field

sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')

from services.schema_actions import ActionEnum, ActionArguments, StateUpdate, get_parser_json_schema
from services.llm_parser import build_parser_messages, OLLAMA_BASE_URL, PARSER_MODEL, DEV_FEW_SHOTS
from services.validator import validate_parser_output


class CompactActionArgs(BaseModel):
    kat: str | None = None
    merk: str | None = None
    not_merk: str | None = None
    model: str | None = None
    gpu: str | None = None
    min_p: int | None = None
    max_p: int | None = None
    ram: int | None = None
    ssd: int | None = None
    layar: float | None = None
    butuh: str | None = None
    persona: str | None = None
    slot: str | None = None
    val: Any = None
    ref_prod: list[Any] | None = None
    attr: str | None = None
    jenis: str | None = None
    topik: str | None = None
    alasan: str | None = None

    model_config = {"extra": "ignore"}


class CompactParserOutput(BaseModel):
    act: ActionEnum
    args: CompactActionArgs = Field(default_factory=CompactActionArgs)
    state: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


def test_compact_vs_standard(n: int = 20):
    items = []
    with open("eval/parse_gold.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("split") == "dev":
                items.append(d)
                if len(items) >= n:
                    break

    print(f"=== Membandingkan Skema Standar vs Kompak pada {len(items)} dev items ===")

    # 1. Standard schema run
    print("\n[1] Menjalankan Skema Standar...")
    from services.llm_parser import parse_user_message
    std_lats = []
    std_correct = 0
    for idx, it in enumerate(items, 1):
        out, m = parse_user_message(it["pesan"], state=it.get("state"))
        std_lats.append(m["latency_ms"])
        if out.aksi.value == it["label_aksi"]:
            std_correct += 1

    std_p50 = sorted(std_lats)[len(std_lats)//2]
    std_acc = (std_correct / len(items)) * 100.0
    print(f"Standar: Acc={std_acc:.1f}% ({std_correct}/{len(items)}), Lat p50={std_p50:.1f}ms")

    # 2. Compact schema run
    print("\n[2] Menjalankan Skema Kompak...")
    compact_schema = CompactParserOutput.model_json_schema()
    cmp_lats = []
    cmp_correct = 0

    for idx, it in enumerate(items, 1):
        t0 = time.perf_counter()
        messages = build_parser_messages(it["pesan"], state=it.get("state"))
        # Call Ollama with compact schema
        req_data = {
            "model": PARSER_MODEL,
            "messages": messages,
            "format": compact_schema,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 120}
        }
        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/chat",
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_c = data.get("message", {}).get("content", "").strip()
            parsed = json.loads(raw_c)
            act_pred = parsed.get("act")
        except Exception as e:
            act_pred = "tidak_jelas"
        dt = (time.perf_counter() - t0) * 1000.0
        cmp_lats.append(dt)
        if act_pred == it["label_aksi"]:
            cmp_correct += 1

    cmp_p50 = sorted(cmp_lats)[len(cmp_lats)//2]
    cmp_acc = (cmp_correct / len(items)) * 100.0
    print(f"Kompak : Acc={cmp_acc:.1f}% ({cmp_correct}/{len(items)}), Lat p50={cmp_p50:.1f}ms")

    print("\n=== HASIL PERBANDINGAN ===")
    print(f"Standar -> Akurasi: {std_acc:.1f}%, p50: {std_p50:.1f} ms")
    print(f"Kompak  -> Akurasi: {cmp_acc:.1f}%, p50: {cmp_p50:.1f} ms")
    selisih_lat = std_p50 - cmp_p50
    print(f"Selisih latensi: {selisih_lat:+.1f} ms | Selisih akurasi: {cmp_acc - std_acc:+.1f}%")

    with open("eval/compact_latency_experiment.json", "w", encoding="utf-8") as f:
        json.dump({
            "samples": len(items),
            "std_acc_pct": std_acc,
            "std_latency_p50_ms": std_p50,
            "cmp_acc_pct": cmp_acc,
            "cmp_latency_p50_ms": cmp_p50,
            "delta_latency_ms": selisih_lat,
            "apply_compact": (cmp_acc >= std_acc and cmp_p50 < std_p50)
        }, f, indent=2)


if __name__ == "__main__":
    test_compact_vs_standard(20)
