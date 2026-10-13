#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Putar ulang percakapan nyata dari logs/chat_history.jsonl dengan model LLM tertentu.

Tujuan: membandingkan cara berpikir dua model pada masukan yang SAMA, tanpa mengubah kode bot.
Skrip hanya membaca log, memakai pipeline apa adanya, dan menulis hasil ke scratch/replay_model_<label>.json.

Pemakaian (dari D:\\RAG, Telegram bot sebaiknya dihentikan dulu):
    .\\.venv\\Scripts\\python.exe scratch\\replay_model.py gemma gemma4:e4b
    .\\.venv\\Scripts\\python.exe scratch\\replay_model.py qwen qwen3:8b

Opsi:
    --dari 2026-10-10T15:53   awal jendela waktu log (UTC lokal seperti tertulis di log)
    --sampai 2026-10-10T23:59 akhir jendela
    --bebas                   riwayat dari balasan model itu sendiri (percakapan bercabang);
                              tanpa opsi ini, riwayat memakai balasan ASLI sehingga setiap giliran
                              menerima konteks yang sama persis dengan sesi nyata.
    --timeout 300             batas waktu tiap panggilan Ollama (detik), dilonggarkan agar model
                              yang lebih lambat tidak dianggap gagal.
Model parser dan generator sama-sama diganti ke model yang dipilih. Penyematan tetap bge-m3.
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ap = argparse.ArgumentParser()
ap.add_argument("label")
ap.add_argument("model")
ap.add_argument("--dari", default="2026-10-10T15:53")
ap.add_argument("--sampai", default="2026-10-10T23:59")
ap.add_argument("--bebas", action="store_true")
ap.add_argument("--timeout", type=float, default=300.0)
ap.add_argument("--katalog", default=None, help="Path ke berkas database katalog SQLite alternatif")
args = ap.parse_args()

if args.katalog:
    os.environ["DB_PATH"] = args.katalog

# Model harus ditetapkan sebelum modul layanan diimpor (konstanta dibaca saat impor).
os.environ["PARSER_MODEL"] = args.model
os.environ["GENERATOR_MODEL"] = args.model
OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Longgarkan batas waktu tanpa menyentuh kode layanan.
_orig_urlopen = urllib.request.urlopen


def _urlopen(req, *a, **kw):
    kw["timeout"] = args.timeout
    return _orig_urlopen(req, *a, **kw)


urllib.request.urlopen = _urlopen


def ollama(path, payload=None, timeout=300):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        OLLAMA + path, data=data, headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET")
    with _orig_urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def siapkan_model():
    """Bongkar model LLM lain dari memori (bge-m3 dibiarkan), lalu muat model target."""
    try:
        for m in ollama("/api/ps").get("models", []):
            nama = m.get("name", "")
            if nama and nama != args.model and not nama.startswith("bge"):
                ollama("/api/generate", {"model": nama, "keep_alive": 0})
        ollama("/api/generate", {"model": args.model, "prompt": "", "keep_alive": "30m"}, timeout=600)
        print("Model siap:", args.model)
    except Exception as e:  # noqa: BLE001
        print("PERINGATAN siapkan_model:", repr(e))


def bongkar_model():
    try:
        ollama("/api/generate", {"model": args.model, "keep_alive": 0})
    except Exception:
        pass


def baca_giliran():
    path = ROOT / "logs" / "chat_history.jsonl"
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = r.get("timestamp", "")
            if not (args.dari <= ts <= args.sampai):
                continue
            out.append(r)
    return out


