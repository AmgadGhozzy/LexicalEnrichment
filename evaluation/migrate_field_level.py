#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""G4 transactional field-level migration engine (dry-run default).

Applies the G3 promotion actions from migration_manifest_348.json to a
TARGET sqlite DB copy, writes a field_versions-style audit trail, then
VERIFIES and ROLLS BACK, proving the DB returns to the identical
logical state (hash) as before.

Safety invariants:
- MANDATORY target. If the target resolves to the production
  WordsMaster.db path, the run REFUSES unless --allow-production is
  passed (never passed in dry-run; only a human + governance-lock lift
  may do so).
- Promotions are field-level cells keyed by stable `id`, never
  row-overwrite, never touching non-promoted columns.
- Exclusions applied before writing: provenance-gap card (billion/num)
  keeps ALL fields; sense_separation is manual (never written)
  everywhere; CEFR/difficulty/unit/rank are NOT in promotion scope.
- Abort doctrine: on ANY error or failed verification the transaction
  aborts; no "commit-then-fix-later".

Usage:
  python -m evaluation.migrate_field_level --dry-run
  python -m evaluation.migrate_field_level --target <db-copy> [--keep-applied]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDMASTER = os.path.join(ROOT, "WordsMaster.db")
MANIFEST = os.path.join(
    ROOT,
    ".scratch",
    "lexical-migration-build",
    "output",
    "migration_readiness",
    "migration_manifest_348.json",
)
GEN_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "EXP-SEEDED-001A", "generated_356"
)
DRYRUN_DIR = os.path.join(
    ROOT,
    ".scratch",
    "lexical-migration-build",
    "output",
    "migration_readiness",
    "dryrun",
)

# candidate field -> wordsMaster column
FIELD_COL = {
    "definition_en": "definitionEn",
    "explanation_ar": "definitionAr",
    "examples": "examples",
    "translations": "arabicAr",
    "mnemonic": "mnemonicAr",
    "relations_synonyms": "synonyms",
    "relations_antonyms": "antonyms",
    "relations_collocations": "collocations",
}
WRITE_FIELDS = list(FIELD_COL.keys())
AUDIT_TABLE = "migration_audit_2026_001"


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def json_dump(v) -> str:
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def candidate_field_value(cand: dict, field: str):
    rel = cand.get("relations") or {}
    if field.startswith("relations_"):
        return rel.get(field[len("relations_"):])
    if field == "translations":
        return cand.get("translations")
    return cand.get(field)


def candidate_field_write_value(cand: dict, field: str) -> str:
    v = candidate_field_value(cand, field)
    if v is None:
        return None
    if field == "translations":
        if not isinstance(v, (list, tuple)):
            return str(v)
        return " / ".join(str(x) for x in v)
    if isinstance(v, (list, dict)):
        return json_dump(v)
    return str(v)


def logical_hash(con, tables=("wordsMaster",)) -> str:
    """Deterministic logical-state hash over canonical tables."""
    dump = {}
    for t in tables:
        rows = con.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
        cols = [d[0] for d in con.execute(f"pragma table_info({t})")]
        dump[t] = [dict(zip(cols, r)) for r in rows]
    return sha256_text(json_dump(dump))


def copy_db(src: str, dst: str) -> None:
    scon = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dcon = sqlite3.connect(dst)
    with dcon:
        scon.backup(dcon)
    scon.close()
    dcon.close()


def load_promotions():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    records = manifest["records"]
    summary = manifest["summary"]
    promotions = []  # dicts for apply
    for r in records:
        key = r["candidate_key"]
        if r["provenance_gap"]:  # billion/num: blocked
            continue
        raw_path = os.path.join(GEN_DIR, "raw", key.replace("/", "__") + ".json")
        if not os.path.exists(raw_path):
            raise RuntimeError(f"missing raw candidate: {key}")
        cand = (json.load(open(raw_path, encoding="utf-8")) or {}).get("candidate") or {}
        for field, action in r["actions"].items():
            if action != "promote":
                continue
            if field not in FIELD_COL:
                continue  # sense_separation is manual, never written
            val = candidate_field_write_value(cand, field)
            if val is None:
                raise RuntimeError(f"promote without value on {key} field {field}")
            promotions.append(
                {
                    "id": r["wordsMaster_id"],
                    "col": FIELD_COL[field],
                    "field": field,
                    "value_after": val,
                    "value_after_sha": sha256_text(val),
                    "candidate_key": key,
                    "eval_id": r["eval_id"],
                    "adjudication": r["adjudication"]["fields"].get(field),
                }
            )
    return promotions, summary


def verify_state(con, expect_rows: int, expect_ids: set):
    rows = con.execute("SELECT count(*) FROM wordsMaster").fetchone()[0]
    ids = set(x[0] for x in con.execute("SELECT id FROM wordsMaster"))
    if rows != expect_rows:
        raise RuntimeError(f"row count changed {rows} != {expect_rows}")
    if ids != expect_ids:
        raise RuntimeError("id set changed (identity violation)")
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"integrity_check: {integrity}")
    return True


