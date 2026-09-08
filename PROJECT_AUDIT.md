# PROJECT-WIDE AUDIT — LexicalEnrichment
**Step 8A / Pre-Production Readiness Review**
**Date:** 2026-09-03 | **Author:** Principal Data Engineer + LLM Evaluation Architect

> This is a read-only AUDIT. No files were modified. All conclusions cite actual evidence from the repository.

---

## 0. EXECUTIVE SUMMARY (one page)

1. **أين نحن الآن؟**
   في **مرحلة "Pilot"** وليس Production وليس مجرد Experimentation. عندنا:
   - محرك V2 كامل (System A / `pipeline/`) يمثل مخطط database كبير (16 جدول) ويمكنه توليد `senses[]`، لكنه **نائم جزئيًا**: تم تشغيله على 10 كلمات فقط في smoke test + 200 كلمة في تقييم منفصل، و `data/production` **فارغ**، ومراحل 2–4 (examples/relations/translations/families) **غير مكتوبة**.
   - نظام تقييم Batch (System B) **نشط وواقعي**: أنتج 14 تجربة، واحدة منها (EXP-014) Batch Pilot كامل بـ 160/160 نجاحًا.

2. **هل Prompt v1.1 هو الأفضل حاليًا؟**
   **نعم — كأفضل مرشح مقياس compliance (بنائي/شكل فقط).** بالأدلة: EXP-010 (v1.0) → exact-target compliance 81.13%، EXP-012 (v1.1) → 98.13%. لكن هذا يُثبت فقط `TARGET_WORD` و schema/شكل، **لا يثبت جودة تعريفية/تربوية/ذكاء عربي/جودة mnemonic**.

3. **هل Batch Pilot ناجح؟**
   **ناجح تقنيًا.** EXP-014: 160/160 completed، 0 failed، `key` mapping يعمل 1:1، importer صارم. **لكنه يُنتج مخططًا `enrichment.v1` أخف (4 حقول فقط)** — لا يُنتج مخطط الإنتاج `lexical_core` الكامل.

4. **هل نحن جاهزون لـ 8,000؟**
   **لا.** البنية المعمارية للبيانات غير حاسمة بعد، وجودة content لم تُثبَت بشريًا على نطاق، والنظامان منفصلان، و`total:160` مكتوب hardcoded. التوسع الآن = مضاعفة الضوضاء.

5. **أكبر 5 مخاطر:**
   1. **نظامان معمارّيان منفصلان** (V2 `pipeline` غني لكن نائم، وبين `evaluation` بسيط لكن نشط) — سيُلزمنا بدمج مسارين.
   2. **جودة mnemonic التراجعت بشريًا.** human_ground_truth_30.csv: V2 `MNE=0` لمعظم الكلمات بينما Legacy `MNE=5`. نص نعم البنية سليمة 100% لكن الإنسان حكم بالتراجع.
   3. **البيانات القديمة (WordsMaster.db) قديمة وغير موثقة provenance lab/algorithm** — rank/frequency/CEFR مدفونة، لا نعرف مصدرها. (ملاحظة: الترميز نظيف UTF-8 — راجع DATA_TRUST_MATRIX للمعالجة التفصيلية.)
   4. **`total:160` و `entry_count==160` hardcoded** في batch runner/importer/input_builder.
   5. **Zero human review مكتمل** على مخرجات EXP-014/012 (الـhuman calibration يخص System A القديم وليس batch v1.1).

6. **ما الذي يجب freeez؟** Prompt v1.1.0 (للـbatch)، و`enrichment.v1` schema (بشكل مؤقت في سياقه)، وGolden Set `golden_v2` (160)، و`artifact_validator`، و`db/schema.sql`. **لا تجمّد** مخطط `lexical_core` لأنه قد تغيّر بعد آخر run.

7. **ما الذي يجب عدم إعادة توليده؟** كل ما هو deterministic + source-backed: `id`, `lemma`, `pos`, `cefr`, `rank`, `frequency`, `fromOxford`, `unitId`, base `difficultyScore`. هذه منقولة verbatim كان ينبغي الحفاظ عليها.

8. **ما الذي يحتاج human review؟** mnemonic_ar، explanation_ar/definition_ar، definition_en (خصوصًا بعد معرفة أن `MNE` تراجعت)، والأمثلة الإنجليزية.

9. **ما الذي يجب اختباره؟** 1) هل v1.1 يتفوق في MNE/ARA/تعريف (وليس فقط target)؟ 2) مقارنة مخطط lexical_core vs enrichment أحدهما عليه أن يفوز. 3) الـEnglish model والـtemperature. 4) قياسات تكلفة فعلية لكل كلمة.

10. **الخطوة التالية بالضبط؟** Frozen v1.1 + اختبار جودة (LLM judge + human على عيّنة 30) على **ناتج الـbatch الذاتي** — ثم قرار بنائي واحد (lexical_core مطوّر ليشمل الآرابيك/المعادن التي يخرجها الـbatch، أو رفع enrichment.v1 ليشمل الأعمدة). **لا 8k.**

---

## 1. Verdict (حكم عام)

| حالة | الحكم | الدليل |
| --- | --- | --- |
| RED (غير جاهز) | | |
| YELLOW (جاهز للتجارب فقط) | ✔ | بنية batch سليمة، prompt v1.1 قوي شكليًا، لكن جودة content غير مثبتة ومعمارية data غير محسومة |
| GREEN (جاهز للتوسع) | | |

**Verdict: YELLOW.** جاهز للخطوة التالية من التجارب (جودة على نطاق 30–160) وليس للتوسع 8k.
