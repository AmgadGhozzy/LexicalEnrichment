"""Record the human reference judgments for the HUMAN30 sample.

Source of truth: the human reviewer's decision table (30 cards,
verbatim; a card judged once). The program maps A/B/tie onto the
blind ballot contract (adjudicate.validate_ballot) and puts any
non-contract material — non-v3 critical classes (example_sense_error,
mnemonic_quality_error), field notes, and the two locked rulings
(billion NOT a regression; deal/verb conditional resolution) — into a
separate annotations file. Bias note: sides here are the BLIND A/B
sides; nothing in this module loads the identity map.
"""

import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.adjudicate import record_judgments

OUT_DIR = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                       "output", "human_review_seeded30")
PKG_PATH = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                        "output", "eval_seeded348_v1",
                        "eval_seeded348_v1.json")

# id -> [definition, arabic, sense, examples, translations, relations,
# mnemonic] with A/B/tie (verbatim from the reviewer's table).
VERDICTS = {
    "eval_seeded348_v1-0040": ["tie","tie","tie","A","A","A","tie"],
    "eval_seeded348_v1-0006": ["tie","tie","tie","A","tie","tie","tie"],
    "eval_seeded348_v1-0010": ["tie","tie","tie","B","A","A","tie"],
    "eval_seeded348_v1-0139": ["tie","tie","tie","A","A","A","tie"],
    "eval_seeded348_v1-0052": ["tie","B","tie","B","tie","B","tie"],
    "eval_seeded348_v1-0336": ["tie","tie","tie","B","tie","B","tie"],
    "eval_seeded348_v1-0299": ["tie","tie","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0153": ["B","B","tie","B","tie","B","tie"],
    "eval_seeded348_v1-0317": ["tie","tie","tie","B","tie","B","tie"],
    "eval_seeded348_v1-0114": ["tie","tie","tie","A","A","tie","tie"],
    "eval_seeded348_v1-0311": ["tie","tie","tie","A","A","A","tie"],
    "eval_seeded348_v1-0119": ["B","B","tie","B","B","B","tie"],
    "eval_seeded348_v1-0093": ["tie","A","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0273": ["tie","tie","tie","A","tie","tie","tie"],
    "eval_seeded348_v1-0200": ["tie","tie","tie","B","tie","A","A"],
    "eval_seeded348_v1-0018": ["tie","tie","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0071": ["tie","tie","B","B","tie","tie","tie"],
    "eval_seeded348_v1-0072": ["tie","tie","tie","B","tie","B","tie"],
    "eval_seeded348_v1-0145": ["tie","B","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0245": ["B","B","tie","B","tie","tie","tie"],
    "eval_seeded348_v1-0023": ["tie","tie","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0208": ["tie","tie","tie","A","tie","tie","tie"],
    "eval_seeded348_v1-0149": ["tie","tie","tie","A","tie","tie","tie"],
    "eval_seeded348_v1-0046": ["tie","A","tie","A","A","A","tie"],
    "eval_seeded348_v1-0166": ["tie","tie","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0029": ["tie","tie","tie","A","tie","tie","tie"],
    "eval_seeded348_v1-0129": ["A","A","tie","A","tie","A","A"],
    "eval_seeded348_v1-0057": ["tie","A","tie","A","tie","A","tie"],
    "eval_seeded348_v1-0260": ["tie","tie","tie","A","tie","tie","tie"],
    "eval_seeded348_v1-0287": ["A","A","tie","A","tie","A","tie"],
}

FIELDS7 = ("definition", "arabic_explanation", "sense_separation",
           "examples", "translations", "relations", "mnemonic")

# v3 critical_errors (side is the offending blind arm).
CRITICALS_V3 = {
    "eval_seeded348_v1-0311": {"invalid_relation_synonym": "B"},
    "eval_seeded348_v1-0119": {"invalid_relation_synonym": "A"},
    "eval_seeded348_v1-0093": {"invalid_relation_synonym": "B"},
    "eval_seeded348_v1-0018": {"invalid_relation_synonym": "A"},
    "eval_seeded348_v1-0287": {"invalid_relation_synonym": "B"},
}

# Non-contract material, kept OUT of the ballot, by eval_id.
ANNOTATIONS = {
    "eval_seeded348_v1-0010": [{
        "type": "note", "side": "A",
        "text": "A mnemonic ('Edge') considered weak by the reviewer."}],
    "eval_seeded348_v1-0299": [{
        "type": "note", "side": "B",
        "text": "B relations overly broad (rays/sun/beam)."}],
    "eval_seeded348_v1-0153": [{
        "type": "note", "side": "A",
        "text": "A example 'import data from other files' is a software/"
               "data-import sense not established by definition (note, "
               "not a critical)."}],
    "eval_seeded348_v1-0071": [{
        "type": "non_v3_critical", "class": "example_sense_error",
        "side": "A",
        "text": "'a great deal of work' (quantity sense) and 'raw deal' "
               "(treatment sense) are not covered by the agreement/"
               "transaction definition."}],
    "eval_seeded348_v1-0072": [{
        "type": "non_v3_critical", "class": "example_sense_error",
        "side": "A", "conditional_resolved": True,
        "text": "A (legacy) includes 'deal a blow to the regime'; the "
               "displayed A definition covers deal-with and cards only, "
               "and the full record (candidate senses 1-2) also does NOT "
               "separate the 'deal a blow' sense => example_sense_error "
               "on A per the reviewer's conditional rule."}],
    "eval_seeded348_v1-0245": [{
        "type": "non_v3_critical", "class": "mnemonic_quality_error",
        "side": "A",
        "text": "Volcano is a weak indirect association for 'provoke' "
               "(note: shared mnemonic text; flaw attached to side A "
               "per the reviewer)."}],
    "eval_seeded348_v1-0023": [{
        "type": "note", "side": "B",
        "text": "B example 'pure awareness meditation' is specialized "
               "but not necessarily wrong — explicitly NOT a critical."}],
    "eval_seeded348_v1-0029": [{
        "type": "locked_fact", "side": None,
        "text": "billion/num is NOT a regression: both arms are correct, "
               "differ only in phrasing; numerals in A do not make the "
               "definition less accurate."}],
    "eval_seeded348_v1-0129": [{
        "type": "note", "side": "B",
        "text": "B examples include idiomatic/extended uses (poke fun, "
               "good fun) without sense separation; noted, not a "
               "critical."}],
    "eval_seeded348_v1-0046": [{
        "type": "operator_flag", "side": None,
        "text": "arbitration flag: A and B arabic strings are byte-"
               "identical yet arabic was recorded A-better; keeping "
               "verbatim, flagged for the reconciliation."}],
    "eval_seeded348_v1-0200": [{
        "type": "operator_flag", "side": None,
        "text": "arbitration flag: A and B mnemonic strings are byte-"
               "identical yet mnemonic was recorded A-better; keeping "
               "verbatim, flagged for the reconciliation."}],
    "eval_seeded348_v1-0311": [{
        "type": "note", "side": "B",
        "text": "B lists 'that' as BOTH synonym and antonym of 'this' — "
               "self-contradiction; the invalid_relation_synonym "
               "critical is recorded."}],
}


def build_ballots():
    ballots = {}
    for eval_id, verdicts in VERDICTS.items():
        fields = {f: ("%s-better" % v if v in ("A", "B") else v)
                  for f, v in zip(FIELDS7, verdicts)}
        critical_errors = {}
        for cls in ("wrong_meaning", "misleading_arabic",
                    "invalid_relation_synonym", "example_semantic_error",
                    "target_word_violation",
                    "fabricated_etymology_mnemonic",
                    "cefr_learner_mismatch"):
            side = CRITICALS_V3.get(eval_id, {}).get(cls)
            critical_errors[cls] = {"side": side, "evidence": ""}
        ballots[eval_id] = {"fields": fields,
                            "critical_errors": critical_errors,
                            "note": ""}
    return ballots


def main():
    with open(PKG_PATH, encoding="utf-8") as f:
        package_items = json.load(f)["items"]
    ballots = build_ballots()
    assert set(ballots) == set(VERDICTS)
    missing = set(VERDICTS) - {c["eval_id"] for c in package_items}
    assert not missing, missing
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "human_judgments_30.json")
    record_judgments(package_items, ballots, path)
    annotations_path = os.path.join(OUT_DIR, "human30_annotations.json")
    with open(annotations_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": "human30", "annotations": ANNOTATIONS},
                  f, ensure_ascii=False, indent=1)
    print("ballots:", path, "(%d cards)" % len(ballots))
    print("annotations:", annotations_path)
    for eval_id, entry in CRITICALS_V3.items():
        print("v3 critical: %s %r" % (eval_id, entry))
    return path


if __name__ == "__main__":
    main()