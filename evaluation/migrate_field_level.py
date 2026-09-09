#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""G4 transactional field-level migration engine.

Three modes:
  --dry-run                 build a sandbox copy from WordsMaster.db,
                            apply, verify, then roll back and prove the
                            logical state is byte-identical (hash).
  --execute                 PRODUCTION migration of the G3 promotion set
                            into WordsMaster.db (the real one), following
                            the ratified protocol: pre-write checklist ->
                            backup-first -> single transaction -> audit
                            (expected == actual == 1384) -> verify-inside-
                            transaction before COMMIT -> post-commit
                            re-verification -> abort/rollback on any
                            failure. Requires --allow-production AND the
                            explicit EXECUTE authorization (documented in
                            the report). NEVER passes without both.
  --target <path>           apply to an arbitrary copy (kept for sandbox
                            diagnostics) with --allow-production guard.

Safety invariants (all modes):
- Field-level cells only, keyed by stable `id`; no row overwrite, no
  DELETE of wordsMaster data, no id rebuild, no rank / frequency /
  difficultyScore / CEFR / unitId / curriculum touch.
- Promoted columns are exactly the 8 content columns endorsed by G3.
- Provenance-gap card (billion/num) excluded before writing.
- On ANY mismatch/error: ABORT + rollback; never "commit-then-fix".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDMASTER = os.path.join(ROOT, "WordsMaster.db")
MANIFEST = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "migration_readiness",
    "migration_manifest_348.json",
)
MANIFEST_META = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "migration_readiness",
    "manifest.json",
)
GEN_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output",
    "EXP-SEEDED-001A", "generated_356",
)
DRYRUN_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output",
    "migration_readiness", "dryrun",
)
EXECUTION_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output",
    "migration_readiness", "execution",
)

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
PROTECTED_COLS = {
    "id", "wordEn", "pos", "cefrLevel", "fromOxford", "rank", "frequency",
    "difficultyScore", "unitId", "phoneticUs", "phoneticUk", "phoneticAr",
    "translit", "syllabify", "usageNote", "category", "primarySense",
    "semanticTags", "register", "relatedWords", "wordFamily",
}
AUDIT_TABLE = "migration_audit_2026_001"
EXPECTED_PROMOTIONS = 1384
AUTH_NOTE = (
    "governance lock LIFTED by human-owner EXECUTE decision 2026-09-08 "
    "(Monday final decision); protocol ratified verbatim; 1384 field-level "
    "promotions. This migration wave only; 348/356/AI-rubric/pilot-60 stay frozen."
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def json_dump(v) -> str:
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def candidate_field_write_value(cand: dict, field: str) -> str:
    rel = cand.get("relations") or {}
    if field.startswith("relations_"):
        v = rel.get(field[len("relations_"):])
    elif field == "translations":
        v = cand.get("translations")
    else:
        v = cand.get(field)
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
    dump = {}
    for t in tables:
        cols = [d[1] for d in con.execute(f"pragma table_info({t})")]
        rows = con.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
        dump[t] = [dict(zip(cols, r)) for r in rows]
    return sha256_text(json_dump(dump))


def snapshot_wordsmaster(con) -> dict:
    cols = [d[1] for d in con.execute("pragma table_info(wordsMaster)")]
    return {
        r[0]: dict(zip(cols, r))
        for r in con.execute("SELECT * FROM wordsMaster ORDER BY id").fetchall()
    }


def copy_db(src: str, dst: str) -> None:
    scon = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dcon = sqlite3.connect(dst)
    with dcon:
        scon.backup(dcon)
    scon.close()
    dcon.close()


def load_promotions(snapshot: dict):
    """Build the promotion cell list from the frozen manifest.

    Excludes provenance-gap cards (billion/num) per G2; skips manual
    sense_separation; skips empty candidates (already 'keep' in manifest).
    Returns list of dicts with id/col/field/value_after/after_sha/key/eval_id.
    """
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    promotions = []
    for r in manifest["records"]:
        key = r["candidate_key"]
        if r["provenance_gap"]:
            continue
        raw_path = os.path.join(GEN_DIR, "raw", key.replace("/", "__") + ".json")
        cand = json.load(open(raw_path, encoding="utf-8")).get("candidate") or {}
        for field, action in r["actions"].items():
            if action != "promote" or field not in FIELD_COL:
                continue
            val = candidate_field_write_value(cand, field)
            if val is None:
                raise RuntimeError(f"promote without value {key}/{field}")
            if isinstance(snapshot, dict) and r["wordsMaster_id"] not in snapshot:
                ex = list(snapshot)[:3]
                raise RuntimeError(
                    f"wordsMaster id {r['wordsMaster_id']} for {key} not in "
                    f"snapshot (sample {ex}) — identity mismatch"
                )
            promotions.append({
                "id": r["wordsMaster_id"],
                "col": FIELD_COL[field],
                "field": field,
                "value_after": val,
                "value_after_sha": sha256_text(val),
                "candidate_key": key,
                "eval_id": r["eval_id"],
                "adjudication": r["adjudication"]["fields"].get(field),
            })
    return promotions


def verify_cells(con, snapshot: dict, promotions: list) -> int:
    """Every (id,col) in promotions must equal value_after; every other
    cell must equal its pre-write snapshot value."""
    prom = {(p["id"], p["col"]): p for p in promotions}
    checked = 0
    for rid, row in snapshot.items():
        for col, before in row.items():
            cur = con.execute(
                f"SELECT {col} FROM wordsMaster WHERE id=?", (rid,)
            ).fetchone()[0]
            p = prom.get((rid, col))
            if p is not None:
                if cur != p["value_after"]:
                    raise RuntimeError(
                        f"promoted cell mismatch {rid}/{col}: expected "
                        f"{p['value_after'][:60]!r} got {cur[:60]!r}"
                    )
                checked += 1
            elif cur != before:
                raise RuntimeError(
                    f"unexpected cell mutation {rid}/{col}: before "
                    f"{before!r} -> now {cur!r}"
                )
    return checked


def verify_state(con, expect_rows: int, expect_ids: set) -> None:
    rows = con.execute("SELECT count(*) FROM wordsMaster").fetchone()[0]
    ids = set(x[0] for x in con.execute("SELECT id FROM wordsMaster"))
    if rows != expect_rows:
        raise RuntimeError(f"row count changed {rows} != {expect_rows}")
    if ids != expect_ids:
        raise RuntimeError("id set changed (identity drift)")
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("integrity_check failed")


def verify_audit(con, promotions: list) -> int:
    n = con.execute(f"SELECT count(*) FROM {AUDIT_TABLE}").fetchone()[0]
    if n != len(promotions):
        raise RuntimeError(f"audit rows {n} != promotions {len(promotions)}")
    for p in promotions:
        row = con.execute(
            f"SELECT value_before, value_after, value_after_sha, field, "
            f"candidate_key, eval_id, adjudication FROM {AUDIT_TABLE} "
            f"WHERE id=? AND col=?", (p["id"], p["col"])
        ).fetchone()
        if not row:
            raise RuntimeError(f"audit gap {p['id']}/{p['col']}")
        vb, va, vash, fld, ck, ei, adj = row
        if va != p["value_after"] or vash != p["value_after_sha"]:
            raise RuntimeError(f"audit value/hash mismatch {p['id']}/{p['col']}")
        if vb is None:
            raise RuntimeError(f"audit missing value_before {p['id']}/{p['col']}")
    return n


def apply_and_verify(con, promotions: list, snapshot: dict,
                     expect_rows: int, expect_ids: set) -> int:
    """Single transaction: apply + verify INSIDE transaction; COMMIT only
    if every check passes, else ROLLBACK (abort)."""
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} "
        "(id INTEGER, col TEXT, value_before TEXT, value_after TEXT, "
        "value_after_sha TEXT, field TEXT, candidate_key TEXT, eval_id TEXT, "
        "adjudication TEXT, migrated_at TEXT)"
    )
    if con.execute(f"SELECT count(*) FROM {AUDIT_TABLE}").fetchone()[0]:
        raise RuntimeError(f"audit table {AUDIT_TABLE} already has rows — "
                           "re-run requires fresh permission")
    con.execute("BEGIN")
    try:
        for p in promotions:
            before = snapshot[p["id"]][p["col"]]
            con.execute(
                f"UPDATE wordsMaster SET {p['col']}=? WHERE id=?",
                (p["value_after"], p["id"]),
            )
            con.execute(
                f"INSERT INTO {AUDIT_TABLE} (id, col, value_before, value_after, "
                f"value_after_sha, field, candidate_key, eval_id, adjudication, "
                f"migrated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (p["id"], p["col"], before, p["value_after"], p["value_after_sha"],
                 p["field"], p["candidate_key"], p["eval_id"], p["adjudication"],
                 datetime.now(timezone.utc).isoformat()),
            )
        checked = verify_cells(con, snapshot, promotions)
        verify_audit(con, promotions)
        verify_state(con, expect_rows, expect_ids)
        con.execute("COMMIT")
        return checked
    except Exception:
        con.execute("ROLLBACK")
        raise


