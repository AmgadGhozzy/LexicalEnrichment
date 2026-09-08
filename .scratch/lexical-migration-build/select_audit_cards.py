#!/usr/bin/env python3
"""FROZEN post-scale human-audit card selection (BT-14).

Pre-registered procedure (seed 356014), executed for the first time
here. Purpose: give the human auditor 10-15 blind cards to decide
whether v3's conservatism is stable-and-useful or collapses into
tie/cannot-judge.

Selection constraints (all binding, none relaxed):
- operates ONLY on (eval_id, lemma, pos, AI field verdicts) —
  never touches eval_identity_map.json; no decode anywhere.
- completed judgments = progress.json judgments, minus the 4
  monitor items (EVAL-BLIND-V1-0006/0014/0019/0020).
- strata (disjoint-by-intent, overlaps allowed):
  sense_abstain : sense_separation == cannot-judge
  tie_heavy     : >= 4 of 7 fields == tie
  strong_decided: >= 5 of 7 fields in {A-better,B-better}
  polysemy      : lemma appears >1x across the whole blind package
- draw min(3, |stratum|) from each stratum via random.Random(SEED).
- output audit_cards.json (identity-free: eval_id/lemma/pos/strata)
  + a records block with the effective seed, strata sizes, and hash.
"""

import hashlib
import json
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = ROOT + "/output"
PROGRESS = os.path.join(OUT_ROOT, "ai_judge_356/progress.json")
PACKAGE = os.path.join(OUT_ROOT, "eval_blind_v1/eval_blind_v1.json")
AUDIT_DIR = os.path.join(OUT_ROOT, "audit")

SEED = 356014
PER_STRATUM = 3
MONITOR = {"EVAL-BLIND-V1-0006", "EVAL-BLIND-V1-0014",
           "EVAL-BLIND-V1-0019", "EVAL-BLIND-V1-0020"}

FIELDS = ["definition", "arabic_explanation", "sense_separation",
          "examples", "translations", "relations", "mnemonic"]


def main():
    with open(PROGRESS, encoding="utf-8") as f:
        J = json.load(f)["judgments"]
    with open(PACKAGE, encoding="utf-8") as f:
        items = {x["eval_id"]: x for x in json.load(f)["items"]}

    lemma_count = {}
    for x in items.values():
        lemma_count[x["lemma"]] = lemma_count.get(x["lemma"], 0) + 1

    done = sorted(set(J) - MONITOR)

    def stratum_fn(eid):
        f = J[eid]["fields"]
        vals = list(f.values())
        s = []
        if f["sense_separation"] == "cannot-judge":
            s.append("sense_abstain")
        if sum(1 for v in vals if v == "tie") >= 4:
            s.append("tie_heavy")
        if sum(1 for v in vals if v in ("A-better", "B-better")) >= 5:
            s.append("strong_decided")
        if lemma_count[items[eid]["lemma"]] > 1:
            s.append("polysemy")
        return s

    strata = {"sense_abstain": [], "tie_heavy": [],
              "strong_decided": [], "polysemy": []}
    for eid in done:
        for s in stratum_fn(eid):
            strata[s].append(eid)

    rng = random.Random(SEED)
    selected = []
    for name in ["sense_abstain", "tie_heavy", "strong_decided",
                 "polysemy"]:
        pool = strata[name]
        n = min(PER_STRATUM, len(pool))
        picks = rng.sample(pool, n)
        for eid in sorted(picks):
            selected.append({
                "eval_id": eid,
                "lemma": items[eid]["lemma"],
                "pos": items[eid]["pos"],
                "strata": stratum_fn(eid)})

    selected = sorted(selected, key=lambda r: r["eval_id"])
    os.makedirs(AUDIT_DIR, exist_ok=True)
    out = os.path.join(AUDIT_DIR, "audit_cards.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "seed": SEED,
            "per_stratum": PER_STRATUM,
            "completed_included": len(done),
            "stratum_sizes": {k: len(v) for k, v in strata.items()},
            "cards": selected,
        }, f, ensure_ascii=False, indent=1)

    blob = json.dumps(selected, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    print("audit set => %s" % out)
    print("cards:", len(selected))
    for c in selected:
        print("  %s %s/%s %s" % (c["eval_id"], c["lemma"], c["pos"],
                                 ",".join(c["strata"])))
    print("selection hash:", digest)


if __name__ == "__main__":
    main()