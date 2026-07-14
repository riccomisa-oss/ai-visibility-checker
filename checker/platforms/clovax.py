from __future__ import annotations
import os
import requests


def query(prompt: str) -> dict:
    """HyperCLOVA X에 질문을 던져 응답을 반환한다.
    CLOVAX_API_KEY 미설정 시 자동 skipped 처리.
    API 키는 네이버 클라우드 플랫폼 CLOVA Studio에서 발급.

    HCX-003은 웹검색 그라운딩이 없는 순수 생성 모델이라 인용 출처가 없다
    (citations는 항상 빈 리스트). 다른 어댑터와 반환 스키마를 맞추기 위해 넣어둔다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None,
         "citations": list[str], "error"?: str}
    """
    api_key = os.environ.get("CLOVAX_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None, "citations": []}

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
        return {"status": "ok", "response": text, "citations": []}
    except Exception as e:
        return {"status": "error", "response": None, "citations": [], "error": str(e)}
