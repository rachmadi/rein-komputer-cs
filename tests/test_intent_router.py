import pytest
from services.intent_router import classify_intent

def test_intent_router_classes():
    # 1. Sapaan
    assert classify_intent("halo") == "sapaan"
    assert classify_intent("Hai kak") == "sapaan"
    assert classify_intent("selamat pagi") == "sapaan"
    assert classify_intent("p") == "sapaan"

    # 2. Kategori-saja (tidak boleh masuk retrieval profil)
    assert classify_intent("laptop") == "kategori-saja"
    assert classify_intent("ada laptop?") == "kategori-saja"
    assert classify_intent("mau cari desktop") == "kategori-saja"
    assert classify_intent("printer") == "kategori-saja"
    assert classify_intent("ada monitor?") == "kategori-saja"

    # 3. Kebutuhan-jelas
    assert classify_intent("laptop buat edit video 4k") == "kebutuhan-jelas"
    assert classify_intent("butuh komputer buat kasir toko") == "kebutuhan-jelas"
    assert classify_intent("laptop kuliah teknik sipil arsitektur") == "kebutuhan-jelas"
    assert classify_intent("laptop RAM 128GB") == "kebutuhan-jelas"
    assert classify_intent("laptop baterai awet") == "kebutuhan-jelas"

    # 4. Produk-spesifik
    assert classify_intent("Acer Nitro V 15 ada?") == "produk-spesifik"
    assert classify_intent("KB-L10") == "produk-spesifik"
    assert classify_intent("ASUS TUF Gaming A15") == "produk-spesifik"
    assert classify_intent("Lenovo Legion Pro 5 ready?") == "produk-spesifik"

    # 5. Lanjutan
    assert classify_intent("cuma itu?") == "lanjutan"
    assert classify_intent("ada yang lain?") == "lanjutan"
    assert classify_intent("yang lain?") == "lanjutan"
    assert classify_intent("ada yang lebih murah?") == "lanjutan"
    assert classify_intent("yang ASUS aja") == "lanjutan"

    # 6. Meta
    assert classify_intent("Dari mana kamu tahu kebutuhanku?") == "meta"
    assert classify_intent("kok bisa tahu kebutuhanku?") == "meta"
    assert classify_intent("kenapa nawarin yang ini?") == "meta"
    assert classify_intent("kamu ini robot ya?") == "meta"

    # 7. Di-luar-topik
    assert classify_intent("jam buka toko jam berapa?") == "di-luar-topik"
    assert classify_intent("alamat tokonya dimana?") == "di-luar-topik"
    assert classify_intent("bisa bayar cicilan?") == "di-luar-topik"
    assert classify_intent("garansi resmi berapa tahun?") == "di-luar-topik"
