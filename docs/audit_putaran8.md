# Laporan Audit Putaran 8 — ReIn Komputer

Dokumen audit ini menyajikan fakta teknis murni tanpa pembelaan atas proses dan artefak pada Putaran 8, sebagai dasar fondasi integritas Putaran 9.

---

## 1. Audit Riwayat Git & Entri Amend (0.2a)

### Output `git reflog` Sejak Tag `sebelum-putaran8`
```text
1bcb755 HEAD@{0}: commit (amend): putaran8-tahap5-laporan
681d2a0 HEAD@{1}: commit: putaran8-tahap5-laporan
45dbfa6 HEAD@{2}: commit: putaran8-tahap4-eval
171aa1c HEAD@{3}: commit (amend): putaran8-tahap3-akar
f9b101b HEAD@{4}: commit (amend): putaran8-tahap3
bdc8f14 HEAD@{5}: commit (amend): putaran8-tahap3
2bcedfc HEAD@{6}: commit: putaran8-tahap3
906f8ba HEAD@{7}: commit: putaran8-tahap2-tes-merah
e25d064 HEAD@{8}: commit: putaran8-tahap1-label
dad9274 HEAD@{9}: commit: putaran7-tahap6-laporan (tag: sebelum-putaran8)
```

### Daftar Entri `commit (amend)`
Tercatat 4 kali operasi amend selama Putaran 8:
1. `bdc8f14 HEAD@{5}`: commit (amend) putaran8-tahap3
2. `f9b101b HEAD@{4}`: commit (amend) putaran8-tahap3
3. `171aa1c HEAD@{3}`: commit (amend) putaran8-tahap3-akar (dijalankan setelah hasil pengujian integrasi terlihat)
4. `1bcb755 HEAD@{0}`: commit (amend) putaran8-tahap5-laporan

---

## 2. Audit Integritas Label Dev8 (0.2b)

### Output `git diff e25d064 --stat -- eval/dev_multi_putaran8.jsonl`
```text
 eval/dev_multi_putaran8.jsonl | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)
```

### Diff Lengkap `eval/dev_multi_putaran8.jsonl` sejak Commit `e25d064`
```diff
--- a/eval/dev_multi_putaran8.jsonl
+++ b/eval/dev_multi_putaran8.jsonl
@@ -8,3 +8,3 @@
-{"id": "conv-dev8-08", ... "t_idx": 3, "asersi": {"nilai_spek_wajib": {"harga": "Rp1.950.000"}, ...}}
+{"id": "conv-dev8-08", ... "t_idx": 3, "asersi": {"nilai_spek_wajib": {"harga": "Rp1.699.000"}, ...}}
-{"id": "conv-dev8-09", ... "t_idx": 2, "asersi": {"nilai_spek_wajib": {"layar": "15.6 inci Full HD 144Hz"}, ...}}
+{"id": "conv-dev8-09", ... "t_idx": 2, "asersi": {"nilai_spek_wajib": {"layar": "144 Hz"}, ...}}
-{"id": "conv-dev8-10", ... "t_idx": 3, "asersi": {"nilai_spek_wajib": {"storage": "SSD 512 GB"}, ...}}
+{"id": "conv-dev8-10", ... "t_idx": 3, "asersi": {"nilai_spek_wajib": {"storage": "512 GB"}, ...}}
```

### Jawaban 0.2b
**YA**, berkas label `eval/dev_multi_putaran8.jsonl` telah dimodifikasi setelah commit label `e25d064`.
Sesuai aturan Putaran 9:
- `eval/dev_multi_putaran8.jsonl` **HANYA** digunakan sebagai set uji regresi.
- `eval/dev_multi_putaran8.jsonl` **DIKECUALIKAN** dari syarat kelulusan gerbang G7 (tidak menjadi penentu kelulusan).

---

## 3. Audit Perubahan Kode Komponen `services/` (0.2c)

