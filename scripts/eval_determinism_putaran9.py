# -*- coding: utf-8 -*-
"""
scripts/eval_determinism_putaran9.py
Uji determinisme ActionEngine pada 134 giliran (11 percakapan)
dengan input parser yang dibekukan, dijalankan sebanyak 3 repetisi.
Menghasilkan eval/determinism_putaran9.json untuk memenuhi gerbang G8.
"""
import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))
from services.action_engine import ActionEngine
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments

def run_determinism_test():
    replay_path = "eval/replay_putaran9.jsonl"
    output_path = "eval/determinism_putaran9.json"

    if not os.path.exists(replay_path):
        raise FileNotFoundError(f"{replay_path} tidak ditemukan.")

    with open(replay_path, "r", encoding="utf-8") as f:
        turns = [json.loads(line) for line in f if line.strip()]

    print(f"Memuat {len(turns)} giliran dari {replay_path}...")

    from collections import defaultdict
    conv_turns = defaultdict(list)
    for t in turns:
        conv_turns[t["conv_id"]].append(t)

    runs_results = {1: [], 2: [], 3: []}

    engine = ActionEngine()

    for r in [1, 2, 3]:
        for conv_id, t_list in conv_turns.items():
            state = {}
            for t in t_list:
                aksi_enum = ActionEnum(t["aksi_terpilih"])
                parsed = ParserOutput(
                    aksi=aksi_enum,
                    argumen=ActionArguments()
                )
                act_res = engine.execute(parsed, session_state=state)
                runs_results[r].append({
                    "conv_id": conv_id,
                    "turn_idx": t["turn_idx"],
                    "aksi": act_res.aksi.value if hasattr(act_res.aksi, "value") else str(act_res.aksi),
                    "status": act_res.fakta.get("status")
                })

    identical = 0
    total = len(turns)
    for i in range(total):
        r1 = runs_results[1][i]
        r2 = runs_results[2][i]
        r3 = runs_results[3][i]
        if r1 == r2 == r3:
            identical += 1

    pct = (identical / total * 100.0) if total else 0.0

    result = {
        "dataset": replay_path,
        "total_turns": total,
        "repetitions": 3,
        "identical_turns": identical,
        "determinism_percent": round(pct, 2),
        "status": "PASS" if pct >= 95.0 else "FAIL"
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Hasil determinisme disimpan di {output_path}:")
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    run_determinism_test()
