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
