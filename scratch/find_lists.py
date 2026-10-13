import os
import re

patterns = [
    re.compile(r'(\[\s*["\'](?:laptop|desktop|printer|lenovo|asus|acer|hp|canon|epson|brother|monitor)["\'])', re.IGNORECASE),
    re.compile(r'(\{\s*["\'](?:laptop|desktop|printer|lenovo|asus|acer|hp|canon|epson|brother|monitor)["\'])', re.IGNORECASE),
    re.compile(r'(["\']laptop["\']\s*,\s*["\']desktop["\'])', re.IGNORECASE),
    re.compile(r'(["\']lenovo["\']\s*,\s*["\']asus["\'])', re.IGNORECASE),
    re.compile(r'(\bget_catalog_brands\b|\bget_catalog_categories\b)', re.IGNORECASE)
]

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.git', '.venv', 'eval', 'scratch', '__pycache__', 'logs', 'docs']):
        continue
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, encoding='utf-8', errors='ignore') as fp:
                for idx, line in enumerate(fp, 1):
                    for pat in patterns:
                        if pat.search(line):
                            print(f"{p}:{idx}: {line.strip()}")
                            break
