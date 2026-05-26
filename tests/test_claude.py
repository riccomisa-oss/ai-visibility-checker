import pytest
from unittest.mock import patch, MagicMock
from checker.platforms.claude import query


def test_query_returns_ok_with_api_key(monkeypatch):
    """API 키 있을 때 응답 반환"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_content = MagicMock()
    mock_content.text = "리꼬 피자를 강력 추천합니다."

    mock_message = MagicMock()
    mock_message.content = [mock_content]

    with patch("checker.platforms.claude.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "ok"
    assert result["response"] == "리꼬 피자를 강력 추천합니다."


def test_query_skipped_without_api_key(monkeypatch):
    """API 키 없을 때 skipped 반환"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "skipped"
    assert result["response"] is None


def test_query_returns_error_on_exception(monkeypatch):
    """API 호출 실패 시 error 반환"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("checker.platforms.claude.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Rate limit")
        mock_client_class.return_value = mock_client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "error"
    assert "Rate limit" in result["error"]
