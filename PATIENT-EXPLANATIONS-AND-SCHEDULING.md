# Selected medicine explanations and scheduling correction

## Root causes confirmed in code

1. `assistant.explain_prescription()` intentionally renders confirmed OCR fields
   offline. It is not a drug-information generator. The UI had presented that
   technical renderer as the primary medicine explanation.
2. `PrescriptionFlow.selectLanguage()` called the old explanation endpoint on
   language changes. That automatic call is removed. No patient explanation is
   requested on upload, OCR, review, confirmation, restoration or navigation.
3. `literal_count()` rejected named timing and accepted only phrases such as
   `once daily`. Thus reviewed `once at night` / `once in the morning` records
   did not establish the stored count, even though their count was unambiguous.
4. Scheduling read the separate API-facing association list, which could be
   absent while AIIntegration still held valid, current confirmation receipts.
5. Time pickers were hidden whenever a medicine was ineligible, including when
   its count was known but a different clinical review flag remained unresolved.
6. A missing/unloaded endpoint could become generic `api_error`. Transport now
   distinguishes an unloaded route, expired session, stale source and invalid
   input, preserving safe server categories and English/Hindi errors.

## What changed

Prescription Analysis keeps its existing layout and ordinary review/save/scope
confirmation workflow. Each medicine now has an **Explain Medicine** button and
an expandable patient information card beneath it. Technical OCR/source summaries
remain available inside a collapsed technical-details disclosure.

Only the selected medicine is requested. The interface language determines English
or Hindi. Changing language does not request content; another explicit click is
needed for an uncached language. Closing/reopening reuses in-memory content.
Navigating back or refreshing may require clicking again, but the server reuses
the session cache without another provider call for the same confirmed context.

The backend checks authentication/workspace ownership, current analysis/revision
and actual medicine-scope confirmation. It never accepts records, trusted events
or confirmation claims from the explanation request. Cache keys include medicine,
language, instruction/association context, source revision and reference version.
Source changes revoke/hide old cards. Concurrent requests are serialized by the
existing session lock. No credentials or medical records enter localStorage.

### Grounding and coverage

`api/drug_information.py` is a separate versioned reference registry, **not** a
change to the medicine pricing dataset. It contains bilingual patient information
for paracetamol, cetirizine and omeprazole. Exact generic identities qualify only
when supported and not flagged for unresolved medicine review. Dolo qualifies
only for the documented 650 mg paracetamol tablet tuple with matching confirmed
ingredient/strength/form; a brand name alone never qualifies. Conflicting salts,
combination products, unsupported brands or unresolved identity return an explicit
uncertain status and make no Gemini call.

Sources consulted:

- NHS paracetamol: https://www.nhs.uk/medicines/paracetamol-for-adults/
- Product SmPC: https://www.medicines.org.uk/emc/product/5164/smpc
- Historical NPPA Dolo-650 identity row:
  https://nppa.gov.in/uploads/year2022/118-Revised.pdf
- NHS cetirizine overview, mechanism, precautions and side effects:
  https://www.nhs.uk/medicines/cetirizine/
- NHS omeprazole: https://www.nhs.uk/medicines/omeprazole/
- MedlinePlus omeprazole: https://medlineplus.gov/druginfo/meds/a693050.html

The NPPA row is an identity reference, not a current price quote or proof of the
physical medicine pack. Direct PDF retrieval timed out during review; its indexed
official row was available. No prices or clinical facts are inferred from the
existing unverified example catalogue.

Gemini receives only the selected generic ingredient, requested language and
approved bilingual facts. It assembles approved fact IDs; free model clinical
claims, invented sources, doses or diagnoses are never rendered. All six sections,
including precautions and serious warning signs, must be present. The server
renders the approved language text after validation. This is deliberately a
constrained, source-grounded explanation, not unrestricted medical generation.

The card separately labels the patient's original confirmed source text and,
where available, its independently confirmed linked instruction. Those instructions
are not sent to Gemini. General uses are explicitly distinguished from the reason
the doctor prescribed the medicine. Information is a short overview, not a complete
leaflet or personalized treatment advice. Other ingredients/products require added
trusted reference coverage; they are not fabricated from model memory.

Gemini is called server-side through the existing reader configuration and SDK.
There is one provider attempt per uncached explicit click, no schema retry, no
fallback model and no static-success fallback if Gemini is unavailable.

### Scheduling

Literal reviewed phrases now include `once at night` and `once in the morning`.
Count/explicit named meaning is stored during the existing genuine association
action, not parsed again by generation. Conflicting timing/count, unsupported
notation and ambiguous relationships remain blocked. Current authoritative backend
link receipts can repair missing API-facing association metadata; no new link is
guessed or approved silently.

Known-count time pickers remain visible even if another unresolved clinical field
blocks that medicine. Eligible medicines can still generate their courses. The
unresolved medicine is clearly identified and is not silently included. No flags,
doses, durations or missing frequencies are automatically filled/cleared.

Scheduling still has only start date and clock-time inputs, read-only prescription
values and Generate My Schedule. No new association dropdown, confirmation checkbox,
plan-review screen or approval action was added. Existing server events, source
binding, independent confirmations, account isolation and clinical guards remain.

## Routes

