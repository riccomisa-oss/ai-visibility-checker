import pytest
from unittest.mock import patch, MagicMock
from checker.platforms.gemini import query


def test_query_returns_ok_with_api_key(monkeypatch):
    """API 키 있을 때 응답 반환"""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.text = "분당 리꼬 피자가 맛있어요."

    with patch("checker.platforms.gemini.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = query("분당 미금역 근처 화덕피자 어디가 좋아?")

    assert result["status"] == "ok"
    assert result["response"] == "분당 리꼬 피자가 맛있어요."


def test_query_skipped_without_api_key(monkeypatch):
    """API 키 없을 때 skipped 반환"""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    result = query("분당 미금역 근처 화덕피자 어디가 좋아?")

    assert result["status"] == "skipped"
    assert result["response"] is None


def test_query_returns_error_on_exception(monkeypatch):
    """API 호출 실패 시 error 반환"""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    with patch("checker.platforms.gemini.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Quota exceeded")
        mock_client_class.return_value = mock_client

        result = query("분당 미금역 근처 화덕피자 어디가 좋아?")

    assert result["status"] == "error"
    assert "Quota exceeded" in result["error"]
