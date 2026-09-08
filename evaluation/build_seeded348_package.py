"""Blind package builder for the full-356 evaluation set (the 348).

Same DTO, same A/B method, same isolation gate as the pilot-60
builder (build_seeded60_package.py) — frozen modules untouched. New
pinned IDs:

  EVAL_ID_348 = "eval_seeded348_v1", SEED_348 = 600116.

Identities are derived deterministically from the merged generated_356
run: exactly the 348 identities that have a decision record (31 online
combined + 317 batch phase=decision). Transport (channel) never enters
the DTO; assert_blind additionally rejects run-identifier leaks.
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
    candidate_arm, legacy_arm, blank_ballot, assert_blind)
from evaluation.utils import canonical_hash

EVAL_ID_348 = "eval_seeded348_v1"
SEED_348 = 600116

WORDS_MASTER = os.path.join(ROOT_DIR, "WordsMaster.db")
LEGACY_COLUMNS = ("wordEn", "pos", "definitionEn", "definitionAr",
                  "examples", "arabicAr", "synonyms", "antonyms",
                  "mnemonicAr")

BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                    "output")
GENERATED_DIR = os.path.join(BASE, "EXP-SEEDED-001A", "generated_356")
OUT_DIR = os.path.join(BASE, "eval_seeded348_v1")


def load_decided_identities(provenance_path):
    by = {}
    with open(provenance_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            key = "%s/%s" % (e["identity"]["lemma"].strip().lower(),
                             (e["identity"].get("pos") or "")
                             .strip().lower())
            by.setdefault(key, set()).add(e.get("phase"))
    decided = [k for k, phases in by.items()
               if "decision" in phases or None in phases]
    return sorted({(k.rsplit("/", 1)[0], k.rsplit("/", 1)[1])
                   for k in decided})


def load_legacy_rows(db_path, identities):
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = {}
    missing = []
    for lemma, pos in identities:
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
    for lemma, pos in identities:
        key = "%s/%s" % (lemma, pos)
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
    for lemma, pos in identities:
        key = "%s/%s" % (lemma, pos)
        items.append({"eval_key": key, "lemma": lemma, "pos": pos,
                      "candidate_output": arms[key],
                      "legacy_row": legacy_rows[key]})
    return items


def build_package_348(items, seed=SEED_348):
    rng = random.Random(seed)
    package_items = []
    id_map = {}
    for i, item in enumerate(sorted(items, key=lambda x: x["eval_key"])):
        eval_id = "%s-%04d" % (EVAL_ID_348, i + 1)
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
            if "validator" not in e:
                continue
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
    entries = [prov["%s/%s" % (l, p)] for (l, p) in identities]
    record = {"eval_input_id": EVAL_ID_348 + "-INPUT",
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


def write_package_348(out_dir, package_items, id_map, eval_input):
    os.makedirs(out_dir, exist_ok=True)
    package_path = os.path.join(out_dir, "eval_seeded348_v1.json")
    map_path = os.path.join(out_dir, "eval_identity_map.json")
    input_path = os.path.join(out_dir, "eval_input.json")
    with open(package_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_348, "seed": SEED_348,
                   "items": package_items}, f, ensure_ascii=False,
                  indent=1)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_348, "map": id_map}, f,
                  ensure_ascii=False, indent=1)
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(eval_input, f, ensure_ascii=False, indent=1)
    hashes = {"eval_seeded348_v1.json": sha256_file(package_path),
              "eval_identity_map.json": sha256_file(map_path),
              "eval_input.json": sha256_file(input_path)}
    with open(os.path.join(out_dir, "hashes.json"), "w",
              encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_348, "sha256": hashes}, f,
                  ensure_ascii=False, indent=1)
    return package_path, map_path, input_path, hashes


TRANSPORT_KEYS = {"channel", "phase", "provenance", "job_id",
                  "input_gcs", "output_gcs", "candidate_id",
                  "created_at", "imported_at"}


def _assert_no_transport_keys(obj):
    """Reject transport-shaped keys anywhere in the package.

    Content words are NEVER banned here (the word 'channel' is a real
    identity in this run). This only rejects JSON keys that name
    transport wiring, which the DTO constructors cannot produce.
    """
    if isinstance(obj, dict):
        overlap = set(obj) & TRANSPORT_KEYS
        if overlap:
            raise RuntimeError("transport key leak %s in package"
                               % sorted(overlap))
        for v in obj.values():
            _assert_no_transport_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_transport_keys(v)


def main():
    provenance_path = os.path.join(
        GENERATED_DIR, "seeded_generation_provenance.jsonl")
    identities = load_decided_identities(provenance_path)
    expected = 31 + 317
    if len(identities) != expected:
        raise RuntimeError("decided identities %d != %d (31 online + "
                           "317 batch decisions)" %
                           (len(identities), expected))

    legacy_rows, missing_rows = load_legacy_rows(WORDS_MASTER,
                                                 identities)
    arms, missing_arms = load_candidate_arms(GENERATED_DIR, identities)
    if missing_rows or missing_arms:
        raise RuntimeError("legacy missing %s; arms missing %s"
                           % (missing_rows, missing_arms))

    items = build_items(identities, legacy_rows, arms)
    package_items, id_map = build_package_348(items)
    assert_blind(package_items)
    _assert_no_transport_keys(package_items)

    snap_records = [json.loads(l) for l in open(os.path.join(
        BASE, "EXP-SEEDED-001", "seed_snapshot_v1.jsonl"),
        encoding="utf-8")]
    snapshot_sha = hashlib.sha256(json.dumps(
        snap_records, sort_keys=True,
        ensure_ascii=False).encode("utf-8")).hexdigest()
    prompt_text = open(os.path.join(
        ROOT_DIR, "evaluation", "prompts",
        "lexical_enrichment_seeded_v1.1.txt"),
        encoding="utf-8").read()
    batch_merge = json.load(open(os.path.join(
        GENERATED_DIR, "batch_merge.json"), encoding="utf-8"))
    eval_input = build_input_manifest(
        provenance_path, identities,
        {"run": "generated_356",
         "batch_merge_sha256": sha256_file(os.path.join(
             GENERATED_DIR, "batch_merge.json")),
         "generated_356_sha256": _dir_hash(os.path.join(
             GENERATED_DIR, "raw")),
         "seed_snapshot_sha256": snapshot_sha,
         "prompt_id": "lexical_enrichment_seeded_v1.1",
         "prompt_sha256": hashlib.sha256(
             prompt_text.encode("utf-8")).hexdigest()})
    paths = write_package_348(OUT_DIR, package_items, id_map,
                              eval_input)
    print("wrote:", paths[0])
    print("items:", len(package_items), "| map:", len(id_map))
    sides = {}
    for v in id_map.values():
        sides[v["candidate_side"]] = sides.get(v["candidate_side"], 0) + 1
    print("candidate sides:", sides)
    print("hashes:", paths[3])
    return OUT_DIR


def _dir_hash(directory):
    h = hashlib.sha256()
    for name in sorted(os.listdir(directory)):
        h.update(name.encode("utf-8"))
        with open(os.path.join(directory, name), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


if __name__ == "__main__":
    main()