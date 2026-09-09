# Ticket 18 — Full Dataset Field Triage

**Status:** EXECUTED — READ-ONLY FULL TRIAGE COMPLETE (PASS) — NO CANONICAL WRITES — NO AUTO-TRANSITION
**Opened:** 2026-09-08 (separate governance decision; fully independent of Ticket 17)
**Baseline:** Baseline-PostMigration-001
**Scope:** جميع الـ7,300 identities × الحقول الثمانية المحددة في Ticket 17.

## Requested authorization
تشغيل evaluation/field_triage.py على كامل الـpopulation باستخدام القواعد المجمدة
المعتمدة في Ticket 17، بما فيها C1 morphology closure، دون أي تعديل سلوكي أو
prompt/model change.

## Allowed
- قراءة WordsMaster.db فقط.
- إنتاج field-level triage manifest.
- تصنيف كل (id, field) إلى: KEEP / DETERMINISTIC_REPAIR / LLM_REVIEW /
  MANUAL_REVIEW / BLOCK.
- تسجيل defect_code وmachine-checkable evidence.
- حساب prevalence/quotas لكل field.
- التحقق من hash والـbaseline وعدم حدوث أي write.

## Explicitly forbidden
- generation
- LLM review/judgment
- promotion
- canonical DB writes
- prompt/model/config changes
- إعادة تشغيل 348/356
- تعديل قواعد C1
- إصلاح KNOWN_MICRO_BUG
- أي تغيير في WordsMaster.db

## Acceptance gates
1. DB hash قبل/بعد مطابق.
2. SQLite integrity check PASS.
3. عدد population = 7,300.
4. كل (id, field) ضمن الـ8 fields مُمثل exactly once.
5. لا records خارج scope.
6. جميع non-KEEP classifications تحتوي defect/evidence صالحًا.
7. quotas تعمل كـcircuit breakers فقط؛ أي تجاوز = HALT وليس تليين القاعدة.
8. أي BLOCK أو anomaly غير متوقع يمنع الانتقال للمرحلة التالية.
9. output manifest له SHA-256 مثبت.
10. لا توجد canonical writes.

## Decision requested
AUTHORIZE READ-ONLY FULL TRIAGE فقط.

## Important boundary
نجاح Ticket 18 لا يعني تفويض أي إصلاح أو توليد أو ترقية. مخرجاته ستكون evidence
لاتخاذ Governance Decision لاحق مستقل بشأن كل field.

## Expected next decision after Ticket 18
نستخدم نتائج الـ7,300 لتحديد أين نحتاج DETERMINISTIC_REPAIR وأين نحتاج LLM_REVIEW
وأين يكفي KEEP، ثم نقرر إن كانت هناك حاجة فعلية لجولة generation واسعة. يعني لا
نعيد عصر الـ7,300 كلمة في مطحنة LLM لمجرد أن لدينا مطحنة.

## Governance ruling (human-owner, 2026-09-08): AUTHORIZED FOR READ-ONLY EXECUTION ONLY
- DECISION: APPROVED — READ-ONLY FULL TRIAGE. Authorization strictly limited to
  running `field_triage.py` on the full 7,300 population per the Ticket 17 frozen
  rules (incl. C1). No canonical writes. No generation. No prompt changes.
  No reopening Ticket 17.
- Gate 4 interpretation (LOCKED): the uniqueness requirement applies to the 8
  triage fields — each (id, field) exactly once. `sense_separation` is an
  accompanying record, once per identity per the frozen design, NOT a 9th field
  inside the 8-field cardinality.
- Gate 6 interpretation (LOCKED): defect_code/evidence requirements apply to
  classifications indicating defect/review. `sense_separation` = MANUAL_REVIEW
  with defect_code null is a pre-approved default workflow state, not a defect
  classification — NOT a gate violation.
- No schema/output-shape change required. No `field_triage.py` modification
  permitted under this authorization. Quotation KNOWN_MICRO_BUG stays as-is.
- Operator execution note (transparency, not a rule change): the engine FILE stays
  byte-identical; the run reuses its frozen functions/constants verbatim. The
  existing CLI only builds samples, so the full-population driver iterates all
  ids read-only and applies the Ticket 17 §8 presets to the 12 exception cards
  (3× MANUAL/CEFR-track, 1× BLOCK/G2-gap, 8× KEEP/legacy-only — each preset
  carrying gate-6-compliant defect/evidence or KEEP-null as applicable); quotas
  are computed over the rule-triaged set per R2 (presets are quota-exempt
  pre-decisions, like the sense default). Any deviation ⇒ abort, no manifest.
