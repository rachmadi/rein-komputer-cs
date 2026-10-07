#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bobby Computer Customer Care — CLI Entrypoint
Menggunakan data terstruktur dari Qdrant dan Core Engine FSM v1.2
"""
from __future__ import annotations

import argparse
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.catalog import Catalog
from core.state import new_state
from core.engine import step
import ingest

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bobby Computer Customer Care (Spek v1.2 & Qdrant)")
    ap.add_argument("command", nargs="?", default="chat", choices=["chat", "ingest"],
                    help="Perintah: chat (default) atau ingest")
    ap.add_argument("--source", choices=["qdrant", "dummy"], default="qdrant",
                    help="Sumber katalog: qdrant (default) atau dummy (offline fallback)")
    ap.add_argument("--qdrant", default="http://localhost:6333",
                    help="URL Qdrant (default: http://localhost:6333)")
    ap.add_argument("--collection", default="computer_knowledge",
                    help="Nama koleksi Qdrant (default: computer_knowledge)")
    ap.add_argument("--model", default="gemma4:e4b",
                    help="Model Ollama untuk fallback Level 3 (default: gemma4:e4b)")
    ap.add_argument("--debug", action="store_true",
                    help="Tampilkan route dan debug state")
    args = ap.parse_args(argv)

    if args.command == "ingest":
        print("Menjalankan pipeline ingestion ke Qdrant...")
        ingest.main()
        return 0

    print("Memuat katalog dari Qdrant...")
    catalog = Catalog.load(source=args.source, url=args.qdrant, collection=args.collection)
    print(f"Katalog berhasil dimuat ({len(catalog.products)} produk dari Qdrant).\n")

    print("Bobby Computer Customer Care. Ketik 'exit' untuk keluar.\n")
    state = new_state()
    
    while True:
        try:
            user = input("Anda: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in ("exit", "quit", "keluar"):
            print("Sampai jumpa, Kak! Terima kasih sudah menghubungi Bobby Computer.")
            break
            
        t0 = time.time()
        state, reply, route = step(state, user, catalog, nlu=None, llm_model=args.model)
        print(f"\nCS: {reply}\n")
        
        if args.debug:
            print(f"[debug: route={route} waktu={time.time() - t0:.3f}s fsm={state.get('fsm_stage')} "
                  f"needs={state.get('needs')} cat={state.get('category')} "
                  f"offered={state.get('offered_products')}]\n")
            
    return 0

if __name__ == "__main__":
    sys.exit(main())