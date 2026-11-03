# Confirmed numeric scheduling and restored strip expiry

## Scheduling behavior

`1-0-1` was previously rejected before reaching Person 3's engine: AIIntegration accepted only BD/BID/TDS/TID/QID/HS and its numeric-range detector also matched the hyphens in a three-slot pattern. The engine already supports binary slots alongside a separately explicit dose.

`medisaathi/confirmed_frequency.py` now recognizes exactly the seven nonzero ASCII binary triples: 1-0-0 morning, 0-1-0 noon, 0-0-1 night, 1-0-1 morning/night, 1-1-0 morning/noon, 0-1-1 noon/night, 1-1-1 all three. These are time-of-day flags, not quantities or clock times. Fractions, 2-0-1, four slots, ranges, tapers, OD/PRN and ambiguous patterns remain blocked.

Both medicine and instruction scopes must first be independently reviewed and confirmed, and their explicit association must be persisted. The Review page then displays the exact pattern and mapping, with a separate checkbox and **Confirm three-slot meaning** action. `POST /api/prescriptions/{analysis_id}/schedule/notation/confirm` validates the session, analysis, all three revisions and association. It creates and consumes a server-side receipt bound to the current confirmed records. Browser booleans/events cannot substitute for this receipt.

AIIntegration permits a pattern only when that exact meaning has been acknowledged for its current linked records. Only that exact source token is removed from range detection; other ranges remain rejected. The existing source checks for separate dose quantity, unit/form agreement, duration, conflicts and uncertainty still run. Numeric source food timing such as `After food` is preserved; slots come only from acknowledged notation. Optional x/× prefixes on literal day durations are supported without altering source text.

Missing dose/unit is not filled from notation or strength. For example, a line containing only `Tab Dolo 650 1-0-1 x 5 days After food` can still be blocked if the existing extractor has withheld its administered dose/unit. The successful synthetic regression includes a separately explicit `take 1 tablet` dose. Users must review actual data; this feature does not invent what the source omits.

Read-only schedule summaries and existing review/approval endpoints are reused. Start date is the only new required Schedule input. Independent durations survive multi-medicine generation. Persisted association verification and cross-tab/current-state refresh from the previous fix remain in place. Source edits revoke links, notation acknowledgement and schedules; a stale request cannot reuse them. The original scheduling engine is unchanged.

### Preserved safety limit

An attempted adapter change to clear the medicine `needs_review` flag was rejected by automatic approval review. It was not implemented. The original flag is preserved and those unresolved records remain blocked by preparation and the existing engine. Supporting a separate safe resolution workflow for that flag is outside this change. Confirmation of slot meaning does not resolve other medical uncertainty.

## Standalone strip scanner

The restored dashboard card is **Medicine Strip Expiry Scanner** and sidebar entry is **Strip Expiry**, at `/dashboard/strip-expiry`. Old `/dashboard/expiry` links redirect there. Investigations remain hidden. Strip scanning is not reintroduced into Prescription Analysis.

The existing scanner, uploader/camera preview (zoom/rotation), strip client, `/api/strips` upload/analyze/review/confirm/invalidate routes, Python read_strip extractor and conservative parser are reused. PNG/JPEG uploads in real mode have normal validation, not fixture allowlists. Mode provenance distinguishes Gemini, static offline fixtures and unverified/unavailable modes. A capability GET never triggers extraction. Original medicine/batch/date observations remain reviewable; source text is retained separately.

The API adds a date-only comparison after genuine strip confirmation, using the current Asia/Kolkata date:

- Day precision: dates before today are expired; today/future dates are not expired according to the confirmed date.
- Month precision: past calendar months are expired; future months are not expired by date; the current month stays unclear. No last day of month is inferred.
- Unconfirmed, unknown, uncertain or conflicting results remain unclear. Original month-only precision and raw observations are unchanged.

The UI shows the comparison date and prominently states that expiry text does not establish medicine safety, handling or storage quality. Strip edits revoke strip confirmation without invalidating unrelated prescriptions or schedules. No inventory entries, notifications or Telegram calls are enabled.

## Verification

Full offline backend tests: 1,177 passed, one skipped, 13 subtests passed. All 205 frontend tests and the production build passed after the final UI changes. Existing bundle-size warnings remain.

The integration test goes through actual local account auth, real reader/normalizer code and a mocked Google SDK: synthetic Dolo 1-0-1/5 days, Cetirizine 0-0-1/3 days and Omeprazole 1-0-0/7 days; both independent confirmations; persisted pair confirmations; separate notation acknowledgement; source checks; schedule review/approval; correct slot quantities and end dates. All seven patterns have API tests proving they fail before notation acknowledgement and cannot reuse stale revisions. Strip review follows without damaging those schedules.

An additional isolated real loopback HTTP smoke passed (not just TestClient): signup/login, all three schedules, PNG and JPEG strip extraction/review/confirmation, past/future statuses, prescription isolation and logout. Its provider was mocked (four SDK calls), and its account database was created in an isolated temporary directory. The existing account DB, port 8005 service, datasets and user workspaces were untouched. No genuine browser interaction or live Gemini OCR was performed.

## Restart commands

The current server has no automatic reload. Restart only when ready: its temporary medical workspace is not durable across restart. Do not start a competing listener; stop it using Ctrl+C in its own terminal first. This change did not stop it or delete its workspace.

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH = 'C:\Users\ASHTAMI\MediSaathi-TeamIntegration\api\.venv\deps'
$env:MEDISAATHI_LOCAL_OFFLINE = '0'
$env:MEDISAATHI_LOCAL_HTTPS = '0' # Loopback HTTP only. HTTPS uses Secure cookies.
$python = 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

The existing AI `.env` is loaded read-only, only into Python. No key is printed or copied to Vite. Startup makes no Gemini request.

In a second terminal:

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Use `http://localhost:5177` consistently. Review and confirm scopes, confirm each link and its numeric slot meaning, then choose the start date on Schedule. Open the separate scanner from the dashboard. Only clicking Analyze triggers extraction; live requests require available server credentials/quota and an appropriate image. Offline mode (`MEDISAATHI_LOCAL_OFFLINE=1`) remains fixture-restricted and is labeled simulation.

## Files changed

- `medisaathi/confirmed_frequency.py`
- `medisaathi/ai_integration.py`
- `api/downstream/automatic.py`
- `api/downstream_routes.py`
- `api/expiry_status.py`
- `api/strip_routes.py`
- `api/tests/test_numeric_and_strip_integration.py`
- `api/tests/test_association_persistence_flow.py`
- `frontend/src/App.tsx`
- `frontend/src/components/DashboardLayout.tsx`
- `frontend/src/components/ScheduleAssociations.tsx`
- `frontend/src/components/ScheduleAssociations.test.tsx`
- `frontend/src/pages/Overview.tsx`
- `frontend/src/pages/Schedule.tsx`
- `frontend/src/pages/ExpiryScanner.tsx`
- `frontend/src/pages/ExpiryScanner.test.tsx`
- `frontend/src/pages/BilingualWorkflow.test.tsx`
- `frontend/src/ReducedScope.test.tsx`
- `frontend/src/lib/scheduling.ts`
- `frontend/src/lib/strip.ts`
- `frontend/src/lib/language.ts`
- `frontend/src/lib/restoredFeaturesHindi.ts`
- `frontend/src/dashboard-typography.css`
- `SCHEDULING-STRIP-INTEGRATION.md`

Ignored editing/HTTP-smoke helpers remain under `api/.venv`. No staging, commit, push, merge, diagnostic guard change, authentication/database migration, dependency installation or original worktree modification was performed.
