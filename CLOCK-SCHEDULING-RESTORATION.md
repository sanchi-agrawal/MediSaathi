# Restored Prescription Analysis and user-selected clock scheduling

## What was restored

`App.tsx` again routes `/dashboard/analysis` directly to the existing
`pages/PrescriptionFlow.tsx`. The preceding component had been retained intact;
it was not necessary to reconstruct it from an older Git commit, overwrite it,
or discard any uncommitted work. Its styles and child components were not edited
in this correction:

- `ImageUploader`: original upload, preview, camera and explicit extraction flow.
- `MedicineReviewChecklist`: existing medicine review/flag-resolution controls.
- `SectionReview`: original independent instruction editing, saving and confirmation.
- `ScheduleAssociations`: existing explicit medicine–instruction association review.
- `PrescriptionExplanation`: original English/Hindi/Hinglish explanation controls.
- `MedicineMatching`: existing catalogue and pricing restrictions.

The combined `UnifiedPrescriptionReview` and its final-confirmation UI are no
longer routed or displayed. Experimental source remains unreferenced for rollback
provenance; no current application page calls its confirmation endpoint. No full
project restore/reset/checkout was performed. The Strip Expiry route/card/sidebar,
authentication, pricing dataset, Gemini credentials/configuration and original
AI/pricing worktrees were not changed.

## Scheduling data and safety

Scheduling reads the existing independently confirmed medicine and instruction
scopes plus their server-confirmed association. Dose and unit come from the linked
instruction, duration must agree with the confirmed medicine, and food phrases
remain literal confirmed source information. They are read-only.

The only editable fields are a shared course start date and exactly the prescribed
number of per-medicine clock times. There are no clinical fields, association
dropdowns, confirmation checkboxes or approval screens on Scheduling. Generation
is one HTTP action with invisible server-side approvals and validation.

Daily administration count comes from either:

1. Previously confirmed named timing slots, preserving morning/afternoon/evening/
   night/bedtime distinctions; or
2. A literal daily count, such as `twice daily`, established and bound when the
   ordinary explicitly reviewed medicine–instruction association is confirmed.
   It is not parsed again by generation. It does not invent morning/night slots.

Numeric notation is not sent to or displayed by Scheduling and is never parsed
by its preparation/generation path. Bare numeric notation without reviewed timing,
unsupported abbreviations, conflicting/variable/PRN courses, missing dosage,
unsupported units, missing duration, unresolved medicine flags and stale or
unconfirmed records remain blocked. Links return to the existing review controls.
No review flags are cleared by this scheduling implementation.

The existing AIIntegration source, association, independent confirmation and event
checks remain active. The existing schedule engine handles course arithmetic;
its additive explicit-count option requires an explicit dose/unit and never reads
the original frequency. Strict result validation checks dose totals, units, dates
and administration count before publishing the course.

Times are explicit patient preferences in `Asia/Kolkata` (`+05:30`), not inferred
medical recommendations. Every medicine must have distinct valid HH:MM values,
in the displayed order within a course day. No extra administrations may be added.
Overnight day-boundary reinterpretation and ambiguous timing require clarification;
the application does not silently move a bedtime dose into the next day.

Edits to source records/associations revoke schedules through the existing revision
and session invalidation. Clock preferences can be changed/regenerated without
editing the prescription. Prescription/clock state remains temporary server memory,
not a durable medical archive. SQLite local accounts remain unchanged and survive
restart. Real notification delivery remains disabled.

## Routes

- `GET /api/clock-scheduling/current`: confirmed read-only values, eligible daily
  counts, source revisions, precise blockers and any saved clock course.
- `POST /api/prescriptions/{analysis_id}/schedule/clock-generate`: current medicine,
  instruction and scheduling revisions, start date and `{medicine_ref, clock_times}`
  entries only. Dose/unit/duration/approval claims in the request are rejected.

Current local-account middleware authenticates both routes and scopes them to its
workspace. Existing CSRF/origin checks apply. The legacy association status API
keeps its previous response shape, so returning to Prescription Review after a
clock course does not break its client with a different schedule-result schema.

