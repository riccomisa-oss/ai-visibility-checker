from __future__ import annotations
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from checker import config
from checker import detector
from checker.platforms import chatgpt, perplexity, claude, gemini, clovax

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "ai-visibility"

PLATFORM_MODULES = {
    "chatgpt": chatgpt,
    "perplexity": perplexity,
    "claude": claude,
    "gemini": gemini,
    "clovax": clovax,
}

STORES = ("hanam", "bundang", "brand")


def _domain(ref: str) -> str:
    """인용 URL(또는 도메인 문자열)에서 등록 도메인만 뽑는다.

    Gemini는 grounding_chunk.web.uri가 vertexaisearch 리다이렉터라 도메인이
    안 보이고, 대신 web.title에 실제 도메인이 담겨 온다. 그래서 URL이 아닌
    맨 도메인 문자열도 받을 수 있어야 한다.
    """
    if not ref:
        return ""
    ref = ref.strip()
    host = urlparse(ref).netloc if "://" in ref else ref.split("/")[0]
    return host.lower().removeprefix("www.")


def run() -> None:
    """모든 AI 플랫폼에 질문을 던지고 결과를 JSON으로 저장한다."""
    today = datetime.now().strftime("%Y-%m-%d")
    negative_controls = getattr(config, "NEGATIVE_CONTROLS", [])
    nc_set = set(negative_controls)
    store_by_query = getattr(config, "QUERY_STORE", {})

    # 노출 통계의 분모가 되는 질문 = QUERIES 중 역지표가 아닌 것.
    # (역지표가 QUERIES에도 들어 있으면 그 질문은 노출 통계에서 빠진다.)
    measured_queries = [q for q in config.QUERIES if q not in nc_set]

    results: dict = {
        "date": today,
        "collected_at": datetime.now().strftime("%H:%M KST"),
        "queries": [],
        "summary": {
            # total = 시도한 전체(ok + error, skipped 제외) — 에러도 분모에 넣어
            # 미노출로 처리한다. 실패를 분모에서 빼면 노출률이 낙관 편향된다.
            platform: {
                "exposed_count": 0,
                "total": 0,
                "errored": 0,
                "skipped": False,
                "rate": 0.0,
            }
            for platform in PLATFORM_MODULES
        },
        # 매장별 분리 집계. 총합 노출률은 하남(885리뷰)이 분당(34리뷰)을 가려
        # "리꼬가 보인다"는 착시를 만든다. 분당이 실제로 0인지 여기서 갈린다.
        "by_store": {
            store: {
                platform: {"exposed_count": 0, "total": 0, "rate": 0.0}
                for platform in PLATFORM_MODULES
            }
            for store in STORES
        },
        # AI가 실제로 읽은 출처 도메인. 어떤 오프사이트 채널에 돈을 쓸지는
        # 여기 뭐가 찍히느냐로만 결정한다(추측 금지).
        "citations": {platform: {} for platform in PLATFORM_MODULES},
        # 역지표: 리꼬가 나오면 환각. QUERIES 통계와 완전 분리해서 집계한다.
        "negative_control": {
            platform: {"hits": 0, "total": 0} for platform in PLATFORM_MODULES
        },
    }

    cite_counters: dict[str, Counter] = {p: Counter() for p in PLATFORM_MODULES}

    def _ask_platforms(q: str, is_nc: bool) -> dict:
        """한 질문을 전 플랫폼에 던지고 결과 dict를 반환. 통계는 results에 누적."""
        store = store_by_query.get(q)
        query_result: dict = {"query": q, "results": {}}
        if is_nc:
            query_result["is_negative_control"] = True
        if store:
            query_result["store"] = store

        for platform_name, module in PLATFORM_MODULES.items():
            platform_result = module.query(q)
            status = platform_result["status"]
            citations = platform_result.get("citations") or []
            domains = sorted({d for d in (_domain(c) for c in citations) if d})

            if status == "ok":
                exposed = detector.is_exposed(
                    platform_result["response"], config.TARGET_KEYWORDS
                )
                query_result["results"][platform_name] = {
                    "exposed": exposed,
                    "response": platform_result["response"],
                    "status": "ok",
                    "citations": citations,
                    "cited_domains": domains,
                }
                # 인용 도메인은 역지표 질문에서도 유효한 정보라 함께 센다.
                cite_counters[platform_name].update(domains)

                if is_nc:
                    # 역지표: '리꼬' 등장 = 환각 hit. 노출 통계에는 넣지 않는다.
                    results["negative_control"][platform_name]["total"] += 1
                    if exposed:
                        results["negative_control"][platform_name]["hits"] += 1
                else:
                    results["summary"][platform_name]["total"] += 1
                    if exposed:
                        results["summary"][platform_name]["exposed_count"] += 1
                    if store:
                        bs = results["by_store"][store][platform_name]
                        bs["total"] += 1
                        if exposed:
                            bs["exposed_count"] += 1
            else:
                query_result["results"][platform_name] = {
                    "exposed": None,
                    "response": None,
                    "status": status,
                    "error": platform_result.get("error"),
                }
                if status == "skipped":
                    results["summary"][platform_name]["skipped"] = True
                elif not is_nc:
                    # 에러도 분모에 포함(미노출 취급) — 낙관 편향 제거
                    results["summary"][platform_name]["total"] += 1
                    results["summary"][platform_name]["errored"] += 1
                    if store:
                        results["by_store"][store][platform_name]["total"] += 1
                else:
                    results["negative_control"][platform_name]["total"] += 1

        return query_result

    # QUERIES 순서는 baseline 호환을 위해 보존한다. 다만 역지표로 지정된 질문은
    # 여기서 is_nc=True로 처리해 노출 통계를 오염시키지 않는다(같은 질문을 두 번
    # 던지지도 않는다 — 예전엔 QUERIES와 NEGATIVE_CONTROLS 양쪽에 있어 2회 호출됐다).
    for q in config.QUERIES:
        results["queries"].append(_ask_platforms(q, is_nc=q in nc_set))
    for q in negative_controls:
        if q not in config.QUERIES:
            results["queries"].append(_ask_platforms(q, is_nc=True))

    # 노출률 계산 (분모 = ok + error, skipped 플랫폼은 total 0 → rate 0)
    for platform in results["summary"]:
        s = results["summary"][platform]
        s["rate"] = round(s["exposed_count"] / s["total"], 3) if s["total"] > 0 else 0.0
    for store in STORES:
        for platform, bs in results["by_store"][store].items():
            bs["rate"] = (
                round(bs["exposed_count"] / bs["total"], 3) if bs["total"] > 0 else 0.0
            )

    # 인용 도메인 히스토그램 (빈도 내림차순)
    for platform, counter in cite_counters.items():
        results["citations"][platform] = dict(counter.most_common())

    # JSON 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{today}.json"
    output_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # index.json 업데이트 (대시보드가 사용 가능한 날짜 목록 파악용)
    index_file = OUTPUT_DIR / "index.json"
    dates: list[str] = json.loads(index_file.read_text()) if index_file.exists() else []
    if today not in dates:
        dates.append(today)
        dates.sort()
    index_file.write_text(json.dumps(dates), encoding="utf-8")

    # 실행 요약 출력
    print(f"✅ 저장 완료: {output_file}")
    print(f"   측정 질문 {len(measured_queries)}개 · 역지표 {len(negative_controls)}개")

    for platform, s in results["summary"].items():
        if s["skipped"]:
            print(f"  {platform}: SKIPPED (API 키 없음)")
            continue
        err = f" · 에러 {s['errored']}" if s["errored"] else ""
        print(
            f"  {platform}: {s['exposed_count']}/{s['total']} 노출 "
            f"({s['rate']*100:.0f}%){err}"
        )

    # 매장별 — 여기가 진짜 지표다. 분당이 0이면 총합이 올라도 의미 없다.
    print("\n매장별 노출:")
    for store in STORES:
        cells = []
        for platform, bs in results["by_store"][store].items():
            if results["summary"][platform]["skipped"] or bs["total"] == 0:
                continue
            cells.append(f"{platform} {bs['exposed_count']}/{bs['total']}")
        if cells:
            print(f"  {store}: " + " · ".join(cells))

    # 인용 도메인 — AI가 실제로 뭘 읽고 답하는가
    print("\n인용 도메인 TOP5 (엔진이 실제로 읽은 출처):")
    any_cite = False
    for platform, hist in results["citations"].items():
        if not hist:
            continue
        any_cite = True
        top = ", ".join(f"{d}({n})" for d, n in list(hist.items())[:5])
        print(f"  {platform}: {top}")
    if not any_cite:
        print("  (인용 0건 — 엔진이 웹을 안 읽고 파라메트릭 지식으로 답했다는 뜻이면")
        print("   오프사이트 채널 투자는 올해 무효다. 어댑터 버그인지 먼저 확인할 것.)")

    # 역지표(환각) 경보
    nc_alerts = {
        p: v["hits"] for p, v in results["negative_control"].items() if v["hits"]
    }
    if nc_alerts:
        print("\n⚠️  역지표 환각 감지(블루리본 등 미보유 사실):", nc_alerts)


if __name__ == "__main__":
    run()
