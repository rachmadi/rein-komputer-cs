# -*- coding: utf-8 -*-
import sys
sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')
import requests
import json
import time

# Kita uji apakah Ollama gemma4:e4b bisa menerima schema argumen oneOf 12 aksi
action_arg_schemas = [
    # sapa
    {"properties": {}, "additionalProperties": False},
    # cari_produk
    {
        "properties": {
            "kategori": {"type": ["string", "null"]},
            "merek": {"type": ["string", "null"]},
            "merek_kecuali": {"type": ["string", "null"]},
            "nama_model": {"type": ["string", "null"]},
            "gpu": {"type": ["string", "null"]},
            "min_harga": {"type": ["integer", "null"]},
            "max_harga": {"type": ["integer", "null"]}
        }
    },
    # minta_rekomendasi
    {
        "properties": {
            "kebutuhan_teks": {"type": ["string", "null"]},
            "persona": {"type": ["string", "null"]},
            "budget_max": {"type": ["integer", "null"]}
        }
    },
    # jawab_pertanyaan_bot
    {
        "properties": {
            "slot": {"type": "string", "enum": ["kebutuhan", "aktivitas", "budget", "kategori", "merek", "persona"]},
            "nilai": {"type": ["string", "integer", "number", "null"]}
        }
    },
    # lanjutan_hasil
    {
        "properties": {
            "jenis": {"type": "string", "enum": ["lebih_murah", "lebih_mahal", "yang_lain", "filter_tambahan"]},
            "merek_kecuali": {"type": ["string", "null"]}
        },
        "required": ["jenis"]
    },
    # basa_basi
    {
        "properties": {
            "jenis": {"type": "string", "enum": ["terima_kasih", "pamit", "lainnya"]}
        },
        "required": ["jenis"]
    },
    # perbaiki_percakapan
    {
        "properties": {
            "jenis": {"type": "string", "enum": ["salah_paham", "keluhan", "koreksi"]},
            "rujukan": {"type": ["string", "null"]}
        },
        "required": ["jenis"]
    }
]

schema_oneof = {
    "type": "object",
    "properties": {
        "aksi": {
            "type": "string",
            "enum": ["sapa", "cari_produk", "minta_rekomendasi", "jawab_pertanyaan_bot", "lanjutan_hasil", "basa_basi", "perbaiki_percakapan"]
        },
        "argumen": {
            "type": "object",
            "oneOf": action_arg_schemas
        },
        "pembaruan_state": {
            "type": "object",
            "properties": {
                "persona": {"type": ["string", "null"]},
                "kategori": {"type": ["string", "null"]}
            }
        }
    },
    "required": ["aksi", "argumen", "pembaruan_state"]
}

url = "http://localhost:11434/api/chat"
test_cases = [
    ("sampai jumpa lagi min", "Harus basa_basi + pamit, BUKAN lanjutan_hasil"),
    ("ada yang lebih murah?", "Harus lanjutan_hasil + lebih_murah"),
    ("halo", "Harus sapa")
]

for text, desc in test_cases:
    t0 = time.perf_counter()
    resp = requests.post(url, json={
        "model": "gemma4:e4b",
        "messages": [{"role": "user", "content": f"Pesan: {text}\nState: {{\"produk_tampil\": [1]}}"}],
        "stream": False,
        "format": schema_oneof
    }, timeout=30)
    dur = (time.perf_counter() - t0) * 1000
    print(f"\nTest: '{text}' ({desc}) -> HTTP {resp.status_code} [{dur:.1f}ms]")
    if resp.status_code == 200:
        print("Result:", resp.json()["message"]["content"])
