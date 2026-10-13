import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

META_PATTERNS = [
    r"dari\s+mana\s+kamu\s+tahu",
    r"kok\s+(kamu\s+)?(bisa\s+)?tahu",
    r"kenapa\s+(kamu\s+)?(nawarin|rekomendasiin|pilih)\s+(ini|yang\s+ini)",
    r"kamu\s+(ini\s+)?(ai|bot|robot|manusia)",
    r"siapa\s+kamu",
    r"apakah\s+kamu\s+(ai|bot|robot)",
    r"kebutuhan(nya)?\s+(aja\s+)?(kamu\s+)?belum\s+(tahu|tau)",
    r"belum\s+(tahu|tau)\s+kebutuhan",
    r"(gak|tidak|kurang)\s+(kegedean|kebesaran|kemahalan|ketinggian|keberatan|overkill)",
    r"terlalu\s+(besar|tinggi|berat|mahal|spek|berlebih)",
    r"spek(nya)?\s+(gak\s+)?kegedean",
    r"kok\s+(malah\s+)?(ditawarin|nawarin)",
    r"aku\s+(kan\s+|tadi\s+)?(tanya|nanya)",
    r"kurang\s+nangkap",
    r"bukan\s+itu\s+maksud(ku|nya)?",
    r"maksudku\s+bukan",
]

test_cases = [
    "Gak kegedean tuh speknya?",
    "Loh...kok ditawarin yang lain? Aku tadi tanya apa gak kegedean spek yang sebelumnya?",
    "Kebutuhannya aja kamu belum tau",
    "Dari mana kamu tahu kebutuhanku?",
    "Kurang nangkap kok nawarin?"
]

for tc in test_cases:
    matched = [pat for pat in META_PATTERNS if re.search(pat, tc.lower())]
    print(f"'{tc}' -> matched {len(matched)} patterns: {matched}")
