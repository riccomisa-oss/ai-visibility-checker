from __future__ import annotations
import os
from openai import OpenAI


def query(prompt: str) -> dict:
    """OpenAI GPT-4o-mini(웹검색)에 질문을 던져 응답과 인용 출처를 반환한다.

    Returns:
        {"status": "ok"|"skipped"|"error", "response": str|None,
         "citations": list[str], "error"?: str}
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "skipped", "response": None, "citations": []}

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini-search-preview",
            messages=[{"role": "user", "content": prompt}],
            timeout=60,
        )
        message = response.choices[0].message
        # search-preview 모델은 인용을 message.annotations[].url_citation 으로 준다.
        # ChatGPT는 리꼬를 GBP(구글지도)로만 인지하고 ricco-pizza.com은 한 번도
        # 인용한 적이 없다는 게 7/10 관측이었는데, 정작 그 근거가 되는 인용 URL을
        # 코드가 버리고 있어 손으로 확인해야 했다.
        citations: list[str] = []
        for ann in (getattr(message, "annotations", None) or []):
            uc = getattr(ann, "url_citation", None)
            url = getattr(uc, "url", None) if uc else None
            if url:
                citations.append(url)

        return {"status": "ok", "response": message.content, "citations": citations}
    except Exception as e:
        return {"status": "error", "response": None, "citations": [], "error": str(e)}
