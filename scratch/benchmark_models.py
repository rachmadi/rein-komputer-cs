# -*- coding: utf-8 -*-
import json
import time
import urllib.request
import re

MODELS_TO_TEST = ["qwen2.5-coder:1.5b", "llama3.2:1b", "gemma2:2b", "gemma4:e4b"]

def query_ollama(model: str, user_text: str, pending_q: str | None, current_slots: dict):
    sys_prompt = (
        "Kamu asisten NLU ekstraksi slot untuk toko komputer Bobby Computer.\n"
        "Ekstrak intent dan slots dari pesan pelanggan dalam JSON.\n"
        "Daftar Intent: sapaan, tanya_merek_stok, kebutuhan, produk_spesifik, lanjutan, meta_protes, di_luar_topik.\n"
        "Slots: persona (ibu/bapak/anak/dll), aktivitas (hiburan/game/kuliah/kantor/dll), budget (angka), kategori (laptop/pc/printer), merek (asus/acer/dll).\n"
        "PENTING: Jika ada Pending Question, perlakukan pesan sebagai jawaban untuk slot itu!\n"
        "Format JSON eksklusif:\n"
        "{\"intent\": \"...\", \"slots\": {\"persona\": null, \"aktivitas\": null, \"budget\": null, \"kategori\": null, \"merek\": null}}"
    )
    user_prompt = f"Pending Question: {pending_q}\nSlots Sekarang: {json.dumps(current_slots)}\nPesan: \"{user_text}\""

    req_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": 80,
            "temperature": 0.0
        },
        "keep_alive": "60m"
    }

    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(req_data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        lat = time.perf_counter() - t0
        content = res["message"]["content"]
        parsed = json.loads(content)
        return parsed, lat, None
    except Exception as e:
        return None, time.perf_counter() - t0, str(e)

if __name__ == "__main__":
    test_cases = [
        ("Ada asus?", None, {}),
        ("Untuk ibu saya yang sudah sepuh", "kebutuhan", {"merek": "asus"}),
        ("Buat hiburan", "aktivitas", {"merek": "asus", "persona": "ibu"}),
        ("Mana?", "aktivitas", {"merek": "asus", "persona": "ibu", "aktivitas": "hiburan"}),
        ("Kan sudah dibilang buat hiburan", None, {"merek": "asus", "persona": "ibu", "aktivitas": "hiburan"}),
    ]

    for m in ["llama3.2:1b", "gemma4:e4b"]:
        print(f"\n=== TESTING MODEL: {m} ===")
        # warmup
        query_ollama(m, "halo", None, {})
        for q, p, s in test_cases:
            res, lat, err = query_ollama(m, q, p, s)
            if err:
                print(f"[{lat:.2f}s] '{q}' -> ERROR: {err}")
            else:
                print(f"[{lat:.2f}s] '{q}' (Pending: {p}) -> Intent: {res.get('intent')} | Slots: {res.get('slots')}")
