import sys
import json

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=== MEMERIKSA LOG LIVE TEST TERAKHIR DARI logs/chat_history.jsonl ===")
    with open("logs/chat_history.jsonl", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"Total baris log: {len(lines)}")
    recent_lines = lines[-35:]

    for idx, l in enumerate(recent_lines, 1):
        try:
            item = json.loads(l)
        except Exception:
            continue

        ts = item.get("timestamp")
        u_text = item.get("user_text")
        b_reply = item.get("bot_reply", "")
        route = item.get("route")
        lat = item.get("latency_ms", 0)
        tool_calls = item.get("tool_calls", [])
        penguji = item.get("penguji")
        sess = item.get("session_id")
        fallback = item.get("is_emergency_fallback")

        print(f"\n--- [Turn {idx}] Timestamp: {ts} | Sesi: {sess} | Penguji: {penguji} ---")
        print(f"User   : {u_text}")
        print(f"Tools  : {[tc.get('nama') for tc in tool_calls]} -> Args: {[tc.get('argumen') for tc in tool_calls]}")
        print(f"Bot    : {b_reply}")
        print(f"Latency: {lat/1000:.2f}s | Route: {route} | Fallback: {fallback}")

if __name__ == "__main__":
    main()

