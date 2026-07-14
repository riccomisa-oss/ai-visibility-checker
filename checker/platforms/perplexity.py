from __future__ import annotations
import os
import requests


def query(prompt: str) -> dict:
    """Perplexity sonar 모델에 질문을 던져 응답과 인용 출처를 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None,
         "citations": list[str], "error"?: str}
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None, "citations": []}

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt}],
        }
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        # sonar는 인용을 최상위 citations(문자열 URL 배열)로 준다.
        # 최근 응답에는 search_results(제목·URL 객체 배열)도 함께 온다.
        citations = [c for c in (data.get("citations") or []) if isinstance(c, str)]
        if not citations:
            citations = [
                r.get("url")
                for r in (data.get("search_results") or [])
                if isinstance(r, dict) and r.get("url")
            ]
        return {"status": "ok", "response": text, "citations": citations}
    except Exception as e:
        return {"status": "error", "response": None, "citations": [], "error": str(e)}
