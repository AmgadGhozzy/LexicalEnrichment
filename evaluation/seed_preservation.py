"""Seed-preservation classifier (EXP-SEEDED-001, BT-15).

Deterministic field-level comparison between the frozen legacy seed
and a seeded-generation candidate. This module is an EVALUATION
artifact — it does NOT replace LexicalValidator and does not alter
its byte-for-byte contract.

Scope boundary (locked):
- "worse" is decided HERE only on validation-level evidence
  (candidate fails a check the legacy passed). Semantic better/worse
  between two valid values is adjudicated by the blind evaluator
  (human + AI judge v3), module never guesses it.
- "valid" below ALWAYS means deterministically valid against the
  candidate contract (non-empty, exact-lemma examples, non-generic
  mnemonic, ...). It NEVER means human-quality gold. Report pools
  are named legacy_valid_pool / legacy_defective_pool for this
  reason — never read "valid" as semantic approval.
- Categories are mutually exclusive per (field, value pair).

Taxonomy (user-locked for BT-15, amended EXP-SEEDED-001A):
  preserved            : legacy == candidate, action preserve/absent
  preserved_implicit   : legacy == candidate, no declared action
  redundant_replace    : legacy == candidate, action replace (declared
                         change that did not change anything)
  fill                 : legacy null/empty, candidate valid non-empty
  remain_null          : legacy null/empty, candidate null/empty/fails
  changed              : legacy valid, candidate valid & different,
                         declared improve/replace + reason +
                         declared replacement_superiority
  unjustified_change   : candidate changed with no declared reason or
                         no declared superiority
  justified_nullification   : legacy valid + candidate null, declared
                         null + legacy_defect=true + concrete evidence
  unjustified_nullification : legacy valid + candidate null without
                         the above (enters the regression pool)
  field_decision_conflict: declaration contradicts observation
                         (state mismatch, null-with-value,
                         preserve-with-change)
  regression           : legacy valid, candidate fails a check the
                         legacy passed (non-null candidate)
  repair               : legacy failed the candidate contract,
                         candidate passes

Metrics (user-locked, amended EXP-SEEDED-001A):
  Preservation Precision (raw) = preserved / legacy-valid pool.
    A changed field NEVER counts as preserved, however good the
    declared reason sounds.
  Repair Recall = repair / legacy-defective pool.
  Justified Change Rate = (changed + justified_nullification)
    / legacy-valid pool.
  Unjustified Change Rate = (unjustified_change
    + field_decision_conflict) / legacy-valid pool.
  Nullification Rate = (justified + unjustified nullification)
    / legacy-valid pool.
  Unjustified Nullification Rate = unjustified_nullification
    / legacy-valid pool.
  Regression Rate = (regression + unjustified_nullification)
    / legacy-valid pool.
"""

from evaluation.lexical_validator import (
    contains_target, is_circular_definition, GENERIC_NULL_VALUES)

FIELDS = ("definition_en", "explanation_ar", "examples",
          "translations", "synonyms", "antonyms", "collocations",
          "mnemonic")


def _norm_str(v):
    if v is None:
        return None
    if isinstance(v, str):
        return " ".join(v.strip().lower().split())
    return None


def _as_flat_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return list(v.values())
    if isinstance(v, str):
        return [v]
    return [v]


def _list_eq(a, b):
    return _as_flat_list(a) == _as_flat_list(b)


def _examples_text(v):
    out = []
    for e in _as_flat_list(v):
        if isinstance(e, dict):
            out.append(e.get("example_text") or e.get("text") or "")
        else:
            out.append(str(e))
    return [s for s in out if s]


def field_is_valid(field, value, lemma):
    """Deterministic validity proxy. Returns (valid, why)."""
    if field == "definition_en":
        s = _norm_str(value)
        if not s:
            return False, "empty"
        if is_circular_definition(s, lemma):
            return False, "circular"
        return True, ""
    if field == "explanation_ar":
        s = _norm_str(value)
        if not s:
            return False, "empty"
        if s in GENERIC_NULL_VALUES:
            return False, "generic_null"
        if s.startswith("[") or s.startswith("("):
            return False, "bracket_placeholder"
        return True, ""
    if field == "examples":
        ex = _examples_text(value)
        if len(ex) != 3:
            return False, "count!=3"
        if not all(s.strip() for s in ex):
            return False, "empty_example"
        if not all(contains_target(s, lemma) for s in ex):
            return False, "target_missing"
        return True, ""
    if field == "translations":
        items = [x for x in _as_flat_list(value) if str(x).strip()]
        if not items:
            return False, "empty"
        if all(_norm_str(x) in GENERIC_NULL_VALUES for x in items):
            return False, "generic_null"
        return True, ""
    if field in ("synonyms", "antonyms", "collocations"):
        items = [x for x in _as_flat_list(value) if str(x).strip()]
        return (bool(items), "" if items else "empty")
    if field == "mnemonic":
        if value is None:
            return False, "null"
        s = _norm_str(value)
        if not s:
            return False, "empty"
        if s in GENERIC_NULL_VALUES:
            return False, "generic_null"
        return True, ""
    return True, ""


