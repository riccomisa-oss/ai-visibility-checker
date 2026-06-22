from __future__ import annotations
import os
import anthropic


def query(prompt: str) -> dict:
    """Claude Haiku에 질문을 던져 응답을 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None, "error"?: str}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None}

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
        # 웹검색 사용 시 content가 여러 블록(검색결과+텍스트) → text 블록만 모아 최종 답변 추출
        text = "".join(
            block.text for block in message.content
            if getattr(block, "type", None) == "text"
        )
        return {"status": "ok", "response": text}
    except Exception as e:
        return {"status": "error", "response": None, "error": str(e)}
