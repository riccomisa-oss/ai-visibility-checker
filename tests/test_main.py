import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from checker.main import run


def _measured() -> list[str]:
    """노출 통계의 분모가 되는 질문 = QUERIES 중 역지표가 아닌 것."""
    from checker import config
    nc = set(getattr(config, "NEGATIVE_CONTROLS", []))
    return [q for q in config.QUERIES if q not in nc]


@pytest.fixture
def mock_all_platforms():
    """모든 플랫폼 모듈을 mock으로 대체"""
    ok_response = {"status": "ok", "response": "리꼬 피자를 추천합니다."}
    with patch("checker.main.chatgpt.query", return_value=ok_response), \
         patch("checker.main.perplexity.query", return_value=ok_response), \
         patch("checker.main.claude.query", return_value=ok_response), \
         patch("checker.main.gemini.query", return_value=ok_response), \
         patch("checker.main.clovax.query", return_value=ok_response):
        yield


def test_run_creates_json_file(tmp_path, mock_all_platforms):
    """run() 실행 시 JSON 파일이 생성됨"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    json_files = list(tmp_path.glob("*.json"))
    # index.json + 날짜.json
    date_files = [f for f in json_files if f.name != "index.json"]
    assert len(date_files) == 1


def test_run_json_has_correct_structure(tmp_path, mock_all_platforms):
    """생성된 JSON이 올바른 구조를 가짐"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    assert "date" in data
    assert "queries" in data
    assert "summary" in data
    from checker import config
    # 역지표가 QUERIES에도 들어 있으면 한 번만 던진다(중복 호출 금지).
    extra_nc = [q for q in config.NEGATIVE_CONTROLS if q not in config.QUERIES]
    assert len(data["queries"]) == len(config.QUERIES) + len(extra_nc)
    assert "chatgpt" in data["summary"]
    assert "perplexity" in data["summary"]
    assert "claude" in data["summary"]
    assert "gemini" in data["summary"]
    assert "clovax" in data["summary"]


