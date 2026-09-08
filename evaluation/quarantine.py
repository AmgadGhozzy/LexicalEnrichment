"""Quarantine formalization (build ticket 10).

Implements spec section 3 / wayfinding 04 + 10. Builds quarantine
RECORDS (metadata layer), not a data migration: no database is read
or written, no row is promoted, nothing is deleted.

Scope boundary (locked, tested in the negative):
- 727: class-complete formalization against the forensic
  decomposition (121 + 571 + 32 + 3 = 727) with per-class review
  state, criteria, and provenance. Per-ROW materialization
  (source_row_id enumeration from staging) is BLOCKED on Gate B:
  ingesting rows from an unlocated vintage into any store —
  quarantine included — would launder provenance. Stated, not done.
- 34 IELTS multiwords: full per-row records (all rows available in
  the v2 mapping artifact), topics attached, never split.
"""

QUARANTINE_727_CLASSES = (
    {
        "class": "implausible_function_word_pos",
        "count": 121,
        "criteria": "closed-class lemma with open-class POS "
                    "(e.g. the/and/would/shall->noun, at/on->verb, "
                    "vice/well-being->verb); presumptively malformed, "
                    "rebuttable only by cited evidence (Ticket 03 rule).",
        "review_state": "quarantined_pending_item_review",
    },
    {
        "class": "zero_derivation_mixed",
        "count": 571,
        "criteria": "auto-POS-expansion of mixed legitimacy "
                    "(defensible e.g. torture/noun vs wrong e.g. "
                    "get/noun, see/noun); per-item POS adjudication "
                    "under Ticket 03, never blanket approve/reject.",
        "review_state": "quarantined_pending_item_review",
    },
    {
        "class": "same_lemma_diff_pos",
        "count": 32,
        "criteria": "lemma exists in canonical universe under a "
                    "different POS; POS variants may be legitimate "
                    "separate identities — quarantine is review "
                    "state, not an invalidity verdict.",
        "review_state": "quarantined_pending_item_review",
    },
    {
        "class": "brand_new_lemma",
        "count": 3,
        "criteria": "holding/noun, complicate/adj, dressing/noun; "
                    "genuinely new lemmas, admissible only via "
                    "Tickets 02/03 gates, never auto-created.",
        "review_state": "quarantined_pending_item_review",
    },
)

EXPECTED_727_TOTAL = 727
EXPECTED_MULTIWORD_TOTAL = 34


def build_727_quarantine(forensic_ref):
    """Class-level quarantine records for the 727.

    forensic_ref: provenance dict (artifact path/hash). Returns
    (records, total). Raises on any count inconsistency.
    """
    records = []
    for cls in QUARANTINE_727_CLASSES:
        records.append(
            {
                "kind": "vintage_727",
                "class": cls["class"],
                "count": cls["count"],
                "criteria": cls["criteria"],
                "review_state": cls["review_state"],
                "forensic_ref": forensic_ref,
                "row_level_materialization": "BLOCKED_on_Gate_B",
            }
        )
    total = sum(r["count"] for r in records)
    if total != EXPECTED_727_TOTAL:
        raise ValueError("quarantine classes sum to %d, not 727" % total)
    return records, total


def build_multiword_quarantine(v2_records):
    """Per-row quarantine records for IELTS multiwords.

    v2_records: rows from the BT-09 v2 mapping artifact. Returns only
    MULTIWORD rows, each with topics attached. Raises if the count
    is not exactly 34 (completeness asserted, not assumed).
    """
    rows = [
        {
            "kind": "multiword",
            "original_form": r["source_lemma"],
            "normalized_form": r["normalized_form"],
            "source_name": "IeltsWord.db",
            "source_row_id": r["ielts_row_id"],
            "classification": "MULTIWORD_QUARANTINE",
            "topic": r.get("topic"),
            "review_state": "quarantined_awaiting_multiword_architecture",
        }
        for r in v2_records
        if r["classification"] == "MULTIWORD"
    ]
    if len(rows) != EXPECTED_MULTIWORD_TOTAL:
        raise ValueError("expected 34 multiwords, got %d" % len(rows))
    for r in rows:
        if " " not in (r["normalized_form"] or ""):
            raise ValueError("non-multiword leaked into quarantine: %r" % r)
    return rows


def assert_no_promotion(records):
    """Quarantine records must never carry lexical-identity ids.

    Raises if any record looks like a minted identity (has an
    identity id field or an approved/canonical status).
    """
    for r in records:
        for forbidden in ("lexical_identity_id", "identity_id", "canonical"):
            if forbidden in r:
                raise ValueError("promotion leak in quarantine: %r" % r)
        if str(r.get("review_state", "")).startswith("approved"):
            raise ValueError("approved state inside quarantine: %r" % r)
    return True
