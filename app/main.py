# -*- coding: utf-8 -*-
"""
Bobby Computer Web Application — FastAPI Backend
Menyediakan REST API untuk Admin Katalog (dengan autentikasi JWT)
dan Live Chat Pelanggan (bebas akses tanpa login) untuk Flutter Web.
"""
from __future__ import annotations

import os
import time
from typing import Any
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.auth import (
    authenticate_admin,
    create_access_token,
    get_current_admin
)
from services.catalog_service import (
    list_products,
    get_product_by_code,
    upsert_product,
    delete_product_record,
    sync_all_products_to_qdrant,
    get_active_catalog
)
from services.chat_service import (
    process_chat_message,
    reset_chat_session,
    get_chat_history
)
from core.chat_logger import get_recent_logs, get_log_stats

import shutil
import uuid

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title="Bobby Computer Customer Care & Admin API",
    description="Sistem Web Admin Katalog (JWT Auth) dan Live Chat CS (Anonim) dengan integrasi Qdrant & Core Engine FSM v1.2",
    version="2.1.0"
)

# Static Files for Uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# =============================================================================
# CORS Middleware (Untuk mendukung Flutter Web di port mana saja)
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Pydantic Schemas
# =============================================================================
class LoginPayload(BaseModel):
    username: str = Field(..., description="Username admin")
    password: str = Field(..., description="Password admin")

class ProductPayload(BaseModel):
    kode: str = Field(..., description="Kode unik produk, misal: KB-L01")
    nama: str = Field(..., description="Nama produk lengkap")
    kategori: str = Field(..., description="Kategori: laptop, desktop, printer, monitor")
    brand: str | None = Field(None, description="Merek: acer, asus, lenovo, hp, canon, dll.")
    harga_idr: int = Field(..., description="Harga dalam rupiah")
    cpu: str | None = Field(None, description="Tipe prosesor")
    cpu_vendor: str | None = Field(None, description="intel atau amd")
    ram: str | None = Field(None, description="Kapasitas & tipe RAM, misal: 16 GB DDR5")
    ram_gb: int | None = Field(None, description="Kapasitas numerik RAM dalam GB")
    ram_type: str | None = Field(None, description="DDR4 atau DDR5")
    storage: str | None = Field(None, description="Kapasitas storage, misal: 512 GB NVMe SSD")
    gpu: str | None = Field(None, description="Model kartu grafis, misal: NVIDIA GeForce RTX 2050 4 GB")
    display: str | None = Field(None, description="Ukuran & tipe layar")
    os: str | None = Field(None, description="Sistem operasi")
    usage_text: str | None = Field(None, description="Rekomendasi pemakaian atau use-case")
    image_url: str | None = Field(None, description="URL gambar produk")
    is_accessory: bool = Field(False, description="Apakah produk merupakan aksesori")
    sync_qdrant: bool = Field(True, description="Otomatis buat embedding dan simpan ke Qdrant")
    gpu_dedicated: int | None = Field(None, description="0 untuk iGPU, 1 untuk Dedicated")
    vram_gb: int | None = Field(None, description="VRAM dalam GB")
    cpu_tier: int | None = Field(None, description="Tingkatan CPU")

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID sesi unik pelanggan (dari browser)")
    message: str = Field(..., description="Pesan dari pelanggan")
    model: str | None = Field(None, description="Model LLM Ollama jika diperlukan")

class ResetRequest(BaseModel):
    session_id: str = Field(..., description="ID sesi unik pelanggan")

# =============================================================================
# Health & Public Status API (Bebas Akses)
# =============================================================================
@app.get("/api/health")
def health_check():
    catalog = get_active_catalog()
    return {
        "status": "healthy",
        "active_products": len(catalog.products),
        "categories": {
            "laptop": len(catalog.pool("laptop")),
            "desktop": len(catalog.pool("desktop")),
            "printer": len(catalog.pool("printer")),
            "monitor": len(catalog.pool("monitor"))
        }
    }

