# -*- coding: utf-8 -*-
"""
Core Engine: Finite State Machine & Routing Policy (§5B, §15, §20)
Fungsi murni: step(state, user_text, catalog, nlu=None) -> (new_state, reply, route)
"""
from __future__ import annotations

import copy
import re
from core.normalizer import normalize, has_phrase, find_phrase
from core.taxonomy import (
    CATEGORY_LABEL, CATEGORY_NOUN_NYA, CATEGORY_WORDS, NEED_LABEL, NEED_TAGS,
    AFFIRM_WORDS, CANCEL_SET, CLOSING_SET, AVAIL_VERBS, BRAND_LEXICON
)
from core.catalog import Catalog, has_tag, tag_entries
from core.state import new_state, reset_state, has_filter, has_rank, apply_budget, apply_prefs
from core.acts import (
    extract_needs, extract_persona, extract_persona_name, extract_user_type, extract_category,
    extract_budget, extract_preferences, extract_vendor_os, extract_brand, detect_attrs,
    detect_unavailable, is_meta_critique, is_uncertain, is_correction,
    detect_category_guard, REL_PHRASES, COMPARE_WORDS, COMPARE_PHRASES,
    PURCHASE_TOKENS, is_insult, is_catalog_doubt, is_meta_explanation,
    is_capability_inquiry, is_banter, is_spec_or_rag_query, is_mismatch,
    is_choice_or_recommendation_query, is_type_or_inventory_query, GPU_EXPLANATION_PHRASES,
    is_hardware_spec_query, is_spec_objection, is_persona_insist, is_need_negation,
    is_size_or_weight_objection, is_recommendation_request, is_need_insist,
    extract_vendor_negation, extract_brand_negation, is_price_confirm_or_inquiry,
    is_alternative_request
)
from core.responses import (
    format_price, format_juta, render_product_lines, render_summary,
    answer_attrs, compare_answer, render_decision_assistance,
    render_decision_advice, validate_reply, need_labels, specs_line
)
from core.llm import query_llm_fallback, query_llm_opening, query_llm_product_chat

GREET_RE = r"(?:halo|hai|hello|hi|hei|p|(?:selamat )?(?:pagi|siang|sore|malam)|permisi|assalamualaikum)"
HONOR_RE = r"(?:kak|kakak|mas|mbak|om|tante|pak|bu|bapak|ibu|admin|min|cs|dek|adek|adik|bang|bro|sis|gan)"
BYE_RE = r"(?:bye|bye bye|dadah|dah|sampai jumpa|selamat tinggal|sampai nanti)(?: kak)?"
IDENTITY_SET = {"siapa kamu", "kamu siapa", "anda siapa", "siapa anda", "ini siapa"}
LIST_SET = {"jual apa", "jualan apa", "produk apa", "punya apa", "ada apa saja", "ada apa",
            "jual apa saja", "produk apa saja", "punya apa saja", "jual apa aja", "ada apa aja", "punya apa aja"}

def is_pure_greeting(norm: str) -> bool:
    """Deteksi salam murni (sekadar salam) tanpa pertanyaan atau maksud lain."""
    words = [re.sub(r"[^\w]", "", w) for w in norm.split()]
    words = [w for w in words if w]
    if not words:
        return False
    greet_tokens = {"halo", "hai", "hello", "hi", "hei", "p", "permisi", "assalamualaikum", "selamat", "pagi", "siang", "sore", "malam"}
    honor_tokens = {"kak", "kakak", "mas", "mbak", "om", "tante", "pak", "bu", "bapak", "ibu", "admin", "min", "cs", "dek", "adek", "adik", "bang", "bro", "sis", "gan"}
    return all(w in greet_tokens or w in honor_tokens for w in words)

def all_category_str(catalog: Catalog, conj: str = "atau") -> str:
    cats = [CATEGORY_LABEL[c] for c in ("laptop", "desktop", "printer", "monitor")
            if any(p["kategori"] == c for p in catalog.products)]
    if not cats:
        return f"laptop, desktop, {conj} printer"
    if len(cats) == 1:
        return cats[0]
    return ", ".join(cats[:-1]) + f", {conj} " + cats[-1]

def category_counts(catalog: Catalog) -> str:
    parts = []
    for cat, label in (("laptop", "laptop"), ("desktop", "desktop"), ("printer", "printer"), ("monitor", "monitor")):
        n = sum(1 for p in catalog.products if p["kategori"] == cat)
        if n:
            parts.append(f"{label} ({n} produk)")
    return ", ".join(parts)

def strip_greeting(norm: str) -> str:
    m = re.match(rf"^{GREET_RE}(?: {HONOR_RE})*\s+(.+)$", norm)
    return m.group(1) if m else norm

# Pola pertanyaan bundling/inklusi produk: "termasuk monitor gak?", "sudah termasuk monitor?", "include monitor gak?"
_BUNDLE_PATTERNS = re.compile(
    r"\b(?:termasuk|sudah termasuk|sudah include|udah termasuk|include|sudah ada|apa sudah ada)\b"
    r"\s+(?:\w+\s+)*(?:monitor|keyboard|mouse|speaker|headset|tas|bag|dus|box|kabel|charger|adaptor|garansi|"
    r"aksesoris|aksesori)\b",
    re.IGNORECASE
)

def is_bundle_question(norm_text: str, state: dict | None = None) -> str | None:
    """Deteksi pertanyaan bundling/inklusi produk: 'termasuk monitor gak?', 'sudah termasuk keyboard?'
    
    Returns the mentioned item if detected, None otherwise.
    """
    m = _BUNDLE_PATTERNS.search(norm_text)
    if m:
        # Ekstrak item yang ditanyakan (kata terakhir dalam match)
        words = m.group(0).split()
        return words[-1].lower()
    # Pola tambahan: "monitornya termasuk gak?", "monitornya include gak?"
    m2 = re.search(
        r"\b(monitor|keyboard|mouse|speaker|headset|tas|bag|kabel|charger|adaptor|garansi|aksesoris)\b"
        r"(?:nya)?\s+(?:termasuk|include|masuk)\b",
        norm_text, re.IGNORECASE
    )
    if m2:
        return m2.group(1).lower()
    # Konteks desktop yang sedang dibahas
    if state and (state.get("category") == "desktop" or any("tower" in str(p).lower() or "desktop" in str(p).lower() for p in state.get("offered_products", []))):
        if re.search(r"\b(?:ada|dapat|dapet)\s+monitor(?:nya)?\b", norm_text):
            return "monitor"
        if re.search(r"\bmonitor(?:nya)?\s+(?:ada|dapet|dapat)\b", norm_text):
            return "monitor"
    return None

def is_category_confirm_query(norm_clean: str, raw: str, state: dict, catalog: Catalog) -> tuple[str, list[dict]] | None:
    """
    Deteksi pertanyaan konfirmasi jenis/kategori produk yang sedang dibahas.
    Misal: 'Itu desktop?', 'Loq itu desktop?', 'Bukannya loq itu laptop?'.
    Returns: (target_category, matched_products) or None
    """
    # Jangan intersep jika ini pertanyaan daftar inventaris / tipe apa saja / keraguan jumlah pilihan
    if is_type_or_inventory_query(norm_clean) or any(has_phrase(norm_clean, p) for p in (
        "ada apa", "jual apa", "punya apa", "ada tipe apa", "apa saja", "apa aja",
        "tipe apa", "seri apa", "pilihan apa", "daftar tipe", "rekomendasi",
        "cuma itu", "itu doang", "hanya itu", "cuma 1", "cuma satu", "segitu doang"
    )) or "doang" in norm_clean.split():
        return None

    toks = norm_clean.split()
    target_cat = None
    if "desktop" in toks or "pc" in toks:
        target_cat = "desktop"
    elif "laptop" in toks:
        target_cat = "laptop"
    elif "printer" in toks:
        target_cat = "printer"
        
    if not target_cat:
        return None
        
    # Cek apakah ada penanda pertanyaan konfirmasi:
    # '?' pada raw, kata tanya konfirmasi (apakah, emang, bukannya, beneran, kan, ya, kah, bukan),
    # atau kata tunjuk (itu, ini, tersebut)
    is_q = (
        "?" in raw
        or any(w in toks for w in ("apakah", "bukannya", "emang", "beneran", "kan", "ya", "kah", "bukan"))
        or any(w in toks for w in ("itu", "ini", "tersebut"))
    )
    if not is_q:
        return None

    offered_codes = state.get("offered_products", [])
    offered_prods = [catalog.by_code[c] for c in offered_codes if c in catalog.by_code]

    # Cek penyebutan model spesifik (BUKAN merek vendor utama seperti lenovo/asus/acer)
    # Misal 'loq', 'ideacentre', 'vivobook', 'nitro', dsb.
    specific_model = None
    for t in toks:
        if (
            len(t) >= 3
            and t not in ("itu", "ini", "dan", "atau", "apa", "nya", "deh", "kak", "aja", "gak", "tidak",
                          "desktop", "laptop", "printer", "komputer", "bukan", "apakah", "emang", "kalau", "kalo")
            and t not in BRAND_LEXICON.keys()
        ):
            matching = [p for p in catalog.products if t in p["nama"].lower()]
            if matching:
                specific_model = matching
                break

    if specific_model:
        return target_cat, specific_model
    elif offered_prods and any(w in toks for w in ("itu", "ini", "keduanya", "semua", "tersebut")):
        # Hanya cocokkan jika kata tunjuk (itu/ini) merujuk pada kategori:
        # e.g. "itu desktop", "apakah itu desktop", "ini desktop ya"
        if any(has_phrase(norm_clean, p) for p in (
            "itu desktop", "ini desktop", "tersebut desktop", "keduanya desktop", "semua desktop",
            "itu laptop", "ini laptop", "tersebut laptop", "keduanya laptop", "semua laptop",
            "itu pc", "ini pc", "tersebut pc", "itu printer", "ini printer"
        )) or "?" in raw:
            return target_cat, offered_prods
        
    return None

def handle_category_confirm(target_cat: str, target_prods: list[dict], state: dict, catalog: Catalog) -> tuple[str, str]:
    # Jika produk yang disebut memiliki varian desktop DAN laptop (seperti Lenovo LOQ)
    has_desktop = any(p["kategori"] == "desktop" for p in target_prods)
    has_laptop = any(p["kategori"] == "laptop" for p in target_prods)
    
    if has_desktop and has_laptop:
        d_prod = next(p for p in target_prods if p["kategori"] == "desktop")
        l_prod = next(p for p in target_prods if p["kategori"] == "laptop")
        words = d_prod["nama"].split()
        base_name = words[1] if len(words) > 1 and words[0].lower() in BRAND_LEXICON else d_prod["nama"]
        state["offered_products"] = [d_prod["kode"], l_prod["kode"]]
        state["pool"] = [d_prod["kode"], l_prod["kode"]]
        state["category"] = target_cat
        state["fsm_stage"] = "OFFERED"
        
        if target_cat == "desktop":
            reply = (
                f"Betul sekali, Kak! Seri **{d_prod['nama']}** yang tertera di atas adalah komputer desktop (PC Tower), bukan laptop.\n\n"
                f"Seri {base_name} memang populer sebagai laptop (di katalog kami ada varian laptopnya yaitu **{l_prod['nama']}**), "
                f"namun tipe yang di atas adalah versi desktop PC gaming bertenaga {specs_line(d_prod)}.\n\n"
                f"Apakah Kakak mencari varian desktop PC atau sedang mencari yang versi laptopnya?"
            )
        else:
            reply = (
                f"Iya betul Kak, seri {base_name} memang ada versi laptopnya yaitu **{l_prod['nama']}** "
                f"({specs_line(l_prod)}, harga {format_price(l_prod['harga_idr'])}).\n\n"
                f"Sedangkan yang tertera di daftar pilihan tadi adalah varian PC desktop-nya yaitu **{d_prod['nama']}**.\n\n"
                f"Mau saya jelaskan lebih lanjut untuk varian laptop atau desktopnya, Kak?"
            )
        return reply, "CATEGORY_CONFIRM"

    # Jika produk yang ditanyakan seluruhnya memang sesuai kategori target
    all_match = all(p["kategori"] == target_cat for p in target_prods)
    if all_match:
        cat_label = CATEGORY_LABEL.get(target_cat, target_cat)
        state["offered_products"] = [p["kode"] for p in target_prods]
        state["pool"] = [p["kode"] for p in target_prods]
        state["category"] = target_cat
        state["fsm_stage"] = "OFFERED"
        if len(target_prods) == 1:
            p = target_prods[0]
            state["selected_product"] = p["kode"]
            if p.get("brand"):
                state["constraints"]["brand"] = p["brand"]
            extra = " (unit PC tanpa monitor)" if target_cat == "desktop" else ""
            reply = (
                f"Iya betul, Kak! **{p['nama']}** adalah perangkat {cat_label}{extra} "
                f"yang dibekali {specs_line(p)}.\n\n"
                f"Ada yang ingin ditanyakan lagi tentang spesifikasinya?"
            )
            return reply, "CATEGORY_CONFIRM"
        else:
            prod_names = " dan ".join(f"**{p['nama']}**" for p in target_prods[:2])
            extra = " (unit PC tanpa monitor ya Kak)" if target_cat == "desktop" else ""
            reply = (
                f"Iya betul, Kak! Pilihan di atas ({prod_names}) adalah perangkat {cat_label}{extra}.\n\n"
                f"Ada yang ingin Kakak tanyakan lebih lanjut tentang spesifikasi salah satunya, atau ada kebutuhan tertentu yang ingin disesuaikan?"
            )
            return reply, "CATEGORY_CONFIRM"

    # Jika tidak cocok (misal user tanya 'itu laptop?' padahal desktop)
    actual_cats = list({CATEGORY_LABEL.get(p["kategori"], p["kategori"]) for p in target_prods})
    cat_str = " dan ".join(actual_cats)
    reply = (
        f"Bukan Kak, pilihan di atas adalah perangkat {cat_str}. "
        f"Jika Kakak mencari {CATEGORY_LABEL.get(target_cat, target_cat)}, mau saya tunjukkan pilihan {CATEGORY_LABEL.get(target_cat, target_cat)} yang tersedia di katalog kami?"
    )
    return reply, "CATEGORY_CONFIRM"

def apply_constraints(pool: list[dict], c: dict) -> list[dict]:
    out = []
    for p in pool:
        price = p["harga_idr"]
        if c.get("budget_max") is not None:
            if c["budget_max_strict"]:
                if not price < c["budget_max"]:
                    continue
            elif not price <= c["budget_max"]:
                continue
        if c.get("budget_min") is not None:
            if c["budget_min_strict"]:
                if not price > c["budget_min"]:
                    continue
            elif not price >= c["budget_min"]:
                continue
        if c.get("vendor") and p.get("cpu_vendor") != c["vendor"]:
            continue
        if c.get("excluded_vendor") and p.get("cpu_vendor") == c["excluded_vendor"]:
            continue
        if c.get("os") and (not p.get("os") or c["os"] not in p["os"].lower()):
            continue
        if c.get("excluded_brand"):
            ex_aliases = BRAND_LEXICON.get(c["excluded_brand"].lower(), [c["excluded_brand"].lower()])
            if any(alias in p["nama"].lower() for alias in ex_aliases):
                continue
        if c.get("brand"):
            brand_req = c["brand"].lower()
            aliases = BRAND_LEXICON.get(brand_req, [brand_req])
            p_name = p["nama"].lower()
            if not any(alias in p_name for alias in aliases):
                continue
        out.append(p)
    return out

def build_ranked(s: dict, catalog: Catalog) -> dict:
    c = s["constraints"]
    prefs = set(s["preferences"])
    pool = catalog.pool(s["category"])
    needs = s["needs"]
    split = False
    
    if needs:
        inter = [p for p in pool if all(has_tag(p, n) for n in needs)]
        if inter:
            base = inter
        else:
            base = []
            for n in needs:
                for p in pool:
                    if has_tag(p, n) and p not in base:
                        base.append(p)
            split = True
    else:
        base = list(pool)
        
    unfiltered = base
    base = apply_constraints(base, c)
    notes = []
    items = sorted(base, key=lambda p: p["harga_idr"])

    if not needs and s["category"] in (None, "computer") and \
            prefs & {"cheapest", "most_expensive"} and items:
        per = []
        for cat in ("laptop", "desktop"):
            sub = [p for p in items if p["kategori"] == cat]
            if sub:
                per.append(sub[0] if "cheapest" in prefs else sub[-1])
        items = per
        notes.append("per_category")
    elif "cheapest" in prefs and items:
        notes.append(("cheapest", len(items)))
        items = items[:1]
    elif "most_expensive" in prefs and items:
        notes.append(("most_expensive", len(items)))
        items = items[-1:]
    else:
        if c["budget_target"] is not None and items:
            t = c["budget_target"]
            items = sorted(items, key=lambda p: (abs(p["harga_idr"] - t), p["harga_idr"]))
            notes.append(("target", t))
        if "large_ram" in prefs and items:
            rams = {p["ram_gb"] for p in items}
            if len(rams) == 1:
                notes.append(("ram_tie", items[0]["ram_gb"],
                              sorted({p["ram_type"] for p in items if p["ram_type"]})))
            else:
                items = sorted(items, key=lambda p: (-(p["ram_gb"] or 0), p["harga_idr"]))
                notes.append(("ram_sorted",))
        if "large_processor" in prefs:
            notes.append(("cpu_unrankable",))
        if "discrete_gpu" in prefs and items:
            discrete_items = [p for p in items if p.get("gpu_type") == "discrete" or (p.get("gpu") and any(x in p["gpu"].lower() for x in ("rtx", "gtx", "geforce", "radeon rx")))]
            if discrete_items:
                items = discrete_items
                notes.append(("discrete_gpu", len(items)))
        if "large_vram" in prefs and items:
            from core.responses import vram_gb
            items = sorted(items, key=lambda p: (-(p.get("gpu_vram") or vram_gb(p) or 0), p["harga_idr"]))
            notes.append(("vram_sorted",))

    related = []
    if (needs == ["design"] and not split and items and
            not prefs & {"cheapest", "most_expensive"} and len(items) < 3):
        cat = items[0]["kategori"]
        cand = [p for p in apply_constraints(catalog.pool(cat), c)
                if not has_tag(p, "design") and
                (has_tag(p, "video_editing") or has_tag(p, "rendering_3d"))]
        cand.sort(key=lambda p: p["harga_idr"])
        related = cand[:1]
        
    return {"items": items, "notes": notes, "split": split, "unfiltered": unfiltered,
            "related": related}

def subject_label(s: dict) -> str:
    label = CATEGORY_LABEL.get(s["category"], "komputer")
    if s["needs"]:
        label += " untuk " + need_labels(s["needs"])
    return label

def budget_desc(c: dict) -> str:
    if c["budget_max"] is not None:
        return ("di bawah " if c["budget_max_strict"] else "maksimal ") + format_juta(c["budget_max"])
    if c["budget_min"] is not None:
        return ("di atas " if c["budget_min_strict"] else "minimal ") + format_juta(c["budget_min"])
    return ""

def empty_reply(s: dict, catalog: Catalog, r: dict) -> tuple[str, str]:
    c = s["constraints"]
    label = subject_label(s)
    unf = r["unfiltered"]
    cat_noun = CATEGORY_NOUN_NYA.get(s.get("category"), "perangkat")
    if unf:
        if c["budget_max"] is not None and min(p["harga_idr"] for p in unf) > c["budget_max"]:
            alt = min(unf, key=lambda p: p["harga_idr"])
            s["last_question"] = {"slot": "confirm_product", "product": alt["kode"]}
            return (f"Mohon maaf, Kak, untuk {label} yang paling terjangkau di katalog kami adalah {alt['nama']} "
                    f"di harga {format_price(alt['harga_idr'])}, jadi belum ada yang {budget_desc(c)}. "
                    f"Mau saya jelaskan spesifikasi {cat_noun} tersebut?"), "EMPTY"
        if c["budget_min"] is not None and max(p["harga_idr"] for p in unf) < c["budget_min"]:
            alt = max(unf, key=lambda p: p["harga_idr"])
            s["last_question"] = {"slot": "confirm_product", "product": alt["kode"]}
            return (f"Mohon maaf, Kak, untuk {label} di katalog kami saat ini adalah {alt['nama']} "
                    f"di harga {format_price(alt['harga_idr'])}, jadi belum ada yang {budget_desc(c)}. "
                    f"Mau saya jelaskan spesifikasi {cat_noun} tersebut?"), "EMPTY"
        alt = min(unf, key=lambda p: p["harga_idr"])
        s["last_question"] = {"slot": "confirm_product", "product": alt["kode"]}
        what = c["vendor"] or c["os"] or (f"brand {c['brand'].title()}" if c.get("brand") else "kriteria tersebut")
        return (f"Maaf, Kak, belum ada {label} dengan {what} di katalog kami. "
                f"Pilihan terdekat adalah {alt['nama']} ({format_price(alt['harga_idr'])}). "
                "Mau saya jelaskan detailnya?"), "EMPTY"
    
    alts = []
    for p in catalog.products:
        if p["kategori"] != s["category"] and not p["is_accessory"] and \
                all(has_tag(p, n) for n in s["needs"]):
            alts.append(p)
    msg = f"Mohon maaf, Kak, di katalog kami belum ada {label} yang sesuai."
    if alts:
        a = min(alts, key=lambda p: p["harga_idr"])
        s["last_question"] = {"slot": "confirm_product", "product": a["kode"]}
        msg += (f" Namun ada seri {a['nama']} ({a['kategori']}) yang cocok untuk "
                f"{need_labels(s['needs'])}. Mau saya jelaskan detailnya?")
    return msg, "EMPTY"

