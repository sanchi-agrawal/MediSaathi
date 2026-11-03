# Remaining scheduling blockers: diagnosis and fix

## Confirmed causes and runtime findings

1. The previous parser matched only compact ASCII `[01]-[01]-[01]`. Spaces and en dashes therefore produced `frequency_unsupported`, even though their displayed meaning could be the same. Instruction normalization and later source-substring checks could also withhold/reject a compact model field when the original text used spaced separators.
2. Scheduling correctly refused a reviewed medicine whose `needs_review` flag was still true. The reader sets that consolidated flag when the model's flag is not false, **any original ten-field value is null**, or original confidence is below 0.8. Thus an unknown ingredient or confidence can retain the flag even when dose/frequency/duration look complete. Generic confirmation did not resolve it, and the UI offered no guarded field-level resolution path.
3. Raw instruction unit `tab` could fail the strict canonical plan unit schema. A narrow literal unit alias conversion now uses the already confirmed explicit unit/form. It never supplies a quantity or resolves an absent unit.

The running API inspected on port 8005 was PID 25964, started 2026-11-01 21:49:27 without auto-reload. It included `/schedule/notation/confirm`, and Vite on 5177 served that acknowledgement UI; the installation was not simply missing the entire numeric feature. After these edits, its public health response still lacked the new `scheduling_review_contract: pattern-format-review-v1`, proving that the new fixes are not yet loaded in that live process. It was left running to preserve the user's current temporary workspace. No private browser cookie or authenticated prescription data was inspected; the exact missing fields in that live Dolo record cannot be asserted from the three displayed summary values alone.

## Format-only normalization

`1-0-1`, `1 - 0 - 1` and `1 – 0 – 1` now compare as the same binary triple, with horizontal spaces/tabs/nonbreaking spaces and ASCII hyphen/en dash accepted. Original strings are preserved in OCR and reviewed records. The helper recognizes all seven nonzero binary triples; fractions, nonbinary quantities, four slots, em dash, trailing instructions and other ambiguous text remain blocked.

Format equivalence is checked consistently in instruction source evidence, medicine/instruction comparison, explicit notation acknowledgement, source range checking, automatic plan preparation and the UI's displayed proposed digits. Only an exactly matching verified triple is removed from range detection. A separate `5-7 days` range is not removed. No dose, duration or clock time is inferred, and generic medicine/instruction confirmation still does not approve the notation's meaning.

Confirmed raw units such as `tab` map to canonical `tablet` only at the validated scheduling boundary. The raw unit remains visible, its explicit dose/source evidence is still required, and its canonical unit must agree with the confirmed medicine form.

## Truthful review-flag resolution

The API now returns per-record `review_requirements`: current/source flag, exact missing fields, unsupported source fields, original confidence status, required field verifications and eligibility to resolve. The Prescription Review checklist explains these in English/Hindi. Original OCR confidence and the original flag remain read-only and visible.

The new `POST /api/prescriptions/{analysis_id}/review/resolve` is an explicit **record review** action, not a scheduling override. It requires:

- The authenticated session's current analysis/revision and a saved review.
- An exact verification list for all eight clinical/source fields and explicit boolean acknowledgement.
- Complete reviewed values, source-supported names/ingredient/strength/form/frequency/duration/timing, original source availability and no unresolved question/uncertainty markers.
- Original confidence at the existing threshold of at least 0.8, unchanged from extraction.

Only then does the existing strict AIIntegration review method save a new reviewed record with its review flag resolved. The original OCR record remains unchanged. Existing confirmation, associations, notation approvals, explanations and schedules are revoked; a new independent medicine confirmation is required. Nothing is auto-confirmed or scheduled. Direct record payloads cannot clear an unresolved flag, edit original confidence, or silently alter a previously resolved flagged record. Frontend edits conservatively mark review pending again.

Unknown/low confidence cannot be invented or fixed by ticking checkboxes. Missing/unsupported fields cannot be dismissed. If the source cannot truthfully resolve them, scheduling remains blocked. The reader retained only a consolidated flag, not the provider's original internal reasoning; when no specific missing/low-confidence field explains it, the source flag is reported as such rather than inventing a reason.

## Verification

- **1,185 backend tests passed**, one skipped, 13 subtests passed.
- **213 frontend tests passed** and production build passed; the existing bundle-size warning remains.
- Real loopback HTTP smoke passed with a temporary local-account database and a mocked Google SDK: source-supported per-field flag resolution; unchanged original flag; required reconfirmation; all three formatting variants; separate association and notation acknowledgements; three date-only schedules with 5/3/7-day durations; unchanged independent strip workflows; session isolation/logout; and the new health contract. Four SDK calls were mocked, with **no live Gemini request**.
- Tests reject unresolved confidence/missing fields, direct flag-clearing payloads, incomplete attestations, stale revisions, unconfirmed notation and clinical ranges. They verify `1 tab` compatibility without deriving a dose from the pattern.
- No human browser verification was performed. The existing local account DB, authentication code, scheduling engine, strip parser, diagnostic guards, datasets and active workspaces were not modified or restarted.

## Load the fix

The API needs a deliberate restart. Restarting discards its temporary medical workspace, so do so only when ready. Use the exact PowerShell commands in SCHEDULING-STRIP-INTEGRATION.md. After restart, this presence-only check makes no provider request:

```powershell
(Invoke-RestMethod http://127.0.0.1:8005/api/health).scheduling_review_contract
# expected: pattern-format-review-v1
```

Review the now-visible field requirements, correct only source-supported information, save, perform eligible per-field resolution, and explicitly confirm again. Confirm each medicine–instruction link and the displayed three-slot meaning. Schedule then asks only for the start date. If requirements remain unresolved, leave the record flagged and seek source/clinical clarification.

## Files changed for this fix

- `medisaathi/confirmed_frequency.py`
- `medisaathi/ai_integration.py`
- `medisaathi/medication_instructions.py`
- `api/medicine_review.py`
- `api/models.py`
- `api/main.py`
- `api/downstream/automatic.py`
- `api/tests/test_review_pattern_resolution.py`
- `api/tests/test_numeric_and_strip_integration.py`
- `frontend/src/components/MedicineReviewChecklist.tsx`
- `frontend/src/components/MedicineReviewChecklist.test.tsx`
- `frontend/src/components/ScheduleAssociations.tsx`
- `frontend/src/lib/prescriptions.ts`
- `frontend/src/lib/scheduling.ts`
- `frontend/src/lib/scheduling.test.ts`
- `frontend/src/lib/language.ts`
- `frontend/src/lib/reviewRequirementsHindi.ts`
- `frontend/src/pages/PrescriptionFlow.tsx`
- `REVIEW-FORMAT-BLOCKERS.md`

Ignored editing and isolated HTTP-smoke helpers were created under `api/.venv`. No packages were installed and no files were staged, committed or pushed.
