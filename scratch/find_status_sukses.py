with open("services/action_engine.py", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        if '"sukses"' in line:
            print(f"{idx}: {line.strip()}")
