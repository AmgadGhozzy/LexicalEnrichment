"""
Shared lexical contracts and the canonical tri-state artifact validator.

TWO RESPONSIBILITIES, DELIBERATELY SEPARATED
--------------------------------------------

1. SHARED LEXICAL CONTRACTS
   Single owner of the closed enum sets the enrichment domains are validated
   against. The legacy call sites that previously each re-declared these now
   import them from here:

       * phase1_lexical_core.validate_response        (System A pre-write)
       * phase_eval_machine.evaluate_word             (System A scoring)
       * qa.verify_staging_integrity                  (System A DB audit)

   IMPORTANT: sharing the *sets* must NOT be mistaken for sharing the
   *acceptance semantics*. These callers depart in how they treat a missing
   enum value and are NOT to be unified (see each caller's docstring):

       - phase1 / verify_staging_integrity  : missing value is an ERROR.
       - phase_eval_machine.evaluate_word   : missing value is TOLERATED;
                                              only an invalid supplied value
                                              is an ERROR.

   Do not "simplify" these apart. That is a behavioral migration, not a
   refactor.

2. TRI-STATE ARTIFACT VALIDATOR
   LexicalValidator is the canonical deep validator for a single generated
   artifact. It returns per-rule diagnostics in three severities:

       ERROR  -> artifact cannot pass
       FLAG   -> suspicious, human review
       PASS   -> no violations

   `artifact_validator.validate_artifact` is a compatibility wrapper over
   this module so existing callers migrate incrementally without changing
   their imports.

   NON-GOAL: LexicalValidator is NOT a database audit. It knows nothing
   about SQLite staging tables. `qa/verify_staging_integrity` remains a
   separate DB-audit concern that merely CONSUMES the shared contracts.
"""

import re

import jsonschema

# --------------------------------------------------------------------------
# Shared lexical contracts
# --------------------------------------------------------------------------

# Closed enums, single source of truth. Keep these in lockstep with the
# allowed values encoded in config/schemas/lexical_core.json and
# evaluation/prompts/schemas/lexical_output.v1.json (see the characterization
# suite == test_validator_characterization.py::test_enum_sets_match_schema).

VALID_REGISTERS = {"Formal", "Neutral", "Informal", "Slang", "Technical", "Literary"}

VALID_PRIMARY_SENSES = {
    "Action", "Process", "Movement", "State", "Condition", "Change",
    "Relation", "Time", "Event", "Quantity", "Measure", "Quality",
    "Attribute", "Emotion", "Concept", "Communication", "Object",
    "Tool", "Person", "Place",
}

VALID_CATEGORIES = {
    "General / Common", "Social Life & Communication", "Work & Business",
    "Actions & Processes", "Objects & Tools", "Mind & Thinking",
    "Numbers, Time & Math", "Food & Drink", "Travel & Movement",
    "Nature & Science", "Feelings & Emotions", "Health & Senses",
}

# Semantic tags are OPEN hashtags, not a closed enum. The enforceable
# contract is count + format, captured below. There deliberately is NO
# VALID_SEMANTIC_TAGS closed set: any '#word' tag is admissible, so an
# enum here would silently tighten validation across all call sites.
MIN_SEMANTIC_TAGS = 3
MAX_SEMANTIC_TAGS = 5
SEMANTIC_TAG_PREFIX = "#"


# --------------------------------------------------------------------------
# Tri-state artifact validator
# --------------------------------------------------------------------------

GENERIC_NULL_VALUES = {
    "none", "null", "n/a", "لا يوجد", "لا توجد", "لا شيء", "غير متوفر", "لا توجد وسيلة"
}


def normalize_token(text):
    return re.sub(r"[^a-z']", "", text.lower())


def tokenize(text):
    return [normalize_token(t) for t in re.findall(r"[A-Za-z']+", text) if normalize_token(t)]


def contains_target(example_text, lemma):
    lemma_norm = normalize_token(lemma)
    return lemma_norm in tokenize(example_text)


def is_circular_definition(definition, lemma):
    # Very basic normalization to ignore case and basic punctuation
    d = re.sub(r"[^a-z0-9\s]", " ", definition.lower()).strip()
    l = re.sub(r"[^a-z0-9\s]", " ", lemma.lower()).strip()

    if not d:
        return False

    patterns = [
        rf"^the act of {re.escape(l)}(?:ing)?$",
        rf"^to {re.escape(l)}$",
        rf"^{re.escape(l)}$",
        rf"^a {re.escape(l)}$",
        rf"^the {re.escape(l)}$",
    ]

    return any(re.fullmatch(p, d) for p in patterns)


