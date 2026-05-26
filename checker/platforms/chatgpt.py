from __future__ import annotations
import os
from openai import OpenAI


def query(prompt: str) -> dict:
    """OpenAI GPT-4o-mini에 질문을 던져 응답을 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None, "error"?: str}
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None}

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            timeout=30,
        )
        text = response.choices[0].message.content
        return {"status": "ok", "response": text}
    except Exception as e:
        return {"status": "error", "response": None, "error": str(e)}
