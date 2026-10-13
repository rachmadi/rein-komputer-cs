# -*- coding: utf-8 -*-
import json

with open('scratch/replay_model_gemma_sebelum_p12.json', 'r', encoding='utf-8') as f:
    giliran = json.load(f)['giliran']

for item in giliran:
    n = item.get('n')
    if 26 <= n <= 33:
        b = item.get('baru', {})
        balasan = b.get('balasan', '')
        print(f"Turn {n}: user={repr(item.get('user'))} | aksi={b.get('aksi')} | status={b.get('status_fakta')} | prods={item.get('produk_tampil')} | state={item.get('state')} | balasan={repr(balasan[:80])}")
