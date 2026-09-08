"""Deterministic IELTS cascade execution (build ticket 09).

Implements spec section 2 (IELTS) / wayfinding 05 using the locked
BT-04 normalizer, the BT-03 first-match order, and the BT-07
mapping_provenance shape. Reads the frozen
`evaluation/forensic_audit/ielts_mapping.json` as INPUT (never
modified); writes a NEW versioned artifact elsewhere. No DB access
except `:memory:` integration checks in tests.

First-match order (BT-03): #4 whitespace -> #5 no candidate ->
#2 POS absent/unmappable -> #1 mapped POS held -> #3 mapped POS
not held -> #6 otherwise. Classification never creates an identity
and never overwrites canonical POS.
"""

import json

from evaluation.identity import CANONICAL_POS, normalize_lemma

IELTS_TO_CANONICAL = {
    "noun": "noun",
    "adj": "adj",
    "verb": "verb",
    "adv": "adv",
}

CLASSIFICATIONS = (
    "NORMALIZED_LEMMA_POS_EXACT",
    "NORMALIZED_LEMMA_EXACT",
    "SAME_LEMMA_DIFFERENT_POS",
    "MULTIWORD",
    "NEW_SINGLE_WORD",
    "UNRESOLVED_MALFORMED",
)


def build_master_universe(artifact_entries):
    """(lemma, pos) universe from artifact candidates (read-only input).

    Both sides normalized with the locked BT-04 folding so the
    comparison itself obeys Ticket 02.
    """
    universe = {}
    for entry in artifact_entries:
        for cand in entry.get("candidates", []):
            lemma = normalize_lemma(cand.get("word", ""))
            pos = (cand.get("pos") or "").strip().lower()
            if lemma and pos in CANONICAL_POS:
                universe.setdefault(lemma, set()).add(pos)
    return universe


def classify_row(source_lemma, source_pos, universe):
    """Classify one IELTS row. Returns (classification, matched_pos|None).

    matched_pos is the canonical POS when exactly one held POS
    matches (#1); None otherwise (classification decides nothing).
    """
    normalized = normalize_lemma(source_lemma or "")
    if not normalized:
        return ("UNRESOLVED_MALFORMED", None)
    if any(ch.isspace() for ch in normalized):
        return ("MULTIWORD", None)
    held = universe.get(normalized)
    if not held:
        return ("NEW_SINGLE_WORD", None)
    mapped = IELTS_TO_CANONICAL.get((source_pos or "").strip().lower())
    if mapped is None:
        return ("NORMALIZED_LEMMA_EXACT", None)
    if mapped in held:
        return ("NORMALIZED_LEMMA_POS_EXACT", mapped)
    return ("SAME_LEMMA_DIFFERENT_POS", None)


def run_mapping(artifact_entries):
    """Run the cascade over artifact rows. Returns record list."""
    universe = build_master_universe(artifact_entries)
    records = []
    for entry in artifact_entries:
        classification, matched = classify_row(
            entry.get("source_lemma"), entry.get("pos"), universe
        )
        records.append(
            {
                "ielts_row_id": entry.get("ielts_row_id"),
                "source_lemma": entry.get("source_lemma"),
                "normalized_form": normalize_lemma(
                    entry.get("source_lemma") or ""
                ),
                "source_pos": entry.get("pos"),
                "classification": classification,
                "matched_pos": matched,
                "topic": entry.get("topic"),
            }
        )
    return records


def count_by_class(records):
    counts = {c: 0 for c in CLASSIFICATIONS}
    for record in records:
        counts[record["classification"]] += 1
    return counts
