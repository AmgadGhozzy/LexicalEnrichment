"""Ticket-20 guarded promotion driver: 564 verified cells -> WordsMaster.db.

Wave-separated from migration_audit_2026_001 (untouched): writes audit to
migration_audit_2026_002 (superset schema: + candidate_hash, verdict,
provenance_json). Proven pattern (single txn, verify-inside, backup-first,
dry-run with rollback proof). The promotion manifest
(output/EXP-SEEDED-609/promotion_manifest_564.json) is the ONLY input.

No-op guard is VALUE-level (parsed-JSON equality), per the approved 564 scope:
conquest/antonyms spacing-only diff counts as NO-OP (excluded at manifest
build, re-asserted here).

Usage (production --execute requires the explicit governance lift flag):
  python -m evaluation.promote_remed609 --dry-run
  python -m evaluation.promote_remed609 --execute --allow-production [--target WordsMaster.db]
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MANIFEST = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output",
    "EXP-SEEDED-609", "promotion_manifest_564.json")
OUT_DIR = os.path.join(
    ROOT, ".scratch", "lexical-migration-build", "output", "EXP-SEEDED-609")
AUDIT_TABLE = "migration_audit_2026_002"
EXPECTED_PROMOTIONS = 564
ALLOWED_COLS = frozenset({"examples", "synonyms", "antonyms"})
EXCEPTION_IDS = frozenset({551, 1239, 3136, 1789, 4004, 4499, 2734, 412,
                           3628, 83, 3043, 3916})
AUTH_NOTE = ("Ticket 20 governance decision 2026-09-09 (corrected 564): "
             "AUTHORIZED — 564 VERIFIED PROMOTIONS ONLY. This wave only.")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canon(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def cols_of(con, table):
    return [d[1] for d in con.execute("pragma table_info(%s)" % table)]


def logical_hash(con, tables=("wordsMaster",)):
    dump = {}
    for t in tables:
        cols = cols_of(con, t)
        rows = con.execute("SELECT * FROM %s ORDER BY rowid" % t).fetchall()
        dump[t] = [dict(zip(cols, r)) for r in rows]
    return hashlib.sha256(canon(dump).encode("utf-8")).hexdigest()


def value_equal(before_text, after_text, col):
    """Value-level equality: parsed-JSON compare for relations, string
    compare otherwise. conquest/antonyms spacing-only diff => EQUAL."""
    if col in ("synonyms", "antonyms"):
        try:
            return json.loads(before_text) == json.loads(after_text)
        except (ValueError, TypeError):
            pass
    return before_text == after_text


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        man = json.load(f)
    claimed = man.pop("manifest_sha256")
    recomputed = hashlib.sha256(canon(man).encode("utf-8")).hexdigest()
    if claimed != recomputed:
        raise RuntimeError("promotion manifest hash mismatch")
    man["manifest_sha256"] = claimed
    return man


def snapshot_wordsmaster(con):
    cols = cols_of(con, "wordsMaster")
    idx = cols.index("id")
    rows = con.execute("SELECT * FROM wordsMaster ORDER BY rowid").fetchall()
    return cols, {r[idx]: dict(zip(cols, r)) for r in rows}


def pre_write_checklist(target, man):
    promos = man["promotions"]
    checks = {}
    checks["promotions"] = len(promos)
    checks["expected"] = EXPECTED_PROMOTIONS
    checks["count_ok"] = (len(promos) == EXPECTED_PROMOTIONS)
    checks["columns"] = sorted({p["col"] for p in promos})
    checks["columns_allowed"] = set(checks["columns"]) <= ALLOWED_COLS
    checks["exception_ids_in_scope"] = sorted(
        {p["id"] for p in promos} & EXCEPTION_IDS)
    checks["exceptions_excluded"] = (
        len(checks["exception_ids_in_scope"]) == 0)
    con = sqlite3.connect("file:%s?mode=ro" % target, uri=True)
    try:
        checks["rows"] = con.execute(
            "SELECT count(*) FROM wordsMaster").fetchone()[0]
        checks["pre_logical"] = logical_hash(con, ("wordsMaster",))
        mismatch_before = 0
        mismatch_hash = 0
        noop_leak = 0
        for p in promos:
            cur = con.execute(
                "SELECT %s FROM wordsMaster WHERE id=?" % p["col"],
                (p["id"],)).fetchone()[0]
            if cur != p["value_before"]:
                mismatch_before += 1
            raw = json.load(open(p["provenance"]["raw"], encoding="utf-8"))
            ch = hashlib.sha256(json.dumps(
                raw["candidate"], sort_keys=True,
                ensure_ascii=False).encode("utf-8")).hexdigest()
            if ch != p["candidate_hash"]:
                mismatch_hash += 1
            if value_equal(p["value_before"], p["value_after"], p["col"]):
                noop_leak += 1
        checks["value_before_drift"] = mismatch_before
        checks["candidate_hash_mismatch"] = mismatch_hash
        checks["noop_leak"] = noop_leak
    finally:
        con.close()
    checks["governance_note"] = AUTH_NOTE
    ok = (checks["count_ok"] and checks["columns_allowed"]
          and checks["exceptions_excluded"] and checks["rows"] == 7300
          and checks["value_before_drift"] == 0
          and checks["candidate_hash_mismatch"] == 0
          and checks["noop_leak"] == 0)
    checks["checklist_pass"] = ok
    return checks


def ensure_audit_table(con):
    con.execute(
        "CREATE TABLE IF NOT EXISTS %s ("
        "id INTEGER, col TEXT, value_before TEXT, value_after TEXT, "
        "value_after_sha TEXT, field TEXT, candidate_key TEXT, eval_id TEXT, "
        "adjudication TEXT, migrated_at TEXT, candidate_hash TEXT, "
        "verdict TEXT, provenance_json TEXT)" % AUDIT_TABLE)


def apply_and_verify(con, promos, now):
    for p in promos:
        con.execute("UPDATE wordsMaster SET %s=? WHERE id=?"
                    % p["col"], (p["value_after"], p["id"]))
    ensure_audit_table(con)
    for p in promos:
        con.execute(
            "INSERT INTO %s (id,col,value_before,value_after,"
            "value_after_sha,field,candidate_key,eval_id,adjudication,"
            "migrated_at,candidate_hash,verdict,provenance_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)" % AUDIT_TABLE,
            (p["id"], p["col"], p["value_before"], p["value_after"],
             hashlib.sha256(str(p["value_after"]).encode("utf-8")).hexdigest(),
             p["field"], p["candidate_key"],
             p["provenance"]["eval_id"], "candidate",
             now, p["candidate_hash"], "candidate",
             json.dumps(p["provenance"], ensure_ascii=False, sort_keys=True)))
    cells_ok = 0
    for p in promos:
        cur = con.execute("SELECT %s FROM wordsMaster WHERE id=?" % p["col"],
                          (p["id"],)).fetchone()[0]
        if cur == p["value_after"]:
            cells_ok += 1
    audit_ok = (con.execute("SELECT count(*) FROM %s" % AUDIT_TABLE)
                .fetchone()[0] == len(promos))
    state_ok = (con.execute("SELECT count(*) FROM wordsMaster").fetchone()[0]
                == 7300)
    if not (cells_ok == len(promos) and audit_ok and state_ok):
        raise RuntimeError(
            "in-txn verify failed: cells %d/%d audit %s state %s"
            % (cells_ok, len(promos), audit_ok, state_ok))
    return cells_ok


def full_diff(pre_snap, post_snap, cols):
    changed = set()
    for _id, before in pre_snap.items():
        after = post_snap[_id]
        for c in cols:
            if before[c] != after[c]:
                changed.add((_id, c))
    return changed


def dry_run():
    man = load_manifest()
    promos = man["promotions"]
    assert len(promos) == EXPECTED_PROMOTIONS
    assert not ({p["id"] for p in promos} & EXCEPTION_IDS)
    work = os.path.join(OUT_DIR, "dryrun")
    os.makedirs(work, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sandbox = os.path.join(work, "wordsMaster_dryrun_%s.db" % ts)
    shutil.copyfile(os.path.join(ROOT, "WordsMaster.db"), sandbox)
    con = sqlite3.connect(sandbox, isolation_level=None)
    try:
        cols, pre = snapshot_wordsmaster(con)
        pre_hash = logical_hash(con, ("wordsMaster",))
        now = datetime.now(timezone.utc).isoformat()
        con.execute("BEGIN IMMEDIATE")
        try:
            n = apply_and_verify(con, promos, now)
            _, post = snapshot_wordsmaster(con)
            changed = full_diff(pre, post, cols)
            expected = {(p["id"], p["col"]) for p in promos}
            assert changed == expected, (
                "diff mismatch: +%s -%s"
                % (sorted(changed - expected)[:5],
                   sorted(expected - changed)[:5]))
            con.execute("ROLLBACK")
        except BaseException:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        rb_hash = logical_hash(con, ("wordsMaster",))
        report = {"mode": "dry-run", "applied": n,
                  "changed_cells": len(changed),
                  "expected": EXPECTED_PROMOTIONS,
                  "diff_exact": True,
                  "pre_hash": pre_hash,
                  "rollback_equal": (rb_hash == pre_hash),
                  "sandbox": sandbox}
        with open(os.path.join(work, "dryrun_report_564.json"), "w",
                  encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("dry-run: applied=%d changed=%d rollback_equal=%s"
              % (n, len(changed), report["rollback_equal"]))
    finally:
        con.close()


def execute_production(target, allow):
    if not allow:
        raise SystemExit("refusing production write without --allow-production")
    man = load_manifest()
    promos = man["promotions"]
    checks = pre_write_checklist(target, man)
    print("== PRE-WRITE CHECKLIST ==")
    for k in ("promotions", "expected", "count_ok", "columns",
              "columns_allowed", "exceptions_excluded", "rows",
              "value_before_drift", "candidate_hash_mismatch", "noop_leak",
              "checklist_pass"):
        print("  %s: %s" % (k, checks[k]))
    if not checks["checklist_pass"]:
        raise SystemExit("ABORT: pre-write checklist failed")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(ROOT, "WordsMaster_backup_%s.db" % ts)
    shutil.copyfile(target, backup)
    assert sha_file(backup) == sha_file(target)
    con = sqlite3.connect(target, isolation_level=None)
    try:
        pre_hash = logical_hash(con, ("wordsMaster",))
        now = datetime.now(timezone.utc).isoformat()
        con.execute("BEGIN IMMEDIATE")
        try:
            n = apply_and_verify(con, promos, now)
            con.execute("COMMIT")
        except BaseException:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        rcon = sqlite3.connect("file:%s?mode=ro" % target, uri=True)
        try:
            post_hash = logical_hash(rcon, ("wordsMaster",))
            audit_n = rcon.execute(
                "SELECT count(*) FROM %s" % AUDIT_TABLE).fetchone()[0]
            integ = rcon.execute("PRAGMA integrity_check").fetchone()[0]
            assert audit_n == EXPECTED_PROMOTIONS and integ == "ok"
        finally:
            rcon.close()
        rep = {"outcome": "COMMITTED", "cells": n, "audit_rows": audit_n,
               "pre_hash": pre_hash, "post_hash": post_hash,
               "backup": backup, "manifest_sha": man["manifest_sha256"],
               "checks": checks, "governance": AUTH_NOTE}
        execd = os.path.join(OUT_DIR, "execution")
        os.makedirs(execd, exist_ok=True)
        with open(os.path.join(execd, "execution_report_564.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        print("EXECUTION COMMITTED — canonical writes this wave: %d" % n)
    finally:
        con.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--allow-production", action="store_true")
    ap.add_argument("--target", default=os.path.join(ROOT, "WordsMaster.db"))
    args = ap.parse_args(argv)
    if args.dry_run:
        dry_run()
    elif args.execute:
        execute_production(args.target, args.allow_production)
    else:
        raise SystemExit("specify --dry-run or --execute")


if __name__ == "__main__":
    main()
