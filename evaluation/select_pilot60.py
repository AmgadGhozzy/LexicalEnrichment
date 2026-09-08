"""Stratified 60-word pilot sampler (EXP-SEEDED-001A).

Frozen procedure: deterministic stratified draw from the 356-record
seed snapshot. The 12 human-audit cards are MONITORING/REFERENCE
ONLY — they never reshape quotas; overlap is reported, not forced.
The 3 v1 smoke words are excluded from the pool (immutable v1
evidence; re-running them would confuse experiment lineage).

Quotas (locked for 001A):
  POS : noun 17 / verb 15 / adj 12 / adv 6 / function 10 (=60)
    (function=10 because hard-includes contain 9 mnemonic-null
    function words + since/conj polysemy; noun 17 keeps total 60)
  CEFR: A1 8 / A2 8 / B1 9 / B2 18 / C1 16 / C2 1 (=60)
  mnemonic-null: all 16 available (tiny pool, take all)
  multi-POS: all 6 records (3 lemmas: deal, since, spell)
  coverage floors (preference, not hard partitions):
    technical (Nature & Science + Health & Senses, pool 14): >=8
    multi-separator translations (pool 203): >=20
    relations-lean (total relations <= 5, pool 18; the corpus has
      no truly poor records, min total is 2): >=6

Method: hard-include the 16 mnemonic-null plus the 5 non-null
multi-POS records (since/prep is already among the nulls), then
greedy fill of the remaining 39 slots by largest POS/CEFR cell
deficit, preferring candidates that cover still-uncovered flags,
seeded-RNG tie-break. Fully deterministic given PILOT_SEED.
"""

import hashlib
import json
import os
import random
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.lexical_validator import contains_target
from evaluation.seeded_generator import load_seed_snapshot
from evaluation.seed_preservation import (
    field_is_valid, _has_content, _examples_text, _as_flat_list)

PILOT_SEED = 600114
PILOT_N = 60

QUOTAS_POS = {"noun": 17, "verb": 15, "adj": 12, "adv": 6,
              "function": 10}
QUOTAS_CEFR = {"A1": 8, "A2": 8, "B1": 9, "B2": 18, "C1": 16,
               "C2": 1}
FUNCTION_POS = {"prep", "conj", "pron", "det", "modal", "num",
                "excl"}
TECHNICAL_CATEGORIES = {"Nature & Science", "Health & Senses"}
SEPARATORS = ("؛", ";", "/", "،", ",")
SMOKE_KEYS = {("bottom", "adj"), ("refuse", "verb"),
              ("bucket", "noun")}


def pos_group(pos):
    p = (pos or "").strip().lower()
    if p in ("noun", "verb", "adj", "adv"):
        return p
    return "function"


def features(rec, multi_pos_lemmas):
    seed = rec["seed"]
    lemma = rec["lemma"]
    ex = seed.get("examples")
    ex_valid, _ = field_is_valid("examples", ex, lemma)
    texts = _examples_text(ex)
    target_all = (len(texts) == 3
                  and all(contains_target(t, lemma) for t in texts))
    translations = seed.get("translations")
    multi_trans = any(s in str(translations or "")
                      for s in SEPARATORS)
    syn = _as_flat_list(seed.get("synonyms"))
    ant = _as_flat_list(seed.get("antonyms"))
    collo = _as_flat_list(seed.get("collocations"))
    rel_total = len([x for x in syn + ant + collo
                     if str(x).strip()])
    # Corpus reality: no record has <2 relations (min is 2, one
    # record). "Lean" (<=5) is the poorest available stratum.
    lean = rel_total <= 5
    defn = seed.get("definition_en")
    def_valid, _ = field_is_valid("definition_en", defn, lemma)
    return {
        "lemma": lemma,
        "pos": rec.get("pos"),
        "cefr": rec.get("cefr"),
        "pos_group": pos_group(rec.get("pos")),
        "mnemonic_null": not _has_content(
            "mnemonic", seed.get("mnemonic")),
        "examples_contract": ex_valid,
        "examples_target_all": target_all,
        "examples_count": len(texts),
        "translations_multi": multi_trans,
        "relations_total": rel_total,
        "relations_poor": lean,
        "definition_valid": def_valid,
        "definition_len": len(str(defn or "")),
        "multi_pos": lemma.strip().lower() in multi_pos_lemmas,
        "technical": str(seed.get("category") or "")
        in TECHNICAL_CATEGORIES,
        "key": "%s/%s" % (lemma.strip().lower(),
                          (rec.get("pos") or "").strip().lower()),
    }


