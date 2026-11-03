# Milestone 14D: scheduling browser diagnostics and error reporting

## Confirmed findings and limits

The generic `api_error: Scheduling failed.` originates in the scheduling TypeScript client's fallback for a non-success HTTP response without `{detail: {category, message}}`. FastAPI's default 404/405 bodies have string detail, so the previous client dropped the numeric status and replaced the useful error with that generic message. A non-JSON failure similarly discarded its HTTP category. Regression tests reproduce these cases. Arbitrary response bodies are never echoed.

The earlier browser request's Network status/body was not retained in the available diagnostics. Its original HTTP status and failed action remain unconfirmed; a historical 404, stale backend, cookie issue, provider issue or engine failure must not be asserted as fact from the generic text. Before this fix, sessionless probes of the running normal API and Vite proxy both returned the correctly structured 401/session_expired. The scheduling route already existed; no current missing-route fault was reproduced.

Fictional, independently reviewed/confirmed records pass the actual association, saved-plan and approval endpoints and unchanged schedule engine, producing 6 tablets over 3 days with an end date of 2026-10-29. This also works with Gemini configuration deliberately absent when the extractors are mocked. No clinical adapter, saved-review, association or revision defect was reproduced, so none of those contracts was changed.

## Fixes

- Preserve typed server errors such as unsafe_schedule, stale_result and confirmation_required.
- Classify unstructured HTTP errors safely: api_route_unavailable (404/405), session_expired (401), origin_rejected (403), request_conflict (409), invalid_input (422), rate_limited (429), backend_unavailable (5xx), or api_http_error. Include numeric HTTP status and useful recovery guidance. Never echo provider/HTML/medical response bodies, retry automatically, or show success after failure.
- Add presence-only local health fields: api_contract=medisaathi-14d, scheduling_contract=review-approve-v1 (or null on restricted diagnostic servers), gemini_configured boolean. Reading configuration never constructs a provider client or requests a model.
- Restart the identified normal API using the tested api/.venv interpreter, existing original-worktree environment file read server-side only, and access logging disabled. No credentials were printed, copied to frontend or committed. This restart discarded the old RAM-only demo sessions.

The original normal process was a non-reloading Miniforge uvicorn process without --env-file. Its inherited environment was not inspected, so its previous credential presence cannot be proved. The local adjacent medisaathi/.env is absent; the original AI workspace's existing .env contains both settings. The restarted actual API reports gemini_configured=true. This establishes presence, not valid quota, model access or successful OCR.

## Runtime verification

Normal API: http://127.0.0.1:8000. Normal frontend: http://localhost:5173.

GET /api/health through each endpoint returns medisaathi-14d, review-approve-v1, gemini_configured=true and all four extraction scopes. Sessionless GET /api/scheduling/current returns 401/session_expired, as expected. No cookies or patient data were sent/read in these probes.

The current normal launch command, from repository root, is:

```powershell
api/.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --env-file C:/Users/ASHTAMI/MediSaathi/medisaathi/.env --no-access-log
```

It is already running. Do not launch another process on that port. Restarting loses demo sessions; do not reset any consumed diagnostic guard. Startup and health checks never call Gemini. Do not click Analyze on the normal frontend as part of this no-provider milestone.

## Exact no-Gemini browser procedure

A local, ignored diagnostic harness is available separately, with a conspicuous OFFLINE FICTIONAL TEST banner, fixed fictional extractor outputs, PNG hash restriction and a blocked provider client. It uses unchanged production review, confirmation, association and schedule routes. The normal API/frontend do not silently switch to mocks. A separate medisaathi_fixture_14d cookie preserves Secure/HttpOnly/SameSite/Path attributes and avoids clobbering the normal localhost demo cookie (cookies are not port-scoped).

The harness is running at http://localhost:5174; its API is on 127.0.0.1:8001. The HTML banner and proxy were verified over HTTP; actual browser rendering/cookie acceptance/user interaction are still pending. Its full in-process --check workflow passed with the provider client blocked.

1. Open **http://localhost:5174/dashboard/analysis**, not port 5173. Verify the visible mocked-OCR banner before continuing.
2. Upload exactly `C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\14d-fictional-scheduling.png`. This is a newly generated fictional text image containing no patient information. Other images are rejected by the fixture server.
3. Select medicines and dosage instructions. Click Analyze with AI once. In this labelled harness it calls only the fixed mock extractors, never Gemini. It should show Fictional-A and `1 tablet BD morning and night for 3 days`.
4. Save the medicines review, acknowledge its values/unknowns and explicitly confirm medicines. Separately save, acknowledge and confirm the instruction section. Keep this tab open.
5. Open **http://localhost:5174/dashboard/schedule** in a second tab. Explicitly choose the Fictional-A medicine and instruction_001, then choose Associate selected records.
6. Enter dose quantity 1, unit tablet, duration 3 days, start date 2026-10-27. Check morning and night only. Save the plan. No schedule should yet appear.
7. Acknowledge the saved inputs and choose Approve & generate schedule. Expect morning=1, noon=0, night=1, bedtime=0 tablet; per day=2; total=6; start=2026-10-27; end=2026-10-29; refill date not calculated. No notification is sent.
8. Change a plan input: the result must disappear immediately. Saving a duration of 4 then approving must fail with unsafe_schedule, because the source says 3. Refresh current state, correct it, save and approve again to recover; never manufacture source values.
9. In the original Analysis tab, edit a confirmed medicine or instruction. The Schedule tab must hide its result; stale approvals must be rejected. No automatic association or generation should occur.
10. Check Chrome's Network panel for HTTP status/category if anything fails. Report only method, route template, numeric status and safe error category, not request/response medical content, cookies or credentials.

If a fixture cookie is not accepted on HTTP localhost, use trusted local HTTPS rather than disabling Secure. No real authentication, notifications or live OCR are established by this fixture.

To restart the offline harness only, stop its existing fixture processes first and use separate terminals from repository root:

```powershell
api/.venv/Scripts/python.exe -u api/.venv/14d_browser_fixture.py
node frontend/node_modules/vite/bin/vite.js --config api/.venv/14d-vite.config.mjs --host localhost
```

These helper files are intentionally local/ignored diagnostics under api/.venv, not deployable product modules or a second OCR pipeline. Their test check command is `api/.venv/Scripts/python.exe api/.venv/14d_browser_fixture.py --check`.

## Verification and exact files

- 979 offline Python tests passed; one existing Starlette test-client deprecation warning.
- 64 frontend tests passed; TypeScript/Vite production build passed.
- Fictional full-flow harness check passed, with provider construction blocked.
- Normal and fixture proxy/health checks passed. No browser automation, human-browser verification or Gemini request was performed by the agent.
- All medisaathi files, original AI worktree and five existing guard/authorization/result artifacts remain unchanged. Index remains empty; no commit, merge or push.

Product/test/documentation files changed in 14D (on top of the uncommitted 14C work):

- api/main.py
- api/tests/test_browser_readiness.py (new)
- api/BROWSER_14D.md (new)
- api/README.md
- frontend/src/lib/scheduling.ts
- frontend/src/lib/scheduling.test.ts

Ignored local diagnostics: api/.venv/14d_configuration.py, 14d_probe.py, 14d_verify_runtime.py, 14d_browser_fixture.py, 14d-vite.config.mjs, 14d-fictional-scheduling.png, and normal API stdout/stderr logs. No new execution authorization or provider guard was created.
