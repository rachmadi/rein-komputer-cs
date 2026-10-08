# -*- coding: utf-8 -*-
"""
Bobby Computer — Telegram Bot Customer Care
Terhubung langsung dengan Unified Chat Service (Core Engine FSM v1.2 & Qdrant).
Mendukung multi-user session per chat_id Telegram.

Cara Penggunaan:
  1. Set environment variable:
     $env:TELEGRAM_BOT_TOKEN="TOKEN_DARI_BOTFATHER"
  2. Jalankan bot:
     python telegram_bot.py
  Atau kirim langsung via flag:
     python telegram_bot.py --token "TOKEN_DARI_BOTFATHER"
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import asyncio
from datetime import datetime

import hashlib
import json
import uuid

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

# Integrasi dengan Unified Chat Service
from services.chat_service import process_chat_message, reset_chat_session

FEEDBACK_LOG_PATH = "logs/feedback.jsonl"

from core.chat_logger import anonymize_id

def record_feedback(session_id: str, user_id: int | str, rating: str, note: str = "") -> None:
    """Simpan feedback pelanggan ke log secara teranonimasi dengan HMAC-SHA256."""
    os.makedirs("logs", exist_ok=True)
    anon_user = anonymize_id(str(user_id), length=12)
    anon_session = anonymize_id(str(session_id), length=12)
    record = {
        "timestamp": datetime.now().isoformat(),
        "anon_user_id": anon_user,
        "anon_session_id": anon_session,
        "raw_session_id": session_id,
        "rating": rating,
        "note": note
    }
    with open(FEEDBACK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def get_feedback_keyboard(turn_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard 👍/👎 untuk feedback percakapan."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍", callback_data=f"fb:like:{turn_id}"),
            InlineKeyboardButton("👎", callback_data=f"fb:dislike:{turn_id}")
        ]
    ])

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("bobby_telegram_bot")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani perintah /start dari pelanggan."""
    chat_id = update.effective_chat.id
    session_id = f"tg_{chat_id}"
    reset_chat_session(session_id)
    context.user_data["sent_photo_codes"] = set()
    context.user_data["last_mentioned_products"] = []

    welcome_text = (
        "Halo, Kak! Selamat datang di *Bobby Computer Customer Care* 💻🤖\n\n"
        "Saya asisten resmi Bobby Computer yang siap membantu Kakak mencari laptop, desktop, printer, atau monitor terbaik sesuai kebutuhan & anggaran.\n\n"
        "Silakan langsung ketik apa yang sedang Kakak cari, misalnya:\n"
        "• _Ada laptop Acer untuk kerja?_\n"
        "• _Rekomendasi laptop gaming RTX budget 15 jutaan_\n"
        "• _Cari mini PC atau desktop Lenovo_\n\n"
        "Gunakan perintah /reset jika ingin memulai percakapan baru dari awal."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mereset sesi percakapan pengguna saat ini."""
    chat_id = update.effective_chat.id
    session_id = f"tg_{chat_id}"
    reset_chat_session(session_id)
    context.user_data["sent_photo_codes"] = set()
    context.user_data["last_mentioned_products"] = []
    await update.message.reply_text(
        "Sesi percakapan Kakak telah direset! Ada yang bisa kami bantu seputar produk Bobby Computer hari ini?",
        parse_mode=ParseMode.MARKDOWN
    )


import html
import re

def format_telegram_text(text: str) -> tuple[str, str | None]:
    """
    Format teks untuk Telegram:
    - Melarang asteris ** mentah tampil di chat.
    - Mengonversi **bold** menjadi <b>bold</b> untuk ParseMode.HTML.
    - Mengonversi _italic_ atau *italic* menjadi <i>italic</i>.
    """
    if not text:
        return "", None

    # Escape karakter HTML dasar (&, <, >)
    escaped = html.escape(text)

    # Ubah **bold** menjadi <b>bold</b>
    formatted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)

    # Ubah *italic* menjadi <i>italic</i> jika ada
    formatted = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", formatted)

    return formatted, ParseMode.HTML


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Memproses pesan teks dari pelanggan Telegram."""
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    session_id = f"tg_{chat_id}"
    user_text = update.message.text.strip()

    # Tampilkan indikasi "typing..."
    async def keep_typing():
        try:
            while True:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                await asyncio.sleep(4.5)
        except asyncio.CancelledError:
            pass

    typing_task = asyncio.create_task(keep_typing())

    try:
        res = await asyncio.to_thread(process_chat_message, 
            session_id,
            user_text)
        cards_html = res.get("kartu_produk_html")
        reply_text = (res.get("reply") or "").strip()
        if not reply_text:
            reply_text = "Mohon maaf Kak, ada kendala teknis sesaat. Ada produk komputer atau laptop yang bisa saya bantu carikan?"
        products = res.get("products", [])
        route = res.get("route", "")

        # 1. Antigravity v2: Kirim kartu produk terlebih dahulu (jika ada) sesuai R1 & Bagian 3
        if cards_html:
            try:
                await update.message.reply_text(cards_html, parse_mode=ParseMode.HTML)
            except Exception as card_err:
                logger.warning(f"Kirim kartu HTML gagal ({card_err}), fallback teks polos")
                await update.message.reply_text(cards_html)
            await asyncio.sleep(0.4)

        # 2. Kirim balasan teks percakapan dari Generator LLM dengan tombol umpan balik
        turn_id = str(uuid.uuid4())[:8]
        fb_kb = get_feedback_keyboard(turn_id)
        html_text, p_mode = format_telegram_text(reply_text)
        try:
            await update.message.reply_text(html_text, parse_mode=p_mode, reply_markup=fb_kb)
        except Exception as tg_err:
            logger.warning(f"ParseMode HTML gagal ({tg_err}), fallback ke teks polos")
            plain_clean = re.sub(r"\*\*", "", reply_text)
            await update.message.reply_text(plain_clean, reply_markup=fb_kb)

        typing_task.cancel()

        # Inisialisasi himpunan kode produk yang sudah pernah dikirimkan fotonya
        if "sent_photo_codes" not in context.user_data or not isinstance(context.user_data["sent_photo_codes"], set):
            context.user_data["sent_photo_codes"] = set()
        sent_photos: set = context.user_data["sent_photo_codes"]

        # Deteksi apakah user meminta foto/gambar secara eksplisit (phrase-based matching)
        user_text_lower = user_text.lower()
        photo_phrases = (
            "kirim foto", "minta foto", "tampilkan foto", "lihat foto", "mana foto", "coba foto", "ada foto",
            "kirim gambar", "minta gambar", "tampilkan gambar", "lihat gambar", "mana gambar", "coba gambar", "ada gambar",
            "lihat bentuk", "tampilkan fisik", "kirim pic", "minta pic", "lihat penampakan"
        )
        is_photo_requested = any(phrase in user_text_lower for phrase in photo_phrases) and "malah" not in user_text_lower and "jangan" not in user_text_lower

        prods_to_send = []

        if is_photo_requested:
            # Aturan 3 pengecualian: Pelanggan memang minta dikirim/dikirim ulang foto
            if products:
                prods_to_send = products[:2]
            else:
                last_codes = context.user_data.get("last_mentioned_products", [])
                if last_codes:
                    from services.catalog_service import get_active_catalog
                    cat = get_active_catalog()
                    prods_to_send = [cat.by_code[c] for c in last_codes if c in cat.by_code][:2]
        else:
            # Aturan 1 & 2 & 3:
            # Hanya kirim foto jika ada tawaran produk baru yang BELUM pernah dikirim fotonya
            if products:
                new_products = [p for p in products if p.get("kode") and p.get("kode") not in sent_photos]
                if new_products:
                    # Ambil maksimal 2 produk baru untuk dikirimkan fotonya
                    prods_to_send = new_products[:2]

        if prods_to_send:
            for p in prods_to_send:
                img_url = (p.get("image_url") or "").strip()
                # Foto hanya dikirim jika image_url produk terisi asli, jangan memakai gambar pengganti
                if not img_url or "unsplash" in img_url or not img_url.startswith("http"):
                    continue

                nama = p.get("nama", "Produk")
                raw_price = p.get("harga") or p.get("harga_idr", 0)
                if isinstance(raw_price, (int, float)):
                    harga = f"Rp{int(raw_price):,}".replace(",", ".")
                else:
                    harga = str(raw_price)
                cpu = p.get("prosesor") or p.get("cpu", "")
                gpu = p.get("gpu", "")
                gpu_part = f" | {gpu}" if gpu else ""
                ram_val = p.get("ram") or (f"{p.get('ram_gb', '')} GB {p.get('ram_type', '')}".strip() if p.get("ram_gb") else "")
                ram_part = f" | RAM {ram_val}" if ram_val else ""
                caption = f"{nama}\nHarga: {harga}\n{cpu}{gpu_part}{ram_part}"

                try:
                    await update.message.reply_photo(
                        photo=img_url,
                        caption=caption
                    )
                    # Tandai bahwa foto produk ini sudah dikirimkan
                    if p.get("kode"):
                        sent_photos.add(p["kode"])
                except Exception as img_err:
                    logger.warning(f"Gagal mengirim foto {nama}: {img_err}")

        # Simpan produk yang aktif di giliran ini
        if products:
            context.user_data["last_mentioned_products"] = [p["kode"] for p in products if p.get("kode")]

    except Exception as e:
        typing_task.cancel()
        logger.error(f"Error memproses pesan chat_id {chat_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "Mohon maaf Kak, terjadi kendala saat memproses jawaban. Silakan ulangi pertanyaan Kakak ya!"
        )


async def feedback_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani feedback jempol 👍 / 👎 dari pelanggan Telegram."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    if data.startswith("fb:"):
        parts = data.split(":")
        rating_type = parts[1] if len(parts) > 1 else "unknown"
        turn_id = parts[2] if len(parts) > 2 else ""

        chat_id = update.effective_chat.id if update.effective_chat else "unknown"
        user_id = query.from_user.id if query.from_user else "unknown"
        session_id = f"tg_{chat_id}"

        record_feedback(
            session_id=session_id,
            user_id=user_id,
            rating=rating_type,
            note=f"turn_{turn_id}"
        )

        ack_text = "Terima kasih atas tanggapan positifnya! 😊" if rating_type == "like" else "Terima kasih atas masukannya, kami akan terus meningkatkan kualitas rekomendasi 🙏"
        await query.answer(ack_text)
        try:
            label = "👍 Tanggapan dicatat" if rating_type == "like" else "👎 Masukan dicatat"
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="none")]])
            )
        except Exception:
            pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error('Exception while handling an update:', exc_info=context.error)

def main() -> None:
    parser = argparse.ArgumentParser(description="Bobby Computer Telegram Bot")
    parser.add_argument("--token", help="Telegram Bot Token dari BotFather", default=None)
    args = parser.parse_args()

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print(
            "PERINGATAN: TELEGRAM_BOT_TOKEN belum diset!\n"
            "Untuk menjalankan bot Telegram di masa mendatang:\n"
            "  1. Dapatkan token dari @BotFather di Telegram.\n"
            "  2. Jalankan: python telegram_bot.py --token <TOKEN_ANDA>\n"
            "     atau set environment variable TELEGRAM_BOT_TOKEN."
        )
        sys.exit(1)

    print("Memulai Bobby Computer Telegram Bot...")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(feedback_callback_handler, pattern=r"^fb:"))
    app.add_error_handler(error_handler)

    print("Bot berhasil berjalan dan mendengarkan pesan Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()
