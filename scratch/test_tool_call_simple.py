# -*- coding: utf-8 -*-
import urllib.request
import json

# Simulasi putaran 1: search_catalog dipanggil
tool_result = json.dumps({
    "status": "success",
    "products": [
        {
            "kode": "KB-L10",
            "nama": "Lenovo Legion Pro 5 16",
            "harga": "Rp24.999.000",
            "cpu": "Intel Core i7-14700HX",
            "gpu": "NVIDIA GeForce RTX 4060 8 GB",
            "ram": "16 GB DDR5",
            "storage": "1 TB NVMe SSD",
            "display": "16 inci WQXGA IPS 240 Hz",
            "keunggulan": "Sangat ideal untuk menjalankan model LLM lokal dan komputasi AI berat."
        },
        {
            "kode": "KB-L09",
            "nama": "ASUS TUF Gaming A15",
            "harga": "Rp17.499.000",
            "cpu": "AMD Ryzen 7 7735HS",
            "gpu": "NVIDIA GeForce RTX 4050 6 GB",
            "ram": "16 GB DDR5",
            "storage": "512 GB NVMe SSD",
            "display": "15,6 inci FHD IPS 144 Hz"
        }
    ]
})

messages = [
    {
        "role": "system",
        "content": (
            "Kamu adalah Bobby CS dari Bobby Computer toko komputer resmi. "
            "ATURAN: Jelaskan produk secara ramah, ringkas, dan jelas berdasarkan data resmi dari tool. "
            "Jika pelanggan menanyakan detail spesifikasi ('speknya dong'), bacakan spesifikasi lengkap produk tersebut tanpa menanyakan budget."
        )
    },
    {"role": "user", "content": "Kadang main LLM lokal juga"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "call_01", "function": {"name": "search_catalog", "arguments": {"query": "laptop untuk LLM lokal"}}}
        ]
    },
    {"role": "tool", "content": tool_result},
    {
        "role": "assistant",
        "content": "Untuk menjalankan LLM lokal, kami sangat merekomendasikan **Lenovo Legion Pro 5 16** (RTX 4060 8 GB) atau **ASUS TUF Gaming A15** (RTX 4050 6 GB) Kak. Keduanya punya VRAM dan RAM besar yang mumpuni untuk AI lokal."
    },
    {"role": "user", "content": "Speknya dong"}
]

payload = {
    "model": "gemma4:e4b",
    "messages": messages,
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "search_catalog",
                "description": "Mencari produk atau spesifikasi di katalog Bobby Computer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }
    ],
    "stream": False
}

req = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    msg = res.get("message", {})
    print("THINKING:", msg.get("thinking"))
    print("TOOL CALLS:", msg.get("tool_calls"))
    print("CONTENT:", msg.get("content"))
