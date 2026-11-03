# Single prescription review → date-only scheduling

**Superseded:** the user requested restoration of the preceding Prescription
Analysis page. The application now routes Analysis to `PrescriptionFlow` and
Scheduling to `ClockSchedule`. This document describes the previous experiment,
not the current user flow. See [CLOCK-SCHEDULING-RESTORATION.md](CLOCK-SCHEDULING-RESTORATION.md)
for the current implementation, verification and restart commands.

The application routes now use `UnifiedPrescriptionReview` and `UnifiedSchedule`.
Legacy scope/association/plan endpoints remain compatible, but the routed schedule
page does not call them or ask the patient to repeat approval actions.

## Patient workflow

1. Explicitly analyze the image. Existing medicine and instruction extractors run
   server-side; restoring/navigating/refreshing only reads the workspace.
2. In Prescription Analysis, review each medicine beside its selected instruction,
   dose, unit, duration, original frequency text and proposed **named** timing.
   Unique exact-name pairs are proposals, never silently approved. Correct a pair
   and its fields here when necessary. Confirm the complete review once.
3. Scheduling shows the confirmed snapshot. Choose a course start date, then
   **Generate My Schedule**. One HTTP operation generates all eligible courses,
   keeping each medicine's dose and duration. Blocked medicines remain separately
   listed with review links. No dose defaults or clock times are invented.

Review flags are not automatically removed. The existing source-supported medicine
resolution rule still requires every verification and acceptable original confidence.
Instruction resolution must be explicitly selected within the same review. It is
restricted to original `missing_information` warnings and must first pass the
existing source-backed clinical scheduling guard with the flag still intact.
Unsupported/ambiguous source warnings cannot qualify. Original extraction flags,
nulls and uncertainty codes remain stored separately; only the reviewed flag can
change. For example, an absent route remains null, never inferred from the form.
Unresolved instructions/medicines remain blocked.

## HTTP contracts

- `GET /api/prescription-review/current`: current independent extraction scopes,
  revisions, source review requirements and proposed pairs/named slots.
- `POST /api/prescriptions/{analysis_id}/review/confirm-all`: strict ten-field
  medicines, separate instruction envelope, reviewed pairs and canonical slots,
  current scope revisions, explicit review acknowledgement and explicitly selected
  record resolutions. Creates scope-bound acknowledgements and association/timing
  events on the server. The browser cannot submit trusted events or clear an
  existing instruction flag by changing its boolean.
- `GET /api/confirmed-prescription/current`: confirmed source-bound snapshot and
  the current generated course, if any.
- `POST /api/confirmed-prescription/generate`: only `snapshot_id` and ISO
  `start_date`. Validates ownership, source revisions, independent confirmations,
  links, canonical slots and clinical fields. Uses existing AIIntegration and
  schedule arithmetic with server-created action-bound events internally.

Canonical slots: morning, afternoon, evening, night, bedtime. Afternoon maps to
the engine's noon field. Evening is separately represented, never folded into
night or bedtime. Legacy frequency notation is interpreted only to propose timing
in review; generation does not parse it again. Literal named timing is preferred.
Numeric and literal timing that conflict remain blocked. Dates are course dates,
not invented appointment/administration clock times.

Same snapshot/date requests reuse the calculated course. A new date recalculates
the calendar; source edits/replacements and association changes invalidate the
snapshot and generated results. Cross-tab invalidation hides old calendars, and a
late response cannot restore one after an invalidation event.

The current local-account middleware still binds the workspace to the authenticated
session. Account SQLite, authentication, cookies and medical confirmation rules
were not replaced. Prescription snapshots remain **session-memory only**, not a
durable medical archive; a backend restart loses them. Original images remain in
that temporary workspace. No notifications or provider requests occur on startup.

## Verification and limitations

`api/tests/test_confirmed_workflow.py` covers the full authenticated route flow,
including an actual ephemeral loopback TCP server, a temporary SQLite account
database and mocked Gemini SDK responses. The synthetic prescription uses Dolo
(1 tablet morning/night, 5 days), Cetirizine (1 tablet night, 3 days), and
Omeprazole (1 capsule morning, 7 days). Starting 5 November yields course end
dates 9, 7 and 11 November respectively. Tests deliberately disable numeric pattern
parsers after confirmation. Separate tests distinguish evening from bedtime/night,
reject stale/cross-session/forged operations, preserve original warnings, and
prevent failed scheduler output from being published.

`UnifiedWorkflow.test.tsx` exercises the routed React flow, restoration under
StrictMode, source-validated resolution requests, Hindi/light theme, failure states
and late-response invalidation. These are jsdom tests, not human browser evidence.
No live Gemini requests were made. Actual browser visual/interaction verification
remains manual; the computer-use helper previously stopped because it could not
verify the current browser URL. No bypass was used.

## Restart the application

The inspected process on port 8005 was still running the older contract. It was
left untouched to avoid erasing its current prescription workspace. Stop that
server with **Ctrl+C in its own terminal** before restarting. Local user accounts
remain in SQLite; temporary prescription state must be reviewed again.

Real OCR backend (reads the existing server-only environment file):

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

For the existing offline registered-fixture demo instead, set
`MEDISAATHI_LOCAL_OFFLINE='1'` before starting. Fixture simulation is labelled and
does not establish live OCR accuracy. No external request is made merely by
starting either mode.

Frontend, in another terminal:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Check the running contract without printing credentials:

```powershell
(Invoke-RestMethod http://127.0.0.1:8005/api/health).confirmed_prescription_contract
# single-review-date-only-v1
```

Manual browser check: log in at localhost:5177; upload a synthetic source; explicitly
analyze; review all fields and timing beside each instruction, resolving only
source-supported flags; confirm once; navigate to Scheduling; choose a date;
generate; verify the three independent calendars; return to review and edit a
field; verify the old course disappears and fresh source review is required.
Repeat in Hindi/light mode and refresh without re-analyzing. Do not use real
patient images for demonstration or make an unapproved live provider call.

## Files changed for this workflow

Backend:

- `api/confirmed_workflow.py`
- `api/main.py`
- `api/sessions.py`
- `api/downstream/automatic.py`
- `api/downstream/models.py`
- `api/downstream/scheduling.py`
- `medisaathi/ai_integration.py`
- `medisaathi/confirmed_frequency.py`
- `medisaathi/schedule.py`
- `api/tests/test_confirmed_workflow.py`
- `api/tests/test_named_slot_workflow.py`

Frontend:

- `frontend/src/App.tsx`
- `frontend/src/ReducedScope.test.tsx`
- `frontend/src/components/ImageUploader.tsx`
- `frontend/src/lib/confirmedPrescription.ts`
- `frontend/src/lib/confirmedWorkflowHindi.ts`
- `frontend/src/lib/language.ts`
- `frontend/src/pages/UnifiedPrescriptionReview.tsx`
- `frontend/src/pages/UnifiedSchedule.tsx`
- `frontend/src/pages/UnifiedWorkflow.test.tsx`
- `frontend/src/confirmed-workflow.css`

Documentation: this file. Other existing uncommitted project changes were retained.
Temporary edit helpers and isolated test databases/results are under ignored
`api/.venv/`; they are not source changes or account-database migrations.

Final verification: full Python suite **1,213 passed, 1 skipped**, plus 13 subtests;
full frontend suite **219 passed**; production build passed with the existing
large-chunk warning. No dependencies were added. No commit or push was made.
