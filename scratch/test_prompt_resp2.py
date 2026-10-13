import urllib.request, json

# Test disabling thinking
for body in [
    {"model": "gemma4:e4b", "prompt": "/set nothinking\nKalimat: 'laptop baterai awet'. Apakah mencari spesifikasi laptop? Jawab YA atau TIDAK.", "stream": False, "options": {"num_predict": 10}},
    {"model": "gemma4:e4b", "prompt": "Kalimat: 'laptop baterai awet'. Apakah mencari spesifikasi laptop? Jawab YA atau TIDAK.", "stream": False, "system": "Jangan berpikir. Langsung jawab YA atau TIDAK.", "options": {"num_predict": 10}},
    {"model": "gemma4:e4b", "prompt": "Kalimat: 'laptop baterai awet'. Apakah mencari spesifikasi laptop? Jawab YA atau TIDAK.", "stream": False, "options": {"num_predict": 500, "temperature": 0.0}}
]:
    req = urllib.request.Request('http://localhost:11434/api/generate', data=json.dumps(body).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode('utf-8'))
        print("Body:", body.get("system") or body.get("options"))
        print("Response:", repr(data.get("response")))
        print("Thinking:", repr((data.get("thinking") or "")[:80]))