- Completion evidence requested (10 items): final manifest + SHA-256; DB pre/post
  hash; population/cardinality report; per-field 5-status distribution;
  quota/circuit-breaker report; BLOCK + anomaly inventory; DETERMINISTIC_REPAIR
  list with evidence; LLM_REVIEW / MANUAL_REVIEW counts; integrity/read-only
  proof; verdict PASS or HALT. No automatic transition afterwards.

## Execution record (operator, 2026-09-08) — verdict PASS, STOPPED (no transition)
Engine file byte-identical (no modification); frozen functions reused verbatim;
full-population driver read-only + §8 presets; quotas over the 7,288 rule-triaged
set per R2. Evidence: `output/triage/triage_manifest_7300_v1.json`,
`output/triage/triage_full_run_report.json`.
1. Manifest + SHA-256: `triage_manifest_7300_v1` (65,700 records = 7,300×9),
   sha `8614274b…05d090` (23.4 MB).
2. DB pre/post hash: pre `9c50a5b9…43caa` == baseline == post (identical).
3. Population/cardinality: 7,300 rows, ids exactly 1–7300; 9 records/id;
   each of the 8 content fields exactly once per id; sense exactly once per id.
4. Per-field distribution (content fields; sense = 7300 MANUAL by frozen default):
   examples KEEP 6699 / LLM 597 / MANUAL 3 / BLOCK 1; relations_synonyms KEEP
   7290 / LLM 6 / MANUAL 3 / BLOCK 1; relations_antonyms same 7290/6/3/1;
   definition_en, explanation_ar, translations, mnemonic, collocations each
   KEEP 7296 / MANUAL 3 / BLOCK 1, LLM 0.
5. Quotas (rule set, n=7288): examples 8.19% (597) vs 35%; relations ±0.08% (6)
   vs 30%; all others 0.00%. No breach — breaker never fired at scale.
6. BLOCK inventory: 8 records, ALL `billion/num` (G2_PROVENANCE_GAP) — expected,
   no unexpected BLOCKs. Anomalies: 0.
7. DETERMINISTIC_REPAIR: 0 in the wild (no empty/generic mnemonic cells in 7,300).
8. LLM_REVIEW 609 (597 examples + 6 + 6 relations); MANUAL_REVIEW 7324
   (7300 sense-default + 24 exception presets).
9. Integrity `ok`; DB file sha `31a3434f…59ae92` unchanged vs baseline
   (read-only proven: pre==post==baseline on bytes and logical hash).
10. Verdict: PASS. NO canonical writes. NO transition taken — next governance
   decision (per-field repair/review/generation scoping) is for the human-owner.

## Comments

- 2026-09-08: The operator note below is SUPERSEDED by the locked gate
  interpretations in the ruling above (kept for audit trail; no engine change
  was made pursuant to it).

- 2026-09-08 (operator note — NOT part of the approved text; needs owner
  confirmation before/at ruling): two acceptance readings to lock —
  (a) Gate 4 "8 fields exactly once": the frozen engine emits 9 records/card
  (the 8 content fields + sense_separation default-MANUAL per Amendment 2).
  Proposed reading: gate 4 constrains the 8 content fields (each exactly once
  per id); sense records ride along exactly once under the frozen default.
  (b) Gate 6 "non-KEEP carries valid defect/evidence": sense MANUAL records
  carry defect_code null BY FROZEN DESIGN (evidence.reason=auto_manual_per_G3).
  Proposed reading: gate 6 applies to rule-produced non-KEEP labels; the
  sense default is exempt (null defect + reason evidence = valid by design).
  If the owner intends 8-records-strict instead, the engine needs a
  (decision-authorized) output-shape change before the run — NOT a rule change.

- 2026-09-08: Post-18 governance rulings recorded (per-field 1–10: remediation scope
  = 609 LLM cells only; everything else KEEP/manual/blocked); remediation proposed
  as Ticket 19 (`19_targeted_remediation.md`, PENDING — candidates-only, no
  promotion). This ticket stays EXECUTED-complete; nothing further happens here.

(append operator notes below this line; newest at the end)
