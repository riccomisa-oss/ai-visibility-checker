import pytest
from unittest.mock import patch, MagicMock
from checker.platforms.chatgpt import query


def test_query_returns_ok_with_api_key(monkeypatch):
    """API 키 있을 때 응답 반환"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "리꼬 피자를 추천합니다."

    with patch("checker.platforms.chatgpt.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "ok"
    assert result["response"] == "리꼬 피자를 추천합니다."


def test_query_skipped_without_api_key(monkeypatch):
    """API 키 없을 때 skipped 반환"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "skipped"
    assert result["response"] is None


def test_query_returns_error_on_exception(monkeypatch):
    """API 호출 실패 시 error 반환"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("checker.platforms.chatgpt.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "error"
    assert result["response"] is None
    assert "API Error" in result["error"]
