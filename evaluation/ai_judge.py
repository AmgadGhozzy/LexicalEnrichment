"""AI Blind Adjudicator (BT-14 AI Judge).

Judges frozen blind-package items with a model call each, under the
same blind view a human sees. Structural guarantees (tested):

- input allowlist: exactly {eval_id, lemma, pos, armA, armB} plus
  the frozen rubric — nothing else enters the model input.
- no map access anywhere in this module (source-tested).
- serialized model input equals the canonical blind view
  byte-for-byte under the agreed normalization (sort_keys,
  ensure_ascii=False, compact separators).
- temperature=0 is selected to MINIMIZE SAMPLING VARIANCE, not to
  guarantee determinism; reproducibility rests on frozen
  input/prompt/config hashes plus run records.
- field judgments and critical-error annotations are INDEPENDENT:
  a critical error never auto-decides any field; CANNOT_JUDGE is
  not a tie; a tie is not perfection; side null means "no
  critical error identified" per contract.
"""

import hashlib
import json
import os

from evaluation.adjudicate import validate_ballot

RUBRIC_VERSION = "ai-rubric-v3"

FROZEN_RUBRIC = """\
You are a blind adjudicator of English-learner lexical content.
You see two arms, A and B. You know NOTHING about which system
produced either arm. Never infer identity from count, style,
order, or formatting. Judge CONTENT ONLY against this rubric.

For EACH field, first assess Arm A alone, then Arm B alone, then
compare. Emit exactly one of (exact spelling, all lowercase):
A-better, B-better, tie, cannot-judge. Use cannot-judge when the
displayed evidence is insufficient — never guess. A tie means no
discernible winner, not that both are perfect. cannot-judge is
not a tie.

OUTPUT SHAPE (exact — these keys and no others at the top level):
{
  "fields": {
    "definition": "...", "arabic_explanation": "...",
    "sense_separation": "...", "examples": "...",
    "translations": "...", "relations": "...", "mnemonic": "..."
  },
  "critical_errors": {
    "wrong_meaning": {"side": null, "evidence": ""},
    "misleading_arabic": {"side": null, "evidence": ""},
    "invalid_relation_synonym": {"side": null, "evidence": ""},
    "example_semantic_error": {"side": null, "evidence": ""},
    "target_word_violation": {"side": null, "evidence": ""},
    "fabricated_etymology_mnemonic": {"side": null, "evidence": ""},
    "cefr_learner_mismatch": {"side": null, "evidence": ""}
  },
  "note": ""
}
Each field value is exactly one of the four verdict strings. Each
critical side is exactly "A", "B", or null. No overall_winner, no
rationale object, no field_judgments key, no markdown fences.

FIELD CRITERIA (grounded in the locked enrichment contract):
- definition: correctness, completeness, sense coverage, clarity,
  semantic precision. Penalize wrong scope, not brevity alone.
- arabic_explanation: accuracy, natural Arabic, semantic fidelity
  to the sense, learner clarity, no misleading interpretation.
- sense_separation: arms are FLAT (no explicit sense structures).
  Judge only what definition+examples show: conflated senses,
  wrong sense, or missing distinction the learner needs. Use
  cannot-judge when the display cannot support a verdict.
- examples: semantic correctness, naturalness, EXACT target lemma
  as a standalone token (inflections/derivatives do NOT satisfy),
  fit to the stated sense, no fabricated context.
- translations: correctness, coverage, appropriateness.
- relations (synonyms/antonyms/collocations): validity only.
  more relations is not better by itself.
- mnemonic: usefulness, correctness, tie to the target. null is a
  legitimate outcome (no valid hook); never reward a fabricated
  etymology presented as fact.

POLYSEMY / POS / EXACT-TARGET GUARDS (binding — added ai-rubric-v2
after dry-run overreach on a polysemous lemma):
- Do NOT label an example a semantic error merely because the
  target lemma has another legitimate sense. A different
  legitimate sense is an error ONLY when the arm's displayed
  definition/context claims a different sense AND the example
  contradicts that displayed meaning.
- For polysemous words, a natural example using another
  legitimate sense is NOT a critical error unless it conflicts
  with the arm's stated sense or learner-facing presentation.
- POS-vs-sense distinction: an example is not wrong merely for
  exercising a different semantic shade while the target itself
  performs the required POS in the example.
- Exact-target guard is morphological and independent: the exact
  lemma token satisfies it; an inflection or derived form
  violates it. POS/sense validity is NEVER inferred from
  morphology alone.

SENSE_SEPARATION SUFFICIENCY GUARD (binding — added ai-rubric-v3
after run-to-run drift between cannot-judge and tie on flat
arms): for sense_separation, if the displayed definition +
examples do not provide sufficient evidence to establish or
distinguish senses, return cannot-judge. Do NOT use tie merely
because neither arm provides enough evidence to establish a
winner. A tie requires a discernible comparison with no winner,
not an absence of evidence.

STYLE NEUTRALITY (binding): do NOT penalize example count alone,
synonym count alone, definition length alone, tone, or ordering.
Penalize a difference ONLY when it affects correctness, semantic
precision, learner usefulness, clarity, coverage, or validity.

CRITICAL ERRORS (independent annotations — a critical error NEVER
auto-decides any field; a field may still win on its own merits):
wrong_meaning, misleading_arabic, invalid_relation_synonym,
example_semantic_error, target_word_violation,
fabricated_etymology_mnemonic, cefr_learner_mismatch.
For each: side A, B, or null (null = no critical error identified
for that class), plus SHORT evidence quoted from the displayed
text only. Evidence must name content, never systems
(e.g. "B defines X as Y, but the displayed sense is Z").
"""

