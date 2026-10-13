import urllib.request, json
prompt = "Kalimat: 'ada diskon laptop gaming'. Apakah kalimat ini mencari atau bertanya spesifikasi/rekomendasi komputer/laptop? Jawab HANYA 'YA' atau 'TIDAK'."
req_body = {'model': 'gemma4:e4b', 'prompt': prompt, 'stream': False, 'options': {'num_predict': 250, 'temperature': 0.0}}
req = urllib.request.Request('http://localhost:11434/api/generate', data=json.dumps(req_body).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as res:
    data = json.loads(res.read().decode('utf-8'))
    print('Response:', repr(data.get('response')))
    print('Thinking:', data.get('thinking'))
