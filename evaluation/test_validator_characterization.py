"""
Behavior-preservation characterization tests for the four validator rule families.

PURPOSE (per architecture review Candidate 1):
Pin the CURRENT behavior of each validator site against fixed fixtures, BEFORE any
consolidation. After the validator seam is introduced, these tests must still pass --
they prove the consolidation was a refactor, not a hidden rules rewrite.

The four sites and their distinct contracts:
  1. phase1_lexical_core.validate_response(enriched_words, expected_inputs)
       - all-or-nothing: raises ValueError listing every ERROR. No FLAG/INFO.
  2. evaluation.artifact_validator.validate_artifact(artifact, exp_id, schema)
       - tri-state: (checks, failures, flags). ERROR + FLAG severities.
  3. qa.verify_staging_integrity.verify_staging_integrity(run_id)
       - DB audit; binary pass/fail. (Not unit-tested here -- needs a DB.)
  4. pipeline.phase_eval_machine.evaluate_word(eval_id, word_id, raw_payload, legacy_data)
       - scoring + enum check that is lazy: only rejects enums PRESENT and truthy.

Note the semantic divergence this suite must protect:
  phase1 rejects a missing/invalid 'register' as an ERROR.
  eval_machine ACCEPTS a missing 'register' (only rejects if present and invalid).
Consolidation must NOT flatten these into one rule.
"""

import unittest
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
_PIPELINE_DIR = os.path.join(ROOT_DIR, "pipeline")
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from pipeline.phase1_lexical_core import validate_response, VALID_REGISTERS, VALID_PRIMARY_SENSES, VALID_CATEGORIES
from pipeline.phase_eval_machine import evaluate_word
from evaluation import artifact_validator
from evaluation.artifact_validator import (
    convert_gemini_schema, normalize_token, tokenize, contains_target,
    is_circular_definition, validate_artifact,
)


def load_schema():
    with open(os.path.join(ROOT_DIR, "evaluation", "prompts", "schemas", "lexical_output.v1.json"), encoding="utf-8") as f:
        return json.load(f)


def minimal_sense(register="Neutral", primary_sense="Action"):
    return {
        "sense_no": 1,
        "definition_en": "to make something happen",
        "short_def_en": "cause to happen",
        "definition_ar": "\u0627\u0644\u062a\u0633\u0628\u0628 \u0641\u064a \u062d\u062f\u0648\u062b \u0634\u064a\u0621",
        "is_primary": True,
        "register": register,
        "primary_sense": primary_sense,
        "semantic_tags": ["#Cause", "#Action", "#Happen"],
        "usage_note": "",
        "mnemonic_ar": None,
    }


class TestCharacterization_ValidateResponse(unittest.TestCase):
    """Site 1: phase1_lexical_core.validate_response -- all-or-nothing, ERROR only."""

    def test_valid_batch_passes(self):
        word = {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "aiConfidence": 0.9, "category": "General / Common",
            "phonetic_us": "bæŋk", "phonetic_ar": "بَنگ",
            "senses": [minimal_sense()],
        }
        expected = {1: word}
        validate_response([word], expected)  # must not raise

    def test_invalid_register_raises(self):
        word = {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "aiConfidence": 0.9, "category": "General / Common",
            "phonetic_us": "bæŋk", "phonetic_ar": "بَنگ",
            "senses": [minimal_sense(register="BogusRegister")],
        }
        expected = {1: word}
        with self.assertRaisesRegex(ValueError, "register"):
            validate_response([word], expected)

    def test_missing_register_raises(self):
        word = {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "aiConfidence": 0.9, "category": "General / Common",
            "phonetic_us": "bæŋk", "phonetic_ar": "بَنگ",
            "senses": [minimal_sense(register="")],
        }
        expected = {1: word}
        with self.assertRaisesRegex(ValueError, "register"):
            validate_response([word], expected)

    def test_missing_primary_sense_raises(self):
        word = {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "aiConfidence": 0.9, "category": "General / Common",
            "phonetic_us": "bæŋk", "phonetic_ar": "بَنگ",
            "senses": [minimal_sense(primary_sense="NotASense")],
        }
        expected = {1: word}
        with self.assertRaisesRegex(ValueError, "primary_sense"):
            validate_response([word], expected)

    def test_count_mismatch_raises(self):
        word = {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "aiConfidence": 0.9, "category": "General / Common",
            "phonetic_us": "bæŋk", "phonetic_ar": "بَنگ",
            "senses": [minimal_sense()],
        }
        # Send one word, expect two
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            validate_response([word], {1: word, 2: dict(word)})

    def test_enum_sets_match_schema(self):
        """The three Python enum sets must stay in lockstep with the JSON Schema."""
        schema = load_schema()
        sense = schema["properties"]["senses"]["items"]["properties"]
        schema_registers = set(sense["register"]["enum"])
        schema_primary = set(sense["primary_sense"]["enum"])
        schema_categories = set(schema["properties"]["category"]["enum"])
        self.assertEqual(VALID_REGISTERS, schema_registers)
        self.assertEqual(VALID_PRIMARY_SENSES, schema_primary)
        self.assertEqual(VALID_CATEGORIES, schema_categories)


