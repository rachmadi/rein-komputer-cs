# -*- coding: utf-8 -*-
"""
services/agentic_tool_engine.py
Mesin AI Agent Customer Care ReIn Komputer berbasis Tool Calling (Ollama /api/chat).

PRINSIP:
1. LLM memimpin percakapan dan menanggapi pelanggan seperti staf toko yang ramah.
2. Kode TIDAK menentukan maksud pelanggan, TIDAK memilih aksi, TIDAK memaksa slot.
3. Fakta produk dan kebijakan toko hanya dari isi alat, bukan pemblokir jawaban.
4. Balasan LLM dikirim utuh tanpa pemotongan kode.
5. Kartu produk dan foto hanya untuk produk yang disebut di balasan akhir dan berasal dari hasil alat giliran itu.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.catalog import Catalog
from services.catalog_service import get_active_catalog
from services.agent_tools import AGENT_TOOLS_SCHEMA, execute_agent_tool
from services.product_card import format_product_cards_message

logger = logging.getLogger("agentic_tool_engine")

def build_agent_system_prompt() -> str:
    from core.db import get_catalog_inventory
    inv = get_catalog_inventory()
    kategori_str = ", ".join(inv.get("kategori", []))
    merek_str = ", ".join(inv.get("merek", []))

    return (
        'Kamu staf toko ReIn Komputer yang melayani pelanggan lewat chat. Ramah, '
        'sopan, gaya chat Indonesia sehari-hari, sapa pelanggan "Kak".\n'
        'Layani obrolan, permintaan, dan pertanyaan pelanggan secara manusiawi, dan '
        'penuhi permintaan pelanggan secara langsung.\n'
        'Kamu punya dua alat: katalog untuk produk yang dijual, harga, spesifikasi, '
        'ketersediaan, dan jumlah produk; pengetahuan untuk penjelasan produk, '
        'panduan memilih sesuai kebutuhan, dan kebijakan toko.\n'
        'Setiap kali jawabanmu menyangkut produk, harga, spesifikasi, jumlah, atau '
        'kebijakan toko, panggil alat dulu dan jawab berdasarkan hasilnya. Jangan '
        'menyebut data yang tidak ada di hasil alat.\n'
        'Bila pelanggan meminta pilihan atau daftar produk, sebutkan nama dan harga '
        'produknya dari hasil katalog.\n'
        'Tanyakan kebutuhan hanya bila membantu memilih, dan jangan menjadikannya '
        'syarat untuk melayani. Jangan menebak kebutuhan yang belum disebut '
        'pelanggan.\n'
        'Balas maksimal 4 kalimat, tanpa markdown, emoji, atau daftar berpoin.\n'
        f'Kategori yang tersedia: {kategori_str}.\n'
        f'Merek yang tersedia: {merek_str}.'
    )


SYSTEM_PROMPT = build_agent_system_prompt()

FALLBACK_EMERGENCY_REPLY = "Mohon maaf Kak, sistem kami sedang mengalami kendala teknis sesaat. Boleh tolong ulangi pertanyaannya?"

STOP_WORDS = {
    "asus", "acer", "lenovo", "hp", "msi", "apple", "intel", "axioo", "dell", "lg", "brother", "epson", "canon",
    "laptop", "desktop", "monitor", "printer", "tower", "pro", "mini", "inch", "essential", "gen", "plus"
}


def summarize_tool_result(fn_name: str, result: Any) -> str:
    """Membuat ringkasan singkat dari hasil alat untuk pencatatan log."""
    if not isinstance(result, dict):
        return str(result)[:100]
    if fn_name == "cari_produk":
        prods = result.get("produk", [])
        if prods:
            codes = [p.get("kode", "") for p in prods if p.get("kode")]
            return f"Ditemukan {len(prods)} produk: {', '.join(codes)}"
        termurah = result.get("harga_termurah_katalog")
        if termurah:
            return f"0 produk. Harga termurah katalog: {termurah}"
        return "0 produk ditemukan"
    elif fn_name == "detail_produk":
        items = result.get("detail", [])
        codes = [it.get("kode", "") for it in items if it.get("kode")]
        return f"Detail lembar spesifikasi: {', '.join(codes)}"
    elif fn_name == "pengetahuan_kebutuhan":
        sumber = result.get("sumber", "")
        profil = result.get("profil_id") or result.get("judul", "")
        return f"Pengetahuan kebutuhan: {profil} ({sumber})"
    elif fn_name == "info_toko":
        topik = result.get("topik", "")
        return f"Info toko topik: {topik}"
    return str(result)[:100]


def is_product_mentioned_in_reply(product: dict, reply_text: str) -> bool:
    """
    Mengecek apakah produk secara spesifik disebut di balasan akhir LLM.
    Mencocokkan kode produk (misal KB-L19) atau token model unik dari namanya.
    """
    reply_lower = reply_text.lower()
    kode = product.get("kode", "").lower()
    if kode and re.search(rf"\b{re.escape(kode)}\b", reply_lower):
        return True

    nama = product.get("nama", "")
    tokens = [t.lower() for t in re.split(r"[\s\+\-/]+", nama) if len(t) >= 3 and t.lower() not in STOP_WORDS]
    # Ambil token yang mengandung karakter huruf dan bukan angka murni
    model_tokens = [t for t in tokens if any(c.isalpha() for c in t) and not t.isdigit()]

    for tok in model_tokens:
        if re.search(rf"\b{re.escape(tok)}\b", reply_lower):
            return True

    return False


def call_ollama_chat_raw(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434",
    num_predict: int = 1024,
    num_ctx: int = 8192,
    timeout: int = 120
) -> dict:
    """Memanggil endpoint /api/chat Ollama secara langsung dan mengembalikan respons mentah & metrik."""
    t0 = time.perf_counter()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "temperature": 0.2
        }
    }
    if tools:
        payload["tools"] = tools

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/chat",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        latency_ms = (time.perf_counter() - t0) * 1000
        data["_latency_ms"] = latency_ms
        data["_raw_output"] = body
        return data


def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Optional[Catalog] = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434",
    session_state: Optional[dict] = None,
    **kwargs
) -> dict[str, Any]:
    """
    Menjalankan 1 giliran percakapan dengan AI agent ReIn Komputer.
    Alur:
      1. Rakit pesan: prompt sistem + konteks produk riwayat + riwayat chat + pesan user
      2. Loop tool calling (maksimal 3 putaran):
         - LLM membalas langsung ATAU memanggil alat
         - Sistem mengeksekusi alat dan mengembalikan hasilnya ke LLM
         - LLM meramu jawaban akhir
      3. Ambil kartu produk & foto HANYA untuk produk yang disebut di balasan akhir dan berasal dari hasil alat giliran ini.
      4. Balasan LLM dikirim utuh tanpa dipotong kode.
    """
    t_start = time.perf_counter()
    cat = catalog or get_active_catalog()
    state = session_state if session_state is not None else kwargs.get("state") or {}

    # Siapkan catatan riwayat produk yang pernah disebut sebelumnya
    mentioned_history: list[dict] = state.get("mentioned_products") or []
    mentioned_notes = ""
    if mentioned_history:
        lines = ["\nCatatan riwayat produk yang pernah dibahas sebelumnya:"]
        seen_codes = set()
        for mp in reversed(mentioned_history):
            c = mp.get("kode")
            if c and c not in seen_codes:
                seen_codes.add(c)
                lines.append(f"- {c}: {mp.get('nama')}")
            if len(seen_codes) >= 5:
                break
        mentioned_notes = "\n".join(lines)

    system_content = build_agent_system_prompt()
    if mentioned_notes:
        system_content += "\n" + mentioned_notes

    # Format riwayat pesan
    messages: list[dict] = [{"role": "system", "content": system_content}]
    for m in history[-8:]:
        role = m.get("role") or ("assistant" if m.get("sender") in ("bot", "assistant") else "user")
        content = m.get("content") or m.get("text") or ""
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    MAX_TOOL_ROUNDS = 3
    round_idx = 0
    final_reply = ""
    all_tool_calls_logged: list[dict[str, Any]] = []
    all_llm_calls_logged: list[dict[str, Any]] = []
    all_tools_products_returned: list[dict[str, Any]] = []
    is_emergency_fallback = False
    emergency_error = None

    while round_idx < MAX_TOOL_ROUNDS:
        try:
            llm_resp = call_ollama_chat_raw(
                messages=messages,
                tools=AGENT_TOOLS_SCHEMA,
                model=model,
                url=url,
                num_predict=1024,
                num_ctx=8192,
                timeout=120
            )
        except Exception as e:
            logger.error(f"Ollama chat error pada putaran {round_idx + 1}: {e}", exc_info=True)
            emergency_error = str(e)
            is_emergency_fallback = True
            all_llm_calls_logged.append({
                "urutan": round_idx + 1,
                "prompt_eval_count": None,
                "eval_count": None,
                "done_reason": "error",
                "latensi_ms": 0.0,
                "latensi": 0.0,
                "raw_output": str(e),
                "error": str(e)
            })
            break

        msg = llm_resp.get("message", {})
        tool_calls = msg.get("tool_calls")
        latency_call = llm_resp.get("_latency_ms", 0.0)

        all_llm_calls_logged.append({
            "urutan": round_idx + 1,
            "prompt_eval_count": llm_resp.get("prompt_eval_count"),
            "eval_count": llm_resp.get("eval_count"),
            "done_reason": llm_resp.get("done_reason"),
            "latensi_ms": round(latency_call, 2),
            "latensi": round(latency_call, 2),
            "raw_output": llm_resp.get("_raw_output", "")
        })

        if not tool_calls:
            # LLM langsung memberikan jawaban akhir
            final_reply = msg.get("content", "").strip()
            break

        # LLM memanggil alat
        messages.append(msg)
        for tc in tool_calls:
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            fn_args = fn.get("arguments", {})
            if isinstance(fn_args, str):
                try:
                    fn_args = json.loads(fn_args)
                except Exception:
                    fn_args = {}

            t0_tool = time.perf_counter()
            tool_res = execute_agent_tool(fn_name, fn_args)
            t_tool = (time.perf_counter() - t0_tool) * 1000

            if isinstance(tool_res, dict) and "produk" in tool_res:
                prods = tool_res.get("produk", [])
                if isinstance(prods, list):
                    all_tools_products_returned.extend(prods)
            elif isinstance(tool_res, dict) and "detail" in tool_res:
                details = tool_res.get("detail", [])
                if isinstance(details, list):
                    all_tools_products_returned.extend(details)

            ringkasan = summarize_tool_result(fn_name, tool_res)
            all_tool_calls_logged.append({
                "nama": fn_name,
                "argumen": fn_args,
                "ringkasan_hasil": ringkasan,
                "latensi_ms": round(t_tool, 2),
                "latensi": round(t_tool, 2),
            })

            messages.append({
                "role": "tool",
                "content": json.dumps(tool_res, ensure_ascii=False)
            })

        round_idx += 1

    # Jika setelah loop belum ada final_reply dan tidak ada error, minta balasan akhir sintetis tanpa alat
    if not final_reply and not is_emergency_fallback:
        try:
            llm_resp_final = call_ollama_chat_raw(
                messages=messages,
                tools=None,
                model=model,
                url=url,
                num_predict=1024,
                num_ctx=8192,
                timeout=120
            )
            final_reply = llm_resp_final.get("message", {}).get("content", "").strip()
            all_llm_calls_logged.append({
                "urutan": round_idx + 1,
                "prompt_eval_count": llm_resp_final.get("prompt_eval_count"),
                "eval_count": llm_resp_final.get("eval_count"),
                "done_reason": llm_resp_final.get("done_reason"),
                "latensi_ms": round(llm_resp_final.get("_latency_ms", 0.0), 2),
                "latensi": round(llm_resp_final.get("_latency_ms", 0.0), 2),
                "raw_output": llm_resp_final.get("_raw_output", "")
            })
        except Exception as e:
            logger.error(f"Ollama final synthesis error: {e}", exc_info=True)
            is_emergency_fallback = True
            emergency_error = str(e)

    if is_emergency_fallback or not final_reply:
        final_reply = FALLBACK_EMERGENCY_REPLY

    # Saring produk yang disebut di balasan akhir dan berasal dari hasil alat giliran ini
    mentioned_this_turn: list[dict] = []
    seen_turn_codes = set()
    for p in all_tools_products_returned:
        code = p.get("kode")
        if code and code not in seen_turn_codes:
            seen_turn_codes.add(code)
            if is_product_mentioned_in_reply(p, final_reply):
                # Ambil spesifikasi lengkap dari katalog resmi jika tersedia
                cat_p = cat.by_code.get(code)
                prod_data = dict(cat_p) if cat_p else dict(p)
                # Pastikan key standar tersedia
                if "harga" not in prod_data and "harga_idr" in prod_data:
                    prod_data["harga"] = prod_data["harga_idr"]
                mentioned_this_turn.append(prod_data)

    # Susun kartu produk Telegram HTML (hanya jika ada produk yang disebut)
    kartu_html = format_product_cards_message(mentioned_this_turn) if mentioned_this_turn else None

    # Perbarui riwayat produk yang pernah dibahas di session_state
    new_mentioned = list(mentioned_history)
    for p in mentioned_this_turn:
        if not any(x.get("kode") == p.get("kode") for x in new_mentioned):
            new_mentioned.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "harga": p.get("harga") or p.get("harga_idr")
            })

    # GroundingChecker LOG SAJA (Butir 4b): tidak memblokir, tidak memicu retry, tidak mengganti balasan
    pemeriksa_catatan: list[str] = []
    try:
        from services.grounding_checker import GroundingChecker
        checker = GroundingChecker()
        fakta_log = {
            "produk": mentioned_this_turn or all_tools_products_returned,
            "produk_tampil": mentioned_this_turn or all_tools_products_returned,
            "tool_calls": all_tool_calls_logged,
            "status": "sukses" if not is_emergency_fallback else "sistem_error",
        }
        _, violations = checker.check(final_reply, fakta=fakta_log, state=state)
        pemeriksa_catatan = violations
    except Exception as check_err:
        logger.warning(f"GroundingChecker log-only error: {check_err}")
        pemeriksa_catatan = [f"checker_error: {check_err}"]

    total_latency_ms = (time.perf_counter() - t_start) * 1000

    return {
        "reply": final_reply,
        "products": mentioned_this_turn,
        "kartu_produk_html": kartu_html,
        "route": "AGENTIC_TOOL",
        "tool_calls": all_tool_calls_logged,
        "tools_called": [tc["nama"] for tc in all_tool_calls_logged],
        "llm_calls": all_llm_calls_logged,
        "generator_calls": all_llm_calls_logged,
        "latency_ms": round(total_latency_ms, 2),
        "is_emergency_fallback": is_emergency_fallback,
        "emergency_error": emergency_error,
        "mentioned_products": new_mentioned,
        "pemeriksa_catatan": pemeriksa_catatan,
    }