def _has_content(field, value):
    """True when the legacy value carries real content for this field.
    Empty strings / empty lists / None are the null pool."""
    if field in ("definition_en", "explanation_ar", "mnemonic"):
        return bool(_norm_str(value))
    if field == "examples":
        return bool(_examples_text(value))
    if field in ("translations", "synonyms", "antonyms", "collocations"):
        return any(str(x).strip() for x in _as_flat_list(value))
    return True


BANNED_NULL_EVIDENCE_PHRASES = (
    "prefer null", "not ideal", "cannot improve", "can't improve",
    "can not improve", "could not improve", "no better",
    "not perfect", "cleaner", "minimalism", "uncertain",
    "rather omit", "prefer to omit", "no strong",
)


def nullification_evidence_sufficient(evidence):
    """Structural check on a declared nullification reason.

    Heuristic only: rejects empty evidence and vague preference
    statements ("not ideal", "cannot improve", "prefer NULL", ...).
    The semantic truth of a claimed defect is adjudicated blind,
    never here.
    """
    if not evidence or not str(evidence).strip():
        return False, "no evidence declared"
    norm = " ".join(str(evidence).strip().lower().split())
    if len(norm) < 10:
        return False, "evidence too short to name a defect"
    for phrase in BANNED_NULL_EVIDENCE_PHRASES:
        if phrase in norm:
            return False, "vague preference, not a concrete defect"
    return True, ""


def classify_field(field, legacy, candidate, action, reason, lemma,
                   legacy_defect=None, evidence=None,
                   replacement_superiority=None,
                   declared_legacy_state=None):
    """One field -> one category. Returns (category, why).

    Declaration keys (all optional; absence weakens the declaration):
      legacy_defect: declared True when the model claims the legacy
        value has a concrete defect (required for nullification).
      evidence: concrete evidence string for the claimed defect or
        superiority (vague preferences are rejected structurally).
      replacement_superiority: declared True when the model claims
        the replacement is better (required for replace/improve).
        A declaration, never a certification — blind evaluation
        decides better vs merely different.
      declared_legacy_state: "null" | "non_null" as declared; must
        match the observed legacy, else field_decision_conflict.
    """
    if field == "examples":
        lg, cd = _examples_text(legacy), _examples_text(candidate)
    elif field in ("translations", "synonyms", "antonyms", "collocations"):
        lg, cd = _as_flat_list(legacy), _as_flat_list(candidate)
    else:
        lg, cd = _norm_str(legacy), _norm_str(candidate)

    lv, lwhy = field_is_valid(field, legacy, lemma)
    cv, cwhy = field_is_valid(field, candidate, lemma)

    legacy_empty = not _has_content(field, legacy)

    def action_kind():
        if action in ("replace", "improve", "improve/replace"):
            return "replace"
        if action == "null":
            return "null"
        if action == "preserve":
            return "preserve"
        return None

    ak = action_kind()

    def declared_state():
        s = (declared_legacy_state or "").strip().lower().replace("-", "_")
        if s in ("null", "non_null"):
            return s
        return None

    ds = declared_state()

    # 0. Declaration contract: state must match observation.
    if ds == "null" and not legacy_empty:
        return ("field_decision_conflict",
                "declared legacy null but legacy has content")
    if ds == "non_null" and legacy_empty:
        return ("field_decision_conflict",
                "declared legacy non-null but legacy is empty")
    # 0b. Declared null must not produce a valid value.
    if ak == "null" and cv:
        return ("field_decision_conflict",
                "declared null but candidate is valid")

    if legacy_empty:
        if not cv:
            return "remain_null", "legacy null/empty, candidate not valid"
        return "fill", "legacy null/empty, candidate valid"

    if lg == cd:
        if ak == "replace":
            return "redundant_replace", "action replace but value unchanged"
        return "preserved", "legacy retained"

    if not lv:
        if cv:
            return ("repair",
                    "legacy failed the candidate contract (%s), "
                    "candidate passes" % lwhy)
        return ("changed_defective",
                "legacy failed the candidate contract (%s), "
                "candidate fails (%s)" % (lwhy, cwhy))

    # Legacy is deterministically valid from here on.
    if not cv:
        if not _has_content(field, candidate):
            if ak == "null" and legacy_defect is True:
                ok, why_ev = nullification_evidence_sufficient(evidence)
                if ok:
                    return ("justified_nullification",
                            "declared null with concrete defect evidence")
                return ("unjustified_nullification",
                        "nullification evidence insufficient: %s" % why_ev)
            return ("unjustified_nullification",
                    "legacy valid nullified without declared defect "
                    "evidence")
        return ("regression",
                "legacy valid, candidate failed the contract: %s" % cwhy)

    if ak == "replace" and reason and replacement_superiority is True:
        return "changed", "declared improve/replace with reason"
    if ak == "replace" and not reason:
        return "unjustified_change", "changed without a concrete reason"
    if ak == "replace":
        return ("unjustified_change",
                "changed without declared superiority")
    if ak == "preserve":
        return "field_decision_conflict", "declared preserve but value changed"
    return "unjustified_change", "changed without a declared reason"


