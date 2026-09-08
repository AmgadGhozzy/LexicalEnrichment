Type: grilling
Status: resolved
Blocked by: 05 (satisfied)

## Question

Does `is_ielts` live directly on lexical identity as a derived flag, or is it purely materialized from the IELTS evidence table at read time?

## Evidence

- `ielts_mapping.json` rules: "`is_ielts` derives from approved mapping only; never the reverse."
- Draft semantics to ratify: `0` = no approved IELTS evidence, `1` = approved evidence exists; source of truth is the evidence table (one identity → many topic rows, no duplicate identities per topic).

## Gate

NON-BLOCKING — resolved. Schema DDL placement deferred to `/to-spec`.

## Answer

Lock the semantic invariant:

- The IELTS evidence/mapping layer is the SOLE source of truth for IELTS membership.
- `is_ielts` is a derived projection of approved IELTS evidence and MUST NOT be independently writable.
- No write path may directly set, clear, or otherwise authoritatively modify `is_ielts`.
- Any stored value must be recomputable from the approved IELTS evidence.

Definition:

    is_ielts = 1
    iff at least one approved IELTS evidence/mapping row resolves to the lexical identity.

    is_ielts = 0
    iff no approved IELTS evidence/mapping row resolves to the lexical identity.

Raw/unresolved/quarantined IELTS rows do not make `is_ielts = 1`.

One lexical identity may have multiple approved IELTS evidence rows and/or multiple IELTS topics. These remain evidence associations; topics never mint lexical identities.

Storage is intentionally deferred to /to-spec:
- `is_ielts` may be implemented as a stored/cache column or a read-time projection/view.
- Regardless of physical representation, the semantic invariant remains that the evidence table is authoritative and the flag is derived.

A stale or inconsistent cached value is an implementation defect; it does not become a second source of truth.

Gate: RESOLVED / NON-BLOCKING
