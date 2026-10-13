# -*- coding: utf-8 -*-
from services.action_engine import ActionEngine, ActionArguments, SlotEnum, get_product_brand
from services.knowledge_service import get_usage_requirements, get_profile_by_id
from services.catalog_search import apply_filters

ae = ActionEngine()
state = {
    'kategori': 'printer',
    'merek': 'canon',
    'kebutuhan_teks': 'cetak dokumen hemat tinta'
}
args = ActionArguments(slot=SlotEnum.KEBUTUHAN, nilai='cetak dokumen hemat tinta')

print('=== TRACE A2 DIAGNOSTIC ===')
# 1. Ambang RAG
reqs = get_usage_requirements('cetak dokumen hemat tinta')
pls = reqs.get('profil', [])
print(f'Tahap 1 - RAG Profil: Ditemukan {len(pls)} profil di atas ambang: {[p.get("profil_id") for p in pls]}')

# 2. Filter Kategori
kategori = state['kategori']
cands_cat = [p for p in ae.catalog.products if p.get('kategori', '').lower() == kategori.lower()]
print(f'Tahap 2 - Filter Kategori ({kategori}): {len(cands_cat)} produk')

# 3. Filter Merek
merek = state['merek']
cands_merek = [p for p in cands_cat if merek == get_product_brand(p) or merek in str(p.get('nama', '')).lower()]
print(f'Tahap 3 - Filter Merek ({merek}): {len(cands_merek)} produk: {[p.get("nama") for p in cands_merek]}')

# 4. Filter Profil (apply_filters)
prof_id = pls[0]['profil_id'] if pls else None
prof_data = get_profile_by_id(prof_id)
filters = prof_data.get('filter', [])
print(f'Tahap 4 - Profil {prof_id} ({prof_data.get("judul")}) dengan filter: {filters}')

cands_passed = []
for p in cands_merek:
    passed, reason, penalty, report = apply_filters(p, filters)
    print(f'  Produk {p.get("nama")}: passed={passed}, reason={reason}, report={report}')
    if passed:
        cands_passed.append(p)
print(f'Jumlah kandidat lolos apply_filters: {len(cands_passed)}')

# Execute _handle_jawab_pertanyaan_bot
res = ae._handle_jawab_pertanyaan_bot(args, state)
print('Hasil _handle_jawab_pertanyaan_bot:')
print('  Aksi:', res.aksi)
print('  Status fakta:', res.fakta.get('status'))
print('  Pesan fakta:', res.fakta.get('pesan'))
print('  Produk list count:', len(res.produk_list))
