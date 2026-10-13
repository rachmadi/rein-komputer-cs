import json

path = r"C:\Users\rachm\.gemini\antigravity\brain\dfc0fdb1-7085-4cbc-8fc8-1c939e32aa2d\.system_generated\logs\transcript.jsonl"
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        if "PUTARAN 15b" in line and '"USER_EXPLICIT"' in line:
            obj = json.loads(line)
            print("=== FOUND USER PROMPT ===")
            print(obj.get("content"))
            print("=========================")
