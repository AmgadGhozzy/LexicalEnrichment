# PROMPT INVENTORY — LexicalEnrichment

## جدول الجرد

| الملف/الـPrompt | الإصدار | المستخدم بواسطة | الهدف | Current? | الدليل |
| --- | --- | --- | --- | --- | --- |
| `prompts/system/lexical_core.md` | ? (غير معروف الإصدار) | System A `phase1_lexical_core.py` | توليد senses غني | نعم (لكن schema تغيّر) | مستخدم في pipeline |
| `prompts/tasks/lexical_core.md` | ? | System A | إدخال batch | نعم | task prompt |
| `evaluation/prompts/lexical_enrichment.txt` | **v1.0.0** | `evaluation_runner.py` (EXP-001..011) | تعريف/شرح/3 أمثلة/mnemonic | **يفوقه v1.1** | EXP-010 81% |
| `evaluation/prompts/lexical_enrichment_v1.1.txt` | **v1.1.0** | `evaluation_runner` EXP-012 + Batch EXP-014 | نفسه + constraint الكلمة الحرفي | **نعم — المختار** | EXP-012 98%, EXP-014 160/160 |
| `SystemPrompt_Enhanced.md` (root) | Legacy V1 | Legacy (DictionaryEnrichment) | توليد كامل legacy (10 لغات + wordFamily + senses×6) | Legacy | استُخرج إلى V2 |
| `StructuredOutput_Enhanced.json` (root) | Legacy V1 | Legacy | Schema الكامل القديم | Legacy | استُخرج إلى lexical_core |

---

## أسئلة محددة

1. **ما الـprompt المستخدم في آخر تجربة ناجحة (EXP-014)؟**
   `evaluation/prompts/lexical_enrichment_v1.1.txt` (الإصدار 1.1.0) عبر `evaluation/configs/gemini_flash_v1.1_batch_pilot.json`.

2. **هل v1.1 هو الأفضل حاليًا بالأدلة؟**
   نعم — **بعدً بنائي/شكل فقط**. 98.13% evidence (EXP-012) مقابل 81.13% (EXP-010). **لكنه لم يفُز بعدُ تجريبيًا في جودة MNE/ARA/تعريف.**

3. **أين يُحمَّل؟** يُقرأ داخل `evaluation/utils.py` → `PROMPTS_DIR`, ويُمرَّر في `batch_input_builder` و`evaluation_runner`.

4. **ما config الذي يشير إليه؟** `gemini_flash_v1.1_full.json` و `gemini_flash_v1.1_batch_pilot.json` (للمقارنة: `smoke_gemini_flash.json` و `gemini_flash_v1_full.json` يستخدمان v1.0.0).

5. **هل هناك prompts قديمة مستخدمة بالخطأ؟** `lexical_enrichment.txt` (v1.0.0) مستخدم في EXP-011 (حالة `running`/قديمة) ولا يجب استخدامه للمضي قدمًا. `SystemPrompt_Enhanced.md` و`StructuredOutput_Enhanced.json` من legacy — تُستخدم فقط كمرجع.

6. **هل هناك duplication؟** نعم: prompt النظام A (`lexical_core.md`) مقابل النظام B (`lexical_enrichment_v1.1.txt`) — وظيفيّان متساويان تقريبًا لكن بنِى schemaS مختلفة. **Duplication بنيوي.**

7. **Freeze:** `lexical_enrichment_v1.1.txt` + `enrichment.v1.json` (في سياق الـbatch التجريبي حتى تُحسم جودة).

8. **Archive:** v1.0.0، EXP-001..007 الفاشلة، Legacy prompts.

9. **Delete (بعد قرار بنيوي):** أي مسار prompt ينسخ الآخر — سنُبقي مسارًا واحدًا.

---

## تحليل v1.0 → v1.1 علميًا (هل المقارنة عادلة؟)

| المتغيّر | EXP-010 (v1.0) | EXP-012 (v1.1) | العدالة |
| --- | --- | --- | --- |
| Prompt | lexical_enrichment.txt | lexical_enrichment_v1.1.txt | **هو المتغيّر الوحيد الكبير** |
| Schema | enrichment.v1 | enrichment.v1 | ✔ نفسه |
| Validator | artifact_validator v1.0.0 | artifact_validator v1.0.0 | ✔ نفسه |
| Model | gemini-2.5-flash | gemini-2.5-flash | ✔ نفسه |
| Temperature | 0.2 | 0.2 | ✔ نفسه |
| Golden Set | golden_v2 (hash نفسه) | golden_v2 (hash نفسه) | ✔ نفسه |
| عدد الحالات | 160 (159 نتج) | 160 | ~~ (~1 فرق) |
| Runner failures | 1 (CAND مفقود) | 0 | ✔ |
| Bug: target | 30 TARGET_WORD_MISSING | 3 | ← التحسين المنسوب لـv1.1 |

**التحسين المنسوب للـv1.1 = فقط الالتزام بالكلمة الحرفي في الأمثلة.** ليس تحسينًا في جودة المعنى. التصنيف:
- **Proven:** v1.1 يرفع الالتزام بالكلمة الحرفية في الأمثلة (30→3). ✔ VERIFIED.
- **Likely:** الجودة العامة أفضل قليلًا في struct.
- **Unknown:** تأثير v1.1 على MNE/ARA/definitions على نطاق 160 — **غير مقاس**.
