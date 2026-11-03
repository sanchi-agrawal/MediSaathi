# Canonical named-slot medicine scheduling

## What was repaired

The old application interpreted frequency text in review, revalidated it during plan preparation, and then asked the arithmetic engine to parse it again. One existing regression reproduced a real contradiction: confirmed **noon and night** with BD passed the AI source gate, but the engine reinterpreted BD as **morning and night**, causing the adapter to reject the result. Spaced notation and source/field spelling differences compounded that design problem.

The application now stores revision-bound named slots on the confirmed medicine–instruction link:

```json
{"Dolo":["morning","night"],"Cetirizine":["night"],"Omeprazole":["morning"]}
```

Numeric transcription remains a review proposal until its named meaning is explicitly acknowledged. After acknowledgement, current-state reads, plan preparation, approval and arithmetic use the stored names. Original frequency text, dose/unit, duration and food timing remain separate and unchanged.

## Single interpretation layer and API handoff

`medisaathi/confirmed_frequency.py:timing_proposal` is the shared review-layer interpretation function. It recognizes the seven binary triples under the explicitly acknowledged morning–afternoon–night convention, and supported literal named timing in confirmed source text. It does not infer quantity or clock times. Unsafe/ambiguous patterns, source conflicts, ranges and missing timing remain blocked.

`POST /api/prescriptions/{analysis_id}/schedule/slots/confirm` receives the current medicine/instruction/scheduling revisions, association ID and displayed named slot list. It checks current independent scope confirmations and rejects lists that differ from the source-backed proposal. The backend creates a one-use, source-bound acknowledgement event and stores `confirmed_slots` privately on that current AIIntegration link. No browser approval boolean or model field can authorize scheduling.

The current scheduling response adds `timing_contract: confirmed-named-slots-v1`. Each automatic entry has `proposed_slots` and `confirmed_slots`, alongside its existing clinical template and blockers. Confirmed names are authoritative; the source pattern is not parsed again during schedule generation. Source edits clear links/slot confirmations/results through existing scope/revision invalidation.

The public plan contract remains compatible (`administrations_by_slot` uses morning/noon/night/bedtime). The adapter maps canonical `afternoon` to legacy `noon` exactly once and verifies agreement between the plan and confirmed names. The private handoff carries `confirmed_slots` outside the strict ten-field medicine record.

`build_schedule(medicine, start_date, confirmed_slots=None)` adds a backward-compatible optional named-slot input to the existing engine. The application always supplies it. This branch validates slot names, explicit quantity/unit, confirmation, review flags and duration, and then uses the existing date/refill arithmetic. It never reads/parses the frequency string. Existing callers that omit the third argument retain their legacy string behavior; the React/FastAPI path does not fall back to that behavior.

The older `/schedule/notation/confirm` endpoint remains a compatibility wrapper that stores the same canonical names. It is not a separate downstream frequency validator. For legacy literal-English timing, independent instruction review plus the genuine association action accepts the explicit named source timing; abbreviations alone never establish slots. Numeric conventions still require a separate explicit acknowledgement.

## Patient interface

Prescription Review shows original frequency text and backend-proposed **named** times. The user checks them against the source and clicks **Confirm named timing slots**. The frontend submits the actual proposal list and re-fetches/compares the persisted names before reporting success. The frontend no longer parses numeric notation to draw the acknowledgement.

Scheduling displays confirmed named times, medicine, dose/unit, original frequency, food timing and duration in read-only cards. The only new required scheduling input is start date. Calendar output uses morning/afternoon/night/bedtime labels; no hours are invented. Existing optional reminder clock preferences remain a separate collapsed step and no notifications are enabled. English/Hindi and existing dark/light tokens are preserved.

## Verification and remaining limitations

- **1,192 backend tests passed**, one skipped, 13 subtests passed.
- **212 frontend tests passed**, and production build passed. The existing bundle-size warning remains.
- The synthetic three-medicine API regression confirms both independent scopes, associates all three records, confirms named slots and generates five-, three- and seven-day courses from a single start date. It explicitly replaces both the review frequency parser and engine parser with failing functions **after confirmation**; generation still succeeds, proving no downstream reparse.
- A real loopback HTTP smoke passed with local authentication, an isolated temporary account DB and mocked SDK responses: source-supported review resolution; persisted named slots; all three date-only schedules; strip-workflow isolation; logout and session rejection. It checks the new API contract and also disables downstream frequency parsing. Its four SDK calls were mocked; no live Gemini/Telegram request was made.
- Instruction edits revoke all affected scope bindings and schedules; stale IDs/revisions and forged slot lists are rejected. Bedtime cannot be added through a three-slot convention. Dose/unit and review flags are never defaulted or cleared by the scheduler.

