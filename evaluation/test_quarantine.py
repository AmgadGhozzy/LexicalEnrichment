"""Tests for quarantine formalization (ticket 10).

Locks: class completeness vs the 727 decomposition, 34/34
multiwords with topics and no leakage, no-promotion invariant,
BT-07 schema fit on :memory:. No DB, no staging reads.
"""

import json
import os
import sqlite3
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import evaluation.evidence_schema as es
from evaluation.quarantine import (
    assert_no_promotion,
    build_727_quarantine,
    build_multiword_quarantine,
)


def load_v2():
    path = os.path.join(
        ROOT_DIR, ".scratch", "lexical-migration-build", "output",
        "ielts_mapping_v2.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Test727(unittest.TestCase):
    def test_classes_sum_727(self):
        recs, total = build_727_quarantine({"artifact": "forensic_727"})
        self.assertEqual(total, 727)
        self.assertEqual(len(recs), 4)
        for r in recs:
            self.assertEqual(r["review_state"],
                             "quarantined_pending_item_review")
            self.assertEqual(r["row_level_materialization"],
                             "BLOCKED_on_Gate_B")

    def test_no_promotion(self):
        recs, _ = build_727_quarantine({"artifact": "forensic_727"})
        self.assertTrue(assert_no_promotion(recs))
        with self.assertRaises(ValueError):
            assert_no_promotion([{"lexical_identity_id": 5}])
        with self.assertRaises(ValueError):
            assert_no_promotion([{"review_state": "approved_x"}])


class TestMultiword(unittest.TestCase):
    def test_34_with_topics_no_leak(self):
        v2 = load_v2()
        rows = build_multiword_quarantine(v2["records"])
        self.assertEqual(len(rows), 34)
        for r in rows:
            self.assertTrue(r["topic"])
            self.assertIn(" ", r["normalized_form"])
        self.assertTrue(assert_no_promotion(rows))

    def test_wrong_count_refused(self):
        with self.assertRaises(ValueError):
            build_multiword_quarantine([])

    def test_schema_fit(self):
        v2 = load_v2()
        rows = build_multiword_quarantine(v2["records"])
        conn = sqlite3.connect(":memory:")
        es.create_schema(conn)
        for r in rows:
            es.add_quarantine(
                conn, r["kind"], r["original_form"],
                r["normalized_form"], r["source_name"],
                r["classification"], "test-run",
                source_row_id=str(r["source_row_id"]),
                status="quarantined")
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM quarantine_record").fetchone()[0],
            34)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM lexical_identity").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
