from __future__ import annotations
import os
import anthropic


def query(prompt: str) -> dict:
    """Claude Haiku에 질문을 던져 응답과 인용 출처를 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None,
         "citations": list[str], "error"?: str}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None, "citations": []}

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,
            }],
        )
        # 웹검색 사용 시 content가 여러 블록으로 온다.
        #   web_search_tool_result : 검색이 실제로 가져온 페이지들
        #   text (.citations)      : 최종 답변이 근거로 실제 인용한 페이지들
        # 예전엔 text 블록만 취하고 두 출처를 다 버렸다 — AI가 무엇을 읽고
        # 답했는지가 이 프로젝트의 핵심 질문인데 그 데이터를 매번 폐기한 셈이다.
        texts: list[str] = []
        citations: list[str] = []
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                texts.append(block.text)
                for c in (getattr(block, "citations", None) or []):
                    url = getattr(c, "url", None)
                    if url:
                        citations.append(url)
            elif btype == "web_search_tool_result":
                for item in (getattr(block, "content", None) or []):
                    url = getattr(item, "url", None)
                    if url:
                        citations.append(url)

        return {"status": "ok", "response": "".join(texts), "citations": citations}
    except Exception as e:
        return {"status": "error", "response": None, "citations": [], "error": str(e)}
