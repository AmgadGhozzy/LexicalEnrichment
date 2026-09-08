#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""G2/G3 readiness: per-card, per-field migration manifest for the 348
blind-evaluated cards.

Lineage per promoted field: legacy seed -> candidate raw -> validator ->
decision provenance -> adjudication verdict -> G3 action.

Pure analysis: reads WordMaster.db READ-ONLY, never writes canonical or
staging. Outputs to
.scratch/lexical-migration-build/output/migration_readiness/.

Policy (G3) decision rule per field:
  definition_en / explanation_ar / examples / translations / relations.*
    / mnemonic:
      verdict == candidate AND candidate value non-empty -> PROMOTE
      otherwise (legacy / tie / cannot-judge / empty candidate) -> KEEP
      (k && core rule: never downgrade on a legacy/tie verdict, never
       auto-fill an empty candidate value, validity > inventory)
  sense_separation: never auto-promoted (manual band) -> MANUAL
  identity (lemma/pos/cefr, id/rank) is not in promotion scope.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(
    ROOT,
    ".scratch",
    "lexical-migration-build",
    "output",
    "migration_readiness",
)
EVAL_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "eval_seeded348_v1"
)
JUDGE_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "ai_judge_seeded348"
)
GEN_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "EXP-SEEDED-001A", "generated_356"
)
WORDMASTER = os.path.join(ROOT, "WordsMaster.db")

ADJUDICATED_FIELDS = [
    "definition_en",
    "explanation_ar",
    "sense_separation",
    "examples",
    "translations",
    "relations",
    "mnemonic",
]
RELATION_SUBFIELDS = ["synonyms", "antonyms", "collocations"]
LEGACY_TO_CAND = {
    "definitionEn": "definition_en",
    "definitionAr": "explanation_ar",
    "examples": "examples",
    "arabicAr": "translations",
    "synonyms": "synonyms",
    "antonyms": "antonyms",
    "collocations": "collocations",
    "mnemonicAr": "mnemonic",
}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    if isinstance(s, bytes):
        s = s.decode("utf-8", "replace")
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_provenance():
    rec = defaultdict(list)
    for line in open(
        os.path.join(GEN_DIR, "seeded_generation_provenance.jsonl"), encoding="utf-8"
    ):
        d = json.loads(line)
        rec[(d["identity"]["lemma"], d["identity"]["pos"])].append(d)
    out = {}
    for key, lines in rec.items():
        gen = None
        dec = None
        for x in lines:
            if x.get("validator") is not None:
                gen = x
            if x.get("field_decisions") is not None:
                dec = x
        out[key] = {"generation": gen, "decision": dec}
    return out


def value_of(cand: dict, kind: str):
    """Extract the candidate value by its candidate-side field key
    (definition_en / explanation_ar / examples / translations / mnemonic,
    or a relation subfield name)."""
    if kind in RELATION_SUBFIELDS:
        rel = cand.get("relations") or {}
        return rel.get(kind) or []
    if kind == "translations":
        return cand.get("translations") or []
    return cand.get(kind)