def test_run_detects_exposure(tmp_path, mock_all_platforms):
    """'리꼬'가 포함된 응답 → exposed=True"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    first_query = data["queries"][0]
    assert first_query["results"]["chatgpt"]["exposed"] is True


def test_run_updates_index_json(tmp_path, mock_all_platforms):
    """run() 실행 시 index.json이 업데이트됨"""
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    index_file = tmp_path / "index.json"
    assert index_file.exists()
    dates = json.loads(index_file.read_text())
    assert len(dates) == 1


def test_run_handles_skipped_platform(tmp_path):
    """플랫폼 skipped 시 summary에 skipped=True 기록"""
    skipped = {"status": "skipped", "response": None}
    ok = {"status": "ok", "response": "리꼬 피자 추천"}

    with patch("checker.main.chatgpt.query", return_value=skipped), \
         patch("checker.main.perplexity.query", return_value=ok), \
         patch("checker.main.claude.query", return_value=ok), \
         patch("checker.main.gemini.query", return_value=ok), \
         patch("checker.main.clovax.query", return_value=skipped), \
         patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    assert data["summary"]["chatgpt"]["skipped"] is True
    assert data["summary"]["clovax"]["skipped"] is True
    assert data["summary"]["perplexity"]["skipped"] is False


def test_error_counts_toward_denominator(tmp_path):
    """API 에러는 분모(total)에 포함되고 미노출로 처리된다(낙관 편향 제거).

    이전 버그: status != 'ok'이면 total을 안 올려서, 실패가 많을수록 노출률이
    높아 보였다(6/24 Gemini 11/23 = 48%가 실은 11/30 = 37%).
    """
    err = {"status": "error", "response": None, "error": "503 UNAVAILABLE"}
    ok = {"status": "ok", "response": "리꼬 피자 추천"}

    with patch("checker.main.chatgpt.query", return_value=ok), \
         patch("checker.main.perplexity.query", return_value=ok), \
         patch("checker.main.claude.query", return_value=ok), \
         patch("checker.main.gemini.query", return_value=err), \
         patch("checker.main.clovax.query", return_value=ok), \
         patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))
    n = len(_measured())

    gem = data["summary"]["gemini"]
    assert gem["errored"] == n           # 전 질문 에러
    assert gem["total"] == n             # 에러도 분모에 포함
    assert gem["exposed_count"] == 0     # 에러는 미노출
    assert gem["rate"] == 0.0
    assert gem["skipped"] is False


def test_negative_control_tracked_separately(tmp_path):
    """역지표 질문에서 리꼬가 나오면 노출이 아니라 hit으로 분리 집계된다.

    역지표는 QUERIES 노출 분자/분모 어디에도 들어가지 않는다.
    """
    ok = {"status": "ok", "response": "리꼬 피자 추천"}  # 모든 질문에 '리꼬' 등장

    with patch("checker.main.chatgpt.query", return_value=ok), \
         patch("checker.main.perplexity.query", return_value=ok), \
         patch("checker.main.claude.query", return_value=ok), \
         patch("checker.main.gemini.query", return_value=ok), \
         patch("checker.main.clovax.query", return_value=ok), \
         patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))
    from checker import config
    n = len(_measured())

    # 노출 분모는 측정 질문만 — 역지표는 QUERIES 안에 있어도 빠진다
    assert data["summary"]["chatgpt"]["total"] == n
    # 역지표에서 '리꼬'가 나왔으니 hit 집계됨
    assert "negative_control" in data
    assert data["negative_control"]["chatgpt"]["hits"] >= 1
    # 역지표 질문 자체는 별도 블록으로 기록
    nc_queries = [q for q in data["queries"] if q.get("is_negative_control")]
    assert len(nc_queries) == len(config.NEGATIVE_CONTROLS)


def test_negative_control_in_queries_is_not_double_asked(tmp_path, mock_all_platforms):
    """역지표가 QUERIES에도 들어 있으면 한 번만 던지고, 노출 통계는 오염되지 않는다.

    이전 버그: '분당 블루리본 화덕피자 맛집 추천'이 QUERIES와 NEGATIVE_CONTROLS
    양쪽에 있어서 (1) 같은 질문을 두 번 호출하고 (2) QUERIES 쪽 집계에는 역지표가
    노출로 섞여 들어갔다. 역지표 분리가 절반만 돼 있던 셈이다.
    """
    from checker import config
    overlap = [q for q in config.NEGATIVE_CONTROLS if q in config.QUERIES]
    assert overlap, "이 테스트는 역지표가 QUERIES에 있는 상황을 전제한다"

    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    for q in overlap:
        entries = [e for e in data["queries"] if e["query"] == q]
        assert len(entries) == 1, f"'{q}'가 중복 실행됨"
        assert entries[0].get("is_negative_control") is True

    # 오염 제거 확인: 분모에 역지표가 안 들어갔다
    assert data["summary"]["chatgpt"]["total"] == len(_measured())


def test_by_store_breakdown(tmp_path, mock_all_platforms):
    """매장별(하남/분당/브랜드) 노출이 분리 집계된다.

    총합 노출률은 하남(리뷰 885개)이 분당(34개)을 가려 '리꼬가 보인다'는 착시를
    만든다. 분당 슬롯이 실제로 0인지는 이 분리로만 확인된다.
    """
    with patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    assert set(data["by_store"]) == {"hanam", "bundang", "brand"}

    # 매장별 분모의 합 = 측정 질문 수 (모든 측정 질문에 store 태그가 있어야 함)
    total = sum(data["by_store"][s]["chatgpt"]["total"] for s in data["by_store"])
    assert total == len(_measured())

    # mock이 전 질문에 '리꼬'를 넣으므로 매장별 rate는 모두 1.0
    assert data["by_store"]["bundang"]["chatgpt"]["rate"] == 1.0


def test_citation_domains_collected(tmp_path):
    """어댑터가 준 인용 URL이 도메인 히스토그램으로 집계된다."""
    ok = {
        "status": "ok",
        "response": "리꼬 피자 추천",
        "citations": [
            "https://www.diningcode.com/profile.php?rid=x",
            "https://ricco-pizza.com/journal/",
            "https://www.diningcode.com/list.dc?query=y",
        ],
    }
    none_cite = {"status": "ok", "response": "리꼬 피자 추천"}  # citations 키 없음

    with patch("checker.main.chatgpt.query", return_value=ok), \
         patch("checker.main.perplexity.query", return_value=none_cite), \
         patch("checker.main.claude.query", return_value=none_cite), \
         patch("checker.main.gemini.query", return_value=none_cite), \
         patch("checker.main.clovax.query", return_value=none_cite), \
         patch("checker.main.OUTPUT_DIR", tmp_path):
        run()

    date_files = [f for f in tmp_path.glob("*.json") if f.name != "index.json"]
    data = json.loads(date_files[0].read_text(encoding="utf-8"))

    hist = data["citations"]["chatgpt"]
    # www. 제거 + 같은 질문 내 중복 도메인은 1회로 셈 → 질문 수만큼 누적
    n_all = len(data["queries"])
    assert hist["diningcode.com"] == n_all
    assert hist["ricco-pizza.com"] == n_all
    # 빈도 내림차순 정렬
    assert list(hist.values()) == sorted(hist.values(), reverse=True)
    # 인용을 안 준 어댑터는 빈 히스토그램
    assert data["citations"]["claude"] == {}

    # 질문 단위로도 기록된다
    first = data["queries"][0]["results"]["chatgpt"]
    assert first["cited_domains"] == ["diningcode.com", "ricco-pizza.com"]
