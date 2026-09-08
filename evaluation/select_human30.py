"""Stratified human review sample: 30 cards from the frozen 348.

Deterministic, drawn AFTER the AI results are frozen and pinned by a
fixed seed. Strata (user ruling):

  10 translations (candidate wins + legacy wins + ties; priority to
     content-changed), 6 relations (empty-after-cleaning, candidate
     wins, legacy-preserved), 5 sense_separation (polysemy /
     multi-POS / AI abstain), 4 examples (candidate wins + legacy
     wins + critical-related), 3 definition/Arabic (technical or
     semantic-change), 2 mnemonic (changed/null, indirect
     association preferred).

The five pre-registered cases (this/det, fish/noun synonyms; billion
/num definition+explanation+collocations) are FORCED into the sample
instead of the draw pretending fairness.

Every card is reviewed ONCE (selection excludes already-chosen ids).
AI verdicts are used ONLY for stratification (the reviewer pack carries
no AI information and no side assignment — those stay in the PRIVATE
identity map). Sampling never re-runs anything and never writes to the
frozen 348 artifacts.
"""

import hashlib
import json
import os
import random
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

SEED_H30 = 600117
FORCED = {
    "relations": ["this/det", "fish/noun"],
    "definition_arabic": ["billion/num"],
}
STRATA = (
    ("translations", 10),
    ("relations", 6),
    ("sense_separation", 5),
    ("examples", 4),
    ("definition_arabic", 3),
    ("mnemonic", 2),
)

BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                    "output")
PKG_DIR = os.path.join(BASE, "eval_seeded348_v1")
PKG_PATH = os.path.join(PKG_DIR, "eval_seeded348_v1.json")
MAP_PATH = os.path.join(PKG_DIR, "eval_identity_map.json")
DECODE_PATH = os.path.join(BASE, "ai_judge_seeded348",
                           "decode_analysis.json")
PROV_PATH = os.path.join(BASE, "EXP-SEEDED-001A", "generated_356",
                         "seeded_generation_provenance.jsonl")
SNAPSHOT_PATH = os.path.join(BASE, "EXP-SEEDED-001",
                             "seed_snapshot_v1.jsonl")
OUT_DIR = os.path.join(BASE, "human_review_seeded30")

EX_FIELDS = {"example_semantic_error", "target_word_violation"}
REL_FIELDS = ("synonyms", "antonyms", "collocations")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_package():
    return load_json(PKG_PATH)["items"]


def load_map():
    return load_json(MAP_PATH)["map"]


def load_decode():
    return load_json(DECODE_PATH)["items"]


