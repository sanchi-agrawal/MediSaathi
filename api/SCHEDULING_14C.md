# Milestone 14C: guarded medication scheduling

Implemented on `feature/scheduling-integration`, created from clean checkpoint `40ab046`. No merge, staging, commit, push, provider request or original AI worktree edit was performed. Person 3's app.py, schedule.py and confirm_utils.py and all original AI modules remain unchanged.

## Journey and authority

Extract medicines and instructions explicitly, review/save/confirm each section independently, open `/dashboard/schedule`, select and explicitly associate one medicine and instruction, enter the values supported by the source, save the plan for review, acknowledge it, then separately choose **Approve & generate schedule**.

The normal API factory injects `schedule_handoff` into each session's AIIntegration. The callback invokes unchanged `schedule.build_schedule`. Temporary engine input adds confirmed/dose fields to a copy only; the original ten-field records and separate instruction envelopes remain intact. It never clears the original needs_review flag or infers a dose from strength.

Saving a plan validates its shape and calendar date; it does not assert that the source supports the plan or call the engine. Approval registers a one-use server-owned event for the exact stored association/plan and calls AIIntegration.schedule, which checks both confirmed source snapshots and explicit source semantics. No browser event tokens, confirmation claims or replacement plan are accepted at approval.

The adapter converts ISO strings to date and mL to engine ml only at its boundary. It strictly validates engine output and checks slots, per-day/course quantities, units, duration and calculated dates against the approved plan. These checks validate Person 3 output; they do not supply substitute schedules. HTTP output is independently validated, including injected callbacks. Malformed/inconsistent output or engine exceptions cannot produce a successful schedule.

## Routes and contracts

All mutation routes retain exact-Origin/custom-header CSRF protection and the existing Secure/HttpOnly/SameSite=Strict session cookie. No account authentication has been added.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /api/scheduling/current | Current session source context, revisions, active association/plan/result |
| POST | /api/prescriptions/{id}/associations | Explicit medicine_ref/instruction_id association |
| DELETE | /api/prescriptions/{id}/associations | Remove association, approval and results |
| POST | /api/prescriptions/{id}/schedule/invalidate | Remove the saved plan/API approval/result while retaining the association |
| PUT | /api/prescriptions/{id}/schedule/review | Save exact plan inputs, without generation |
| POST | /api/prescriptions/{id}/schedule/approve | Separately approve the stored plan and run the engine |

Mutation bodies require `medicine_revision`, `instruction_revision`, `scheduling_revision`. Linked plan actions additionally require the server-issued `association_id`. Association requests add only `medicine_ref` (e.g. medicine_001, bound to the current medicine order) and `instruction_id`. Review adds only:

```json
{
  "dose_quantity": 1,
  "dose_unit": "tablet",
  "duration_days": 3,
  "administrations_by_slot": {"morning": 1, "noon": 0, "night": 1, "bedtime": 0},
  "start_date": "2026-10-27"
}
```

This is a fictional example, not prescribing guidance. Approve contains no plan or approved boolean: only the current revisions and association ID. Extra fields, wrong types, nonfinite quantities, stale IDs/revisions and cross-session requests are rejected. A successful response carries the source context and `{derived_id, payload}`; payload includes validated doses_by_slot, units_per_day, total_units, unit, duration_days, start_date, end_date and nullable refill_date. Refusals contain status/reason with no calculated fields. States are blocked, ready, associated, reviewed, succeeded, needs_input and failed. Unavailable integrations return 503; source safety errors 422, stale/current-confirmation errors 409 and engine failures 502. No automatic retry is made.

## Invalidation and isolation

Both API confirmation metadata and AIIntegration confirmation bindings must be current on every downstream mutation and result read. Medicine invalidation/review/analyze/clear and instruction invalidation/review/analyze clear associations, plan approval and results through public AIIntegration.clear_associations as well as API state. Prescription replacement clears both relevant scopes. Investigation and strip changes remain independent. One selected association/plan is active per demo session; associating another pair removes the previous result. This is not a durable multi-medicine schedule database.

Plan-only edits remove API approval/results and rotate scheduling_revision immediately. Old internal AI derived objects can remain in RAM until regeneration/source invalidation, because the original module has no public plan-only revocation method. No route reads/exposes them, and notification/pricing/reminder callbacks are not configured. Future downstream integrations must use these API gates rather than bypassing them through a private derived ID. This preserves the existing AI contract without private-state mutation.

