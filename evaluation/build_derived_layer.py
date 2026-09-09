"""Derived-layer builder (Ticket 21). CANONICAL READ-ONLY.

Reads WordsMaster.db (Baseline-002 file hash asserted before any read) and
ielts_mapping_v2.json. Writes materialized artifacts under
.scratch/.../output/derived/ plus a hash manifest.

Views carry REFERENCES ONLY (id/lemma/pos + derived attributes). Enrichment
payload (definitions/examples/translations/relations/mnemonics/...) is NEVER
copied — enforced by the audit step, not by convention.
"""

import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build", "output")
OUT = os.path.join(BASE, "derived")
MIN_COLS = ["id", "wordEn", "pos", "cefrLevel", "fromOxford", "rank",
            "frequency", "difficultyScore", "unitId", "category"]
CEFR_ORDER = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(os.path.join(OUT, "views"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "curriculum"), exist_ok=True)
    db_path = os.path.join(ROOT_DIR, "WordsMaster.db")
    base2 = json.load(open(os.path.join(
        BASE, "migration_readiness", "baseline",
        "Baseline-PostMigration-002.json"), encoding="utf-8"))
    assert sha_file(db_path) == base2["file_sha256"], "canonical moved!"
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    rows = con.execute(
        "SELECT %s FROM wordsMaster ORDER BY id" % ",".join(MIN_COLS)
    ).fetchall()
    assert len(rows) == 7300
    cards = [dict(zip(MIN_COLS, r)) for r in rows]
    by_id = {c["id"]: c for c in cards}
    idx_lp = defaultdict(list)
    idx_l = defaultdict(list)
    for c in cards:
        idx_lp[(c["wordEn"].strip().lower(), (c["pos"] or "").lower())].append(
            c["id"])
        idx_l[c["wordEn"].strip().lower()].append(c["id"])

    mapping_path = os.path.join(BASE, "ielts_mapping_v2.json")
    mapping = json.load(open(mapping_path, encoding="utf-8"))
    ielts_ev = defaultdict(lambda: {"tiers": [], "row_ids": [],
                                    "topics": [], "source_pos": []})
    consumed = Counter()
    unmapped = []
    for rec in mapping["records"]:
        cls = rec["classification"]
        norm = (rec.get("normalized_form") or "").strip().lower()
        if cls == "NORMALIZED_LEMMA_POS_EXACT":
            key = (norm, (rec.get("matched_pos") or "").lower())
            ids = idx_lp.get(key, [])
            assert len(ids) == 1, (rec, ids)
            tier = "exact_lemma_pos"
        elif cls == "SAME_LEMMA_DIFFERENT_POS":
            ids = idx_l.get(norm, [])
            tier = "same_lemma_diff_pos"
        elif cls == "MULTIWORD":
            ids = idx_l.get(norm, [])
            tier = "multiword"
        else:
            continue  # NEW_SINGLE_WORD = candidate additions, not members
        consumed[cls] += 1
        if not ids:
            unmapped.append({
                "source_row_id": rec["ielts_row_id"],
                "source_text": rec.get("source_lemma"),
                "topic": rec.get("topic"),
                "normalized_form": rec.get("normalized_form"),
                "source_pos": rec.get("source_pos"),
                "match_status": "unmapped_multiword"})
        for _id in ids:
            ev = ielts_ev[_id]
            ev["tiers"].append(tier)
            ev["row_ids"].append(rec["ielts_row_id"])
            if rec.get("topic") and rec["topic"] not in ev["topics"]:
                ev["topics"].append(rec["topic"])
            if rec.get("source_pos"):
                ev["source_pos"].append(rec["source_pos"])
    assert consumed["NORMALIZED_LEMMA_POS_EXACT"] == 678
    assert consumed["SAME_LEMMA_DIFFERENT_POS"] == 34
    assert consumed["MULTIWORD"] == 34

    ev_path = os.path.join(OUT, "evidence_layer.jsonl")
    with open(ev_path, "w", encoding="utf-8") as f:
        for c in cards:
            ie = ielts_ev.get(c["id"])
            rec = {
                "id": c["id"], "lemma": c["wordEn"], "pos": c["pos"],
                "oxford": {"flag": bool(c["fromOxford"]),
                           "source": "fromOxford:unversioned_legacy_flag"},
                "ielts": ({"matched": True, **ie,
                            "source": "ielts_mapping_v2"} if ie else
                          {"matched": False,
                           "source": "ielts_mapping_v2"}),
                "cefr": {"value": c["cefrLevel"],
                         "provenance": "legacy_unverified"},
                "frequency": {"value_1_6": c["frequency"],
                              "provenance": "legacy_unverified_scale"},
            }
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True)
                    + "\n")

    def dump(name, obj):
        p = os.path.join(OUT, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        return p

    ox = [c["id"] for c in cards if c["fromOxford"]]
    nonox = [c["id"] for c in cards if not c["fromOxford"]]
    dump("views/oxford_flagged.json", {
        "view": "oxford_flagged",
        "meaning": "fromOxford=1 (unversioned legacy flag). NOT the Oxford "
                   "3000/5000 named lists (no source lists in repo).",
        "count": len(ox), "ids": ox})
    dump("views/non_oxford.json", {"view": "non_oxford", "count": len(nonox),
                                   "ids": nonox})
    ielts_ids = sorted(ielts_ev)
    dump("views/ielts.json", {
        "view": "ielts_matched",
        "tiers": {t: sorted(i for i, e in ielts_ev.items() if t in e["tiers"])
                  for t in ("exact_lemma_pos", "same_lemma_diff_pos",
                            "multiword")},
        "matched_identities": len(ielts_ids),
        "candidate_additions_NEW_SINGLE_WORD": 276,
        "mapping": "ielts_mapping_v2.json"})
    unmapped_sorted = sorted(unmapped, key=lambda r: r["source_row_id"])
    dump("views/ielts_unmapped.json", {
        "view": "ielts_unmapped_multiword",
        "meaning": "mapping rows with zero canonical counterpart. Preserved "
                   "as evidence of intent; NOT members, NO fake identities, "
                   "NOT counted in matched_identities.",
        "count": len(unmapped_sorted),
        "rows": unmapped_sorted})
    oxford_set, ielts_set = set(ox), set(ielts_ids)
    cefr_ox, cefr_ie = {}, {}
    for c in cards:
        cefr_ox.setdefault(c["cefrLevel"], {"oxford": 0, "total": 0})
        cefr_ox[c["cefrLevel"]]["total"] += 1
        if c["id"] in oxford_set:
            cefr_ox[c["cefrLevel"]]["oxford"] += 1
        cefr_ie.setdefault(c["cefrLevel"], {"ielts": 0, "total": 0})
        cefr_ie[c["cefrLevel"]]["total"] += 1
        if c["id"] in ielts_set:
            cefr_ie[c["cefrLevel"]]["ielts"] += 1
    dump("views/intersections.json", {
        "oxford_and_ielts": sorted(oxford_set & ielts_set),
        "ielts_only": sorted(ielts_set - oxford_set),
        "oxford_only": sorted(oxford_set - ielts_set),
        "counts": {"both": len(oxford_set & ielts_set),
                   "ielts_only": len(ielts_set - oxford_set),
                   "oxford_only": len(oxford_set - ielts_set),
                   "neither": 7300 - len(oxford_set | ielts_set)},
        "cefr_x_oxford": cefr_ox, "cefr_x_ielts": cefr_ie})

    units = {r[0]: {"levelId": r[1], "unitOrder": r[2]}
             for r in con.execute(
                 "SELECT unitId,levelId,unitOrder FROM units").fetchall()}
    agg = defaultdict(lambda: {"rows": 0, "lemmas": set(), "oxford": 0,
                               "ielts": 0})
    for c in cards:
        a = agg[c["unitId"]]
        a["rows"] += 1
        a["lemmas"].add(c["wordEn"].strip().lower())
        a["oxford"] += 1 if c["fromOxford"] else 0
        a["ielts"] += 1 if c["id"] in ielts_set else 0
    units_derived = []
    for u in sorted(agg):
        a = agg[u]
        units_derived.append({
            "unitId": u, "levelId": units[u]["levelId"],
            "unitOrder": units[u]["unitOrder"],
            "distinctLemmaCount": len(a["lemmas"]),
            "rowCount": a["rows"], "oxfordCount": a["oxford"],
            "ieltsCount": a["ielts"],
            "totalWords_semantics": "canonical units.totalWords counts "
                "DISTINCT LEMMAS per unit (legacy name retained in canonical; "
                "use distinctLemmaCount here)"})
    dump("curriculum/units_derived.json", {"units": units_derived})
    by_level = defaultdict(list)
    for u in units_derived:
        by_level[u["levelId"]].append(u)
    for lvl in by_level:
        by_level[lvl].sort(key=lambda u: u["unitOrder"])
    order = [u["unitId"] for lvl in sorted(by_level, key=CEFR_ORDER.get)
             for u in by_level[lvl]]
    dump("curriculum/curricula.json", {
        "framework": "Curricula are ORDERINGS over existing unitIds. No unit "
            "reassignment, no duplication, no pedagogical-validity claim "
            "(structural v1). Academic track needs a topic/source decision.",
        "curricula": [
            {"id": "general_progression",
             "rule": "CEFR order, then unitOrder (current canonical order, "
                     "made explicit)",
             "unit_sequence": order},
            {"id": "oxford_progression",
             "rule": "within each CEFR (in order): units by oxfordCount "
                     "desc, stable by unitOrder",
             "unit_sequence": [
                 u["unitId"] for lvl in sorted(by_level, key=CEFR_ORDER.get)
                 for u in sorted(by_level[lvl],
                                 key=lambda x: (-x["oxfordCount"],
                                                x["unitOrder"]))]},
            {"id": "ielts_progression",
             "rule": "within each CEFR (in order): units by ieltsCount "
                     "desc, stable by unitOrder",
             "unit_sequence": [
                 u["unitId"] for lvl in sorted(by_level, key=CEFR_ORDER.get)
                 for u in sorted(by_level[lvl],
                                 key=lambda x: (-x["ieltsCount"],
                                                x["unitOrder"]))]}]})
    con.close()

    manifest = {"layer": "derived_v1", "baseline": "Baseline-PostMigration-002",
                "canonical_db_sha256": sha_file(db_path),
                "hash_semantics": "canonical_db_sha256 = SHA-256 of "
                    "WordsMaster.db FILE BYTES (cf Baseline-002 file_sha256). "
                    "Content-level hash lives separately as Baseline-002 "
                    "final_logical_hash_wordsmaster. Different functions, "
                    "both pinned; never compared across.",
                "normalization_provenance": {
                    "mapping_produced_by": mapping.get("produced_by"),
                    "mapping_rule_order": mapping.get("rule_order"),
                    "derived_join": "lower(strip) both sides; tiers "
                        "exact_lemma_pos / same_lemma_diff_pos / multiword",
                    "builder": "evaluation/build_derived_layer.py"},
                "mapping_sha256": sha_file(mapping_path),
                "files": {}}
    for dirpath, _dirs, files in os.walk(OUT):
        for fn in sorted(files):
            if fn == "manifest.json":
                continue
            p = os.path.join(dirpath, fn)
            manifest["files"][os.path.relpath(p, OUT)] = sha_file(p)
    with open(os.path.join(OUT, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("derived built:", len(manifest["files"]), "files;",
          "oxford:", len(ox), "| ielts matched:", len(ielts_ids),
          "| units:", len(units_derived))


if __name__ == "__main__":
    main()