def annotate(records):
    by_lemma = {}
    for r in records:
        by_lemma.setdefault(r["lemma"].strip().lower(),
                            set()).add(
            (r.get("pos") or "").strip().lower())
    multi = {l for l, poses in by_lemma.items() if len(poses) > 1}
    feats = [features(r, multi) for r in records]
    return feats, multi


def audit_keys(out_dir):
    """(lemma,pos) keys of the 12 human-audit cards (monitoring)."""
    audit_path = os.path.join(
        ROOT_DIR, ".scratch", "lexical-migration-build", "output",
        "audit", "audit_cards.json")
    pkg_path = os.path.join(
        ROOT_DIR, ".scratch", "lexical-migration-build", "output",
        "eval_blind_v1", "eval_blind_v1.json")
    try:
        cards = json.load(open(audit_path, encoding="utf-8"))
        pkg = json.load(open(pkg_path, encoding="utf-8"))
    except OSError:
        return set()
    items = {it.get("eval_id"): it for it in pkg.get("items", [])}
    keys = set()
    for c in cards.get("cards", cards if isinstance(cards, list) else []):
        it = items.get(c.get("eval_id") if isinstance(c, dict) else c)
        if it:
            keys.add((it["lemma"].strip().lower(),
                      (it.get("pos") or "").strip().lower()))
    return keys


FLAG_ORDER = ("technical", "multi_pos", "translations_multi",
              "relations_poor")


def draw(feats, seed=PILOT_SEED):
    rng = random.Random(seed)
    pool = [f for f in feats if (f["lemma"].strip().lower(),
                                 (f["pos"] or "").strip().lower())
            not in SMOKE_KEYS]
    by_key = {f["key"]: f for f in pool}

    selected = []
    # Hard include: every mnemonic-null record + every multi-POS
    # record (since/prep is in both sets; tiny pools, take all).
    for f in pool:
        if f["mnemonic_null"] or f["multi_pos"]:
            selected.append(f)
    remaining = {f["key"]: f for f in pool
                 if f not in selected}

    need_pos = dict(QUOTAS_POS)
    need_cefr = dict(QUOTAS_CEFR)
    for f in selected:
        need_pos[f["pos_group"]] = need_pos.get(f["pos_group"], 0) - 1
        need_cefr[f["cefr"]] = need_cefr.get(f["cefr"], 0) - 1

    covered = {flag: sum(1 for f in selected if f[flag])
               for flag in FLAG_ORDER}

    while len(selected) < PILOT_N:
        # Largest-deficit POS and CEFR cells.
        pos_cands = sorted(
            ((k, v) for k, v in need_pos.items() if v > 0),
            key=lambda kv: (-kv[1], kv[0]))
        cefr_cands = sorted(
            ((k, v) for k, v in need_cefr.items() if v > 0),
            key=lambda kv: (-kv[1], kv[0]))
        if not pos_cands or not cefr_cands:
            break
        target_pos = pos_cands[0][0]
        target_cefr = cefr_cands[0][0]
        cands = [f for f in remaining.values()
                 if f["pos_group"] == target_pos
                 and f["cefr"] == target_cefr]
        if not cands:  # relax CEFR, then POS.
            cands = [f for f in remaining.values()
                     if f["pos_group"] == target_pos]
        if not cands:
            cands = [f for f in remaining.values()
                     if f["cefr"] == target_cefr]
        if not cands:
            cands = list(remaining.values())
        if not cands:
            break

        def score(f):
            bonus = sum(1 for flag in FLAG_ORDER
                        if f[flag] and covered[flag] < _floor(flag))
            return (bonus, rng.random())

        cands.sort(key=score, reverse=True)
        pick = cands[0]
        selected.append(pick)
        del remaining[pick["key"]]
        need_pos[pick["pos_group"]] -= 1
        need_cefr[pick["cefr"]] -= 1
        for flag in FLAG_ORDER:
            if pick[flag]:
                covered[flag] += 1

    assert len(selected) == PILOT_N, "quota fill failed: %d" % len(selected)
    for k, v in need_pos.items():
        assert v <= 0, "POS quota unmet: %s=%d" % (k, v)
    for k, v in need_cefr.items():
        assert v <= 0, "CEFR quota unmet: %s=%d" % (k, v)
    return selected


