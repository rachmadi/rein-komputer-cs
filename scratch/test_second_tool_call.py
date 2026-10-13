# -*- coding: utf-8 -*-
import urllib.request
import json

system_prompt = (
    "Kamu adalah Bobby CS dari toko komputer resmi 'Bobby Computer' (menjual laptop, desktop PC, printer, monitor).\n"
    "Karakter: Ramah, santun, solutif, to the point, panggil pelanggan 'Kak'.\n\n"
    "ATURAN UTAMA:\n"
    "1. WAJIB PANGGIL TOOL: Setiap kali pelanggan membahas perangkat, kebutuhan komputasi, mencari rekomendasi, atau menanyakan tipe/spesifikasi/harga produk, KAMU WAJIB memanggil tool 'search_catalog' terlebih dahulu!\n"
    "2. JANGAN PERNAH menolak, mengatakan harus cek sistem manual, atau mendesak menanyakan budget pelanggan jika kamu belum memanggil tool. Cek katalog dulu!\n"
    "3. BACAKAN DATA RESMI: Setelah tool mengembalikan data produk, jelaskan spesifikasi utama (CPU, GPU, RAM, Layar) dan harga resminya secara jelas, ringkas, dan ramah (2-3 kalimat saja).\n"
    "4. DILARANG MENGARANG harga atau produk di luar data yang diberikan tool.\n"
    "5. GAYA BAHASA: Bicaralah alami seperti manusia CS toko. DILARANG KERAS menuliskan teks meta dalam kurung seperti '*(Sistem bot...)*' atau '*(Melampirkan foto...)*'.\n"
    "6. JANGAN mengulang salam pembuka ('Halo Kak', 'Selamat datang') jika percakapan sudah berjalan."
)

history = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "Ada asus?"},
    {"role": "assistant", "content": "Wah, banyak sekali produk dari ASUS, Kak! Ada ExpertCenter, ROG Strix, dan Vivobook 14."},
    {"role": "user", "content": "Laptop"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "call_1", "function": {"name": "search_catalog", "arguments": {"query": "laptop"}}}
        ]
    },
    {
        "role": "tool",
        "content": json.dumps({
            "status": "success",
            "products": [
                {"nama": "Lenovo IdeaCentre Mini 01", "kategori": "desktop", "harga": "Rp8.999.000"},
                {"nama": "ASUS ExpertCenter D500 Tower", "kategori": "desktop", "harga": "Rp9.899.000"}
            ]
        })
    }
]

payload = {
    "model": "gemma4:e4b",
    "messages": history,
    "stream": False
}
req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as resp:
    res = json.loads(resp.read().decode("utf-8"))

msg = res.get("message", {})
print("TOOL CALLS IN RES2:", msg.get("tool_calls"))
print("CONTENT REPR:", repr(msg.get("content")))
