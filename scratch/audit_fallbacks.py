import ast

with open('services/action_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines, 1):
    if 'laptop' in line.lower() and ('or' in line or 'default' in line or 'else' in line or '==' in line):
        print(f"{idx}: {line.strip()}")