def render_offer(s: dict, catalog: Catalog, r: dict, prefix: str = "") -> str:
    items = r["items"]
    shown = items[:3]
    rest = items[3:]
    needs = s["needs"]
    show_price = not s["hide_price"]
    out = []
    intro = f"{prefix}" if prefix else ""
    if needs:
        cooking_words = ("masak", "memasak", "resep", "dapur", "kue", "baking")
        hist = s.get("history", [])
        curr = s.get("_current_raw", "").lower()
        last_user_texts = curr + " " + " ".join([t[1].lower() for t in hist[-3:] if t[0] == "user"])
        if any(w in last_user_texts for w in cooking_words):
            target = f" untuk {s['persona_name']}" if s.get("persona_name") else ""
            head = f"Wah, kalau untuk masak atau lihat resep video di YouTube{target}, "
        else:
            head = f"Untuk {need_labels(needs)}, "
    else:
        head = ""
    if len(shown) == 1:
        intro += head + "ada satu rekomendasi yang sesuai di katalog kami:"
    else:
        intro += head + "ada beberapa pilihan yang bisa dipertimbangkan:"
    intro = intro[0].upper() + intro[1:] if intro else intro
    out.append(intro)
    out += render_product_lines(shown, needs, show_price)
    
    for note in r["notes"]:
        if note == "per_category":
            out.append("Ini pilihan yang paling " + ("terjangkau" if "cheapest" in s["preferences"]
                                                   else "tinggi") + " untuk tiap kategori.")
        elif note[0] == "cheapest":
            out.append("Ini seri yang paling murah dari " + str(note[1]) + " pilihan yang sesuai di katalog kami."
                       if note[1] > 1 else "Ini satu-satunya pilihan yang sesuai di katalog kami.")
        elif note[0] == "most_expensive":
            out.append("Ini seri yang paling tinggi dari " + str(note[1]) + " pilihan yang sesuai di katalog kami."
                       if note[1] > 1 else "Ini satu-satunya pilihan yang sesuai di katalog kami.")
        elif note[0] == "target":
            out.append(f"Daftar ini diurutkan berdasarkan selisih harga terdekat terhadap kisaran {format_juta(note[1])}.")
        elif note[0] == "ram_tie":
            types = "/".join(note[2])
            out.append(f"Catatan: semua pilihan di atas memiliki RAM {note[1]} GB yang sama. Perbedaannya ada pada jenis memori ({types}).")
        elif note[0] == "ram_sorted":
            out.append("Daftar diurutkan dari kapasitas RAM terbesar.")
        elif note[0] == "cpu_unrankable":
            out.append("Catatan: katalog tidak memuat perbandingan performa prosesor secara kuantitatif, sehingga tidak diranking. Tipe prosesor tertera pada spesifikasi masing-masing.")
            
    if r["split"]:
        out.append("Karena belum ada produk yang mencakup semua kebutuhan sekaligus, kami tawarkan pilihan untuk masing-masing kebutuhan.")
    for p in r["related"]:
        phr = [t["phrase"] for t in tag_entries(p, ("video_editing", "rendering_3d"))]
        out.append(f"Sebagai catatan tambahan, seri **{p['nama']}** tidak disebut khusus untuk "
                   f"{need_labels(needs)} di katalog, tapi cocok untuk "
                   f"{', '.join(phr)} dan memakai {p['gpu']}."
                   + (f" Harga {format_price(p['harga_idr'])}." if show_price else ""))
    if any(p["kategori"] == "desktop" for p in shown):
        out.append("Perhatian: untuk desktop, monitor tidak termasuk ya Kak.")
    if rest:
        out.append(f"Masih ada {len(rest)} pilihan lain di katalog kami jika ingin melihat opsi lainnya.")
    else:
        out.append("Kalau mau, kita masih bisa mempersempit pilihan berdasarkan budget atau spesifikasi tertentu.")
    return "\n".join(out)

def do_offer(s: dict, catalog: Catalog, prefix: str = "", route: str = "OFFER"):
    r = build_ranked(s, catalog)
    if not r["items"]:
        return empty_reply(s, catalog, r)
    items = r["items"]
    all_offered = [p["kode"] for p in items[:3]]
    for p in r.get("related", []):
        if p["kode"] not in all_offered:
            all_offered.append(p["kode"])
    s["offered_products"] = all_offered
    s["pool"] = [p["kode"] for p in items]
    s["shown"] = list(s["offered_products"])
    s["selected_product"] = None
    s["fsm_stage"] = "OFFERED"
    return render_offer(s, catalog, r, prefix), route

