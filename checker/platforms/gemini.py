from __future__ import annotations
import os
import google.genai as genai


def query(prompt: str) -> dict:
    """Google Gemini 2.5 Flash에 질문을 던져 응답을 반환한다.
    무료 티어 사용 (하루 1,500 요청 무료).

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None, "error"?: str}
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None}

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text
        return {"status": "ok", "response": text}
    except Exception as e:
        return {"status": "error", "response": None, "error": str(e)}
