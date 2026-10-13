import requests
import json
import sys

def dump_points(collection_name: str, output_path: str):
    url = f"http://127.0.0.1:6333/collections/{collection_name}/points/scroll"
    points = []
    offset = None
    while True:
        body = {"limit": 100, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        resp = requests.post(url, json=body, timeout=30)
        resp.raise_for_status()
        res = resp.json().get("result", {})
        pts = res.get("points", [])
        for p in pts:
            payload = p.get("payload", {})
            points.append({
                "point_id": p.get("id"),
                "id": payload.get("id"),
                "judul": payload.get("judul"),
                "tipe": payload.get("tipe")
            })
        offset = res.get("next_page_offset")
        if offset is None:
            break

    print(f"Total titik ({collection_name}): {len(points)}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(points, f, indent=2, ensure_ascii=False)
    for p in points:
        print(f"  - {p.get('id')}: {p.get('judul')} ({p.get('tipe')})")

if __name__ == "__main__":
    coll = sys.argv[1] if len(sys.argv) > 1 else "computer_knowledge"
    out = sys.argv[2] if len(sys.argv) > 2 else "scratch/qdrant_titik_sebelum_p20.json"
    dump_points(coll, out)
