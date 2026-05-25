from __future__ import annotations


def is_exposed(response_text: str | None, keywords: list[str] | None = None) -> bool:
    """AI 응답 텍스트에 타겟 키워드가 포함됐는지 판정한다.

    Args:
        response_text: AI 응답 원문. None이면 False 반환.
        keywords: 검색할 키워드 목록. None이면 기본값(["리꼬", "ricco"]) 사용.

    Returns:
        키워드가 하나라도 포함되면 True, 아니면 False.
    """
    if not response_text:
        return False

    if keywords is None:
        keywords = ["리꼬", "ricco"]

    text_lower = response_text.lower()
    return any(kw.lower() in text_lower for kw in keywords)
