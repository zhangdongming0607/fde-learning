"""Score one W2 extraction run against hand-written gold labels.

Matching is by message_id plus keywords, so unmatched or odd results still need a human look.
"""
import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def candidates_path(path):
    p = Path(path)
    if p.name == "run.json":
        p = p.parent / "candidates.json"
    return p


def text_of(claim):
    return claim["statement"] + "\n" + "\n".join(claim["qualifiers"])


def check_item(item, claim):
    text = text_of(claim)
    problems = []
    if claim["kind"] not in item["kind"]:
        problems.append(f"kind={claim['kind']}，应为 {'/'.join(item['kind'])}")
    status = claim["evidence_status"]
    if status == "conflicting":
        problems.append("evidence_status=conflicting（冲突阶段改写，需人工看）")
    elif status not in item["evidence_status"]:
        problems.append(f"evidence_status={status}，应为 {'/'.join(item['evidence_status'])}")
    for group in item["must_keep_any"]:
        if not any(word in text for word in group):
            problems.append(f"缺少限定（任一）：{'/'.join(group)}")
    for phrase in item["must_not"]:
        if phrase in text:
            problems.append(f"出现禁止表述：{phrase}")
    return problems


def score(gold, facts):
    meetings = gold["meetings"]
    claims = facts["claims"]
    rows = []
    for item in gold["items"]:
        mid = meetings[item["meeting"]]
        hits = [c for c in claims
                if any(e["meeting_id"] == mid and e["message_id"] == item["message_id"] for e in c["evidence"])
                and any(k in text_of(c) + "".join(e["quote"] for e in c["evidence"]) for k in item["match_any"])]
        if not hits:
            rows.append({"id": item["id"], "result": "missed", "claim": None, "problems": ["未提取到"]})
            continue
        judged = sorted(((check_item(item, c), c) for c in hits), key=lambda x: len(x[0]))
        problems, best = judged[0]
        rows.append({"id": item["id"], "result": "pass" if not problems else "fail",
                     "claim": best["id"], "problems": problems, "matched": len(hits)})
    interviewer = {meetings[k]: set(v) for k, v in gold["interviewer_messages"].items()}
    quoting_interviewer = [{"claim": c["id"], "message_id": e["message_id"]}
                           for c in claims for e in c["evidence"]
                           if e["message_id"] in interviewer.get(e["meeting_id"], set())]
    summary = {
        "claims": len(claims),
        "gold_items": len(rows),
        "pass": sum(r["result"] == "pass" for r in rows),
        "fail": sum(r["result"] == "fail" for r in rows),
        "missed": sum(r["result"] == "missed" for r in rows),
        "quoting_interviewer": len(quoting_interviewer),
        "inference_claims": sum(c["kind"] == "inference" for c in claims),
        "conflict_groups": len(facts.get("conflicts", [])),
    }
    return {"summary": summary, "items": rows, "quoting_interviewer": quoting_interviewer,
            "inferences": [{"claim": c["id"], "statement": c["statement"]} for c in claims if c["kind"] == "inference"],
            "conflicts": [{"id": g["id"], "claim_ids": g["claim_ids"], "question": g.get("question", "")}
                          for g in facts.get("conflicts", [])]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", help="run.json 或 candidates.json")
    p.add_argument("--gold", default="artifacts/w02/eval/gold_labels.json")
    p.add_argument("--output")
    a = p.parse_args()
    result = score(load(a.gold), load(candidates_path(a.run)))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if a.output:
        out = Path(a.output)
        if out.exists():
            raise SystemExit(f"{out} 已存在，不覆盖")
        out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
