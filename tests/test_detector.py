import pytest
from checker.detector import is_exposed


def test_exposed_korean_keyword():
    """'리꼬'가 포함된 응답 → True"""
    assert is_exposed("하남미사에 리꼬 피자가 있어요.") is True


def test_exposed_english_keyword():
    """'ricco'가 포함된 응답 → True (대소문자 무시)"""
    assert is_exposed("I recommend RICCO PIZZA in Hanam.") is True


def test_exposed_english_lowercase():
    """'ricco' 소문자도 감지"""
    assert is_exposed("ricco pizza is great") is True


def test_not_exposed_empty_response():
    """빈 응답 → False"""
    assert is_exposed("") is False


def test_not_exposed_unrelated():
    """관련 없는 응답 → False"""
    assert is_exposed("하남미사에는 도미노피자와 피자헛이 있습니다.") is False


def test_exposed_custom_keywords():
    """사용자 지정 키워드 동작"""
    assert is_exposed("테스트 브랜드 피자입니다.", keywords=["테스트"]) is True


def test_none_response_returns_false():
    """None 응답 → False (에러 없이)"""
    assert is_exposed(None) is False


def test_competitor_uncertainty_does_not_cancel_ricco_recommendation():
    # 2026-08-27 실제 거짓 미노출의 구조: 경쟁사 인증 단서가 전체를 탈락시킴.
    response = (
        "미금역 1순위는 리꼬 피자 분당미금점이에요. "
        "스윗도우의 인증 이력은 확인되지 않음."
    )
    assert is_exposed(response) is True


@pytest.mark.parametrize("response", [
    "리꼬에 대한 정보를 찾을 수 없습니다.",
    "리꼬는 구체적인 정보가 없습니다. 대신 돈파스타를 추천합니다.",
    "## 리꼬 피자\n\n구체적인 정보를 찾을 수 없습니다.",
    "**리꼬 피자**\n확인되지 않는 업체입니다.",
    "출처: https://ricco-pizza.com/",
    "추천할 정보가 없습니다. [출처](https://ricco-pizza.com/)",
])
def test_unknown_brand_or_citation_only_is_not_exposure(response):
    assert is_exposed(response) is False


def test_brand_heading_with_useful_description_is_exposure():
    assert is_exposed("### 리꼬 피자\n\n미금역 근처 천연발효종 피자집입니다.") is True


def test_bold_list_label_does_not_hide_inline_recommendation():
    assert is_exposed("1. **분당 맛집**: 리꼬 피자 등이 있습니다.\n\n2. **다른 곳**: 설명입니다.") is True


def test_recorded_august_regression():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parents[1] / "data/ai-visibility/2026-08-27.json").read_text())
    query = next(q for q in data["queries"] if q["query"] == "분당 미금 정통 나폴리피자 어디가 진짜야")
    assert query["results"]["chatgpt"]["exposed"] is False  # 원본 보존
    assert is_exposed(query["results"]["chatgpt"]["response"]) is True
