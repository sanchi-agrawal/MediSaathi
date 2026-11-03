# Scheduler request-flow and partial-course repair

## Confirmed causes

### Record errors incorrectly treated as global scheduling hazards

`medication_instructions` correctly returns per-record uncertainty reasons and also adds their union to the section's `issues` summary. AIIntegration's association/count/slot and schedule checks previously treated that summary as if every issue affected every medicine. A rejected Dolo frequency (`unsupported_source_value`) therefore prevented storing valid daily counts for Cetirizine and Omeprazole too. This reproduced **0/0/0 clock counts**, despite independently reviewed and confirmed scopes and genuine associations.

The corrected scheduling-only `_unsafe_instruction` gate checks the linked instruction's own reasons, preserves unattributed global warnings, and always preserves global blurred/clipped/unreadable hazards even when also present on a record. An unrelated record's summarized source-value or dose error no longer poisons complete records. No warning, source record, medical value or confirmation is cleared by this gate. Actual source evidence, dose/unit/duration checks, current confirmations, associations, session ownership and revision gates still apply.

### Browser event races and calendar loss

Three frontend regressions were reproduced as failing tests before the fix:

1. A focus refresh during generation incremented the shared request epoch. The subsequent successful POST response was discarded as stale, while `adopt()` ignored the same-revision GET's course. An HTTP-successful schedule could therefore disappear from the UI.
2. A temporary failed focus refresh cleared all medicine cards and the valid calendar.
3. Starting a replacement generation cleared the valid calendar before any successful response.

Background refresh now does not supersede a pending generation. Temporary failures preserve the last valid view/preferences/calendar. Authentication expiry, revoked/stale workspace responses and actual source invalidation still clear private/stale state. A source change detected immediately before generation is adopted and no old-bound POST is sent. Older refresh completions cannot unset a newer refresh's busy state.

## What the reported clinical blockers mean

No HTTP status was inferred from the user's messages. In a synthetic reproduction, `TWICE DAILY` in literal source text versus `twice  daily` in a structured raw field was rejected by the existing exact-source extractor as `unsupported_source_value`; the frequency became null. Confirming the section did not make that missing field present. That is a real unresolved value, not an invented count to be filled by Scheduling.

The regression corrects this through the existing explicit instruction-review API to match the original source, confirms the corrected instruction and its current associations, and then generates the course. Extraction and literal-count parsing were not changed. Scheduling never reparses numeric notation or repairs missing clinical instructions.

Likewise, medicine confirmation does not truthfully resolve `needs_review=True`. The new additive `review_details` field reuses the same existing medicine review requirements to expose missing fields, unsupported source values and original confidence state. Scheduling shows those specific reasons on the incomplete medicine. Its correction link now points to medicine review rather than incorrectly pointing at an instruction-dose field. Low/unknown confidence, absent ingredients and other unresolved conditions are not silently cleared. Actual reasons for the user's particular records remain unverified without access to that browser state.

## Verification and actual browser limitations

- Backend full suite: **1,258 passed, 1 skipped, 13 subtests passed**.
- Frontend full suite: **254 passed**, 35 files.
- Production build: **passed**; existing large-chunk warning remains.
- Whitespace check: `git diff --check` passed, existing CRLF notices only.
- New authenticated tests run both through ASGI and through a real ephemeral loopback TCP/HTTP server using temporary local SQLite accounts, the actual reader/normalization/review/association/scheduling flow, synthetic PNG input and mocked Gemini responses. No external request, real image or credential is used.
- Before source correction: Dolo remains visible/excluded, Cetirizine and Omeprazole generate 3- and 7-day courses with one selected time each.
- After actual source-supported review: Dolo has two time inputs, the others one each. At 1 tablet twice daily for 5 days, 1 tablet once daily for 3 days and 1 capsule once daily for 7 days, the result has **10/3/7 administrations**, with each selected clock time and separate duration. There is no additional Scheduling confirmation.
- With a genuine Dolo medicine flag retained, only Dolo is excluded even after its count is established. Tests assert the flag remains true, the exact review diagnostics are returned, and no blocked medicine is included in generation.
- Tests also retain the current calendar after invalid replacement, restore a saved server course after remount, preserve entered preferences on focus, reject stale/cross-account operations and preserve global document hazards.

The real services were found listening on 8005 and 5177. Direct and Vite-proxied health both returned `confirmed-clock-schedule-v1`. HTTP inspection of the running Vite module confirmed the routed component is `ClockSchedule` and it serves the updated generation guard and review diagnostics. This is source/proxy evidence, **not browser interaction evidence**.

Actual Chrome verification could not be performed: the native computer-use runtime failed with `helper_read_acl_helper_spawn_failed`, and the browser connector returned `The browser access host is unavailable`. No browser cookies were requested/read, no browser authentication was automated, and no screenshot/recording was inspected. The user's precise saved clinical records and failed request status remain unknown. Do not claim their live browser session is fixed from these tests alone.

## Files changed in this task

- `medisaathi/ai_integration.py`: scope scheduling uncertainty correctly; preserve global hazards.
- `api/clock_scheduling.py`: additive existing review diagnostics and correct medicine-review destination.
- `api/tests/test_clock_browser_handoff.py`: new complete/partial authenticated ASGI/TCP regressions and hazard preservation.
- `frontend/src/pages/ClockSchedule.tsx`: fix focus/generation races, preserve valid results on transient failures, revoke on expiry/source changes, show precise existing review diagnostics.
- `frontend/src/pages/ClockSchedule.test.tsx`: seven new regressions for event races, diagnostics and genuine invalidation/expiry.
- `frontend/src/lib/clockScheduling.ts`: optional typed review diagnostics; no request or confirmation contract change.
- This report.

Prescription Analysis, Gemini extraction, the count parser, authentication/accounts, explanations, pricing, Lab Costs removal, Strip Expiry, translation files and themes were not changed. The original AI worktree, diagnostic guards and scheduling arithmetic engine were not touched. No commit, stage, push or merge.

## Load the backend fix and complete the manual check

The existing server was not stopped or restarted, to avoid discarding its current in-memory workspace. Restart it to ensure it loads the Python fix. This clears temporary prescriptions/schedules, while registered accounts remain in SQLite. Vite already serves the changed frontend; a browser reload may still be useful after the API restart.

In the API terminal press Ctrl+C, then:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

No OCR request occurs during startup. For the registered offline demonstration use `MEDISAATHI_LOCAL_OFFLINE='1'` instead; fixture mode is not evidence of live recognition. Tests do not invoke Gemini.

If restarting Vite is needed, in its terminal press Ctrl+C, then:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

At `http://localhost:5177`, sign in and use the existing review flow with fictional data. Open Scheduling, verify 2/1/1 time inputs for the established counts, choose the start date and four times, generate, then switch away/back and reload. A valid saved course should remain. With one genuinely incomplete medicine, complete medicines should still generate; inspect the excluded medicine's exact field diagnostics rather than reconfirming unchanged complete records. No new live Gemini request was made in this task.
