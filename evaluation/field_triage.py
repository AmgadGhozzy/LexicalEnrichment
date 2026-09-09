"""Deterministic field-level triage engine — Ticket 17, rules v0.1 + C1 (FROZEN).

FROZEN per Ticket 17 closing verdict 2026-09-08 (DESIGN VALIDATED / RULES FROZEN).
Any rule change requires a new human-owner decision + same-sample-same-seed repeat.
Known limitation (not a failed gate): quote-glued tokens ("'freeze" != "freeze").

READ-ONLY by construction: the engine only labels (identity x field) records.
It never generates, never promotes, never writes to any canonical DB.
Quota breach => HALT (no manifest), never quota-tuning.

Usage:
  python -m evaluation.field_triage --mode sample-run --n 300 \\
      --db WordsMaster.db --out .scratch/lexical-migration-build/output/triage
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sqlite3
from pathlib import Path

from evaluation.lexical_validator import (
    GENERIC_NULL_VALUES,
    is_circular_definition,
    tokenize,
)

RULES_VERSION = "triage_rules_v1"
SAMPLE_SEED = "triage-sample-v1"
SOFT_ESCALATION_THRESHOLD = 2  # distinct soft-signal types -> escalate (R3b)

# Amendment 1: circuit breakers on the FLAGGED share (status != KEEP).
QUOTAS = {
    "examples": 0.35,
    "relations_synonyms": 0.30,
    "relations_antonyms": 0.30,
    "relations_collocations": 0.30,
    "translations": 0.30,
    "explanation_ar": 0.20,
    "definition_en": 0.20,
    "mnemonic": 0.20,
}
QUOTA_EXEMPT = frozenset({"sense_separation"})  # default MANUAL_REVIEW by design

FIELD_COL = {
    "definition_en": "definitionEn",
    "explanation_ar": "definitionAr",
    "examples": "examples",
    "translations": "arabicAr",
    "mnemonic": "mnemonicAr",
    "relations_synonyms": "synonyms",
    "relations_antonyms": "antonyms",
    "relations_collocations": "collocations",
    "sense_separation": None,
}

# Ticket 17 section 8: preset statuses, excluded from sampling and quotas.
EXCEPTION_IDS = frozenset({551, 1239, 3136, 1789, 4004, 4499, 2734, 412, 3628, 83, 3043, 3916})

TECHNICAL_CATEGORIES = frozenset({"Numbers, Time & Math", "Nature & Science", "Health & Senses"})

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
TERMINAL_PUNCT = (".", "!", "?", "\u061f", "\u06d4")


class QuotaBreach(Exception):
    def __init__(self, report):
        super().__init__("quota circuit breaker tripped; run HALTED for rule review")
        self.report = report


def _canon_json(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_cell(value) -> str:
    raw = "null" if value is None else str(value)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm_phrase(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("-", " ")).strip()


# C1 (Ticket 17, approved): finite regular-morphology closure. Suffix rules only,
# POS-gated so invalid forms are never generated (car/noun has no +ed "cared").
# No semantic inference, no open stemming, no synonyms/derivatives, no irregulars.
_VERB = frozenset({"verb"})
_NOMINAL = frozenset({"noun", "verb", "num"})
_COMPAR = frozenset({"adj", "adv"})
_SIBILANT_END = ("s", "x", "z", "ch", "sh")


def _cvc_double(w: str) -> str | None:
    if (len(w) >= 3 and w[-1] not in "aeiouwyx" and w[-2] in "aeiou"
            and w[-3] not in "aeiou"):
        return w + w[-1]
    return None


def lemma_form_closure(lemma: str, pos: str) -> frozenset:
    w = lemma.lower().strip()
    forms = {w}
    if pos in _NOMINAL:
        forms.add(w + "s")
        if w.endswith(_SIBILANT_END):
            forms.add(w + "es")
        if len(w) > 1 and w.endswith("y") and w[-2] not in "aeiou":
            forms.add(w[:-1] + "ies")
    if pos in _VERB:
        if w.endswith("e"):
            forms.add(w + "d")
            forms.add(w[:-1] + "ing")
        else:
            forms.add(w + "ed")
            forms.add(w + "ing")
        if len(w) > 1 and w.endswith("y") and w[-2] not in "aeiou":
            forms.add(w[:-1] + "ied")
        d = _cvc_double(w)
        if d:
            forms.add(d + "ed")
            forms.add(d + "ing")
    if pos in _COMPAR:
        if w.endswith("e"):
            forms.add(w + "r")
            forms.add(w + "st")
        else:
            forms.add(w + "er")
            forms.add(w + "est")
        if len(w) > 1 and w.endswith("y") and w[-2] not in "aeiou":
            forms.add(w[:-1] + "ier")
            forms.add(w[:-1] + "iest")
        d = _cvc_double(w)
        if d:
            forms.add(d + "er")
            forms.add(d + "est")
    return frozenset(forms)


def _phrase_variants(lemma_norm: str, pos: str) -> set:
    """Base phrase + one-token-substituted variants (each token position once)."""
    toks = lemma_norm.split()
    variants = {" ".join(toks)}
    for i, tok in enumerate(toks):
        for form in lemma_form_closure(tok, pos):
            if form != tok:
                variants.add(" ".join(toks[:i] + [form] + toks[i + 1:]))
    return variants


def target_present(example_text: str, lemma: str, pos: str) -> bool:
    """C1 target check. Single token -> any closure form as exact token.
    Multi-word lemma -> base phrase or one-token-inflected phrase as substring.
    Irregular forms (drank/went) are NOT matched: documented HARD-signal residue."""
    if not example_text or not lemma:
        return False
    ln = _norm_phrase(lemma)
    if " " in ln:
        en = _norm_phrase(example_text)
        return any(v in en for v in _phrase_variants(ln, pos))
    return bool(lemma_form_closure(ln, pos) & set(tokenize(example_text)))


def _record(identity, field, value, status, defect_code, evidence,
            requires_llm=False, requires_human=False):
    return {
        "identity": identity,
        "field": field,
        "current_value_hash": sha_cell(value),
        "triage_status": status,
        "defect_code": defect_code,
        "evidence": evidence,
        "requires_llm": requires_llm,
        "requires_human": requires_human,
    }


def _keep(identity, field, value, checked):
    return _record(identity, field, value, "KEEP", None, {"checked": checked})


def triage_definition_en(identity, lemma, value):
    if value is None or not str(value).strip():
        return _record(identity, "definition_en", value, "LLM_REVIEW", "DEF_EMPTY",
                        {"checked": "non_empty"}, True, False)
    if str(value).strip().lower() in GENERIC_NULL_VALUES:
        return _record(identity, "definition_en", value, "LLM_REVIEW", "DEF_GENERIC_NULL",
                        {"checked": "generic_null"}, True, False)
    if is_circular_definition(str(value), lemma):
        return _record(identity, "definition_en", value, "LLM_REVIEW", "DEF_CIRCULAR",
                        {"checked": "circularity"}, True, False)
    return _keep(identity, "definition_en", value, ["non_empty", "generic_null", "circularity"])


def triage_explanation_ar(identity, value):
    if value is None or not str(value).strip():
        return _record(identity, "explanation_ar", value, "LLM_REVIEW", "AR_EMPTY",
                        {"checked": "non_empty"}, True, False)
    if str(value).strip().lower() in GENERIC_NULL_VALUES:
        return _record(identity, "explanation_ar", value, "LLM_REVIEW", "AR_GENERIC_NULL",
                        {"checked": "generic_null"}, True, False)
    if not ARABIC_RE.search(str(value)):
        return _record(identity, "explanation_ar", value, "LLM_REVIEW", "AR_NO_ARABIC_SCRIPT",
                        {"checked": "arabic_script"}, True, False)
    return _keep(identity, "explanation_ar", value, ["non_empty", "generic_null", "arabic_script"])


def triage_examples(identity, lemma, pos, value):
    field = "examples"
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except (json.JSONDecodeError, TypeError):
        parsed = None
    # C1 array-format branch: legacy JSON-array-of-strings parses deterministically
    # before content checks; never "malformed" if the content itself is valid.
    if isinstance(parsed, list):
        if not parsed or not all(isinstance(s, str) for s in parsed):
            return _record(identity, field, value, "LLM_REVIEW", "EX_MALFORMED_JSON",
                            {"checked": "json_array_of_strings"}, True, False)
        bands = {f"arr{i}": s for i, s in enumerate(parsed)}
        fmt = "array"
    elif isinstance(parsed, dict) and parsed:
        bands = parsed
        fmt = "object"
    else:
        return _record(identity, field, value, "LLM_REVIEW", "EX_MALFORMED_JSON",
                        {"checked": "json_bands"}, True, False)
    failing_target, empty_bands, softs = [], [], []
    texts = {}
    for band, sent in bands.items():
        if not isinstance(sent, str) or not sent.strip():
            empty_bands.append(band)
            continue
        texts[band] = sent
        if not target_present(sent, lemma, pos):
            failing_target.append(band)
        s = sent.strip()
        if not s.endswith(TERMINAL_PUNCT):
            softs.append({"band": band, "signal": "EX_NO_TERMINAL_PUNCT"})
        if s[0].isalpha() and s[0] != s[0].upper():
            softs.append({"band": band, "signal": "EX_LEADING_LOWERCASE"})
    if empty_bands:
        return _record(identity, field, value, "LLM_REVIEW", "EX_EMPTY_BAND",
                        {"checked": "non_empty_bands", "format": fmt,
                         "empty_bands": empty_bands}, True, False)
    if failing_target:
        return _record(identity, field, value, "LLM_REVIEW", "EX_NO_LEMMA_TOKEN",
                        {"checked": "contains_target", "format": fmt,
                         "failing_bands": failing_target}, True, False)
    norm_texts = [_norm_phrase(t) for t in texts.values()]
    if len(set(norm_texts)) < len(norm_texts):
        return _record(identity, field, value, "LLM_REVIEW", "EX_DUPLICATE_BANDS",
                        {"checked": "band_uniqueness", "format": fmt}, True, False)
    soft_types = sorted({s["signal"] for s in softs})
    if len(soft_types) >= SOFT_ESCALATION_THRESHOLD:
        return _record(identity, field, value, "LLM_REVIEW", "EX_SOFT_ESCALATION",
                        {"checked": "soft_combination", "format": fmt,
                         "soft_signals": softs}, True, False)
    ev = {"checked": ["json_bands", "non_empty_bands", "contains_target", "band_uniqueness"],
          "format": fmt}
    if softs:
        ev["soft_signals"] = softs
    return _record(identity, field, value, "KEEP", None, ev)


def triage_translations(identity, value):
    field = "translations"
    if value is None or not str(value).strip():
        return _record(identity, field, value, "LLM_REVIEW", "TR_EMPTY",
                        {"checked": "non_empty"}, True, False)
    slots = [s.strip() for s in str(value).split("/") if s.strip()]
    if not slots:
        return _record(identity, field, value, "LLM_REVIEW", "TR_EMPTY",
                        {"checked": "non_empty_slots"}, True, False)
    lowered = [s.lower() for s in slots]
    if len(set(lowered)) < len(lowered):
        return _record(identity, field, value, "LLM_REVIEW", "TR_DUPLICATE_SLOTS",
                        {"checked": "slot_uniqueness", "slot_count": len(slots)}, True, False)
    ev = {"checked": ["non_empty_slots", "slot_uniqueness"], "slot_count": len(slots)}
    if not ARABIC_RE.search(str(value)):
        ev["soft_signals"] = [{"signal": "TR_NO_ARABIC_SCRIPT"}]
    return _record(identity, field, value, "KEEP", None, ev)


def triage_mnemonic(identity, value):
    field = "mnemonic"
    if value is None:
        return _record(identity, field, value, "KEEP", None,
                        {"checked": ["null_valid"], "null_valid": True})
    if not isinstance(value, str):
        return _record(identity, field, value, "MANUAL_REVIEW", "MNE_INVALID_TYPE",
                        {"checked": ["type_is_string_or_null"]}, False, True)
    if not value.strip():
        return _record(identity, field, value, "DETERMINISTIC_REPAIR", "MNE_EMPTY_STRING",
                        {"checked": ["non_empty"], "proposed_fix": "normalize_to_null"}, False, False)
    if value.strip().lower() in GENERIC_NULL_VALUES:
        return _record(identity, field, value, "DETERMINISTIC_REPAIR", "MNE_GENERIC_NULL",
                        {"checked": ["generic_null"], "proposed_fix": "normalize_to_null"}, False, False)
    return _keep(identity, field, value, ["type_is_string_or_null", "non_empty", "generic_null"])


def _parse_rel_list(value):
    if value is None:
        return None
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except (json.JSONDecodeError, TypeError):
        return False
    return parsed if isinstance(parsed, list) else False


def triage_relations(identity, lemma, syn_value, ant_value, col_value):
    """Returns 3 records (synonyms/antonyms/collocations). Empty [] and NULL are
    NOT defects (Amendment 4); evidence distinguishes inventory_empty/inventory_null."""
    recs = []
    parsed = {}
    for field, value in (("relations_synonyms", syn_value),
                         ("relations_antonyms", ant_value),
                         ("relations_collocations", col_value)):
        pl = _parse_rel_list(value)
        if pl is False:
            recs.append(_record(identity, field, value, "LLM_REVIEW", "REL_MALFORMED_JSON",
                                 {"checked": "json_array"}, True, False))
            parsed[field] = None
            continue
        if pl is None:
            recs.append(_record(identity, field, value, "KEEP", None,
                                 {"checked": ["inventory"], "inventory_null": True}))
            parsed[field] = []
            continue
        bad_items = [i for i in pl if not isinstance(i, str)]
        if bad_items:
            recs.append(_record(identity, field, value, "LLM_REVIEW", "REL_INVALID_ITEM",
                                 {"checked": "string_items"}, True, False))
            parsed[field] = None
            continue
        norm_items = [_norm_phrase(i) for i in pl]
        if [i for i in norm_items if i == _norm_phrase(lemma)]:
            recs.append(_record(identity, field, value, "LLM_REVIEW", "REL_SELF_REFERENCE",
                                 {"checked": "self_reference"}, True, False))
            parsed[field] = None
            continue
        if len(set(norm_items)) < len(norm_items):
            recs.append(_record(identity, field, value, "LLM_REVIEW", "REL_DUPLICATES",
                                 {"checked": "item_uniqueness", "item_count": len(pl)}, True, False))
            parsed[field] = None
            continue
        parsed[field] = pl
        recs.append(None)  # placeholder; overlap/soft checks below
    syn = parsed.get("relations_synonyms") or []
    ant = parsed.get("relations_antonyms") or []
    overlap = sorted({_norm_phrase(i) for i in syn} & {_norm_phrase(i) for i in ant})
    out = []
    for rec, (field, value) in zip(recs, (("relations_synonyms", syn_value),
                                          ("relations_antonyms", ant_value),
                                          ("relations_collocations", col_value))):
        if rec is not None:
            out.append(rec)
            continue
        items = parsed[field]
        ev = {"checked": ["json_array", "string_items", "self_reference", "item_uniqueness"],
              "item_count": len(items),
              "inventory_empty": len(items) == 0}
        if field in ("relations_synonyms", "relations_antonyms") and overlap:
            out.append(_record(identity, field, value, "LLM_REVIEW", "REL_SYN_ANT_OVERLAP",
                               {"checked": "syn_ant_disjoint", "overlap": overlap}, True, False))
            continue
        if field == "relations_collocations":
            missing = [i for i in items if _norm_phrase(lemma) not in _norm_phrase(i)]
            if missing:
                ev["soft_signals"] = [{"signal": "REL_COLLOCATION_NO_TARGET",
                                       "count": len(missing)}]
        out.append(_record(identity, field, value, "KEEP", None, ev))
    return out


def triage_sense(identity, primary_sense):
    """Amendment 2: in-scope, default MANUAL_REVIEW, quota-exempt. No judgment."""
    return _record(identity, "sense_separation", primary_sense, "MANUAL_REVIEW", None,
                    {"reason": "default_manual_per_G3", "primary_sense": primary_sense},
                    False, True)


def triage_card(row: dict) -> list:
    """Row keys: id, wordEn, pos, primarySense + the 8 content columns. Pure function."""
    identity = {"id": row["id"], "lemma": row["wordEn"], "pos": row["pos"]}
    lemma = row["wordEn"]
    return [
        triage_definition_en(identity, lemma, row.get("definitionEn")),
        triage_explanation_ar(identity, row.get("definitionAr")),
        triage_examples(identity, lemma, row["pos"], row.get("examples")),
        triage_translations(identity, row.get("arabicAr")),
        triage_mnemonic(identity, row.get("mnemonicAr")),
        *triage_relations(identity, lemma, row.get("synonyms"),
                          row.get("antonyms"), row.get("collocations")),
        triage_sense(identity, row.get("primarySense")),
    ]


def quota_report(records: list) -> dict:
    by_field: dict = {}
    for r in records:
        f = r["field"]
        if f in QUOTA_EXEMPT:
            continue
        b = by_field.setdefault(f, {"total": 0, "flagged": 0})
        b["total"] += 1
        if r["triage_status"] != "KEEP":
            b["flagged"] += 1
    report = {}
    breached = []
    for f in sorted(by_field):
        total = by_field[f]["total"]
        flagged = by_field[f]["flagged"]
        rate = (flagged / total) if total else 0.0
        quota = QUOTAS[f]
        is_breach = rate > quota
        report[f] = {"total": total, "flagged": flagged,
                     "flag_rate": round(rate, 4), "quota": quota, "breached": is_breach}
        if is_breach:
            breached.append(f)
    return {"per_field": report, "breached": breached, "halted": bool(breached)}


def check_quotas_or_halt(records: list) -> dict:
    report = quota_report(records)
    if report["halted"]:
        raise QuotaBreach(report)
    return report


# --------------------------------------------------------------------------
# Sampling (deterministic; read-only)
# --------------------------------------------------------------------------

def build_sample(con, n=300, seed=SAMPLE_SEED, exclude_ids=EXCEPTION_IDS,
                 wave1_ids=frozenset()) -> dict:
    rows = con.execute(
        "SELECT id, wordEn, pos, cefrLevel, category FROM wordsMaster").fetchall()
    pool = [r for r in rows if r[0] not in exclude_ids]
    by_stratum: dict = {}
    for _id, lemma, pos, cefr, cat in pool:
        by_stratum.setdefault((cefr, pos), []).append((_id, lemma, pos, cefr, cat))
    total = len(pool)
    rng = random.Random(seed)
    for members in by_stratum.values():
        rng.shuffle(members)
    alloc = {}
    fractions = []
    assigned = 0
    for key, members in by_stratum.items():
        exact = n * len(members) / total
        base = min(int(exact), len(members))
        alloc[key] = base
        assigned += base
        if base < len(members):
            fractions.append((exact - base, key))
    fractions.sort(reverse=True)
    i = 0
    while assigned < n and fractions:
        key = fractions[i % len(fractions)][1]
        if alloc[key] < len(by_stratum[key]):
            alloc[key] += 1
            assigned += 1
        i += 1
        if i > len(fractions) * (n + 1):
            break
    # floors for tiny strata
    for key, members in by_stratum.items():
        want = min(2, len(members))
        while alloc[key] < want and assigned < n:
            alloc[key] += 1
            assigned += 1
    chosen = []
    for key, members in by_stratum.items():
        chosen.extend(members[:alloc[key]])
    chosen_ids = [c[0] for c in chosen]

    def meets(ids):
        idset = set(ids)
        by_id = {r[0]: r for r in pool}
        multi = sum(1 for _id in idset
                    if sum(1 for r in pool if r[1] == by_id[_id][1] and r[2] != by_id[_id][2]) > 0)
        tech = sum(1 for _id in idset if by_id[_id][4] in TECHNICAL_CATEGORIES)
        w1 = sum(1 for _id in idset if _id in wave1_ids)
        return {"multi_pos": multi, "technical": tech, "wave1": w1}

    quotas = {"multi_pos": 15, "technical": 10, "wave1": 25}
    by_id = {r[0]: r for r in pool}
    multi_pool = [_id for _id, r in by_id.items()
                  if sum(1 for x in pool if x[1] == r[1] and x[2] != r[2]) > 0]
    tech_pool = [_id for _id, r in by_id.items() if r[4] in TECHNICAL_CATEGORIES]
    w1_pool = [_id for _id in wave1_ids if _id in by_id]
    for name, need, cand_pool in (("multi_pos", 15, multi_pool),
                                  ("technical", 10, tech_pool),
                                  ("wave1", 25, w1_pool)):
        have = meets(chosen_ids)[name]
        cands = [_id for _id in cand_pool if _id not in chosen_ids]
        rng.shuffle(cands)
        victims = [_id for _id in chosen_ids
                   if _id not in multi_pool and _id not in tech_pool and _id not in wave1_ids]
        rng.shuffle(victims)
        while have < need and cands and victims:
            old = victims.pop()
            new = cands.pop()
            chosen_ids[chosen_ids.index(old)] = new
            have += 1
    final_q = meets(chosen_ids)
    strata = {}
    for _id in chosen_ids:
        r = by_id[_id]
        strata[f"{r[3]} x {r[2]}"] = strata.get(f"{r[3]} x {r[2]}", 0) + 1
    return {"sample_id": "triage-sample-v1", "n": len(chosen_ids), "seed": seed,
            "ids": sorted(chosen_ids), "strata": strata,
            "representation": {k: {"have": final_q[k], "need": quotas[k]} for k in quotas},
            "excluded_ids": sorted(exclude_ids)}


def run_sample(db_path, out_dir, n=300, wave1_ids=frozenset()):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        sample = build_sample(con, n=n, wave1_ids=wave1_ids)
        cols = ["id", "wordEn", "pos", "primarySense", "definitionEn", "definitionAr",
                "examples", "arabicAr", "mnemonicAr", "synonyms", "antonyms", "collocations"]
        records = []
        for _id in sample["ids"]:
            row = con.execute(
                f"SELECT {','.join(cols)} FROM wordsMaster WHERE id=?", (_id,)).fetchone()
            records.extend(triage_card(dict(zip(cols, row))))
        report = check_quotas_or_halt(records)  # HALTs here on breach: no manifest
    finally:
        con.close()
    records_sorted = sorted(records, key=lambda r: (r["identity"]["id"], r["field"]))
    manifest = {"manifest_id": "triage_sample_300_v1", "rules_version": RULES_VERSION,
                "sample": {k: v for k, v in sample.items() if k != "ids"},
                "sample_ids": sample["ids"],
                "quota_report": report, "records": records_sorted}
    blob = _canon_json(manifest)
    manifest["manifest_sha256"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    (out / "triage_sample_300.json").write_text(
        _canon_json(manifest), encoding="utf-8")
    (out / "triage_sample_300_quota.json").write_text(
        _canon_json(report), encoding="utf-8")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic field triage (Ticket 17, read-only)")
    ap.add_argument("--mode", choices=["sample-run"], required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--db", default="WordsMaster.db")
    ap.add_argument("--out", default=".scratch/lexical-migration-build/output/triage")
    ap.add_argument("--wave1-manifest",
                    default=".scratch/lexical-migration-build/output/migration_readiness/migration_manifest_348.json")
    args = ap.parse_args(argv)
    wave1_ids = frozenset()
    try:
        man = json.loads(Path(args.wave1_manifest).read_text(encoding="utf-8"))
        wave1_ids = frozenset(r["wordsMaster_id"] for r in man["records"])
    except (OSError, KeyError, json.JSONDecodeError):
        pass
    try:
        manifest = run_sample(args.db, args.out, n=args.n, wave1_ids=wave1_ids)
    except QuotaBreach as q:
        print("HALTED — quota breach (rule review required):")
        print(_canon_json(q.report))
        raise SystemExit(3)
    print(f"sample triaged: {len(manifest['sample_ids'])} ids, "
          f"{len(manifest['records'])} records, sha={manifest['manifest_sha256'][:12]}…")
    print(_canon_json(manifest["quota_report"]))


if __name__ == "__main__":
    main()
