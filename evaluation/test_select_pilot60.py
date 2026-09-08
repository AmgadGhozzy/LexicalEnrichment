"""Tests for the 001A pilot sampler: determinism, quotas,
smoke exclusion, audit-monitoring (never forced)."""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation import select_pilot60 as sp
from evaluation.seeded_generator import load_seed_snapshot

SNAP = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                    "output", "EXP-SEEDED-001", "seed_snapshot_v1.jsonl")


class TestPilot60(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_seed_snapshot(SNAP)
        cls.feats, _ = sp.annotate(cls.records)

    def test_deterministic(self):
        a = sp.draw(self.feats)
        b = sp.draw(self.feats)
        self.assertEqual([f["key"] for f in a],
                         [f["key"] for f in b])
        self.assertEqual(sp.selection_hash(a), sp.selection_hash(b))

    def test_size_and_quotas(self):
        sel = sp.draw(self.feats)
        self.assertEqual(len(sel), 60)
        from collections import Counter
        pos = Counter(f["pos_group"] for f in sel)
        self.assertEqual(dict(pos), dict(sp.QUOTAS_POS))
        cefr = Counter(f["cefr"] for f in sel)
        self.assertEqual(dict(cefr), dict(sp.QUOTAS_CEFR))

    def test_mnemonic_null_all_included(self):
        sel = sp.draw(self.feats)
        pool_null = {f["key"] for f in self.feats
                     if f["mnemonic_null"]}
        sel_null = {f["key"] for f in sel if f["mnemonic_null"]}
        self.assertEqual(sel_null, pool_null)
        self.assertEqual(len(sel_null), 16)

    def test_smoke_excluded(self):
        sel = sp.draw(self.feats)
        keys = {(f["lemma"].strip().lower(),
                 (f["pos"] or "").strip().lower()) for f in sel}
        self.assertTrue(keys.isdisjoint(sp.SMOKE_KEYS))

    def test_coverage_floors(self):
        sel = sp.draw(self.feats)
        self.assertGreaterEqual(
            sum(1 for f in sel if f["technical"]), 8)
        # pool holds exactly 3 multi-POS lemmas (6 records): take all.
        self.assertEqual(
            sum(1 for f in sel if f["multi_pos"]), 6)
        self.assertGreaterEqual(
            sum(1 for f in sel if f["translations_multi"]), 20)
        self.assertGreaterEqual(
            sum(1 for f in sel if f["relations_poor"]), 6)


if __name__ == "__main__":
    unittest.main()