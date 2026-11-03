# Scheduling: independent courses and preserved clock preferences

## Findings

The currently routed Scheduling component is `ClockSchedule`, not the older `Schedule` or `UnifiedSchedule`. It does not contain association selectors or approval controls. The backend already retrieves genuine AIIntegration associations and stored confirmed slots/daily counts; generation does not parse numeric frequency notation. A genuine unresolved medicine review flag still correctly excludes that medicine. These checks must not be removed to make incomplete data actionable.

A remaining reproduced UI defect was `adopt()` clearing the start date and all unsaved clock preferences on every server refresh, including window focus. It now preserves preferences when analysis and all three revision bindings are unchanged. Source invalidation/replacement clears them. An invalid replacement schedule request also used to delete the saved calendar before input validation; it now preserves that calendar.

## Changes in this task

- `frontend/src/pages/ClockSchedule.tsx`: preserve same-source preferences, clear on invalidation, explain partial generation, name excluded medicines and their individual reasons in the generated result.
- `frontend/src/lib/clockSchedulingHindi.ts`: Hindi for the partial-generation notice and exclusions heading.
- `frontend/src/pages/ClockSchedule.test.tsx`: focus restoration and mixed complete/incomplete page generation regressions.
- `api/clock_scheduling.py`: do not discard a valid course for a rejected replacement request.
- `api/tests/test_patient_explanations.py`: authenticated real-loopback HTTP partial-course regressions for a review flag and a genuinely unavailable count, including preserved calendar on invalid replacement.
- This report.

Prescription Analysis, authentication, AI extraction, explanations, pricing, strip scanning, account databases and diagnostic guards were not changed in this task. Existing uncommitted work was preserved. Nothing staged, committed or pushed.

## Verification

- Full Python suite: **1,238 passed, 1 skipped, 13 subtests passed**. This full run loaded the initial new HTTP case; its subsequent two-case parametrization was verified separately: **2 passed, 10 deselected**.
- Full frontend suite: **236 passed**, 33 test files.
- Production build: **passed**, existing large-chunk warning.
- `git diff --check`: passed; existing line-ending notices only.
- HTTP tests use real localhost TCP/HTTP, temporary SQLite accounts, cookie-authenticated requests and realistic mocked Gemini responses. External provider connections are forbidden. No Gemini or Telegram calls.

Fully confirmed three-medicine case: Dolo has two clock inputs and a five-day course (10 tablets at the selected times); Cetirizine has one input and a three-day course (3 tablets); Omeprazole has one input and a seven-day course (7 capsules). No additional scheduling confirmation is requested.

Partial cases: Dolo remains visible but excluded when its review flag is unresolved or its daily administration count is genuinely missing. With a verified count, its two time inputs remain visible even while that clinical flag blocks generation. With no verified count, no number of inputs is invented. Cetirizine and Omeprazole still generate their own courses. The returned `blocked` list names Dolo and the exact issue. An invalid replacement preserves the prior valid calendar.

## Browser limitation and manual check

No actual browser interactions or live OCR were verified in this task. No listener was found on local ports 8005 and 5177 during inspection, so the recorded browser state could not be compared with the running source version. The screenshot/recording itself was not inspected.

Restart using the existing commands in `PATIENT-EXPLANATIONS-AND-SCHEDULING.md` and open `http://localhost:5177`. Sign in, use the normal medicine/instruction review and existing confirmed relationships, then open Scheduling. Enter the date and clock times, switch windows and return: choices should remain. Generate with one genuinely incomplete medicine: complete medicines should receive calendars and the incomplete medicine should be named under exclusions. Editing the source must revoke the old schedule. Do not clear clinical flags merely to pass this test.

Restarting the API retains local registered accounts but clears temporary in-memory prescription workspaces. Do not expect a previous temporary prescription to survive a backend restart.
