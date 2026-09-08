"""Blind package builder: Legacy vs Seeded-v1.1 for the pilot-60.

New module for EXP-SEEDED-001A — frozen BT-14 modules are NOT
modified. Same DTO (FIELDS, CRITICAL_ERRORS, blank ballots), same
A/B randomization method (sorted by key, seeded coin per item),
same isolation gate (assert_blind), new pinned IDs:

  EVAL_ID_60 = "eval_seeded60_v1", SEED_60 = 600115.

Legacy arm comes from a fresh read-only WordsMaster query for the
60 identities (re-validates the (lemma,pos) mapping); candidate arm
comes from the 001A generated arms. Identity map stays PRIVATE.
"""

import hashlib
import json
import os
import random
import sqlite3
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.blind_package import (
    FIELDS, candidate_arm, legacy_arm, blank_ballot, assert_blind)
from evaluation.utils import canonical_hash

EVAL_ID_60 = "eval_seeded60_v1"
SEED_60 = 600115

WORDS_MASTER = os.path.join(ROOT_DIR, "WordsMaster.db")
LEGACY_COLUMNS = ("wordEn", "pos", "definitionEn", "definitionAr",
                  "examples", "arabicAr", "synonyms", "antonyms",
                  "mnemonicAr")


def load_identities(pilot_path):
    with open(pilot_path, encoding="utf-8") as f:
        return json.load(f)["items"]


def load_legacy_rows(db_path, identities):
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = {}
    missing = []
    for ident in identities:
        lemma = ident["lemma"].strip().lower()
        pos = (ident.get("pos") or "").strip().lower()
        cur.execute(
            "SELECT %s FROM wordsMaster WHERE lower(wordEn)=? "
            "AND lower(pos)=?" % ",".join(LEGACY_COLUMNS),
            (lemma, pos))
        found = cur.fetchall()
        key = "%s/%s" % (lemma, pos)
        if len(found) == 1:
            rows[key] = dict(found[0])
        else:
            missing.append({"key": key, "count": len(found)})
    con.close()
    return rows, missing


def load_candidate_arms(generated_dir, identities):
    arms = {}
    missing = []
    for ident in identities:
        key = "%s/%s" % (ident["lemma"].strip().lower(),
                         (ident.get("pos") or "").strip().lower())
        path = os.path.join(generated_dir, "raw",
                            key.replace("/", "__") + ".json")
        if not os.path.exists(path):
            missing.append(key)
            continue
        with open(path, encoding="utf-8") as f:
            arms[key] = json.load(f)["arm"]
    return arms, missing


def build_items(identities, legacy_rows, arms):
    items = []
    for ident in identities:
        key = "%s/%s" % (ident["lemma"].strip().lower(),
                         (ident.get("pos") or "").strip().lower())
        items.append({"eval_key": key, "lemma": ident["lemma"],
                      "pos": ident.get("pos"),
                      "candidate_output": arms[key],
                      "legacy_row": legacy_rows[key]})
    return items


def build_package_60(items, seed=SEED_60):
    """Same algorithm as BT-14 build_package, new pinned IDs."""
    rng = random.Random(seed)
    package_items = []
    id_map = {}
    for i, item in enumerate(sorted(items, key=lambda x: x["eval_key"])):
        eval_id = "%s-%04d" % (EVAL_ID_60, i + 1)
        arms = {
            "candidate": candidate_arm(item["candidate_output"]),
            "legacy": legacy_arm(item["legacy_row"]),
        }
        candidate_side = "A" if rng.random() < 0.5 else "B"
        package_items.append({
            "eval_id": eval_id,
            "lemma": item["lemma"],
            "pos": item["pos"],
            "armA": arms["candidate" if candidate_side == "A"
                         else "legacy"],
            "armB": arms["candidate" if candidate_side == "B"
                         else "legacy"],
            "ballot": blank_ballot(),
        })
        id_map[eval_id] = {
            "candidate_side": candidate_side,
            "candidate_key": item["eval_key"],
        }
    return package_items, id_map


