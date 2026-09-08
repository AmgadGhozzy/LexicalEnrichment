"""Tests for the canonical identity folding contract (build ticket 04).

Locks spec section 1 / wayfinding 02+03 behavior: every sub-rule below
traces to a locked decision. No DB access; pure string fixtures.
"""

import json
import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.identity import (
    CANONICAL_POS,
    build_key,
    is_single_word_candidate,
    normalize_lemma,
)


def load_pos_enum(schema_name):
    with open(
        os.path.join(ROOT_DIR, "evaluation", "prompts", "schemas", schema_name),
        encoding="utf-8",
    ) as f:
        return set(json.load(f)["properties"]["pos"]["enum"])


class TestEnumLockstep(unittest.TestCase):
    def test_pos_matches_v1_schema(self):
        self.assertEqual(
            set(CANONICAL_POS), load_pos_enum("lexical_output.v1.json")
        )

    def test_pos_matches_v1_1_candidate_schema(self):
        self.assertEqual(
            set(CANONICAL_POS),
            load_pos_enum("lexical_output.v1.1-candidate.json"),
        )


class TestFolding(unittest.TestCase):
    def test_trim_lower_collapse(self):
        self.assertEqual(normalize_lemma("  Solar   SYSTEM\t"), "solar system")

    def test_nfc_and_diacritics_preserved(self):
        # e + combining acute must fold to NFC but keep the accent.
        self.assertEqual(normalize_lemma("café"), "café")
        self.assertEqual(normalize_lemma("CAFÉ"), "café")

    def test_hyphenated_kept(self):
        self.assertEqual(normalize_lemma("Well-Being"), "well-being")
        self.assertEqual(
            normalize_lemma("state-of-the-art"), "state-of-the-art"
        )

    def test_possessive_maps_to_base(self):
        self.assertEqual(normalize_lemma("dog's"), "dog")
        self.assertEqual(normalize_lemma("DOG'S"), "dog")

    def test_internal_apostrophe_preserved(self):
        self.assertEqual(normalize_lemma("don't"), "don't")

    def test_curly_apostrophe_folded_not_stripped(self):
        self.assertEqual(normalize_lemma("don’t"), "don't")

    def test_none_and_empty(self):
        self.assertEqual(normalize_lemma(None), "")
        self.assertEqual(normalize_lemma("   "), "")


class TestAdmissibility(unittest.TestCase):
    def test_single_words_pass(self):
        for w in ["well-being", "don't", "café", "get", "tv"]:
            self.assertTrue(is_single_word_candidate(w), w)

    def test_whitespace_is_multiword(self):
        self.assertFalse(is_single_word_candidate("solar system"))
        self.assertFalse(is_single_word_candidate("look back"))

    def test_stray_punctuation_fails(self):
        for w in ["", "well-being!", "(get)", "say.", "a,b", "up?"]:
            self.assertFalse(is_single_word_candidate(w), w)


class TestKey(unittest.TestCase):
    def test_key_shape(self):
        self.assertEqual(build_key("get", "verb"), ("get", "verb"))
        self.assertNotEqual(
            build_key("get", "verb"), build_key("get", "noun")
        )

    def test_all_enum_values_accepted(self):
        for pos in sorted(CANONICAL_POS):
            self.assertEqual(build_key("x", pos), ("x", pos))

    def test_composites_refused(self):
        for bad in ["noun+verb", "adj+prep", "NOUN", "noun ", "", "Noun"]:
            with self.assertRaises(ValueError, msg=bad):
                build_key("get", bad)

    def test_whitespace_lemma_refused(self):
        for bad in ["solar system", "", "  "]:
            with self.assertRaises(ValueError, msg=bad):
                build_key(bad, "noun")


if __name__ == "__main__":
    unittest.main()
