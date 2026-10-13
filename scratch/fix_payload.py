import sys
import re

with open("d:/RAG/app/main.py", "r", encoding="utf-8") as f:
    text = f.read()

old_fields = """    is_accessory: bool = Field(False, description="Apakah produk merupakan aksesori")
    sync_qdrant: bool = Field(True, description="Otomatis buat embedding dan simpan ke Qdrant")"""

new_fields = """    is_accessory: bool = Field(False, description="Apakah produk merupakan aksesori")
    sync_qdrant: bool = Field(True, description="Otomatis buat embedding dan simpan ke Qdrant")
    gpu_dedicated: int | None = Field(None, description="0 untuk iGPU, 1 untuk Dedicated")
    vram_gb: int | None = Field(None, description="VRAM dalam GB")
    cpu_tier: int | None = Field(None, description="Tingkatan CPU")"""

text = text.replace(old_fields, new_fields)

with open("d:/RAG/app/main.py", "w", encoding="utf-8") as f:
    f.write(text)