class TestCharacterization_EvalMachine(unittest.TestCase):
    """Site 4: phase_eval_machine.evaluate_word -- lazy enum check, scores."""

    def _payload(self, senses=None):
        senses = senses or [{
            "register": "Neutral", "primary_sense": "Action",
            "definition_en": "to make happen",
        }]
        return json.dumps({
            "lemma": "bank", "pos": "noun", "phonetic_us": "bæŋk",
            "phonetic_ar": "بَنگ", "senses": senses,
        })

    def _legacy(self):
        return {
            "legacy": {
                "wordEn": "bank", "pos": "noun",
                "mnemonicAr": None, "phoneticUk": None,
            }
        }

    def test_missing_register_is_ACCEPTED_by_machine(self):
        """CRITICAL divergence: eval_machine tolerates a missing register, unlike phase1."""
        senses = [{"definition_en": "to make happen"}]  # no register key at all
        res = evaluate_word(1, 1, self._payload(senses), self._legacy())
        self.assertEqual(res["machine_validation_result"], "pass")

    def test_missing_primary_sense_is_ACCEPTED_by_machine(self):
        senses = [{"definition_en": "to make happen", "register": "Neutral"}]
        res = evaluate_word(1, 1, self._payload(senses), self._legacy())
        self.assertEqual(res["machine_validation_result"], "pass")

    def test_invalid_register_is_REJECTED_by_machine(self):
        senses = [{"register": "Bogus", "definition_en": "to make happen"}]
        res = evaluate_word(1, 1, self._payload(senses), self._legacy())
        self.assertEqual(res["machine_validation_result"], "invalid_enum")

    def test_wrong_lemma_rejected(self):
        res = evaluate_word(1, 1, self._payload(), self._legacy())
        # payload has lemma 'bank', legacy wordEn 'bank' -> pass
        self.assertEqual(res["machine_validation_result"], "pass")
        bad = self._payload()
        bad_obj = json.loads(bad)
        bad_obj["lemma"] = "bankk"
        res = evaluate_word(1, 1, json.dumps(bad_obj), self._legacy())
        self.assertEqual(res["machine_validation_result"], "wrong_word")


