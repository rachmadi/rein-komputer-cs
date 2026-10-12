import os
import re
import requests
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.catalog_service import QDRANT_URL, get_embedding

KNOWLEDGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge", "panduan_kebutuhan_v2.md")
COLLECTION_NAME = os.getenv("QDRANT_KNOWLEDGE_COLLECTION", "computer_knowledge")

def parse_filter_line(line: str):
    filters = []
    line = line.strip()
    if line.endswith('.'): line = line[:-1]
    
    parts = line.split(';')
    for part in parts:
        part = part.strip()
        if not part: continue
        hint = None
        hint_match = re.search(r'\((.*?)\)', part)
        if hint_match:
            hint_text = hint_match.group(1).lower()
            if "disarankan" in hint_text: strength = "soft"
            else: strength = "hard"; hint = hint_text
            part = re.sub(r'\(.*?\)', '', part).strip()
        else: strength = "hard"
            
        if "tidak disyaratkan" in part.lower(): continue
            
        op_match = re.search(r'([≥>=]+)', part)
        if op_match:
            op = op_match.group(1)
            if op == '≥': op = '>='
            field, val = part.split(op_match.group(1), 1)
            try: val = float(val.strip()) if '.' in val else int(val.strip())
            except: val = val.strip()
            f_dict = {"field": field.strip(), "op": op, "value": val, "strength": strength}
            if hint and "nvidia" in hint:
                f_dict["gpu_vendor_hint"] = "nvidia"
                f_dict["strength"] = "soft"
            filters.append(f_dict)
        elif '=' in part:
            field, val = part.split('=', 1)
            f_dict = {"field": field.strip(), "op": "=", "value": val.strip(), "strength": strength}
            filters.append(f_dict)
    return filters

def parse_kb(filepath: str):
    with open(filepath, 'r', encoding='utf-8') as f: text = f.read()
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    sections = text.split('\n## ')
    
    chunks = []
    for i, sec in enumerate(sections):
        if not sec.strip() or (i == 0 and not sec.startswith('## ')): continue
        sec = "## " + sec if not sec.startswith('## ') else sec
        lines = sec.split('\n')
        judul = lines[0].replace('## ', '').strip()
        
        chunk_id = ""; tipe = ""; tag_katalog = []; perangkat = ""; kata_kunci = []; filter_data = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("- **ID:**"):
                parts = line_str.replace("- **ID:**", "").split("|")
                chunk_id = parts[0].strip()
                if "**Tipe:**" in parts[1]: tipe = parts[1].replace("**Tipe:**", "").strip()
            elif line_str.startswith("- **Tag katalog:**"):
                t = line_str.replace("- **Tag katalog:**", "").strip()
                if t and t != "-": tag_katalog = [x.strip() for x in t.split(",")]
            elif line_str.startswith("- **Perangkat:**"):
                perangkat = line_str.replace("- **Perangkat:**", "").strip()
            elif line_str.startswith("- **Kata kunci pelanggan:**"):
                t = line_str.replace("- **Kata kunci pelanggan:**", "").strip()
                if t and t != "-": kata_kunci = [x.strip() for x in t.split(",")]
            elif line_str.startswith("- **Filter minimum:**"):
                f_str = line_str.replace("- **Filter minimum:**", "").strip()
                filter_data = parse_filter_line(f_str)
                
        if not chunk_id and "kebijakan" in judul.lower():
            chunk_id = "K01"
            tipe = "kebijakan_toko"
        if not tipe:
            if chunk_id.startswith('P'): tipe = "profil"
            elif chunk_id.startswith('G'): tipe = "panduan_umum"
            elif chunk_id.startswith('M'): tipe = "panduan_kategori"
            elif chunk_id.startswith('K') or "kebijakan" in judul.lower(): tipe = "kebijakan_toko"
            
        chunk_data = {
            "id": chunk_id, "judul": judul, "tipe": tipe, "tag_katalog": tag_katalog,
            "perangkat": perangkat, "kata_kunci": kata_kunci, "text": sec.strip(), "filter": filter_data
        }
        chunks.append(chunk_data)
    return chunks

def ingest(collection_name: str | None = None, mode: str = "ringkas", recreate: bool = False):
    target_coll = collection_name or COLLECTION_NAME
    if recreate:
        requests.delete(f"{QDRANT_URL}/collections/{target_coll}")
        requests.put(f"{QDRANT_URL}/collections/{target_coll}", json={"vectors": {"size": 1024, "distance": "Cosine"}})

    chunks = parse_kb(KNOWLEDGE_FILE)
    points = []
    import uuid
    for i, c in enumerate(chunks):
        if mode == "penuh":
            clean_body = c["text"].replace("## ", "").strip()
            embed_text = f"Judul: {c['judul']}. {clean_body}"
        else:
            # COMPACT EMBEDDING TEXT: Judul + Kata Kunci + Perangkat, atau Judul + Text
            keys = ", ".join(c["kata_kunci"])
            if keys:
                embed_text = f"Judul: {c['judul']}. Kata Kunci: {keys}. Perangkat: {c['perangkat']}."
            else:
                embed_text = f"Judul: {c['judul']}. {c['text'].replace('## ', '')}."

        vec = get_embedding(embed_text)
        if not vec:
            continue

        payload = {
            "id": c["id"], "judul": c["judul"], "tipe": c["tipe"], "tag_katalog": c["tag_katalog"],
            "perangkat": c["perangkat"], "kata_kunci": c["kata_kunci"], "text": c["text"], "filter": c["filter"]
        }
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, c["id"] or str(i)))
        points.append({"id": point_id, "vector": vec, "payload": payload})

    if points:
        url = f"{QDRANT_URL}/collections/{target_coll}/points?wait=true"
        resp = requests.put(url, json={"points": points})
        print(f"Ingest [{target_coll}] Mode [{mode}] Status:", resp.status_code)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Knowledge Base ke Qdrant")
    parser.add_argument("--collection", default=COLLECTION_NAME, help="Nama koleksi Qdrant")
    parser.add_argument("--mode", choices=["ringkas", "penuh"], default="ringkas", help="Mode embedding (ringkas atau penuh)")
    parser.add_argument("--recreate", action="store_true", help="Hapus dan buat ulang koleksi")
    args = parser.parse_args()

    ingest(collection_name=args.collection, mode=args.mode, recreate=args.recreate)
