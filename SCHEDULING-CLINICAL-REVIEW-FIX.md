# Scheduling eligibility: current clinical review, not OCR completeness

This supersedes earlier reports describing every medicine `needs_review` flag as a scheduling blocker. Those reports reflected an overly broad policy: OCR completeness and scheduling readiness were conflated. No application redesign was performed.

## Exact conditions behind the messages

| Message | Condition before this correction |
| --- | --- |
| Missing fields: Printed ingredient | `api/medicine_review.requirements()` includes every null medicine OCR field except `needs_review`. `salt=None` therefore appears as a missing ingredient, independently of a current confirmed dosing instruction. |
| Values to verify: Written frequency / Written timing | The medicine's structured OCR field is not a literal substring of that medicine record's `raw_text` (numeric patterns have a separate formatting-aware check). This does not check the separately reviewed instruction line. |
| Values to verify: Duration in days | The medicine text does not contain the literal numeric duration followed by `day/days`. A brief medicine line can fail this even when a separate current confirmed instruction establishes duration. |
| Clarify and confirm the daily administration count | Clock preparation has neither current confirmed slots nor a stored confirmed-count capability. Count binding previously also required equality with the medicine OCR frequency and did not support the literal `once per day` / `twice per day` wording. Missing/unsafe current instructions legitimately produce the same blocker. |
| Resolve the medicine review flag | `prepare()` unconditionally added `medicine_review_flag` for `needs_review != False`; the clock count fallback also skipped these records. Separately, the adapter forwarded that OCR flag into the arithmetic engine, whose generic gate refused it. |
| Return to Prescription Review | The clock component renders this link when the API says a medicine is ineligible; it is not itself an automatic navigation action. The old blanket flag/count conditions caused unnecessary repeated prompts. |

The existing medicine flag-resolution action requires all eight verification fields, original confidence at least 0.8, no missing values and no unsupported OCR values. That full-record policy remains intact for its existing purpose. A missing printed ingredient or unknown original extraction confidence must not prevent a clinically complete, independently reviewed dosing plan from being scheduled.

No actual user session payload or HTTP error status was available. The code paths above were inspected directly and reproduced with synthetic source records. No HTTP status was inferred from screenshot text.

## Current scheduling requirements

Scheduling now requires:

1. Current authenticated workspace ownership, analysis and all relevant revisions.
2. Existing medicine review saved and genuinely confirmed, and independent instruction review saved and genuinely confirmed.
3. An existing, explicitly confirmed medicine–instruction association bound to those source revisions.
4. A current nonempty medicine name and supported form, explicit positive dose quantity and compatible unit.
5. Source-supported instruction duration agreeing with the current reviewed medicine duration.
6. Current confirmed named slots or a source-supported explicit literal daily-count capability created during association. `once per day` and `twice per day` are supported literally. Numeric notation is not parsed by Scheduling.
7. No actual unsafe instruction or document-wide hazard. Variable/tapering/conditional instructions, unsafe source values, ambiguous quantities, incompatible units and missing clinical details remain blocked.
8. Valid start date and exactly the prescribed number of distinct valid clock times. Output dates, amounts, units and totals are strictly revalidated.

The independently reviewed linked instruction is the authoritative prescribing source. A stale medicine OCR `frequency_pattern` is no longer a second frequency authority overriding that instruction. Source values still must occur literally in the instruction; missing values or unsupported words do not create counts.

No new confirmation exists in Scheduling. The existing generation endpoint performs the genuine server-side approval internally after validation. Complete medicines can generate independently of incomplete medicines.

## Original records and engine boundary

The original ten medicine fields, `salt=None`, original confidence and `needs_review=True` remain unchanged. No ingredient is fabricated and no source flag is cleared. The full medicine-review resolution rules were not weakened or bypassed to label a record resolved.

After AIIntegration validates the current confirmed clinical handoff, the existing adapter builds a **separate engine input DTO** containing only name, form, validated duration, dose and unit plus the engine's confirmation/readiness fields. Its readiness refers to that clinical plan, not the OCR record. The arithmetic engine's original code and generic confirmation gate remain unchanged. Both the source handoff record and all archived original OCR metadata remain separate and unchanged, verified after generation in regression tests.

