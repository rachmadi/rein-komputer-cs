#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cegah httpx mencetak URL Telegram (yang memuat token bot) ke log.

Pemakaian (dari D:\\RAG):
    .\\.venv\\Scripts\\python.exe scratch\\fix_httpx_log.py
Menyisipkan dua baris setelah definisi `logger` di telegram_bot.py. Cadangan di scratch\\backup_loopback\\.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
p = ROOT / "telegram_bot.py"
data = p.read_bytes()
nl = b"\r\n" if b"\r\n" in data else b"\n"
anchor = b'logger = logging.getLogger("reinkomputer_telegram_bot")'
marker = b'logging.getLogger("httpx").setLevel'
if marker in data:
    print("Sudah ada; tidak ada yang diubah.")
    sys.exit(0)
if data.count(anchor) != 1:
    print("Jangkar tidak ditemukan tepat satu kali; dibatalkan.")
    sys.exit(1)
addition = (anchor + nl +
            b"# httpx mencetak URL lengkap (termasuk token bot) pada level INFO; turunkan agar token tidak masuk log" + nl +
            b'logging.getLogger("httpx").setLevel(logging.WARNING)' + nl +
            b'logging.getLogger("httpcore").setLevel(logging.WARNING)')
backup = ROOT / "scratch" / "backup_loopback"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup / "telegram_bot.py")
p.write_bytes(data.replace(anchor, addition))
print("Selesai. Cek dengan: git diff telegram_bot.py")
