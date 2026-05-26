from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

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


def run() -> None:
    """모든 AI 플랫폼에 질문을 던지고 결과를 JSON으로 저장한다."""
    today = datetime.now().strftime("%Y-%m-%d")
    results: dict = {
        "date": today,
        "collected_at": datetime.now().strftime("%H:%M KST"),
        "queries": [],
        "summary": {
            platform: {"exposed_count": 0, "total": 0, "skipped": False, "rate": 0.0}
            for platform in PLATFORM_MODULES
        },
    }

    for q in config.QUERIES:
        query_result: dict = {"query": q, "results": {}}

        for platform_name, module in PLATFORM_MODULES.items():
            platform_result = module.query(q)

            if platform_result["status"] == "ok":
                exposed = detector.is_exposed(platform_result["response"], config.TARGET_KEYWORDS)
                query_result["results"][platform_name] = {
                    "exposed": exposed,
                    "response": platform_result["response"],
                    "status": "ok",
                }
                results["summary"][platform_name]["total"] += 1
                if exposed:
                    results["summary"][platform_name]["exposed_count"] += 1
            else:
                query_result["results"][platform_name] = {
                    "exposed": None,
                    "response": None,
                    "status": platform_result["status"],
                }
                if platform_result["status"] == "skipped":
                    results["summary"][platform_name]["skipped"] = True

        results["queries"].append(query_result)

    # 노출률 계산
    for platform in results["summary"]:
        s = results["summary"][platform]
        s["rate"] = round(s["exposed_count"] / s["total"], 3) if s["total"] > 0 else 0.0

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
    for platform, s in results["summary"].items():
        if s["skipped"]:
            print(f"  {platform}: SKIPPED (API 키 없음)")
        else:
            print(f"  {platform}: {s['exposed_count']}/{s['total']} 노출 ({s['rate']*100:.0f}%)")


if __name__ == "__main__":
    run()
