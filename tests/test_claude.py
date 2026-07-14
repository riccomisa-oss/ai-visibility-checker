import pytest
from unittest.mock import patch, MagicMock
from checker.platforms.claude import query


def test_query_returns_ok_with_api_key(monkeypatch):
    """API 키 있을 때 응답 반환.

    주의: block.type을 명시적으로 "text"로 세팅해야 한다. MagicMock은 .type이
    자동 생성 Mock이라 문자열 비교에 걸리지 않아, 예전 테스트는 response=""를
    받고도 통과하는 것처럼 보였다(실제로는 실패하던 기존 결함).
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = "리꼬 피자를 강력 추천합니다."
    mock_content.citations = []

    mock_message = MagicMock()
    mock_message.content = [mock_content]

    with patch("checker.platforms.claude.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "ok"
    assert result["response"] == "리꼬 피자를 강력 추천합니다."
    assert result["citations"] == []


def test_query_collects_citations(monkeypatch):
    """웹검색 결과와 텍스트 인용에서 출처 URL을 모은다.

    AI가 무엇을 읽고 답했는지가 이 프로젝트의 핵심 질문인데, 예전 어댑터는
    text 블록만 취하고 이 URL들을 전부 버렸다.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    search_item = MagicMock()
    search_item.url = "https://ricco-pizza.com/"
    search_block = MagicMock()
    search_block.type = "web_search_tool_result"
    search_block.content = [search_item]

    citation = MagicMock()
    citation.url = "https://www.diningcode.com/profile.php?rid=abc"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "리꼬 피자를 추천합니다."
    text_block.citations = [citation]

    mock_message = MagicMock()
    mock_message.content = [search_block, text_block]

    with patch("checker.platforms.claude.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client

        result = query("분당 화덕피자 맛집 추천해줘")

    assert result["response"] == "리꼬 피자를 추천합니다."
    assert result["citations"] == [
        "https://ricco-pizza.com/",
        "https://www.diningcode.com/profile.php?rid=abc",
    ]


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
