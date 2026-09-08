"""Tests for deterministic repairs + CI guard (ticket 08).

Locks spec section 4: UK fallback provenance, grounding removal
that preserves Arabic/IPA/CJK, contamination guard, before/after
counts, input immutability. Fixtures only; no DB.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.deterministic_repairs import (
    apply_artifact_strip,
    apply_ipa_fallback,
    ci_guard_learner_text,
    strip_grounding_artifacts,
    uk_ipa_fallback,
)


class TestUkFallback(unittest.TestCase):
    def test_dictionary_wins(self):
        self.assertEqual(
            uk_ipa_fallback("həˈloʊ", "həˈləʊ"), ("həˈləʊ", "dictionary")
        )

    def test_fallback_from_us(self):
        self.assertEqual(
            uk_ipa_fallback("kæt", None), ("kæt", "fallback_from_us")
        )
        self.assertEqual(
            uk_ipa_fallback("kæt", ""), ("kæt", "fallback_from_us"))

    def test_both_missing(self):
        self.assertEqual(uk_ipa_fallback(None, None), (None, None))
        self.assertEqual(uk_ipa_fallback("", ""), (None, None))

    def test_no_slashes_introduced(self):
        value, _ = uk_ipa_fallback("kæt", None)
        self.assertNotIn("/", value)


class TestArtifactStrip(unittest.TestCase):
    def test_url_removed(self):
        self.assertEqual(
            strip_grounding_artifacts("see https://ex.com/a for more"),
            "see for more",
        )

    def test_bracket_citation_removed(self):
        self.assertEqual(
            strip_grounding_artifacts("معنى 【source†L12】 جميل"), "معنى جميل"
        )

    def test_dagger_removed(self):
        self.assertEqual(strip_grounding_artifacts("word† meaning"), "word meaning")

    def test_arabic_ipa_cjk_preserved(self):
        clean = "القطة تجلس /kæt/ على 猫 word"
        self.assertEqual(strip_grounding_artifacts(clean), clean)

    def test_empty_and_nonstring(self):
        self.assertEqual(strip_grounding_artifacts(""), "")
        self.assertIsNone(strip_grounding_artifacts(None))


class TestGuard(unittest.TestCase):
    def test_flags_contamination(self):
        self.assertEqual(
            ci_guard_learner_text("x https://a.b y"), ["url"])
        self.assertEqual(
            ci_guard_learner_text("x【s†L1】y"), ["bracket_citation", "dagger"])
        self.assertEqual(ci_guard_learner_text("see [12]"), ["bare_citation"])

    def test_clean_text_passes(self):
        self.assertEqual(ci_guard_learner_text("القطة تجلس على السجادة"), [])
        self.assertEqual(ci_guard_learner_text(""), [])
        self.assertEqual(ci_guard_learner_text(None), [])


class TestCounts(unittest.TestCase):
    def test_ipa_counts(self):
        rows = [
            {"phonetic_us": "a", "phonetic_uk": "b"},
            {"phonetic_us": "a", "phonetic_uk": None},
            {"phonetic_us": None},
        ]
        new_rows, counts = apply_ipa_fallback(rows)
        self.assertEqual(
            counts, {"dictionary": 1, "fallback_from_us": 1, "missing": 1}
        )
        self.assertEqual(new_rows[1]["phonetic_uk_source"], "fallback_from_us")
        self.assertIsNone(new_rows[2]["phonetic_uk_resolved"])
        self.assertNotIn("phonetic_uk_resolved", rows[1])  # no mutation

    def test_strip_counts(self):
        rows = [{"d": "a https://x.y b"}, {"d": "clean"}]
        new_rows, counts = apply_artifact_strip(rows, "d")
        self.assertEqual(counts, {"changed": 1, "unchanged": 1})
        self.assertEqual(new_rows[0]["d"], "a b")
        self.assertEqual(rows[0]["d"], "a https://x.y b")  # no mutation


if __name__ == "__main__":
    unittest.main()
