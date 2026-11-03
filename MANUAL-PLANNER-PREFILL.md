# Optional reviewed-prescription prefill for the manual planner

## Implemented

The working `ManualSchedule` page and its calendar/list calculation model remain in use. An optional `PrescriptionPlannerPrefill` panel reads the current local-account workspace and shows every identified medicine, including incomplete records. Eligible medicines have read-only name, quantity/unit, days and daily administration count. The only editable prescription-card inputs are start date and the exact number of preferred clock times.

The existing standalone manual form remains available via **Add Medicine Manually**, and remains usable without any prescription or if the read endpoint is unavailable. No prescription layout or existing review controls changed.

## API/data source

`GET /api/planner/prescription` is registered additively in the existing `api.local_server:app` through `register_team_routes`. It uses the existing server-owned authenticated workspace cookie/session store. There is no second server, no OCR call and no scheduling endpoint invocation.

Sources:

- Current reviewed medicine records, with names available for display even before review is saved.
- Current independently saved instruction review, not original OCR confidence or general medicine review flags.
- A genuinely confirmed, current medicine–instruction association when available. Its existing stored slot/count capability is preferred.
- Otherwise, an exact case/whitespace-normalized name join **only when one reviewed medicine and one reviewed instruction uniquely match**. This is a read-only join, not an association acknowledgement; it never writes a link or marks a field confirmed. Similar/partial names and duplicates remain unresolved.
- Count fallback uses the existing conservative literal-count helper on reviewed source text. Unverified numeric notation is not interpreted into a count. Missing/unsafe source values, ambiguous relationships, unit contradictions, missing dose/duration/count and document-wide hazards keep that record incomplete. Other records remain usable.

Both medicine and instruction reviews must have been explicitly saved to supply complete prefills. Existing confirmations and associations are reused if present; **this demo read does not create or demand a new confirmation**. It does not authorize any downstream clinical schedule. The response labels provenance as `confirmed_link` or `unique_reviewed_name`, not a fabricated verified identity.

The response contains current analysis/medicine IDs, source fingerprints, reviewed values, missing-field codes and a server-derived account ID. Existing local-auth middleware verifies the request. The endpoint reads the existing authenticated workspace mapping and session table to identify its owner; it does not change authentication or database data. The client checks that returned owner against the current local user, preventing account-switch responses from being cached under another user. No browser-provided owner or analysis ID is trusted to select someone else's records.

The endpoint does not call old clock eligibility, schedule review/approval, association mutation or OCR endpoints. Original ten-field medicine records, `needs_review`, ingredients and confidence remain untouched. No image or raw prescription text is sent in this response.

## Generating and preserving demo calendars

- Clicking **Generate Schedule from Reviewed Medicines** re-reads the same GET endpoint and checks the selected source fingerprints before creating local visual plans.
- Only eligible medicines with a selected start date and all their clock times are generated. Incomplete or unfilled cards do not block complete filled cards.
- Generation passes the values into the existing `validatePlan` / `validatePlans` and existing calendar/event model. No new calendar arithmetic engine or backend generation path was added.
- Source plans use IDs namespaced by analysis ID and medicine reference. An explicit regeneration replaces that source course, rather than duplicating it. Independently added manual UUID courses are preserved. Background refresh never writes or deletes an existing calendar plan.
- Existing account-scoped tab-local generated-plan persistence remains unchanged. New start/time drafts use a separate account-scoped `sessionStorage` entry. Focus refresh and remount preserve these entries; the planner is remounted when account identity changes. No credentials or images are stored.
- Saved demo calendars remain user-created snapshots until explicitly regenerated/edited/deleted. They are not a live prescription archive or an approved medication order. A server workspace reset may remove current prefills while leaving the user's local demo calendar intact.
- If the reviewed clinical values changed before Generate, the new cards are shown and no plan is silently generated using old values. Previously entered preferences and independent saved plans are preserved.

Existing unencrypted browser-tab demo-storage limitations and resource limits in `MANUAL-SCHEDULER.md` still apply. Use fictional data, follow clinician instructions, and do not treat browser storage as secure medical-record storage. No reminders, messages, push notifications or external calendar operations exist in this path.

