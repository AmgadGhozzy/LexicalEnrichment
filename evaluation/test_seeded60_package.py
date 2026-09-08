"""Tests for the seeded-60 blind package builder.

Invariants: 60 items, DTO shape equality, isolation gate,
determinism, map coverage, manifest pins.
"""

import json
import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation import build_seeded60_package as b
from evaluation.blind_package import (
    FIELDS, CRITICAL_ERRORS, assert_blind)

BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                    "output")
PILOT = os.path.join(BASE, "EXP-SEEDED-001A", "pilot60.json")
GENERATED = os.path.join(BASE, "EXP-SEEDED-001A", "generated")


def _load():
    identities = b.load_identities(PILOT)
    rows, missing_rows = b.load_legacy_rows(b.WORDS_MASTER,
                                            identities)
    arms, missing_arms = b.load_candidate_arms(GENERATED,
                                               identities)
    return identities, rows, arms, missing_rows, missing_arms


class TestSeeded60Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.identities, cls.rows, cls.arms, cls.missing_rows,
         cls.missing_arms) = _load()

    def test_no_missing_inputs(self):
        self.assertEqual(self.missing_rows, [])
        self.assertEqual(self.missing_arms, [])
        self.assertEqual(len(self.identities), 60)

    def test_build_and_gate(self):
        items = b.build_items(self.identities, self.rows,
                              self.arms)
        package_items, id_map = b.build_package_60(items)
        self.assertEqual(len(package_items), 60)
        self.assertEqual(len(id_map), 60)
        self.assertTrue(assert_blind(package_items))
        for it in package_items:
            self.assertEqual(set(it["armA"].keys()),
                             set(it["armB"].keys()))
            self.assertEqual(set(it["ballot"]["fields"].keys()),
                             set(FIELDS))
            self.assertEqual(
                set(it["ballot"]["critical_errors"].keys()),
                set(CRITICAL_ERRORS))
            self.assertTrue(it["eval_id"].startswith(
                b.EVAL_ID_60 + "-"))

    def test_deterministic(self):
        items = b.build_items(self.identities, self.rows,
                              self.arms)
        p1, m1 = b.build_package_60(items)
        p2, m2 = b.build_package_60(items)
        self.assertEqual(
            [i["eval_id"] for i in p1], [i["eval_id"] for i in p2])
        self.assertEqual(m1, m2)
        sides = [v["candidate_side"] for v in m1.values()]
        self.assertIn("A", sides)
        self.assertIn("B", sides)

    def test_map_covers_items(self):
        items = b.build_items(self.identities, self.rows,
                              self.arms)
        package_items, id_map = b.build_package_60(items)
        self.assertEqual({i["eval_id"] for i in package_items},
                         set(id_map.keys()))

    def test_arms_differ_somewhere(self):
        # Sanity: seeded arms are not byte-copies of legacy arms
        # (otherwise the blind comparison would be vacuous).
        items = b.build_items(self.identities, self.rows,
                              self.arms)
        package_items, _ = b.build_package_60(items)
        identical = sum(1 for it in package_items
                        if it["armA"] == it["armB"])
        self.assertLess(identical, len(package_items))


if __name__ == "__main__":
    unittest.main()