"""Tests for versioned frequency observations + dense rank (ticket 06).

Locks spec section 2 / wayfinding 01: pinned recording, dense-rank
semantics, scope separation. Pinned fixtures only; no network, no DB.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.frequency import (
    build_observation,
    derive_ranks,
    ranks_by_scope,
)

V1 = {"source_version": "wordfreq-3.1", "lang": "en"}


def obs(lemma, pos, zipf, **kw):
    args = dict(V1)
    args.update(kw)
    return build_observation((lemma, pos), zipf, **args)


class TestRecording(unittest.TestCase):
    def test_full_observation(self):
        o = obs("apple", "noun", 5.0, corpus_id="c4")
        self.assertEqual(o["source"], "wordfreq")
        self.assertEqual(o["metric"], "zipf")
        self.assertEqual(o["corpus_id"], "c4")
        self.assertEqual(o["identity_key"], ["apple", "noun"])
        self.assertTrue(o["observed_at"])

    def test_missing_pins_rejected(self):
        with self.assertRaises(ValueError):
            build_observation(("a", "noun"), 5.0, source_version="", lang="en")
        with self.assertRaises(ValueError):
            build_observation(("a", "noun"), 5.0, source_version="v", lang="")

    def test_nonfinite_zipf_rejected(self):
        for bad in (float("nan"), float("inf"), "5.0", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                obs("a", "noun", bad)

    def test_bad_key_rejected(self):
        for bad in (None, ("only",), ("", "noun"), "apple"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                build_observation(bad, 5.0, **V1)

    def test_no_db_footprint(self):
        import evaluation.frequency as fq

        src = open(fq.__file__, encoding="utf-8").read()
        for token in ("sqlite", "connect", "open(", "urllib", "requests"):
            self.assertNotIn(token, src)


class TestDenseRank(unittest.TestCase):
    def test_basic_dense(self):
        rows = [
            obs("apple", "noun", 5.0),
            obs("banana", "noun", 5.0),
            obs("cat", "noun", 4.9),
        ]
        self.assertEqual(
            derive_ranks(rows),
            {("apple", "noun"): 1, ("banana", "noun"): 1, ("cat", "noun"): 2},
        )

    def test_input_order_independent(self):
        rows = [
            obs("cat", "noun", 4.9),
            obs("banana", "noun", 5.0),
            obs("apple", "noun", 5.0),
        ]
        self.assertEqual(
            derive_ranks(rows),
            {("apple", "noun"): 1, ("banana", "noun"): 1, ("cat", "noun"): 2},
        )

    def test_no_unique_ordinals(self):
        rows = [obs("a", "noun", 5.0), obs("b", "noun", 5.0)]
        self.assertEqual(len(set(derive_ranks(rows).values())), 1)

    def test_mixed_scopes_refused(self):
        rows = [
            obs("a", "noun", 5.0),
            obs("b", "noun", 4.0, source_version="wordfreq-9.9"),
        ]
        with self.assertRaises(ValueError):
            derive_ranks(rows)

    def test_scopes_partitioned(self):
        rows = [
            obs("a", "noun", 5.0),
            obs("b", "noun", 4.0, source_version="wordfreq-9.9"),
        ]
        out = ranks_by_scope(rows)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[("wordfreq", "wordfreq-3.1", "en", "zipf")],
                         {("a", "noun"): 1})
        self.assertEqual(out[("wordfreq", "wordfreq-9.9", "en", "zipf")],
                         {("b", "noun"): 1})

    def test_supersede_visible(self):
        rows = [obs("a", "noun", 5.0), obs("a", "noun", 1.0),
                obs("b", "noun", 2.0)]
        self.assertEqual(
            derive_ranks(rows), {("b", "noun"): 1, ("a", "noun"): 2}
        )


if __name__ == "__main__":
    unittest.main()
