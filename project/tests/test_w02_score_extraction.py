import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scorer", ROOT / "tools/w02_score_extraction.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)
GOLD = json.loads((ROOT / "artifacts/w02/eval/gold_labels.json").read_text(encoding="utf-8"))


def perfect_facts():
    claims = []
    for n, item in enumerate(GOLD["items"], 1):
        words = [item["match_any"][0]] + [group[0] for group in item["must_keep_any"]]
        claims.append({
            "id": f"CLM-{n:04}", "statement": "，".join(words), "kind": item["kind"][0],
            "evidence_status": item["evidence_status"][0], "qualifiers": [],
            "evidence": [{"meeting_id": GOLD["meetings"][item["meeting"]],
                          "message_id": item["message_id"], "quote": "x"}],
            "conflict_ids": [], "review": {"status": "pending", "note": ""}})
    return {"claims": claims, "conflicts": []}


def by_id(result):
    return {row["id"]: row for row in result["items"]}


def test_perfect_run_passes_every_item():
    result = scorer.score(GOLD, perfect_facts())
    assert result["summary"]["pass"] == len(GOLD["items"])
    assert result["summary"]["quoting_interviewer"] == 0
    assert result["summary"]["inference_claims"] == 0


def test_inference_claims_are_counted():
    facts = perfect_facts()
    facts["claims"][0]["kind"] = "inference"
    assert scorer.score(GOLD, facts)["summary"]["inference_claims"] == 1


def test_each_injected_error_is_caught_and_nothing_else():
    facts = perfect_facts()
    c = {GOLD["items"][i]["id"]: facts["claims"][i] for i in range(len(GOLD["items"]))}
    c["G15"]["evidence_status"] = "unknown"
    c["G16"]["kind"] = "question"
    c["G17"]["statement"] = "适用范围"
    c["G18"]["statement"] += "，门店没用过"
    c["G09"]["statement"] = "费用构成"
    facts["claims"].remove(c["G14"])
    extra = copy.deepcopy(c["G01"])
    extra["id"] = "CLM-9999"
    extra["evidence"] = [{"meeting_id": GOLD["meetings"]["ZHOU"], "message_id": "MSG-02623", "quote": "x"}]
    facts["claims"].append(extra)

    result = scorer.score(GOLD, facts)
    rows = by_id(result)
    assert rows["G15"]["result"] == "fail" and "evidence_status" in rows["G15"]["problems"][0]
    assert rows["G16"]["result"] == "fail" and "kind" in rows["G16"]["problems"][0]
    assert rows["G17"]["result"] == "fail" and "缺少限定" in rows["G17"]["problems"][0]
    assert rows["G18"]["result"] == "fail" and "禁止表述" in rows["G18"]["problems"][0]
    assert rows["G09"]["result"] == "fail" and "缺少限定" in rows["G09"]["problems"][0]
    assert rows["G14"]["result"] == "missed"
    assert result["quoting_interviewer"] == [{"claim": "CLM-9999", "message_id": "MSG-02623"}]
    assert result["summary"]["pass"] == len(GOLD["items"]) - 6
