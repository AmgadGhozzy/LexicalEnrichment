"""Tests for the deterministic IELTS cascade (ticket 09).

Locks the BT-03 first-match order on fixtures plus BT-07 schema
integration on :memory:. A full-artifact reproduction check lives
in the execution script output, not here (fixtures stay small).
"""

import os
import sqlite3
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation import evidence_schema as es
from evaluation.ielts_cascade import (
    build_master_universe,
    classify_row,
    count_by_class,
    run_mapping,
)

UNIVERSE = {("adopt", frozenset({"verb"})), ("trust", frozenset({"verb"}))}
UNIV = {"adopt": {"verb"}, "trust": {"verb"}}


class TestCascade(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(
            classify_row("adopt", "verb", UNIV),
            ("NORMALIZED_LEMMA_POS_EXACT", "verb"),
        )

    def test_case_folds_to_exact(self):
        self.assertEqual(
            classify_row("Adopt", "verb", UNIV)[0],
            "NORMALIZED_LEMMA_POS_EXACT",
        )

    def test_diff_pos(self):
        cls, matched = classify_row("trust", "noun", UNIV)
        self.assertEqual(cls, "SAME_LEMMA_DIFFERENT_POS")
        self.assertIsNone(matched)  # classification decides nothing

    def test_unmappable_pos_is_class2(self):
        cls, _ = classify_row("adopt", "interjection", UNIV)
        self.assertEqual(cls, "NORMALIZED_LEMMA_EXACT")

    def test_multiword_before_match(self):
        # even if components existed, whitespace short-circuits to #4
        uni = {"solar": {"noun"}, "system": {"noun"}}
        self.assertEqual(
            classify_row("solar system", "noun", uni)[0], "MULTIWORD"
        )

    def test_new_word(self):
        self.assertEqual(
            classify_row("adolescence", "noun", UNIV)[0], "NEW_SINGLE_WORD"
        )

    def test_empty_unresolved(self):
        self.assertEqual(classify_row("", "noun", UNIV)[0],
                         "UNRESOLVED_MALFORMED")
        self.assertEqual(classify_row(None, "noun", UNIV)[0],
                         "UNRESOLVED_MALFORMED")

    def test_counts_shape(self):
        cand = lambda w, p: [{"word": w, "pos": p}]
        recs = run_mapping(
            [
                {"ielts_row_id": 1, "source_lemma": "adopt",
                 "pos": "verb", "topic": "T",
                 "candidates": cand("adopt", "verb")},
                {"ielts_row_id": 2, "source_lemma": "trust",
                 "pos": "noun", "topic": "T",
                 "candidates": cand("trust", "verb")},
                {"ielts_row_id": 3, "source_lemma": "solar system",
                 "pos": "noun", "topic": "T", "candidates": []},
                {"ielts_row_id": 4, "source_lemma": "adolescence",
                 "pos": "noun", "topic": "T", "candidates": []},
            ]
        )
        counts = count_by_class(recs)
        self.assertEqual(counts["NORMALIZED_LEMMA_POS_EXACT"], 1)
        self.assertEqual(counts["SAME_LEMMA_DIFFERENT_POS"], 1)
        self.assertEqual(counts["MULTIWORD"], 1)
        self.assertEqual(counts["NEW_SINGLE_WORD"], 1)
        self.assertEqual(sum(counts.values()), 4)


class TestUniverseAndSchema(unittest.TestCase):
    def test_universe_uses_locked_folding(self):
        entries = [
            {"candidates": [{"word": "Adopt", "pos": "verb"}]},
            {"candidates": [{"word": "x", "pos": "noun+verb"}]},
        ]
        uni = build_master_universe(entries)
        self.assertEqual(uni, {"adopt": {"verb"}})  # composite dropped

    def test_records_fit_mapping_provenance(self):
        conn = sqlite3.connect(":memory:")
        es.create_schema(conn)
        recs = run_mapping(
            [{"ielts_row_id": 1, "source_lemma": "adopt", "pos": "verb",
              "topic": "T"}]
        )
        for r in recs:
            es.add_mapping_provenance(
                conn, r["ielts_row_id"], r["source_lemma"],
                r["normalized_form"], r["source_pos"] or "",
                r["classification"], "test-run",
                matched_pos=r["matched_pos"], topic_ref=r["topic"])
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM mapping_provenance").fetchone()[0],
            len(recs))


if __name__ == "__main__":
    unittest.main()
