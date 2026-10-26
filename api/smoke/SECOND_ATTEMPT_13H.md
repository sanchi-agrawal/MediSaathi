# Milestone 13H: second diagnostic attempt prepared, execution disabled

**Preparation readiness: PASS. Execution authorization: NOT GRANTED.**

Attempt ID: `13h-20261026-b47e69c18a2f`

Model: `gemini-3.1-flash-lite`

Maximum physical provider requests for the entire attempt: **1**, including failed or timed-out sends.

Fixture: exact bytes of `api/smoke/fictional_demo.png`. This is the verified committed fictional prescription, not patient information. Its SHA-256 is registered in the prepared guard. Re-encoding/screenshotting the image does not qualify for this new attempt.

## Artifacts

Within `api/smoke/attempts/13h-20261026-b47e69c18a2f/`:

| File | Current state / purpose |
|---|---|
| `guard.json` | Created exclusively during preparation; immutable registered identity, fixture/model/call limit, checksum of original guard, and `execution_authorized: false` |
| `execution_authorization.json` | **Absent.** Must only be created after a separate explicit user authorization; no browser endpoint or CLI flag can create it |
| `consumed.json` | **Absent.** Exclusive, flushed/fsynced reservation immediately before the first permitted HTTP send; its existence permanently blocks another send |
| `diagnostic_result.json` | **Absent.** Atomic sanitized result written by the reservation owner only; no extracted records or provider bodies |

The original `api/smoke/live_result.json` is unchanged. The second attempt checks its registered checksum at startup and reservation; no route or launcher removes/resets either attempt's guard.

## One-call mechanism

The dedicated diagnostic context uses the existing reader's image validator, system prompt, response schema and `normalize_model_response`. It invokes the SDK once with no schema-validation retry loop. It does not globally patch the SDK or change `reader.read_prescription`; normal extraction and confirmation contracts are unchanged.

The installed/pinned SDK is given a dedicated synchronous HTTPX client with SDK retry attempts=1, HTTP transport retries=0, no redirects and no environment-proxy routing. Its transport accepts only the HTTPS POST generation endpoint for the registered model. Model-listing, other models, query-string endpoints and HTTP are refused without sending. Immediately before I/O, it revalidates authorization, fixture/original-guard registration and obtains an exclusive on-disk reservation. This protects the physical HTTP send across sessions, threads and processes even if code above it accidentally tries again. Timeouts/API errors consume the budget and have no retries or mock fallback.

`consumed.json` is never rewritten with results. Outcome writing is separate and atomic, so a crash or diagnostic-write failure cannot reopen the allowance. A competing rejected extractor cannot overwrite the reservation owner's result. Filesystem permissions/full disks can still prevent an outcome record; a successfully created reservation stays consumed. These guarantees assume the trusted local operator does not manually tamper with/remove guard artifacts and uses this launcher, not the normal unguarded API.

## Authorization boundary

The current user's scope is preparation and offline testing only. The production attempt directory contains no execution authorization. Import, preparation, status/page reruns and startup never send Gemini requests. The launcher refuses to start without a matching, unexpired authorization record.

Only after a **new explicit user instruction** should a trusted operator record:

- this exact attempt ID, model and fixture hash;
- `max_provider_calls: 1`, `execution_authorized: true`, `authorized_by: user`;
- an `authorization_reference` to that new instruction and an ISO timestamp `expires_at` with timezone.

Those are the exact allowed authorization fields; mismatches, extras, expired records or a consumed reservation are refused. This local file is an auditable operator gate, not production authentication or cryptographic proof of a human browser click. Do not create it based on this preparation request. The immutable prepared guard itself remains unchanged when a separately approved authorization is eventually added.

## Commands

Safe read-only check now (expected refusal/nonzero exit):

```powershell
cd C:/Users/ASHTAMI/MediSaathi-Frontend
api/.venv/Scripts/python.exe -m api.smoke.second_attempt --check
```

**Future launch only after separate execution authorization is recorded, and permission to replace the old server is given:**

```powershell
cd C:/Users/ASHTAMI/MediSaathi-Frontend
api/.venv/Scripts/python.exe -m api.smoke.second_attempt --credentials-file C:/Users/ASHTAMI/MediSaathi/medisaathi/.env
```

This command currently refuses to start. No server was started/stopped in 13H. Do not use the original `--mode live` launcher or `uvicorn api.main:app` for the second attempt; they do not implement this registered one-call context.

Frontend command for a future authorized session:

```powershell
cd C:/Users/ASHTAMI/MediSaathi-Frontend/frontend
npm.cmd run dev
```

After future authorization/startup, reload `http://localhost:5173/dashboard/analysis`, upload the exact registered PNG and click Analyze **once**. The new server retains real session/revision/review/confirmation handling, existing image limits and demo-only authentication. Keys load only into Python. Review/confirm/explain do not generate additional provider calls.

## Offline verification

**100 API tests / 891 combined Python tests passed**, including 34 new second-attempt tests. One non-failing Starlette test-client deprecation warning remains. The read-only launcher check correctly refused execution. The original guard checksum remains unchanged.

Tests use synthetic authorization files in temporary directories and HTTPX MockTransport with fake SDK credentials. They test actual installed SDK serialization without external network, API/transport errors, malformed responses without retry, exhaustion, concurrent threads/processes, process-exit persistence, failed reservation flush, endpoint restrictions, unchanged first guard, and startup/upload without SDK calls. No real authorization artifact, provider call, live server or consumed second reservation was created.

Exact 13H files:

- `api/smoke/second_attempt.py` (new diagnostic adapter/launcher)
- `api/tests/test_second_attempt.py` (new offline tests)
- `api/smoke/attempts/13h-20261026-b47e69c18a2f/guard.json` (new disabled registration)
- `api/.gitignore` (ignore future authorization, consumed guard and diagnostic runtime artifacts)
- `api/smoke/SECOND_ATTEMPT_13H.md` (this report)
