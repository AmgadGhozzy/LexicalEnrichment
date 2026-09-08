"""Blind adjudication recorder (build ticket 14, BT-14).

Records human verdicts against the frozen blind package. This
module has NO code path that loads, imports, or references the
identity map — blindness is structural, not procedural (asserted
in-test by source inspection). Decoding lives exclusively in
evaluation/adjudication_decode.py and runs only after judging
closes.

Ballot values: per field one of {A-better, B-better, tie,
cannot-judge, unjudged}; critical errors map class -> {"side":
A/B/null, "evidence": str}. Judgments file: {eval_id: ballot}.
"""

import json
import os

from evaluation.blind_package import CRITICAL_ERRORS, FIELDS

FIELD_VERDICTS = frozenset(
    {"A-better", "B-better", "tie", "cannot-judge", "unjudged"}
)


def validate_ballot(ballot):
    """Return a list of defects; empty means a well-formed ballot."""
    defects = []
    if not isinstance(ballot, dict):
        return ["ballot is not a mapping"]
    fields = ballot.get("fields")
    if not isinstance(fields, dict) or set(fields) != set(FIELDS):
        defects.append("fields must cover exactly the 7 locked fields")
    else:
        for field, verdict in fields.items():
            if not isinstance(verdict, str) or verdict not in FIELD_VERDICTS:
                defects.append("bad verdict %r for %s" % (verdict, field))
    crits = ballot.get("critical_errors")
    if not isinstance(crits, dict) or set(crits) != set(CRITICAL_ERRORS):
        defects.append("critical_errors must cover exactly the 7 classes")
    else:
        for cls, entry in crits.items():
            if not isinstance(entry, dict):
                defects.append("bad entry for %s" % cls)
                continue
            if entry.get("side") not in ("A", "B", None):
                defects.append("bad side for %s" % cls)
    return defects


def record_judgments(package_items, judgments, out_path):
    """Validate + write a judgments file. Never touches the map.

    package_items: the frozen package list (for eval_id roster).
    judgments: {eval_id: ballot}. Unknown eval_ids raise. Missing
    ids stay unjudged (no default-filling, ever).
    """
    roster = {item["eval_id"] for item in package_items}
    unknown = set(judgments) - roster
    if unknown:
        raise ValueError("judgments for unknown eval ids: %s" % sorted(unknown))
    for eval_id, ballot in judgments.items():
        defects = validate_ballot(ballot)
        if defects:
            raise ValueError("%s: %s" % (eval_id, defects))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"judgments": judgments}, f, ensure_ascii=False, indent=1)
    return out_path
