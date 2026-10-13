import sys

with open("d:/RAG/dokumen/Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md", "a", encoding="utf-8") as f:
    f.write("""

## OOD1 — Info Toko, Lokasi, dan Jam Operasional

- **ID:** OOD1 | **Tag katalog:** info_toko | **Perangkat:** none
- **Kata kunci pelanggan:** jam buka, alamat, lokasi, toko dimana, hari minggu buka, tutup jam berapa, cabang, parkir, denah
- **Kebutuhan/Aktivitas:** Menanyakan informasi operasional dan fisik toko Bobby Computer.
- **Karakteristik yang dicari:** Informasi lokasi dan jadwal.

- **Tipe:** di_luar_topik

- **Filter minimum:** tidak_ada
- **Catatan:** Ini adalah chunk di luar domain (OOD) untuk menyaring pertanyaan tentang operasional toko. Arahkan ke staf jika perlu.

---
## OOD2 — Garansi, Servis, dan Purna Jual

- **ID:** OOD2 | **Tag katalog:** servis | **Perangkat:** none
- **Kata kunci pelanggan:** garansi berapa lama, servis laptop rusak, ganti baterai, klaim garansi, garansi resmi, perbaikan, layanan purna jual, service center
- **Kebutuhan/Aktivitas:** Menanyakan layanan purna jual, perbaikan perangkat rusak, atau klaim garansi.
- **Karakteristik yang dicari:** Informasi layanan perbaikan.

- **Tipe:** di_luar_topik

- **Filter minimum:** tidak_ada
- **Catatan:** Ini adalah chunk OOD untuk pertanyaan tentang garansi dan perbaikan.

---
## OOD3 — Pembayaran, Cicilan, dan Pengiriman

- **ID:** OOD3 | **Tag katalog:** transaksi | **Perangkat:** none
- **Kata kunci pelanggan:** bisa cicil, kredit, paylater, tokopedia, shopee, ongkir, gratis ongkir, bayar pakai kartu, pengiriman hari ini, cod, gosend
- **Kebutuhan/Aktivitas:** Menanyakan metode pembayaran, fasilitas cicilan, atau layanan pengiriman pesanan.
- **Karakteristik yang dicari:** Metode transaksi.

- **Tipe:** di_luar_topik

- **Filter minimum:** tidak_ada
- **Catatan:** Chunk OOD untuk memfasilitasi filter pertanyaan pembayaran dan logistik.

---
""")
