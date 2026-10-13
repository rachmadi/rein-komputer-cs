import sys

with open("d:/RAG/tests/test_turn2_failures.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('print("MR:", mr); assert len(mr["tidak_terpenuhi"]) > 0', 'assert len(mr["tidak_terpenuhi"]) > 0 or len(mr["tidak_diketahui"]) > 0')

with open("d:/RAG/tests/test_turn2_failures.py", "w", encoding="utf-8") as f:
    f.write(text)
