from __future__ import annotations
import os
import time
import google.genai as genai
from google.genai import types


def query(prompt: str) -> dict:
    """Google Gemini 2.5 Flash(구글 검색 그라운딩)에 질문을 던져 응답을 반환한다.
    rate limit 대비 최대 3회 재시도(10초 간격).

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None, "error"?: str}
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None}

    client = genai.Client(api_key=api_key)
    last_err = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            return {"status": "ok", "response": response.text}
        except Exception as e:
            last_err = str(e)
            if attempt < 2:
                time.sleep(10)  # rate limit 회피 후 재시도
    return {"status": "error", "response": None, "error": last_err}
