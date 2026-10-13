import json

with open('scratch/uji_p28_live37_false.json', 'r', encoding='utf-8') as f:
    df_false = json.load(f)
with open('scratch/uji_p28_live37_true.json', 'r', encoding='utf-8') as f:
    df_true = json.load(f)

target_queries = [
    'Jual laptop untuk desain gak?',
    'Kasih aku spek ROG tadi deh sama gambarnya',
    'Gambarnya mana?',
    'Kalo desktop untuk desain 3D, apa rekomendasimu?',
    'Gak ada yang ram 32 GB?',
    'ROG itu bukannya untuk gaming?',
    'Baiklah. DAri model yang kamu tawarkan, mana yang bisa upgrade ram?',
    'Kasih rekomendasi',
    'Lihat spek ecotank deh. Kalo ada sama gambarnya',
    'Di mana aku bisa lihat katalog kamu?',
    'Sama Reni kan?'
]

extracted = []
for q in target_queries:
    q_data = {'query': q, 'cases': []}
    for var_label, data in [('False', df_false), ('True', df_true)]:
        for r in data['runs']:
            rep = r['rep']
            matched_turn = None
            for t in r['turns']:
                if q.lower() in t['user_msg'].lower():
                    matched_turn = t
                    break
            if matched_turn:
                # Format arguments of tool calls cleanly
                args_summary = []
                for tc in matched_turn.get('tool_calls_detail', []):
                    fn = tc.get('nama')
                    ar = tc.get('argumen', {})
                    args_summary.append(f"{fn}({json.dumps(ar, ensure_ascii=False)})")
                arg_str = "; ".join(args_summary) if args_summary else "-"

                q_data['cases'].append({
                    'varian': f"ATURAN_LAYANAN_P28={var_label}",
                    'ulangan': rep,
                    'user_msg': matched_turn['user_msg'],
                    'turn_idx': matched_turn['turn'],
                    'tools_called': matched_turn['tools_called'],
                    'argumen_alat': arg_str,
                    'foto_dikirim': matched_turn['foto_dikirim'],
                    'balasan_verbatim': matched_turn['balasan_verbatim']
                })
    extracted.append(q_data)

with open('scratch/uji_p28_tabel_11_turns.json', 'w', encoding='utf-8') as f:
    json.dump(extracted, f, ensure_ascii=False, indent=2)

print('Extracted successfully, total target queries:', len(extracted))
for item in extracted:
    print(f"Query: {item['query']} -> found {len(item['cases'])} cases")
