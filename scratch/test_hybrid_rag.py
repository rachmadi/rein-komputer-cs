import sys
import json
import urllib.request
sys.stdout.reconfigure(encoding='utf-8')

from core.catalog import Catalog
from core.state import new_state
from core.engine import step

cat = Catalog.load(source="qdrant")

dialog_1 = [
    "Halo",
    "Emang bisa bantu apa?",
    "Ada apa aja?",
    "laptop deh",
    "Buat apa aja",
    "Kata papa, yang bisa gambar",
    "Kata papa yang bisa bikin gambar",
]

print("=== TESTING DIALOG 1 (with gemma3:1b) ===")
s = new_state()
for u in dialog_1:
    s, r, route = step(s, u, cat, llm_model="gemma3:1b")
    print(f"Anda: {u}")
    print(f"CS ({route}):\n{r}\n")

dialog_2 = [
    "Sore",
    "ada",
    "laptop",
    "Gak tau juga sih",
    "Mmm...papa sih kerja",
    "Keknya gak tepat deh",
    "Papaku developer",
    "Emang cocok buat developer?",
    "Mana bisa",
    "Ya gak kuatlah",
]

print("\n=== TESTING DIALOG 2 (with gemma3:1b) ===")
s2 = new_state()
for u in dialog_2:
    s2, r, route = step(s2, u, cat, llm_model="gemma3:1b")
    print(f"Anda: {u}")
    print(f"CS ({route}):\n{r}\n")
