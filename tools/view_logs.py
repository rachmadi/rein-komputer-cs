# -*- coding: utf-8 -*-
"""
CLI Tool untuk Melihat dan Memantau Chat Log Bobby Computer.
Usage:
    python tools/view_logs.py --tail 10
    python tools/view_logs.py --session tg_12345
    python tools/view_logs.py --stats
"""
from __future__ import annotations

import argparse
import sys
import os

# Konfigurasi encoding stdout untuk Windows terminal
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Tambahkan project root ke sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat_logger import get_recent_logs, get_log_stats

def print_stats():
    stats = get_log_stats()
    print("=" * 60)
    print("📊 STATISTIK CHAT CUSTOMER CARE BOBBY COMPUTER")
    print("=" * 60)
    print(f"Total Pesan Masuk : {stats['total_messages']}")
    print(f"Total Sesi Unik   : {stats['total_sessions']}")
    print(f"Rata-rata Latensi : {stats['avg_latency_ms']} ms")
    print("\nDistribusi Channel:")
    for ch, count in stats.get("channels", {}).items():
        print(f"  • {ch.upper()}: {count} pesan")
    print("\nTop 5 Rute FSM:")
    for route, count in list(stats.get("top_routes", {}).items())[:5]:
        print(f"  • {route}: {count}")
    print("=" * 60)

def print_logs(logs: list[dict]):
    if not logs:
        print("Belum ada data percakapan yang tercatat.")
        return
        
    print(f"\nMenampilkan {len(logs)} log percakapan terbaru (urutan waktu):\n")
    # Urutkan dari yang paling lama ke terbaru untuk dibaca berurutan
    for l in reversed(logs):
        ts = l.get("timestamp", "").replace("T", " ")[:19]
        ch = l.get("channel", "web").upper()
        sid = l.get("session_id", "-")
        route = l.get("route", "-")
        pname = l.get("persona_name") or "-"
        user_msg = l.get("user_text", "")
        bot_reply = l.get("bot_reply", "")
        
        print(f"[{ts}] [{ch}] Sesi: {sid} | Rute: {route} | Persona: {pname}")
        print(f"👤 USER : {user_msg}")
        print(f"🤖 BOT  : {bot_reply}")
        if l.get("offered_products"):
            print(f"📦 Ditawarkan: {l['offered_products']}")
        print("-" * 60)

def main():
    parser = argparse.ArgumentParser(description="Lihat Chat Log Bobby Computer")
    parser.add_argument("--tail", type=int, default=10, help="Jumlah baris log terbaru yang ditampilkan")
    parser.add_argument("--session", type=str, default=None, help="Filter berdasarkan session_id tertentu")
    parser.add_argument("--channel", type=str, choices=["web", "telegram"], default=None, help="Filter channel")
    parser.add_argument("--stats", action="store_true", help="Tampilkan statistik percakapan")
    
    args = parser.parse_args()
    
    if args.stats:
        print_stats()
    else:
        logs = get_recent_logs(limit=args.tail, session_id=args.session, channel=args.channel)
        print_logs(logs)

if __name__ == "__main__":
    main()
