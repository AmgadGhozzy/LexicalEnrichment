"""Deterministic repairs + learner-text CI guard (build ticket 08).

Implements spec section 4 (legacy enrichment handling) / the settled
deterministic transformations. Pure string functions over fixtures;
no I/O, no DB access, no LLM. Before/after counts via transform
helpers. Repairs applied to real data belong to execution scope;
this ticket locks the transformations and their tests.

Locked rules:
- UK IPA fallback: present UK -> (uk, 'dictionary'); else present
  US -> (us, 'fallback_from_us'); else (None, None). IPA stored
  WITHOUT slashes (callers must not introduce them; the guard flags
  them in learner text only where they indicate leakage — see below).
- Grounding-artifact removal: strip http(s) URLs, 【...】 citation
  segments, and dagger footnote markers; collapse whitespace.
  Must not mangle Arabic, IPA, or CJK learner content (tested).
- CI guard on learner-facing text: reports URLs, 【】 markers,
  daggers, and bare bracket-citation patterns; empty input is not
  itself a defect here (emptiness is the validator's jurisdiction).
"""

import re

UK_DICTIONARY = "dictionary"
UK_FALLBACK = "fallback_from_us"

_URL_RE = re.compile(r"https?://\S+")
_BRACKET_CITATION_RE = re.compile(r"【[^】]*】")
_DAGGER_RE = re.compile(r"[†‡]")
_BARE_CITATION_RE = re.compile(r"\[\d+\]")


def uk_ipa_fallback(phonetic_us, phonetic_uk):
    """Deterministic UK IPA resolution with provenance.

    Returns (value, source): ('dictionary' when UK was given,
    'fallback_from_us' when copied from US, (None, None) when
    neither exists). Empty strings count as missing.
    """
    if phonetic_uk:
        return (phonetic_uk, UK_DICTIONARY)
    if phonetic_us:
        return (phonetic_us, UK_FALLBACK)
    return (None, None)


def strip_grounding_artifacts(text):
    """Remove machine citation leakage deterministically.

    Returns the cleaned string (whitespace-collapsed). Non-string
    input returns it unchanged; empty string stays empty.
    """
    if not isinstance(text, str) or not text:
        return text
    cleaned = _URL_RE.sub("", text)
    cleaned = _BRACKET_CITATION_RE.sub("", cleaned)
    cleaned = _DAGGER_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def ci_guard_learner_text(text):
    """CI/data-quality guard for learner-facing content fields.

    Returns a list of defect codes found: 'url', 'bracket_citation',
    'dagger', 'bare_citation'. Empty list means clean. Never judges
    quality, language, or emptiness — only contamination markers.
    """
    if not isinstance(text, str) or not text:
        return []
    defects = []
    if _URL_RE.search(text):
        defects.append("url")
    if _BRACKET_CITATION_RE.search(text):
        defects.append("bracket_citation")
    if _DAGGER_RE.search(text):
        defects.append("dagger")
    if _BARE_CITATION_RE.search(text):
        defects.append("bare_citation")
    return defects


def apply_ipa_fallback(rows):
    """Apply UK fallback over row dicts with before/after counts.

    Each row needs 'phonetic_us' and 'phonetic_uk' keys (missing
    counts as None). Returns (new_rows, counts) where each new row
    gains 'phonetic_uk_resolved' + 'phonetic_uk_source' keys and
    counts = {'dictionary': n, 'fallback_from_us': n, 'missing': n}.
    Input rows are not mutated.
    """
    new_rows = []
    counts = {"dictionary": 0, "fallback_from_us": 0, "missing": 0}
    for row in rows:
        value, source = uk_ipa_fallback(
            row.get("phonetic_us"), row.get("phonetic_uk")
        )
        new_row = dict(row)
        new_row["phonetic_uk_resolved"] = value
        new_row["phonetic_uk_source"] = source
        new_rows.append(new_row)
        counts[source if source else "missing"] += 1
    return new_rows, counts


def apply_artifact_strip(rows, field):
    """Strip grounding artifacts from `field` over row dicts.

    Returns (new_rows, counts) with counts = {'changed': n,
    'unchanged': n}. Input rows are not mutated.
    """
    new_rows = []
    counts = {"changed": 0, "unchanged": 0}
    for row in rows:
        original = row.get(field)
        cleaned = strip_grounding_artifacts(original)
        new_row = dict(row)
        new_row[field] = cleaned
        new_rows.append(new_row)
        counts["changed" if cleaned != original else "unchanged"] += 1
    return new_rows, counts
