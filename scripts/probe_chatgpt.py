"""chatgpt 어댑터 라이브 프로브 — data/ 미기록.

왜 있나: 2026-07-23 모델 폐기로 8/26 측정이 29질의 전부 404로 죽었는데,
월 1회만 도는 파이프라인이라 그게 한 달 뒤에야 드러났다. 어댑터를 고친 뒤
"진짜 되는지"를 정기 측정(전체 30질의 + 그날 데이터 덮어쓰기) 없이 몇 센트로
확인하려고 분리했다. 다음 폐기 때도 이걸로 먼저 확인한다.

프리셋:
  smoke(기본)   — 질의 1건. 어댑터 생존 확인용.
  journal-slots — 저널이 노린 속성 슬롯 8종. 정기 측정을 덮어쓰지 않고
                  "저널이 인용되는가"의 재현성만 다시 잰다. 08-27 1회차는
                  4/8 노출(르방×2·72시간·페라라)이었고, 표본 1회라 재현 확인이 필요했다.

실행: PROBE_PRESET=journal-slots python -m scripts.probe_chatgpt
"""
from __future__ import annotations
import os
import sys

from checker import config
from checker.platforms import chatgpt
from checker import detector


SMOKE = ["하남미사 화덕피자 맛집 추천해줘"]

# 07-10에 "전 엔진 0"이라 저널 트랙을 접게 만든 바로 그 질의들.
JOURNAL_SLOTS = [
    "경기도 천연발효종 르방 화덕피자 전문점 알려줘",
    "천연발효종 르방으로 만든 화덕피자 어디서 파나요",
    "나폴리피자 장인협회 APN 인증 받은 한국 피자집 있어?",
    "카푸토 밀가루 쓰는 정통 화덕피자집 알려줘",
    "소화 잘되는 건강한 도우 피자 어디가 좋아?",
    "72시간 숙성 도우 같은 장시간 발효 피자 맛집",
    "스테파노 페라라 화덕 쓰는 피자집 어디야",
    "르꼬르동블루 출신 셰프가 하는 피자집 있나요",
]

PRESETS = {"smoke": SMOKE, "journal-slots": JOURNAL_SLOTS}


def _run_one(prompt: str) -> tuple[int, bool, int]:
    """(exit코드, 노출여부, 홈인용수)"""
    result = chatgpt.query(prompt)
    status = result["status"]

    print(f"질의: {prompt}")
    print(f"status: {status}")

    if status == "skipped":
        print("판정: 미실행 — OPENAI_API_KEY가 없다(어댑터 문제 아님).\n")
        return 3, False, 0

    if status != "ok":
        print(f"error: {result.get('error')}")
        print("판정: 실패 — 모델·도구 설정을 다시 봐야 한다.\n")
        return 1, False, 0

    body = result["response"] or ""
    citations = result["citations"]
    exposed = detector.is_exposed(body, config.TARGET_KEYWORDS)
    home = sum(1 for u in citations if "ricco-pizza.com" in u)

    print(f"model: {result.get('model')} | searched: {result.get('searched')} "
          f"| citations: {len(citations)}건 | 홈 인용: {home}회 | 리꼬 노출: {exposed}")
    for url in citations[:8]:
        print(f"  - {url}")

    # 검색을 안 했다면 인용 0건이 정상이므로 노출 통계로 읽으면 안 된다.
    if not result.get("searched"):
        print("⚠️ 웹검색 미수행 — 파라메트릭 답변이라 인용 지형 측정에 쓸 수 없다.\n")
        return 2, exposed, home

    print()
    return 0, exposed, home


def main() -> int:
    preset = os.environ.get("PROBE_PRESET", "smoke")
    prompts = PRESETS.get(preset)
    if prompts is None:
        print(f"알 수 없는 프리셋: {preset} (가능: {', '.join(PRESETS)})")
        return 1

    print(f"프리셋: {preset} — 질의 {len(prompts)}건 (data/ 미기록)\n")
    codes, exposed_n, home_n = [], 0, 0
    for p in prompts:
        code, exposed, home = _run_one(p)
        codes.append(code)
        exposed_n += 1 if exposed else 0
        home_n += home

    print(f"요약: 노출 {exposed_n}/{len(prompts)} · 홈 인용 누적 {home_n}회")
    if any(c == 1 for c in codes):
        print("판정: 실패 — 어댑터를 다시 봐야 한다.")
        return 1
    if all(c == 3 for c in codes):
        return 3
    print("판정: 정상 — Responses API + web_search 경로가 살아 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
