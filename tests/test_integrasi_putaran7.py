# -*- coding: utf-8 -*-
"""
tests/test_integrasi_putaran7.py
Tes integrasi multi-giliran untuk memverifikasi Cacat D1–D8 dan Aturan B (Putaran 7).
State dihasilkan secara nyata oleh alur pipeline multi-turn (bukan dict state buatan tangan),
menggunakan SessionPipeline, validator, engine, dan katalog asli.
"""
import unittest
from unittest.mock import patch, MagicMock

from services.session_pipeline import SessionPipeline
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, AtributSpesifikasiEnum, AlasanTidakJelasEnum
)
from core.catalog import Catalog


class TestIntegrasiMultiGiliranPutaran7(unittest.TestCase):
    def setUp(self):
        self.pipeline = SessionPipeline()

    def _execute_turn(self, state: dict, user_msg: str, parser_output: ParserOutput):
        """Menjalankan satu giliran pipeline dengan ParserOutput tertentu dan state dinamis."""
        with patch("services.session_pipeline.parse_user_message", return_value=(parser_output, {"json_valid": True})):
            turn_res, new_state = self.pipeline.process_turn(user_msg, session_state=state)
            return turn_res, new_state

    # -------------------------------------------------------------------------
    # D1: Tanya RAM/CPU/GPU/Harga produk yang baru ditampilkan
    # Nilai HARUS diambil dari katalog nyata, bukan kosong dari formatted_prods.
    # -------------------------------------------------------------------------
    def test_D1_tanya_spesifikasi_membaca_katalog_bukan_formatted_state(self):
        # Giliran 1: Tampilkan laptop lenovo
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", merek="lenovo")
        )
        res1, state1 = self._execute_turn({}, "Cari laptop lenovo", t1_out)
        self.assertEqual(res1.fakta_eksekusi.get("status"), "sukses")
        self.assertTrue(len(state1.get("produk_tampil", [])) > 0)
        top_code = state1["produk_tampil"][0]["kode"]

        # Giliran 2: Tanya spesifikasi RAM produk pertama
        t2_out = ParserOutput(
            aksi=ActionEnum.TANYA_SPESIFIKASI,
            argumen=ActionArguments(produk=[top_code], atribut=AtributSpesifikasiEnum.RAM)
        )
        res2, state2 = self._execute_turn(state1, "Berapa RAM laptop pertama?", t2_out)

        # Harus sukses dan membaca data asli dari katalog (misal 8 GB DDR4 / 16 GB)
        self.assertEqual(res2.fakta_eksekusi.get("status"), "sukses",
                         "D1: tanya_spesifikasi RAM gagal karena membaca formatted_prods kosong di state")
        fakta_items = res2.fakta_eksekusi.get("spesifikasi_produk", [])
        self.assertTrue(len(fakta_items) > 0)
        self.assertIsNotNone(fakta_items[0].get("nilai"), "Nilai RAM tidak boleh None")
        self.assertIn("GB", str(fakta_items[0].get("nilai")), "Nilai RAM harus memuat GB")

    # -------------------------------------------------------------------------
    # D2: Permintaan spek umum / spek lengkap harus mengembalikan ringkasan spek utama
    # bukan atribut 'lainnya' yang memicu 'belum tersedia'.
    # -------------------------------------------------------------------------
    def test_D2_spek_umum_merangkum_spek_utama_katalog(self):
        # Giliran 1: Cari laptop asus
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", merek="asus")
        )
        res1, state1 = self._execute_turn({}, "Cari laptop asus", t1_out)
        top_code = state1["produk_tampil"][0]["kode"]

        # Giliran 2: Minta spek lengkap / spek umum (atribut None)
        t2_out = ParserOutput(
            aksi=ActionEnum.TANYA_SPESIFIKASI,
            argumen=ActionArguments(produk=[top_code], atribut=None)
        )
        res2, state2 = self._execute_turn(state1, "Spek lengkapnya gimana?", t2_out)

        self.assertEqual(res2.fakta_eksekusi.get("status"), "sukses",
                         "D2: Spek umum tidak boleh menghasilkan atribut_tidak_tersedia")
        fakta_items = res2.fakta_eksekusi.get("spesifikasi_produk", [])
        self.assertTrue(len(fakta_items) > 0)
        ringkasan = fakta_items[0].get("ringkasan_spek") or fakta_items[0].get("nilai")
        self.assertIsNotNone(ringkasan, "D2: Harus menyediakan ringkasan spek utama dari katalog")

    # -------------------------------------------------------------------------
    # D3: Standar bawaan tidak boleh mengarang fakta angka (misal RAM 8 GB / SSD 256 GB)
    # untuk produk yang berspesifikasi tinggi (16 GB / 512 GB).
    # -------------------------------------------------------------------------
    def test_D3_evaluasi_spek_tinggi_tidak_mengarang_angka_bawaan(self):
        # Giliran 1: Tampilkan laptop gaming Acer Nitro (KB-L06, RAM 16GB, SSD 512GB)
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", nama_model="nitro")
        )
        res1, state1 = self._execute_turn({}, "Tampilkan laptop acer nitro", t1_out)
        self.assertTrue(any(p["kode"] == "KB-L06" for p in state1.get("produk_tampil", [])))

        # Giliran 2: Evaluasi kecocokan untuk programmer
        t2_out = ParserOutput(
            aksi=ActionEnum.EVALUASI_KECOCOKAN,
            argumen=ActionArguments(produk=["KB-L06"], kebutuhan_teks="programmer software")
        )
        res2, state2 = self._execute_turn(state1, "Kuat gak buat programmer?", t2_out)
        self.assertEqual(res2.fakta_eksekusi.get("status"), "sukses")
        eval_items = res2.fakta_eksekusi.get("evaluasi_produk", [])
        self.assertTrue(len(eval_items) > 0)
        p_eval = eval_items[0]
        # Angka aktual harus 16 GB dan 512 GB dari katalog, BUKAN bawaan 8 GB / 256 GB
        angka = p_eval.get("angka_aktual", {})
        self.assertEqual(angka.get("ram_gb"), 16, "D3: RAM aktual KB-L06 adalah 16GB, bukan bawaan 8GB")
        self.assertEqual(angka.get("ssd_gb"), 512, "D3: SSD aktual KB-L06 adalah 512GB, bukan bawaan 256GB")

    # -------------------------------------------------------------------------
    # D4: Kebutuhan baru di giliran ini wajib menggantikan profil lama di state
    # tidak boleh memakai profil basi secara diam-diam.
    # -------------------------------------------------------------------------
    def test_D4_kebutuhan_baru_menggantikan_profil_basi(self):
        # Giliran 1: Rekomendasi awal untuk administrasi kantoran
        t1_out = ParserOutput(
            aksi=ActionEnum.MINTA_REKOMENDASI,
            argumen=ActionArguments(kebutuhan_teks="administrasi dan pengetikan kantor")
        )
        res1, state1 = self._execute_turn({}, "Butuh laptop buat administrasi kantor", t1_out)
        self.assertIn("P01", state1.get("profil_aktif", "P01"))

        # Giliran 2: Pengguna mengubah kebutuhan menjadi rendering 3D blender
        t2_out = ParserOutput(
            aksi=ActionEnum.EVALUASI_KECOCOKAN,
            argumen=ActionArguments(produk=["KB-L06"], kebutuhan_teks="rendering 3d blender seharian")
        )
        res2, state2 = self._execute_turn(state1, "Kalau buat rendering 3D blender seharian kuat gak?", t2_out)

        # Engine TIDAK BOLEH mengevaluasi berdasarkan P01 (Kantoran)
        self.assertNotEqual(res2.fakta_eksekusi.get("profil_id"), "P01",
                            "D4: Profil kebutuhan baru diabaikan dan engine memakai profil basi P01!")

    # -------------------------------------------------------------------------
    # D5: Penyebutan merek/model eksplisit saat produk tampil memicu cari_produk baru,
    # sedangkan permintaan lanjutan murni ('merek lain') memicu yang_lain.
    # -------------------------------------------------------------------------
    def test_D5_penyebutan_merek_eksplisit_vs_lanjutan_murni(self):
        # Giliran 1: Cari laptop HP
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", merek="hp")
        )
        res1, state1 = self._execute_turn({}, "Cari laptop hp", t1_out)

        # Kasus A: Merek lain murni ("merek lain apa?") -> lanjutan_hasil jenis yang_lain
        t2a_out = ParserOutput(
            aksi=ActionEnum.LANJUTAN_HASIL,
            argumen=ActionArguments(jenis_lanjutan="yang_lain", merek_kecuali="hp")
        )
        res2a, state2a = self._execute_turn(state1, "Merek lain apa?", t2a_out)
        self.assertEqual(res2a.fakta_eksekusi.get("status"), "sukses")
        for p in res2a.fakta_eksekusi.get("produk", []):
            self.assertNotEqual(str(p.get("brand")).lower(), "hp", "D5: Merek HP harus dikecualikan")

        # Kasus B: Sebut merek eksplisit ("Kalo asus ada?") -> cari_produk baru
        t2b_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", merek="asus")
        )
        res2b, state2b = self._execute_turn(state1, "Kalo asus ada?", t2b_out)
        self.assertEqual(res2b.fakta_eksekusi.get("status"), "sukses")
        self.assertTrue(any("asus" in str(p.get("nama")).lower() for p in res2b.fakta_eksekusi.get("produk", [])))

    # -------------------------------------------------------------------------
    # D6: Pergantian kategori mereset slot anggaran, merek, dan filter spek lama
    # -------------------------------------------------------------------------
    def test_D6_ganti_kategori_mereset_anggaran_dan_merek_lama(self):
        # Giliran 1: Cari printer budget 2 juta merek epson
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="printer", max_harga=2000000, merek="epson")
        )
        res1, state1 = self._execute_turn({}, "Cari printer epson budget 2 juta", t1_out)
        self.assertEqual(state1.get("kategori"), "printer")
        self.assertEqual(state1.get("budget"), 2000000)
        self.assertEqual(state1.get("merek"), "epson")

        # Giliran 2: Beralih ke kategori desktop
        t2_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="desktop")
        )
        res2, state2 = self._execute_turn(state1, "Sekarang cari komputer desktop ya", t2_out)
        self.assertEqual(state2.get("kategori"), "desktop")
        # Anggaran 2 juta dan merek epson dari printer TIDAK BOLEH terbawa ke desktop
        self.assertIsNone(state2.get("budget"), "D6: Budget printer 2 juta masih terbawa ke desktop!")
        self.assertIsNone(state2.get("merek"), "D6: Merek epson masih terbawa ke desktop!")

    # -------------------------------------------------------------------------
    # D7: Batas anggaran eksplisit dipatuhi persis; B7 jika tidak ada dalam anggaran
    # -------------------------------------------------------------------------
    def test_D7_batas_anggaran_eksplisit_dipatuhi_dan_b7(self):
        # Giliran 1: Tampilkan laptop lenovo
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", merek="lenovo")
        )
        res1, state1 = self._execute_turn({}, "Cari laptop lenovo", t1_out)

        # Giliran 2: Batas harga di bawah 3 juta (tidak ada laptop lenovo di bawah 3 juta di katalog)
        t2_out = ParserOutput(
            aksi=ActionEnum.LANJUTAN_HASIL,
            argumen=ActionArguments(jenis_lanjutan="lebih_murah", max_harga=3000000)
        )
        res2, state2 = self._execute_turn(state1, "Ada yang di bawah 3 juta gak?", t2_out)

        # Harus mengembalikan B7 (tidak_ada_dalam_anggaran) dengan batas_dipakai = 3000000
        self.assertEqual(res2.fakta_eksekusi.get("status"), "tidak_ada_dalam_anggaran",
                         "D7: Permintaan di bawah 3 juta harus menghasilkan tidak_ada_dalam_anggaran (B7)")
        self.assertEqual(res2.fakta_eksekusi.get("batas_dipakai"), 3000000)

    # -------------------------------------------------------------------------
    # D8: Syarat spesifikasi GPU RTX 3050 dan tipe RAM DDR5 diverifikasi dari katalog
    # -------------------------------------------------------------------------
    def test_D8_verifikasi_katalog_rtx_3050_dan_ddr5(self):
        # Giliran 1: Cari laptop dengan GPU RTX 3050
        t1_out = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori="laptop", gpu="rtx 3050")
        )
        res1, state1 = self._execute_turn({}, "Ada laptop dengan rtx 3050?", t1_out)
        self.assertEqual(res1.fakta_eksekusi.get("status"), "sukses",
                         "D8: Laptop RTX 3050 (KB-L07) ada di katalog tetapi tidak ditemukan")
        prods = res1.fakta_eksekusi.get("produk", [])
        self.assertTrue(any("3050" in str(p.get("gpu", "")) or "3050" in str(p.get("nama", "")) for p in prods))

    # -------------------------------------------------------------------------
    # B14: Evaluasi kecocokan tanpa produk aktif mengembalikan belum_ada_produk
    # tanpa penilaian dan tanpa standar bawaan
    # -------------------------------------------------------------------------
    def test_B14_evaluasi_tanpa_produk_aktif(self):
        t_out = ParserOutput(
            aksi=ActionEnum.EVALUASI_KECOCOKAN,
            argumen=ActionArguments(produk=[], kebutuhan_teks="editing video")
        )
        res, state = self._execute_turn({}, "Cocok gak buat video editing?", t_out)
        self.assertEqual(res.fakta_eksekusi.get("status"), "belum_ada_produk")
        self.assertNotIn("evaluasi_produk", res.fakta_eksekusi)

    # -------------------------------------------------------------------------
    # B15: Atribut tidak dikenal mengembalikan atribut_tidak_tersedia dengan nama atribut
    # -------------------------------------------------------------------------
    def test_B15_atribut_tidak_dikenal_jujur_tidak_tersedia(self):
        t1_out = ParserOutput(aksi=ActionEnum.CARI_PRODUK, argumen=ActionArguments(kategori="laptop"))
        _, state1 = self._execute_turn({}, "Cari laptop", t1_out)

        t2_out = ParserOutput(
            aksi=ActionEnum.TANYA_SPESIFIKASI,
            argumen=ActionArguments(produk=["KB-L01"], atribut=AtributSpesifikasiEnum.LAINNYA)
        )
        # Pada B15, jika atribut spesifik yang ditanyakan tidak ada kolomnya
        res2, _ = self._execute_turn(state1, "Apakah tahan banting militer?", t2_out)
        # Menghasilkan status jujur tanpa data karangan
        self.assertIn(res2.fakta_eksekusi.get("status"), ["sukses", "atribut_tidak_tersedia"])

    # -------------------------------------------------------------------------
    # B16: Produk di luar katalog di evaluasi/spesifikasi menghasilkan padanan
    # -------------------------------------------------------------------------
    def test_B16_produk_di_luar_katalog_menawarkan_padanan(self):
        t_out = ParserOutput(
            aksi=ActionEnum.TANYA_SPESIFIKASI,
            argumen=ActionArguments(produk=["MACBOOK-M3"], atribut=AtributSpesifikasiEnum.HARGA)
        )
        res, _ = self._execute_turn({}, "Berapa harga macbook m3?", t_out)
        self.assertEqual(res.fakta_eksekusi.get("status"), "produk_tidak_di_katalog")
        self.assertTrue("padanan_terdekat" in res.fakta_eksekusi)

    # -------------------------------------------------------------------------
    # B18: Kartu produk dihasilkan untuk SETIAP aksi yang menghasilkan daftar produk
    # -------------------------------------------------------------------------
    def test_B18_kartu_produk_untuk_setiap_aksi_berproduk(self):
        t_out = ParserOutput(aksi=ActionEnum.CARI_PRODUK, argumen=ActionArguments(kategori="laptop"))
        res, _ = self._execute_turn({}, "Cari laptop", t_out)
        self.assertIsNotNone(res.kartu_produk_html, "B18: Kartu produk HTML wajib ada jika aksi menghasilkan produk")
        self.assertIn("[KB-", res.kartu_produk_html, "B18: Header kartu produk wajib memuat [KODE]")

    # -------------------------------------------------------------------------
    # B5: Qdrant/embedding mati menghasilkan status sistem_error
    # -------------------------------------------------------------------------
    def test_B5_qdrant_mati_sistem_error(self):
        with patch("services.action_engine.get_usage_requirements", side_effect=ConnectionError("Qdrant down")):
            t_out = ParserOutput(aksi=ActionEnum.MINTA_REKOMENDASI, argumen=ActionArguments(kategori="laptop", kebutuhan_teks="gaming berat"))
            res, _ = self._execute_turn({}, "Rekomendasi laptop gaming", t_out)
            self.assertEqual(res.fakta_eksekusi.get("status"), "sistem_error",
                             "B5: Gangguan Qdrant wajib menghasilkan fakta status sistem_error")

    # -------------------------------------------------------------------------
    # B10: Ollama timeout menghasilkan status sistem_error
    # -------------------------------------------------------------------------
    def test_B10_ollama_timeout_sistem_error(self):
        with patch("services.llm_parser._call_ollama_chat", side_effect=TimeoutError("Ollama timeout")):
            res, _ = self.pipeline.process_turn("Halo", session_state={})
            self.assertEqual(res.fakta_eksekusi.get("status"), "sistem_error",
                             "B10: Kegagalan koneksi/timeout Ollama wajib menghasilkan fakta status sistem_error")

    # -------------------------------------------------------------------------
    # B17: Keluaran parser rusak setelah 1 reparse menghasilkan alasan tidak_dipahami
    # -------------------------------------------------------------------------
    def test_B17_parser_rusak_fallback_tidak_dipahami(self):
        with patch("services.llm_parser._call_ollama_chat", return_value=(None, False, "bad json", "JSONDecodeError")):
            res, _ = self.pipeline.process_turn("Pesanan tidak jelas", session_state={})
            self.assertEqual(res.fakta_eksekusi.get("status"), "tidak_jelas")
            self.assertEqual(res.fakta_eksekusi.get("alasan"), "tidak_dipahami",
                             "B17: Skema JSON gagal setelah 1 reparse wajib menghasilkan alasan tidak_dipahami")


if __name__ == "__main__":
    unittest.main()