## Verification

- Full offline Python suite: **1,227 passed, 1 skipped, 13 subtests passed**.
- Full frontend suite: **226 passed**.
- Production build passed; existing large-chunk warning remains.
- Real ephemeral local TCP/HTTP test: signup → upload matching synthetic image →
  mocked Gemini extraction → ordinary separate medicine/instruction review and
  confirmation → reviewed associations/timing → clock selection → three dated
  courses → persisted current workspace → independent strip upload → logout.
- Dolo: 2 tablets at 08:15/20:30 for 5 days; Cetirizine: 1 tablet at 21:45 for
  3 days; Omeprazole: 1 capsule at 07:10 for 7 days. Start 5 November 2026; end
  dates 9, 7 and 11 November respectively. Separate literal-count test verifies
  two selected clock times without invented named slots.
- Tests reject extra/missing/duplicate/invalid times, forged dose fields, stale
  revisions and cross-account requests. Source edits remove the saved course.
- Numeric parsers are deliberately disabled after review in integration tests.
- Original Prescription Analysis tests, authentication, pricing and strip suites
  passed. UI tests cover fixed picker counts, preference restoration/editing,
  Hindi/light mode, blocked states and errors without false calendars.

No live Gemini or Telegram request was made. Gemini availability was checked only
by the existing presence-only health flag. Actual human browser visual verification
was not performed; source restoration, jsdom interactions and real local HTTP
verification are distinguished here rather than claimed as browser evidence.

## Files changed in this correction

Backend:

- `api/clock_scheduling.py` (new)
- `api/downstream/automatic.py`
- `api/downstream/models.py`
- `api/downstream/scheduling.py`
- `api/downstream_routes.py`
- `api/main.py`
- `medisaathi/confirmed_count.py` (new)
- `medisaathi/ai_integration.py`
- `medisaathi/schedule.py`
- `api/tests/test_clock_scheduling.py` (new)

Frontend:

- `frontend/src/App.tsx`
- `frontend/src/ReducedScope.test.tsx`
- `frontend/src/pages/ClockSchedule.tsx` (new)
- `frontend/src/pages/ClockSchedule.test.tsx` (new)
- `frontend/src/lib/clockScheduling.ts` (new)
- `frontend/src/lib/clockSchedulingHindi.ts` (new)
- `frontend/src/lib/language.ts`
- `frontend/src/clock-scheduling.css` (new)

Documentation: this file and the superseded notice in `SINGLE-REVIEW-SCHEDULING.md`.
No dependencies or account-database migrations were added. The ignored temporary
UI edit helper/test artifacts are under `api/.venv/`. Nothing was staged, committed
or pushed.

## Exact restart commands

The inspected port-8005 API is configured for Gemini but does **not** yet advertise
the new clock contract. It was not stopped, avoiding loss of its current in-memory
workspace. In its terminal press **Ctrl+C**, then restart. This loses temporary
prescriptions but does not delete registered accounts or change their database.

Backend, real OCR mode, using the existing server-only environment file:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

For the existing registered-fixture offline demo, set
`MEDISAATHI_LOCAL_OFFLINE='1'` instead before starting. Fixture simulation remains
explicitly labelled; it is not evidence of live OCR accuracy. Startup sends no
extraction requests in either mode. Local HTTP cookie handling uses the existing
explicit local-development setting; HTTPS deployment cookie protections remain.

Frontend, in a separate terminal (stop any existing port-5177 Vite instance first):

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Verify the process/version without credentials or any provider request:

```powershell
(Invoke-RestMethod http://127.0.0.1:8005/api/health).clock_scheduling_contract
# confirmed-clock-schedule-v1
```

Manual check: log in at localhost:5177; use the restored Analysis page to explicitly
analyze a synthetic prescription; save and confirm medicine/instruction scopes;
confirm correct links/timing there; open Scheduling; choose date and clock times;
generate; verify the dated courses; change a clock time and regenerate; edit an
instruction in Review and verify the old course disappears. Repeat in Hindi/light
mode. Open Strip Expiry from the sidebar and verify pricing remains separate.