**Actual browser reproduction was not completed.** The computer-use skill was initialized and the running browser was selected from the returned inventory, but Windows Computer Use stopped before returning its contents because it could not determine the browser URL confidently enough to enforce policy. No browser input or medical action was performed, and no alternative automation was used to bypass that stop. Consequently, the user's exact live prescription records and every clinical blocker in that authenticated workspace were not inspected. Passing HTTP/jsdom tests is not reported as browser success.

The live API and Vite proxy both returned HTTP 200 for `/api/health`, reported Gemini configuration present, and reported `pattern-format-review-v1` but **no named_slot_contract** at final inspection. Thus the active process does not yet run this new implementation. It was not restarted because doing so discards its temporary prescription workspace. Your current account DB, datasets, original worktrees and active medical workspace were left untouched.

Remaining blockers are real clinical requirements: unresolved review flags, missing/unsupported dose/unit/duration, unconfirmed scopes/association/timing, ambiguous source or stale revisions. The existing per-field review-resolution rules are unchanged; original OCR metadata and unknown confidence cannot be invented or cleared to force a schedule. All selected course records must be ready before the existing Generate action proceeds. Source edits conservatively revoke the prescription's linked schedules rather than retaining approvals for changed scope fingerprints. Multi-medicine generation remains sequential, not transactional. Durable medical storage and exact-clock inference are not introduced.

## Load and manually verify

When ready, stop the existing API with Ctrl+C and restart it using the commands in SCHEDULING-STRIP-INTEGRATION.md. This change has not stopped it. Startup makes no provider call, but a restart clears temporary prescription state.

```powershell
(Invoke-RestMethod http://127.0.0.1:8005/api/health).named_slot_contract
# expected: confirmed-named-slots-v1
```

Open `http://localhost:5177`, review/confirm the current source records, resolve only eligible genuine review requirements, confirm each association and its proposed named timing, navigate to Schedule, choose the start date and generate. Check Dolo morning/night (5 days), Cetirizine night (3), Omeprazole morning (7). Navigate away/back and verify the source-bound names remain. Edit an instruction and confirm that its old scheduling approval is withheld. If a real OCR request is needed, it remains a deliberate user action with available credentials/quota, not an automatic verification step.

## Exact source changes

- `medisaathi/confirmed_frequency.py`: shared review timing proposals and named-to-engine slot mapping.
- `medisaathi/ai_integration.py`: trusted named-slot acknowledgement, private source-bound canonical storage, and a slot-only scheduling gate.
- `medisaathi/schedule.py`: optional confirmed-slot branch using unchanged quantity/date/refill rules; legacy calls preserved.
- `api/downstream/models.py`: strict named-slot confirmation request.
- `api/downstream_routes.py`: confirmation endpoint and current-state timing contract.
- `api/downstream/automatic.py`: readiness/templates built from current confirmed names; proposals only when timing is not yet confirmed.
- `api/downstream/scheduling.py`: strict named-slot handoff to the engine.
- `api/main.py`: presence-only named-slot contract marker.
- `api/tests/test_named_slot_workflow.py`: full three-medicine workflow, no-reparse proof, invalid-slot and unresolved-input tests.
- `api/tests/test_downstream.py`: explicit noon/night regression now verifies the intended schedule rather than engine disagreement.
- `frontend/src/components/ScheduleAssociations.tsx`: named proposals, explicit approval, persisted-name verification.
- `frontend/src/components/ScheduleAssociations.test.tsx`: canonical named-list request/response tests and compatibility coverage.
- `frontend/src/pages/Schedule.tsx`: read-only confirmed names and afternoon display mapping.
- `frontend/src/lib/scheduling.ts`: typed named-slot transport, validation and compatibility interface; frontend frequency parser removed.
- `frontend/src/lib/scheduling.test.ts`: named-list wire contract tests.
- `frontend/src/lib/namedSlotsHindi.ts`: new English/Hindi interface copy.
- `frontend/src/lib/language.ts`: bilingual catalogue integration.
- `NAMED-SLOTS-SCHEDULING.md`: current behavior, evidence and limitations.

Ignored editing/HTTP-smoke helpers remain under `api/.venv`. No dependencies were installed. No authentication or account DB implementation, prescription OCR contract, strip parser, pricing implementation or diagnostic guard was changed. No files were staged, committed or pushed.
