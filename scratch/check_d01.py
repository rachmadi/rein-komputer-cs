import sys; sys.path.insert(0, '.')
from services.action_engine import ActionEngine

engine = ActionEngine(db_path="data/test_catalog.db")
p = engine.get_product_by_code("KB-D01")
print("engine p ram:", p.get("ram"))
print("engine p ram_gb:", p.get("ram_gb"))
print("engine p storage:", p.get("storage"))
print("engine p display:", p.get("display"))