def main():
    rows = baca_giliran()
    n_turn = sum(1 for r in rows if r.get("user_text") and r.get("route") != "session_boundary"
                 and not str(r.get("user_text")).startswith("["))
    print(f"Jendela log: {args.dari} .. {args.sampai}  -> {n_turn} giliran")
    if not n_turn:
        print("Tidak ada giliran di jendela itu. Periksa --dari/--sampai.")
        return

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    siapkan_model()
    from services.session_pipeline import SessionPipeline  # impor setelah env diset
    from services.action_engine import ActionEngine

    action_engine = ActionEngine(db_path=args.katalog) if args.katalog else ActionEngine()
    pipe = SessionPipeline(action_engine=action_engine)
    state = {}
    hist_asli = []
    hasil = []
    i = 0
    for r in rows:
        teks = r.get("user_text") or ""
        if r.get("route") == "session_boundary" or teks.startswith("["):
            state, hist_asli = {}, []
            continue
        if not teks:
            continue
        i += 1
        hist = None if args.bebas else list(hist_asli[-8:])
        t0 = time.perf_counter()
        rec = {
            "n": i, "waktu": r.get("timestamp", "")[11:19], "user": teks,
            "asli": {"aksi": r.get("aksi_parser") or r.get("route"), "jenis": r.get("jenis"),
                     "balasan": r.get("bot_reply")},
        }
        try:
            res, state = pipe.process_turn(teks, state, history=hist)
            dt = time.perf_counter() - t0
            fakta = res.fakta_eksekusi or {}
            pelanggaran_list = getattr(res, "pelanggaran", []) or getattr(res, "pelanggaran_pemeriksa", [])
            retry_count = getattr(res, "jumlah_retry", 0)
            is_fallback = bool(getattr(res, "is_emergency_fallback", False) or getattr(res, "jalur", "") == "fallback")
            rec["baru"] = {
                "aksi": getattr(res, "aksi_parser", None) or res.aksi_terpilih,
                "jenis": getattr(res, "jenis", None),
                "jalur": getattr(res, "jalur", None),
                "status_fakta": fakta.get("status"),
                "balasan": res.teks_jawaban,
                "kartu": bool(res.kartu_produk_html),
                "latensi_s": round(dt, 1),
                "pelanggaran": pelanggaran_list,
                "retry": retry_count,
                "fallback": is_fallback,
            }
            rec["state"] = {k: state.get(k) for k in ("kategori", "budget", "merek", "kebutuhan_teks", "persona")}
            rec["produk_tampil"] = [p.get("kode") for p in (state.get("produk_tampil") or []) if isinstance(p, dict)]
        except Exception as e:  # noqa: BLE001
            rec["error"] = repr(e)
            rec["baru"] = {
                "aksi": None, "balasan": None, "latensi_s": round(time.perf_counter() - t0, 1),
                "pelanggaran": [], "retry": 0, "fallback": True
            }
        hasil.append(rec)
        hist_asli.append({"role": "user", "content": teks, "text": teks})
        hist_asli.append({"role": "assistant", "content": r.get("bot_reply") or "", "text": r.get("bot_reply") or ""})
        b = rec["baru"]
        print(f"{i:>2} {rec['asli']['aksi']!s:<20} -> {b.get('aksi')!s:<20} "
              f"[{b.get('status_fakta')}] {b.get('latensi_s')}s | {str(b.get('balasan'))[:110]!r}", flush=True)

    ok = [h for h in hasil if h.get("baru", {}).get("balasan")]
    lat = [h["baru"]["latensi_s"] for h in ok if h["baru"].get("latensi_s") is not None]
    ringkas = {
        "model": args.model,
        "katalog": args.katalog or "data/catalog.db",
        "mode_riwayat": "bebas (cabang)" if args.bebas else "asli (konteks sama dengan sesi nyata)",
        "giliran": len(hasil),
        "error": sum(1 for h in hasil if "error" in h),
        "total_pelanggaran": sum(len(h.get("baru", {}).get("pelanggaran", [])) for h in hasil),
        "total_retry": sum(h.get("baru", {}).get("retry", 0) for h in hasil),
        "total_fallback": sum(1 for h in hasil if h.get("baru", {}).get("fallback")),
        "aksi_sama_dengan_asli": sum(1 for h in ok if h["baru"]["aksi"] == h["asli"]["aksi"]),
        "median_latensi_s": round(statistics.median(lat), 1) if lat else None,
        "maks_latensi_s": max(lat) if lat else None,
    }
    out = {"ringkasan": ringkas, "giliran": hasil}
    path = ROOT / "scratch" / f"replay_model_{args.label}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ringkas, ensure_ascii=False, indent=2))
    print("Disimpan:", path)
    bongkar_model()


if __name__ == "__main__":
    main()
