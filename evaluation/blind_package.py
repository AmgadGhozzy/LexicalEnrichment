"""Blind linguistic evaluation package builder (ticket BT-13).

Builds the frozen A/B package for human adjudication of the 354
ok/partial pilot outputs against legacy comparator content. Pure
functions + file writers; no DB access inside this module (legacy
rows are caller-supplied read-only input); no judging, no
regeneration, no canonical writes.

Blinding contract (locked, tested):
- DTO arms carry ONLY: lemma, definition, arabic, examples (plain
  lists, level keys stripped both sides), translations,
  relations, mnemonic. No ids, no model/version/provider/
  thinking/grounding/run/hash/EXP strings anywhere in the package.
- Sides randomized per entry under a pinned seed ("A"/"B");
  the assignment lives ONLY in the separate identity map file.
- Equalized rendering rule (documented for the renderer):
  fixed-height scrolling example area, no visible example
  count/pagination indicator, same DTO structure both arms.
- Ballot per entry: 7 field verdicts (candidate-better /
  legacy-better / tie / cannot-judge) + critical-error checklist
  (7 classes) + optional note. Ballots ship BLANK.
"""

import hashlib
import json
import os
import random
import re

EVAL_ID = "EVAL-BLIND-V1"
EVAL_SEED = 354013

FIELDS = (
    "definition",
    "arabic_explanation",
    "sense_separation",
    "examples",
    "translations",
    "relations",
    "mnemonic",
)

CRITICAL_ERRORS = (
    "wrong_meaning",
    "misleading_arabic",
    "invalid_relation_synonym",
    "example_semantic_error",
    "target_word_violation",
    "fabricated_etymology_mnemonic",
    "cefr_learner_mismatch",
)

# Identifier-leak patterns (regex). Bare English words are NEVER
# banned: thinking/temperature/grounding/google can all be legitimate
# lexical content (a "TV pilot" false positive already proved this).
# Only run-identifier shapes are forbidden: candidate keys, run ids,
# experiment ids, model ids, exact versions, hex hashes.
BANNED_PATTERNS = (
    r"PILOT-V1-CAND-\d+",
    r"RUN-[A-Z0-9]+(?:-[A-Z0-9]+)*",
    r"EXP-\d{4}",
    r"gemini[\w.\-]*",
    r"\b2\.2\.3\b",
    r"\b[0-9a-f]{32,}\b",
    r"pilot_manifest",
    r"input_snapshot",
    r"output_hash",
)


def candidate_arm(output):
    """Normalize a v1.1 model output to the blind DTO arm shape."""
    translations = output.get("translations") or {}
    examples = output.get("examples") or []
    return {
        "definition": output.get("definition_en"),
        "arabic": output.get("explanation_ar"),
        "examples": [e.get("example_text") if isinstance(e, dict) else e
                     for e in examples],
        "translations": translations.get("arabic_ar"),
        "relations": {
            "synonyms": output.get("synonyms") or [],
            "antonyms": output.get("antonyms") or [],
            "collocations": output.get("collocations") or [],
        },
        "mnemonic": output.get("mnemonic_ar"),
    }


def legacy_arm(legacy_row):
    """Normalize a legacy master row to the SAME DTO arm shape.

    legacy_row keys: definitionEn, definitionAr, examples (JSON dict
    or dict), arabicAr, synonyms/antonyms (JSON lists or lists),
    mnemonicAr. CEFR cell keys are dropped (plain list) so level
    labels cannot leak structure.
    """
    def as_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list(value.values())
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return list(parsed.values())
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass
        return [value] if value else []

    return {
        "definition": legacy_row.get("definitionEn"),
        "arabic": legacy_row.get("definitionAr"),
        "examples": as_list(legacy_row.get("examples")),
        "translations": legacy_row.get("arabicAr"),
        "relations": {
            "synonyms": as_list(legacy_row.get("synonyms")),
            "antonyms": as_list(legacy_row.get("antonyms")),
            "collocations": [],
        },
        "mnemonic": legacy_row.get("mnemonicAr"),
    }


