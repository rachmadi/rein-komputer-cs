import urllib.request, json, time

def test(user_text):
    t0 = time.time()
    prompt = f"Kalimat: '{user_text}'. Apakah kalimat ini mencari atau bertanya spesifikasi/rekomendasi komputer/laptop? Jawab HANYA 'YA' atau 'TIDAK'."
    req_body = {
        "model": "gemma4:e4b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 250, "temperature": 0.0}
    }
    req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        ans = res_data.get("response", "").strip().upper()
        if not ans:
            th = res_data.get("thinking", "").upper()
            if "YA" in th:
                ans = "YA"
        dt = time.time() - t0
        print(f"'{user_text}' -> ans={repr(ans)} in {dt:.2f}s")
        return "YA" in ans

print(test("laptop baterai awet"))
print(test("ada diskon laptop gaming"))
print(test("install apa saja untuk laptop kuliah"))
