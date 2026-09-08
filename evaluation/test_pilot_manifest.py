"""Tests for the pilot manifest builder (ticket 11).

Locks: determinism, exact N, exclusions, hash stability,
CEFR-OPEN flag, no convenience strata. Fixtures only.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.pilot_manifest import (
    CEFR_STRATUM_AUTHORITY,
    allocate,
    freeze_manifest,
    sample_manifest,
)


def rows(n, cefr="B2", pos="noun"):
    return [
        {"id": i, "lemma": "w%d" % i, "pos": pos, "cefr": cefr,
         "freq": 4, "unit": 1}
        for i in range(1, n + 1)
    ]


class TestAllocate(unittest.TestCase):
    def test_sums_to_total(self):
        q = allocate({("B2", "noun"): 700, ("A1", "verb"): 300}, 100)
        self.assertEqual(sum(q.values()), 100)
        self.assertTrue(all(v >= 2 for v in q.values()))

    def test_tiny_cells_kept_whole(self):
        q = allocate({("C2", "modal"): 2, ("B2", "noun"): 700}, 100)
        self.assertEqual(q[("C2", "modal")], 2)


class TestManifest(unittest.TestCase):
    def test_deterministic(self):
        uni = rows(200) + rows(200, cefr="A1", pos="verb")
        for r in uni[200:]:
            r["id"] += 1000
        e1, _ = sample_manifest(uni, set(), set(), set(), total=50)
        e2, _ = sample_manifest(uni, set(), set(), set(), total=50)
        self.assertEqual([e["id"] for e in e1], [e["id"] for e in e2])

    def test_exclusions_and_n(self):
        uni = rows(300)
        e, rep = sample_manifest(uni, {1, 2, 3}, {4, 5}, set(), total=100)
        ids = {x["id"] for x in e}
        self.assertEqual(len(e), 100)
        self.assertTrue(ids.isdisjoint({1, 2, 3, 4, 5}))
        self.assertEqual(rep["excluded_golden"], 3)
        self.assertEqual(rep["excluded_prior_exp"], 2)

    def test_overlap_flag(self):
        uni = rows(100)
        e, _ = sample_manifest(uni, set(), set(), {10, 20}, total=50)
        flagged = {x["id"] for x in e if x["ielts_overlap"]}
        self.assertTrue(flagged <= {10, 20})

    def test_cefr_open_flag(self):
        uni = rows(100)
        _, rep = sample_manifest(uni, set(), set(), set(), total=50)
        self.assertIn("OPEN", rep["cefr_stratum_authority"])
        self.assertIn("OPEN", CEFR_STRATUM_AUTHORITY)

    def test_hash_stable(self):
        uni = rows(100)
        e, rep = sample_manifest(uni, set(), set(), set(), total=50)
        m1 = freeze_manifest(e, rep, "abc")
        m2 = freeze_manifest(e, rep, "abc")
        self.assertEqual(m1["manifest_hash"], m2["manifest_hash"])
        e3, _ = sample_manifest(uni, set(), set(), {7}, total=100)
        m3 = freeze_manifest(e3, rep, "abc")
        flagged = [x for x in e3 if x["id"] == 7 and x["ielts_overlap"]]
        self.assertEqual(len(flagged), 1)
        e4, _ = sample_manifest(uni, set(), set(), set(), total=100)
        m4 = freeze_manifest(e4, rep, "abc")
        self.assertNotEqual(m3["manifest_hash"], m4["manifest_hash"])


if __name__ == "__main__":
    unittest.main()
