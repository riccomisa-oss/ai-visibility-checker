"""chatgpt 어댑터 라이브 스모크 테스트 — 질의 1건, data/ 미기록.

왜 있나: 2026-07-23 모델 폐기로 8/26 측정이 29질의 전부 404로 죽었는데,
월 1회만 도는 파이프라인이라 그게 한 달 뒤에야 드러났다. 어댑터를 고친 뒤
"진짜 되는지"를 정기 측정(전체 30질의 + 그날 데이터 덮어쓰기) 없이 몇 센트로
확인하려고 분리했다. 다음 폐기 때도 이걸로 먼저 확인한다.

실행: python -m scripts.probe_chatgpt
"""
from __future__ import annotations
import sys

from checker import config
from checker.platforms import chatgpt
from checker import detector


PROMPT = "하남미사 화덕피자 맛집 추천해줘"


def main() -> int:
    result = chatgpt.query(PROMPT)
    status = result["status"]

    print(f"질의: {PROMPT}")
    print(f"status: {status}")

    if status == "skipped":
        print("\n판정: 미실행 — OPENAI_API_KEY가 없다(어댑터 문제 아님).")
        return 3

    if status != "ok":
        print(f"error: {result.get('error')}")
        print("\n판정: 실패 — 모델·도구 설정을 다시 봐야 한다.")
        return 1

    body = result["response"] or ""
    citations = result["citations"]
    exposed = detector.is_exposed(body, config.TARGET_KEYWORDS)

    print(f"model: {result.get('model')}")
    print(f"searched(웹검색 수행): {result.get('searched')}")
    print(f"citations: {len(citations)}건")
    for url in citations[:10]:
        print(f"  - {url}")
    print(f"리꼬 노출 여부: {exposed}")
    print(f"\n본문 앞 400자:\n{body[:400]}")

    # 검색을 안 했다면 인용 0건이 정상이므로 노출 통계로 읽으면 안 된다.
    if not result.get("searched"):
        print("\n⚠️ 웹검색이 수행되지 않았다. 이 응답은 파라메트릭 답변이라 "
              "인용 지형 측정에 쓸 수 없다 — 도구 설정을 확인할 것.")
        return 2

    print("\n판정: 정상 — Responses API + web_search 경로가 살아 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