class TestCharacterization_ArtifactValidator(unittest.TestCase):
    """Site 2: artifact_validator.validate_artifact -- tri-state ERROR/FLAG."""

    @classmethod
    def setUpClass(cls):
        cls.schema = convert_gemini_schema(load_schema())

    def _artifact(self, output):
        return {
            "candidate_id": "EXP-X-CAND-1",
            "experiment_id": "EXP-X",
            "lexical_entry": {"lexical_id": 1, "lemma": "bank", "pos": "noun", "cefr": "B1"},
            "runtime": {"status": "success"},
            "provenance": {
                "output_hash": artifact_validator.canonical_hash(output),
                "golden_set_hash": "h", "schema_version": "lexical_output.v1",
            },
            "output": output,
        }

    def test_valid_artifact_passes(self):
        output = {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "difficulty_score": "5", "category": "General / Common",
            "ai_confidence": 0.9, "phonetic_us": "bæŋk", "phonetic_uk": None,
            "phonetic_ar": "بَنگ", "definition_en": "a place where money is kept",
            "explanation_ar": "مؤسسة مالية",
            "examples": [
                {"example_text": "I put my money in the bank.", "intended_cefr": "A1"},
                {"example_text": "The bank opens at nine.", "intended_cefr": "A2"},
                {"example_text": "He works at a bank.", "intended_cefr": "B1"},
            ],
            "mnemonic_ar": None,
            "senses": [{
                "sense_no": 1, "definition_en": "a financial institution",
                "short_def_en": "financial institution", "definition_ar": "بنك",
                "is_primary": True, "register": "Formal", "primary_sense": "Place",
                "semantic_tags": ["#Finance", "#Institution", "#Money"],
                "usage_note": "", "mnemonic_ar": None,
            }],
            "collocations": ["bank account"], "synonyms": [], "antonyms": [],
            "related_words": {"en": ["money"], "ar": ["مال"]},
            "word_family": {"noun": "bank", "verb": "", "adj": "", "adv": ""},
            "translations": {
                "arabic_ar": "بنك", "french_fr": "banque", "german_de": "Bank",
                "spanish_es": "banco", "chinese_zh": "银行 (yínháng)",
                "russian_ru": "банк", "portuguese_pt": "banco", "japanese_ja": "銀行 (ginkō)",
                "italian_it": "banca", "turkish_tr": "banka",
            },
        }
        artifact = self._artifact(output)
        checks, failures, flags = validate_artifact(artifact, "EXP-X", self.schema)
        self.assertEqual(failures, [], f"expected no failures, got {failures}")

    def test_target_word_flag_when_missing(self):
        output = self._valid_output()
        # Rewrite examples to omit the lemma 'bank'
        output["examples"] = [
            {"example_text": "I went to town today.", "intended_cefr": "A1"},
            {"example_text": "The store is open.", "intended_cefr": "A2"},
            {"example_text": "He likes reading books.", "intended_cefr": "B1"},
        ]
        artifact = self._artifact(output)
        checks, failures, flags = validate_artifact(artifact, "EXP-X", self.schema)
        self.assertTrue(any(f["code"] == "TARGET_WORD_MISSING" for f in failures))

    def test_wrong_example_count_actually_yields_schema_violation(self):
        """Characterization of ACTUAL behavior: the JSON Schema (minItems:3) rejects
        a short examples array and short-circuits BEFORE the explicit
        WRONG_EXAMPLE_COUNT check (step 6) is ever reached. Consolidation must not
        reorder this: under-counting examples surfaces as SCHEMA_VIOLATION today."""
        output = self._valid_output()
        output["examples"] = output["examples"][:2]
        artifact = self._artifact(output)
        checks, failures, flags = validate_artifact(artifact, "EXP-X", self.schema)
        codes = [f["code"] for f in failures]
        self.assertIn("SCHEMA_VIOLATION", codes)
        self.assertNotIn("WRONG_EXAMPLE_COUNT", codes)
        # Schema failure path returns early: no content checks after it.
        self.assertIn("schema", checks)

    def test_hash_mismatch_is_error_but_content_checks_run(self):
        output = self._valid_output()
        artifact = self._artifact(output)
        artifact["provenance"]["output_hash"] = "wrong-hash"
        checks, failures, flags = validate_artifact(artifact, "EXP-X", self.schema)
        self.assertTrue(any(f["code"] == "HASH_MISMATCH" for f in failures))
        # It should still have run the schema check (collecting full diagnostics)
        self.assertIn("schema", checks)

    def test_circular_definition_is_a_flag_not_error(self):
        output = self._valid_output()
        output["definition_en"] = "the act of banking"
        artifact = self._artifact(output)
        checks, failures, flags = validate_artifact(artifact, "EXP-X", self.schema)
        self.assertEqual(failures, [])
        self.assertTrue(any(f["code"] == "CIRCULAR_DEFINITION" for f in flags))

    def _valid_output(self):
        return {
            "id": 1, "lemma": "bank", "pos": "noun", "cefr_level": "B1",
            "difficulty_score": "5", "category": "General / Common",
            "ai_confidence": 0.9, "phonetic_us": "bæŋk", "phonetic_uk": None,
            "phonetic_ar": "بَنگ", "definition_en": "a place where money is kept",
            "explanation_ar": "مؤسسة مالية",
            "examples": [
                {"example_text": "I put my money in the bank.", "intended_cefr": "A1"},
                {"example_text": "The bank opens at nine.", "intended_cefr": "A2"},
                {"example_text": "He works at a bank.", "intended_cefr": "B1"},
            ],
            "mnemonic_ar": None,
            "senses": [{
                "sense_no": 1, "definition_en": "a financial institution",
                "short_def_en": "financial institution", "definition_ar": "بنك",
                "is_primary": True, "register": "Formal", "primary_sense": "Place",
                "semantic_tags": ["#Finance", "#Institution", "#Money"],
                "usage_note": "", "mnemonic_ar": None,
            }],
            "collocations": ["bank account"], "synonyms": [], "antonyms": [],
            "related_words": {"en": ["money"], "ar": ["مال"]},
            "word_family": {"noun": "bank", "verb": "", "adj": "", "adv": ""},
            "translations": {
                "arabic_ar": "بنك", "french_fr": "banque", "german_de": "Bank",
                "spanish_es": "banco", "chinese_zh": "银行 (yínháng)",
                "russian_ru": "банк", "portuguese_pt": "banco", "japanese_ja": "銀行 (ginkō)",
                "italian_it": "banca", "turkish_tr": "banka",
            },
        }


class TestCharacterization_ValidatorHelpers(unittest.TestCase):
    """Pure helpers in artifact_validator that consolidation must preserve."""

    def test_normalize_token(self):
        self.assertEqual(normalize_token("Bank."), "bank")
        # Apostrophe is preserved by the regex (allowed set includes ').
        self.assertEqual(normalize_token("don't"), "don't")

    def test_contains_target(self):
        # Exact-token match: 'bank' in 'I went to the bank.'
        self.assertTrue(contains_target("I went to the bank.", "bank"))
        # No stemming: 'banked' does not equal 'bank'.
        self.assertFalse(contains_target("I banked the money.", "bank"))

    def test_circular_definition_patterns(self):
        self.assertTrue(is_circular_definition("the act of banking", "bank"))
        self.assertTrue(is_circular_definition("bank", "bank"))
        self.assertFalse(is_circular_definition("a financial institution", "bank"))

    def test_convert_gemini_schema_lowers_types(self):
        converted = convert_gemini_schema({"type": "OBJECT", "properties": {"x": {"type": "STRING"}}})
        self.assertEqual(converted["type"], "object")
        self.assertEqual(converted["properties"]["x"]["type"], "string")

    def test_convert_gemini_schema_nullable_becomes_union(self):
        converted = convert_gemini_schema({"type": "STRING", "nullable": True})
        self.assertEqual(converted["type"], ["string", "null"])


if __name__ == "__main__":
    unittest.main()
