"""Blind package builder for the Ticket-19 609 remediation set.

Same DTO, same A/B method, same isolation gate as the 348 builder
(build_seeded348_package.py) — frozen modules untouched. New pinned IDs:

  EVAL_ID_609 = "eval_remed609_v1", SEED_609 = 600118.

Identities: exactly the artifact_pass generation records from the 609 run
(590). The 13 validator-failed identities are EXCLUDED (no user framing
exists to keep them, unlike fourth/adj in 348) and reported as generation
failures. Transport (channel) never enters the DTO.
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

EVAL_ID_609 = "eval_remed609_v1"
SEED_609 = 600118

WORDS_MASTER = os.path.join(ROOT_DIR, "WordsMaster.db")
LEGACY_COLUMNS = ("wordEn", "pos", "definitionEn", "definitionAr",
                  "examples", "arabicAr", "synonyms", "antonyms",
                  "mnemonicAr")

BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                    "output")
GENERATED_DIR = os.path.join(BASE, "EXP-SEEDED-609", "generated_609")
OUT_DIR = os.path.join(BASE, "eval_remed609_v1")


def load_passed_identities(provenance_path):
    passed = []
    failed = []
    with open(provenance_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            key = "%s/%s" % (e["identity"]["lemma"].strip().lower(),
                             (e["identity"].get("pos") or "")
                             .strip().lower())
            (passed if e.get("artifact_pass") else failed).append(key)
    return sorted(set(passed)), sorted(set(failed))


def load_legacy_rows(db_path, identities):
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = {}
    missing = []
    for key in identities:
        lemma, pos = key.rsplit("/", 1)
        cur.execute(
            "SELECT %s FROM wordsMaster WHERE lower(wordEn)=? "
            "AND lower(pos)=?" % ",".join(LEGACY_COLUMNS),
            (lemma, pos))
        found = cur.fetchall()
        if len(found) == 1:
            rows[key] = dict(found[0])
        else:
            missing.append({"key": key, "count": len(found)})
    con.close()
    return rows, missing


def load_candidate_arms(generated_dir, identities):
    arms = {}
    missing = []
    for key in identities:
        path = os.path.join(generated_dir, "raw",
                            key.replace("/", "__") + ".json")
        if not os.path.exists(path):
            missing.append(key)
            continue
        with open(path, encoding="utf-8") as f:
            arms[key] = json.load(f)["arm"]
    return arms, missing


def build_package_609(identities, legacy_rows, arms, seed=SEED_609):
    rng = random.Random(seed)
    package_items = []
    id_map = {}
    for i, key in enumerate(sorted(identities)):
        lemma, pos = key.rsplit("/", 1)
        eval_id = "%s-%04d" % (EVAL_ID_609, i + 1)
        side_arms = {
            "candidate": candidate_arm(arms[key]),
            "legacy": legacy_arm(legacy_rows[key]),
        }
        candidate_side = "A" if rng.random() < 0.5 else "B"
        package_items.append({
            "eval_id": eval_id,
            "lemma": lemma,
            "pos": pos,
            "armA": side_arms["candidate" if candidate_side == "A"
                              else "legacy"],
            "armB": side_arms["candidate" if candidate_side == "B"
                              else "legacy"],
            "ballot": blank_ballot(),
        })
        id_map[eval_id] = {
            "candidate_side": candidate_side,
            "candidate_key": key,
        }
    return package_items, id_map


TRANSPORT_KEYS = {"channel", "phase", "provenance", "job_id",
                  "input_gcs", "output_gcs", "candidate_id",
                  "created_at", "imported_at"}


def _assert_no_transport_keys(obj):
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


def build_input_manifest_609(provenance_path, identities):
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
    entries = [prov[key] for key in identities]
    record = {"eval_input_id": EVAL_ID_609 + "-INPUT", "entries": entries}
    record["input_hash"] = canonical_hash(record["entries"])
    return record


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    provenance_path = os.path.join(
        GENERATED_DIR, "seeded_generation_provenance.jsonl")
    passed, failed = load_passed_identities(provenance_path)
    print("passed:", len(passed), "| failed (excluded):", len(failed))

    legacy_rows, missing_rows = load_legacy_rows(WORDS_MASTER, passed)
    arms, missing_arms = load_candidate_arms(GENERATED_DIR, passed)
    if missing_rows or missing_arms:
        raise RuntimeError("legacy missing %s; arms missing %s"
                           % (missing_rows, missing_arms))

    items = [{"eval_key": k} for k in passed]
    package_items, id_map = build_package_609(
        passed, legacy_rows, arms)
    assert_blind(package_items)
    _assert_no_transport_keys(package_items)

    snap_records = [json.loads(l) for l in open(os.path.join(
        BASE, "EXP-SEEDED-609", "seed_snapshot_609.jsonl"),
        encoding="utf-8")]
    snapshot_sha = hashlib.sha256(json.dumps(
        snap_records, sort_keys=True,
        ensure_ascii=False).encode("utf-8")).hexdigest()
    prompt_text = open(os.path.join(
        ROOT_DIR, "evaluation", "prompts",
        "lexical_enrichment_seeded_v1.1.txt"),
        encoding="utf-8").read()
    eval_input = build_input_manifest_609(provenance_path, passed)
    eval_input.update({
        "run": "generated_609",
        "seed_snapshot_sha256": snapshot_sha,
        "prompt_id": "lexical_enrichment_seeded_v1.1",
        "prompt_sha256": hashlib.sha256(
            prompt_text.encode("utf-8")).hexdigest()})

    os.makedirs(OUT_DIR, exist_ok=True)
    package_path = os.path.join(OUT_DIR, "eval_remed609_v1.json")
    map_path = os.path.join(OUT_DIR, "eval_identity_map.json")
    input_path = os.path.join(OUT_DIR, "eval_input.json")
    with open(package_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_609, "seed": SEED_609,
                   "items": package_items}, f, ensure_ascii=False, indent=1)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_609, "map": id_map}, f,
                  ensure_ascii=False, indent=1)
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(eval_input, f, ensure_ascii=False, indent=1)
    hashes = {"eval_remed609_v1.json": sha256_file(package_path),
              "eval_identity_map.json": sha256_file(map_path),
              "eval_input.json": sha256_file(input_path)}
    with open(os.path.join(OUT_DIR, "hashes.json"), "w",
              encoding="utf-8") as f:
        json.dump({"eval_id": EVAL_ID_609, "sha256": hashes}, f,
                  ensure_ascii=False, indent=1)
    sides = {}
    for v in id_map.values():
        sides[v["candidate_side"]] = sides.get(v["candidate_side"], 0) + 1
    print("wrote:", package_path)
    print("items:", len(package_items), "| candidate sides:", sides)
    print("hashes:", hashes)
    return OUT_DIR


if __name__ == "__main__":
    main()
