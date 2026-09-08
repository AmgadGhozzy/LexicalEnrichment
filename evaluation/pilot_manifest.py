"""Stratified pilot manifest builder (build ticket 11).

Implements spec section 7 / the 01+08 -> stratification decision ->
frozen manifest -> pilot chain. Pure functions over in-memory rows;
no DB access inside this module (universe loading is the caller's
read-only concern). Deterministic under a pinned seed.

Stratification decision (locked here, reviewable in the manifest):
- universe: verified master rows + approved clean IELTS candidates
  (none approved yet -> master only; stated, not assumed).
- exclusions: Golden 160 ids, prior-experiment master ids.
  Quarantined/unresolved/malformed are staging-side and absent
  from the master universe by construction (stated explicitly).
- strata: (cefr_evidence_label, pos) cells over RAW master values.
  No POS remapping is invented: master POS already equals the
  canonical 11-tag set verbatim (verified at execution).
- CEFR: legacy values used as EVIDENCE-LABEL strata only —
  explicitly non-authoritative. Manifest carries
  cefr_stratum_authority='OPEN' with re-stratification required
  after Gate A licensed EVP. No canonical CEFR assumed.
- allocation: proportional by cell size with a floor of 2 per
  non-empty cell, largest-remainder for leftovers; within-cell
  sampling by seeded shuffle over id-sorted rows. N=1000.
"""

from evaluation.utils import canonical_hash

PILOT_N = 1000
PILOT_SEED = 730011
CELL_FLOOR = 2

CEFR_STRATUM_AUTHORITY = (
    "OPEN — legacy cefrLevel values used as evidence-label strata "
    "only; non-authoritative; re-stratification required after "
    "Gate A licensed EVP (BT-01). No canonical CEFR assumed."
)


def stratum_key(row):
    """Stratum cell for a universe row dict (id/lemma/pos/cefr/freq)."""
    return (row["cefr"], row["pos"])


def allocate(counts, total, floor=CELL_FLOOR):
    """Proportional allocation with per-cell floor + largest remainder.

    counts: {cell: size}. Returns {cell: quota} summing to total.
    Cells that cannot meet the floor keep all their rows (tiny-cell
    rule, stated in output). Deterministic; no randomness here.
    """
    quotas = {}
    tiny = set()
    for cell, size in counts.items():
        if size <= floor:
            quotas[cell] = size
            tiny.add(cell)
    remaining_cells = {c: s for c, s in counts.items() if c not in tiny}
    remaining_total = total - sum(quotas.values())
    if remaining_total < 0:
        raise ValueError("floors exceed pilot N")
    base = {}
    if remaining_cells:
        universe = sum(remaining_cells.values())
        fractions = {}
        for cell, size in remaining_cells.items():
            exact = size * remaining_total / universe
            base[cell] = floor + int(exact - floor) if exact > floor else floor
            fractions[cell] = exact - int(exact)
        leftover = remaining_total - sum(base.values())
        for cell, _ in sorted(fractions.items(),
                              key=lambda kv: (-kv[1], kv[0])):
            if leftover <= 0:
                break
            base[cell] += 1
            leftover -= 1
    quotas.update(base)
    assert sum(quotas.values()) == total
    return quotas


def sample_manifest(universe_rows, golden_ids, prior_exp_ids,
                    ielts_overlap_ids, seed=PILOT_SEED, total=PILOT_N):
    """Build the frozen manifest entry list.

    Returns (entries, report). entries: id-sorted sample rows with
    stratum + evidence labels + overlap flag. report: exclusions,
    strata, quotas, seed, authority flags. Raises if the eligible
    universe cannot fill total.
    """
    excluded_golden = [r for r in universe_rows if r["id"] in golden_ids]
    excluded_prior = [r for r in universe_rows
                      if r["id"] in prior_exp_ids and r["id"] not in golden_ids]
    eligible = [r for r in universe_rows
                if r["id"] not in golden_ids and r["id"] not in prior_exp_ids]
    if len(eligible) < total:
        raise ValueError("eligible universe too small")
    cells = {}
    for r in eligible:
        cells.setdefault(stratum_key(r), []).append(r)
    quotas = allocate({c: len(v) for c, v in cells.items()}, total)
    import random
    rng = random.Random(seed)
    picked = []
    for cell in sorted(cells):
        rows = sorted(cells[cell], key=lambda r: r["id"])
        rng.shuffle(rows)
        picked.extend(rows[:quotas[cell]])
    assert len(picked) == total
    entries = [
        {
            "id": r["id"],
            "lemma": r["lemma"],
            "pos": r["pos"],
            "stratum": list(stratum_key(r)),
            "cefr_evidence_legacy": r["cefr"],
            "frequency_band_legacy": r["freq"],
            "ielts_overlap": r["id"] in ielts_overlap_ids,
        }
        for r in sorted(picked, key=lambda r: r["id"])
    ]
    report = {
        "algorithm": "proportional (cefr_evidence_label, pos) cells, "
                     "floor 2, largest-remainder, seeded shuffle",
        "seed": seed,
        "total": total,
        "universe_rows": len(universe_rows),
        "eligible_rows": len(eligible),
        "excluded_golden": len(excluded_golden),
        "excluded_prior_exp": len(excluded_prior),
        "approved_ielts_candidates_included": 0,
        "quarantine_note": "staging-side classes absent from master "
                           "universe by construction; no master id excluded "
                           "on quarantine grounds",
        "cefr_stratum_authority": CEFR_STRATUM_AUTHORITY,
        "quotas": {str(k): v for k, v in sorted(quotas.items())},
    }
    return entries, report


def freeze_manifest(entries, report, snapshot_hash):
    """Freeze entries+report with a manifest hash. Returns manifest dict."""
    manifest = {
        "manifest_id": "pilot_manifest_v1",
        "source_snapshot_hash": snapshot_hash,
        "report": report,
        "entries": entries,
    }
    manifest["manifest_hash"] = canonical_hash(
        {"entries": entries, "report": report,
         "snapshot": snapshot_hash}
    )
    return manifest