def load_source_by_key():
    by = {}
    with open(PROV_PATH, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if "source_type" not in e:
                continue
            ident = e["identity"]
            key = "%s/%s" % (ident["lemma"].strip().lower(),
                             (ident.get("pos") or "").strip().lower())
            by[key] = e["source_type"]
    return by


def load_multipos():
    counts = {}
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            lemma = s["lemma"].strip().lower()
            pos = (s.get("pos") or "").strip().lower()
            counts.setdefault(lemma, set()).add(pos)
    return {lemma for lemma, poss in counts.items() if len(poss) > 1}


def classify(card, id_map, decode_rows, source_by_key, multipos):
    eval_id = card["eval_id"]
    key = id_map[eval_id]["candidate_key"]
    side = id_map[eval_id]["candidate_side"]
    cand_arm = card["armA"] if side == "A" else card["armB"]
    leg_arm = card["armB"] if side == "A" else card["armA"]
    row = decode_rows.get(eval_id, {"fields": {}, "criticals": []})
    fields = row.get("fields", {})
    crits = row.get("criticals", [])
    src = source_by_key.get(key, {})
    lemma = card["lemma"].strip().lower()

    eligibility = {}
    focus = []

    tv = fields.get("translations")
    t_src = src.get("translations")
    if tv in ("candidate", "legacy", "tie"):
        tags = [tv]
        if t_src == "llm_changed":
            tags.append("changed")
        elif t_src == "legacy_preserved":
            tags.append("preserved")
        eligibility["translations"] = tags
        focus.append("translations")

    rv = fields.get("relations")
    rel_tags = []
    rel_cand = cand_arm.get("relations", {})
    rel_leg = leg_arm.get("relations", {})
    emptied = [k for k in REL_FIELDS
               if rel_leg.get(k) and not rel_cand.get(k)]
    if emptied:
        rel_tags.append("emptied")
    src_rel = [src.get(f) for f in REL_FIELDS]
    if any(v == "legacy_preserved" for v in src_rel):
        rel_tags.append("legacy_preserved")
    if rv == "candidate":
        rel_tags.append("candidate")
    if rel_tags:
        eligibility["relations"] = rel_tags
        focus.append("relations")

    sv = fields.get("sense_separation")
    if sv == "cannot-judge":
        sense_tags = ["abstain"]
        if lemma in multipos:
            sense_tags.append("multi_pos")
        eligibility["sense_separation"] = sense_tags
        focus.append("sense_separation")
    elif lemma in multipos:
        eligibility["sense_separation"] = ["multi_pos"]
        focus.append("sense_separation")

    ev = fields.get("examples")
    crit_ex = any(c["class"] in EX_FIELDS and c["side"] for c in crits)
    if ev:
        ex_tags = [ev]
        if crit_ex:
            ex_tags.append("critical_related")
        eligibility["examples"] = ex_tags
        focus.append("examples")

    dv = fields.get("definition")
    d_src = src.get("definition_en")
    a_src = src.get("explanation_ar")
    if dv in ("candidate", "legacy", "tie") and (
            d_src == "llm_changed" or a_src == "llm_changed"):
        eligibility["definition_arabic"] = ["semantic_change", dv]
        focus.append("definition_arabic")

    m_src = src.get("mnemonic")
    m_text = cand_arm.get("mnemonic")
    if m_src in ("llm_changed", "null"):
        m_tags = [m_src]
        if m_text and lemma not in str(m_text).lower():
            m_tags.append("indirect")
        eligibility["mnemonic"] = m_tags
        focus.append("mnemonic")

    return {"key": key, "eligibility": eligibility, "focus": focus}


def _shuffle_and_take(rng, ids, k):
    ids = list(ids)
    rng.shuffle(ids)
    return ids[:k]


def _cohort_pick(rng, keys_seen, cohorts, quota):
    """cohorts: ordered list of (name, cap, ids); take up to cap per
    cohort in priority order, skipping already-seen ids; excess work
    spills to later cohorts. Raises only if the TOTAL shortfall
    exceeds availability across all cohorts."""
    picked = []
    seen = set(keys_seen)
    for name, cap, ids in cohorts:
        room = quota - len(picked)
        if room <= 0:
            break
        avail = [i for i in ids if i not in seen]
        rng.shuffle(avail)
        taken = avail[:min(cap, room)]
        picked.extend(taken)
        seen.update(taken)
    if len(picked) < quota:
        raise RuntimeError("stratum cohort pools too small "
                           "(%d/%d picked)" % (len(picked), quota))
    return picked


def select_cards(classified, seed=SEED_H30):
    """classified: {eval_id: {"key":..., "eligibility": {stratum:
    [tags]}, "focus": [...]}}. Returns selected list of dicts
    (eval_id, stratum, reason), one card per stratum, unique ids.
    """
    rng = random.Random(seed)
    flat = {eid: info["eligibility"] for eid, info in
            classified.items()}
    chosen = set()
    selected = []

    for stratum, quota in STRATA:
        elig = [eid for eid, info in classified.items()
                if stratum in info.get("eligibility", {})]
        n_forced = 0
        for key in FORCED.get(stratum, []):
            fids = [eid for eid in elig if classified[eid]["key"] == key]
            if not fids:
                raise RuntimeError("forced key %s not eligible for %s"
                                   % (key, stratum))
            n_forced += 1
            chosen.add(fids[0])
            selected.append({"eval_id": fids[0], "stratum": stratum,
                             "reason": "forced:%s" % key})
        quota_left = quota - n_forced
        if quota_left <= 0:
            continue

        if stratum == "translations":
            picked = _cohort_pick(
                rng, chosen, [
                    ("cand_changed", 4, _cand_changed(elig, flat,
                                                      stratum)),
                    ("cand_other", 1, [eid for eid in elig
                                       if "candidate" in
                                       flat[eid][stratum]
                                       and "changed" not in
                                       flat[eid][stratum]]),
                    ("legacy", 2, _legacy(elig, flat, stratum)),
                    ("tie", 3, _tie(elig, flat, stratum)),
                    ("fill", quota_left, elig),
                ], quota_left)
            reason = "cand_changed/cand_other/legacy/tie"
        elif stratum == "relations":
            picked = _cohort_pick(
                rng, chosen, [
                    ("emptied", 1, [eid for eid in elig
                                    if "emptied" in flat[eid][stratum]]),
                    ("preserved", 1, [eid for eid in elig
                                      if "legacy_preserved" in
                                      flat[eid][stratum]]),
                    ("candidate", quota_left, _cand_wins(
                        elig, flat, stratum)),
                ], quota_left)
            reason = "emptied/preserved/candidate"
        elif stratum == "sense_separation":
            picked = _cohort_pick(
                rng, chosen, [
                    ("multi_pos", 2, [eid for eid in elig
                                      if "multi_pos" in
                                      flat[eid][stratum]]),
                    ("abstain", 3, [eid for eid in elig
                                    if "abstain" in
                                    flat[eid][stratum]]),
                ], quota_left)
            reason = "multi_pos/abstain"
        elif stratum == "examples":
            picked = _cohort_pick(
                rng, chosen, [
                    ("candidate", 2, _cand_wins(elig, flat, stratum)),
                    ("legacy", 1, _legacy(elig, flat, stratum)),
                    ("critical", 1, [eid for eid in elig
                                     if "critical_related" in
                                     flat[eid][stratum]]),
                    ("fill", quota_left, elig),
                ], quota_left)
            reason = "candidate/legacy/critical"
        elif stratum == "definition_arabic":
            picked = _cohort_pick(
                rng, chosen, [
                    ("semantic_change", quota_left, elig),
                ], quota_left)
            reason = "semantic_change"
        else:  # mnemonic
            picked = _cohort_pick(
                rng, chosen, [
                    ("indirect", 1, [eid for eid in elig
                                     if "indirect" in
                                     flat[eid][stratum]]),
                    ("changed_null", quota_left, [eid for eid in elig]),
                ], quota_left)
            reason = "indirect/changed_null"

        for eid in picked:
            chosen.add(eid)
            tags = ",".join(flat[eid][stratum])
            selected.append({"eval_id": eid, "stratum": stratum,
                             "reason": reason, "tags": tags})
    return selected


def _cand_changed(ids, flat, stratum):
    return [eid for eid in ids
            if "candidate" in flat[eid][stratum]
            and "changed" in flat[eid][stratum]]


def _legacy(ids, flat, stratum):
    return [eid for eid in ids if "legacy" in flat[eid][stratum]]


def _tie(ids, flat, stratum):
    return [eid for eid in ids if "tie" in flat[eid][stratum]]


def _cand_wins(ids, flat, stratum):
    return [eid for eid in ids if "candidate" in flat[eid][stratum]]


def write_selection_record(selected, classified):
    os.makedirs(OUT_DIR, exist_ok=True)
    record = {
        "eval_id": "human30",
        "seed": SEED_H30,
        "strata": dict((s, n) for s, n in STRATA),
        "forced": FORCED,
        "n_cards": len(selected),
        "cards": [{"eval_id": s["eval_id"], "stratum": s["stratum"],
                   "reason": s["reason"], "tags": s.get("tags", ""),
                   "key": classified[s["eval_id"]]["key"],
                   "focus": classified[s["eval_id"]]["focus"]}
                  for s in selected],
    }
    path = os.path.join(OUT_DIR, "human30_selection.json")
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True,
                     indent=1)
    record["selection_sha256"] = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw)
    return path, record


