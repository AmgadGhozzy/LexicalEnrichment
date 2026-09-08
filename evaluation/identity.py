"""Canonical lexical identity: normalization folding + identity key.

Implements build ticket 04 (spec section 1; wayfinding decisions 02, 03).
Read-only wrt databases: pure string functions, no I/O, no DB access.

Locked contract (do not extend without a superseding wayfinding decision):
- folding: trim, lowercase, Unicode NFC, collapse inner whitespace runs
  to one space, diacritics preserved exactly (never stripped).
- hyphenated form without whitespace: single-word candidate.
- any internal whitespace: multiword candidate (Ticket 04 quarantine).
- possessive "'s": not an identity, maps to the base lemma.
- internal apostrophes: preserved as written.
- punctuation other than internal apostrophe/hyphen: inadmissible.
- lemma-level identities only; inflected surface forms map to the base
  and are never separate identities (inflection mapping itself lives
  with the caller: this module folds, it does not lemmatize English).
- proper names / brands: excluded at the ADMISSION layer, not by this
  module. Folding is deterministic and must not perform entity
  detection ("not a tiny opinionated linguist").
- identity key: (normalized_lemma, canonical_pos), exactly one POS per
  identity from the locked 11-tag enum. Composite values such as
  "noun+verb" are refused.
- zero-derivation legitimacy is NOT judged here (Ticket 03 adjudication).
"""

import re
import unicodedata

# Locked 11-tag canonical POS enum. Must stay in lockstep with
# evaluation/prompts/schemas/lexical_output.v1.json (and the identical
# enum in lexical_output.v1.1-candidate.json) — enforced by test.
CANONICAL_POS = frozenset(
    {
        "adj",
        "adv",
        "conj",
        "det",
        "excl",
        "modal",
        "noun",
        "num",
        "prep",
        "pron",
        "verb",
    }
)

_APOSTROPHES = {"'", "\u2018", "\u2019", "\u02bc"}
_WS_RUN = re.compile(r"\s+")

# Allowed inside a normalized single-word candidate: Unicode letters and
# marks (diacritics preserved), digits, ASCII hyphen, ASCII apostrophe.
# Everything else (other punctuation/symbols) makes it inadmissible.
_ALLOWED_EXTRA = {"-", "'"}


def _is_allowed_char(ch):
    if ch in _ALLOWED_EXTRA:
        return True
    cat = unicodedata.category(ch)
    return cat.startswith("L") or cat.startswith("M") or cat == "Nd"


def normalize_lemma(raw):
    """Fold a raw lexical form to its normalized lemma.

    trim -> lowercase -> NFC -> collapse inner whitespace -> ASCII-fold
    apostrophes. Possessive "'s"/"'S" suffix maps to the base form.
    Returns the normalized string (may contain a single internal space
    for multiword forms; may be empty for empty input).
    """
    if raw is None:
        return ""
    text = unicodedata.normalize("NFC", str(raw).strip().lower())
    for apos in _APOSTROPHES - {"'"}:
        text = text.replace(apos, "'")
    text = _WS_RUN.sub(" ", text)
    if text.endswith("'s") and len(text) > 2:
        text = text[:-2]
    return text


def is_single_word_candidate(normalized):
    """True iff a normalized form is admissible as a single-word candidate.

    Rules: non-empty, no whitespace, every char allowed
    (letters/marks/digits/hyphen/apostrophe). A trailing possessive was
    already removed by normalize_lemma; a bare "'" remnant fails here.
    """
    if not normalized:
        return False
    if any(ch.isspace() for ch in normalized):
        return False
    return all(_is_allowed_char(ch) for ch in normalized)


def build_key(normalized_lemma, canonical_pos):
    """Build the canonical identity key (normalized_lemma, canonical_pos).

    Raises ValueError on empty lemma, whitespace-bearing lemma, or a
    POS outside the locked 11-tag enum (composites such as "noun+verb"
    are refused here, never stored).
    """
    if not normalized_lemma or any(
        ch.isspace() for ch in normalized_lemma
    ):
        raise ValueError(
            "identity lemma must be a non-empty single-word form: %r"
            % (normalized_lemma,)
        )
    if canonical_pos not in CANONICAL_POS:
        raise ValueError(
            "canonical_pos %r not in locked 11-tag enum" % (canonical_pos,)
        )
    return (normalized_lemma, canonical_pos)