Original OCR diagnostics remain available in a collapsible technical-details section on eligible medicine cards. They no longer produce a false scheduling blocker or a correction link on an eligible medicine. Incomplete medicines still show actual blocking reasons and retain existing review links. Existing English/Hindi labels and theme tokens are reused.

## Regression evidence

New tests use the actual local-account app factory, temporary SQLite accounts, real extraction normalization and API reviews with mocked Gemini output. Both ASGI and real loopback TCP/HTTP transports are exercised; external requests are forbidden.

Synthetic source:

- Dolo 650: 1 tablet, twice per day, 5 days, After food.
- Cetirizine 10 mg: 1 tablet, once per day, 3 days.
- Omeprazole 20 mg: 1 capsule, once per day, 7 days.

The initial medicine OCR has `needs_review=True`, absent ingredient/confidence, a brief medicine-only source line, stale `BD`/timing metadata and an incorrect duration. The existing review API saves corrected durations, the user confirms medicines, independently reviews/confirms instructions and confirms their links. Scheduling then exposes 2/1/1 daily administrations and generates **10/3/7 administrations** over **5/3/7 days** at the user-selected times. Original OCR records remain byte-for-byte equivalent as JSON; current medicine flags remain true and ingredients remain null.

Negative cases retain a missing dose or an unestablished count for Dolo. Dolo is excluded; Cetirizine and Omeprazole still generate. No default dose or count is invented. Editing/invalidation of instructions revokes the course and eligibility. Existing cross-session, stale-revision, clock-input, clinical-warning and global-hazard tests remain active.

The previous blanket-flag regression expectations were updated to this corrected policy. They were not simply removed: the original flag must remain preserved, and genuine incomplete-dose/count cases must remain blocked.

Results:

- Full Python suite: **1,264 passed, 1 skipped, 13 subtests passed**.
- Full frontend suite: **255 passed**, 35 files.
- Production build: **passed**, existing large-chunk warning only.
- Final six exact-case ASGI/TCP regressions, including health marker: **6 passed**.
- `git diff --check`: passed, existing CRLF notices only.

Actual Chrome interactions were not verified. Browser access failed in the preceding investigation (`helper_read_acl_helper_spawn_failed`; browser access host unavailable). This report does not claim a human-browser fix was observed. No live Gemini/Telegram request was made.

## Files changed in this correction

- `api/downstream/automatic.py`
- `api/downstream/scheduling.py`
- `api/clock_scheduling.py`
- `api/main.py` (safe loaded-policy marker)
- `medisaathi/confirmed_count.py`
- `medisaathi/ai_integration.py` (reject missing medicine identity at handoff)
- `api/tests/test_scheduling_review_scope.py` (new)
- `api/tests/test_clock_browser_handoff.py`
- `api/tests/test_patient_explanations.py` (scheduling assertions only)
- `api/tests/test_downstream.py`
- `frontend/src/pages/ClockSchedule.tsx`
- `frontend/src/pages/ClockSchedule.test.tsx`
- `frontend/src/lib/confirmedWorkflowHindi.ts` (missing-name label)
- This report.

Prescription Analysis layout and review controls, medicine explanations, Market Pricing, Lab Costs removal, Strip Expiry, authentication/database, original AI worktree, Gemini extraction/configuration, arithmetic scheduling engine, theme architecture and translation architecture were not modified. No commit, stage, push, merge, reset or clean.

## Load this specific fix

The API must load the newly changed Python code. The existing process was not forcibly stopped, to preserve its current temporary workspace. Restarting clears temporary prescriptions/schedules, but retains local registered accounts.

In the API terminal, Ctrl+C, then:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

Verify this correction, not merely the older clock API contract:

```powershell
(Invoke-RestMethod http://127.0.0.1:8005/api/health).scheduling_eligibility_policy
# confirmed-clinical-fields-v2
```

Frontend, if not already running:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Open `http://localhost:5177`, sign in and use fictional data in the unchanged review workflow. A missing ingredient may remain an OCR warning while current confirmed prescribing data produces schedule inputs. If dose, duration or count truly remains absent in the reviewed instruction, that medicine must still be excluded. No startup request invokes Gemini.
