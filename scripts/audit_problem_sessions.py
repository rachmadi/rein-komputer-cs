# -*- coding: utf-8 -*-
"""
Skrip Audit Sesi Bermasalah Bobby Computer
Mendeteksi dan merangkum:
1. Sesi dengan tanggapan negatif (👎).
2. Sesi dengan daftar produk yang ditawarkan berulang kali.
3. Sesi dengan klaim centang ✅ tanpa kebutuhan/syarat teknis yang diperiksa.
4. Sesi dengan kata sanggahan/keberatan dari pelanggan ("kok", "bukan", dll).
"""
import os
import sys
import json
import re
from datetime import datetime
from collections import defaultdict

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CHAT_HISTORY_FILE = "logs/chat_history.jsonl"
FEEDBACK_FILE = "logs/feedback.jsonl"
OUTPUT_REPORT_FILE = "docs/problem_sessions_report.json"

OBJECTION_PATTERN = re.compile(r"\b(kok|bukan|kenapa|loh|lah|salah|ngawur)\b", re.IGNORECASE)

def load_jsonl(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records

def audit_sessions():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Memulai Audit Sesi Percakapan...")
    chat_logs = load_jsonl(CHAT_HISTORY_FILE)
    feedback_logs = load_jsonl(FEEDBACK_FILE)

    print(f"Total log giliran percakapan: {len(chat_logs)}")
    print(f"Total log feedback pelanggan: {len(feedback_logs)}")

    # 1. Kumpulkan feedback negatif per session
    negative_feedback_sessions = set()
    for fb in feedback_logs:
        if fb.get("rating") in ("dislike", "negative"):
            raw_sid = fb.get("raw_session_id") or fb.get("session_id")
            if raw_sid:
                negative_feedback_sessions.add(raw_sid)

    # 2. Kelompokkan giliran per sesi
    sessions = defaultdict(list)
    for log in chat_logs:
        sid = log.get("session_id", "unknown")
        sessions[sid].append(log)

    problem_reports = []
    category_counts = {
        "negative_feedback": 0,
        "repeated_offerings": 0,
        "invalid_checkmark": 0,
        "customer_objection": 0
    }

    for sid, turns in sessions.items():
        issues_in_session = []

        # A. Cek Negative Feedback
        if sid in negative_feedback_sessions:
            category_counts["negative_feedback"] += 1
            issues_in_session.append({
                "category": "negative_feedback",
                "detail": "Pengguna memberikan tombol jempol ke bawah (👎)"
            })

        # Analisis per giliran
        last_offered = None
        for idx, turn in enumerate(turns):
            user_msg = turn.get("user_text", "")
            bot_reply = turn.get("bot_reply", "")
            offered = turn.get("offered_products", [])

            # B. Cek Daftar Berulang
            if offered and last_offered and offered == last_offered and len(offered) > 0:
                # Pastikan giliran ini bukan karena user menanyakan hal sama persis
                category_counts["repeated_offerings"] += 1
                issues_in_session.append({
                    "category": "repeated_offerings",
                    "turn_index": idx,
                    "user_text": user_msg,
                    "offered_products": offered,
                    "detail": f"Daftar produk persis sama berulang dengan giliran sebelumnya: {offered}"
                })
            if offered:
                last_offered = offered

            # C. Cek ✅ Tanpa Kebutuhan Jelas
            # Jika bot memberikan centang ✅ padahal tidak ada profil/kebutuhan atau kebutuhan kosong
            if "✅" in bot_reply:
                route = turn.get("route", "")
                user_low = user_msg.lower().strip()
                # Kategori murni tanpa filter
                is_pure_cat = user_low in ["laptop", "pc", "komputer", "desktop", "printer"]
                is_greeting = any(user_low == g for g in ["halo", "hai", "hi", "p", "permisi"])
                has_no_needs = not turn.get("needs") and (is_pure_cat or is_greeting or route in ("CLARIFY_CATEGORY", "GREETING"))
                if has_no_needs:
                    category_counts["invalid_checkmark"] += 1
                    issues_in_session.append({
                        "category": "invalid_checkmark",
                        "turn_index": idx,
                        "user_text": user_msg,
                        "detail": "Tanda centang (✅) muncul padahal belum ada syarat teknis yang diverifikasi."
                    })

            # D. Cek Kata Keberatan/Sanggahan ("kok", "bukan", dll)
            m_obj = OBJECTION_PATTERN.search(user_msg)
            if m_obj:
                category_counts["customer_objection"] += 1
                issues_in_session.append({
                    "category": "customer_objection",
                    "turn_index": idx,
                    "matched_keyword": m_obj.group(0),
                    "user_text": user_msg,
                    "detail": f"Pelanggan menunjukkan kebingungan/keberatan dengan kata '{m_obj.group(0)}'"
                })

        if issues_in_session:
            problem_reports.append({
                "session_id": sid,
                "turn_count": len(turns),
                "issues": issues_in_session,
                "first_turn_at": turns[0].get("timestamp"),
                "dialog_sample": [
                    {"turn": i, "user": t.get("user_text"), "bot_snippet": (t.get("bot_reply") or "")[:120] + "..."}
                    for i, t in enumerate(turns[:4])
                ]
            })

    # Simpan hasil laporan ke JSON
    os.makedirs(os.path.dirname(OUTPUT_REPORT_FILE), exist_ok=True)
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_sessions_audited": len(sessions),
            "total_problem_sessions": len(problem_reports),
            "counts_by_category": category_counts
        },
        "sessions": problem_reports
    }

    with open(OUTPUT_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print("\n=== RINGKASAN AUDIT SESI BERMASALAH ===")
    print(f"Total Sesi Diaudit        : {len(sessions)}")
    print(f"Total Sesi Bermasalah    : {len(problem_reports)}")
    print("Rincian Masalah:")
    print(f"  - Tanggapan Negatif (👎)   : {category_counts['negative_feedback']}")
    print(f"  - Daftar Produk Berulang   : {category_counts['repeated_offerings']}")
    print(f"  - ✅ Tanpa Kebutuhan        : {category_counts['invalid_checkmark']}")
    print(f"  - Keberatan Pelanggan      : {category_counts['customer_objection']}")
    print(f"\nLaporan lengkap tersimpan di: {OUTPUT_REPORT_FILE}\n")
    return report_data

if __name__ == "__main__":
    audit_sessions()