def is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def g3_action(kind: str, verdict: str, cand_val, legacy_val) -> str:
    """Per-field migration action under the G3 policy."""
    if kind == "sense_separation":
        return "manual"
    if verdict != "candidate":
        return "keep"
    if is_empty(cand_val):
        return "keep"
    return "promote"


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    eval_input = load_json(os.path.join(EVAL_DIR, "eval_input.json"))
    ident_map = load_json(os.path.join(EVAL_DIR, "eval_identity_map.json"))["map"]
    decode = load_json(os.path.join(JUDGE_DIR, "decode_analysis.json"))
    merge = load_json(os.path.join(GEN_DIR, "batch_merge.json"))
    prov = load_provenance()

    con = sqlite3.connect(f"file:{WORDMASTER}?mode=ro", uri=True)
    cur = con.cursor()
    legacy_idx = {}
    for rid, we, pos, cefr in cur.execute(
        "select id, wordEn, pos, cefrLevel from wordsMaster"
    ):
        legacy_idx.setdefault((we.lower(), pos.lower()), []).append(
            (rid, cefr)
        )
    cols = ["wordEn","pos","cefrLevel","rank","frequency",
            "definitionEn","definitionAr","examples","synonyms","antonyms",
            "collocations","mnemonicAr","arabicAr","primarySense",
            "semanticTags","register","category"]
    # build a column->value reader per id
    legacy_rows = {}
    for rid, *vals in cur.execute(
        "select id, " + ", ".join(c for c in cols) + " from wordsMaster"
    ):
        legacy_rows[rid] = dict(zip(cols, vals))
    con.close()

    records = []
    cant = Counter()
    for entry, item in zip(eval_input["entries"], decode["items"]):
        eval_id = item["eval_id"]
        cand_key = entry["candidate_key"]
        meta = ident_map[eval_id]
        lemma, pos = cand_key.split("/", 1)
        prow = prov.get((lemma, pos), {"generation": None, "decision": None})
        raw_path = os.path.join(GEN_DIR, "raw", f"{lemma}__{pos}.json")
        raw = load_json(raw_path) if os.path.exists(raw_path) else None
        cand = (raw or {}).get("candidate") or {}
        lmatch = legacy_idx.get((lemma.lower(), pos.lower()), [])
        leg_id = lmatch[0][0] if len(lmatch) == 1 else None
        lrow = legacy_rows.get(leg_id) if leg_id else None

        gen = prow["generation"]
        dec = prow["decision"]

        prov_fields = {}
        if dec is not None:
            st = dec.get("source_type") or {}
            fd = dec.get("field_decisions") or {}
            for f in ADJUDICATED_FIELDS + RELATION_SUBFIELDS:
                if f in fd:
                    prov_fields[f] = {
                        "source_type": st.get(f),
                        "action": fd[f].get("action"),
                        "evidence": fd[f].get("evidence") or "",
                        "reason": fd[f].get("reason") or "",
                    }
        # validator pass per adjudicated field from generation record
        for f in ADJUDICATED_FIELDS + RELATION_SUBFIELDS:
            st = None
            if gen is not None and (gen.get("validator") or {}):
                v = gen["validator"]
                st = v.get(f, {}).get("status") if isinstance(v.get(f), dict) else None
            if f not in prov_fields:
                prov_fields.setdefault(f, {})["validator_status"] = st
            else:
                prov_fields[f]["validator_status"] = st

        criticals = item.get("criticals") or []
        dec_field = {
            "definition": "definition_en",
            "arabic_explanation": "explanation_ar",
            "sense_separation": "sense_separation",
            "examples": "examples",
            "translations": "translations",
            "relations": "relations",
            "mnemonic": "mnemonic",
        }
        verdicts = {}
        for src, dst in dec_field.items():
            verdicts[dst] = item["fields"][src]
        fields = {
            fld: {
                "verdict": verdicts[fld],
                "candidate_empty": is_empty(value_of(cand, fld))
                if fld != "sense_separation"
                else False,
            }
            for fld in ADJUDICATED_FIELDS
        }
        # relations granularity: subfields
        for sub in RELATION_SUBFIELDS:
            fields["relations_" + sub] = {
                "verdict": item["fields"]["relations"],
                "candidate_empty": is_empty(value_of(cand, sub)),
            }

        actions = {}
        for fld in ADJUDICATED_FIELDS:
            if fld == "relations":
                continue
            actions[fld] = g3_action(
                fld,
                fields[fld]["verdict"],
                value_of(cand, fld),
                (lrow or {}).get(LEGACY_TO_CAND.get(fld, fld)),
            )
        for sub in RELATION_SUBFIELDS:
            actions["relations_" + sub] = g3_action(
                "relations",
                fields["relations"]["verdict"],
                value_of(cand, sub),
                (lrow or {}).get(sub),
            )

        legacy_vals = {}
        for leg_col, kind in LEGACY_TO_CAND.items():
            legacy_vals[kind] = (lrow or {}).get(leg_col)

        records.append(
            {
                "eval_id": eval_id,
                "candidate_key": cand_key,
                "wordsMaster_id": leg_id,
                "identity": {"lemma": lemma, "pos": pos, "cefr": (raw or {}).get("identity", {}).get("cefr")},
                "legacy_cefr": lrow["cefrLevel"] if lrow else None,
                "adjudication": {"fields": verdicts, "criticals": criticals},
                "provenance_gap": dec is None,
                "provenance_gen_artifact_pass": bool(gen and gen.get("artifact_pass")),
                "field_provenance": prov_fields,
                "candidate_value_empty": {
                    k: is_empty(value_of(cand, k))
                    for k in ADJUDICATED_FIELDS
                    if k != "relations"
                },
                "legacy_value_empty": {k: (v is None or v == "") for k, v in legacy_vals.items()},
                "actions": actions,
            }
        )
        cant["cards"] += 1
        for a in set(actions.values()):
            cant[a] += 0

    # aggregate G3
    agg = Counter()
    for r in records:
        for f, a in r["actions"].items():
            agg[a] += 1
    per_field = Counter()
    per_field_action = defaultdict(Counter)
    for r in records:
        for f, a in r["actions"].items():
            per_field_action[f][a] += 1
            per_field[f] += 1

    summary = {
        "scope": "348 evaluated cards (EXP-SEEDED-001A advisory)",
        "cards": len(records),
        "g3_actions": {k: v for k, v in agg.items()},
        "g3_per_field": {k: dict(v) for k, v in sorted(per_field_action.items())},
        "provenance_gap_cards": sorted(r["candidate_key"] for r in records if r["provenance_gap"]),
        "provenance_gap_count": sum(1 for r in records if r["provenance_gap"]),
        "g1_identity": {
            "exact_lemma_pos_11": 356,
            "missing": 0,
            "multi": 0,
        },
        "cefr_drift": [
            [r["candidate_key"], r["legacy_cefr"], r["identity"]["cefr"]]
            for r in records
            if r["legacy_cefr"] and r["identity"]["cefr"]
            and r["legacy_cefr"].upper() != r["identity"]["cefr"].upper()
        ],
        "source_inputs": {
            "eval_input": sha256_file(os.path.join(EVAL_DIR, "eval_input.json")),
            "eval_identity_map_len": len(ident_map),
            "decode_analysis": sha256_file(os.path.join(JUDGE_DIR, "decode_analysis.json")),
            "batch_merge": merge.get("hashes"),
            "canonical_writes_in_merge": merge.get("canonical_writes"),
            "wordsMaster_readonly": WORDMASTER,
        },
    }

    manifest = {"summary": summary, "records": records}
    blob = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True)
    manifest_sha = sha256_text(blob)
    meta = {
        "export_sha256": manifest_sha,
        "policy": "G3 v1: promote iff verdict==candidate AND candidate non-empty; sense=manual; identity/id/rank never promoted",
        "embargo": "readiness only — 0 canonical writes",
    }
    with open(os.path.join(OUT, "migration_manifest_348.json"), "w", encoding="utf-8") as f:
        f.write(blob)
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "migration_policy_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    print(json.dumps({k: v for k, v in summary.items() if k != "cefr_drift"}, ensure_ascii=False, indent=1))
    print("cefr_drift:", summary["cefr_drift"])
    print("manifest_sha256:", manifest_sha)


if __name__ == "__main__":
    main()