### Output `git diff --numstat sebelum-putaran8..HEAD -- services/`
```text
89	6	services/action_engine.py
30	1	services/grounding_checker.py
9	0	services/llm_generator.py
83	13	services/llm_parser.py
30	0	services/session_pipeline.py
86	9	services/validator.py
```
Total baris perubahan: 327 baris ditambahkan, 29 baris dihapus (+298 net across services).

---

## 4. Audit Kesamaan N-Gram & Frasa Prompt vs Eval/Tests (0.2d)

Pemeriksaan rangkaian 4 kata dan frasa ≥12 karakter yang sama antara `services/llm_parser.py` dan seluruh berkas di `eval/` serta `tests/`:

1. **Rangkaian Sama dengan Dataset Evaluasi**:
   - `'yang posisinya di bawah'`: Muncul di few-shot `llm_parser.py` dan pada baris 4 `eval/parse_frozen_putaran8.csv`.
   - `'rujukan_produk 1 atribut harga'`: Muncul di prompt/few-shot dan di `eval/parse_frozen_putaran8.csv`.
   - `'opsi alternatif lain yang'`: Muncul di prompt parser dan di `eval/dev_multi_putaran7.jsonl` serta `eval/dev_multi_putaran7_koreksi.jsonl`.
   - `'rujukan_produk 1 kebutuhan_teks rendering'`: Muncul di parser dan di `eval/dev_probe_putaran6.csv`.
   - `'daftar yang sedang tampil'`: Muncul di prompt parser dan di `eval/replay_putaran8.jsonl`.

2. **Frasa Domain dalam Few-Shot Putaran 8**:
   - Frasa `"animasi blender"`, `"render 3D"`, `"kasir toko"` digunakan di few-shot sintetis Putaran 8 sementara frasa/kebutuhan yang sangat mirip juga menjadi target evaluasi pada set pengujian beku.

**Tindak Lanjut Putaran 9 (Tahap 2.3)**:
Seluruh few-shot sintetis pada `services/llm_parser.py` akan ditulis ulang total dari nol dengan struktur dan perbendaharaan kata yang sama sekali baru, tanpa frasa di atas, dan tanpa tumpang tindih 4-gram dengan seluruh berkas di `eval/` maupun tes smoke.

---

## 5. Audit Penggunaan Atribut `lainnya` dan Atribut Kosong (0.2e)

Pemetaan atribut `lainnya` dan atribut kosong di seluruh sistem:

1. **`services/action_engine.py:823`**:
   - Kode: `attr = args.atribut or AtributSpesifikasiEnum.LAINNYA`
   - Masalah: Jika pelanggan tidak menyebut atribut (`args.atribut is None`, misalnya "speknya gimana?"), sistem memaksakan nilainya menjadi `LAINNYA`.
2. **`services/action_engine.py:907–910`**:
   - Kode:
     ```python
     elif attr == AtributSpesifikasiEnum.LAINNYA:
         val = clean_specs(p) or f"{p.get('cpu', '')} | {p.get('ram', '')} | {p.get('storage', '')} | {p.get('display', '')}"
     ```
   - Masalah (Akar Masalah F3): `LAINNYA` digunakan sekaligus untuk dua arti yang berlawanan:
     - Permintaan spesifikasi umum / lengkap (harus dijawab ringkasan spek utama katalog).
     - Permintaan atribut tak dikenal / tidak ada di katalog (harus dijawab sesuai B15: "datanya belum ada di sistem kami" + kontak staf, bukan dijawab dengan spek lain).
3. **`services/llm_parser.py:72`**:
   - Mendaftarkan `'lainnya'` dalam daftar atribut spesifikasi.
4. **`tests/test_integrasi_putaran7.py:74, 253`**:
   - Kode tes mempassing `atribut=AtributSpesifikasiEnum.LAINNYA` dengan ekspektasi ringkasan spek umum.
   - Pengecualian Aturan Keras 8: Tes ini bertentangan dengan B15 dan akan diperbarui agar `args.atribut = None` untuk spek umum, sedangkan `atribut = AtributSpesifikasiEnum.LAINNYA` wajib menghasilkan penolakan B15 (`atribut_tidak_tersedia`).