## Verification

- **1,272 Python tests passed**, 1 skipped, 13 subtests passed.
- **294 frontend tests passed**, 39 files, run with `--maxWorkers=4`. The first high-parallelism run hit the previously timing-sensitive login test; authentication source/tests were not modified. The bounded-worker full run passed.
- Production build **passed**; existing large-chunk warning only.
- `git diff --check` passed; existing CRLF notices only.
- Authenticated ASGI and actual loopback TCP/HTTP tests use temporary SQLite accounts, synthetic image extraction through mocked Gemini, existing review/confirmation/association setup, and the new read endpoint. They assert 2/1/1 counts, 1/1/1 quantities, 5/3/7 durations, unchanged AI snapshots, no new associations/schedules and no additional Gemini calls.
- Read-only exact-name fallback works with missing ingredient/original OCR flags and no existing associations. Missing doses, ambiguous names and unknown/unverified numeric frequency remain incomplete. Account B receives no account A workspace data.
- React integration tests show three read-only cards, exactly four prescribed clock inputs, and local generation of **20 events** starting 3 November 2026: Dolo 10 through 7 November; Cetirizine 3 through 5 November; Omeprazole 7 through 9 November.
- Adding a separate two-event manual course, then generating prefills, produces 22 events; refresh/remount and explicit regeneration retain 22, not duplicate or overwrite the manual course. Existing month/year/leap-year boundary tests remain passing through the unchanged calendar model.
- Client transport tests confirm only authenticated GET prefill reads; no old review, approval or association API calls from Scheduling. Incomplete records, stale source, unavailable endpoint, owner mismatch, Hindi/light rendering and persisted clock values are covered.

Actual browser interaction was **not verified**: the browser connector returned `The browser access host is unavailable`. Component tests and HTTP tests are not claimed as actual Chrome verification. No live Gemini request was made.

## Current runtime and loading the feature

The running Vite module includes the new prefill component. The running port-8005 backend's OpenAPI does **not yet contain** `/api/planner/prescription`; it must be restarted to load the added route. It was not forcibly restarted because doing so clears the current temporary prescription workspace. Local registered accounts and browser-local manual plans survive that restart.

In the API terminal press Ctrl+C, then:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

Verify route loading without credentials or OCR:

```powershell
$schema=Invoke-RestMethod http://127.0.0.1:8005/openapi.json
$null -ne $schema.paths.'/api/planner/prescription'
# True
```

Vite, if not already running:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Manual verification: sign in at localhost:5177; analyze a synthetic prescription explicitly; save the existing medicine and instruction reviews; open Scheduling. If existing confirmed associations are absent, names must uniquely match exactly. Choose dates and times in the reviewed-medicine cards and click Generate Schedule from Reviewed Medicines. Confirm the existing calendar appears. Also test no prescription, one incomplete medicine, refresh and a separate manually added course. Startup and opening Scheduling do not invoke Gemini.

## Exact files changed

New:

- `api/planner_prefill.py`
- `api/tests/test_planner_prefill.py`
- `frontend/src/components/PrescriptionPlannerPrefill.tsx`
- `frontend/src/lib/plannerPrefill.ts`
- `frontend/src/lib/plannerPrefill.test.ts`
- `frontend/src/pages/PlannerPrefill.test.tsx`
- `MANUAL-PLANNER-PREFILL.md`

Modified:

- `api/team_routes.py` — register the additive read route.
- `frontend/src/pages/ManualSchedule.tsx` — mount optional cards and merge their explicitly generated plans into the existing calendar.
- `frontend/src/pages/ManualSchedule.test.tsx` — empty-source mocks and storage-message assertion for the optional panel.
- `frontend/src/lib/manualPlannerHindi.ts` — new feature copy only; existing translations preserved.
- `frontend/src/manual-planner.css` — styling for the new read-only cards.

No dependencies installed. No auth/schema changes, external synchronization, clinical scheduling changes, source-worktree edits, commits, pushes or merges.
