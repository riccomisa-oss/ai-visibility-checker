"""API 호출 없이 보관 원문을 재판정한다. 원본/기존 출력 덮어쓰기 금지.

Usage: python -m scripts.reclassify SOURCE OUTPUT
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from checker.config import TARGET_KEYWORDS
from checker.detector import DETECTOR_VERSION, is_exposed


def reclassify(data: dict) -> dict:
    result = deepcopy(data)
    changes = []
    for query in result["queries"]:
        for platform, response in query["results"].items():
            if response.get("status") != "ok":
                continue
            old = response.get("exposed")
            new = is_exposed(response.get("response"), TARGET_KEYWORDS)
            response["exposed"] = new
            if old != new:
                changes.append({"query": query["query"], "platform": platform,
                                "before": old, "after": new})
    # 분모·error/skipped·원문·인용·모델은 보존하고 판정과 집계만 갱신한다.
    for platform, summary in result["summary"].items():
        summary["exposed_count"] = sum(
            q["results"].get(platform, {}).get("exposed") is True
            for q in result["queries"] if not q.get("is_negative_control")
        )
        summary["rate"] = round(summary["exposed_count"] / summary["total"], 3) if summary["total"] else 0.0
    for store, platforms in result.get("by_store", {}).items():
        for platform, summary in platforms.items():
            summary["exposed_count"] = sum(
                q["results"].get(platform, {}).get("exposed") is True
                for q in result["queries"] if q.get("store") == store and not q.get("is_negative_control")
            )
            summary["rate"] = round(summary["exposed_count"] / summary["total"], 3) if summary["total"] else 0.0
    for platform, summary in result.get("negative_control", {}).items():
        summary["hits"] = sum(
            q["results"].get(platform, {}).get("exposed") is True
            for q in result["queries"] if q.get("is_negative_control")
        )
    result["detector_version"] = DETECTOR_VERSION
    result["reclassification"] = {"changes": changes, "original_summary": data["summary"]}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("원본 파일을 덮어쓸 수 없습니다.")
    raw = args.source.read_bytes()
    result = reclassify(json.loads(raw))
    result["reclassification"].update({
        "source": args.source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "classified_at": datetime.now(timezone.utc).isoformat(),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({"summary": result["summary"], "changes": result["reclassification"]["changes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
