from __future__ import annotations
import re


DETECTOR_VERSION = "2.0-scoped-negatives"


def _contexts(text: str) -> list[str]:
    # 인용 URL에만 브랜드가 있는 경우는 본문 노출이 아니다.
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    paragraphs = re.split(r"\n\s*\n", text)
    contexts: list[str] = []
    heading = ""
    for paragraph in paragraphs:
        lines = paragraph.strip().splitlines()
        if not lines:
            continue
        # 브랜드명만 있는 제목은 다음 설명과 함께 읽는다. 제목 뒤에
        # '정보가 없다'고 쓰인 응답을 긍정 노출로 만들지 않는다.
        if re.fullmatch(r"\s*(?:#{1,6}\s+.+|(?:\d+[.)]\s*)?\*\*[^*]+\*\*)\s*", lines[0]):
            if len(lines) == 1 and not re.search(r"추천|1순위|합니다|이에요|입니다", lines[0]):
                heading = lines[0]
                continue
            if len(lines) > 1:
                contexts.append(paragraph)
                heading = ""
                continue
        if heading:
            contexts.append(heading + " " + paragraph)
            heading = ""
        else:
            contexts.extend(re.split(r"(?<=[.!?。！？])\s+|\n+", paragraph))
    return contexts


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

    # 부정 표현은 브랜드가 실제로 등장한 문맥 안에서만 적용한다.
    # 경쟁사 인증 여부에 대한 단서가 리꼬의 명백한 추천을 취소하면 안 된다.
    negatives = [
        "정보가 없", "정보는 없", "정보를 찾을 수 없", "찾을 수 없",
        "알 수 없", "데이터베이스에", "구체적인 정보가 없", "확인되지 않",
        "정보가 부족", "잘 모르", "알지 못", "정보가 제한", "정보가 충분하지 않",
    ]
    for context in _contexts(response_text):
        if any(kw.lower() in context.lower() for kw in keywords):
            if not any(neg in context for neg in negatives):
                return True
    return False
