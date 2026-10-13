import urllib.request, json

for q in ["laptop baterai awet", "ada diskon laptop gaming", "install apa saja untuk laptop kuliah", "berapa jam buka toko", "cara bayar cicilan"]:
    prompt = f"Kalimat: '{q}'. Apakah kalimat ini relevan dengan pencarian, pembelian, produk, harga, diskon, atau rekomendasi komputer/laptop? Jawab HANYA 'YA' atau 'TIDAK'."
    req_body = {'model': 'gemma4:e4b', 'prompt': prompt, 'stream': False, 'options': {'num_predict': 250, 'temperature': 0.0}}
    req = urllib.request.Request('http://localhost:11434/api/generate', data=json.dumps(req_body).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode('utf-8'))
        ans = data.get('response', '').strip().upper()
        if not ans:
            th = (data.get('thinking') or '').upper()
            if "YA" in th[-50:]:
                ans = "YA"
            elif "TIDAK" in th[-50:]:
                ans = "TIDAK"
        print(f"'{q}' -> ans={repr(ans)}")
