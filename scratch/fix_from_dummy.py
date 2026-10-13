import sys

with open("d:/RAG/tests/test_e2e_golden.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("Catalog.from_synthetic_v1_2()", "Catalog.from_dummy()")

with open("d:/RAG/tests/test_e2e_golden.py", "w", encoding="utf-8") as f:
    f.write(text)
