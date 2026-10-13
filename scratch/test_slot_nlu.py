# -*- coding: utf-8 -*-
import json
import time
import urllib.request

def test_nlu(user_text: str, pending_question: str | None = None, current_slots: dict | None = None, model: str = "llama3.2:1b"):
    current_slots = current_slots or {}
    prompt = (
        "Kamu adalah Slot-based NLU Dialogue State Tracker untuk asisten toko Bobby Computer.\n"
        "Tugasmu mengekstrak intent dan slot dari pesan pelanggan.\n\n"
        f"Pending Question (pertanyaan bot sebelumnya): {pending_question or 'None'}\n"
        f"Slots Terisi Saat Ini: {json.dumps(current_slots, ensure_ascii=False)}\n"
        f"Pesan Pelanggan: \"{user_text}\"\n\n"
        "Daftar Intent:\n"
        "- \"sapaan\": sapaan awal murni (halo, selamat pagi)\n"
        "- \"tanya_merek_stok\": bertanya ketersediaan merek/stok (ada asus, jual acer)\n"
        "- \"kebutuhan\": menyebutkan peruntukan, aktivitas, persona, spek, atau budget\n"
        "- \"produk_spesifik\": menyebut seri/tipe produk spesifik (Nitro, Legion, dsb)\n"
        "- \"lanjutan\": meminta opsi/rekomendasi (mana?, cuma itu?, yang lain?)\n"
        "- \"meta_protes\": komplain, protes alur, atau kritik spek\n"
        "- \"di_luar_topik\": di luar produk komputer (jam buka, alamat toko, dsb)\n\n"
        "ATURAN:\n"
        "1. Jika ada Pending Question, perlakukan pesan pelanggan sebagai jawaban untuk slot itu!\n"
        "   Contoh: pending 'aktivitas' + pesan 'Buat hiburan' -> intent 'kebutuhan', slot aktivitas='hiburan'.\n"
        "   Contoh: pending 'kebutuhan' + pesan 'Untuk ibu saya yang sudah sepuh' -> slot persona='ibu'.\n"
        "2. Ekstrak persona sesuai kata asli pelanggan (misal 'ibu', 'bapak', 'mama').\n"
        "3. Keluaran HANYA JSON valid:\n"
        "{\"intent\": \"<intent>\", \"slots\": {\"persona\": null, \"aktivitas\": null, \"budget\": null, \"kategori\": null, \"merek\": null}}\n"
    )

    req_data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
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
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    latency = time.perf_counter() - t0
    content = res["message"]["content"]
    parsed = json.loads(content)
    return parsed, latency

if __name__ == "__main__":
    queries = [
        ("Ada asus?", None, {}),
        ("Untuk ibu saya yang sudah sepuh", "kebutuhan", {"merek": "asus"}),
        ("Buat hiburan", "aktivitas", {"merek": "asus", "persona": "ibu"}),
        ("Mana?", "aktivitas", {"merek": "asus", "persona": "ibu", "aktivitas": "hiburan"}),
        ("Kan sudah dibilang buat hiburan", None, {"merek": "asus", "persona": "ibu", "aktivitas": "hiburan"}),
    ]

    for q, pending, slots in queries:
        parsed, lat = test_nlu(q, pending, slots)
        print(f"Pesan: '{q}' | Pending: {pending}")
        print(f"  Latensi: {lat:.3f}s | Parsed: {parsed}")
