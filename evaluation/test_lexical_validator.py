"""Direct unit tests for the canonical LexicalValidator.

Complements evaluation/test_validator_characterization.py, which pins the
legacy byte-for-byte behavior through the compatibility wrapper. This suite
targets LexicalValidator directly so the deep validator is testable without
going through artifact-construction boilerplate.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline"))

import jsonschema

from evaluation.lexical_validator import (
    LexicalValidator,
    normalize_token,
    tokenize,
    contains_target,
    is_circular_definition,
    VALID_REGISTERS,
    VALID_PRIMARY_SENSES,
    VALID_CATEGORIES,
    MIN_SEMANTIC_TAGS,
    MAX_SEMANTIC_TAGS,
    SEMANTIC_TAG_PREFIX,
)


def make_artifact(output, exp_id="EXP-X"):
    from evaluation import utils
    payload = utils.canonical_hash(output) if output is not None else utils.canonical_hash(None)
    return {
        "candidate_id": "cand-1",
        "experiment_id": exp_id,
        "lexical_entry": {"lexical_id": "L1", "lemma": "bank", "pos": "noun", "cefr": "B1"},
        "runtime": {"status": "success", "iteration": 1, "engine": "test"},
        "provenance": {
            "output_hash": payload,
            "golden_set_hash": "g",
            "schema_version": "test",
        },
        "output": output,
    }


def valid_output():
    return {
        "definition_en": "a financial institution",
        "translation_ar": "بنك",
        "explanation_ar": "مؤسسة مالية",
        "examples": [
            {"example_text": "I went to the bank", "intended_cefr": "A2"},
            {"example_text": "the bank on the corner", "intended_cefr": "B1"},
            {"example_text": "a bank account", "intended_cefr": "A2"},
        ],
        "mnemonic_ar": None,
    }


MINIMAL_SCHEMA = {
    "type": "object",
    "properties": {
        "definition_en": {"type": "string"},
        "explanation_ar": {"type": "string"},
        "examples": {
            "type": "array",
            "minItems": 3,
            "items": {"type": "object", "properties": {"example_text": {"type": "string"}}},
        },
    },
    "required": ["definition_en", "explanation_ar", "examples"],
}


class TestLexicalValidator(unittest.TestCase):
    def setUp(self):
        self.v = LexicalValidator()
        self.schema = MINIMAL_SCHEMA

    # -- contracts ----------------------------------------------------------

    def test_enums_are_nonempty_closed_sets(self):
        for enum in (VALID_REGISTERS, VALID_PRIMARY_SENSES, VALID_CATEGORIES):
            self.assertIsInstance(enum, set)
            self.assertTrue(enum)

    def test_semantic_tag_bounds_are_sane(self):
        self.assertLessEqual(MIN_SEMANTIC_TAGS, MAX_SEMANTIC_TAGS)
        self.assertTrue(SEMANTIC_TAG_PREFIX)

    # -- rule-group methods -------------------------------------------------

    def test_validate_schema_pass_and_fail(self):
        checks, failures = {}, []
        cont = self.v.validate_schema(valid_output(), self.schema, checks, failures)
        self.assertFalse(cont)
        self.assertEqual(checks["schema"], "pass")

        bad = dict(valid_output())
        bad["examples"] = bad["examples"][:2]
        checks, failures = {}, []
        cont = self.v.validate_schema(bad, self.schema, checks, failures)
        self.assertTrue(cont)
        self.assertEqual(checks["schema"], "fail")
        self.assertEqual(failures[0]["code"], "SCHEMA_VIOLATION")

    def test_validate_structure_missing_key(self):
        art = make_artifact(valid_output())
        del art["provenance"]
        checks, failures = {}, []
        cont = self.v.validate_structure(art, "EXP-X", checks, failures)
        self.assertTrue(cont)
        self.assertEqual(checks["artifact_structure"], "fail")
        self.assertEqual(failures[0]["code"], "INVALID_STRUCTURE")

    def test_validate_structure_experiment_mismatch(self):
        art = make_artifact(valid_output())
        checks, failures = {}, []
        cont = self.v.validate_structure(art, "OTHER", checks, failures)
        self.assertTrue(cont)
        self.assertIn("experiment_id mismatch", failures[0]["message"])

    def test_validate_semantics_empty_definition(self):
        out = dict(valid_output())
        out["definition_en"] = "   "
        checks, failures = {}, []
        self.v.validate_semantics(out, checks, failures)
        self.assertEqual(checks["required_fields"], "fail")
        self.assertEqual(failures[0]["code"], "INVALID_DEFINITION")

    def test_validate_examples_missing_lemma(self):
        examples = [{"example_text": "I went home"}, {"example_text": "x"}, {"example_text": "y"}]
        checks, failures = {}, []
        self.v.validate_examples(examples, "bank", checks, failures)
        self.assertEqual(checks["target_word"], "fail")
        self.assertEqual(failures[0]["code"], "TARGET_WORD_MISSING")
        self.assertEqual(failures[0]["message"], "Lemma 'bank' not found in examples [0, 1, 2]")

    def test_validate_mnemonic_generic_null(self):
        out = dict(valid_output())
        out["mnemonic_ar"] = "n/a"
        checks, failures = {}, []
        self.v.validate_mnemonic(out, checks, failures)
        self.assertEqual(checks["mnemonic"], "fail")
        self.assertEqual(failures[0]["code"], "MNEMONIC_GENERIC_NULL")

    def test_validate_relations_verb_flag(self):
        out = dict(valid_output())
        out["definition_en"] = "banking the river"
        checks, flags = {}, []
        self.v.validate_relations(out, "verb", checks, flags)
        self.assertEqual(checks["pos_alignment"], "flag")
        self.assertEqual(flags[0]["code"], "POS_HEURISTIC_SUSPICION")

    # -- orchestrator -------------------------------------------------------

    def test_validate_artifact_null_output(self):
        art = make_artifact(None)
        checks, failures, flags = self.v.validate_artifact(art, "EXP-X", self.schema)
        self.assertEqual(failures[0]["code"], "MISSING_OUTPUT")

    def test_validate_artifact_success(self):
        art = make_artifact(valid_output())
        checks, failures, flags = self.v.validate_artifact(art, "EXP-X", self.schema)
        self.assertEqual(failures, [])
        self.assertEqual(flags, [])
        self.assertEqual(checks["schema"], "pass")
        self.assertEqual(checks["output_hash"], "pass")

    def test_validate_artifact_hash_mismatch(self):
        art = make_artifact(valid_output())
        art["provenance"]["output_hash"] = "deadbeef"
        checks, failures, flags = self.v.validate_artifact(art, "EXP-X", self.schema)
        self.assertEqual(failures[0]["code"], "HASH_MISMATCH")
        # content checks still run after hash failure
        self.assertIn("required_fields", checks)

    def test_validate_artifact_runtime_failed_stops(self):
        art = make_artifact(valid_output())
        art["runtime"]["status"] = "failure"
        checks, failures, flags = self.v.validate_artifact(art, "EXP-X", self.schema)
        self.assertEqual(failures[0]["code"], "RUNTIME_FAILED")
        self.assertNotIn("schema", checks)


class TestValidatorTokenHelpers(unittest.TestCase):
    def test_normalize_token_keeps_apostrophes(self):
        self.assertEqual(normalize_token("Don't"), "don't")

    def test_tokenize_splits_words(self):
        self.assertIn("bank", tokenize("Go to the bank today"))

    def test_contains_target_is_exact_no_stemming(self):
        self.assertFalse(contains_target("I banked the money", "bank"))
        self.assertTrue(contains_target("the bank opens", "bank"))

    def test_is_circular_definition_detects_trivial(self):
        self.assertTrue(is_circular_definition("the act of banking", "bank"))
        self.assertFalse(is_circular_definition("a financial institution", "bank"))


if __name__ == "__main__":
    unittest.main()
