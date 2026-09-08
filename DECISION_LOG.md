# DECISION LOG — LexicalEnrichment

## Decisions Already Proven (مدعومة بأدلة)

| القرار | المصدر | الحالة |
| --- | --- | --- |
| Prompt v1.1.0 > v1.0.0 في exact-target compliance (98.13% vs 81.13%) | EXP-010 vs EXP-012 (immutable) | **VERIFIED** (بنائي فقط) |
| Batch output يعيد 160/160 (0 failed) | EXP-014 manifest + progress | **VERIFIED** |
| `key` mapping يعمل 1:1 | batch_importer (strict) + EXP-014 raw artifacts كاملة | **VERIFIED** |
| validator بدون تغيير عبر v1.0/v1.1 (fiar comparison) | artifact_validator_1.0.0 في report.json | **VERIFIED** |
| Legacy mnemonic `MNE=5` تفوق V2 `MNE=0` لفئة كبيرة | human_ground_truth_30.csv | **VERIFIED (بشري)** |
| Golden set golden_v2 سليم (160، hash ثابت، strata) | manifest.json + strata_report | **VERIFIED** |
| WordsMaster.db (7,300) مستورد immutable؛ rank/freq/CEFR مبني في المصدر وليس محسوبة هنا | db_audit + phase0 import verbatim | **VERIFIED** |
| System A أنتج 8027 كلمة import لكن 27 sense فقط (smoke 10 كلمات) | staging DB counts | **VERIFIED** |

## Decisions Pending (تحتاج حسم)

| القرار | لماذا معلّق |
| --- | --- |
| الاختيار البنوي: lexical_core (غني) vs enrichment (خفيف) كمخطط واحد | لا أحد مثبت؛ كل يعمل في مساره المنفصل |
| Build enrichment.v1 مع senses أم توسيع lexical_core بالأعمدة؟ | لم تُنفَّذ تعديلات |
| الموديل النهائي (gemini-2.5-flash vs الأحدث) + temperature | لا تجربة مقارنة على نتائج كاملة |
| تشغيل human review نافذ على مخرجات EXP-014 | لا review مكتمل على batch v1.1 |
| مصدر CEFR/rank/frequency موثوق (wordfreq/lexicon) | لم يُختَر |
| دمج IELTS كـauxiliary (topics/audio/لغات) | قرار pending (شهرية) |
| الـ8k batch strategy (chunking, billing) | ليس جاهزًا |

## Decisions Rejected (مرفوض)

| القرار المرفوض | السبب |
| --- | --- |
| undocumented candidate_id mapping | batch_importer يفرض strict 1:1 — مقبول؛ أي mapping يدوي بدون hash مرفوض |
| blind regeneration للـmetadata الموثوق (id/pos/cefr/rank) | يهدر التكلفة ويكسر lineage |
| indiscriminate web grounding لكل 8k كلمة | تكلفة+ضوضاء، بلا دليل فائدة |
| استخدام IELTS لإعادة تخصيص CEFR/rank | IELTS بلا إشارة صلبة للمستوى؛ منطقة رمادية قانونيًا |

---

## MINEFIELD / quality عبر الحقول (نصيحة):

- `mnemonic_ar`: الحقل الأكثر خطورة — الإدخال يعتمد كليًا على الإنساني، والتوليد اللّامبالي يتراجع. **يحتاج gate بشري.**
- `definition_ar`: انتبه — أسوأ نكهة هي machine translation. Legacy كان أفضل في كثير من الحالات.
- `phonetic*` و `translations`: مشوّه بـ `?`/`�` في golden_v2 — يجب إعادة توليد/تحقق.
