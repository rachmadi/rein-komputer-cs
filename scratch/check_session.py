import json

session_id = '99b9b3f6adc7'
messages = []
with open('logs/chat_history.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        sid = d.get('session_id') or d.get('anon_session_id')
        if sid and session_id in sid:
            messages.append(d)

user_msgs = [m for m in messages if m.get('user_text')]
for idx, m in enumerate(user_msgs[213:], 214):
    print(f"{idx}: ts={m.get('timestamp')} text='{m.get('user_text')}'")
