from __future__ import annotations
import os
import requests


def query(prompt: str) -> dict:
    """Perplexity sonar 모델에 질문을 던져 응답을 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None, "error"?: str}
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None}

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
        text = response.json()["choices"][0]["message"]["content"]
        return {"status": "ok", "response": text}
    except Exception as e:
        return {"status": "error", "response": None, "error": str(e)}
