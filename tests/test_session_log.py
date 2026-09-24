from session_log import SessionLog


def test_record_appends_json_lines(tmp_path):
    log = SessionLog(str(tmp_path / "nested" / "log.jsonl"))
    log.record(mode="Coach", hints_used=2)
    log.record(mode="Solve", hints_used=None)
    entries = log.read()
    assert [e["mode"] for e in entries] == ["Coach", "Solve"]
    assert "ts" in entries[0]


def test_read_missing_file_is_empty(tmp_path):
    assert SessionLog(str(tmp_path / "none.jsonl")).read() == []
