import sqlite3
import requests
import sys

sys.path.append("d:/RAG")
from services.knowledge_service import QDRANT_URL, CATALOG_COLLECTION

# Delete from SQLite
conn = sqlite3.connect('d:/RAG/data/catalog.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM products WHERE kode='TEST-GPU-NULL'")
conn.commit()
conn.close()

# Delete from Qdrant
url = f"{QDRANT_URL}/collections/{CATALOG_COLLECTION}/points/delete"
payload = {
    "points": [
        "TEST-GPU-NULL"
    ]
}
resp = requests.post(url, json=payload)
print(resp.json())