# =============================================================================
# Authentication API
# =============================================================================
@app.post("/api/admin/login")
def api_admin_login(payload: LoginPayload):
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah"
        )
    token = create_access_token(data={"sub": payload.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": payload.username
    }

@app.get("/api/admin/me")
def api_admin_me(current_admin: str = Depends(get_current_admin)):
    return {"username": current_admin, "status": "authenticated"}

# =============================================================================
# Admin Catalog API (Terproteksi — Wajib JWT Token)
# =============================================================================
@app.get("/api/admin/stats")
def get_admin_stats(current_admin: str = Depends(get_current_admin)):
    prods = list_products()
    by_cat = {}
    for p in prods:
        c = p.get("kategori", "lainnya")
        by_cat[c] = by_cat.get(c, 0) + 1
    return {
        "total_products": len(prods),
        "categories": by_cat
    }

@app.get("/api/admin/products")
def api_list_products(category: str | None = None, current_admin: str = Depends(get_current_admin)):
    return list_products(category=category)

@app.get("/api/admin/products/{kode}")
def api_get_product(kode: str, current_admin: str = Depends(get_current_admin)):
    p = get_product_by_code(kode)
    if not p:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    return p

@app.post("/api/admin/products")
def api_save_product(payload: ProductPayload, current_admin: str = Depends(get_current_admin)):
    data = payload.model_dump()
    if data.get('gpu_dedicated') == 1 and (data.get('vram_gb') is None or str(data.get('vram_gb')).strip() == ''):
        raise HTTPException(status_code=400, detail='Produk dengan GPU Dedicated wajib mencantumkan kapasitas VRAM')
    sync_q = data.pop("sync_qdrant", True)
    try:
        saved, q_synced = upsert_product(data, sync_qdrant=sync_q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "success": True,
        "product": saved,
        "qdrant_synced": q_synced
    }

@app.delete("/api/admin/products/{kode}")
def api_delete_product(kode: str, sync_qdrant: bool = True, current_admin: str = Depends(get_current_admin)):
    existing = get_product_by_code(kode)
    if not existing:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    ok = delete_product_record(kode, sync_qdrant=sync_qdrant)
    return {"success": ok, "deleted_code": kode}

@app.post("/api/admin/sync-qdrant")
def api_sync_qdrant(current_admin: str = Depends(get_current_admin)):
    res = sync_all_products_to_qdrant()
    return res

@app.post("/api/admin/upload-image")
async def api_upload_image(
    file: UploadFile = File(...),
    current_admin: str = Depends(get_current_admin)
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa format gambar valid (jpg, png, webp, dll.)")
    
    ext = os.path.splitext(file.filename or "")[1].lower()
    if not ext or ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        ext = ".png"
    unique_filename = f"prod_{uuid.uuid4().hex[:12]}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "filename": unique_filename,
        "url": f"/uploads/{unique_filename}"
    }

@app.get("/api/admin/chat-logs")
def api_get_chat_logs(
    limit: int = 50,
    session_id: str | None = None,
    channel: str | None = None,
    current_admin: str = Depends(get_current_admin)
):
    """Mengambil riwayat percakapan pelanggan untuk evaluasi CS."""
    logs = get_recent_logs(limit=limit, session_id=session_id, channel=channel)
    return {"logs": logs, "total": len(logs)}

@app.get("/api/admin/chat-logs/stats")
def api_get_chat_log_stats(current_admin: str = Depends(get_current_admin)):
    """Mengambil ringkasan statistik penggunaan chat."""
    return get_log_stats()

# =============================================================================
# Customer Live Chat API (Bebas Akses — Tanpa Otentikasi)
# =============================================================================
@app.post("/api/chat")
def api_chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong")
    res = process_chat_message(
        session_id=req.session_id,
        user_text=req.message,
        model=req.model
    )
    return res

@app.get("/api/chat/history/{session_id}")
def api_chat_history(session_id: str):
    return {"messages": get_chat_history(session_id)}

@app.post("/api/chat/reset")
def api_chat_reset(req: ResetRequest):
    return reset_chat_session(req.session_id)

# =============================================================================
# Flutter Web Static Frontend Mount (Production / Unified Single-Port Hosting)
# =============================================================================
FLUTTER_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend_flutter", "build", "web")
if os.path.isdir(FLUTTER_WEB_DIR):
    app.mount("/", StaticFiles(directory=FLUTTER_WEB_DIR, html=True), name="flutter_web")

