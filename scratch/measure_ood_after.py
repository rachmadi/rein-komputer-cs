import os
import csv
from services.knowledge_service import get_usage_requirements

os.system("d:\\RAG\\.venv\\Scripts\\python.exe d:\\RAG\\scripts\\ingest_knowledge.py")

def measure_after():
    queries = [
        ("laptop baterai awet", "P16"),
        ("ada diskon laptop gaming", "P04"),
        ("install apa saja untuk laptop kuliah", "P06"),
    ]
    results = []
    for q, exp in queries:
        res = get_usage_requirements(q, limit=1)
        pred = res['profil'][0]['profil_id'] if res['profil'] else "NONE"
        results.append({"Query": q, "Expected": exp, "Predicted": pred, "Match": pred == exp})
    
    with open("docs/ood_recall_after.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Query", "Expected", "Predicted", "Match"])
        writer.writeheader()
        writer.writerows(results)
    
    for r in results:
        print(f"AFTER: {r['Query']} -> Pred: {r['Predicted']} (Exp: {r['Expected']}) Match: {r['Match']}")

measure_after()