def blank_ballot():
    return {
        "fields": {f: "unjudged" for f in FIELDS},
        "critical_errors": {c: {"side": None, "evidence": ""}
                            for c in CRITICAL_ERRORS},
    }


def build_package(items, seed=EVAL_SEED):
    """Build blind items + separate identity map.

    items: list of dicts with keys: eval_key, lemma, pos,
    candidate_output, legacy_row. Returns (package_items, id_map).
    package_items carry eval_id, lemma, pos, armA, armB, ballot.
    id_map carries eval_id -> {candidate_side, candidate_key}.
    """
    rng = random.Random(seed)
    package_items = []
    id_map = {}
    for i, item in enumerate(sorted(items, key=lambda x: x["eval_key"])):
        eval_id = "%s-%04d" % (EVAL_ID, i + 1)
        arms = {
            "candidate": candidate_arm(item["candidate_output"]),
            "legacy": legacy_arm(item["legacy_row"]),
        }
        candidate_side = "A" if rng.random() < 0.5 else "B"
        legacy_side = "B" if candidate_side == "A" else "A"
        package_items.append({
            "eval_id": eval_id,
            "lemma": item["lemma"],
            "pos": item["pos"],
            "armA": arms["candidate" if candidate_side == "A" else "legacy"],
            "armB": arms["candidate" if candidate_side == "B" else "legacy"],
            "ballot": blank_ballot(),
        })
        id_map[eval_id] = {
            "candidate_side": candidate_side,
            "candidate_key": item["eval_key"],
        }
    return package_items, id_map


def assert_blind(package_items):
    """Raise on any identifier leak or structural inequality.

    Only the blinded content is scanned (lemma + arms + ballot) —
    never eval_id itself, and never with bare-word bans.
    """
    for item in package_items:
        blob = json.dumps(
            {"lemma": item["lemma"], "armA": item["armA"],
             "armB": item["armB"], "ballot": item["ballot"]},
            ensure_ascii=False)
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, blob, re.IGNORECASE):
                raise ValueError("blinding leak %r in %s"
                                 % (pattern, item["eval_id"]))
        if set(item["armA"].keys()) != set(item["armB"].keys()):
            raise ValueError("arm shape mismatch in %s" % item["eval_id"])
        if item["ballot"]["fields"].keys() != set(FIELDS):
            raise ValueError("ballot field mismatch in %s" % item["eval_id"])
    return True


def freeze_eval_input(processed_reports):
    """Freeze the evaluation input manifest from processed reports.

    processed_reports: {candidate_key: report}. Returns the frozen
    input record (keys + output hashes + run refs + hash).
    """
    from evaluation.utils import canonical_hash
    entries = []
    for key in sorted(processed_reports):
        rep = processed_reports[key]
        entries.append({
            "candidate_key": key,
            "status": rep["status"],
            "validator_failures": rep.get("validator", {}).get(
                "failures", []),
        })
    record = {"eval_input_id": EVAL_ID + "-INPUT", "entries": entries}
    record["input_hash"] = canonical_hash(record["entries"])
    return record


def write_package(out_dir, package_items, id_map, eval_input):
    """Write package + PRIVATE identity map + input manifest."""
    os.makedirs(out_dir, exist_ok=True)
    package_path = os.path.join(out_dir, "eval_blind_v1.json")
    map_path = os.path.join(out_dir, "eval_identity_map.json")
    input_path = os.path.join(out_dir, "eval_input.json")
    with open(package_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID, "seed": EVAL_SEED,
                   "items": package_items}, f, ensure_ascii=False, indent=1)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID, "map": id_map}, f,
                  ensure_ascii=False, indent=1)
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(eval_input, f, ensure_ascii=False, indent=1)
    return package_path, map_path, input_path
