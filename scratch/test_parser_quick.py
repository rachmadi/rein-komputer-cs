import sys; sys.path.append('.')
import urllib.request, json, time
from services.schema_actions import ParserOutput

schema = ParserOutput.model_json_schema()

test_cases = [
    ('halo', None, None),
    ('ada asus?', None, None),
    ('Buat hiburan', 'aktivitas', None),
    ('Mana?', None, {'kebutuhan_teks': 'hiburan nonton'}),
    ('Emang spek segitu cukup?', None, {'produk_tampil': [{'no': 1, 'kode': 'KB-L01'}]}),
    ('Yang tanya HP 14 siapa?', None, None)
]

sys_prompt = '''Kamu adalah NLU Parser untuk customer care Bobby Computer.
Tugas: terjemahkan pesan pelanggan menjadi aksi terstruktur JSON.
Aksi yang tersedia:
- sapa: sapaan pembuka
- cari_produk: mencari produk/merek/spek eksplisit
- minta_rekomendasi: kebutuhan sudah jelas untuk rekomendasi
- jawab_pertanyaan_bot: menjawab pending_question bot
- evaluasi_kecocokan: tanya kecocokan spek produk yang tampil ('cukup gak?', 'bagus gak?')
- bandingkan: bandingkan beberapa produk
- lanjutan_hasil: opsi lebih murah, lebih mahal, yang lain
- tanya_info_toko: tanya garansi, servis, toko, alamat
- perbaiki_percakapan: protes, koreksi, keluhan bot salah paham ('kok malah...', 'siapa yang tanya...')
- basa_basi: terima kasih, pamit
- tidak_jelas: maksud tidak jelas

Aturan:
1. Jika ada pending_question dan pelanggan menjawabnya, gunakan jawab_pertanyaan_bot atau minta_rekomendasi.
2. Jika pelanggan mengeluh, menyindir, atau menegur bot, gunakan perbaiki_percakapan.
3. Jika bertanya apakah spek cukup atau produk bagus, gunakan evaluasi_kecocokan.
'''

few_shots = [
    {'role': 'user', 'content': 'Pesan: "halo"\nState: {"pending_question": null}'},
    {'role': 'assistant', 'content': json.dumps({'aksi': 'sapa', 'argumen': {}, 'pembaruan_state': {}})},
    {'role': 'user', 'content': 'Pesan: "ada asus?"\nState: {"pending_question": null}'},
    {'role': 'assistant', 'content': json.dumps({'aksi': 'cari_produk', 'argumen': {'merek': 'asus', 'kategori': 'laptop'}, 'pembaruan_state': {}})},
    {'role': 'user', 'content': 'Pesan: "Buat hiburan"\nState: {"pending_question": "aktivitas"}'},
    {'role': 'assistant', 'content': json.dumps({'aksi': 'jawab_pertanyaan_bot', 'argumen': {'slot': 'aktivitas', 'nilai': 'hiburan (nonton, browsing)'}, 'pembaruan_state': {'kebutuhan_teks': 'hiburan'}})},
    {'role': 'user', 'content': 'Pesan: "Mana?"\nState: {"pending_question": null, "slot_diketahui": {"kebutuhan_teks": "hiburan"}}'},
    {'role': 'assistant', 'content': json.dumps({'aksi': 'minta_rekomendasi', 'argumen': {'kebutuhan_teks': 'hiburan'}, 'pembaruan_state': {}})},
    {'role': 'user', 'content': 'Pesan: "Emang spek segitu cukup?"\nState: {"produk_tampil": [{"kode": "KB-L01"}], "slot_diketahui": {"kebutuhan_teks": "hiburan"}}'},
    {'role': 'assistant', 'content': json.dumps({'aksi': 'evaluasi_kecocokan', 'argumen': {'produk': ['KB-L01'], 'kebutuhan_teks': 'hiburan'}, 'pembaruan_state': {}})},
    {'role': 'user', 'content': 'Pesan: "Yang tanya HP 14 siapa?"\nState: {}'},
    {'role': 'assistant', 'content': json.dumps({'aksi': 'perbaiki_percakapan', 'argumen': {'rujukan': 'HP 14'}, 'pembaruan_state': {}})}
]

for msg, pending, state in test_cases:
    st_dict = {'pending_question': pending}
    if state: st_dict.update(state)
    t0 = time.perf_counter()
    req_data = {
        'model': 'gemma4:e4b',
        'messages': [
            {'role': 'system', 'content': sys_prompt},
            *few_shots,
            {'role': 'user', 'content': f'Pesan: "{msg}"\nState: {json.dumps(st_dict)}'}
        ],
        'format': schema,
        'stream': False,
        'think': False,
        'options': {'temperature': 0, 'num_predict': 120}
    }
    req = urllib.request.Request(
        'http://localhost:11434/api/chat',
        data=json.dumps(req_data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    res = json.loads(resp.read().decode('utf-8'))
    dt = (time.perf_counter() - t0) * 1000
    print(f'Msg: {msg} | Res: {res["message"]["content"]} | Latency: {dt:.1f}ms')