def convert_gemini_schema(schema):
    """Recursively converts Gemini-native schema types to JSON Schema Draft-7."""
    if not isinstance(schema, dict):
        return schema

    converted = {}
    for k, v in schema.items():
        if k == "type" and isinstance(v, str):
            converted[k] = v.lower()
        elif k == "nullable":
            pass
        elif isinstance(v, dict):
            converted[k] = convert_gemini_schema(v)
        elif isinstance(v, list):
            converted[k] = [convert_gemini_schema(item) if isinstance(item, dict) else item for item in v]
        else:
            converted[k] = v

    if schema.get("nullable") is True:
        original_type = converted.get("type")
        if isinstance(original_type, str):
            converted["type"] = [original_type, "null"]
        elif (
            isinstance(original_type, list)
            and "null" not in original_type
            and "NULL" not in original_type
        ):
            # Idempotency: an already-converted schema keeps a single
            # "null" member instead of nesting unions on re-conversion.
            converted["type"] = original_type + ["null"]

    return converted


class LexicalValidator:
    """Canonical deep validator for one generated artifact (ERROR/FLAG/PASS).

    The per-rule methods each append diagnostics to `checks`/`failures`/`flags`
    and return a continuation sentinel. ``validate_artifact`` orchestrates them
    in the canonical order with the canonical early-return semantics inherited
    from the legacy ``artifact_validator.validate_artifact``. Diagnostic codes
    and messages are preserved byte-for-byte; do not re-word them.
    """

    def validate_schema(self, output, schema, checks, failures):
        """JSON Schema frame-check (run after output is known present).

        The frame schema may arrive raw (Gemini-native, with
        "nullable") or pre-converted; conversion is idempotent, so
        both paths validate identically. Transport alignment only:
        no lexical semantics change here.
        """
        try:
            frame = convert_gemini_schema(schema)
            jsonschema.validate(instance=output, schema=frame)
            checks["schema"] = "pass"
        except jsonschema.exceptions.ValidationError as e:
            checks["schema"] = "fail"
            failures.append({"code": "SCHEMA_VIOLATION", "message": e.message})

        if checks["schema"] == "fail":
            return True  # stop: later content checks would crash
        return False  # continue

    def validate_structure(self, artifact, exp_id, checks, failures):
        """Artifact envelope + provenance structure."""
        try:
            for key in ["candidate_id", "experiment_id", "lexical_entry", "runtime", "provenance"]:
                if key not in artifact:
                    raise ValueError(f"Missing root key: {key}")

            if not isinstance(artifact["candidate_id"], str) or not artifact["candidate_id"]:
                raise ValueError("candidate_id must be a non-empty string")

            if artifact["experiment_id"] != exp_id:
                raise ValueError(f"experiment_id mismatch. Expected {exp_id}, got {artifact['experiment_id']}")

            le = artifact["lexical_entry"]
            for key in ["lexical_id", "lemma", "pos", "cefr"]:
                if key not in le:
                    raise ValueError(f"Missing lexical_entry key: {key}")

            if "status" not in artifact["runtime"]:
                raise ValueError("Missing runtime.status")

            prov = artifact["provenance"]
            for key in ["output_hash", "golden_set_hash", "schema_version"]:
                if key not in prov:
                    raise ValueError(f"Missing provenance key: {key}")

            checks["artifact_structure"] = "pass"
        except Exception as e:
            checks["artifact_structure"] = "fail"
            failures.append({"code": "INVALID_STRUCTURE", "message": str(e)})
            return True  # stop early if structure is invalid
        return False  # continue

    def validate_artifact(self, artifact, exp_id, schema):
        checks = {}
        failures = []
        flags = []

        # 1. Artifact Structure & Provenance Integrity
        if self.validate_structure(artifact, exp_id, checks, failures):
            return checks, failures, flags

        # 2. Runtime Status
        if artifact["runtime"]["status"] == "success":
            checks["runtime_status"] = "pass"
        else:
            checks["runtime_status"] = "fail"
            failures.append({"code": "RUNTIME_FAILED", "message": "status is not success"})
            return checks, failures, flags

        output = artifact.get("output")

        # 3. Output presence (before hashing, matching the legacy ordering).
        if output is None:
            checks["schema"] = "fail"
            failures.append({"code": "MISSING_OUTPUT", "message": "output object is missing"})
            return checks, failures, flags

        # 4. Output Hash Integrity
        computed_hash = _canonical_hash(output)
        if computed_hash == artifact["provenance"]["output_hash"]:
            checks["output_hash"] = "pass"
        else:
            checks["output_hash"] = "fail"
            failures.append({
                "code": "HASH_MISMATCH",
                "message": f"Computed hash {computed_hash} does not match provenance {artifact['provenance']['output_hash']}"
            })

        # 5. Schema (with early return on failure)
        if self.validate_schema(output, schema, checks, failures):
            return checks, failures, flags

        # 6. Required Field Types
        self.validate_semantics(output, checks, failures)

        # 7. Example Count
        examples = output.get("examples", [])
        if len(examples) == 3:
            checks["example_count"] = "pass"
        else:
            checks["example_count"] = "fail"
            failures.append({"code": "WRONG_EXAMPLE_COUNT", "message": f"Expected 3 examples, found {len(examples)}"})

        # 8. Target Word in Examples
        lemma = artifact["lexical_entry"]["lemma"]
        self.validate_examples(examples, lemma, checks, failures)

        # 9. Mnemonic Null/Empty
        self.validate_mnemonic(output, checks, failures)

        # 10. Circular Definition
        def_en = output.get("definition_en", "")
        if is_circular_definition(def_en, lemma):
            checks["circular_definition"] = "flag"
            flags.append({"code": "CIRCULAR_DEFINITION", "message": "Definition appears to be trivially circular"})
        else:
            checks["circular_definition"] = "pass"

        # 11. POS Alignment Heuristic
        self.validate_relations(output, artifact["lexical_entry"]["pos"], checks, flags)

        return checks, failures, flags

    def validate_semantics(self, output, checks, failures):
        """Required field presence/emptiness beyond schema."""
        def_en = output.get("definition_en", "")
        exp_ar = output.get("explanation_ar", "")

        if not isinstance(def_en, str) or not def_en.strip():
            checks["required_fields"] = "fail"
            failures.append({"code": "INVALID_DEFINITION", "message": "definition_en is empty"})
        elif not isinstance(exp_ar, str) or not exp_ar.strip():
            checks["required_fields"] = "fail"
            failures.append({"code": "INVALID_EXPLANATION", "message": "explanation_ar is empty"})
        else:
            checks["required_fields"] = "pass"

    def validate_examples(self, examples, lemma, checks, failures):
        """Each example must contain the exact target lemma as a standalone token."""
        missing_in = []
        for i, ex in enumerate(examples):
            if not contains_target(ex.get("example_text", ""), lemma):
                missing_in.append(i)

        if missing_in:
            checks["target_word"] = "fail"
            failures.append({"code": "TARGET_WORD_MISSING", "message": f"Lemma '{lemma}' not found in examples {missing_in}"})
        else:
            checks["target_word"] = "pass"

    def validate_mnemonic(self, output, checks, failures):
        """Mnemonic must be null, non-empty, and not a generic placeholder."""
        mnemonic = output.get("mnemonic_ar")
        if mnemonic is None:
            checks["mnemonic"] = "pass"
        elif isinstance(mnemonic, str):
            normalized_mnem = mnemonic.strip().lower()
            if not normalized_mnem:
                checks["mnemonic"] = "fail"
                failures.append({"code": "MNEMONIC_EMPTY", "message": "mnemonic_ar is an empty string"})
            elif normalized_mnem in GENERIC_NULL_VALUES:
                checks["mnemonic"] = "fail"
                failures.append({"code": "MNEMONIC_GENERIC_NULL", "message": f"mnemonic_ar contains generic null text: {mnemonic}"})
            else:
                checks["mnemonic"] = "pass"
        else:
            checks["mnemonic"] = "fail"
            failures.append({"code": "MNEMONIC_INVALID_TYPE", "message": "mnemonic_ar must be string or null"})

    def validate_relations(self, output, pos, checks, flags):
        """POS-vs-definition heuristic (always a FLAG, never an ERROR)."""
        def_en = output.get("definition_en", "")
        pos_flag = False

        if pos == "verb" and not def_en.strip().lower().startswith("to "):
            pos_flag = True
        elif pos == "noun" and def_en.strip().lower().startswith("to "):
            pos_flag = True
        elif pos == "adjective" and def_en.strip().lower().startswith("to "):
            pos_flag = True

        if pos_flag:
            checks["pos_alignment"] = "flag"
            flags.append({"code": "POS_HEURISTIC_SUSPICION", "message": f"Definition format may not align with POS: {pos}"})
        else:
            checks["pos_alignment"] = "unverified"


def _canonical_hash(obj):
    """Byte-for-byte hash used by the artifact validator (imported from utils)."""
    from .utils import canonical_hash
    return canonical_hash(obj)
