"""Tests for the blind evaluation package builder (ticket BT-13).

Locks: arm-shape equality, identifier-leak refusal, seeded side
balance + determinism, map separation, input freezing. Fixtures
only; no DB, no judging.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.blind_package import (
    assert_blind,
    blank_ballot,
    build_package,
    candidate_arm,
    freeze_eval_input,
    legacy_arm,
)


def cand_output():
    return {
        "definition_en": "a test", "explanation_ar": "اختبار",
        "examples": [{"example_text": "I saw the w.", "intended_cefr": "A1"}],
        "translations": {"arabic_ar": "و"},
        "synonyms": ["x"], "antonyms": [], "collocations": [],
        "mnemonic_ar": None,
    }


def legacy_row():
    return {
        "definitionEn": "a test", "definitionAr": "اختبار",
        "examples": '{"A1": "I saw the w.", "A2": "We saw the w."}',
        "arabicAr": "و", "synonyms": '["x"]', "antonyms": "[]",
        "mnemonicAr": None,
    }


def item(i):
    return {"eval_key": "K-%d" % i, "lemma": "w", "pos": "noun",
            "candidate_output": cand_output(), "legacy_row": legacy_row()}


class TestArms(unittest.TestCase):
    def test_same_shape(self):
        self.assertEqual(set(candidate_arm(cand_output()).keys()),
                         set(legacy_arm(legacy_row()).keys()))

    def test_level_keys_stripped(self):
        arm = legacy_arm(legacy_row())
        self.assertEqual(arm["examples"],
                         ["I saw the w.", "We saw the w."])
        arm2 = candidate_arm(cand_output())
        self.assertEqual(arm2["examples"], ["I saw the w."])


class TestBlinding(unittest.TestCase):
    def test_sides_split_and_deterministic(self):
        items = [item(i) for i in range(40)]
        p1, m1 = build_package(items)
        p2, m2 = build_package(items)
        self.assertEqual([x["eval_id"] for x in p1],
                         [x["eval_id"] for x in p2])
        self.assertEqual(m1, m2)
        sides = [m1[x["eval_id"]]["candidate_side"] for x in p1]
        self.assertTrue(10 < sides.count("A") < 30)  # roughly balanced

    def test_map_separate_from_package(self):
        p, m = build_package([item(1)])
        blob = str(p)
        self.assertNotIn("candidate_side", blob)
        self.assertNotIn("K-1", blob)
        self.assertEqual(m[p[0]["eval_id"]]["candidate_key"], "K-1")

    def test_leak_refused(self):
        p, _ = build_package([item(1)])
        self.assertTrue(assert_blind(p))
        bad = [dict(p[0], lemma="gemini leak")]
        with self.assertRaises(ValueError):
            assert_blind(bad)

    def test_content_words_allowed(self):
        # thinking/temperature/grounding/google/pilot can be legitimate
        # lexical content — only identifier shapes are forbidden.
        p, _ = build_package([item(1)])
        p[0]["armA"]["definition"] = (
            "thinking about temperature and grounding; google a TV pilot")
        self.assertTrue(assert_blind(p))


class TestFreeze(unittest.TestCase):
    def test_input_frozen(self):
        reps = {"K-1": {"status": "ok", "validator": {"failures": []}}}
        rec = freeze_eval_input(reps)
        self.assertEqual(rec["entries"][0]["candidate_key"], "K-1")
        h1 = rec["input_hash"]
        rec2 = freeze_eval_input(reps)
        self.assertEqual(h1, rec2["input_hash"])
        self.assertEqual(blank_ballot()["fields"]["definition"], "unjudged")


if __name__ == "__main__":
    unittest.main()
