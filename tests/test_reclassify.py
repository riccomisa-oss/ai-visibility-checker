from copy import deepcopy
import json
from pathlib import Path

from scripts.reclassify import reclassify


def test_saved_baseline_is_corrected_without_altering_evidence():
    original = json.loads((Path(__file__).parents[1] / "data/ai-visibility/2026-08-27.json").read_text())
    untouched = deepcopy(original)
    result = reclassify(original)
    assert original == untouched
    assert result["summary"]["chatgpt"]["exposed_count"] == 19
    assert result["by_store"]["bundang"]["chatgpt"]["exposed_count"] == 5
    assert len(result["reclassification"]["changes"]) == 1
    assert result["citations"] == original["citations"]
    for old_query, new_query in zip(original["queries"], result["queries"]):
        for platform, old in old_query["results"].items():
            new = new_query["results"][platform]
            assert {k: v for k, v in new.items() if k != "exposed"} == {k: v for k, v in old.items() if k != "exposed"}
