import sys
sys.stdout.reconfigure(encoding='utf-8')

from services.chat_service import process_chat_message, reset_chat_session

sid = "test_telegram_troubleshoot"
reset_chat_session(sid)

turns = [
    "halo",
    "jual laptop acer?",
    "Buat mama sih",
    "Gak kegedean tuh speknya?",
    "Loh...kok ditawarin yang lain? Aku tadi tanya apa gak kegedean spek yang sebelumnya?",
    "Kebutuhannya aja kamu belum tau"
]

print("=== REPRODUKSI PERCAKAPAN TELEGRAM USER ===")
for i, msg in enumerate(turns, 1):
    res = process_chat_message(sid, msg)
    print(f"\n[Turn {i}] User: {msg}")
    print(f"Route: {res.get('route')} | Persona: {res.get('persona_name')} | Products: {[p['kode'] for p in res.get('products', [])]}")
    print(f"Bot Reply:\n{res['reply']}")
    print("-" * 60)