ALLOWED_INPUT_FIELDS = ("eval_id", "lemma", "pos", "armA", "armB")

MODEL_ID = "gemini-3.8-flash"
TEMPERATURE = 0.0
THINKING_MODE = "low"
MAX_RETRIES = 3


def canonical_blind_view(item):
    """The exact blind view: allowlisted fields only, in fixed order."""
    return {k: item[k] for k in ALLOWED_INPUT_FIELDS}


def serialize_blind_view(item):
    """Agreed normalization: sorted keys, UTF-8, compact separators."""
    return json.dumps(canonical_blind_view(item), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


def build_judge_prompt(item):
    """Full model input: rubric + canonical blind view, nothing else."""
    return (FROZEN_RUBRIC
            + "\n\nJUDGE THIS ITEM (respond with JSON ballot only):\n"
            + serialize_blind_view(item))


def rubric_hash():
    return hashlib.sha256(
        FROZEN_RUBRIC.encode("utf-8")).hexdigest()


class JudgeError(Exception):
    pass


def _strip_fences(text):
    """Remove a single markdown code fence; content must still parse."""
    if not isinstance(text, str):
        return text
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped


def parse_ballot(text):
    """Parse + strictly validate a model ballot. Raises JudgeError.

    Tolerances (shape-only, never content): one markdown fence,
    one {"ballot": {...}} wrapper level. Everything inside still
    faces full contract validation.
    """
    try:
        ballot = json.loads(_strip_fences(text))
    except (ValueError, TypeError) as exc:
        raise JudgeError("malformed JSON: %s" % exc)
    if not isinstance(ballot, dict):
        raise JudgeError("ballot is not an object")
    if "fields" not in ballot and isinstance(
            ballot.get("ballot"), dict):
        ballot = ballot["ballot"]
    fields = ballot.get("fields")
    if not isinstance(fields, dict):
        raise JudgeError("missing fields object")
    defects = validate_ballot(
        {"fields": fields,
         "critical_errors": ballot.get("critical_errors"),
         "note": ballot.get("note", "")})
    if defects:
        raise JudgeError("contract defects: %s" % defects)
    if any(v == "unjudged" for v in fields.values()):
        raise JudgeError("unjudged field leaked into model ballot")
    return {"fields": fields,
            "critical_errors": ballot.get("critical_errors"),
            "note": ballot.get("note", "")}


def judge_item(item, generate_fn):
    """One item -> one validated ballot (single attempt).

    generate_fn(prompt_text) -> raw model text. Raises JudgeError
    on any contract breach (caller owns retries).
    """
    return parse_ballot(generate_fn(build_judge_prompt(item)))


def run_batch(items, generate_fn, out_path, progress_path,
              max_retries=MAX_RETRIES):
    """Judge items with per-item checkpoint + bounded retries.

    Resumable: completed eval_ids in progress_path are skipped.
    Returns (judgments, terminal). terminal lists eval_ids that
    exhausted retries WITHOUT a guessed ballot (never default-filled).
    """
    judgments = {}
    attempts = {}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(progress_path)),
                exist_ok=True)
    if os.path.exists(progress_path):
        with open(progress_path, encoding="utf-8") as f:
            saved = json.load(f)
        judgments = saved.get("judgments", {})
        attempts = saved.get("attempts", {})

    def checkpoint():
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump({"judgments": judgments, "attempts": attempts}, f,
                      ensure_ascii=False, indent=1)

    terminal = []
    for item in items:
        eval_id = item["eval_id"]
        if eval_id in judgments:
            continue
        tries = attempts.get(eval_id, 0)
        while True:
            tries += 1
            attempts[eval_id] = tries
            try:
                judgments[eval_id] = judge_item(item, generate_fn)
                break
            except JudgeError:
                if tries > max_retries:
                    terminal.append(eval_id)
                    break
        checkpoint()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"judgments": judgments}, f, ensure_ascii=False, indent=1)
    return judgments, terminal
