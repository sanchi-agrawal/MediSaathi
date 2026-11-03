# Milestone 13G diagnostic readiness audit

**Overall: FAIL for another live attempt.** Diagnostic classification and persistence pass offline. An unconditional no-second-provider-call guarantee and a separately authorized new attempt launcher are not implemented. Neither is silently enabled by this audit.

## Verified behavior

| Check | Result |
|---|---|
| Actual reader wrapping of mocked Google SDK ClientError/ServerError | PASS: safe numeric status survives suppressed context |
| 400 / 401 / 403 / 404 / 422 / 429 / 500 / 503 | PASS: bad-request, authentication, permission, model-or-resource, other client, quota/rate, server categories |
| ReadTimeout / ConnectError | PASS: transport category without claiming a provider response |
| Both cause/context branches and outer transport wrappers | PASS: captured provider status takes precedence over generic transport |
| HTTPStatusError with a real synthetic response object | PASS: numeric response status is retained without body/header/URL logging |
| Persistence across normal process exit | PASS: subprocess runs the actual reader/API path with a mocked SDK; parent reads safe status 503 after exit |
| Failed atomic report replacement | PASS: original consumed guard remains byte-for-byte intact |
| Existing consumed original guard | PASS: public live launcher still refuses it; original file is unchanged |
| SDK automatic API/transport-error retries | PASS: attempts=1; one mocked generate_content call for every tested API/transport failure |
| No automatic second generate_content under any outcome | FAIL: the unchanged reader allows one retry after invalid response normalization |
| Separate explicitly authorized new live attempt | NOT ENABLED: existing CLI has only the original guard; proposal below requires later explicit authorization |

## Changes

`diagnostics.py` now traverses both exception branches with a 16-object bound, recognizes Google SDK client/server subclasses and HTTPStatusError, preserves an available provider status across wrappers, and distinguishes other 4xx client errors. It never serializes exception messages, arbitrary provider enums, bodies, headers, request URLs, cookies, image bytes or credentials.

`persistence.py` writes same-directory temporary output, flushes/fsyncs it, and atomically replaces the consumed result marker. The initial exclusive guard reservation is also flushed/fsynced before reader entry. This verifies normal process-exit persistence and failure-closed replacement, not a universal power-loss guarantee for every OS/filesystem. Disk-full/permission failures can still prevent a final diagnostic report; the already-created guard remains consumed.

The report cannot recreate the first attempt's discarded upstream exception. The running server was not restarted or hot-reloaded; its original analysis/session state remains untouched. Code changes apply only when a future process is deliberately launched.

## Retry finding

The installed Google SDK honors `HttpRetryOptions(attempts=1)` as one total attempt. Reader tests with synthetic API errors and network/timeouts prove there is no reader-level retry for these failures. The reader separately loops up to twice after invalid JSON/schema normalization. An offline test explicitly detects this existing second model invocation. It is part of the preserved medical extraction contract and was not removed. A later authorization must either explicitly allow this narrow retry or coordinate a separate diagnostic-only hard provider-call cap; no unqualified no-retry claim is valid now.

## Configuration boundary

The existing smoke loader reads only the two Gemini settings into the Python process, then uses `reader._configuration`. Tests supply fictional environment values and a fake SDK, never real credentials. Frontend requests contain uploaded image bytes, session-cookie credentials and revisions; Gemini keys are not included. Configuration presence does not establish quota/model access. No Gemini model-listing/generate-content/network call was made during this audit.

## Proposed procedure — requires separate explicit authorization

1. Leave `api/smoke/live_result.json` immutable and retain its checksum. Do not delete, rename, replace or reuse it to gain a request.
2. Obtain a user-authored authorization identifying a unique attempt ID, verified fictional fixture hash, selected model, maximum physical provider calls, permitted retry behavior, expiry and who will trigger the browser action. Persist only that non-secret authorization metadata. The authorization is not supplied by arbitrary browser JSON.
3. Implement and offline-test a dedicated launcher for that ID. It must refuse missing/expired/ambiguous authorization, fixture/model mismatch, an existing new reservation, and a different guard path than its registered attempt. The original guard stays untouched. No new launcher/authorization artifact exists from this milestone.
4. Allocate a new exclusive guard and atomic result artifact scoped to that authorization. Reserve and fsync it before any provider call; share the allowance across sessions/processes. If max physical calls is one, explicitly resolve the reader's schema retry before launch. Do not change extraction/confirmation contracts without coordination.
5. After explicit approval to replace the current process, launch the diagnostic-enabled backend without reloader/workers or startup provider calls. Keep keys server-side and cookie/medical-review safeguards unchanged. Readiness/status may expose non-secret mode/attempt metadata only.
6. The authorized user clicks Analyze once in Chrome. Persist the safe diagnostic outcome; stop on failure. No Retry, automatic API fallback, or marker removal. Preserve the original and new artifacts for review.

This proposal is not authorization, does not create a fresh allowance, and does not make another live request justified automatically.

## Exact files changed in 13G

Offline verification: **66 API tests and 857 combined Python tests passed**. One non-failing Starlette test-client deprecation warning remains. The original consumed guard checksum is unchanged. No frontend implementation changed, so frontend checks were not repeated.

- `api/smoke/diagnostics.py`
- `api/smoke/persistence.py` (new)
- `api/smoke/server.py`
- `api/tests/test_diagnostic_readiness.py` (new)
- `api/.gitignore`
- `api/smoke/READINESS_13G.md` (this file)

No reader, medical normalization, AIIntegration, confirmation, teammate, frontend, secret or original guard file was changed. No reset, commit, merge, push or external provider request occurred.
