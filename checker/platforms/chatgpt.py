from __future__ import annotations
import os
from openai import OpenAI


# 2026-07-23에 gpt-4o-mini-search-preview / gpt-4o-search-preview가 셧다운됐다
# (2026-04-22 폐기 공지). 8/26 측정이 29질의 전부 404 model_not_found로 죽어
# ChatGPT 축이 통째로 공백이 된 게 그 결과다. Chat Completions에도 후속
# (gpt-5-search-api)이 있지만 OpenAI가 "기존 통합을 보존할 때만" 쓰라고 못박았고,
# 어차피 고쳐야 하는 김에 권장 경로인 Responses API + web_search 도구로 옮긴다.
#
# 모델 선택은 "폐기 문서가 지정한 범용 대체(gpt-5.6-terra)"가 아니라 **제품 근사**
# 기준이다. 이 도구가 재는 건 "손님이 ChatGPT에 물었을 때 리꼬가 나오나"이고,
# 2026-08-06부터 무료 ChatGPT의 기본 모델이 gpt-5.6-luna다(=최대 사용자군).
# luna의 web_search 지원은 모델 페이지에 명시돼 있으나 가이드의 지원 모델 표에는
# 없어서, 모델 관련 에러면 아래 순서로 자동 강등한다.
MODEL_CHAIN = ("gpt-5.6-luna", "gpt-5.6", "gpt-5.6-sol")

# 검색 결과의 지역 편향을 한국으로 고정한다. 미설정 시 러너 IP(=GitHub Actions
# 미국 리전)를 따라 결과가 달라져 "하남미사 화덕피자" 같은 로컬 질의 측정이 왜곡된다.
USER_LOCATION = {"type": "approximate", "country": "KR"}

# 한 번 실패한 모델을 30개 질의마다 다시 때리면 시간·비용만 버린다.
# 프로세스 안에서 한 번 해결된 모델을 재사용한다.
_resolved_model: str | None = None


def _is_model_error(exc: Exception) -> bool:
    """모델 자체가 불가한 에러인가(=다음 모델로 강등할 사유인가).

    레이트리밋·타임아웃·일시 장애로 강등해버리면 조용히 다른 모델로 측정하게 되고,
    그러면 시계열이 오염된다. 모델/도구 미지원 신호일 때만 True.
    """
    msg = str(exc).lower()
    if "model_not_found" in msg or "does not exist" in msg or "deprecated" in msg:
        return True
    if "unsupported" in msg and ("model" in msg or "tool" in msg):
        return True
    if "web_search" in msg and ("not supported" in msg or "unsupported" in msg):
        return True
    return False


def _parse(response) -> tuple[str | None, list[str], bool]:
    """Responses API 응답에서 (본문, 인용 URL, 검색수행여부)를 뽑는다.

    output 배열에는 web_search_call(검색 호출 메타)과 message(실제 답변)가 섞여 온다.
    인용은 message → content[type=output_text] → annotations[type=url_citation].url.
    content[0] 같은 하드코딩은 하지 않는다 — 아이템 순서·개수는 보장되지 않는다.
    """
    citations: list[str] = []
    searched = False
    texts: list[str] = []

    for item in (getattr(response, "output", None) or []):
        itype = getattr(item, "type", None)
        if itype == "web_search_call":
            searched = True
            continue
        if itype != "message":
            continue
        for part in (getattr(item, "content", None) or []):
            if getattr(part, "type", None) != "output_text":
                continue
            text = getattr(part, "text", None)
            if text:
                texts.append(text)
            for ann in (getattr(part, "annotations", None) or []):
                if getattr(ann, "type", None) != "url_citation":
                    continue
                url = getattr(ann, "url", None)
                if url:
                    citations.append(url)

    # 편의 속성을 우선 쓰되, 없으면 직접 모은 텍스트로 대체한다.
    body = getattr(response, "output_text", None) or ("\n".join(texts) or None)
    return body, citations, searched


def query(prompt: str) -> dict:
    """OpenAI(웹검색)에 질문을 던져 응답과 인용 출처를 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None,
         "citations": list[str], "searched": bool, "model": str, "error"?: str}

    `searched`가 중요하다: web_search는 모델이 검색 여부를 스스로 판단하므로
    "검색을 안 해서 인용 0건"과 "검색했는데 리꼬가 안 잡힘"이 겉으로 같아 보인다.
    둘을 안 나누면 인용 지형 통계가 조용히 오염된다.
    """
    global _resolved_model

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None, "citations": []}

    client = OpenAI(api_key=api_key)

    # 이미 해결된 모델이 있으면 그것만, 없으면 체인을 순서대로 시도한다.
    candidates = (_resolved_model,) if _resolved_model else MODEL_CHAIN
    last_error: Exception | None = None

    for model in candidates:
        try:
            response = client.responses.create(
                model=model,
                tools=[{"type": "web_search", "user_location": USER_LOCATION}],
                input=prompt,
                timeout=120,
            )
        except Exception as e:  # noqa: BLE001 — 측정 1건 실패가 전체를 죽이면 안 된다
            last_error = e
            if _is_model_error(e) and not _resolved_model:
                continue  # 다음 모델로 강등
            break

        _resolved_model = model
        body, citations, searched = _parse(response)
        return {
            "status": "ok",
            "response": body,
            "citations": citations,
            "searched": searched,
            "model": model,
        }

    return {
        "status": "error",
        "response": None,
        "citations": [],
        "error": str(last_error),
    }
