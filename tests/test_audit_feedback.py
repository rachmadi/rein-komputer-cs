import os
import json
import pytest
import telegram_bot
import scripts.audit_problem_sessions as aps
from telegram_bot import record_feedback, get_feedback_keyboard
from scripts.audit_problem_sessions import audit_sessions

def test_feedback_logging_and_anonymization(tmp_path, monkeypatch):
    test_feedback_file = str(tmp_path / "feedback_test.jsonl")
    monkeypatch.setattr(telegram_bot, "FEEDBACK_LOG_PATH", test_feedback_file)
    monkeypatch.setenv("FEEDBACK_FILE", test_feedback_file)
    monkeypatch.setattr(aps, "FEEDBACK_FILE", test_feedback_file)

    test_sid = "tg_12345678"
    test_uid = 99887766

    record_feedback(session_id=test_sid, user_id=test_uid, rating="dislike", note="turn_1")

    assert os.path.exists(test_feedback_file)
    with open(test_feedback_file, "r", encoding="utf-8") as f:
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

def test_audit_problem_sessions_executes(tmp_path, monkeypatch):
    test_feedback_file = str(tmp_path / "feedback_test.jsonl")
    test_report_file = str(tmp_path / "report_test.json")
    monkeypatch.setattr(aps, "FEEDBACK_FILE", test_feedback_file)
    monkeypatch.setattr(aps, "OUTPUT_REPORT_FILE", test_report_file)

    report = audit_sessions(feedback_file=test_feedback_file, output_file=test_report_file)
    assert report is not None
    assert "summary" in report
    assert "sessions" in report
    assert "counts_by_category" in report["summary"]
    assert os.path.exists(test_report_file)
