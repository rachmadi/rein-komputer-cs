import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("? Berikut rekomendasi yang memenuhi syarat", "✅ Berikut rekomendasi yang memenuhi syarat")
text = text.replace("?? Tidak ada yang memenuhi syarat mutlak", "⚠️ Tidak ada yang memenuhi syarat mutlak")
text = text.replace("? Produk tidak tersedia untuk kriteria tersebut", "❌ Produk tidak tersedia untuk kriteria tersebut")
text = text.replace("âš ï¸ ", "⚠️")

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