def build_input_manifest(provenance_path, identities, extra_pins):
    prov = {}
    with open(provenance_path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            ident = e["identity"]
            key = "%s/%s" % (ident["lemma"].strip().lower(),
                             (ident.get("pos") or "").strip().lower())
            fails = sorted(k for k, v in e["validator"].items()
                           if v.get("status") == "fail")
            prov[key] = {
                "candidate_key": key,
                "status": ("success" if e["artifact_pass"]
                           else "validator_failed"),
                "validator_failures": fails,
                "prompt_hash": e["prompt_hash"],
            }
    entries = []
    for ident in identities:
        key = "%s/%s" % (ident["lemma"].strip().lower(),
                         (ident.get("pos") or "").strip().lower())
        entries.append(prov[key])
    record = {"eval_input_id": EVAL_ID_60 + "-INPUT",
              "entries": entries}
    record.update(extra_pins)
    record["input_hash"] = canonical_hash(record["entries"])
    return record


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_package_60(out_dir, package_items, id_map, eval_input):
    os.makedirs(out_dir, exist_ok=True)
    package_path = os.path.join(out_dir, "eval_seeded60_v1.json")
    map_path = os.path.join(out_dir, "eval_identity_map.json")
    input_path = os.path.join(out_dir, "eval_input.json")
    with open(package_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_60, "seed": SEED_60,
                   "items": package_items}, f, ensure_ascii=False,
                  indent=1)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_60, "map": id_map}, f,
                  ensure_ascii=False, indent=1)
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(eval_input, f, ensure_ascii=False, indent=1)
    hashes = {"eval_seeded60_v1.json": sha256_file(package_path),
              "eval_identity_map.json": sha256_file(map_path),
              "eval_input.json": sha256_file(input_path)}
    with open(os.path.join(out_dir, "hashes.json"), "w",
              encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_60, "sha256": hashes}, f,
                  ensure_ascii=False, indent=1)
    return package_path, map_path, input_path, hashes


def main():
    base = os.path.join(ROOT_DIR, ".scratch",
                        "lexical-migration-build", "output")
    pilot_path = os.path.join(base, "EXP-SEEDED-001A", "pilot60.json")
    generated_dir = os.path.join(base, "EXP-SEEDED-001A", "generated")
    out_dir = os.path.join(base, "eval_seeded60_v1")

    pilot = json.load(open(pilot_path, encoding="utf-8"))
    identities = pilot["items"]
    assert len(identities) == 60

    legacy_rows, missing_rows = load_legacy_rows(WORDS_MASTER,
                                                 identities)
    arms, missing_arms = load_candidate_arms(generated_dir,
                                             identities)
    assert not missing_rows, missing_rows
    assert not missing_arms, missing_arms

    items = build_items(identities, legacy_rows, arms)
    package_items, id_map = build_package_60(items)
    assert_blind(package_items)

    import hashlib as _h
    snap_records = [json.loads(l) for l in open(os.path.join(
        base, "EXP-SEEDED-001", "seed_snapshot_v1.jsonl"),
        encoding="utf-8")]
    snapshot_sha = _h.sha256(json.dumps(
        snap_records, sort_keys=True,
        ensure_ascii=False).encode("utf-8")).hexdigest()
    prompt_text = open(os.path.join(
        ROOT_DIR, "evaluation", "prompts",
        "lexical_enrichment_seeded_v1.1.txt"),
        encoding="utf-8").read()
    eval_input = build_input_manifest(
        os.path.join(generated_dir,
                     "seeded_generation_provenance.jsonl"),
        identities,
        {"pilot_selection_hash": pilot["selection_hash"],
         "seed_snapshot_sha256": snapshot_sha,
         "prompt_id": "lexical_enrichment_seeded_v1.1",
         "prompt_sha256": _h.sha256(
             prompt_text.encode("utf-8")).hexdigest()})
    paths = write_package_60(out_dir, package_items, id_map,
                             eval_input)
    print("wrote:", paths[0])
    print("items:", len(package_items), "| map:", len(id_map))
    sides = {}
    for v in id_map.values():
        sides[v["candidate_side"]] = sides.get(
            v["candidate_side"], 0) + 1
    print("candidate sides:", sides)
    print("hashes:", paths[3])
    return out_dir


if __name__ == "__main__":
    main()