The frontend hides results immediately on plan/selection changes and source invalidation notices, discards late responses by generation, and refreshes current authority on focus/visibility changes. Cross-tab notices carry only a constant invalidation message, no medical information or IDs. They are best-effort when browser isolation disables BroadcastChannel; server gates reject stale requests regardless. Previously delivered responses/screenshots cannot be recalled. No medical values are persisted in localStorage.

## Supported and unsupported cases

The existing AI gate admits only source-backed simple decimal doses, exact tablet/capsule/mL/drop units matching form, integer day durations consistent across records, supported BD/BID/TDS/TID/QID/HS and literal English named slots. The engine's calculated slots must also match; a source specifying BD noon/night is rejected when the engine calculates morning/night.

Numeric frequency patterns, OD, PRN/SOS, slash/unicode fractions, ranges, weeks/months, tapers/variable doses, clock-to-slot conversion, missing/conflicting fields and unsafe uncertainty flags remain blocked. Some decimal quantities can be supported even though fractional notation is not. Durations are limited to 1–365 days and dose quantity to 1000 by the engine boundary. Empty extraction creates no schedule. Medicines still marked needs_review by the extractor are refused by the unchanged engine, even after section acknowledgement. The React review flow does not clear that evidence flag; supporting a separate resolution workflow needs explicit contract coordination, not silent flag removal.

No notification delivery, automatic reminder, inventory, pricing or matching integration is enabled. Refill planning uses the engine's current >=30-day/three-days-before-end policy, not actual stock or a clinically individualized recommendation. Demo sessions remain RAM-only, single-process and expiring; guarded smoke/diagnostic capabilities remain medicines-only and cannot access scheduling.

## Offline verification

- 975 Python tests passed (926 checkpoint tests plus 49 scheduling API/adapter cases).
- 53 frontend tests passed (39 checkpoint tests plus 14 scheduling/client/invalidation cases).
- TypeScript and Vite production build passed.
- One existing Starlette test-client deprecation warning remains.
- No Gemini calls or real browser/visual verification were performed.

## Manual browser verification

Use the normal configured API, not an old guarded diagnostic server. Starting the API never triggers extraction. Do not reuse/reset consumed guards. Tests use fictional injected extractors; a fresh real OCR operation requires its own explicit authorization and may have provider cost.

```powershell
# Repository root; existing server-only configuration, no key in frontend
api/.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
# Separate terminal, frontend directory
npm.cmd run dev
```

1. Open http://localhost:5173/dashboard/analysis. Use a current independently confirmed fictional medicines/instructions session, if available. A server restart loses in-memory sessions; do not trigger fresh OCR without authorization just to seed this test.
2. Open `/dashboard/schedule`. Check missing-session/unconfirmed/empty states first; verify no schedule generation occurs on load, refresh or selections.
3. Explicitly associate matching source records. Review the original text and uncertainty flags. Enter only values actually supported by that source, select the exact written slots and choose a start date.
4. Save, inspect saved inputs, acknowledge and approve once. Verify actual engine quantities, start/end dates, and nullable refill planning date. A source that is unsupported or still marked needs_review must produce no schedule.
5. Change a plan input, then a selected record: results must disappear and generation must require renewed review/approval. Edit either confirmed source section in another tab; verify invalidation notices and server rejection of stale approval/result access.
6. Check mobile layout, keyboard-only selection/approval, focus return, cookie behavior, and that errors never show a successful schedule. Notification delivery must remain absent.

## Exact files changed

Modified: api/main.py, api/sessions.py, api/section_routes.py, api/README.md, frontend/README.md, frontend/src/App.tsx, frontend/src/lib/prescriptions.ts, frontend/src/lib/sections.ts.

Created: api/downstream/__init__.py, api/downstream/models.py, api/downstream/scheduling.py, api/downstream_routes.py, api/tests/test_downstream.py, api/SCHEDULING_14C.md, frontend/src/lib/scheduling.ts, frontend/src/lib/scheduling.test.ts, frontend/src/lib/workflowEvents.ts, frontend/src/lib/workflowEvents.test.ts, frontend/src/pages/Schedule.tsx, frontend/src/pages/Schedule.test.tsx, frontend/src/schedule.css.

Build output, test temporary directories and caches are ignored. Original attempt guards/authorizations/results remain unchanged. No files are staged or committed in this milestone.
