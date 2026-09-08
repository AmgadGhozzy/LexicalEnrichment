"""Reconcile HUMAN30 human reference judgments vs the frozen AI
decode (ai_judge_seeded348/decode_analysis.json), in candidate/legacy
space via the PRIVATE identity map. Runs only AFTER judging closes.

Outputs (output/human_review_seeded30/reconcile30.json):
  - per-card, per-field: human side | AI side | agree/flip/abstain
  - field-level agreement incl. the three watch fields
  - critical comparisons (v3 overlap + human non-v3 classes)
  - semantic-regression scan (human prefers legacy over candidate),
    with a systematicity verdict per the pre-registered protocol.
"""

import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

OUT_DIR = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                       "output", "human_review_seeded30")
BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                    "output")

FIELDS = ("definition", "arabic_explanation", "sense_separation",
          "examples", "translations", "relations", "mnemonic")
WATCH = ("translations", "relations", "sense_separation")
V3_CLASSES = ("wrong_meaning", "misleading_arabic",
              "invalid_relation_synonym", "example_semantic_error",
              "target_word_violation", "fabricated_etymology_mnemonic",
              "cefr_learner_mismatch")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ballots = load_json(os.path.join(OUT_DIR,
                                     "human_judgments_30.json"))[
        "judgments"]
    id_map = load_json(os.path.join(BASE, "eval_seeded348_v1",
                                    "eval_identity_map.json"))["map"]
    decode = {r["eval_id"]: r for r in load_json(
        os.path.join(BASE, "ai_judge_seeded348",
                     "decode_analysis.json"))["items"]}
    annot = load_json(os.path.join(OUT_DIR,
                                   "human30_annotations.json"))

    rows = []
    per_field = {f: {"n": 0, "agree": 0, "flip": 0, "abstain": 0,
                     "mismatch": 0, "legacy_only": 0,
                     "candidate_only": 0}
                 for f in FIELDS}
    regressions = []
    for eval_id, ballot in sorted(ballots.items()):
        side = id_map[eval_id]["candidate_side"]
        ai = decode.get(eval_id, {"fields": {}, "criticals": []})
        card = {"eval_id": eval_id, "key": id_map[eval_id][
            "candidate_key"], "candidate_side": side, "fields": {}}
        for f in FIELDS:
            hv_raw = ballot["fields"][f]   # A-better/B-better/tie/...
            if hv_raw == "unjudged":
                hv_c = "unjudged"
            elif hv_raw == "A-better":
                hv_c = "candidate" if side == "A" else "legacy"
            elif hv_raw == "B-better":
                hv_c = "candidate" if side == "B" else "legacy"
            else:
                hv_c = hv_raw
            av = ai["fields"].get(f)
            status = ""
            if hv_c == av:
                status = "agree"
            elif hv_c == "unjudged" or hv_c == "cannot-judge" or \
                    av == "cannot-judge":
                status = "abstain"
            else:
                status = "flip" if hv_c in ("candidate", "legacy") and \
                    av in ("candidate", "legacy") else "mismatch"
            per_field[f]["n"] += 1
            per_field[f][status] += 1
            card["fields"][f] = {"human": hv_c, "ai": av,
                                 "status": status}
            if hv_c == "legacy":
                per_field[f]["legacy_only"] += 1
                if f in WATCH or f == "examples":
                    regressions.append({"eval_id": eval_id, "field": f,
                                        "human": hv_c, "ai": av})
            if hv_c == "candidate":
                per_field[f]["candidate_only"] += 1
        card["criticals"] = {"human_v3": {
            cls: ballot["critical_errors"][cls]["side"] for cls in
            V3_CLASSES if ballot["critical_errors"][cls]["side"]},
            "ai": ai.get("criticals", [])}
        rows.append(card)

    row_sum = {f: 0 for f in FIELDS}
    for r in rows:
        for f in FIELDS:
            if r["fields"][f]["status"] == "agree":
                row_sum[f] += 1

    watch_regress = [r for r in regressions
                     if r["field"] in WATCH]
    systematic = len(watch_regress) >= 3 and len(
        {r["eval_id"] for r in watch_regress}) >= 3

    v3_human = [(r["eval_id"], cls, r["criticals"]["human_v3"][cls])
                for r in rows
                for cls in r["criticals"]["human_v3"]]
    ai_crits = [(r["eval_id"], c["class"], c["side"])
                for r in rows for c in r["criticals"]["ai"]]
    ai_v3 = [c for c in ai_crits if c[1] in V3_CLASSES]
    non_v3_human = []
    for eval_id, items in annot.get("annotations", {}).items():
        for it in items:
            if it.get("type") == "non_v3_critical":
                non_v3_human.append((eval_id, it["class"], it["side"],
                                     it["text"]))

    human_v3_keys = {(a, b) for a, b, c in v3_human}
    ai_v3_keys = {(a, b) for a, b, c in ai_crits}
    overlap = human_v3_keys & ai_v3_keys
    human_only = human_v3_keys - ai_v3_keys
    ai_only = ai_v3_keys - human_v3_keys

    agree_total = sum(row_sum[f] for f in FIELDS)
    n_total = len(rows) * len(FIELDS)

    out = {
        "n_cards": len(rows),
        "per_field": per_field,
        "agreement": {
            "overall": round(agree_total / n_total, 4),
            "per_field": {f: round(row_sum[f] / len(rows), 4)
                          for f in FIELDS},
            "watch_fields": {f: round(row_sum[f] / len(rows), 4)
                             for f in WATCH},
        },
        "human_v3_criticals": sorted(v3_human),
        "ai_v3_criticals": sorted(ai_v3),
        "non_v3_human_criticals": sorted(non_v3_human),
        "critical_overlap": sorted(overlap),
        "critical_human_only": sorted(human_only),
        "critical_ai_only": sorted(ai_only),
        "regression_scan": {
            "count": len(regressions),
            "watch_count": len(watch_regress),
            "systematic": systematic,
            "entries": sorted(watch_regress, key=lambda r: (
                r["eval_id"], r["field"]))
                        + sorted([r for r in regressions
                                  if r not in watch_regress],
                                 key=lambda r: (r["eval_id"],
                                                r["field"])),
        },
        "cards": rows,
    }
    out_path = os.path.join(OUT_DIR, "reconcile30.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("cards:", len(rows), "| overall agreement:",
          round(agree_total / n_total, 4))
    print("per-field agreement:")
    for f in FIELDS:
        print("  %-18s  agree=%2d/30  flip=%d  abstain=%d  "
              "[legacy_pref=%d cand_pref=%d]" % (
                  f, row_sum[f], per_field[f]["flip"],
                  per_field[f]["abstain"],
                  per_field[f]["legacy_only"],
                  per_field[f]["candidate_only"]))
    print("human v3 criticals:", v3_human)
    print("ai v3 criticals on sample:", len(ai_v3), ai_v3)
    print("non-v3 human criticals:", sorted(non_v3_human))
    print("critical overlap:", sorted(overlap),
          "| human_only:", sorted(human_only),
          "| ai_only:", sorted(ai_only))
    print("regressions (human prefers legacy):", len(regressions),
          "watch:", len(watch_regress),
          "SYSTEMATIC →", systematic)
    for r in sorted(watch_regress, key=lambda x: (x["eval_id"],
                                                   x["field"])) + \
            sorted([x for x in regressions
                    if x not in watch_regress],
                   key=lambda x: (x["eval_id"], x["field"])):
        print("   ", r["eval_id"], r["field"], "human:", r["human"],
              "ai:", r["ai"])
    return out


if __name__ == "__main__":
    main()