from __future__ import annotations
import os
import time
import google.genai as genai
from google.genai import types


def _grounding_sources(response) -> list[str]:
    """Gemini 그라운딩 청크에서 출처 도메인을 뽑는다.

    주의: grounding_chunks[].web.uri 는 vertexaisearch.cloud.google.com 리다이렉터라
    실제 출처 도메인이 URL에 안 드러난다. 실제 도메인은 web.title 에 담겨 온다
    (예: title="ricco-pizza.com"). 그래서 title을 우선 쓰고 없을 때만 uri로 폴백한다.
    """
    sources: list[str] = []
    for cand in (getattr(response, "candidates", None) or []):
        gm = getattr(cand, "grounding_metadata", None)
        for chunk in (getattr(gm, "grounding_chunks", None) or []):
            web = getattr(chunk, "web", None)
            if not web:
                continue
            ref = getattr(web, "title", None) or getattr(web, "uri", None)
            if ref:
                sources.append(ref)
    return sources


def query(prompt: str) -> dict:
    """Google Gemini 2.5 Flash(구글 검색 그라운딩)에 질문을 던져 응답을 반환한다.
    rate limit·503 대비 최대 4회 시도, 지수 백오프(10→20→40초).

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None,
         "citations": list[str], "error"?: str}
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None, "citations": []}

    client = genai.Client(api_key=api_key)
    last_err = None
    max_attempts = 4
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            return {
                "status": "ok",
                "response": response.text,
                "citations": _grounding_sources(response),
            }
        except Exception as e:
            last_err = str(e)
            if attempt < max_attempts - 1:
                # 429(rate limit)·503(overloaded) 회피: 10, 20, 40초 지수 백오프
                time.sleep(10 * (2 ** attempt))
    return {"status": "error", "response": None, "citations": [], "error": last_err}
