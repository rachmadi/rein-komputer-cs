# -*- coding: utf-8 -*-
import os
import json
import pytest
from telegram_bot import record_feedback, get_feedback_keyboard
from scripts.audit_problem_sessions import audit_sessions, FEEDBACK_FILE

def test_feedback_logging_and_anonymization(tmp_path):
    test_sid = "tg_12345678"
    test_uid = 99887766

    record_feedback(session_id=test_sid, user_id=test_uid, rating="dislike", note="turn_1")

    assert os.path.exists(FEEDBACK_FILE)
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) > 0

    last_record = json.loads(lines[-1])
    assert last_record["rating"] == "dislike"
    assert str(test_uid) not in last_record["anon_user_id"]
    assert len(last_record["anon_user_id"]) == 12  # hash terpotong 12 digit

def test_feedback_keyboard_structure():
    kb = get_feedback_keyboard("turn_abc")
    assert kb is not None
    assert len(kb.inline_keyboard) == 1
    assert len(kb.inline_keyboard[0]) == 2
    assert "fb:like:turn_abc" in kb.inline_keyboard[0][0].callback_data
    assert "fb:dislike:turn_abc" in kb.inline_keyboard[0][1].callback_data

def test_audit_problem_sessions_executes():
    report = audit_sessions()
    assert report is not None
    assert "summary" in report
    assert "sessions" in report
    assert "counts_by_category" in report["summary"]
