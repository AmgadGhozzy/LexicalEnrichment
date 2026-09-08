"""Tests for the AI Blind Adjudicator (BT-14 AI Judge).

Blocking gates: source isolation, prompt allowlist, byte-for-byte
blind-view equality. Plus: ballot parsing, retry/terminal
behavior, resume, rubric pin. No network, no map.
"""

import json
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import evaluation.ai_judge as aj
from evaluation.ai_judge import (
    ALLOWED_INPUT_FIELDS,
    FROZEN_RUBRIC,
    JudgeError,
    build_judge_prompt,
    judge_item,
    parse_ballot,
    rubric_hash,
    run_batch,
)


def item():
    return {
        "eval_id": "E-1", "lemma": "w", "pos": "noun",
        "armA": {"definition": "d", "arabic": "a", "examples": ["x"],
                 "translations": "t", "relations": {}, "mnemonic": None},
        "armB": {"definition": "d2", "arabic": "a2", "examples": ["y"],
                 "translations": "t2", "relations": {}, "mnemonic": "m"},
        "ballot": {},
        "extra_trap": "must never enter the prompt",
    }


def good_ballot_text():
    return json.dumps({
        "fields": {"definition": "A-better",
                   "arabic_explanation": "tie",
                   "sense_separation": "cannot-judge",
                   "examples": "B-better",
                   "translations": "tie",
                   "relations": "tie",
                   "mnemonic": "A-better"},
        "critical_errors": {
            "wrong_meaning": {"side": None, "evidence": ""},
            "misleading_arabic": {"side": None, "evidence": ""},
            "invalid_relation_synonym": {"side": None, "evidence": ""},
            "example_semantic_error": {"side": None, "evidence": ""},
            "target_word_violation": {"side": None, "evidence": ""},
            "fabricated_etymology_mnemonic": {"side": None, "evidence": ""},
            "cefr_learner_mismatch": {"side": None, "evidence": ""}},
        "note": ""})


class TestIsolation(unittest.TestCase):
    def test_no_map_access(self):
        src = open(aj.__file__, encoding="utf-8").read()
        for token in ("identity_map", "id_map", "candidate_side",
                      "candidate_key", "decode", "side-mapping",
                      "side_mapping"):
            self.assertNotIn(token, src, token)

    def test_prompt_allowlist(self):
        prompt = build_judge_prompt(item())
        self.assertNotIn("extra_trap", prompt)
        self.assertNotIn("must never enter", prompt)

    def test_blind_view_byte_for_byte(self):
        view = json.dumps(
            {k: item()[k] for k in ALLOWED_INPUT_FIELDS},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        prompt = build_judge_prompt(item())
        tail = prompt.split("JUDGE THIS ITEM (respond with JSON ballot only):\n")[1]
        self.assertEqual(tail, view)

    def test_rubric_pinned(self):
        self.assertEqual(aj.RUBRIC_VERSION, "ai-rubric-v3")
        self.assertEqual(rubric_hash(),
                         __import__("hashlib").sha256(
                             FROZEN_RUBRIC.encode("utf-8")).hexdigest())
        self.assertIn("cannot-judge", FROZEN_RUBRIC)
        self.assertIn("A-better", FROZEN_RUBRIC)
        self.assertIn("auto-decides", FROZEN_RUBRIC.lower())


class TestBallot(unittest.TestCase):
    def test_accept_good(self):
        b = parse_ballot(good_ballot_text())
        self.assertEqual(b["fields"]["definition"], "A-better")

    def test_reject_malformed(self):
        with self.assertRaises(JudgeError):
            parse_ballot("not json{")

    def test_fence_and_wrapper_tolerated(self):
        wrapped = "```json\n" + json.dumps({"ballot": json.loads(
            good_ballot_text())}) + "\n```"
        b = parse_ballot(wrapped)
        self.assertEqual(b["fields"]["definition"], "A-better")

    def test_wrapper_still_validated(self):
        bad = {"ballot": {"fields": {"definition": "A wins"}}}
        with self.assertRaises(JudgeError):
            parse_ballot(json.dumps(bad))

    def test_reject_unknown_enum(self):
        bad = json.loads(good_ballot_text())
        bad["fields"]["definition"] = "A wins"
        with self.assertRaises(JudgeError):
            parse_ballot(json.dumps(bad))

    def test_reject_missing_critical(self):
        bad = json.loads(good_ballot_text())
        del bad["critical_errors"]["wrong_meaning"]
        with self.assertRaises(JudgeError):
            parse_ballot(json.dumps(bad))

    def test_reject_unjudged_leak(self):
        bad = json.loads(good_ballot_text())
        bad["fields"]["examples"] = "unjudged"
        with self.assertRaises(JudgeError):
            parse_ballot(json.dumps(bad))

    def test_sense_sufficiency_guard_pinned(self):
        # Regression guard for run-to-run cannot-judge/tie drift on
        # flat arms: tie requires discernible comparison, never
        # absence of evidence.
        lowered = FROZEN_RUBRIC.lower()
        self.assertIn("sufficiency guard", lowered)
        self.assertIn("absence of evidence", lowered)

    def test_polysemy_pos_guards_pinned(self):        # Regression guard for the dry-run overreach (attention):
        # legitimate alternate sense must never read as critical.
        lowered = FROZEN_RUBRIC.lower()
        self.assertIn("another legitimate sense", lowered)
        self.assertIn("contradicts that displayed meaning", lowered)
        self.assertIn("pos-vs-sense distinction", lowered)
        self.assertIn("never inferred from", lowered)
        self.assertIn("morphology alone", lowered)

    def test_independence_preserved(self):        # a critical error must NOT force field verdicts: parse
        # accepts B-better fields alongside an A-side critical.
        mod = json.loads(good_ballot_text())
        mod["critical_errors"]["wrong_meaning"] = {
            "side": "A", "evidence": "A defines X as Y, shown Z"}
        b = parse_ballot(json.dumps(mod))
        self.assertEqual(b["fields"]["definition"], "A-better")


class TestRunner(unittest.TestCase):
    def test_retry_then_terminal(self):
        calls = []
        def gen(prompt):
            calls.append(prompt)
            return "garbage{"
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "j.json")
            prog = os.path.join(tmp, "p.json")
            judgments, terminal = run_batch(
                [item()], gen, out, prog, max_retries=2)
            self.assertEqual(judgments, {})
            self.assertEqual(terminal, ["E-1"])
            self.assertEqual(len(calls), 3)  # 1 + 2 retries

    def test_creates_missing_dirs(self):
        def gen(prompt):
            return good_ballot_text()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "newdir", "sub", "j.json")
            prog = os.path.join(tmp, "newdir", "sub", "p.json")
            judgments, terminal = run_batch(
                [item()], gen, out, prog)
            self.assertEqual(sorted(judgments), ["E-1"])
            self.assertEqual(terminal, [])

    def test_resume_skips_done(self):
        calls = []
        def gen(prompt):
            calls.append(prompt)
            return good_ballot_text()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "j.json")
            prog = os.path.join(tmp, "p.json")
            run_batch([item()], gen, out, prog)
            self.assertEqual(len(calls), 1)
            run_batch([item()], gen, out, prog)
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