def manual_rollback(con, promotions: list, snapshot: dict) -> None:
    """Post-commit abort path: restore every promoted cell from the
    pre-write snapshot, drop the audit table, re-verify identical state."""
    con.execute("BEGIN")
    try:
        for p in promotions:
            con.execute(
                f"UPDATE wordsMaster SET {p['col']}=? WHERE id=?",
                (snapshot[p["id"]][p["col"]], p["id"]),
            )
        con.execute(f"DROP TABLE IF EXISTS {AUDIT_TABLE}")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def pre_write_checklist():
    checks = {}
    meta = json.load(open(MANIFEST_META, encoding="utf-8"))
    checks["manifest_sha256_file"] = sha256_file(MANIFEST)
    checks["manifest_sha256_meta"] = meta.get("export_sha256")
    checks["manifest_hash_matches"] = checks["manifest_sha256_file"] == checks["manifest_sha256_meta"]
    if not checks["manifest_hash_matches"]:
        raise RuntimeError("manifest hash mismatch — abort")

    con = sqlite3.connect(f"file:{WORDMASTER}?mode=ro", uri=True)
    snapshot = snapshot_wordsmaster(con)
    checks["pre_logical_sha256_wordsmaster"] = logical_hash(con, ("wordsMaster",))
    checks["rows"] = len(snapshot)
    checks["ids"] = set(snapshot)
    con.close()
    checks["production_file_sha256"] = sha256_file(WORDMASTER)
    checks["production_mtime_iso"] = datetime.fromtimestamp(
        os.path.getmtime(WORDMASTER), tz=timezone.utc
    ).isoformat()

    promotions = load_promotions(snapshot)
    checks["promotions"] = len(promotions)
    checks["expected"] = EXPECTED_PROMOTIONS
    checks["promotion_count_ok"] = len(promotions) == EXPECTED_PROMOTIONS
    if not checks["promotion_count_ok"]:
        raise RuntimeError(f"promotion count {len(promotions)} != {EXPECTED_PROMOTIONS}")
    keys = {p["candidate_key"] for p in promotions}
    checks["billion_excluded"] = "billion/num" not in keys
    if not checks["billion_excluded"]:
        raise RuntimeError("billion/num not excluded — abort")
    prom_cols = {p["col"] for p in promotions}
    checks["columns"] = sorted(prom_cols)
    checks["protected_cols_touched"] = sorted(prom_cols & PROTECTED_COLS)
    if checks["protected_cols_touched"]:
        raise RuntimeError(f"protected columns in promotion set: {prom_cols & PROTECTED_COLS}")
    checks["governance_note"] = AUTH_NOTE
    return checks, promotions, snapshot


