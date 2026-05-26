from __future__ import annotations
import os
import requests


def query(prompt: str) -> dict:
    """HyperCLOVA X에 질문을 던져 응답을 반환한다.
    CLOVAX_API_KEY 미설정 시 자동 skipped 처리.
    API 키는 네이버 클라우드 플랫폼 CLOVA Studio에서 발급.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None, "error"?: str}
    """
    api_key = os.environ.get("CLOVAX_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None}

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "maxTokens": 1024,
            "temperature": 0.5,
            "topP": 0.8,
        }
        response = requests.post(
            "https://clovastudio.stream.ntruss.com/v1/chat-completions/HCX-003",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        text = response.json()["result"]["message"]["content"]
        return {"status": "ok", "response": text}
    except Exception as e:
        return {"status": "error", "response": None, "error": str(e)}
