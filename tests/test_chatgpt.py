import pytest
from unittest.mock import patch, MagicMock

from checker.platforms import chatgpt
from checker.platforms.chatgpt import query


@pytest.fixture(autouse=True)
def _reset_resolved_model():
    """모델 해결 캐시는 모듈 전역이라 테스트 간에 새어나간다. 매번 초기화."""
    chatgpt._resolved_model = None
    yield
    chatgpt._resolved_model = None


def _text_part(text, urls=()):
    """Responses API의 content[type=output_text] 조각을 흉내낸다.

    MagicMock은 .type이 자동 생성 Mock이라 문자열 비교에 안 걸린다 —
    claude 어댑터 테스트가 예전에 이걸로 빈 응답을 통과시켰다. 명시 세팅 필수.
    """
    part = MagicMock()
    part.type = "output_text"
    part.text = text
    anns = []
    for u in urls:
        ann = MagicMock()
        ann.type = "url_citation"
        ann.url = u
        anns.append(ann)
    part.annotations = anns
    return part


def _message_item(parts):
    item = MagicMock()
    item.type = "message"
    item.content = parts
    return item


def _search_call_item():
    item = MagicMock()
    item.type = "web_search_call"
    return item


def _response(output, output_text=None):
    r = MagicMock()
    r.output = output
    r.output_text = output_text
    return r


def test_query_returns_ok_and_parses_citations(monkeypatch):
    """본문·인용 URL·검색수행 여부를 Responses API 응답에서 뽑는다."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    resp = _response(
        [
            _search_call_item(),
            _message_item([
                _text_part(
                    "리꼬 피자를 추천합니다.",
                    urls=["https://ricco-pizza.com/", "https://maps.google.com/x"],
                )
            ]),
        ],
        output_text="리꼬 피자를 추천합니다.",
    )

    with patch("checker.platforms.chatgpt.OpenAI") as mock_class:
        client = MagicMock()
        client.responses.create.return_value = resp
        mock_class.return_value = client

        result = query("하남미사 피자 맛집 추천해줘")

        kwargs = client.responses.create.call_args.kwargs

    assert result["status"] == "ok"
    assert result["response"] == "리꼬 피자를 추천합니다."
    assert result["citations"] == [
        "https://ricco-pizza.com/",
        "https://maps.google.com/x",
    ]
    assert result["searched"] is True
    assert result["model"] == "gpt-5.6-luna"
    # GA 타입(web_search)이어야 한다. web_search_preview는 레거시.
    assert kwargs["tools"][0]["type"] == "web_search"
    # 로컬 질의 측정이라 지역을 한국으로 고정해야 한다.
    assert kwargs["tools"][0]["user_location"]["country"] == "KR"


def test_searched_false_when_model_skips_search(monkeypatch):
    """web_search_call이 없으면 '검색 안 함' — 인용 0건과 구분해 기록해야 한다."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    resp = _response(
        [_message_item([_text_part("잘 모르겠습니다.")])],
        output_text="잘 모르겠습니다.",
    )

    with patch("checker.platforms.chatgpt.OpenAI") as mock_class:
        client = MagicMock()
        client.responses.create.return_value = resp
        mock_class.return_value = client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "ok"
    assert result["searched"] is False
    assert result["citations"] == []


def test_falls_back_to_next_model_on_model_error(monkeypatch):
    """모델 미지원이면 다음 모델로 강등한다(luna → gpt-5.6).

    8/26 측정이 통째로 날아간 원인이 모델 폐기였다. 폴백이 없으면 다음 폐기 때
    똑같이 한 달치 측정을 잃는다.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    ok = _response([_message_item([_text_part("답변")])], output_text="답변")

    with patch("checker.platforms.chatgpt.OpenAI") as mock_class:
        client = MagicMock()
        client.responses.create.side_effect = [
            Exception("Error code: 404 - model_not_found"),
            ok,
        ]
        mock_class.return_value = client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "ok"
    assert result["model"] == "gpt-5.6"


def test_does_not_fall_back_on_transient_error(monkeypatch):
    """레이트리밋·타임아웃으로 강등하면 조용히 다른 모델로 재는 셈이라 시계열이 오염된다."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("checker.platforms.chatgpt.OpenAI") as mock_class:
        client = MagicMock()
        client.responses.create.side_effect = Exception("429 rate_limit_exceeded")
        mock_class.return_value = client

        result = query("하남미사 피자 맛집 추천해줘")

        assert client.responses.create.call_count == 1

    assert result["status"] == "error"
    assert "rate_limit_exceeded" in result["error"]


def test_resolved_model_is_reused(monkeypatch):
    """한 번 해결된 모델은 질의마다 다시 탐색하지 않는다(30질의 × 실패 호출 방지)."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    ok = _response([_message_item([_text_part("답변")])], output_text="답변")

    with patch("checker.platforms.chatgpt.OpenAI") as mock_class:
        client = MagicMock()
        client.responses.create.side_effect = [
            Exception("Error code: 404 - model_not_found"),
            ok,
            ok,
        ]
        mock_class.return_value = client

        query("질의1")
        query("질의2")

        models = [c.kwargs["model"] for c in client.responses.create.call_args_list]

    assert models == ["gpt-5.6-luna", "gpt-5.6", "gpt-5.6"]


def test_query_skipped_without_api_key(monkeypatch):
    """API 키 없을 때 skipped 반환"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "skipped"
    assert result["response"] is None


def test_query_returns_error_on_exception(monkeypatch):
    """API 호출 실패 시 error 반환"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("checker.platforms.chatgpt.OpenAI") as mock_class:
        client = MagicMock()
        client.responses.create.side_effect = Exception("API Error")
        mock_class.return_value = client

        result = query("하남미사 피자 맛집 추천해줘")

    assert result["status"] == "error"
    assert result["response"] is None
    assert "API Error" in result["error"]
