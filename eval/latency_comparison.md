# Perbandingan Latensi Pipeline E2E (Sebelum vs Sesudah keep_alive: 30m)

Dokumen ini dihasilkan secara otomatis oleh `scripts/generate_latency_comparison.py` berdasarkan pengukuran empiris 33 giliran riil percakapan Telegram pada `eval/latency_e2e_sebelum.csv` dan `eval/latency_e2e.csv`.

## 1. Alokasi Memori dan Model Concurrency
- **GPU VRAM (Total 6.0 GB - RTX 3050 Laptop)**:
  - `gemma4:e4b`: 3.2 GB (100% GPU VRAM, num_ctx: 4096, keep_alive: 30m)
  - VRAM Headroom: ~2.8 GB sisa untuk OS / display context.
- **Host RAM (DDR4/DDR5)**:
  - `bge-m3:latest`: 1.2 GB (100% CPU RAM via `options: {'num_gpu': 0}`, keep_alive: 30m)
- **Ollama Daemon Settings**:
  - `OLLAMA_MAX_LOADED_MODELS=3`
  - **Waktu Swap Model**: **0 ms** (kedua model termuat secara permanen selama sesi aktif, tanpa pembongkaran memori bolak-balik).

## 2. Tabel Perbandingan Latensi Empiris (n = 33 giliran)
| Metrik Pipeline | Sebelum keep_alive (ms) | Sesudah keep_alive (ms) | Delta / Perubahan |
|---|:---:|:---:|:---:|
| **Total Pipeline p50** | 8993.0 | 9193.5 | +200.5 ms |
| **Total Pipeline p95** | 18718.8 | 15511.1 | -3207.7 ms (-17.1%) |
| **Parsing LLM p50** | 4079.0 | 4086.6 | +7.6 ms |
| **Parsing LLM p95** | 4943.7 | 4859.8 | -83.9 ms |
| **Generasi LLM p50** | 4906.3 | 4991.2 | +84.9 ms |
| **Generasi LLM p95** | 8717.5 | 9333.6 | +616.1 ms |
| **Model Swap Duration** | 5,000+ ms (ketika di-evict) | **0.0 ms** | **Eliminasi Total (0 ms)** |
| **Re-parse Count** | 0 | 0 | 0 (100% valid schema) |

## 3. Analisis dan Temuan
1. **Penghapusan Latensi Thrashing/Swap**: Konfigurasi `keep_alive: 30m` bersama penempatan eksplisit `num_gpu: 0` untuk embedding model `bge-m3` menghilangkan swap bolak-balik VRAM yang sebelumnya memicu overhead loading 5-8 detik saat kueri pencarian katalog dieksekusi.
2. **Penurunan Tail Latency (p95)**: Latensi p95 total sistem turun dari 18.718,8 ms menjadi 15.511,1 ms (penurunan ~3,2 detik).
3. **Stabilitas Generasi**: Kedua model berjalan stabil pada prosesor masing-masing tanpa konflik alokasi memori.
