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
    if not any(kw.lower() in text_lower for kw in keywords):
        return False

    # 거짓양성 제거: "리꼬에 대한 정보가 없다"류 답변은 노출로 보지 않는다.
    # (질문에 '리꼬'가 있으면 답변에도 단어가 섞여 들어가므로, 부정 맥락이면 미노출 처리)
    negatives = [
        "정보가 없", "정보는 없", "정보를 찾을 수 없", "찾을 수 없",
        "알 수 없", "데이터베이스에", "구체적인 정보가 없", "확인되지 않",
        "정보가 부족", "잘 모르", "알지 못", "정보가 제한", "정보가 충분하지 않",
    ]
    if any(neg in response_text for neg in negatives):
        return False

    return True