def _floor(flag):
    return {"technical": 8, "multi_pos": 6,
            "translations_multi": 20, "relations_poor": 6}[flag]


def selection_hash(selected, seed=PILOT_SEED):
    blob = json.dumps({"seed": seed, "quotas_pos": QUOTAS_POS,
                       "quotas_cefr": QUOTAS_CEFR,
                       "keys": sorted(f["key"] for f in selected)},
                      sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def write_pilot60(selected, out_path, snapshot_sha, seed=PILOT_SEED,
                  audit=None):
    payload = {
        "experiment": "EXP-SEEDED-001A",
        "pilot": "pilot60",
        "pilot_seed": seed,
        "quotas_pos": QUOTAS_POS,
        "quotas_cefr": QUOTAS_CEFR,
        "seed_snapshot_sha256": snapshot_sha,
        "selection_hash": selection_hash(selected, seed),
        "audit_overlap_monitoring_only": sorted(
            (audit or set()) & { (f["lemma"].strip().lower(),
                                  (f["pos"] or "").strip().lower())
                                 for f in selected}),
        "items": [{"lemma": f["lemma"], "pos": f["pos"],
                   "cefr": f["cefr"]} for f in selected],
        "features": {f["key"]: {k: f[k] for k in f if k != "key"}
                     for f in selected},
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)),
                exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1,
                  sort_keys=True)
    return payload


def main():
    snap = os.path.join(
        ROOT_DIR, ".scratch", "lexical-migration-build", "output",
        "EXP-SEEDED-001", "seed_snapshot_v1.jsonl")
    records = load_seed_snapshot(snap)
    import hashlib as _h
    snapshot_sha = _h.sha256(
        json.dumps(records, sort_keys=True,
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    feats, multi = annotate(records)
    selected = draw(feats)
    out = os.path.join(
        ROOT_DIR, ".scratch", "lexical-migration-build", "output",
        "EXP-SEEDED-001A", "pilot60.json")
    audit = audit_keys(ROOT_DIR)
    payload = write_pilot60(selected, out, snapshot_sha,
                            audit=audit)
    from collections import Counter
    print("selected:", len(selected))
    print("POS:", dict(Counter(f["pos_group"] for f in selected)))
    print("CEFR:", dict(Counter(f["cefr"] for f in selected)))
    print("mnemonic_null:", sum(1 for f in selected
                                if f["mnemonic_null"]))
    for flag in FLAG_ORDER:
        print("%s: %d" % (flag, sum(1 for f in selected
                                    if f[flag])))
    print("examples_contract_pass:",
          sum(1 for f in selected if f["examples_contract"]))
    print("audit overlap (monitoring only):",
          payload["audit_overlap_monitoring_only"])
    print("selection_hash:", payload["selection_hash"])
    return payload


if __name__ == "__main__":
    main()