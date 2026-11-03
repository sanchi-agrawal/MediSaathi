# Milestone 13K: instructions and investigations

## Architecture and contracts

The normal FastAPI adapter now exposes all three prescription scopes. Medicines remain the exact ten-field list. Dosage instructions use `medication-instructions-v1`; prescribed investigations use `prescribed-investigations-v1`. Their envelopes retain source-image SHA-256, positional IDs, original text, nulls, issue/uncertainty codes, `needs_review` and `confirmation_required`. They are not flattened into medicine records, automatically associated, or turned into schedules.

Existing `AIIntegration.begin_section/execute/review/frontend_events/confirm/snapshot` methods and instruction/investigation extractors are reused unchanged. Each cookie session has one adapter and independent section revisions/review/confirmation gates. Model contracts, prompts and medical interpretation code are unchanged.

Image replacement calls `start_prescription`, invalidates all scopes and resets transport revisions. Old jobs cannot attach to a replacement image. Editing a saved section clears its displayed approval immediately and calls its invalidation endpoint. The API confirmation gate is invalidated first; a changed saved payload additionally invokes the original adapter's underlying invalidation of dependent results. No downstream results are exposed independently of these gates. Other confirmed scopes remain current. No scheduling, pricing, reminders or association endpoints were added.

## Routes

`scope` is exactly `instructions` or `investigations`:

| Method / path | Body | Behavior |
|---|---|---|
| `GET /api/prescriptions/{analysis_id}/sections/{scope}` | — | Original/reviewed section payload, status, revision, warnings/failure and confirmation |
| `POST /api/prescriptions/{analysis_id}/sections/{scope}/analyze` | `{revision}` | Explicit new extraction or explicit failed-section retry |
| `POST /api/prescriptions/{analysis_id}/sections/{scope}/invalidate` | `{revision}` | Remove this section's API review/confirmation gate |
| `PUT /api/prescriptions/{analysis_id}/sections/{scope}/review` | `{revision, payload}` | Validate/save the exact original envelope through AIIntegration |
| `POST /api/prescriptions/{analysis_id}/sections/{scope}/confirm` | `{revision}` | Register/consume a server-owned current-section acknowledgement |

Existing medicine routes retain their request bodies/behavior. Their responses additionally include a `sections` map for enabled extra scopes; medicine fields remain untouched. `GET /api/health` reports enabled scopes. New routes retain HttpOnly/Secure/SameSite cookies, Origin/custom-header mutation checks, no-store responses and sanitized validation errors. Each revision belongs to its section. Cross-session, stale analysis and stale section requests, extra confirmation claims and mixed/forged fields are rejected.

`create_app` has an internal `enabled_sections` setting. The ordinary API enables all three. Both guarded smoke launchers explicitly enable medicines only. New-scope requests to them return unavailable without extraction. This feature does not expand prior live authorization or clear a consumed allowance.

## React interactions

- Select Medicines, Dosage instructions and/or Prescribed investigations; only the explicit Analyze button extracts. Selection, preview, rendering, status reads and timers do not call Gemini.
- Reuse the current uploaded source when adding a section. Completed sections are not re-extracted, and Analyze disables when all selected sections are complete. No cross-image extraction cache was added.
- Selected new/failed sections run sequentially. Each is a distinct extractor/provider operation. Existing malformed-response retry policies remain; API/network failures are not automatically retried. Known configuration/quota errors stop remaining sequential work while preserving successes. The existing medicine reader's generic API error cannot identify every quota subtype.
- Separate panels show original text, editable literal fields, explicit unknown placeholders, read-only review flags/uncertainties and envelope issues. Dose fractions/shorthand stay strings, with no schedule conversion.
- Save and acknowledge each scope, then confirm it explicitly. One scope cannot authorize another. Edits require new review/confirmation and leave original source text visible.
- Partial success is labelled; section Retry retries only that failed scope. Successful empty results remain distinguishable from failure and require explicit confirmation.
- Image replacement/removal clears every local scope and ignores late responses. Source text is rendered as plain text. The navy/coral/blue theme and responsive field grid remain.
- Doctor/pharmacist verification disclaimers explain that confirmation does not resolve uncertainty or authorize schedules/medication changes.

This workflow is in `/dashboard/analysis`; separate dashboard summary pages are not new persistence integrations.

## Local use and remaining live checks

For future authorized manual verification, use the **normal** API with server-only Gemini configuration:

```powershell
cd C:/Users/ASHTAMI/MediSaathi-Frontend
api/.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

The normal API reads Python-process `GEMINI_API_KEY`/`GEMINI_MODEL` or ignored adjacent `medisaathi/.env`. It does not automatically load the original AI worktree's `.env`. Never put secrets in frontend code/environment variables. Existing guarded attempts stay unchanged; their one-call authorizations do not cover these new scopes. No server was restarted or live provider call made in 13K.

```powershell
cd C:/Users/ASHTAMI/MediSaathi-Frontend/frontend
npm.cmd run dev
```

Open `http://localhost:5173/dashboard/analysis`. Live checks of both new scopes, actual-browser interactions and visual QA remain unperformed here. Use fresh authorization for controlled live calls and fictional/privacy-approved images. Initially select one scope at a time; check literal text/nulls/warnings, save/confirm, edit, replace the image and test a partial failure. Authentication stays demo-only.

## Exact files changed

Verification: **907 combined Python tests passed; 30 frontend tests passed; production build and TypeScript checks passed**. Nine new backend tests cover independent scopes, confirmation/edit invalidation, stale/cross-session access, partial failure/retry, strict payloads, duplicates, guarded capability limits, empty results and image replacement during extraction. Nine new frontend tests cover scoped transport/contracts, selection, independent confirmation, partial failures, quota stopping and stale response suppression. One non-failing Starlette test-client deprecation warning remains. No live calls or browser automation occurred.

- `api/main.py`
- `api/models.py`
- `api/sessions.py`
- `api/section_routes.py` (new)
- `api/smoke/server.py` (medicine-only capability restriction)
- `api/smoke/second_attempt.py` (same restriction; transport guard unchanged)
- `api/tests/test_sections.py` (new)
- `api/README.md`
- `api/SECTIONS_13K.md` (this report)
- `frontend/README.md`
- `frontend/src/lib/api.ts` (comment only)
- `frontend/src/lib/sections.ts` (new)
- `frontend/src/lib/sections.test.ts` (new)
- `frontend/src/components/SectionReview.tsx` (new)
- `frontend/src/components/ImageUploader.tsx` (avoid empty preview src causing a page request)
- `frontend/src/pages/PrescriptionFlow.tsx`
- `frontend/src/pages/PrescriptionFlow.test.tsx`
- `frontend/src/pages/PrescriptionSections.test.tsx` (new)
- `frontend/src/styles.css`

No original AI worktree, AI contract, teammate scheduling/pricing/Streamlit implementation, credential, guard or historical diagnostic was modified. No merge/reset/clean/stage/commit/push occurred.
