# -*- coding: utf-8 -*-
import sys
sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')
import requests
import json

test_schemas = {}

# Test A: standard object with oneOf inside properties
test_schemas["oneOf_inside_properties"] = {
    "type": "object",
    "properties": {
        "aksi": {"type": "string", "enum": ["lanjutan_hasil", "basa_basi"]},
        "argumen": {
            "type": "object",
            "oneOf": [
                {
                    "properties": {
                        "jenis": {"type": "string", "enum": ["lebih_murah", "lebih_mahal", "yang_lain", "filter_tambahan"]}
                    },
                    "required": ["jenis"]
                },
                {
                    "properties": {
                        "jenis": {"type": "string", "enum": ["terima_kasih", "pamit", "lainnya"]}
                    },
                    "required": ["jenis"]
                }
            ]
        }
    },
    "required": ["aksi", "argumen"]
}

# Test B: separate action-specific fields in argumen
test_schemas["separate_specific_fields"] = {
    "type": "object",
    "properties": {
        "aksi": {"type": "string", "enum": ["lanjutan_hasil", "basa_basi"]},
        "argumen": {
            "type": "object",
            "properties": {
                "jenis_lanjutan": {"type": "string", "enum": ["lebih_murah", "lebih_mahal", "yang_lain", "filter_tambahan"]},
                "jenis_basa_basi": {"type": "string", "enum": ["terima_kasih", "pamit", "lainnya"]}
            }
        }
    },
    "required": ["aksi", "argumen"]
}

# Test C: oneOf at top level with type object
test_schemas["top_level_oneOf"] = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "aksi": {"const": "lanjutan_hasil"},
                "argumen": {
                    "type": "object",
                    "properties": {
                        "jenis": {"type": "string", "enum": ["lebih_murah", "lebih_mahal", "yang_lain", "filter_tambahan"]}
                    },
                    "required": ["jenis"]
                }
            },
            "required": ["aksi", "argumen"]
        },
        {
            "properties": {
                "aksi": {"const": "basa_basi"},
                "argumen": {
                    "type": "object",
                    "properties": {
                        "jenis": {"type": "string", "enum": ["terima_kasih", "pamit", "lainnya"]}
                    },
                    "required": ["jenis"]
                }
            },
            "required": ["aksi", "argumen"]
        }
    ]
}

url = "http://localhost:11434/api/chat"

for name, s in test_schemas.items():
    print(f"\n--- Testing Schema: {name} ---")
    payload = {
        "model": "gemma4:e4b",
        "messages": [
            {"role": "user", "content": "Pesan: sampai jumpa lagi min"}
        ],
        "stream": False,
        "format": s
    }
    resp = requests.post(url, json=payload, timeout=30)
    print("HTTP:", resp.status_code)
    if resp.status_code == 200:
        c = resp.json()["message"]["content"]
        print("Output:", c)