def do_spread(s: dict, catalog: Catalog, intro: str):
    pool = sorted(catalog.pool(s["category"]), key=lambda p: p["harga_idr"])
    if not pool:
        return "Maaf, Kak, untuk kategori tersebut belum ada produk di katalog kami.", "EMPTY"
    picks = [("termurah", pool[0])]
    if len(pool) > 2:
        picks.append(("menengah", pool[len(pool) // 2]))
    if len(pool) > 1:
        picks.append(("tertinggi", pool[-1]))
    s["offered_products"] = [p["kode"] for _, p in picks]
    s["pool"] = [p["kode"] for p in pool]
    s["shown"] = list(s["offered_products"])
    s["selected_product"] = None
    s["spread_shown"] = True
    s["fsm_stage"] = "OFFERED"
    s["last_question"] = {"slot": "need"}
    show_price = not s["hide_price"]
    lines = [intro]
    for i, (tag, p) in enumerate(picks, 1):
        price = f" Harga {format_price(p['harga_idr'])}." if show_price else ""
        extra = " (Monitor tidak termasuk ya Kak)" if p["kategori"] == "desktop" else ""
        usage_str = f" Katalog: {p['usage_text']}" if p.get("usage_text") else ""
        lines.append(f"{i}. ({tag}) **{p['nama']}** — {specs_line(p)}.{extra}{usage_str}{price}")
    lines.append("Kalau Kakak cerita mau dipakai untuk apa, saya bisa pilihkan yang lebih pas.")
    return "\n".join(lines), "SPREAD"

def ask_need(s: dict, prefix: str = "", custom: str | None = None):
    s["asked_slots"].append("need")
    s["last_question"] = {"slot": "need"}
    s["fsm_stage"] = "AWAITING_NEED"
    if custom:
        return prefix + custom, "ASK"
    brand = s.get("constraints", {}).get("brand")
    cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "komputer"
    if brand:
        q = f"{cat_name.title()} {brand.title()} mau dipakai untuk apa, Kak?"
    elif s["category"]:
        q = f"{CATEGORY_NOUN_NYA[s['category']]} mau dipakai untuk apa, Kak?"
    else:
        q = "Mau dipakai untuk apa, Kak?"
    return prefix + q, "ASK"

def decide(s: dict, catalog: Catalog, prefix: str = "", route: str = "OFFER"):
    has_non_brand_filter = any(s["constraints"].get(k) is not None for k in ("budget_max", "budget_min", "budget_target", "vendor", "os"))
    if s["needs"] or has_non_brand_filter or has_rank(s):
        return do_offer(s, catalog, prefix, route)
    if "need" not in s["asked_slots"]:
        return ask_need(s, prefix)
    if not s["spread_shown"]:
        intro = ("Supaya ada gambaran, ini pilihan dari yang termurah sampai tertinggi:" if prefix else
                 "Baik, Kak, supaya ada gambaran, ini pilihan dari yang termurah sampai tertinggi:")
        return do_spread(s, catalog, prefix + intro)
    return ("Dari pilihan di atas, ada yang mau saya jelaskan lebih detail spesifikasinya?", "SPREAD2")

def extract_hardware_spec_filter(text: str) -> dict | None:
    text_l = text.lower()
    spec = {}
    
    # 1. CPU Vendor & Negation
    neg_v = extract_vendor_negation(text_l)
    if neg_v:
        spec["cpu_vendor"] = neg_v["target"]
        spec["excluded_vendor"] = neg_v["excluded"]
        spec["vendor_negated"] = True
        spec["raw_negated_word"] = neg_v["raw_word"]
    else:
        if "intel" in text_l and not any(x in text_l for x in ("amd", "ryzen")):
            spec["cpu_vendor"] = "intel"
        elif any(x in text_l for x in ("amd", "ryzen")) and "intel" not in text_l:
            spec["cpu_vendor"] = "amd"
            
    neg_b = extract_brand_negation(text_l)
    if neg_b:
        spec["excluded_brand"] = neg_b["excluded_brand"]
        
    # 2. CPU Tier
    if re.search(r"\b(?:core\s+)?i7\b", text_l) or "core i7" in text_l:
        spec["cpu_tier"] = "i7"
    elif re.search(r"\b(?:core\s+)?i5\b", text_l) or "core i5" in text_l:
        spec["cpu_tier"] = "i5"
    elif re.search(r"\b(?:core\s+)?i3\b", text_l) or "core i3" in text_l:
        spec["cpu_tier"] = "i3"
    elif "ryzen 7" in text_l or "r7" in text_l:
        spec["cpu_tier"] = "ryzen 7"
    elif "ryzen 5" in text_l or "r5" in text_l:
        spec["cpu_tier"] = "ryzen 5"
    elif "n100" in text_l:
        spec["cpu_tier"] = "n100"
        
    # 3. GPU Model & Vendor
    for m in ("rtx 4070", "rtx 4060", "rtx 4050", "rtx 3050", "rtx 2050", "gtx 1660"):
        if m in text_l:
            spec["gpu_model"] = m
            break
            
    if "gpu_model" not in spec:
        if any(x in text_l for x in ("nvidia", "geforce", "rtx", "gtx")):
            spec["gpu_vendor"] = "nvidia"
        elif "radeon" in text_l:
            spec["gpu_vendor"] = "radeon"
        elif any(x in text_l for x in ("iris xe", "iris")):
            spec["gpu_model"] = "iris"
        elif "uhd" in text_l:
            spec["gpu_model"] = "uhd"

    # 3B. GPU VRAM Capacity (misal: "gpu minimal 6 gb", "vram 8 gb", "vga 6 gb", "minimal 6 gb")
    vram_m = re.search(r"\b(?:gpu|vga|vram|kartu grafis|grafis|rtx)\b.*?\b(?:minimal|min|paling sedikit|sebesar)?\s*(\d+)\s*(?:gb|giga)\b", text_l)
    if not vram_m:
        vram_m = re.search(r"\b(?:minimal|min|paling sedikit)?\s*(\d+)\s*(?:gb|giga)\b.*?\b(?:gpu|vga|vram|kartu grafis)\b", text_l)
    if not vram_m and any(w in text_l for w in ("gpu", "vga", "vram", "grafis")):
        vram_m = re.search(r"\b(?:minimal|min)\s*(\d+)\s*(?:gb|giga)\b", text_l)
    if vram_m:
        spec["gpu_vram_min"] = int(vram_m.group(1))

    # 3C. RAM Capacity (misal: "ram minimal 16 gb", "ram 16 gb", "memori 32 gb")
    ram_m = re.search(r"\b(?:ram|memori|memory)\b.*?\b(?:minimal|min|paling sedikit|sebesar)?\s*(\d+)\s*(?:gb|giga)\b", text_l)
    if not ram_m:
        ram_m = re.search(r"\b(?:minimal|min|paling sedikit)?\s*(\d+)\s*(?:gb|giga)\b.*?\b(?:ram|memori|memory)\b", text_l)
    if ram_m:
        spec["ram_min"] = int(ram_m.group(1))
            
    # 4. Display
    if "oled" in text_l:
        spec["display"] = "oled"
    elif "144" in text_l:
        spec["display"] = "144"
        
    # 5. Storage
    if "1 tb" in text_l or "1tb" in text_l:
        spec["storage"] = "1 tb"
    elif "512 gb" in text_l or "512gb" in text_l:
        spec["storage"] = "512 gb"
        
    return spec if spec else None

def product_matches_spec(p: dict, spec: dict) -> bool:
    cpu = (p.get("cpu") or "").lower()
    gpu = (p.get("gpu") or "").lower()
    display = (p.get("display") or "").lower()
    storage = (p.get("storage") or "").lower()
    
    if spec.get("cpu_vendor") == "intel" and "intel" not in cpu:
        return False
    if spec.get("cpu_vendor") == "amd" and not any(x in cpu for x in ("amd", "ryzen")):
        return False
    if spec.get("excluded_vendor") == "amd" and any(x in cpu for x in ("amd", "ryzen")):
        return False
    if spec.get("excluded_vendor") == "intel" and "intel" in cpu:
        return False
    if spec.get("excluded_brand"):
        ex_aliases = BRAND_LEXICON.get(spec["excluded_brand"], [spec["excluded_brand"]])
        if any(a in p["nama"].lower() for a in ex_aliases):
            return False
        
    if spec.get("cpu_tier") == "i7" and not any(x in cpu for x in ("i7", "core i7")):
        return False
    if spec.get("cpu_tier") == "i5" and not (any(x in cpu for x in ("i5", "core i5")) and not any(x in cpu for x in ("i7", "core i7"))):
        return False
    if spec.get("cpu_tier") == "i3" and not any(x in cpu for x in ("i3", "core i3")):
        return False
    if spec.get("cpu_tier") == "ryzen 7" and "ryzen 7" not in cpu:
        return False
    if spec.get("cpu_tier") == "ryzen 5" and "ryzen 5" not in cpu:
        return False
    if spec.get("cpu_tier") == "n100" and "n100" not in cpu:
        return False
        
    if spec.get("gpu_model") and spec["gpu_model"] not in gpu:
        return False
    if spec.get("gpu_vendor") == "nvidia" and not any(x in gpu for x in ("nvidia", "geforce", "rtx", "gtx")):
        return False
    if spec.get("gpu_vendor") == "radeon" and "radeon" not in gpu:
        return False

    if spec.get("gpu_vram_min"):
        vram_m = re.search(r"(\d+)\s*gb", gpu, re.IGNORECASE)
        vram_val = int(vram_m.group(1)) if vram_m else 0
        if vram_val < spec["gpu_vram_min"]:
            return False

    if spec.get("ram_min"):
        ram_val = p.get("ram_gb", 0)
        if ram_val < spec["ram_min"]:
            return False
        
    if spec.get("display") and spec["display"] not in display:
        return False
    if spec.get("storage") and spec["storage"] not in storage:
        return False
        
    return True

def describe_spec(spec: dict) -> str:
    parts = []
    if spec.get("cpu_tier"):
        tier_names = {
            "i7": "prosesor Intel Core i7",
            "i5": "prosesor Intel Core i5",
            "i3": "prosesor Intel Core i3",
            "ryzen 7": "prosesor AMD Ryzen 7",
            "ryzen 5": "prosesor AMD Ryzen 5",
            "n100": "prosesor Intel N100"
        }
        parts.append(tier_names.get(spec["cpu_tier"], f"prosesor {spec['cpu_tier']}"))
    elif spec.get("cpu_vendor"):
        vendor_names = {"intel": "prosesor Intel", "amd": "prosesor AMD"}
        parts.append(vendor_names.get(spec["cpu_vendor"], f"prosesor {spec['cpu_vendor']}"))
        
    if spec.get("gpu_model"):
        parts.append(f"kartu grafis {spec['gpu_model'].upper()}")
    elif spec.get("gpu_vendor"):
        gpu_names = {"nvidia": "kartu grafis NVIDIA GeForce RTX", "radeon": "kartu grafis AMD Radeon"}
        parts.append(gpu_names.get(spec["gpu_vendor"], f"grafis {spec['gpu_vendor']}"))
        
    if spec.get("gpu_vram_min"):
        parts.append(f"kartu grafis (GPU) VRAM minimal {spec['gpu_vram_min']} GB")
    if spec.get("ram_min"):
        parts.append(f"RAM minimal {spec['ram_min']} GB")
        
    if spec.get("display"):
        disp_names = {"oled": "layar OLED", "144": "layar 144Hz"}
        parts.append(disp_names.get(spec["display"], f"layar {spec['display']}"))
        
    if spec.get("storage"):
        parts.append(f"storage {spec['storage']}")
        
    return " dan ".join(parts) if parts else "spesifikasi tersebut"

def handle_spec_query(s: dict, norm_clean: str, catalog: Catalog, spec: dict) -> tuple[str, str]:
    eff_cat = extract_category(norm_clean) or s.get("category") or "laptop"
    if eff_cat not in ("laptop", "desktop"):
        eff_cat = "laptop"
    s["category"] = eff_cat
    
    brand_early = extract_brand(norm_clean)
    active_brand = brand_early or s.get("constraints", {}).get("brand")
    
    cat_pool = catalog.pool(eff_cat)
    matches = [p for p in cat_pool if product_matches_spec(p, spec)]

    # Penanganan Khusus Negasi Vendor CPU (misal: "Beliau gak mau kalo Ryzen", "Jangan AMD")
    if spec.get("vendor_negated"):
        target_person = None
        if "beliau" in norm_clean:
            target_person = s.get("persona_name") or "Beliau"
        else:
            p_name = extract_persona_name(norm_clean)
            if p_name:
                s["persona_name"] = p_name
                target_person = p_name
            elif s.get("persona_name"):
                target_person = s["persona_name"]

        # Urutkan matches berdasarkan tag kebutuhan aktif (misal architecture_cad, rendering_3d)
        needs = s.get("needs", [])
        if needs:
            matches.sort(key=lambda p: (
                -sum(1 for n in needs if has_tag(p, n)),
                p["harga_idr"]
            ))

        excluded_label = "AMD Ryzen" if spec.get("excluded_vendor") == "amd" else "Intel Core"
        target_label = "Intel Core" if spec.get("cpu_vendor") == "intel" else "AMD Ryzen"

        if target_person:
            intro_phrase = f"Baik Kak, jika {target_person} tidak menghendaki prosesor {excluded_label}"
        else:
            intro_phrase = f"Baik Kak, jika tidak menginginkan prosesor {excluded_label}"

        if needs:
            need_desc = f" yang sangat mumpuni untuk kebutuhan {need_labels(needs)}"
        else:
            need_desc = ""

        cat_lbl = CATEGORY_LABEL[eff_cat]
        intro_line = f"{intro_phrase}, kami alihkan ke pilihan {cat_lbl} bertenaga {target_label}{need_desc} di katalog Bobby Computer:"

        if matches:
            shown_matches = matches[:3]
            lines = [intro_line]
            for i, p in enumerate(shown_matches, 1):
                price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{price_str}")
            person_q = f"preferensi {target_person}" if target_person else "kebutuhan Kakak"
            lines.append(f"\nSemua pilihan di atas murni menggunakan prosesor {target_label}. Ada tipe yang sesuai dengan {person_q}, Kak?")

            s["offered_products"] = [p["kode"] for p in shown_matches]
            s["pool"] = [p["kode"] for p in matches]
            s["shown"] = list(s["offered_products"])
            s["constraints"]["vendor"] = spec.get("cpu_vendor")
            s["constraints"]["excluded_vendor"] = spec.get("excluded_vendor")
            s["fsm_stage"] = "OFFERED"
            return "\n".join(lines), "SPEC_NEGATION"
        else:
            return f"Mohon maaf Kak, untuk {cat_lbl} dengan prosesor {target_label} saat ini belum tersedia di katalog kami.", "EMPTY"
    
    if active_brand:
        brand_aliases = BRAND_LEXICON.get(active_brand, [active_brand])
        brand_matches = [p for p in matches if any(a in p["nama"].lower() for a in brand_aliases)]
        other_matches = [p for p in matches if not any(a in p["nama"].lower() for a in brand_aliases)]
        
        if brand_matches:
            lines = [f"Ada, Kak! Untuk {CATEGORY_LABEL[eff_cat]} {active_brand.title()} dengan {describe_spec(spec)}, pilihannya:"]
            for i, p in enumerate(brand_matches, 1):
                price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{price_str}")
            lines.append("Ada tipe yang menarik perhatian Kakak?")
            s["offered_products"] = [p["kode"] for p in brand_matches]
            s["pool"] = [p["kode"] for p in brand_matches]
            s["shown"] = list(s["offered_products"])
            s["fsm_stage"] = "OFFERED"
            return "\n".join(lines), "PRODUCT_Q"
        else:
            if active_brand == "asus":
                if spec.get("cpu_vendor") == "intel" and (spec.get("gpu_vendor") == "nvidia" or spec.get("gpu_model")):
                    brand_reason = (
                        "Untuk laptop ASUS di katalog Bobby Computer saat ini belum ada varian yang memadukan prosesor Intel dengan kartu grafis NVIDIA "
                        "(tipe ASUS dengan NVIDIA RTX seperti Vivobook Pro 15 OLED & TUF Gaming A15 menggunakan prosesor AMD Ryzen 7, sedangkan varian Intel memakai Intel Iris Xe)."
                    )
                else:
                    brand_reason = f"Untuk {CATEGORY_LABEL[eff_cat]} ASUS di katalog kami saat ini belum ada yang menggunakan {describe_spec(spec)}."
            elif active_brand == "acer":
                if spec.get("cpu_tier") == "i7":
                    brand_reason = "Untuk merek Acer di katalog kami saat ini belum ada yang menggunakan prosesor Intel Core i7 (Acer Nitro V 15 menggunakan prosesor Intel Core i5-13420H)."
                elif spec.get("gpu_vram_min"):
                    brand_reason = f"Untuk merek Acer di katalog kami saat ini kapasitas GPU tertingginya adalah 4 GB pada Acer Nitro V 15 (belum ada varian Acer dengan GPU {spec['gpu_vram_min']} GB ke atas)."
                else:
                    brand_reason = f"Untuk {CATEGORY_LABEL[eff_cat]} Acer di katalog kami saat ini belum ada yang menggunakan {describe_spec(spec)}."
            else:
                brand_reason = f"Untuk {CATEGORY_LABEL[eff_cat]} merek {active_brand.title()} di katalog kami saat ini belum ada yang menggunakan {describe_spec(spec)}."
                
            if other_matches:
                shown_matches = other_matches if len(other_matches) <= 4 else other_matches[:3]
                intro_text = f"di katalog Bobby Computer ada {len(other_matches)} pilihan:" if len(other_matches) <= 4 else f"di katalog Bobby Computer ada {len(other_matches)} pilihan (3 di antaranya):"
                lines = [f"{brand_reason}\n\nNamun untuk kategori {CATEGORY_LABEL[eff_cat]} dari merek lain yang memiliki {describe_spec(spec)}, {intro_text}"]
                for i, p in enumerate(shown_matches, 1):
                    price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                    lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{price_str}")
                lines.append("Ada tipe yang menarik perhatian Kakak, atau mau saya jelaskan detailnya?")
                s["offered_products"] = [p["kode"] for p in other_matches]
                s["pool"] = [p["kode"] for p in other_matches]
                s["shown"] = list(s["offered_products"])
                s["fsm_stage"] = "OFFERED"
                return "\n".join(lines), "PRODUCT_Q"
            else:
                if eff_cat == "laptop":
                    desktop_matches = [p for p in catalog.pool("desktop") if product_matches_spec(p, spec)]
                    if desktop_matches:
                        d = desktop_matches[0]
                        s["offered_products"] = [d["kode"]]
                        return (
                            f"{brand_reason}\n\n"
                            f"Namun jika Kakak terbuka untuk opsi komputer desktop (PC), kami menyediakan **{d['nama']}** "
                            f"yang dibekali {specs_line(d)} di harga {format_price(d['harga_idr'])}.\n"
                            "Apakah opsi desktop bisa dipertimbangkan, Kak?"
                        ), "PRODUCT_Q"
                return f"{brand_reason} Di katalog kami belum tersedia tipe dengan kriteria tersebut.", "EMPTY"
    else:
        if matches:
            shown_matches = matches if len(matches) <= 4 else matches[:3]
            intro_text = f"di katalog Bobby Computer ada {len(matches)} pilihan tipe:" if len(matches) <= 4 else f"di katalog Bobby Computer ada {len(matches)} pilihan tipe (3 di antaranya):"
            lines = [f"Ada, Kak! Untuk {CATEGORY_LABEL[eff_cat]} dengan {describe_spec(spec)}, {intro_text}"]
            for i, p in enumerate(shown_matches, 1):
                price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{price_str}")
            lines.append("Ada tipe yang sesuai dengan kebutuhan Kakak?")
            s["offered_products"] = [p["kode"] for p in matches]
            s["pool"] = [p["kode"] for p in matches]
            s["shown"] = list(s["offered_products"])
            s["fsm_stage"] = "OFFERED"
            return "\n".join(lines), "PRODUCT_Q"
        else:
            if eff_cat == "laptop":
                desktop_matches = [p for p in catalog.pool("desktop") if product_matches_spec(p, spec)]
                if desktop_matches:
                    d = desktop_matches[0]
                    s["offered_products"] = [d["kode"]]
                    return (
                        f"Mohon maaf Kak, untuk laptop di katalog kami belum tersedia yang menggunakan {describe_spec(spec)}.\n\n"
                        f"Namun di kategori desktop kami menyediakan **{d['nama']}** ({specs_line(d)}) di harga {format_price(d['harga_idr'])}.\n"
                        "Mau saya jelaskan spesifikasi desktop tersebut?"
                    ), "PRODUCT_Q"
            return f"Mohon maaf Kak, di katalog kami saat ini belum tersedia {CATEGORY_LABEL[eff_cat]} dengan {describe_spec(spec)}.", "EMPTY"

def resolve_refs(s: dict, norm: str, catalog: Catalog):
    codes, masked = catalog.find_named(norm)
    refs = [catalog.by_code[c] for c in codes]
    offered = s["offered_products"]
    toks = norm.split()
    
    if has_phrase(norm, "murah tadi") and offered:
        cheapest = min(offered, key=lambda c: catalog.by_code[c]["harga_idr"])
        return [catalog.by_code[cheapest]] + [r for r in refs if r["kode"] != cheapest], masked
        
    if not refs and offered:
        found_refs = []
        for word, i in (("pertama", 0), ("kedua", 1), ("ketiga", 2)):
            if word in toks and 0 <= i < len(offered):
                p = catalog.by_code[offered[i]]
                if p not in found_refs:
                    found_refs.append(p)
        matches = re.findall(r"\b(?:nomor|nomer|no|opsi|pilihan) ?(\d)\b", norm)
        for match in matches:
            i = int(match) - 1
            if 0 <= i < len(offered):
                p = catalog.by_code[offered[i]]
                if p not in found_refs:
                    found_refs.append(p)
        if found_refs:
            return found_refs, masked
            
    if not refs:
        if any(has_phrase(norm, p) for p in ("yang itu", "yang tadi", "produk itu", "laptop itu",
                                             "desktop itu", "monitor itu", "barang itu",
                                             "itu saja", "tadi")):
            if s["selected_product"]:
                return [catalog.by_code[s["selected_product"]]], masked
            if len(offered) == 1:
                return [catalog.by_code[offered[0]]], masked
    return refs, masked

def is_ambiguous_dev(norm: str, needs: list[str]) -> bool:
    toks = set(norm.split())
    if not toks & {"development", "developer", "dev"}:
        return False
    return not any(n in needs for n in ("web_dev", "android_studio", "ai_dev", "programming"))

def small_talk(s: dict, norm: str, catalog: Catalog):
    words = norm.split()
    toks = set(words)
    if is_pure_greeting(norm):
        s["last_question"] = {"slot": "greeting_followup"}
        return "Halo, Kak! Ada yang bisa saya bantu?", "DIRECT"
    if "terima kasih" in norm and set(toks) <= {"terima", "kasih", "banyak", "ya", "kak", "deh", "sih", "oke", "ok", "sip", "siap"}:
        return "Sama-sama, Kak! Kalau ada yang mau ditanyakan lagi, silakan ya.", "DIRECT"
    if re.fullmatch(BYE_RE, norm):
        reset_state(s)
        return "Sampai jumpa, Kak! Terima kasih sudah menghubungi Bobby Computer. 👋", "CANCEL"
    if norm in CANCEL_SET:
        reset_state(s)
        return "Baik Kak, dibatalkan ya. Jika ada yang ingin ditanyakan lagi, silakan hubungi saya kembali.", "CANCEL"
    if norm in CLOSING_SET:
        reset_state(s)
        return "Baik, Kak. Terima kasih banyak sudah menghubungi Bobby Computer!", "CANCEL"
    if norm in IDENTITY_SET:
        return "Saya asisten customer service Bobby Computer. Saya siap membantu merekomendasikan laptop, desktop, atau printer yang sesuai kebutuhan Kakak.", "DIRECT"
    if is_meta_critique(norm):
        return None
    clean_words = [w for w in words if w not in ("kak", "kakak", "min", "admin", "dong", "sih", "nih", "ya", "deh", "gan")]
    clean_phrase = " ".join(clean_words)
    is_store_list = (clean_phrase in LIST_SET or any(clean_phrase == p for p in (
        "ada apa saja", "jual apa saja", "ada produk apa", "jual apa aja", "ada apa aja", "punya apa saja", "punya apa aja", "jual apa", "jualan apa"
    )))
    if is_store_list and not (extract_category(norm) or extract_needs(norm) or extract_preferences(norm)["prefs"]):
        return f"Di katalog Bobby Computer tersedia: {category_counts(catalog)}. Sedang mencari yang mana, Kak?", "DIRECT"
    return None

def route_message(s: dict, raw: str, norm: str, lq: dict | None, catalog: Catalog, nlu, llm_model: str | None = None):
    # 1. Small Talk & Cancellation
    out = small_talk(s, norm, catalog)
    if out:
        return out
        
    norm_clean = strip_greeting(norm)
    toks = norm_clean.split()

    # Simpan apakah persona sudah dikenal SEBELUM turn ini (untuk guard Section 13)
    _had_persona = bool(s.get("persona"))

    # Deteksi dini: pertanyaan bundling/inklusi (harus sebelum extract_category mengubah state)
    _bundle_item = is_bundle_question(norm_clean, s)

    # Ekstraksi kategori, brand, dan persona jika disebutkan di awal (misal: "laptop deh", "buat mama sih")
    cat_t_early = extract_category(norm_clean)
    # Guard: jangan update category jika ini pertanyaan bundling (misalnya "termasuk monitor gak?")
    # — kata "monitor" muncul sebagai konteks objek bundling, bukan kategori produk yang diminta
    if (
        cat_t_early
        and cat_t_early != "computer"
        and s.get("category")
        and cat_t_early != s.get("category")
        and not _bundle_item
    ):
        # User berpindah kategori (misal: dari laptop ke printer, atau laptop ke desktop)
        prev_cat = s["category"]
        s["category"] = cat_t_early
        s["asked_slots"] = []
        s["spread_shown"] = False
        s["preferences"] = []
        s["selected_product"] = None
        s["offered_products"] = []
        s["pool"] = []
        s["shown"] = []
        s["constraints"]["budget_max"] = None
        s["constraints"]["budget_min"] = None
        s["constraints"]["budget_target"] = None
        s["constraints"]["budget_max_strict"] = False
        s["constraints"]["budget_min_strict"] = False

        # Jika beralih ke printer atau monitor: hardware CPU / vendor / OS dan workload laptop tidak relevan
        if cat_t_early in ("printer", "monitor") or prev_cat in ("printer", "monitor"):
            s["constraints"]["vendor"] = None
            s["constraints"]["os"] = None
            s["needs"] = []
            eff_brand = s["constraints"].get("brand")
            brand_aliases = BRAND_LEXICON.get(eff_brand, [eff_brand]) if eff_brand else []
            if eff_brand and not any(any(a in p["nama"].lower() for a in brand_aliases) for p in catalog.pool(cat_t_early)):
                s["constraints"]["brand"] = None
        else:
            # Beralih antara laptop dan desktop:
            # Workload needs (engineer, office, design, gaming) tetap relevan!
            eff_brand = s["constraints"].get("brand")
            if eff_brand:
                brand_aliases = BRAND_LEXICON.get(eff_brand, [eff_brand])
                if not any(any(a in p["nama"].lower() for a in brand_aliases) for p in catalog.pool(cat_t_early)):
                    s["constraints"]["brand"] = None
    elif cat_t_early and not s.get("category") and not _bundle_item:
        s["category"] = cat_t_early

    brand_early = extract_brand(norm_clean)
    if brand_early:
        s["constraints"]["brand"] = brand_early

    vendor_early, os_early = extract_vendor_os(norm_clean)
    if vendor_early:
        s["constraints"]["vendor"] = vendor_early
    if os_early:
        s["constraints"]["os"] = os_early

    pers_early = extract_persona(norm_clean)
    pers_name_early = extract_persona_name(norm_clean)
    needs_early = extract_needs(norm_clean)
    if needs_early:
        s["needs"] = list(dict.fromkeys(s.get("needs", []) + needs_early))

    budget_early = extract_budget(norm_clean)
    if budget_early and "berapa" not in toks:
        apply_budget(s, budget_early)


    # =========================================================================
    # TIER 1: JAWABAN CEPAT (Fast Deterministic Rules - 0ms)
    # =========================================================================
    # 1.1 Pertanyaan Kemampuan / Layanan CS ("Emang bisa bantu apa?", "Bisa apa aja?")
    if is_capability_inquiry(norm_clean):
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, dan monitor"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (f"Di Bobby Computer, saya siap membantu memberikan rekomendasi {cat_name} "
                "sesuai kebutuhan atau budget Kakak. Ada perangkat yang sedang dicari?"), "DIRECT"

    # 1.15 Konfirmasi atas Tawaran Produk Spesifik (confirm_product)
    if lq and lq.get("slot") == "confirm_product" and toks and toks[0] in AFFIRM_WORDS:
        p = catalog.by_code[lq["product"]]
        s["selected_product"] = p["kode"]
        s["offered_products"] = [p["kode"]]
        return render_summary(p, not s["hide_price"]), "SELECT"

    # 1.18 Permintaan Menampilkan Produk Langsung ("mana?", "mana produknya", "tunjukin dong")
    if norm_clean in ("mana", "mana?", "mana produknya", "mana barangnya", "mana pilihannya", "mana opsinya",
                      "mana rekomendasinya", "mana laptopnya", "mana pc nya", "mana komputernya",
                      "tunjukin", "tunjukkan", "tunjukin dong", "tunjukkan dong", "lihat dong", "liat dong",
                      "kasih lihat", "kasih liat"):
        if s.get("needs") or has_filter(s):
            return decide(s, catalog)
        if s.get("category"):
            return do_spread(s, catalog, "Supaya ada gambaran, ini pilihan dari yang termurah sampai tertinggi:")

    # 1.184 Pertanyaan Bundling / Inklusi Produk ("Termasuk monitor gak?", "Sudah termasuk keyboard?")
    # Ditempatkan di awal Tier 1 agar tidak tertutup oleh aturan klarifikasi kategori atau merek
    if _bundle_item:
        eff_cat = s.get("category")
        _offered = s.get("offered_products", [])
        if _bundle_item == "monitor":
            if eff_cat == "desktop" or any(
                catalog.by_code.get(c, {}).get("kategori") == "desktop" for c in _offered
            ):
                return (
                    "Untuk desktop, monitor tidak termasuk ya Kak (hanya unit PC/CPU saja). "
                    "Jadi Kakak perlu menyiapkan monitor terpisah.\n\n"
                    "Ada yang ingin ditanyakan lagi tentang spesifikasi desktopnya, atau ada kebutuhan lain?"
                ), "BUNDLE_Q"
            else:
                return (
                    "Untuk laptop, layarnya sudah terintegrasi ya Kak — jadi tidak perlu monitor tambahan "
                    "kecuali jika Kakak ingin menggunakan layar kedua (eksternal).\n\n"
                    "Ada hal lain seputar laptopnya yang ingin ditanyakan?"
                ), "BUNDLE_Q"
        elif _bundle_item in ("keyboard", "mouse"):
            if eff_cat == "desktop" or any(
                catalog.by_code.get(c, {}).get("kategori") == "desktop" for c in _offered
            ):
                return (
                    f"Untuk desktop, {_bundle_item} dijual terpisah ya Kak (tidak termasuk dalam paket unit PC). "
                    "Periferals seperti keyboard dan mouse perlu disiapkan sendiri."
                ), "BUNDLE_Q"
            else:
                return (
                    f"Untuk laptop, keyboard dan touchpad sudah built-in ya Kak, tidak perlu {_bundle_item} terpisah."
                ), "BUNDLE_Q"
        elif _bundle_item == "garansi":
            return (
                "Informasi garansi resmi toko belum tercantum di katalog kami, Kak. "
                "Bisa ditanyakan langsung ke CS toko Bobby Computer untuk detail masa garansinya ya."
            ), "BUNDLE_Q"
        else:
            if llm_model:
                chat_hist = s.get("history", [])
                offered_prods_ctx = [catalog.by_code[c] for c in _offered if c in catalog.by_code]
                if offered_prods_ctx:
                    llm_reply = query_llm_product_chat(
                        raw, s, offered_prods_ctx, chat_history=chat_hist, model=llm_model
                    )
                    if llm_reply:
                        return llm_reply, "LLM_PRODUCT_CHAT"
            return (
                f"Informasi tentang {_bundle_item} yang termasuk dalam paket belum tersedia di katalog kami, Kak. "
                "Bisa ditanyakan langsung ke toko untuk detailnya ya."
            ), "BUNDLE_Q"

    # 1.1845 Pertanyaan Konfirmasi Jenis / Kategori Produk ("Itu desktop?", "Loq itu desktop?", "Bukannya loq itu laptop?")
    cat_confirm_info = is_category_confirm_query(norm_clean, raw, s, catalog)
    if cat_confirm_info:
        target_cat, target_prods = cat_confirm_info
        return handle_category_confirm(target_cat, target_prods, s, catalog)

    # 1.185 Pertanyaan Ketersediaan Merek Produk ("Jual acer gak?", "Ada acer gak?", "Punya acer gak?")
    named_codes_early, _ = catalog.find_named(norm_clean)
    is_brand_avail = (
        brand_early is not None
        and not named_codes_early
        and any(t in AVAIL_VERBS for t in toks)
        and not extract_needs(norm_clean)
        and not extract_budget(norm_clean)
    )
    if is_brand_avail:
        brand_aliases = BRAND_LEXICON.get(brand_early, [brand_early])
        matching_prods = [p for p in catalog.products if any(a in p["nama"].lower() for a in brand_aliases)]
        if matching_prods:
            s["constraints"]["brand"] = brand_early
            matching_cats = list({p["kategori"] for p in matching_prods})
            if cat_t_early:
                s["category"] = cat_t_early
                return ask_need(s, prefix="Ada, Kak! ")
            elif s.get("category") and any(p["kategori"] == s["category"] for p in matching_prods):
                target_cat = s["category"]
                pool = [p for p in matching_prods if p["kategori"] == target_cat]
                cat_label = CATEGORY_LABEL[target_cat]
                lines = [f"Ada, Kak! Untuk {cat_label} {brand_early.title()}, di katalog Bobby Computer ada {len(pool)} pilihan tipe:"]
                for i, p in enumerate(pool, 1):
                    price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                    extra = " (Monitor tidak termasuk ya Kak)" if p["kategori"] == "desktop" else ""
                    hint = ""
                    if p.get("kategori") == "laptop":
                        gpu_lower = (p.get("gpu") or "").lower()
                        is_discrete = any(x in gpu_lower for x in ("geforce", "rtx", "gtx", "radeon rx", "arc"))
                        if is_discrete:
                            hint = " (Cocok untuk gaming & desain grafis berat)"
                        else:
                            hint = " (Cocok untuk kerja kantor, kuliah & harian)"
                    lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{extra}{price_str}{hint}")
                lines.append("Ada tipe yang menarik perhatian Kakak, atau ada kebutuhan spesifik yang ingin disesuaikan?")
                s["offered_products"] = [p["kode"] for p in pool]
                s["pool"] = [p["kode"] for p in pool]
                s["shown"] = list(s["offered_products"])
                s["fsm_stage"] = "OFFERED"
                s["last_question"] = {"slot": "need"}
                return "\n".join(lines), "INVENTORY_LIST"
            elif len(matching_cats) == 1:
                target_cat = matching_cats[0]
                s["category"] = target_cat
                pool = [p for p in matching_prods if p["kategori"] == target_cat]
                cat_label = CATEGORY_LABEL[target_cat]
                lines = [f"Ada, Kak! Untuk {cat_label} {brand_early.title()}, di katalog Bobby Computer ada {len(pool)} pilihan tipe:"]
                for i, p in enumerate(pool, 1):
                    price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                    extra = " (Monitor tidak termasuk ya Kak)" if p["kategori"] == "desktop" else ""
                    hint = ""
                    if p.get("kategori") == "laptop":
                        gpu_lower = (p.get("gpu") or "").lower()
                        is_discrete = any(x in gpu_lower for x in ("geforce", "rtx", "gtx", "radeon rx", "arc"))
                        if is_discrete:
                            hint = " (Cocok untuk gaming & desain grafis berat)"
                        else:
                            hint = " (Cocok untuk kerja kantor, kuliah & harian)"
                    lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{extra}{price_str}{hint}")
                lines.append("Ada tipe yang menarik perhatian Kakak, atau ada kebutuhan spesifik yang ingin disesuaikan?")
                s["offered_products"] = [p["kode"] for p in pool]
                s["pool"] = [p["kode"] for p in pool]
                s["shown"] = list(s["offered_products"])
                s["fsm_stage"] = "OFFERED"
                s["last_question"] = {"slot": "need"}
                return "\n".join(lines), "INVENTORY_LIST"
            else:
                cat_names = " dan ".join(CATEGORY_LABEL[c] for c in matching_cats)
                s["last_question"] = {"slot": "category"}
                return f"Ada, Kak! Untuk merek {brand_early.title()} kami menyediakan perangkat {cat_names}. Kakak sedang mencari {cat_names} {brand_early.title()}?", "ASK"
        else:
            return f"Mohon maaf Kak, untuk merek {brand_early.title()} belum tersedia di katalog Bobby Computer saat ini.", "EMPTY"

    # 1.186 Klarifikasi Kategori untuk Merek yang Sedang Dibahas ("Ya laptop maksudnya", "Laptopnya")
    # Hanya boleh jalan jika:
    # 1. Kategori baru pertama kali dipilih (s["category"] belum ada atau berbeda dengan cat_t_early)
    # 2. ATAU bot baru saja menanyakan slot kategori (s["last_question"]["slot"] == "category")
    # 3. ATAU pengguna secara eksplisit menegaskan/mengklarifikasi kategori ("ya laptop maksudnya", "maksudnya laptop")
    has_clarify_phrase = any(has_phrase(norm_clean, p) for p in (
        "maksudnya", "maksud saya", "maksud gue", "maksud aku", "kan laptop", "kan desktop", "ya laptop", "ya desktop"
    ))
    is_switching_or_first_time = (s.get("category") != cat_t_early) or (lq and lq.get("slot") == "category") or has_clarify_phrase
    if (
        cat_t_early
        and s.get("constraints", {}).get("brand")
        and is_switching_or_first_time
        and not _bundle_item
        and not is_hardware_spec_query(norm_clean)
        and not detect_attrs(norm_clean)
        and not detect_unavailable(norm_clean)
        and not extract_needs(norm_clean)
        and not extract_budget(norm_clean)
    ):
        eff_brand = s["constraints"]["brand"]
        brand_aliases = BRAND_LEXICON.get(eff_brand, [eff_brand])
        pool = [p for p in catalog.pool(cat_t_early) if any(a in p["nama"].lower() for a in brand_aliases)]
        if pool:
            s["category"] = cat_t_early
            cat_label = CATEGORY_LABEL[cat_t_early]
            lines = [f"Untuk {cat_label} {eff_brand.title()}, di katalog Bobby Computer ada {len(pool)} pilihan tipe:"]
            for i, p in enumerate(pool, 1):
                price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                extra = " (Monitor tidak termasuk ya Kak)" if p["kategori"] == "desktop" else ""
                hint = ""
                if p.get("kategori") == "laptop":
                    gpu_lower = (p.get("gpu") or "").lower()
                    is_discrete = any(x in gpu_lower for x in ("geforce", "rtx", "gtx", "radeon rx", "arc"))
                    if is_discrete:
                        hint = " (Cocok untuk gaming & desain grafis berat)"
                    else:
                        hint = " (Cocok untuk kerja kantor, kuliah & harian)"
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{extra}{price_str}{hint}")
            lines.append("Ada tipe yang menarik perhatian Kakak, atau ada kebutuhan spesifik yang ingin disesuaikan?")
            s["offered_products"] = [p["kode"] for p in pool]
            s["pool"] = [p["kode"] for p in pool]
            s["shown"] = list(s["offered_products"])
            s["fsm_stage"] = "OFFERED"
            s["last_question"] = {"slot": "need"}
            return "\n".join(lines), "INVENTORY_LIST"

    # 1.1865 Pertanyaan Ketersediaan Spesifikasi / Hardware ("Gak ada intel yang pake nvidia?", "Gak ada yang core i7?", "Ada yang pake rtx 4060?")
    spec_query_filter = extract_hardware_spec_filter(norm_clean)
    is_spec_avail = (
        spec_query_filter is not None
        and not extract_needs(norm_clean)
        and not (extract_preferences(norm_clean)["prefs"] or extract_preferences(norm_clean)["rel"])
        and (
            any(t in AVAIL_VERBS | {"gak", "tidak", "apa", "pake", "pakai", "ada", "punya", "jual", "kalo", "kalau", "tanya", "nanya"} for t in toks)
            or "?" in norm_clean
            or spec_query_filter.get("vendor_negated")
        )
    )
    if is_spec_avail:
        return handle_spec_query(s, norm_clean, catalog, spec_query_filter)

    # 1.1865 Penegasan Fokus Produk Spesifik ("Kan lagi bahas si nitro", "Kan lagi ngomongin nitro malah yang lain")
    named_codes_insist, _ = catalog.find_named(norm_clean)
    named_prods_insist = [catalog.by_code[c] for c in named_codes_insist if c in catalog.by_code]
    if not named_prods_insist and s.get("selected_product") and s["selected_product"] in catalog.by_code:
        curr_p = catalog.by_code[s["selected_product"]]
        model_words = [w for w in curr_p["nama"].lower().split() if len(w) >= 3 and w not in BRAND_LEXICON]
        if any(w in norm_clean.split() for w in model_words):
            named_prods_insist = [curr_p]

    if named_prods_insist and any(has_phrase(norm_clean, p) for p in (
        "lagi bahas", "kan bahas", "kan lagi bahas", "ngomongin", "bicarain", "tanya", "nanya", "fokus"
    )):
        p = named_prods_insist[0]
        s["selected_product"] = p["kode"]
        s["offered_products"] = [p["kode"]]
        s["pool"] = [p["kode"]]
        s["category"] = p["kategori"]
        s["fsm_stage"] = "OFFERED"
        if p.get("brand"):
            s["constraints"]["brand"] = p["brand"]
        return (
            f"Iya betul Kak, mohon maaf ya sempat teralihkan! 🙏 Mari kita kembali fokus membahas **{p['nama']}**.\n\n"
            f"Ada yang ingin Kakak tanyakan lebih lanjut tentang spesifikasi {p['nama']}, atau ada pertimbangan tertentu seputar perangkat ini?"
        ), "PRODUCT_FOCUS"

    # 1.187 Penegasan Merek ("Kan tanya acer", "Kan nanya acer", "Kan bahas asus")
    is_brand_insist = (
        not named_prods_insist
        and any(has_phrase(norm_clean, p) for p in (
            "kan tanya", "kan nanya", "aku tanya", "aku nanya", "yang ditanya",
            "kan bahas", "lagi bahas", "kan lagi bahas", "kan ngomongin", "lagi ngomongin",
            "kan bicarain", "lagi bicarain", "tadi kan asus", "tadi kan acer",
            "tadi kan lenovo", "tadi kan hp", "tentang asus", "tentang acer"
        ))
        and (brand_early or s.get("constraints", {}).get("brand"))
    )
    if is_brand_insist:
        eff_brand = brand_early or s["constraints"]["brand"]
        eff_cat = cat_t_early or s.get("category") or "laptop"
        brand_aliases = BRAND_LEXICON.get(eff_brand, [eff_brand])
        pool = [p for p in catalog.pool(eff_cat) if any(a in p["nama"].lower() for a in brand_aliases)]
        if pool:
            s["category"] = eff_cat
            s["constraints"]["brand"] = eff_brand
            lines = [f"Iya betul Kak, mohon maaf! Untuk {CATEGORY_LABEL[eff_cat]} {eff_brand.title()}, pilihannya ada:"]
            for i, p in enumerate(pool, 1):
                price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{price_str}")
            lines.append("Ada tipe yang sesuai dengan kebutuhan Kakak?")
            s["offered_products"] = [p["kode"] for p in pool]
            s["pool"] = [p["kode"] for p in pool]
            s["fsm_stage"] = "OFFERED"
            return "\n".join(lines), "INVENTORY_LIST"

    # 1.188 Keraguan Jumlah Pilihan ("Cuma 1 itu?", "Cuma itu adanya?", "Itu doang?")
    _activity_toks = {"nonton", "streaming", "game", "gaming", "main", "kerja", "kantor", "ngetik", "browsing", "kuliah", "sekolah", "belajar", "desain"}
    _is_activity_or_negation = bool(set(toks) & _activity_toks) or any(w in norm_clean for w in ("tidak", "bukan", "gak", "nggak")) or bool(is_size_or_weight_objection(norm_clean))
    is_only_one_q = (
        not _is_activity_or_negation
        and (
            any(has_phrase(norm_clean, p) for p in (
                "cuma 1 itu", "cuma satu itu", "cuma 1", "cuma satu", "cuma itu",
                "cuma itu adanya", "cuma ada itu", "cuma ada 1", "cuma ada satu",
                "cuma itu aja", "cuma itu saja", "hanya itu", "hanya 1", "hanya satu",
                "apa cuma itu", "apa cuma 1", "itu doang", "itu doang adanya",
                "itu aja", "itu saja", "segitu doang", "cuma segitu",
                "lah itu doang", "cuma itu doang", "hanya itu doang"
            ))
            or bool(re.search(r"\b(?:itu|segitu)\s+(?:doang|aja|saja)\b", norm_clean))
            or bool(re.search(r"\b(?:cuma|hanya)\s+(?:ada\s+)?(?:satu|1|tipe|seri|opsi|pilihan|barang|ini|itu)\s+(?:saja|aja|doang)\b", norm_clean))
        )
        and not any(w in norm_clean for w in ("tinggi", "murah", "mahal", "spek"))
    )

    if is_only_one_q:
        eff_brand = brand_early or (s.get("constraints") and s["constraints"].get("brand"))
        eff_cat = cat_t_early or s.get("category") or "laptop"
        active_codes = s.get("offered_products") or ([s["selected_product"]] if s.get("selected_product") else [])
        if len(active_codes) == 1 and active_codes[0] in catalog.by_code:
            active_p = catalog.by_code[active_codes[0]]
            is_mini = "mini" in active_p["nama"].lower() or "mini" in norm_clean
            if is_mini:
                return (
                    f"Betul Kak, untuk varian PC mini di katalog Bobby Computer saat ini baru tersedia 1 tipe tersebut yaitu **{active_p['nama']}** ({format_price(active_p['harga_idr'])}).\n\n"
                    f"Namun jika Kakak mencari PC desktop ukuran standar (tower) dengan spesifikasi yang lebih tinggi atau kartu grafis (GPU) terpisah, kami punya pilihan lain seperti **ASUS ExpertCenter D500** atau **Lenovo LOQ Tower 17**.\n"
                    f"Mau melihat pilihan desktop lainnya, Kak?"
                ), "DIRECT"
        if eff_brand:
            brand_aliases = BRAND_LEXICON.get(eff_brand, [eff_brand])
            brand_prods = [p for p in catalog.products if any(a in p["nama"].lower() for a in brand_aliases)]
            cat_prods = [p for p in brand_prods if p["kategori"] == eff_cat]
            if len(cat_prods) > 1:
                if s.get("last_route") == "INVENTORY_LIST" and any(c in s.get("offered_products", []) for c in [p["kode"] for p in cat_prods]):
                    prod_names = " dan ".join(f"**{p['nama']}** ({format_price(p['harga_idr'])})" for p in cat_prods)
                    return (
                        f"Iya Kak, betul. Untuk merek {eff_brand.title()} di katalog Bobby Computer saat ini baru tersedia {len(cat_prods)} tipe tersebut: {prod_names}.\n\n"
                        f"Namun jika Kakak terbuka untuk pilihan merek lain seperti ASUS, Lenovo, atau HP dengan rentang harga dan spesifikasi serupa, saya siap bantu carikan. Mau melihat alternatif merek lain, Kak?"
                    ), "ALTERNATIVE_SUGGEST"
                lines = [f"Tentu tidak cuma satu Kak! Di katalog kami untuk {CATEGORY_LABEL[eff_cat]} {eff_brand.title()} ada {len(cat_prods)} pilihan tipe:"]
                for i, p in enumerate(cat_prods, 1):
                    price_str = f" (Harga {format_price(p['harga_idr'])})"
                    lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}{price_str}")
                lines.append("Ada kebutuhan atau budget spesifik yang ingin disesuaikan Kak?")
                s["offered_products"] = [p["kode"] for p in cat_prods]
                s["pool"] = [p["kode"] for p in cat_prods]
                s["fsm_stage"] = "OFFERED"
                return "\n".join(lines), "INVENTORY_LIST"
            else:
                return (f"Betul Kak, untuk {CATEGORY_LABEL[eff_cat]} merek {eff_brand.title()} di katalog kami saat ini baru ada tipe tersebut. "
                        f"Namun kami juga punya pilihan dari merek lain seperti ASUS, Lenovo, dan HP jika Kakak ingin melihat alternatifnya."), "DIRECT"
        else:
            cat_pool = catalog.pool(eff_cat)
            return (f"Di katalog kami tersedia {len(cat_pool)} pilihan {CATEGORY_LABEL[eff_cat]} dari berbagai merek. "
                    "Mau saya tunjukkan pilihan yang sesuai budget atau kebutuhan tertentu, Kak?"), "DIRECT"

    # 1.19 Pertanyaan Tipe / Model / Inventaris Produk ("Ada tipe apa?", "Tipe apa aja?", "Ada seri apa?")
    if is_type_or_inventory_query(norm_clean) and not extract_hardware_spec_filter(norm_clean):
        eff_cat = cat_t_early or s.get("category")
        eff_brand = brand_early or (s.get("constraints") and s["constraints"].get("brand"))
        
        # Jika belum ada kategori tapi ada brand (misal user nanya printer epson atau laptop asus)
        if not eff_cat and eff_brand:
            matching_cats = {p["kategori"] for p in catalog.products if eff_brand in p["nama"].lower()}
            if len(matching_cats) == 1:
                eff_cat = list(matching_cats)[0]
                s["category"] = eff_cat

        if eff_cat:
            pool = catalog.pool(eff_cat)
            if eff_brand:
                brand_aliases = BRAND_LEXICON.get(eff_brand, [eff_brand])
                pool = [p for p in pool if any(a in p["nama"].lower() for a in brand_aliases)]
            
            if pool:
                brand_label = f" {eff_brand.title()}" if eff_brand else ""
                cat_label = CATEGORY_LABEL[eff_cat]
                lines = [f"Untuk {cat_label}{brand_label}, di katalog Bobby Computer ada {len(pool)} pilihan tipe:"]
                for i, p in enumerate(pool, 1):
                    price_str = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                    extra = " (Monitor tidak termasuk ya Kak)" if p["kategori"] == "desktop" else ""
                    hint = ""
                    if p.get("kategori") == "laptop":
                        gpu_lower = (p.get("gpu") or "").lower()
                        is_discrete = any(x in gpu_lower for x in ("geforce", "rtx", "gtx", "radeon rx", "arc"))
                        if is_discrete:
                            if any(x in gpu_lower for x in ("rtx 4060", "rtx 4070", "rtx 4080", "rtx 4090")):
                                hint = " (Cocok untuk gaming berat & 3D rendering)"
                            else:
                                hint = " (Cocok untuk desain grafis, editing & multimedia)"
                        else:
                            hint = " (Cocok untuk kerja kantor, kuliah & harian)"
                    lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{extra}{price_str}{hint}")
                lines.append("Ada tipe yang menarik perhatian Kakak, atau ada kebutuhan spesifik yang ingin disesuaikan?")
                s["offered_products"] = [p["kode"] for p in pool]
                s["pool"] = [p["kode"] for p in pool]
                s["shown"] = list(s["offered_products"])
                s["fsm_stage"] = "OFFERED"
                s["last_question"] = {"slot": "need"}
                return "\n".join(lines), "INVENTORY_LIST"
            else:
                brand_label = f" brand {eff_brand.title()}" if eff_brand else ""
                return f"Mohon maaf Kak, untuk {CATEGORY_LABEL[eff_cat]}{brand_label} belum tersedia tipe lain di katalog kami.", "EMPTY"
        else:
            return f"Di katalog Bobby Computer tersedia: {category_counts(catalog)}. Mau melihat tipe untuk kategori yang mana, Kak?", "DIRECT"

    # 1.2 Afirmasi atas Tawaran Salam CS ("Ada yang bisa saya bantu? -> Ada / Mau tanya / Bisa / Butuh bantuan")
    is_affirm_greeting = (
        (lq and lq.get("slot") == "greeting_followup" and (
            (toks and toks[0] in AFFIRM_WORDS | {"ada", "bisa", "butuh"}) or
            any(has_phrase(norm_clean, p) for p in ("mau tanya", "mau nanya", "mau cari", "mau beli", "butuh bantuan"))
        )) or (
            not s.get("history") and toks and set(toks) <= AFFIRM_WORDS | {"ada", "bisa", "butuh", "kak", "dong", "min", "deh", "gan", "bantuan"}
        ) or (
            not s.get("history") and any(has_phrase(norm_clean, p) for p in ("mau tanya", "mau nanya", "mau cari", "butuh bantuan"))
        )
    )
    if is_affirm_greeting and not (extract_needs(norm_clean) or extract_category(norm_clean) or extract_budget(norm_clean)):
        # Jika riwayat percakapan sebelumnya memuat konfirmasi kebutuhan/produk (misal: "Laptop Acer untuk ngegame, ya?")
        hist = s.get("history", [])
        if hist:
            last_bot_msg = hist[-1][1] if hist[-1][0] == "assistant" else ""
            last_needs = extract_needs(normalize(last_bot_msg))
            if last_needs and not s.get("needs"):
                s["needs"] = last_needs
                return decide(s, catalog)
        # Jika konteks sudah ada (tahu kebutuhan/kategori/produk/brand) → lanjut decide, jangan tanya lagi
        if s.get("needs") or s.get("offered_products") or (s.get("constraints") and s["constraints"].get("brand")):
            return decide(s, catalog)
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        return (f"Boleh, Kak! Sedang mencari {cat_name}, dan rencananya untuk kebutuhan apa?", "ASK")

    # 1.3 Candaan / Banter Sosial ("Cari kamu", "Mau kamu", "Cari jodoh")
    if is_banter(norm_clean) and not (extract_category(norm_clean) or extract_needs(norm_clean)):
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return ("Hehe, kalau saya selalu siap melayani di sini, Kak! "
                f"Tapi saya asisten virtual khusus penjualan {cat_name} nih. "
                "Ada perangkat komputer yang sedang Kakak cari?"), "DIRECT"

    # 1.4 Tanggapan atas Frustrasi / Makian Pengguna ("CS bego", "ngeselin")
    if is_insult(norm_clean):
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return ("Waduh, maaf banget ya Kak kalau respons saya sebelumnya bikin kesal atau kurang memuaskan. 🙏 "
                f"Saya siap bantu carikan {cat_name} yang pas jika Kakak berkenan. "
                "Ada kebutuhan perangkat tertentu yang sedang dicari?"), "META_ALIGN"

    # 1.5 Tanggapan atas Keraguan Katalog ("kamu pasti gak liat katalog")
    if is_catalog_doubt(norm_clean):
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, dan monitor"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (f"Katalog Bobby Computer sudah saya pelajari dengan baik kok, Kak. Kami menyediakan {cat_name}. "
                "Boleh diceritakan perangkat dan kebutuhan apa yang sedang Kakak cari?"), "META_ALIGN"

    # 1.6 Penjelasan Meta Alur ("Lah tadi kan nanya ada yang bisa saya bantu. Aku jawab ada", "Lah kan sudah dibilang")
    if is_meta_explanation(norm_clean):
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        if s.get("needs"):
            p_label = f" untuk {s['persona_name']}" if s.get("persona_name") else ""
            return (f"Hehe, iya Kak, mohon maaf saya sempat terlewat! 🙏 "
                    f"Tadi kita sudah bahas {cat_name}{p_label} untuk kebutuhan {need_labels(s['needs'])}. "
                    f"Ada bagian spesifikasi yang ingin ditanyakan lagi, atau mau saya berikan rekomendasi lainnya?"), "META_ALIGN"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (f"Hehe, iya Kak, mohon maaf tadi sempat salah paham! 🙏 "
                f"Maksud saya, Kakak sedang mencari {cat_name} untuk kebutuhan apa nih?"), "META_ALIGN"

    # 2. Meta-Critique Handling (Penanganan Protes/Keluhan Pengguna atas Alur CS)
    if is_meta_critique(norm_clean):
        # Jika komplain 'ditanya jual apa malah disuruh cerita' / 'malah disuruh cerita' / 'malah nanya balik'
        if any(has_phrase(norm_clean, p) for p in ("jual apa", "disuruh cerita", "suruh cerita", "malah cerita", "malah nanya", "malah tanya")):
            return (f"Aduh, mohon maaf banget ya Kak! 🙏 "
                    f"Di Bobby Computer kami menyediakan: {category_counts(catalog)}. "
                    "Kakak sedang mencari yang mana nih?"), "META_ALIGN"

        # Jika pengguna menanyakan 'Emang kamu tahu aku butuh yang gimana?' atau 'Tahu dari mana?'
        if re.search(r"\b(?:emang|memang)\b.*\b(?:tahu|tau)\b.*\b(?:butuh|mau|gimana|apa)\b", norm_clean) or \
           re.search(r"\b(?:tahu|tau)\b.*\bdari mana\b", norm_clean):
            cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
            s["last_question"] = {"slot": "need"}
            s["fsm_stage"] = "AWAITING_NEED"
            return (f"Belum tahu persis Kak, makanya tadi saya tanyakan dan baru memberikan pilihan umum sebagai referensi awal. 😊 "
                    f"Biar bisa saya sesuaikan dengan tepat, boleh diceritakan {cat_name}nya rencana dipakai untuk apa saja Kak?"), "META_ALIGN"

        # Jika CS sebelumnya baru saja menawarkan produk atau menampilkan sebaran
        if s.get("last_route") in ("OFFER", "SPREAD") or (s.get("last_route") == "META_ALIGN" and s.get("offered_products")):
            if s.get("persona"):
                p_label = "Papa" if s["persona"] == "family_elder" else "keluarga"
                s["last_question"] = {"slot": "need"}
                s["fsm_stage"] = "PERSONA_CLARIFY"
                return (f"Hehe, iya maaf ya Kak kalau saya terburu-buru memberikan pilihan! 🙏 "
                        f"Maksud saya, untuk laptop {p_label} tadi kira-kira lebih sering dipakai untuk "
                        f"ngetik dokumen/santai, atau ada kebutuhan khusus lainnya Kak?"), "META_ALIGN"
            if s.get("category"):
                cat_name = CATEGORY_LABEL[s["category"]]
            elif s.get("offered_products"):
                off_cats = {catalog.by_code[c]["kategori"] for c in s["offered_products"] if c in catalog.by_code}
                if off_cats == {"desktop"}:
                    cat_name = "desktop"
                elif off_cats == {"laptop"}:
                    cat_name = "laptop"
                elif off_cats == {"monitor"}:
                    cat_name = "monitor"
                else:
                    cat_name = "komputer"
            else:
                cat_name = "laptop, desktop, atau monitor"
            return (f"Hehe, iya maaf ya Kak kalau saya terburu-buru memberikan pilihan! 🙏 "
                    f"Justru karena saya belum tahu kebutuhan persisnya, saya berikan gambaran pilihan tadi supaya ada referensi. "
                    f"Biar bisa saya pilihkan yang benar-benar pas, biasanya {cat_name}nya bakal dipakai untuk apa saja Kak?"), "META_ALIGN"
        
        # Jika CS sebelumnya belum menawarkan produk (salam, tanya kebutuhan, atau salah paham)
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        return (f"Hehe, iya maaf ya Kak atas salah pahamnya atau kalau saya kurang tanggap. 🙏 "
                f"Saya siap membantu jika Kakak sedang mencari {cat_name}. "
                f"Ada kebutuhan perangkat komputer yang bisa saya bantu?"), "META_ALIGN"

    # 2B. Komplain Mengenai Belum Tahu Harga / Syarat Pembelian ("Kalo gak tahu harga ya gak beli")
    is_price_condition = bool(
        re.search(r"\b(?:kalau|kalo|gimana|bagaimana)\b.*\b(?:tidak|belum|gak|nggak)\b.*\b(?:tahu|tau)\b.*\bharga\b", norm_clean) or
        re.search(r"\bharga\b.*\b(?:tidak|belum|gak|nggak)\b.*\b(?:tahu|tau)\b.*\b(?:tidak|belum|gak|nggak)\b.*\bbeli\b", norm_clean) or
        re.search(r"\b(?:tidak|gak|nggak)\b.*\b(?:tahu|tau)\b.*\bharga\b.*\b(?:tidak|belum|gak|nggak)\b.*\bbeli\b", norm_clean)
    )
    if is_price_condition:
        cat_t_temp = extract_category(norm_clean)
        effective_cat = cat_t_temp or s.get("category")
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        if effective_cat:
            pool = catalog.pool(effective_cat)
            lo, hi = min(p["harga_idr"] for p in pool), max(p["harga_idr"] for p in pool)
            lo_prod = min(pool, key=lambda p: p["harga_idr"])["nama"]
            hi_prod = max(pool, key=lambda p: p["harga_idr"])["nama"]
            return (f"Hehe, iya betul banget Kak, tentu harus tahu harganya dulu! 🙏 "
                    f"Di katalog kami, harga {CATEGORY_LABEL[effective_cat]} mulai dari {format_price(lo)} ({lo_prod}) "
                    f"sampai {format_price(hi)} ({hi_prod}). "
                    f"Ada patokan budget tertentu atau kebutuhan {CATEGORY_LABEL[effective_cat]} yang sedang dicari, Kak?"), "PRODUCT_Q"
        else:
            return ("Hehe, iya betul banget Kak, tentu harus tahu harganya dulu! 🙏 "
                    "Di katalog Bobby Computer, harga laptop mulai dari Rp7.999.000 sampai Rp15.999.000, "
                    "desktop mulai dari Rp6.499.000 sampai Rp18.999.000, dan monitor mulai dari Rp1.599.000 sampai Rp2.899.000. "
                    "Ada patokan budget atau perangkat tertentu yang sedang Kakak cari?"), "PRODUCT_Q"

    # 2C. Sanggahan Retoris atas Asumsi Pembelian ("Yang beli siapa?", "Siapa yang mau beli?")
    is_rhetorical_buyer = bool(
        re.search(r"\b(?:siapa|sapa)\b.*\b(?:beli|pesan|checkout|order)\b", norm_clean) or
        re.search(r"\b(?:beli|pesan|checkout|order)\b.*\b(?:siapa|sapa)\b", norm_clean) or
        re.search(r"\b(?:belum|gak|nggak|tidak)\b.*\b(?:ada|mau)\b.*\b(?:yang\s+)?(?:beli|pesan)\b", norm_clean)
    )
    if is_rhetorical_buyer:
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (f"Hehe, iya maaf ya Kak kalau saya salah tangkap maksudnya! 🙏 "
                f"Tentu tidak harus beli sekarang kok, saya siap membantu kalau Kakak butuh info spesifikasi, rekomendasi, atau perbandingan {cat_name} terlebih dahulu. "
                "Ada yang mau ditanyakan seputar perangkatnya?"), "META_ALIGN"

    # 2D. Sanggahan atas Klaim Spesifikasi Tertinggi ("Paling tinggi??", "Paling tingginya cuma segitu?")
    is_max_doubt = any(has_phrase(norm_clean, p) for p in (
        "cuma segitu", "cuma segini", "masa paling tinggi", "masa segitu",
        "kok cuma segitu", "kok cuma segini", "segitu paling tingginya"
    )) or norm_clean in ("paling tinggi", "paling tinggi?", "paling tinggi??", "paing tinggi", "paing tinggi??", "paling tingginya", "paing tingginya", "paling tingginya cuma segitu?")
    if is_max_doubt and not extract_needs(norm_clean):
        cat = s.get("category") or "laptop"
        top_l = max(catalog.pool("laptop"), key=lambda p: p["harga_idr"]) if catalog.pool("laptop") else None
        top_d = max(catalog.pool("desktop"), key=lambda p: p["harga_idr"]) if catalog.pool("desktop") else None
        if cat == "laptop" and top_l and top_d:
            top_p = top_l
            d_top = top_d
            target_person = s.get("persona_name") or "Om"
            if top_p["kode"] in s.get("offered_products", []):
                return (
                    f"Untuk kategori laptop, betul Kak, **{top_p['nama']}** ({format_price(top_p['harga_idr'])}) "
                    f"sudah merupakan pilihan spesifikasi tertinggi di katalog kami dengan prosesor {top_p['cpu']} dan GPU {top_p['gpu']}.\n\n"
                    f"Namun jika {target_person} membutuhkan performa komputasi yang jauh lebih bertenaga lagi untuk kebutuhan teknik berat, "
                    f"kami juga menyediakan komputer desktop workstation **{d_top['nama']}** di harga {format_price(d_top['harga_idr'])} "
                    f"({d_top['cpu']}, RAM {d_top['ram_gb']} GB {d_top.get('ram_type', 'DDR5')}, SSD {d_top['storage']}, GPU {d_top['gpu']}).\n"
                    f"Apakah {target_person} terbuka untuk opsi komputer desktop (PC)?",
                    "MAX_SPEC_CLARIFY"
                )
            s["offered_products"] = [top_p["kode"]]
            s["selected_product"] = top_p["kode"]
            return (
                f"Tentu tidak Kak! Maksud saya tadi adalah pilihan paling tinggi untuk kategori penggunaan kantor standar. "
                f"Di katalog Bobby Computer, kasta spesifikasi tertinggi laptop adalah **{top_p['nama']}** di harga {format_price(top_p['harga_idr'])}. "
                f"Spesifikasinya memakai prosesor {top_p['cpu']}, GPU {top_p['gpu']}, RAM {top_p['ram_gb']} GB {top_p.get('ram_type', 'DDR5')}, "
                f"storage {top_p['storage']}, dan layar {top_p['display']}.\n\n"
                f"Laptop ini bertenaga sangat tinggi untuk 3D rendering, desain kompleks, gaming berat, maupun AI development. "
                "Mau saya jelaskan lebih detail spesifikasinya?",
                "MAX_SPEC_CLARIFY"
            )
        elif cat == "desktop" and top_d:
            top_p = top_d
            s["offered_products"] = [top_p["kode"]]
            s["selected_product"] = top_p["kode"]
            return (
                f"Tentu tidak Kak! Maksud saya tadi adalah pilihan tertinggi untuk penggunaan kantor standar. "
                f"Untuk kasta spesifikasi tertinggi desktop di katalog kami adalah **{top_p['nama']}** di harga {format_price(top_p['harga_idr'])}. "
                f"Spesifikasinya memakai prosesor {top_p['cpu']}, GPU {top_p['gpu']}, RAM {top_p['ram_gb']} GB {top_p.get('ram_type', 'DDR5')}, "
                f"dan storage {top_p['storage']}.\n\n"
                f"Sangat bertenaga untuk rendering 3D, video editing berat, dan AI development. "
                "Mau saya jelaskan lebih detail?",
                "MAX_SPEC_CLARIFY"
            )
        elif top_l and top_d:
            return (
                f"Tentu tidak Kak! Pilihan spesifikasi tertinggi di Bobby Computer ada **{top_l['nama']}** untuk laptop ({format_price(top_l['harga_idr'])}) "
                f"dan **{top_d['nama']}** untuk desktop ({format_price(top_d['harga_idr'])}) dengan GPU NVIDIA RTX bertenaga tinggi. "
                "Ada yang ingin Kakak tanyakan seputar kedua perangkat tersebut?",
                "MAX_SPEC_CLARIFY"
            )

    # 2E. Panduan & Edukasi Peran GPU dalam Pertimbangan Penggunaan
    is_gpu_guidance = (
        ("gpu" in norm_clean or "vga" in norm_clean) and
        any(has_phrase(norm_clean, p) for p in GPU_EXPLANATION_PHRASES)
    ) or any(has_phrase(norm_clean, p) for p in (
        "penggunaan gpu juga jadi pertimbangan", "penggunaan gpu jadi pertimbangan",
        "gpu juga jadi pertimbangan", "vga juga jadi pertimbangan"
    ))
    if is_gpu_guidance and not extract_needs(norm_clean):
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (
            "Betul sekali, Kak! Di Bobby Computer, jenis GPU merupakan pertimbangan utama dalam menentukan kecocokan perangkat:\n"
            "- **GPU Dedicated (NVIDIA RTX series)**: Wajib dipertimbangkan untuk kebutuhan rendering 3D, arsitektur/CAD, simulasi teknik, AI development, video editing berat, dan gaming AAA.\n"
            "- **GPU Integrated (Intel UHD / Iris Xe / AMD Radeon)**: Sangat ideal untuk kebutuhan kerja kantor/office, perkuliahan, administrasi kasir, dan harian karena hemat baterai dan suhu lebih dingin.\n\n"
            "Apakah Kakak sedang mencari perangkat untuk komputasi grafis berat (GPU dedicated) atau mobilitas harian (GPU hemat daya)?",
            "GPU_GUIDANCE"
        )

    # 4. Koreksi ("Aku tanya laptop, bukan harga") (§13)
    if is_correction(norm_clean):
        s["hide_price"] = True
        if s["offered_products"]:
            prods = [catalog.by_code[c] for c in s["offered_products"]]
            lines = ["Baik Kak, mohon maaf. Ini penjelasan spesifikasi produknya:"]
            lines += render_product_lines(prods, s["needs"], False)
            return "\n".join(lines), "CORRECTION"
        if s["needs"] or has_filter(s) or has_rank(s):
            reply, _ = do_offer(s, catalog, "Mohon maaf, Kak. ")
            return reply, "CORRECTION"
        return ask_need(s, "Mohon maaf, Kak. ")[0], "CORRECTION"

    # 1.13 Category Guard untuk perangkat di luar katalog toko
    # PENTING: Jangan tembak CATEGORY_GUARD jika user sedang aktif membahas produk yang sudah ditawarkan
    # — dalam konteks tersebut, pertanyaan ambigu harus ke LLM, bukan CATEGORY_GUARD
    named_codes, _ = catalog.find_named(norm_clean)
    if not named_codes:
        cat_req = extract_category(norm_clean)
        if cat_req and not catalog.pool(cat_req):
            # Bahkan untuk kategori di luar katalog, jika ada offered_products, coba LLM dulu
            if s.get("offered_products") and llm_model:
                _off_prods = [catalog.by_code[c] for c in s["offered_products"] if c in catalog.by_code]
                if _off_prods:
                    _llm_r = query_llm_product_chat(raw, s, _off_prods, chat_history=s.get("history", []), model=llm_model)
                    if _llm_r:
                        return _llm_r, "LLM_PRODUCT_CHAT"
            return (f"Maaf, Kak, di katalog kami saat ini hanya ada {all_category_str(catalog, 'dan')}."), "CATEGORY_GUARD"
        cat_guard = detect_category_guard(norm_clean)
        if cat_guard:
            # PENTING: Jika ada offered_products, coba LLM_PRODUCT_CHAT sebelum tembak CATEGORY_GUARD
            if s.get("offered_products") and llm_model:
                _off_prods = [catalog.by_code[c] for c in s["offered_products"] if c in catalog.by_code]
                if _off_prods:
                    _llm_r = query_llm_product_chat(raw, s, _off_prods, chat_history=s.get("history", []), model=llm_model)
                    if _llm_r:
                        return _llm_r, "LLM_PRODUCT_CHAT"
            # Jika ada brand aktif dalam konteks tapi pertanyaan tidak ke luar katalog,
            # mungkin user bertanya tentang varian brand tsb — serahkan ke spec query
            active_brand = s.get("constraints", {}).get("brand")
            if active_brand and any(t in AVAIL_VERBS | {"gak", "tidak", "apa", "ada"} for t in toks):
                spec_filter = extract_hardware_spec_filter(norm_clean)
                if spec_filter:
                    return handle_spec_query(s, norm_clean, catalog, spec_filter)
            return (f"Maaf, Kak, di katalog kami saat ini hanya ada {all_category_str(catalog, 'dan')}."), "CATEGORY_GUARD"

    # Evaluasi apakah pesan masuk tahap spesifikasi teknis / pilihan komputer / RAG
    named_codes, _ = catalog.find_named(norm_clean)
    has_concrete_rag_criteria = bool(
        s.get("offered_products")
        or s.get("selected_product")
        or named_codes
        or extract_hardware_spec_filter(norm_clean)
        or is_type_or_inventory_query(norm_clean)
        or is_choice_or_recommendation_query(norm_clean)
        or extract_needs(norm_clean)
        or s.get("needs")
        or extract_budget(norm_clean)
        or extract_preferences(norm_clean)["prefs"]
        or extract_preferences(norm_clean)["rel"]
        or is_spec_objection(norm_clean)
        or bool(is_size_or_weight_objection(norm_clean))
        or is_recommendation_request(norm_clean)
        or bool(is_need_insist(norm_clean))
        or extract_persona(norm_clean)
        or extract_persona_name(norm_clean)
        or is_persona_insist(norm_clean)
        or is_need_negation(norm_clean)
        or detect_unavailable(norm_clean)
        or extract_category(norm_clean)
        or extract_brand(norm_clean)
        or _bundle_item
        or is_category_confirm_query(norm_clean, raw, s, catalog)
    )

    # =========================================================================
    # OBROLAN AWAL: Ditangani LLM jika model aktif (user request)
    # Kecuali sekadar salam (sudah ditangani di Tier 1 / small_talk)
    # =========================================================================
    if (
        llm_model
        and not has_concrete_rag_criteria
        and not s.get("offered_products")
        and not s.get("selected_product")
        and s.get("fsm_stage") in ("INIT", "AWAITING_NEED")
    ):
        chat_hist = s.get("history", [])
        llm_reply = query_llm_opening(raw, s, chat_history=chat_hist, model=llm_model)
        if llm_reply:
            s["last_question"] = {"slot": "need"}
            s["fsm_stage"] = "AWAITING_NEED"
            return llm_reply, "LLM_OPENING"

    is_rag = (
        is_spec_or_rag_query(norm_clean, s)
        or bool(named_codes)
        or bool(s.get("offered_products"))
        or bool(s.get("selected_product"))
        or is_spec_objection(norm_clean)
        or bool(is_size_or_weight_objection(norm_clean))
        or is_recommendation_request(norm_clean)
        or bool(is_need_insist(norm_clean))
        or bool(extract_persona(norm_clean))
        or bool(extract_persona_name(norm_clean))
        or bool(is_persona_insist(norm_clean))
        or bool(is_need_negation(norm_clean))
        or bool(detect_unavailable(norm_clean))
        or is_choice_or_recommendation_query(norm_clean)
        or bool(extract_hardware_spec_filter(norm_clean))
        or bool(extract_category(norm_clean))
        or bool(extract_brand(norm_clean))
        or bool(extract_needs(norm_clean))
        or bool(_bundle_item)
        or bool(is_category_confirm_query(norm_clean, raw, s, catalog))
    )

    # =========================================================================
    # TIER 3: LLM KECIL / Deterministik Fallback untuk Obrolan Awal
    # =========================================================================
    if not is_rag:
        if (
            llm_model
            and s.get("fsm_stage") in ("INIT", "AWAITING_NEED")
            and not s.get("selected_product")
            and not s.get("offered_products")
        ):
            chat_hist = s.get("history", [])
            llm_reply = query_llm_opening(raw, s, chat_history=chat_hist, model=llm_model)
            if llm_reply:
                s["last_question"] = {"slot": "need"}
                s["fsm_stage"] = "AWAITING_NEED"
                return llm_reply, "LLM_OPENING"
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"

        # Anti-Loop: Jika bot sudah menanyakan kebutuhan di turn sebelumnya (lq == slot:need),
        # jangan mengulang pertanyaan yang sama seperti kaset rusak.
        # Berikan baseline rekomendasi santai/harian yang terjangkau!
        if lq and isinstance(lq, dict) and lq.get("slot") == "need" and s.get("category"):
            s["needs"] = ["daily"]
            reply, _ = do_offer(s, catalog, f"Baik Kak, jika untuk kebutuhan santai di rumah, berikut beberapa pilihan {cat_name} terfavorit di Bobby Computer:\n")
            return reply, "OFFER"

        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (f"Boleh diceritakan Kak, sedang mencari {cat_name} untuk kebutuhan apa?", "ASK")

    # =========================================================================
    # TIER 2: RAG & KATALOG KOMPUTER (Qdrant & Mesin Rekomendasi Deterministik)
    # =========================================================================
    # 5. Resolusi Referensi (§11.1)
    refs, mnorm = resolve_refs(s, norm_clean, catalog)
    mtoks = mnorm.split()
    attrs = detect_attrs(mnorm)
    budget = extract_budget(mnorm)
    is_q = "?" in raw or bool(set(mtoks) & {"berapa", "apa", "apakah", "bagaimana", "gimana", "mana"})

    # 6. Batasan Katalog & Atribut Tidak Tersedia (§18, §19)
    ua = detect_unavailable(mnorm)
    if ua:
        pname = f" {refs[0]['nama']}" if len(refs) == 1 else ""
        parts = []
        for label in ua:
            if label == "stok":
                parts.append(f"Maaf, Kak, informasi stok{pname} belum tersedia di katalog.")
            elif label == "baterai":
                parts.append(f"Maaf, informasi kapasitas baterai{pname} belum tersedia di katalog.")
            elif label == "operasional toko":
                parts.append("Toko Bobby Computer saat ini melayani konsultasi dan pemesanan secara online di sini, Kak. Untuk info lokasi fisik dan alamat lengkap toko, bisa ditanyakan langsung ke kontak admin kami. Ada perangkat komputer yang sedang dicari?")
            else:
                parts.append(f"Maaf, informasi {label}{pname} belum tersedia di katalog.")
        return " ".join(parts), "UNAVAILABLE"

    needs_t = extract_needs(mnorm)
    cat_t = extract_category(mnorm)
    pref_info = extract_preferences(mnorm)
    vendor, os_ = extract_vendor_os(mnorm)
    brand_t = extract_brand(mnorm)
    persona_t = extract_persona(mnorm)
    budget_stmt = budget is not None and "berapa" not in mtoks
    pref_or_constraint = bool(budget_stmt or pref_info["prefs"] or pref_info["rel"] or vendor or os_ or brand_t)

    # 7. Komparasi (§12)
    cmp_words = bool(set(mtoks) & COMPARE_WORDS) or any(has_phrase(mnorm, p) for p in COMPARE_PHRASES)
    offered_prods = [catalog.by_code[c] for c in s["offered_products"]]

    # Cek apakah ini permintaan opsi lebih / relatif (REFINE) seperti "ada yang lebih bagus", "ada yang lebih murah", "pilihan lain"
    # yang HARUS melewati komparasi dan langsung menuju Seksi 11 (Refinement)
    is_refine_inquiry = is_alternative_request(norm_clean) or any(has_phrase(norm_clean, p) for p in (
        "ada yang lebih", "ada opsi lebih", "ada pilihan lebih", "ada yang lain",
        "ada opsi lain", "ada pilihan lain", "yang lebih bagus", "yang lebih tinggi",
        "yang lebih mahal", "yang lebih murah", "yang lebih kencang"
    ))

    # 7B-0. Pilihan / Rekomendasi Komputer saat belum ada produk ditawarkan ("Mana yang bagus?", "Rekomendasi laptop apa?")
    is_choice_q = is_choice_or_recommendation_query(mnorm) or is_choice_or_recommendation_query(norm_clean)
    if is_choice_q and not is_refine_inquiry and not offered_prods:
        return do_spread(s, catalog, "Supaya ada gambaran, ini pilihan dari yang termurah sampai tertinggi:")

    # 7A. Komparasi Antar Kategori Perangkat (laptop vs desktop)
    cat_tokens = []
    for t in mtoks:
        c = CATEGORY_WORDS.get(t)
        if c and c not in cat_tokens:
            cat_tokens.append(c)
    if "komputer" in cat_tokens and "desktop" not in cat_tokens and "laptop" in cat_tokens:
        cat_tokens = ["laptop", "desktop"]
    if cmp_words and len(set(cat_tokens) - {"computer"}) >= 2 and not refs:
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (
            "Perbedaan utamanya:\n"
            "- **Laptop**: Ringkas dan portabel (mudah dibawa ke mana-mana). Layar, keyboard, dan baterai sudah terintegrasi dalam satu unit.\n"
            "- **Desktop (PC)**: Ditempatkan di meja dan terhubung langsung ke sumber listrik. Memberikan performa lebih tinggi per harga dan upgrade komponen yang lebih fleksibel, namun memerlukan monitor terpisah.\n\n"
            "Di Bobby Computer kami menyediakan laptop, desktop, dan monitor. Kakak lebih membutuhkan yang portabel untuk dibawa bepergian (laptop) atau yang tetap di meja untuk performa maksimal (desktop)?",
            "COMPARE_CATEGORY"
        )

    # 7.1 Penegasan Persona ("Kan mama yang butuh?", "Kan buat mama")
    if is_persona_insist(norm_clean):
        pname = s.get("persona_name") or ("Mama" if "mama" in norm_clean else "Papa")
        s["persona_name"] = pname
        daily_prods = [p for p in catalog.pool("laptop") if (has_tag(p, "daily") or has_tag(p, "office")) and p["harga_idr"] < 10000000][:2]
        if daily_prods:
            s["offered_products"] = [p["kode"] for p in daily_prods]
            s["pool"] = [p["kode"] for p in daily_prods]
            s["shown"] = list(s["offered_products"])
            s["fsm_stage"] = "OFFERED"
            lines = [
                f"Betul sekali Kak, untuk {pname}! Makanya saya sarankan laptop harian yang simpel, tidak berat, dan layarnya nyaman untuk santai di rumah, bukan laptop gaming yang berat dan mahal.\n\nPilihan yang paling pas untuk {pname}:"
            ]
            for i, p in enumerate(daily_prods, 1):
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}. — Harga {format_price(p['harga_idr'])}")
            b0 = daily_prods[0].get("brand") or daily_prods[0]["nama"].split()[0]
            b1 = daily_prods[1].get("brand") or daily_prods[1]["nama"].split()[0]
            lines.append(f"\nKira-kira Kakak lebih sreg dengan merk {b0.title()} atau {b1.title()} untuk {pname}?")
            return "\n".join(lines), "PERSONA_ALIGN"
        return f"Betul sekali Kak, untuk {pname}! Saya siap bantu pilihkan perangkat yang paling nyaman dan pas untuk {pname}.", "PERSONA_ALIGN"

    # 7.2 Negasi Kebutuhan / Aktivitas ("Mamaku gak kerja", "Mamaku bukan anak sekolah")
    negation_info = is_need_negation(norm_clean)
    if negation_info:
        neg_type, neg_word = negation_info
        pname = s.get("persona_name") or ("Mama" if "mama" in norm_clean else ("Papa" if "papa" in norm_clean else "pengguna"))
        if neg_type == "not_work":
            s["needs"] = ["daily"]
            s["persona"] = s.get("persona") or "family_elder"
            s["persona_name"] = pname
            daily_prods = [p for p in catalog.pool("laptop") if (has_tag(p, "daily") or has_tag(p, "office")) and p["harga_idr"] < 10000000][:2]
            s["offered_products"] = [p["kode"] for p in daily_prods]
            s["pool"] = [p["kode"] for p in daily_prods]
            s["shown"] = list(s["offered_products"])
            s["fsm_stage"] = "OFFERED"
            lines = [
                f"Paham Kak! Kalau {pname} tidak untuk kerja kantor, berarti cocoknya untuk pemakaian santai di rumah ya (seperti nonton video/film, browsing resep, belanja online, atau video call keluarga).\n",
                f"Untuk kebutuhan santai {pname}, laptop yang ringan, praktis, dan awet baterai di katalog Bobby Computer pilihannya:"
            ]
            for i, p in enumerate(daily_prods, 1):
                lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}. — Harga {format_price(p['harga_idr'])}")
            lines.append(f"\nAda tipe yang menarik perhatian untuk {pname}, Kak?")
            return "\n".join(lines), "OFFER"
        elif neg_type == "not_school":
            pname = s.get("persona_name") or "Mama"
            return (
                f"Iya betul Kak, mohon maaf ya! Maksud saya tadi untuk pemakaian santai di rumah sehari-hari (bukan untuk belajar atau sekolah). :)\n\n"
                f"Laptop yang saya sebutkan di atas (**Acer Aspire Lite 14** dan **Lenovo IdeaPad Slim 3 14**) memang sangat cocok untuk orang tua di rumah karena ringan, tidak berisik, dan mudah digunakan untuk hiburan santai tanpa fitur yang rumit.\n\n"
                f"Mau dibantu pilihkan antara Acer atau Lenovo untuk {pname}, Kak?"
            ), "PERSONA_ALIGN"
        elif neg_type == "not_game":
            pname = s.get("persona_name") or ("Mama" if s.get("persona") == "family_elder" else "Kakak")
            gaming_codes = [
                p["kode"] for p in offered_prods
                if "gaming" in p.get("tags", []) or (p.get("gpu") and any(g in p["gpu"].lower() for g in ("rtx", "gtx", "radeon rx")))
            ]
            non_gaming = [p for p in offered_prods if p["kode"] not in gaming_codes]
            if not non_gaming and s.get("category"):
                brand_filter = s.get("constraints", {}).get("brand")
                non_gaming = [
                    p for p in catalog.pool(s["category"])
                    if (has_tag(p, "daily") or has_tag(p, "office"))
                    and (not brand_filter or any(a in p["nama"].lower() for a in BRAND_LEXICON.get(brand_filter, [])))
                ]
            if non_gaming:
                p_pick = non_gaming[0]
                s["selected_product"] = p_pick["kode"]
                s["offered_products"] = [p_pick["kode"]]
                s["pool"] = [p_pick["kode"]]
                s["shown"] = [p_pick["kode"]]
                s["fsm_stage"] = "SELECTED"
                gaming_names = " dan ".join(f"**{catalog.by_code[c]['nama']}**" for c in gaming_codes if c in catalog.by_code)
                reject_phrase = f"laptop gaming seperti {gaming_names} langsung kita singkirkan ya" if gaming_names else "pilihan laptop gaming kita singkirkan ya"
                return (
                    f"Paham Kak! Kalau {pname} cuma untuk nonton dan tidak main game, maka {reject_phrase}.\n\n"
                    f"Rekomendasi yang paling pas adalah **{p_pick['nama']}** (Harga {format_price(p_pick['harga_idr'])}). "
                    f"Spesifikasinya ({p_pick['cpu']}, RAM {p_pick['ram_gb']} GB) sudah sangat lancar untuk streaming video/film dan hiburan santai di rumah, "
                    f"serta bodinya ringkas (14 inci) dan ringan tanpa membuat boros budget.\n\n"
                    f"Ada yang ingin ditanyakan lagi tentang {p_pick['nama']}?"
                ), "NEED_ALIGN"
            return f"Siap Kak, kita singkirkan pilihan laptop gaming ya. Untuk kebutuhan non-gaming {pname}, kita fokuskan ke laptop yang ringan dan hemat daya.", "NEED_ALIGN"

    # 7.25 Keberatan Ukuran atau Bobot Fisik Perangkat ("Nitro kegedean", "terlalu berat", "kegedean sih")
    size_obj = is_size_or_weight_objection(norm_clean)
    if size_obj:
        target_person = s.get("persona_name") or ("Mama" if s.get("persona") == "family_elder" else "Kakak")
        obj_prod = None
        if refs:
            obj_prod = refs[0]
        elif s.get("selected_product") and s["selected_product"] in catalog.by_code:
            obj_prod = catalog.by_code[s["selected_product"]]
        elif offered_prods:
            big_ones = [
                p for p in offered_prods
                if "15" in p["nama"] or "16" in p["nama"] or "17" in p["nama"]
                or "gaming" in p.get("tags", [])
                or (p.get("gpu") and "rtx" in p["gpu"].lower())
            ]
            obj_prod = big_ones[0] if big_ones else offered_prods[-1]

        if obj_prod:
            rem_prods = [p for p in offered_prods if p["kode"] != obj_prod["kode"]]
            if not rem_prods and s.get("category"):
                brand_filter = s.get("constraints", {}).get("brand")
                rem_prods = [
                    p for p in catalog.pool(s["category"])
                    if p["kode"] != obj_prod["kode"]
                    and "14" in p["nama"]
                    and (not brand_filter or any(a in p["nama"].lower() for a in BRAND_LEXICON.get(brand_filter, [])))
                ]

            if rem_prods:
                p_compact = rem_prods[0]
                s["selected_product"] = p_compact["kode"]
                s["offered_products"] = [p_compact["kode"]]
                s["pool"] = [p_compact["kode"]]
                s["shown"] = [p_compact["kode"]]
                s["fsm_stage"] = "SELECTED"

                is_gaming_or_big = (
                    "gaming" in obj_prod.get("tags", [])
                    or "nitro" in obj_prod["nama"].lower()
                    or (obj_prod.get("gpu") and "rtx" in obj_prod["gpu"].lower())
                )
                detail_obj = "khas laptop gaming dengan bodi tebal dan bobot lebih berat (sekitar 2 kg lebih)" if is_gaming_or_big else "dengan bodi lebih lebar dan berat"

                return (
                    f"Iya Kak, betul sekali. **{obj_prod['nama']}** memang berlayar 15,6 inci dan {detail_obj}, "
                    f"sehingga terasa kegedean dan kurang praktis kalau untuk kebutuhan santai/nonton {target_person}.\n\n"
                    f"Pilihan yang jauh lebih pas dan ringkas adalah **{p_compact['nama']}** (layar 14 inci, bodi ramping, bobot ringan, harga {format_price(p_compact['harga_idr'])}). "
                    f"Laptop ini sangat nyaman dipakai santai di rumah maupun dibawa bepergian.\n\n"
                    f"Mau saya jelaskan lebih detail tentang spesifikasi {p_compact['nama']}, Kak?"
                ), "SIZE_OBJECTION"

    # 7.26 Penegasan Kebutuhan Aktivitas ("Kan buat nonton?", "Kan cuma buat nonton")
    need_insist_val = is_need_insist(norm_clean)
    if need_insist_val:
        target_person = s.get("persona_name") or ("Mama" if s.get("persona") == "family_elder" else "Kakak")
        compact_prods = [
            p for p in offered_prods
            if not ("gaming" in p.get("tags", []) or (p.get("gpu") and "rtx" in p["gpu"].lower()))
        ]
        if not compact_prods and s.get("category"):
            brand_filter = s.get("constraints", {}).get("brand")
            compact_prods = [
                p for p in catalog.pool(s["category"])
                if (has_tag(p, "daily") or has_tag(p, "office"))
                and (not brand_filter or any(a in p["nama"].lower() for a in BRAND_LEXICON.get(brand_filter, [])))
            ]
        if compact_prods:
            p_fit = compact_prods[0]
            s["selected_product"] = p_fit["kode"]
            s["offered_products"] = [p_fit["kode"]]
            s["pool"] = [p_fit["kode"]]
            s["shown"] = [p_fit["kode"]]
            s["fsm_stage"] = "SELECTED"

            gaming_offered = [
                p for p in offered_prods
                if "gaming" in p.get("tags", []) or (p.get("gpu") and "rtx" in p["gpu"].lower())
            ]
            gaming_note = (
                f"laptop gaming seperti **{gaming_offered[0]['nama']}** memang terlalu berlebihan (overkill) dan bodinya terlalu besar/berat. Oleh karena itu, "
                if gaming_offered else "maka "
            )

            return (
                f"Iya betul Kak! Kalau peruntukannya untuk {target_person} nonton santai, {gaming_note}"
                f"rekomendasi terbaik dan paling efisien adalah **{p_fit['nama']}** (Harga {format_price(p_fit['harga_idr'])}). "
                f"Layarnya 14 inci ringkas, bobotnya ringan, hemat baterai, dan sudah sangat jernih untuk streaming video/film maupun browsing harian.\n\n"
                f"Apakah tipe {p_fit['nama']} ini sudah cocok untuk {target_person}, Kak?"
            ), "NEED_INSIST"

    # 7.27 Permintaan Rekomendasi Definitif ("Apa rekomendasimu?", "Saran kamu apa?", "Menurut kamu yang mana?")
    if is_recommendation_request(norm_clean):
        target_person = s.get("persona_name") or ("Mama" if s.get("persona") == "family_elder" else "Kakak")
        hist_str = str(s.get("history", [])).lower()
        is_nonton_or_daily = "nonton" in hist_str or any(n in ("daily", "office") for n in s.get("needs", []))

        best_p = None
        non_gaming_offered = [
            p for p in offered_prods
            if not ("gaming" in p.get("tags", []) or (p.get("gpu") and "rtx" in p["gpu"].lower()))
        ]
        if is_nonton_or_daily and non_gaming_offered:
            best_p = non_gaming_offered[0]
        elif s.get("selected_product") and s["selected_product"] in catalog.by_code:
            best_p = catalog.by_code[s["selected_product"]]
        elif offered_prods:
            best_p = offered_prods[0]
        elif s.get("category"):
            brand_filter = s.get("constraints", {}).get("brand")
            pool_c = [
                p for p in catalog.pool(s["category"])
                if not brand_filter or any(a in p["nama"].lower() for a in BRAND_LEXICON.get(brand_filter, []))
            ]
            if pool_c:
                best_p = pool_c[0]

        if best_p:
            s["selected_product"] = best_p["kode"]
            s["offered_products"] = [best_p["kode"]]
            s["pool"] = [best_p["kode"]]
            s["shown"] = [best_p["kode"]]
            s["fsm_stage"] = "SELECTED"

            if is_nonton_or_daily:
                return (
                    f"Untuk kebutuhan {target_person} yang utamanya dipakai santai dan nonton, rekomendasi terbaik dari saya adalah **{best_p['nama']}** (Harga {format_price(best_p['harga_idr'])}).\n\n"
                    f"Pertimbangan utamanya:\n"
                    f"1. **Ukuran & Bobot Praktis**: Layar 14 inci yang ramping dan ringan, sangat nyaman dipangku atau dipakai santai di rumah.\n"
                    f"2. **Performa Pas & Hening**: Prosesor {best_p['cpu']} dan RAM {best_p['ram_gb']} GB {best_p.get('ram_type', '')} sudah sangat lancar untuk streaming YouTube/film dan browsing tanpa panas atau bising.\n"
                    f"3. **Hemat Budget**: Harganya jauh lebih efisien dibanding laptop gaming yang spesifikasi grafisnya tidak akan terpakai jika hanya untuk nonton.\n\n"
                    f"Mau saya bantu jelaskan detail lebih lanjut tentang {best_p['nama']}, Kak?"
                ), "RECOMMENDATION"
            else:
                return (
                    f"Rekomendasi terbaik dari saya adalah **{best_p['nama']}** (Harga {format_price(best_p['harga_idr'])}). "
                    f"Laptop ini ditenagai {best_p['cpu']}, RAM {best_p['ram_gb']} GB, dan {best_p['storage']}, yang merupakan pilihan paling seimbang antara performa dan harga.\n\n"
                    f"Apakah tipe ini sesuai dengan yang Kakak harapkan?"
                ), "RECOMMENDATION"

    # 7.3 Deklarasi Persona Baru ("Buat Mama sih", "Buat Papa")
    if persona_t and not needs_t and not s.get("persona"):
        s["persona"] = persona_t
        pname = extract_persona_name(norm_clean) or ("Mama" if persona_t == "family_elder" else "keluarga")
        s["persona_name"] = pname
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "PERSONA_CLARIFY"
        return (
            f"Oh, untuk {pname} ya Kak! Biasanya {pname} lebih sering pakai untuk kebutuhan santai seperti "
            "nonton/browsing, kerja kantor ngetik dokumen, atau ada kebutuhan khusus seperti olah data/desain Kak?"
        ), "ASK"

    # 7B. Pertanyaan Kecocokan Produk dengan Beban Kerja ("Emang cocok buat developer?", "Bisa buat render gak?", "Emangnya bisa pake itu?", "Itu semua untuk kantoran?")
    is_group_ref = any(has_phrase(norm_clean, p) for p in (
        "itu semua", "semua itu", "semuanya", "semua di atas", "pilihan di atas",
        "semua pilihan", "ketiganya", "keduanya", "semua laptop", "semua pc",
        "semuanya untuk", "semua untuk", "itu semua untuk", "semuanya buat", "semua buat",
        "itu buat kantoran semua", "itu untuk kantoran semua", "buat kantoran semua",
        "buat kantor semua", "untuk kantor semua", "untuk kantoran semua"
    )) or (
        any(w in toks for w in ("semua", "semuanya", "ketiganya", "keduanya"))
        and any(w in toks for w in ("kantoran", "kantor", "kerja", "gaming", "desain", "koding", "kuliah"))
    )

    is_suitability_q = (
        any(has_phrase(norm_clean, p) for p in (
            "emang cocok", "apakah cocok", "cocok gak", "cocok tidak", "bisa buat", "bisa untuk",
            "yang cocok buat", "yang cocok untuk", "bisa pake", "bisa pakai", "bisa dipake", "bisa dipakai",
            "emang bisa", "emangnya bisa", "untuk kantoran", "buat kantoran", "untuk kantor", "buat kantor",
            "untuk kerja", "buat kerja"
        ))
        or (is_group_ref and (bool(needs_t) or "?" in raw or any(w in toks for w in ("apakah", "emang", "buat", "untuk"))))
        or (bool(offered_prods) and bool(needs_t) and set(needs_t) == set(s.get("needs", [])) and ("?" in raw or any(w in toks for w in ("apakah", "emang", "kok", "itu", "ini"))))
    )
    if is_suitability_q and (needs_t or s["needs"]) and (refs or s["offered_products"]):
        target_prods = refs or [catalog.by_code[c] for c in s["offered_products"] if c in catalog.by_code]
        query_needs = needs_t or s["needs"]
        matched = [p for p in target_prods if any(has_tag(p, n) for n in query_needs)]
        if matched:
            s["needs"] = query_needs
            if len(matched) == 1:
                p = matched[0]
                s["selected_product"] = p["kode"]
                s["fsm_stage"] = "SELECTED"
                gpu_str = f", GPU {p['gpu']}" if p.get("gpu") else ""
                reason = p.get("usage_text") or f"ditenagai {p['cpu']}{gpu_str}, dan RAM {p['ram_gb']} GB"
                return (
                    f"Untuk kebutuhan {need_labels(query_needs)}, dari pilihan di atas yang paling pas adalah **{p['nama']}** "
                    f"(Harga {format_price(p['harga_idr'])}). Laptop ini {reason}.\n\n"
                    f"Ada yang ingin ditanyakan lagi tentang {p['nama']}?"
                ), "SUITABILITY"
            else:
                has_discrete = any(
                    p.get("gpu_type") == "discrete" or any(x in p.get("gpu", "").lower() for x in ("rtx", "gtx", "geforce", "radeon rx"))
                    for p in matched
                )
                pure_office = [
                    p for p in matched
                    if not (p.get("gpu_type") == "discrete" or any(x in p.get("gpu", "").lower() for x in ("rtx", "gtx", "geforce", "radeon rx")))
                ]
                high_perf = [p for p in matched if p not in pure_office]

                if (is_group_ref or "office" in query_needs) and has_discrete and pure_office:
                    lines = ["Iya Kak, ketiganya bisa digunakan untuk kerja kantoran, namun ada perbedaan peruntukan utamanya:"]
                    p_pure_names = " dan ".join(f"**{p['nama']}**" for p in pure_office)
                    lines.append(f"- {p_pure_names} adalah laptop kantor murni yang tipis, ringan, dan hemat daya.")
                    p_high_names = " dan ".join(f"**{p['nama']}**" for p in high_perf)
                    lines.append(f"- Sedangkan {p_high_names} dibekali kartu grafis dedicated NVIDIA GeForce RTX, sehingga selain lancar untuk aplikasi kantor, juga sangat bertenaga untuk desain grafis berat, video editing, dan gaming.")
                    lines.append(f"\nJika kebutuhan Kakak murni untuk aplikasi kantor standar (Word, Excel, Zoom, browsing), **{pure_office[0]['nama']}** adalah pilihan yang paling hemat dan tepat.")
                    lines.append("Ada tipe yang paling sesuai dengan preferensi Kakak?")
                    return "\n".join(lines), "SUITABILITY"

                if is_group_ref:
                    lines = [
                        f"Betul sekali Kak, semua pilihan di atas sangat cocok untuk kebutuhan {need_labels(query_needs)}.",
                        "Semuanya dibekali performa stabil dan memadai untuk multitasking harian.\n",
                        "Ada tipe yang paling sesuai dengan preferensi Kakak?"
                    ]
                    return "\n".join(lines), "SUITABILITY"

                reasons = []
                for p in matched:
                    if p.get("usage_text"):
                        reasons.append(f"- **{p['nama']}**: {p['usage_text']} ({p['cpu']}, {p.get('gpu', '')}, RAM {p['ram_gb']} GB)")
                    elif p["kategori"] == "printer":
                        reasons.append(f"- **{p['nama']}**: {specs_line(p)}")
                    else:
                        gpu_str = f", {p['gpu']}" if p.get('gpu') else ""
                        reasons.append(f"- **{p['nama']}**: ditenagai {p['cpu']}{gpu_str}, dan RAM {p['ram_gb']} GB yang sangat mumpuni untuk kebutuhan tersebut.")
                return f"Untuk kebutuhan {need_labels(query_needs)}, tipe yang cocok dari pilihan di atas adalah:\n" + "\n".join(reasons) + "\n\nAda tipe yang lebih menarik perhatian Kakak?", "SUITABILITY"
        else:
            if is_group_ref or "?" in raw or any(w in toks for w in ("apakah", "emang", "bisa")):
                return (
                    f"Pilihan di atas kurang cocok untuk kebutuhan {need_labels(query_needs)} Kak, "
                    f"karena belum memenuhi spesifikasi minimum yang disarankan.\n\n"
                    f"Mau saya carikan rekomendasi lain yang khusus bertenaga untuk {need_labels(query_needs)}?"
                ), "SUITABILITY"
            s["needs"] = query_needs
            reply, _ = do_offer(s, catalog, f"Untuk kebutuhan {need_labels(query_needs)}, seri sebelumnya kurang disarankan. Pilihan yang paling pas di katalog kami:\n")
            return reply, "SUITABILITY"

    # 7C. Bantuan Pengambilan Keputusan Khusus dengan Dilema/Kekhawatiran (Decision Assistance)
    # Misal: "Cocok yang mana nih? Ntar diomelin mama kalo salah pilih", "Takut salah pilih", "Saran kamu apa"
    has_decision_anxiety = any(has_phrase(norm_clean, p) for p in (
        "salah pilih", "diomelin", "takut salah", "bingung pilih",
        "enaknya yang mana", "mending ambil yang mana"
    ))
    if has_decision_anxiety and len(offered_prods) >= 2 and not is_refine_inquiry:
        s["fsm_stage"] = "NARROWING_DOWN"
        return render_decision_advice(offered_prods, s), "DECISION_HELP"

    # 7D. Komparasi Produk Langsung (§12)
    # Misal: "Bagus mana?", "Mana yang bagus dari 2 itu?", "Bedanya apa?"
    if not is_refine_inquiry:
        if len(refs) >= 2 and (cmp_words or "atau" in mtoks) or (cmp_words and len(offered_prods) >= 2):
            prods = refs if len(refs) >= 2 else offered_prods
            s["fsm_stage"] = "COMPARING"
            return compare_answer(prods[:3], needs_t), "COMPARE"
        if cmp_words and len(refs) < 2 and len(offered_prods) < 2:
            return "Bisa disebutkan Kak, mau dibandingkan dengan produk yang mana?", "COMPARE"

    # 7D-2. Konfirmasi & Perbandingan Harga ("Lebih mahal ya?", "Lebih murah ya?", "Mahalan mana?", "Kok lebih mahal?")
    if is_price_confirm_or_inquiry(norm_clean):
        p_target = None
        p_base = None
        
        # 1. Jika ada referensi produk eksplisit di input user
        if len(refs) >= 2:
            p_target, p_base = refs[0], refs[1]
        elif len(refs) == 1:
            p_target = refs[0]
            if s.get("selected_product") and s["selected_product"] != p_target["kode"]:
                p_base = catalog.by_code.get(s["selected_product"])
            elif offered_prods:
                p_base = next((p for p in offered_prods if p["kode"] != p_target["kode"]), None)
        else:
            # 2. Ambil dari riwayat percakapan: produk yang baru disebut oleh bot vs produk yang sebelumnya aktif
            last_bot_text = ""
            for role, text in reversed(s.get("history", [])):
                if role in ("assistant", "bot"):
                    last_bot_text = text
                    break
            bot_refs = [p for p in catalog.products if p["nama"].lower() in last_bot_text.lower() or p["kode"].lower() in last_bot_text.lower()]
            
            curr_selected = catalog.by_code.get(s.get("selected_product")) if s.get("selected_product") else None
            
            if bot_refs and curr_selected and bot_refs[0]["kode"] != curr_selected["kode"]:
                p_target = bot_refs[0]
                p_base = curr_selected
            elif bot_refs and len(bot_refs) >= 2:
                p_target, p_base = bot_refs[0], bot_refs[1]
            elif offered_prods and len(offered_prods) >= 2:
                p_target, p_base = offered_prods[1], offered_prods[0]
            elif offered_prods and len(offered_prods) == 1:
                p_target = offered_prods[0]
            elif curr_selected:
                p_target = curr_selected

        if p_target and p_base:
            diff = p_target["harga_idr"] - p_base["harga_idr"]
            diff_abs = abs(diff)
            diff_str = format_price(diff_abs)
            
            is_asking_pricier = any(w in norm_clean for w in ("mahal", "mahalan", "tinggi"))
            is_asking_cheaper = any(w in norm_clean for w in ("murah", "murahan", "rendah", "hemat"))
            
            # Cek keunggulan spesifikasi
            gpu_desc = ""
            if p_target.get("gpu") and p_base.get("gpu") and p_target["gpu"] != p_base["gpu"]:
                gpu_desc = f"kartu grafis {p_target['gpu']} (dibanding {p_base['gpu']} pada {p_base['nama']})"
            cpu_desc = ""
            if p_target.get("cpu") and p_base.get("cpu") and p_target["cpu"] != p_base["cpu"]:
                cpu_desc = f"prosesor {p_target['cpu']} (dibanding {p_base['cpu']})"
                
            spec_reason = gpu_desc or cpu_desc or "spesifikasi yang dibawanya"
            
            if is_asking_pricier:
                if diff > 0:
                    reply = (
                        f"Iya betul Kak, **{p_target['nama']}** ({format_price(p_target['harga_idr'])}) memang lebih mahal sekitar {diff_str} dibanding **{p_base['nama']}** ({format_price(p_base['harga_idr'])}).\n\n"
                        f"Perbedaan harga ini sebanding dengan performanya, karena {p_target['nama']} dibekali {spec_reason}.\n\n"
                        f"Mau saya bantu jelaskan detail perbandingan spesifikasinya Kak?"
                    )
                else:
                    reply = (
                        f"Bukan Kak, justru **{p_target['nama']}** ({format_price(p_target['harga_idr'])}) lebih hemat sekitar {diff_str} dibanding **{p_base['nama']}** ({format_price(p_base['harga_idr'])}).\n\n"
                        f"Ada yang ingin ditanyakan lagi tentang keduanya?"
                    )
                return reply, "COMPARE"
            elif is_asking_cheaper:
                if diff < 0:
                    reply = (
                        f"Iya betul Kak, **{p_target['nama']}** ({format_price(p_target['harga_idr'])}) memang lebih murah/hemat sekitar {diff_str} dibanding **{p_base['nama']}** ({format_price(p_base['harga_idr'])}).\n\n"
                        f"Ada pertimbangan khusus terkait budget, Kak?"
                    )
                else:
                    reply = (
                        f"Bukan Kak, justru **{p_target['nama']}** ({format_price(p_target['harga_idr'])}) lebih tinggi harganya sekitar {diff_str} dibanding **{p_base['nama']}** ({format_price(p_base['harga_idr'])}).\n\n"
                        f"Hal ini karena {p_target['nama']} dibekali {spec_reason}."
                    )
                return reply, "COMPARE"
            else:
                if diff > 0:
                    higher, lower = p_target, p_base
                else:
                    higher, lower = p_base, p_target
                reply = (
                    f"Di antara keduanya, yang lebih tinggi harganya adalah **{higher['nama']}** ({format_price(higher['harga_idr'])}) dibanding **{lower['nama']}** ({format_price(lower['harga_idr'])}), dengan selisih sekitar {diff_str}."
                )
                return reply, "COMPARE"
        elif p_target:
            reply = f"Untuk **{p_target['nama']}**, harganya adalah {format_price(p_target['harga_idr'])}, Kak. Apakah ini sesuai dengan kisaran budget Kakak?"
            return reply, "COMPARE"

    # 7E. Bantuan Keputusan Umum
    is_decision_help = any(has_phrase(norm_clean, p) for p in (
        "cocok yang mana", "mana yang cocok", "pilih yang mana", "pilih mana",
        "mending mana", "mending yang mana", "bagus yang mana", "bagusan yang mana",
        "ambil yang mana"
    ))
    if is_decision_help and len(offered_prods) >= 2 and not is_refine_inquiry:
        s["fsm_stage"] = "NARROWING_DOWN"
        return render_decision_advice(offered_prods, s), "DECISION_HELP"

    # 7E. Pertanyaan Alat Tambahan / AI / Aplikasi Harian pada Produk yang Sudah Ditawarkan
    # Misal: "Tapi, mama sering pake gemini juga", "Bisa buat zoom juga?", "Bisa buat browsing?"
    daily_tools = {"gemini", "chatgpt", "canva", "zoom", "browsing", "sosmed", "youtube", "office", "word", "excel"}
    is_tool_inquiry = bool(set(mtoks) & daily_tools) or any(has_phrase(norm_clean, p) for p in (
        "pake gemini", "pakai gemini", "buka gemini", "pake chatgpt", "pakai chatgpt", "buka chatgpt",
        "buat zoom", "buat canva", "buat ngetik", "buat office"
    ))
    if is_tool_inquiry and offered_prods:
        tool_name = "Google Gemini" if "gemini" in mtoks else ("ChatGPT" if "chatgpt" in mtoks else "aplikasi tersebut")
        target_person = s.get("persona_name") or ("Mama" if s.get("persona") == "family_elder" else "Kakak")
        if len(offered_prods) == 1:
            p = offered_prods[0]
            prod_ref = f"**{p['nama']}**"
            ram_info = f"RAM {p['ram_gb']} GB {p['ram_type']}" if p.get("ram_gb") else "RAM yang memadai"
            subj = "Laptop ini"
        else:
            prod_ref = " dan ".join(f"**{p['nama']}**" for p in offered_prods[:2])
            ram_gb = min(p["ram_gb"] for p in offered_prods[:2] if p.get("ram_gb")) or 16
            ram_type = offered_prods[0].get("ram_type", "DDR5")
            ram_info = f"RAM {ram_gb} GB {ram_type}"
            subj = "Keduanya"
        return (
            f"Tentu sangat lancar Kak! Untuk penggunaan {tool_name}, browsing, maupun aplikasi berbasis web lainnya, "
            f"{prod_ref} sudah lebih dari cukup — berkat {ram_info} dan prosesor generasi terbaru.\n\n"
            f"{subj} siap mendukung aktivitas {target_person} untuk pekerjaan utama sekaligus penggunaan {tool_name} sehari-hari.",
            "PRODUCT_TOOL_SUPPORT"
        )

    # 7F. Keberatan / Komentar atas Spesifikasi Produk ("Tanggung banget", "Nanggung banget", "Speknya nanggung")
    if is_spec_objection(norm_clean):
        target_prod = None
        if s.get("selected_product") and s["selected_product"] in catalog.by_code:
            target_prod = catalog.by_code[s["selected_product"]]
        elif offered_prods and len(offered_prods) == 1:
            target_prod = offered_prods[0]
            
        if target_prod:
            cat = target_prod["kategori"]
            price_str = format_price(target_prod["harga_idr"])
            better_pool = [
                p for p in catalog.pool(cat)
                if p["kode"] != target_prod["kode"] and p["harga_idr"] >= target_prod["harga_idr"]
            ]
            gpu_6gb = [p for p in better_pool if any(v in p.get("gpu", "").lower() for v in ("6 gb", "8 gb", "12 gb", "16 gb"))]
            suggestions = (gpu_6gb or better_pool)[:3]
            
            if suggestions:
                s["offered_products"] = [p["kode"] for p in suggestions]
                s["pool"] = [p["kode"] for p in suggestions]
                s["shown"] = list(s["offered_products"])
                s["fsm_stage"] = "OFFERED"
                
                spec_note = f"kartu grafis {target_prod['gpu']}" if target_prod.get("gpu") else "spesifikasinya"
                lines = [
                    f"Iya Kak, memang {spec_note} di kisaran harga {price_str} sering dirasa agak tanggung untuk kebutuhan grafis atau gaming berat masa kini.\n\n"
                    f"Jika Kakak ingin {CATEGORY_LABEL[cat]} dengan performa yang lebih lega (seperti GPU minimal 6 GB ke atas), ada beberapa alternatif yang jauh lebih mumpuni di katalog kami:"
                ]
                for i, p in enumerate(suggestions, 1):
                    price_str_s = f" — Harga {format_price(p['harga_idr'])}" if not s["hide_price"] else ""
                    lines.append(f"{i}. **{p['nama']}** — {specs_line(p)}.{price_str_s}")
                lines.append("\nAda tipe yang lebih menarik perhatian Kakak?")
                return "\n".join(lines), "PRODUCT_Q"



    # =========================================================================
    # GATE: Produk sudah ditawarkan + user tidak tanya spek langsung + tidak minta produk baru
    # → serahkan ke LLM dengan konteks spek produk yang sedang dibahas.
    # =========================================================================
    _wants_new = (
        is_refine_inquiry
        or (pref_info["rel"] is not None)
        or bool(needs_t)
        or (needs_t and set(needs_t) != set(s.get("needs", [])))
        or (cat_t and cat_t != s.get("category") and not _bundle_item)  # kategori baru tapi bukan bundling
        or (cmp_words and len(offered_prods) >= 2)
        or is_suitability_q
        or has_decision_anxiety
        or is_choice_q
        or is_recommendation_request(norm_clean)
        or bool(is_size_or_weight_objection(norm_clean))
        or bool(is_need_insist(norm_clean))
        or bool(extract_budget(norm_clean))
        or bool(persona_t)
        or bool(extract_persona(norm_clean))
        or bool(extract_persona_name(norm_clean))
        or is_persona_insist(norm_clean)
        or bool(is_need_negation(norm_clean))
        or s.get("fsm_stage") in ("PERSONA_CLARIFY", "AWAITING_NEED")
    )
    if (
        offered_prods
        and not _wants_new
        and llm_model
        and not (
            persona_t
            or extract_persona(norm_clean)
            or extract_persona_name(norm_clean)
            or is_persona_insist(norm_clean)
            or is_need_negation(norm_clean)
            or is_size_or_weight_objection(norm_clean)
            or is_recommendation_request(norm_clean)
            or is_need_insist(norm_clean)
        )
    ):
        # Gate aktif untuk:
        # (1) tidak ada attrs sama sekali, ATAU
        # (2) kalimat retorik/hipotesis bukan pertanyaan spek langsung, ATAU  
        # (3) pertanyaan lanjutan yang ambigu: "gimana?", "bagus gak?", "oke gak?", "worth it gak?"
        is_rhetorical = any(has_phrase(norm_clean, p) for p in (
            "mestinya", "harusnya", "bener gak", "betul gak", "bener tidak",
            "betul tidak", "iya gak", "kan ya", "emang bisa", "bisa gak sih",
            "bisa tidak sih", "gak ngerti", "kurang ngerti", "tidak ngerti",
            "gak tau", "gak tahu", "tidak tahu", "sayang sekali", "wih keren",
            "keren ya", "yang pake", "yang pakai", "bukan aku", "bukan saya",
            "gimana", "bagus gak", "oke gak", "worth it", "layak gak", "pantas gak"
        ))
        # Juga aktifkan untuk pertanyaan ketersediaan tanpa spec yang jelas jika ada brand terkait
        _is_vague_avail = (
            not attrs
            and any(t in AVAIL_VERBS for t in toks)
            and not extract_hardware_spec_filter(norm_clean)
            and not extract_category(norm_clean)
        )
        if not attrs or is_rhetorical or _is_vague_avail:
            chat_hist = s.get("history", [])
            llm_reply = query_llm_product_chat(
                raw, s, offered_prods, chat_history=chat_hist, model=llm_model
            )
            if llm_reply:
                return llm_reply, "LLM_PRODUCT_CHAT"


    # 8. Pertanyaan Produk / Spesifikasi / Harga (§11)
    effective_cat = cat_t or s.get("category")
    if attrs == ["price"] and not refs and is_q and not budget_stmt and not pref_info["prefs"] and not s["offered_products"] and not s["selected_product"]:
        if effective_cat:
            pool = catalog.pool(effective_cat)
            lo, hi = min(p["harga_idr"] for p in pool), max(p["harga_idr"] for p in pool)
            lo_prod = min(pool, key=lambda p: p["harga_idr"])["nama"]
            hi_prod = max(pool, key=lambda p: p["harga_idr"])["nama"]
            s["last_question"] = {"slot": "need"}
            s["fsm_stage"] = "AWAITING_NEED"
            return (f"Untuk harga {CATEGORY_LABEL[effective_cat]} di katalog kami mulai dari "
                    f"{format_price(lo)} ({lo_prod}) sampai {format_price(hi)} ({hi_prod}). "
                    f"{CATEGORY_NOUN_NYA[effective_cat].capitalize()} rencana mau dipakai untuk kebutuhan apa, Kak?"), "PRODUCT_Q"
        else:
            s["last_question"] = {"slot": "need"}
            s["fsm_stage"] = "AWAITING_NEED"
            ranges = []
            for c in ("laptop", "desktop", "printer", "monitor"):
                cp = [p for p in catalog.products if p["kategori"] == c]
                if cp:
                    lo, hi = min(p["harga_idr"] for p in cp), max(p["harga_idr"] for p in cp)
                    ranges.append(f"{c} mulai dari {format_price(lo)} sampai {format_price(hi)}")
            if len(ranges) > 1:
                range_str = ", ".join(ranges[:-1]) + ", dan " + ranges[-1]
            else:
                range_str = ranges[0] if ranges else ""
            return (f"Di katalog Bobby Computer, harga {range_str}. "
                    "Ada kebutuhan atau perangkat tertentu yang sedang dicari, Kak?"), "PRODUCT_Q"
                
    if attrs and (is_q or refs or "spec" in attrs) and not pref_info["prefs"] and not budget_stmt:
        targets = refs or (
            [catalog.by_code[s["selected_product"]]] if s["selected_product"]
            else [catalog.by_code[c] for c in s["offered_products"]]
        )
        if targets:
            if refs and len(refs) == 1:
                s["selected_product"] = refs[0]["kode"]
            return answer_attrs(targets[:3], attrs, bool(refs), mnorm), "PRODUCT_Q"
        if attrs == ["price"] and effective_cat:
            pool = catalog.pool(effective_cat)
            lo, hi = min(p["harga_idr"] for p in pool), max(p["harga_idr"] for p in pool)
            lo_prod = min(pool, key=lambda p: p["harga_idr"])["nama"]
            hi_prod = max(pool, key=lambda p: p["harga_idr"])["nama"]
            s["last_question"] = {"slot": "need"}
            s["fsm_stage"] = "AWAITING_NEED"
            return (f"Untuk harga {CATEGORY_LABEL[effective_cat]} di katalog kami mulai dari "
                    f"{format_price(lo)} ({lo_prod}) sampai {format_price(hi)} ({hi_prod}). "
                    f"{CATEGORY_NOUN_NYA[effective_cat].capitalize()} rencana mau dipakai untuk kebutuhan apa, Kak?"), "PRODUCT_Q"
        if not (needs_t or cat_t):
            cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
            return f"Belum ada produk spesifik yang sedang kita bahas, Kak. Mau cari {cat_name} untuk kebutuhan apa?", "PRODUCT_Q"
            
    # 9. Niat Beli & Pertanyaan Transaksi (§18)
    purchase_kw = find_phrase(norm_clean, PURCHASE_TOKENS)
    if purchase_kw and not needs_t and not cat_t:
        if refs or s["selected_product"] or len(offered_prods) == 1:
            target = refs or ([catalog.by_code[s["selected_product"]]] if s["selected_product"]
                              else [catalog.by_code[c] for c in s["offered_products"]])
            if len(target) == 1:
                s["selected_product"] = target[0]["kode"]
            msg = "Maaf, Kak, informasi transaksi, pembayaran, dan pengiriman belum tersedia di katalog kami."
            if len(target) == 1:
                msg += "\nBerikut ringkasan spesifikasi produk yang dipilih:\n" + render_summary(target[0], not s["hide_price"])
            return msg, "PURCHASE"
        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        s["last_question"] = {"slot": "need"}
        s["fsm_stage"] = "AWAITING_NEED"
        return (f"Untuk transaksi dan pemesanan langsung, saat ini informasinya belum tersedia di katalog kami, Kak. "
                f"Saya siap membantu memberikan rekomendasi dan rincian spesifikasi {cat_name} terlebih dahulu. "
                f"Ada perangkat komputer yang sedang dicari?"), "PURCHASE"

    # 10. Seleksi langsung produk berdasarkan nama/kode
    if refs and not needs_t and not cat_t and not pref_or_constraint:
        if len(refs) == 1:
            s["selected_product"] = refs[0]["kode"]
        s["offered_products"] = [p["kode"] for p in refs[:3]]
        s["pool"] = [p["kode"] for p in refs[:3]]
        s["category"] = refs[0]["kategori"]
        s["fsm_stage"] = "OFFERED"
        if refs[0].get("brand"):
            s["constraints"]["brand"] = refs[0]["brand"]
        avail = bool(toks) and toks[0] in AVAIL_VERBS
        pre = "Ada di katalog kami. Ini detailnya:\n" if avail else ""
        return pre + "\n\n".join(render_summary(p, not s["hide_price"]) for p in refs[:3]), "SELECT"

    # 11. Opsi lain / Opsi lebih murah / Opsi lebih bagus (Relative Refinements)
    is_alt_req = is_alternative_request(norm_clean) or bool(set(mtoks) & {"lain", "lainnya"})
    is_cat_change = bool(cat_t and cat_t != s.get("category"))
    has_new_unrelated_needs = bool(needs_t and set(needs_t) != set(s.get("needs", [])) and needs_t != ["printing"])
    if is_alt_req and not is_cat_change and not has_new_unrelated_needs:
        shown_codes = set(s.get("shown", [])) | set(s.get("offered_products", []))
        if s.get("selected_product"):
            shown_codes.add(s["selected_product"])

        rest = [c for c in s.get("pool", []) if c not in shown_codes][:3]
        if rest:
            s["shown"] += rest
            s["offered_products"] = rest
            prods = [catalog.by_code[c] for c in rest]
            return "\n".join(["Ini beberapa pilihan lainnya, Kak:"] +
                             render_product_lines(prods, s["needs"], not s["hide_price"])), "MORE"

        # Jika pengguna memiliki kebutuhan khusus (s["needs"]) dan tidak ada batasan budget,
        # maka semua pilihan yang cocok untuk kebutuhan tersebut sudah ditampilkan di s["pool"]!
        if s.get("needs") and s.get("constraints", {}).get("budget_max") is None:
            return "Itu semua pilihan yang sesuai di katalog kami, Kak.", "MORE"

        # Jika s["pool"] sudah habis atau kosong/hanya 1 produk, cari dari katalog kategori aktif
        eff_cat = s.get("category") or "laptop"
        cat_pool = catalog.pool(eff_cat)
        unshown = [p for p in cat_pool if p["kode"] not in shown_codes]
        
        c = s.get("constraints", {})
        if c.get("budget_max") is not None:
            b_cand = [p for p in unshown if p["harga_idr"] <= c["budget_max"]]
            if b_cand:
                cand_shown = b_cand[:3]
                s["shown"] += [p["kode"] for p in cand_shown]
                s["offered_products"] = [p["kode"] for p in cand_shown]
                return "\n".join(["Ini pilihan lain yang masih dalam budget Kakak:"] +
                                 render_product_lines(cand_shown, s["needs"], not s["hide_price"])), "MORE"
            else:
                curr_p = catalog.by_code.get(s.get("selected_product")) if s.get("selected_product") else (offered_prods[0] if offered_prods else None)
                curr_name = f"**{curr_p['nama']}** ({format_price(curr_p['harga_idr'])})" if curr_p else "pilihan sebelumnya"
                higher_cand = sorted(unshown, key=lambda p: p["harga_idr"])[:2]
                if higher_cand:
                    alts_str = " atau ".join(f"**{p['nama']}** ({format_price(p['harga_idr'])})" for p in higher_cand)
                    s["last_question"] = {"slot": "confirm_product", "product": higher_cand[0]["kode"]}
                    cat_name = CATEGORY_LABEL.get(eff_cat, eff_cat)
                    return (
                        f"Untuk {cat_name} dengan budget {budget_desc(c)}, di katalog kami hanya ada {curr_name}, Kak.\n\n"
                        f"Namun jika budget bisa dinaikkan sedikit, pilihan berikutnya ada {alts_str}.\n\n"
                        f"Mau saya bantu jelaskan spesifikasi opsi tersebut, Kak?"
                    ), "MORE"
                else:
                    return f"Itu semua pilihan {CATEGORY_LABEL.get(eff_cat, eff_cat)} yang tersedia di katalog kami, Kak.", "MORE"

        if unshown:
            cand_shown = unshown[:3]
            s["shown"] += [p["kode"] for p in cand_shown]
            s["offered_products"] = [p["kode"] for p in cand_shown]
            return "\n".join(["Ini beberapa pilihan lainnya, Kak:"] +
                             render_product_lines(cand_shown, s["needs"], not s["hide_price"])), "MORE"
        return f"Itu semua pilihan {CATEGORY_LABEL.get(eff_cat, eff_cat)} yang tersedia di katalog kami saat ini, Kak.", "MORE"
                         
    is_underpowered = is_mismatch(mnorm) or any(has_phrase(mnorm, p) for p in ("mana bisa", "gak kuat", "tidak kuat", "kurang kuat", "kuatlah"))
    if (pref_info["rel"] or is_underpowered or is_refine_inquiry) and offered_prods and not (needs_t or cat_t):
        r = build_ranked(s, catalog)
        prices = [p["harga_idr"] for p in offered_prods]
        if pref_info["rel"] == "cheaper" or any(has_phrase(norm_clean, p) for p in ("lebih murah", "murahan")):
            cand = [p for p in r["items"] if p["harga_idr"] < min(prices)]
            if not cand and not s.get("needs") and s.get("category"):
                cand = [p for p in catalog.pool(s["category"]) if p["harga_idr"] < min(prices)]
            cand.sort(key=lambda p: p["harga_idr"])
            none_msg = "Pilihan tadi sudah yang paling hemat untuk kebutuhan tersebut di katalog kami, Kak."
            intro = "Ini opsi yang sesuai, Kak:"
        else:
            cand = [p for p in r["items"] if p["harga_idr"] > min(prices) and p["kode"] not in s["offered_products"]]
            if not cand:
                cand = [p for p in r["items"] if p["harga_idr"] > max(prices)]
            if not cand and (not s.get("needs") or is_underpowered) and s.get("category"):
                cand = [p for p in catalog.pool(s["category"]) if p["harga_idr"] > max(prices) and p["kode"] not in s["offered_products"]]
            cand.sort(key=lambda p: -p["harga_idr"])
            cat_label = CATEGORY_LABEL[s.get("category")] if s.get("category") else "katalog"
            cat_pool = catalog.pool(s.get("category"))
            max_pool_price = max(p["harga_idr"] for p in cat_pool) if cat_pool else 0
            if s.get("needs") and max(prices) < max_pool_price:
                top_p = max(cat_pool, key=lambda p: p["harga_idr"])
                s["last_question"] = {"slot": "confirm_product", "product": top_p["kode"]}
                none_msg = (f"Pilihan tadi sudah yang paling tinggi untuk kebutuhan {need_labels(s['needs'])} di katalog kami, Kak. "
                            f"Jika butuh kapasitas atau performa yang lebih tangguh lagi, ada laptop kelas workstation/gaming seperti **{top_p['nama']}** ({format_price(top_p['harga_idr'])}). "
                            f"Mau saya jelaskan spesifikasinya, Kak?")
            else:
                none_msg = f"Pilihan tadi sudah yang paling tinggi spesifikasinya di katalog {cat_label} kami, Kak."
            intro = "Paham Kak, jika butuh spesifikasi yang lebih tangguh dan bertenaga, ini pilihan yang lebih tinggi di katalog kami:"
        if not cand:
            return none_msg, "REFINE"
        cand = cand[:3]
        s["offered_products"] = [p["kode"] for p in cand]
        s["shown"] += [c for c in s["offered_products"] if c not in s["shown"]]
        return "\n".join([intro] +
                         render_product_lines(cand, s["needs"], not s["hide_price"])), "REFINE"

    # 12. Ketidakpastian & Penanganan Keraguan (Anti-Parrot Looping)
    if is_uncertain(mnorm):
        # Jika pelanggan mengulang terserah setelah sebaran (Test AD)
        if s["spread_shown"]:
            return "Dari pilihan di atas, ada yang mau saya jelaskan lebih detail spesifikasinya?", "SPREAD2"
        # Jika pelanggan menyatakan belum tahu budget saat kebutuhan sudah jelas (Test B: P2)
        if "budget" in mnorm and s["needs"]:
            return do_offer(s, catalog, "Baik, Kak, tidak masalah. ", "OFFER")
        # Jika sudah pernah menawarkan produk dan pelanggan bingung/ragu memilih
        if s["offered_products"] and s["fsm_stage"] == "OFFERED" and any(w in mnorm for w in ("bingung", "pusing", "kurang paham", "kurang ngerti")):
            s["fsm_stage"] = "NARROWING_DOWN"
            return render_decision_assistance(offered_prods, s), "UNCERTAIN_HELP"
        if s["needs"] or has_filter(s) or has_rank(s):
            return do_offer(s, catalog, "Baik, Kak. ", "OFFER")
        return decide(s, catalog, "Santai saja, Kak. ")

    # 13. Jawaban atas last_question (slot: need) dengan Persona Penerima (Buat Papa/Mama)
    if lq and lq.get("slot") == "need":
        if persona_t and not needs_t and not _had_persona:
            # Hanya tanya balik jika persona baru pertama kali dikenal di turn ini
            s["persona"] = persona_t
            pname = extract_persona_name(norm_clean)
            if pname:
                s["persona_name"] = pname
            p_name = s.get("persona_name") or ("Papa" if persona_t == "family_elder" else "keluarga")
            s["last_question"] = {"slot": "need"}
            s["fsm_stage"] = "PERSONA_CLARIFY"
            return (f"Oh, untuk {p_name} ya Kak! Biasanya {p_name} lebih sering pakai untuk kebutuhan santai seperti "
                    "nonton/browsing, kerja kantor ngetik dokumen, atau ada kebutuhan khusus seperti olah data/desain Kak?"), "ASK"

    user_type = extract_user_type(mnorm)
    new_info = bool(needs_t or cat_t or budget or vendor or os_ or brand_t or pref_info["prefs"]
                    or pref_info["rel"] or user_type or persona_t)

    # 14. Fallback jika jawaban pertanyaan need tidak dikenal
    if lq and lq.get("slot") in ("need", "dev") and not new_info:
        if is_uncertain(mnorm) or any(has_phrase(mnorm, p) for p in ("terserah", "belum tahu", "bebas")):
            return decide(s, catalog, "Santai saja Kak. ")
        # Jika ada stub NLU
        res = nlu(raw, {"last_question": lq.get("slot"), "category": s["category"], "needs": s["needs"]}) if nlu else None
        if res and res.get("needs"):
            clean_needs = [n for n in res["needs"] if n in NEED_TAGS]
            if clean_needs:
                s["needs"] = clean_needs
                return decide(s, catalog)
        # Jika NLU mengembalikan none / tidak ada NLU
        return do_spread(s, catalog, "Supaya ada gambaran, ini pilihan dari yang termurah sampai tertinggi:")

    if not new_info:
        if toks and set(toks) <= AFFIRM_WORDS | {"kak", "deh", "dong"}:
            return "Ada yang ingin ditanyakan lagi seputar spesifikasinya, Kak?", "DIRECT"
        
        # Level 3: LLM Fallback saat Deterministik Tidak Paham (§17, §20)
        if llm_model:
            chat_hist = s.get("history", [])
            model_to_use = llm_model
            llm_reply = query_llm_fallback(raw, s, chat_history=chat_hist, model=model_to_use)
            if llm_reply:
                s["last_question"] = None
                s["fsm_stage"] = "AWAITING_NEED"
                return llm_reply, "LLM_FALLBACK"

        cat_name = CATEGORY_LABEL[s["category"]] if s.get("category") else "laptop, desktop, atau monitor"
        if s.get("last_route") == "UNKNOWN":
            return (f"Hehe, sepertinya saya masih belum paham maksud Kakak nih. 🙏 "
                    f"Biar pas, Bobby Computer menyediakan {cat_name}. "
                    "Boleh diceritakan sedang butuh komputer untuk apa?"), "UNKNOWN"
        return (f"Maaf, Kak, saya belum menangkap maksudnya. "
                f"Kakak mencari {cat_name}, dan untuk kebutuhan apa?"), "UNKNOWN"

    # 15. Terapkan informasi baru ke State
    prefix = ""
    if any(t in AVAIL_VERBS for t in toks) and (cat_t or brand_t) and not needs_t:
        prefix = "Ada, Kak! "
        
    ctx_changed = False
    if needs_t and set(needs_t) != set(s["needs"]):
        ctx_changed = True
    if cat_t and cat_t != s["category"]:
        ctx_changed = True
        s["asked_slots"] = []
        s["spread_shown"] = False
        s["preferences"] = []
        s["selected_product"] = None
        s["offered_products"] = []
        s["pool"] = []
        s["shown"] = []
        if not brand_t:
            s["constraints"]["brand"] = None
        if not vendor:
            s["constraints"]["vendor"] = None
        if not os_:
            s["constraints"]["os"] = None
        if not budget:
            s["constraints"]["budget_max"] = None
            s["constraints"]["budget_min"] = None
            s["constraints"]["budget_target"] = None
            s["constraints"]["budget_max_strict"] = False
            s["constraints"]["budget_min_strict"] = False
        if not needs_t:
            s["needs"] = []
    if cat_t == "monitor" and not needs_t and s["category"] != "monitor":
        s["needs"] = []
        ctx_changed = True
    if ctx_changed:
        s["preferences"] = []
        s["selected_product"] = None
        
    if needs_t:
        s["needs"] = needs_t
    if cat_t:
        s["category"] = cat_t
    if persona_t:
        s["persona"] = persona_t
        pname = extract_persona_name(norm_clean)
        if pname:
            s["persona_name"] = pname
    if user_type:
        s["user_type"] = user_type
    if budget:
        apply_budget(s, budget)
        s["hide_price"] = False
    if vendor:
        s["constraints"]["vendor"] = vendor
    if os_:
        s["constraints"]["os"] = os_
    if brand_t:
        s["constraints"]["brand"] = brand_t
    if pref_info["prefs"]:
        apply_prefs(s, pref_info["prefs"])
    if "price" in attrs:
        s["hide_price"] = False
        
    if is_ambiguous_dev(mnorm, needs_t) and "need" not in s["asked_slots"]:
        s["asked_slots"].append("need")
        s["last_question"] = {"slot": "dev"}
        return (f"Kira-kira {CATEGORY_NOUN_NYA[s['category']]} untuk development jenis apa, Kak? "
                "Misalnya untuk web, aplikasi Android, atau AI development."), "ASK"
                
    return decide(s, catalog, prefix)

def step(state: dict, user_text: str, catalog: Catalog, nlu=None, llm_model: str | None = None) -> tuple[dict, str, str]:
    """
    Fungsi inti murni (§26.1):
    step(state, user_text, catalog, nlu, llm_model) -> (new_state, reply, route)
    """
    s = copy.deepcopy(state)
    s["_current_raw"] = user_text or ""
    lq = s["last_question"]
    s["last_question"] = None
    
    norm = normalize(user_text)
    if not norm:
        return s, "Boleh diketik dulu pertanyaannya Kak?", "EMPTY_INPUT"
        
    reply, route = route_message(s, user_text or "", norm, lq, catalog, nlu, llm_model=llm_model)
    
    if not validate_reply(reply, catalog, s):
        fallback = "Mohon maaf, sistem kami sedang memvalidasi data katalog. Boleh diulang pertanyaannya, Kak?"
        return s, fallback, "VALIDATION_FALLBACK"
        
    s["last_route"] = route
    hist = s.setdefault("history", [])
    hist.append(("user", user_text))
    hist.append(("assistant", reply))
    if len(hist) > 8:
        s["history"] = hist[-8:]
    return s, reply, route