New: `POST /api/prescriptions/{analysis_id}/medicines/explain`

```json
{"revision":"current-server-revision","record_index":0,"language":"hi"}
```

The response distinguishes `explained` from `identity_uncertain`; includes the six
patient sections, source links and separate original prescription instructions;
and reports cache use. Errors are JSON and contain no provider response bodies.

Existing clock state/generation endpoints remain. No authentication, account
database, Gemini OCR extraction, strip-expiry pipeline or pricing implementation
was replaced.

## Verification

- Full offline Python suite: **1,237 passed, 1 skipped; 13 subtests passed**.
- Full frontend suite: **234 passed**.
- Production build passed; existing large-chunk warning remains.
- Final focused backend suite: **10 passed** after cache refinement.
- Real ephemeral local HTTP test, isolated temporary SQLite DB and mocked SDK:
  ordinary review/confirmation → genuine associations → visible counts 2/1/1 →
  selected start date/times → dated calendars → selected medicine explanations.
- Exact synthetic source: Dolo 1 tablet twice daily for 5 days; Cetirizine 1 tablet
  once at night for 3 days; Omeprazole 1 capsule once in the morning for 7 days.
  Starting 5 November 2026 produces end dates 9, 7 and 11 November, quantities
  10/3/7, and the chosen 08:15/20:30, 21:45 and 07:10 times respectively.
- Exactly two SDK calls during OCR; no explanation calls during review/navigation/
  scheduling. Clicking each selected medicine adds one call. Reopening the same
  medicine/language adds none. Hindi bodies differ from English bodies.
- Tests cover uncertainty, unknown/combination identities, provider/malformed/
  configuration failures, source edits, cross-account access, genuine receipt
  recovery, unresolved flags staying intact, selected-only requests, collapse/
  reopen, transport errors, language changes and no automatic fetching.

No live Gemini or Telegram request was made. Browser automation was attempted with
the computer-use skill. The returned Chrome window was a ChatGPT conversation,
not the local app; navigation also lacked usable geometry. Automatic approval
rejected further capture to avoid exposing unrelated private conversation content.
Automation stopped. **Actual local browser workflow verification is not claimed.**

## Files changed in this correction

Backend:

- `api/drug_information.py` (new)
- `api/patient_explanations.py` (new)
- `api/clock_scheduling.py`
- `api/sessions.py`
- `api/main.py`
- `medisaathi/confirmed_count.py`
- `api/tests/test_patient_explanations.py` (new)

Frontend:

- `frontend/src/components/PatientMedicineExplanation.tsx` (new)
- `frontend/src/components/PatientMedicineExplanation.test.tsx` (new)
- `frontend/src/components/PrescriptionExplanation.tsx`
- `frontend/src/pages/PrescriptionFlow.tsx` (per-medicine button; removed automatic
  explanation request only — existing review layout and confirmations retained)
- `frontend/src/pages/ClockSchedule.tsx`
- `frontend/src/pages/ClockSchedule.test.tsx`
- `frontend/src/pages/WorkspaceRestore.test.tsx`
- `frontend/src/pages/BilingualWorkflow.test.tsx`
- `frontend/src/lib/patientExplanations.ts` (new)
- `frontend/src/lib/patientExplanations.test.ts` (new)
- `frontend/src/lib/patientExplanationHindi.ts` (new)
- `frontend/src/lib/clockScheduling.ts`
- `frontend/src/lib/language.ts`
- `frontend/src/patient-explanations.css` (new)

Documentation: this file. Temporary test/edit helpers are ignored under
`api/.venv/`. No dependency installs, account database changes, staging, commit,
merge or push occurred. Other existing uncommitted work remains intact.

## Runtime and manual verification

The inspected port-8005 backend reports Gemini configuration present and the
previous clock contract, but **not** the new patient-explanation contract. It was
not interrupted to preserve its current temporary prescription workspace. Restart
it to load the new code. Registered accounts remain; temporary prescription state
is lost at restart. No external call happens on startup.

Backend (Ctrl+C in the old API terminal first):

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

Frontend, separate terminal:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Presence-only readiness check:

```powershell
(Invoke-RestMethod http://127.0.0.1:8005/api/health).patient_explanation_contract
# selected-source-grounded-v1
```

Manual browser checklist:

1. Sign in at localhost:5177 and explicitly analyze only a synthetic source.
2. Complete the unchanged medicine/instruction review and correct relationships
   in Prescription Analysis. Do not clear unresolved fields by guessing.
3. Confirm no explanation request appears during those actions or a language change.
4. Click Explain Medicine for one identified medicine; observe one request, loading,
   all patient sections and separate source instructions. Other medicines stay closed.
5. Close/reopen; verify no duplicate provider request. Change to Hindi; verify no
   request until clicking, then full Hindi content. Navigate back and click again;
   the server should report a cache hit for an unchanged context.
6. Open Scheduling; check 2/1/1 time inputs. Select start date and times, then generate.
   Verify the course lengths, quantities and dated times; edit a time and regenerate.
7. Edit a source field; confirm old information/calendars disappear and no automatic
   regeneration occurs. Check unresolved medicine flags remain blocked.
8. Verify Strip Expiry, pricing and account controls remain accessible.
