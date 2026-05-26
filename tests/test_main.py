import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from checker.main import run


@pytest.fixture
def mock_all_platforms():
    """모든 플랫폼 모듈을 mock으로 대체"""
    ok_response = {"status": "ok", "response": "리꼬 피자를 추천합니다."}
    with patch("checker.main.chatgpt.query", return_value=ok_response), \
         patch("checker.main.perplexity.query", return_value=ok_response), \
         patch("checker.main.claude.query", return_value=ok_response), \
         patch("checker.main.gemini.query", return_value=ok_response), \
         patch("checker.main.clovax.query", return_value=ok_response):
        yield


def test_run_creates_json_file(tmp_path, mock_all_platforms):
    """run() 실행 시 JSON 파일이 생성됨"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    json_files = list(tmp_path.glob("*.json"))
    # index.json + 날짜.json
    date_files = [f for f in json_files if f.name != "index.json"]
    assert len(date_files) == 1


def test_run_json_has_correct_structure(tmp_path, mock_all_platforms):
    """생성된 JSON이 올바른 구조를 가짐"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    assert "date" in data
    assert "queries" in data
    assert "summary" in data
    assert len(data["queries"]) == 8  # QUERIES 목록 8개
    assert "chatgpt" in data["summary"]
    assert "perplexity" in data["summary"]
    assert "claude" in data["summary"]
    assert "gemini" in data["summary"]
    assert "clovax" in data["summary"]


def test_run_detects_exposure(tmp_path, mock_all_platforms):
    """'리꼬'가 포함된 응답 → exposed=True"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    first_query = data["queries"][0]
    assert first_query["results"]["chatgpt"]["exposed"] is True


def test_run_updates_index_json(tmp_path, mock_all_platforms):
    """run() 실행 시 index.json이 업데이트됨"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    index_file = tmp_path / "index.json"
    assert index_file.exists()
    dates = json.loads(index_file.read_text())
    assert len(dates) == 1


def test_run_handles_skipped_platform(tmp_path):
    """플랫폼 skipped 시 summary에 skipped=True 기록"""
    skipped = {"status": "skipped", "response": None}
    ok = {"status": "ok", "response": "리꼬 피자 추천"}

    with patch("checker.main.chatgpt.query", return_value=skipped), \
         patch("checker.main.perplexity.query", return_value=ok), \
         patch("checker.main.claude.query", return_value=ok), \
         patch("checker.main.gemini.query", return_value=ok), \
         patch("checker.main.clovax.query", return_value=skipped), \
         patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    assert data["summary"]["chatgpt"]["skipped"] is True
    assert data["summary"]["clovax"]["skipped"] is True
    assert data["summary"]["perplexity"]["skipped"] is False
