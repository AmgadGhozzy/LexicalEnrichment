"""Adjudication decoder (build ticket 14, BT-14).

THE SOLE map-touching tool in the evaluation layer. Run ONLY after
judging closes for an item set: joins judgments with the PRIVATE
identity map and emits aggregates (per-field win rates for the
candidate side, critical-error counts by class and side,
tie/cannot-judge rates). Item-level decode is written to a private
analysis file, never into the judgments file.
"""

import json
import os
from collections import Counter

from evaluation.blind_package import CRITICAL_ERRORS, FIELDS


def decode(judgments_path, map_path, out_dir):
    """Join + aggregate. Returns (aggregates, analysis_path)."""
    judgments = json.load(open(judgments_path, encoding="utf-8"))["judgments"]
    id_map = json.load(open(map_path, encoding="utf-8"))["map"]
    field_wins = {f: Counter() for f in FIELDS}
    crit_counts = {c: Counter() for c in CRITICAL_ERRORS}
    item_rows = []
    for eval_id, ballot in judgments.items():
        side = id_map[eval_id]["candidate_side"]
        other = "B" if side == "A" else "A"
        row = {"eval_id": eval_id, "fields": {}, "criticals": []}
        for field, verdict in ballot["fields"].items():
            if verdict == "unjudged":
                continue
            mapped = (
                "candidate"
                if verdict == side + "-better"
                else "legacy" if verdict == other + "-better" else verdict
            )
            field_wins[field][mapped] += 1
            row["fields"][field] = mapped
        for cls, entry in ballot["critical_errors"].items():
            if not isinstance(entry, dict) or not entry.get("side"):
                continue
            err_side = (
                "candidate" if entry["side"] == side else "legacy")
            crit_counts[cls][err_side] += 1
            row["criticals"].append(
                {"class": cls, "side": err_side,
                 "evidence": entry.get("evidence", "")})
        item_rows.append(row)
    aggregates = {
        "n_judged": len(item_rows),
        "field_wins": {f: dict(c) for f, c in field_wins.items()},
        "critical_counts": {c: dict(x) for c, x in crit_counts.items()},
    }
    os.makedirs(out_dir, exist_ok=True)
    analysis_path = os.path.join(out_dir, "decode_analysis.json")
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump({"aggregates": aggregates, "items": item_rows}, f,
                  ensure_ascii=False, indent=1)
    return aggregates, analysis_path
