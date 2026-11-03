# Manual website-only scheduling demo

`/dashboard/schedule` now routes to `ManualSchedule`. The existing protected dashboard navigation and local account authentication are unchanged. The previous `ClockSchedule` component, API clients, prescription-linked scheduling endpoints, engine and clinical safeguards remain isolated in the repository and are not imported by the manual page.

## Behavior

- The user supplies the medicine name, quantity, unit, duration, start date and every desired daily clock time. Quantity, unit, duration and date start empty. The initial time input is blank; no schedule exists until the user enters values and clicks Generate Schedule.
- Add Time/Remove Time controls determine the number of daily events. Duplicate/invalid times are rejected; no frequency is inferred.
- Generate adds one manual medicine course. Add another to combine courses with different durations and quantities. Edit loads a saved course into the form; Generate replaces that course only. Delete removes that manual course only.
- Calendar and daily-list views show the selected month, with previous/next month navigation. Multiple medicines can share a date. Summary cards show quantity/unit, selected times, start, inclusive last date and total dose-event count.
- English/Hindi use the existing language store. Unit translations are scoped to the manual page. CSS inherits existing dark/light palette tokens.
- Optional `?name=Dolo%20650` prepopulates only the name; it does not select dosage, unit, days, start date or times. No Prescription Analysis interface or links were changed.

The notice is: **Demo planner — follow your clinician's instructions**. This is an on-screen display of user-entered plans, not a prescription, AI instruction or medicine recommendation. No SMS, emails, WhatsApp, push notifications, OS reminders or external calendar writes are implemented or invoked.

## Dates and limits

Dates are validated ISO calendar-date strings. Arithmetic and formatting explicitly use UTC calendar operations, avoiding browser timezone/DST conversion of the selected date. Start is Day 1:

`last_date = start_date + duration_days - 1`

Verified example: Dolo 650, 1 tablet, 5 days starting **3 November 2026**, times **09:00 and 21:00**, creates **10 events** on 3–7 November, with last scheduled date **7 November 2026**. Tests cover differing month lengths, year rollover, leap/non-leap February and a DST boundary.

Demo resource limits: 20 medicines, 1–366 days per course, 1–12 distinct daily times, at most 10,000 total events, names up to 100 characters, finite positive quantities up to 1,000. These are technical input/resource limits, **not medically safe dose ranges or recommendations**. A user must follow their actual clinician's instructions.

## Persistence and privacy

Plans use `sessionStorage`, keyed by the existing authenticated local user ID (`medisaathi.manual-planner.v1:<user-id>`). No password, cookie, token, email, uploaded image or prescription extraction is stored by the planner. Restored data is validated and reconstructed into the allowed plan fields before rendering.

Navigation and refresh within the same tab restore generated plans for the same account. Another account gets a different storage key. Account changes remount the planner, preventing the previous account's in-memory view from carrying over. Without a known signed-in local user or available browser storage, the page reports that persistence is unavailable; it does not pretend plans were saved.

This is **unencrypted browser-tab demo storage**, not secure owner-enforced medical-record storage, a database archive or external synchronization. Use fictional data. Browser/session clearing, closing a tab or browser restore behavior can affect retention. Plans may remain in that tab's browser storage after logout until removed or the tab/session data is cleared; account-scoped keys are UI separation, not encryption against someone with access to the browser/devtools. Backend account deletion does not claim to delete this browser-only demo data. Delete on this page affects the manual plan only, not prescriptions or backend records.

## Isolation

The manual planner has no prescription or scheduling API client. Its local-account hook may perform the existing authentication session restoration request; it never calls clock-scheduling eligibility, OCR, medicine associations, schedule review or approval endpoints. Tests fail if the inner manual workflow tries any fetch. The routed-page test also rejects prescription/clock requests.

No backend code, account database, original worktree, diagnostic guards, pricing, Lab Costs removal, Strip Expiry, medicine explanations, Prescription Analysis, clinical confirmations or scheduling arithmetic was changed in this task.

## Verification

- Full frontend suite: **283 passed**, 37 files.
- Relevant unchanged backend authentication and prescription-scheduling suites: **31 passed**.
- Production build: **passed**, existing large-chunk warning only.
- `git diff --check`: passed, existing line-ending notices only.
- UI tests verify the requested Dolo form creates ten calendar entries immediately, daily-list switching, three independent medicines, editing/removing, same-account refresh/remount restoration, another-account separation, Hindi/light mode, storage failure and name-only prefilling.
- Calculation tests verify once/twice daily courses, inclusive dates, month/year/leap/DST boundaries and invalid/corrupt data.
- The running Vite server returned HTTP 200 for the manual module; served `App.tsx` routes Scheduling to it. The module does not import `clockClient` or `schedulingClient`.
- Actual browser interaction was **not performed**: the Chrome connector returned `The browser access host is unavailable`. Component tests and HTTP source checks are not claimed as browser verification.

## Exact files changed

New:

- `frontend/src/pages/ManualSchedule.tsx`
- `frontend/src/lib/manualPlanner.ts`
- `frontend/src/lib/manualPlannerHindi.ts`
- `frontend/src/manual-planner.css`
- `frontend/src/pages/ManualSchedule.test.tsx`
- `frontend/src/lib/manualPlanner.test.ts`
- `MANUAL-SCHEDULER.md`

Modified:

- `frontend/src/App.tsx` — Scheduling route import only.
- `frontend/src/lib/language.ts` — register the new feature's Hindi strings.
- `frontend/src/ReducedScope.test.tsx` — manual route and no-old-eligibility request regression.

No dependencies installed. No commit, stage, push or merge.

## Try it

The existing backend is needed only for the existing Sign In session. **No backend restart is required for this frontend-only feature.** The running Vite server already serves the new route. Open or refresh `http://localhost:5177/dashboard/schedule` after signing in.

If Vite is not running:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Enter Dolo 650; quantity 1; unit tablet; duration 5; start 2026-11-03; first time 09:00; Add Time and choose 21:00. Click Generate Schedule. Verify 10 pills in the calendar through 7 November, switch Daily list, refresh, edit and regenerate, then delete. No prescription upload or review is needed.
