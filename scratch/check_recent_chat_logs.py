import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/catalog.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute('SELECT * FROM chat_logs ORDER BY id DESC LIMIT 15').fetchall()
print(f'Total recent logs retrieved: {len(rows)}')
for r in reversed(rows):
    print('='*70)
    print(f"ID: {r['id']} | Time: {r['timestamp']} | Channel: {r['channel']} | Session: {r['session_id']}")
    print(f"User: {r['user_text']}")
    print(f"Route: {r['route']} | Latency: {r['latency_ms']} ms")
    print(f"Active Cat: {r['active_category']} | Persona: {r['persona_name']}")
    print(f"Bot Reply:\n{r['bot_reply']}")