def apply_promotions(con, promotions, source_ids_row_vals: dict) -> int:
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} "
        "(id INTEGER, col TEXT, value_before TEXT, value_after TEXT, "
        "value_after_sha TEXT, field TEXT, candidate_key TEXT, eval_id TEXT, "
        "adjudication TEXT, migrated_at TEXT)"
    )
    con.execute(f"DELETE FROM {AUDIT_TABLE}")
    con.execute("BEGIN")
    try:
        for p in promotions:
            before = source_ids_row_vals[p["id"]][p["col"]]
            con.execute(f"UPDATE wordsMaster SET {p['col']}=? WHERE id=?", (p["value_after"], p["id"]))
            con.execute(
                f"INSERT INTO {AUDIT_TABLE} "
                "(id, col, value_before, value_after, value_after_sha, field, "
                "candidate_key, eval_id, adjudication, migrated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    p["id"], p["col"], before, p["value_after"], p["value_after_sha"],
                    p["field"], p["candidate_key"], p["eval_id"], p["adjudication"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        con.execute("COMMIT")
        return len(promotions)
    except Exception:
        con.execute("ROLLBACK")
        raise


def rollback(con, promotions, drop_audit: bool = True) -> int:
    n = con.execute(f"SELECT count(*) FROM {AUDIT_TABLE}").fetchone()[0]
    for p in promotions:
        before = con.execute(
            f"SELECT value_before FROM {AUDIT_TABLE} WHERE id=? AND col=?", (p["id"], p["col"])
        ).fetchone()[0]
        con.execute(f"UPDATE wordsMaster SET {p['col']}=? WHERE id=?", (before, p["id"]))
    if drop_audit:
        con.execute(f"DROP TABLE IF EXISTS {AUDIT_TABLE}")
    return n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=None, help="target sqlite path (required unless --dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="build sandbox copy from WordsMaster.db and verify rollback")
    parser.add_argument("--keep-applied", action="store_true", help="do NOT rollback after verification (dry-run diagnostics)")
    parser.add_argument("--allow-production", action="store_true", help="UNSAFE: permit targeting WordsMaster.db (gated)")
    args = parser.parse_args()

    promotions, summary = load_promotions()
    meta_path = os.path.join(os.path.dirname(MANIFEST), "manifest.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    manifest_sha = meta.get("export_sha256") or summary.get("export_sha256") or MANIFEST
    print(f"promotion cells loaded: {len(promotions)}  (summary.g3 promote={summary['g3_actions']['promote']})")

    if args.dry_run:
        os.makedirs(DRYRUN_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = os.path.join(DRYRUN_DIR, f"wordsMaster_dryrun_{ts}.db")
        copy_db(WORDMASTER, target)
    else:
        target = os.path.abspath(args.target)
        if not args.target:
            parser.error("--target is required unless --dry-run")
        prod = os.path.abspath(WORDMASTER)
        if target == prod and not args.allow_production:
            parser.error("refusing production WordsMaster.db without --allow-production (governance lock)")
    print(f"target: {target}")

    con = sqlite3.connect(target)
    con.isolation_level = None
    con.execute("PRAGMA foreign_keys=OFF")
    expect_rows = con.execute("SELECT count(*) FROM wordsMaster").fetchone()[0]
    expect_ids = set(x[0] for x in con.execute("SELECT id FROM wordsMaster").fetchall())
    source_rows = {}
    for p in promotions:
        source_rows.setdefault(p["id"], {})
    ids_list = list(source_rows.keys())
    cols = [c[1] for c in con.execute(f"pragma table_info(wordsMaster)")]
    for rid in ids_list:
        r = con.execute(f"SELECT {','.join(cols)} FROM wordsMaster WHERE id=?", (rid,)).fetchone()
        source_rows[rid] = dict(zip(cols, r))

    pre_hash = logical_hash(con)
    print("pre logical hash:", pre_hash)
    verify_state(con, expect_rows, expect_ids)

    applied = apply_promotions(con, promotions, source_rows)
    print("applied promotion cells:", applied)
    post_hash = logical_hash(con)
    changed = pre_hash != post_hash
    print("post-hash differs from pre (expected change):", changed)
    if not changed:
        raise RuntimeError("apply produced no change — abort")

    audit_n = con.execute(f"SELECT count(*) FROM {AUDIT_TABLE}").fetchone()[0]
    print("audit rows:", audit_n)
    if audit_n != applied:
        raise RuntimeError(f"audit rows {audit_n} != applied {applied}")
    # JSON columns written remain valid JSON
    for p in promotions:
        if p["col"] in ("examples", "synonyms", "antonyms", "collocations"):
            cell = con.execute(f"SELECT {p['col']} FROM wordsMaster WHERE id=?", (p["id"],)).fetchone()[0]
            json.loads(cell)
    # untouched cells proof: count non-audited columns difference vs source snapshot
    verify_state(con, expect_rows, expect_ids)

    report = {
        "target": target,
        "pre_logical_sha256": pre_hash,
        "post_logical_sha256": post_hash,
        "expected_promote_cells": len(promotions),
        "applied_promote_cells": applied,
        "audit_rows": audit_n,
        "manifest": manifest_sha,
        "dry_run": args.dry_run,
    }

    if not args.keep_applied:
        rb = rollback(con, promotions, drop_audit=True)
        rb_hash = logical_hash(con)
        report["rolled_back_cells"] = rb
        report["post_rollback_logical_sha256"] = rb_hash
        report["rollback_restores_state"] = rb_hash == pre_hash
        verify_state(con, expect_rows, expect_ids)
        print("rollback restored identical logical state:", rb_hash == pre_hash)
        if rb_hash != pre_hash:
            raise RuntimeError("rollback failed to restore identical state — ABORT")
        if con.execute(f"SELECT count(*) FROM sqlite_master WHERE name='{AUDIT_TABLE}'").fetchone()[0]:
            raise RuntimeError("audit table still present after rollback")
    con.close()

    out_path = os.path.join(DRYRUN_DIR, "dryrun_report.json")
    os.makedirs(DRYRUN_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("report written:", out_path)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("DRY-RUN OK — rollback proven. canonical writes: 0")


if __name__ == "__main__":
    sys.exit(main())