def render_cards_md(selected, classified, package_items, out_path):
    by_id = {c["eval_id"]: c for c in package_items}
    lines = []
    for order, sel in enumerate(selected, start=1):
        eid = sel["eval_id"]
        card = by_id[eid]
        info = classified[eid]
        lines.append("## %d. %s (%s / %s)" % (order, eid, card["lemma"],
                                              card["pos"]))
        lines.append("focus: %s" % ", ".join(info["focus"]))
        lines.append("")
        for side in ("A", "B"):
            arm = card["armA"] if side == "A" else card["armB"]
            lines.append("### Side %s" % side)
            for field in ("definition", "arabic", "examples",
                          "translations", "relations", "mnemonic"):
                val = arm.get(field)
                if isinstance(val, list):
                    rendered = "\n".join("- " + str(v)
                                         for v in val) or "—"
                elif isinstance(val, dict):
                    rendered = json.dumps(val, ensure_ascii=False)
                else:
                    rendered = "—" if not val else str(val)
                lines.append("- %s: %s" % (field, rendered))
            lines.append("")
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


def write_ballot_template(selected, out_path):
    from evaluation.blind_package import blank_ballot
    judgments = {}
    for sel in selected:
        ballot = blank_ballot()
        judgments[sel["eval_id"]] = {
            "fields": ballot["fields"],
            "critical_errors": ballot["critical_errors"],
            "note": "",
        }
    out = {"eval_id": "human30",
           "hint": "fields: A-better | B-better | tie | cannot-judge"
                   " | unjudged",
           "judgments": judgments}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out_path


def main():
    package_items = load_package()
    id_map = load_map()
    decode_items = load_decode()
    source_by_key = load_source_by_key()
    multipos = load_multipos()
    decode_by = {r["eval_id"]: r for r in decode_items}
    classified = {card["eval_id"]: classify(
        card, id_map, decode_by, source_by_key, multipos)
        for card in package_items}
    sel = select_cards(classified)
    counts = {}
    for s in sel:
        counts[s["stratum"]] = counts.get(s["stratum"], 0) + 1
    assert counts == dict(STRATA), counts
    assert len({s["eval_id"] for s in sel}) == 30
    forced_keys = {k for keys in FORCED.values() for k in keys}
    sel_keys = {classified[s["eval_id"]]["key"] for s in sel}
    assert forced_keys <= sel_keys, forced_keys - sel_keys
    os.makedirs(OUT_DIR, exist_ok=True)
    path, record = write_selection_record(sel, classified)
    md_path = render_cards_md(sel, classified, package_items,
                              os.path.join(OUT_DIR,
                                           "review_cards_30.md"))
    ballot_path = write_ballot_template(
        sel, os.path.join(OUT_DIR, "human_judgments_30.json"))
    print("selection:", path)
    print("counts by stratum:", counts)
    print("cards:", md_path)
    print("ballots:", ballot_path)
    print("selection_sha256:", record["selection_sha256"])
    return record


if __name__ == "__main__":
    main()