def execute_production() -> None:
    os.makedirs(EXECUTION_DIR, exist_ok=True)
    print("== PRE-WRITE CHECKLIST ==")
    checks, promotions, snapshot = pre_write_checklist()
    for k, v in checks.items():
        print(f"  {k}: {v}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = os.path.join(ROOT, f"WordsMaster_backup_{ts}.db")
    print("== BACKUP ==")
    copy_db(WORDMASTER, backup_path)
    bcon = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
    backup_logical = logical_hash(bcon, ("wordsMaster",))
    backup_rows = bcon.execute("SELECT count(*) FROM wordsMaster").fetchone()[0]
    bcon.close()
    checks["backup_path"] = backup_path
    checks["backup_file_sha256"] = sha256_file(backup_path)
    checks["backup_logical_sha256"] = backup_logical
    checks["backup_rows"] = backup_rows
    checks["backup_logical_equals_pre"] = backup_logical == checks["pre_logical_sha256_wordsmaster"]
    if not checks["backup_logical_equals_pre"]:
        raise RuntimeError("backup logical hash != pre — abort")
    print(f"  backup: {backup_path}")
    print(f"  backup logical == pre: {checks['backup_logical_equals_pre']}")

    print("== APPLY (single transaction, verify-then-commit) ==")
    con = sqlite3.connect(WORDMASTER)
    con.isolation_level = None
    applied = apply_and_verify(con, promotions, snapshot, checks["rows"], checks["ids"])
    print(f"  applied+verified cells inside txn: {applied}")

    print("== POST-COMMIT RE-VERIFICATION (fresh read-only) ==")
    rcon = sqlite3.connect(f"file:{WORDMASTER}?mode=ro", uri=True)
    recheck = verify_cells(rcon, snapshot, promotions)
    verify_state(rcon, checks["rows"], checks["ids"])
    audit_n = verify_audit(rcon, promotions)
    post_logical = logical_hash(rcon, ("wordsMaster",))
    full_hash = logical_hash(rcon, ("wordsMaster", AUDIT_TABLE))
    rcon.close()
    checks["post_logical_sha256_wordsmaster"] = post_logical
    checks["full_state_sha256_wordsmaster_plus_audit"] = full_hash
    checks["post_commit_recheck_cells"] = recheck
    checks["audit_rows"] = audit_n
    checks["audit_rows_match"] = audit_n == applied == EXPECTED_PROMOTIONS
    checks["production_file_sha256_after"] = sha256_file(WORDMASTER)
    checks["production_mtime_iso_after"] = datetime.fromtimestamp(
        os.path.getmtime(WORDMASTER), tz=timezone.utc
    ).isoformat()
    if not checks["audit_rows_match"]:
        raise RuntimeError("audit mismatch after commit — manual rollback")
    if post_logical == checks["pre_logical_sha256_wordsmaster"]:
        raise RuntimeError("no logical change detected post-commit")

    report = {
        "decision": {
            "action": "EXECUTE 1384 field-level promotions",
            "authorization": AUTH_NOTE,
            "protocol": (
                "pre-write checklist -> backup-first -> single transaction -> "
                "audit(expected==actual==1384) -> verify-inside-txn -> post-commit "
                "re-verification -> abort/rollback on any failure"
            ),
        },
        "checks": {k: (sorted(v) if isinstance(v, set) else v) for k, v in checks.items()
                   if k != "ids"},
        "ids_count": len(checks["ids"]),
        "outcome": "COMMITTED" if checks["audit_rows_match"] else "ABORTED",
        "canonical_writes_after_execution": 1,
    }
    report_path = os.path.join(EXECUTION_DIR, "execution_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print("== DONE ==")
    print(f"  audit rows: {audit_n}")
    print(f"  pre  logical sha: {checks['pre_logical_sha256_wordsmaster']}")
    print(f"  post logical sha: {post_logical}")
    print(f"  full state (wordsMaster + audit): {full_hash}")
    print(f"  report: {report_path}")
    print("EXECUTION COMMITTED — canonical writes: 1 (this wave)")


def dry_run() -> None:
    os.makedirs(DRYRUN_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = os.path.join(DRYRUN_DIR, f"wordsMaster_dryrun_{ts}.db")
    copy_db(WORDMASTER, target)
    con = sqlite3.connect(target)
    con.isolation_level = None
    snapshot = snapshot_wordsmaster(con)
    promotions = load_promotions(snapshot)
    pre = logical_hash(con, ("wordsMaster",))
    applied = apply_and_verify(con, promotions, snapshot, len(snapshot), set(snapshot))
    post = logical_hash(con, ("wordsMaster",))
    with open(os.path.join(DRYRUN_DIR, "dryrun_report.json"), "w", encoding="utf-8") as f:
        json.dump({
            "promotions": len(promotions), "applied": applied,
            "audit_rows": con.execute(f"SELECT count(*) FROM {AUDIT_TABLE}").fetchone()[0],
            "pre_logical_sha256": pre, "post_logical_sha256": post,
            "manifest": json.load(open(MANIFEST_META, encoding="utf-8")).get("export_sha256"),
        }, f, ensure_ascii=False, indent=1)
    manual_rollback(con, promotions, snapshot)
    rb = logical_hash(con, ("wordsMaster",))
    print(f"dry-run: applied={applied} pre={pre} rollback_equal={rb == pre}")
    if rb != pre:
        raise RuntimeError("dry-run rollback mismatch")
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--target", default=None)
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()

    if args.execute:
        if not args.allow_production:
            parser.error("--execute requires --allow-production (explicit governance lift)")
        execute_production()
        return
    if args.dry_run:
        dry_run()
        return
    if args.target:
        prod = os.path.abspath(WORDMASTER)
        target = os.path.abspath(args.target)
        if target == prod and not args.allow_production:
            parser.error("refusing production WordsMaster.db without --allow-production")
        con = sqlite3.connect(target)
        con.isolation_level = None
        snapshot = snapshot_wordsmaster(con)
        promotions = load_promotions(snapshot)
        apply_and_verify(con, promotions, snapshot, len(snapshot), set(snapshot))
        print("target apply ok (kept applied + audit); cells:", len(promotions))
        con.close()
        return
    parser.error("one of --dry-run | --execute | --target is required")


if __name__ == "__main__":
    sys.exit(main())