def seed_preservation_report(seed, candidate, lemma,
                             field_decisions=None):
    """Full per-field report + raw PP/RR + change/nullification rates.

    seed: {definition_en, explanation_ar, examples, translations,
    synonyms, antonyms, collocations, mnemonic} (legacy transport).
    candidate: same keys (alias "mnemonic_ar" accepted for the
    blind-arm shape).
    field_decisions: {field: {action, reason, legacy_state,
    legacy_defect, replacement_superiority, evidence}} (optional;
    absence weakens every declaration to unjustified).
    """
    decisions = field_decisions or {}
    per_field = {}
    valid_pool = defective_pool = 0
    preserved = repaired = 0
    changed = justified_null = unjustified_null = 0
    classic_regression = unjustified_change = conflicts = 0
    redundant = 0
    for f in FIELDS:
        if f == "mnemonic":
            cand_value = candidate.get("mnemonic_ar",
                                       candidate.get("mnemonic"))
        else:
            cand_value = candidate.get(f)
        d = decisions.get(f) or {}
        category, why = classify_field(
            f, seed.get(f), cand_value,
            d.get("action"), d.get("reason"), lemma,
            legacy_defect=d.get("legacy_defect"),
            evidence=d.get("evidence"),
            replacement_superiority=d.get("replacement_superiority"),
            declared_legacy_state=d.get("legacy_state"))
        per_field[f] = {"category": category, "why": why}
        lv, _ = field_is_valid(f, seed.get(f), lemma)
        if _has_content(f, seed.get(f)):
            legacy_empty = False
        else:
            legacy_empty = True
        if legacy_empty:
            continue
        if lv:
            valid_pool += 1
            if category in ("preserved", "preserved_implicit"):
                preserved += 1
            elif category == "changed":
                changed += 1
            elif category == "justified_nullification":
                justified_null += 1
            elif category == "unjustified_nullification":
                unjustified_null += 1
            elif category == "regression":
                classic_regression += 1
            elif category == "unjustified_change":
                unjustified_change += 1
            elif category == "field_decision_conflict":
                conflicts += 1
            elif category == "redundant_replace":
                redundant += 1
        else:
            defective_pool += 1
            if category == "repair":
                repaired += 1

    def rate(n, d):
        return (n / d) if d else None

    return {
        "fields": per_field,
        "legacy_valid_pool": valid_pool,
        "legacy_defective_pool": defective_pool,
        "preservation_precision": rate(preserved, valid_pool),
        "repair_recall": rate(repaired, defective_pool),
        "justified_change_rate": rate(changed + justified_null,
                                      valid_pool),
        "unjustified_change_rate": rate(
            unjustified_change + conflicts, valid_pool),
        "nullification_rate": rate(justified_null + unjustified_null,
                                   valid_pool),
        "unjustified_nullification_rate": rate(unjustified_null,
                                               valid_pool),
        "regression_rate": rate(classic_regression + unjustified_null,
                                valid_pool),
        "counts": {
            "preserved": preserved,
            "changed": changed,
            "justified_nullification": justified_null,
            "unjustified_nullification": unjustified_null,
            "regression": classic_regression,
            "unjustified_change": unjustified_change,
            "declaration_conflicts": conflicts,
            "redundant_replace": redundant,
            "repair": repaired,
        },
    }