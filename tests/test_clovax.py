import pytest
from unittest.mock import patch, MagicMock
from checker.platforms.clovax import query


def test_query_returns_ok_with_api_key(monkeypatch):
    """API 키 있을 때 응답 반환"""
    monkeypatch.setenv("CLOVAX_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {"message": {"content": "리꼬 피자 하남미사점을 추천드립니다."}}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("checker.platforms.clovax.requests.post", return_value=mock_response):
        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "ok"
    assert result["response"] == "리꼬 피자 하남미사점을 추천드립니다."


def test_query_skipped_without_api_key(monkeypatch):
    """API 키 없을 때 skipped 반환"""
    monkeypatch.delenv("CLOVAX_API_KEY", raising=False)

    result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "skipped"
    assert result["response"] is None


def test_query_returns_error_on_exception(monkeypatch):
    """API 호출 실패 시 error 반환"""
    monkeypatch.setenv("CLOVAX_API_KEY", "test-key")

    with patch("checker.platforms.clovax.requests.post", side_effect=Exception("Connection error")):
        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "error"
    assert "Connection error" in result["error"]
