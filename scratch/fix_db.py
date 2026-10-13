import sqlite3
import requests

# Delete from SQLite
conn = sqlite3.connect('d:/RAG/data/catalog.db')
cursor = conn.cursor()
cursor.execute("SELECT kode FROM products WHERE nama LIKE '%Test Laptop%'")
rows = cursor.fetchall()
cursor.execute("DELETE FROM products WHERE nama LIKE '%Test Laptop%'")
conn.commit()
conn.close()

# Delete from Qdrant
if rows:
    from services.catalog_service import code_to_point_id
    from services.catalog_service import QDRANT_URL, COLLECTION_NAME
    for row in rows:
        pid = code_to_point_id(row[0])
        requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/delete?wait=true",
            json={"points": [pid]}
        )
        print(f"Deleted {row[0]}")
