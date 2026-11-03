# Milestone 14E: current workspace restoration and multilingual explanations

## Delivered scope

Phase 1 and Phase 2 are implemented. Authentication remains **demo-only**; storage remains **session-memory only**, with a 30-minute absolute lifetime and no durable restart recovery or account history. Phase 3 uses the explicitly authorized fallback: [ACCOUNTS_PLAN_14E.md](ACCOUNTS_PLAN_14E.md) is a concrete provider/database/security plan. No password security, provider tokens, account ownership model, durable storage or real logout is pretended to exist.

## Root causes

PrescriptionFlow initialized all workspace state to empty on every React mount and had no current-analysis fetch. React Router unmounts it when visiting another page. Returning therefore displayed an empty upload screen even though the server still held the analysis. Medicines and Investigations were static integration placeholders. Mounting/navigation itself did not create a new session or analysis ID; there was simply no hydration path.

Schedule already retrieved server context, but requires both medicines and instructions independently saved/confirmed, an explicit association and a reviewed/approved plan. Merely analyzing a prescription must not produce a schedule. The fix restores records for continued review rather than bypassing that prerequisite.

Other distinct loss cases remain explicit: server restart, session expiry, cookie rejection, or switching from the normal backend on localhost:5173 to the isolated fictional backend on localhost:5174. Cookies are not port-scoped; the fixture uses a separate medisaathi_fixture_14d name and independent store. Switching between these applications is not transferring a saved account prescription. The same origin/session must be used for a real navigation test.

Hindi previously only changed selection state and cleared the old explanation; it required a second Explain click. The page also kept English panel labels and could show an empty static panel. assistant.py already produced real controlled Hindi/Hinglish descriptions; it did not require another OCR engine or provider call.

## Backend changes

- GET /api/prescriptions/current returns the active cookie session's actual analysis ID, current medicine revision, original/reviewed records and independently confirmed section snapshots. Static routes are registered before the dynamic analysis route. It neither creates a session nor performs extraction.
- GET /api/prescriptions/current/image?analysis_id=...&revision=... returns original validated PNG/JPEG bytes only to the owning session and exact current binding. Content type is established after Python decode; response is no-store/nosniff. Cross-session/stale/cleared/expired access fails. The API stores a RAM reference to the same immutable bytes passed to AIIntegration, not a new disk medical-image store. Clear removes the API reference; the older AI root retention limitation remains until replacement/expiry.
- The existing explanation endpoint still calls unchanged AIIntegration.explain and assistant.explain_prescription. Its original payload contract remains intact. An additive `summary` sibling gives localized structured descriptions of independently confirmed instructions/investigations, retaining raw values, unknowns and uncertainty flags. Unconfirmed sections contribute no records, facts or source warnings to this confirmed summary. Section changes clear cached explanations.
- Health adds workspace_contract=restore-summary-v1, storage=session-memory and authentication=demo-only. It does not claim account readiness.

Cookie settings remain Secure/HttpOnly/SameSite=Strict/Path=/api. CORS and mutation-origin checks are unchanged. No sessions/tokens or prescription data are placed in localStorage. The existing API gates and unchanged AI/scheduling code continue to reject unconfirmed, stale or cross-session mutations and revoked schedule results.

## Frontend behavior

Returning to Analysis fetches the current server snapshot and original source preview with credentialed, uncached GETs. Both confirmed and unfinished extraction sections reappear. Restored preview setup never fires the upload-change callback, so it does not clear confirmation or create another analysis. Late hydration cannot overwrite a newly selected image. Failed restoration has an explicit message; no new session is silently created to replace an expired one. Restore current session is available for explicit refresh. Unsaved browser drafts are not a saved review: save before navigating.

Medicines and Investigations now show the current server records, original text, nulls, uncertainties and scope confirmation status, with Continue Review and Schedule links. These pages are labelled current-session views, not account history. Schedule continues to load the current authoritative server state and approved result.

For confirmed medicines, selecting Hindi, Hinglish or English directly calls the real explanation API with hi, hinglish or en and renders the returned content. It cannot invoke OCR. Before medicine confirmation, language selection changes readable labels/help and explicitly states the confirmation prerequisite; no explanation authority is fabricated. Explain remains available as an explicit action. A mismatched response language is rejected rather than rendering English as Hindi. Loading/failure clears stale-language success.

The full confirmed summary shows original medicine names, actual controlled medicine fields/glossary/warnings and separately confirmed instruction/test panels. Hindi/Hinglish labels describe the original quantities, strengths, units and text; free-form medical translation is deliberately not inferred. Raw OCR and reviewed source text remain unchanged. Unknown values are visible and extraction uncertainty is not removed by acknowledgement. No ingredients, indications, side effects, dosages, schedules, test variants or associations are added by language selection.

## Verification

- 991 offline Python tests passed; one existing Starlette test-client deprecation warning.
- 75 frontend tests passed; TypeScript/Vite production build passed.
- Component/router tests reproduce Analysis → Medicines → Schedule → Analysis, preserving the same server snapshot and approved schedule with no upload/extraction/reapproval call. They test late hydration, Hindi/Hinglish actual content, preserved original text, prerequisites and failures.
- API tests verify repeated restoration/image reads without new IDs/revisions/extractor calls, anonymous-session isolation, stale image binding, session expiry, restart loss, source invalidation, unknown values and independently confirmed multilingual section inclusion.
- A fixture-only HTTP flow through the live Vite proxy verified current/image hydration, independent confirmation, three distinct actual controlled language payloads, normal/fixture cookie isolation and source invalidation. It blocked real provider use. Cookies were forwarded only in the test client's memory and never printed; this is not proof of browser-specific Secure-cookie acceptance.
- Human Chrome interaction/visual inspection was not performed. No Gemini call was made. Authenticated account A/B isolation and durable restart restoration are **not implemented/tested**; only anonymous-session isolation and honest restart loss are verified.

The normal API was restarted to load this upgrade and read the existing original-worktree environment file server-side. That one-time restart discards older RAM sessions. Health confirms configuration presence only; quota/model access is not tested. Current services: normal localhost:5173 → 127.0.0.1:8000; clearly labelled offline fictional localhost:5174 → 127.0.0.1:8001. No secrets were copied into React or a new .env.

## Manual no-provider browser check

1. Use **http://localhost:5174/dashboard/analysis** and verify the OFFLINE FICTIONAL TEST banner. Use only api/.venv/14d-fictional-scheduling.png. Selecting medicines/instructions and Analyze in this harness invokes fixed fictional extractors with provider construction blocked.
2. After Analyze, navigate to Medicines, then back to Analysis before confirming. The same extracted records/image should reappear. Scheduling must still require confirmation rather than imply the prescription disappeared.
3. Save and independently confirm medicines and instructions. Select Hindi after medicine confirmation: a real Hindi summary should appear without an extra Explain click. Check the original medicine name, units and source textarea are unchanged. Select Hinglish, then English and compare visible descriptions.
4. Associate the explicit pair on Schedule, enter source-backed 1 tablet / 3 days / morning and night, choose a start date, save and approve. Keep this origin and cookie. Return to Analysis, Medicines and Schedule; the approved result must persist without another Analyze or Approve action.
5. Refresh the browser on Analysis: records and preview should restore. Open the same origin in another tab: it shares that demo session. Edit a confirmed source; previous confirmations and schedules must become unavailable and require renewed review.
6. A separate browser profile/incognito session must not see the first profile's records. Port 5173 is the different normal server and does not share the fictional workspace. Do not click Analyze there as part of this no-provider check.
7. If localhost Secure cookies are rejected by the target browser, use trusted local HTTPS; do not disable Secure. Inspect only cookie attributes and safe status/category, never copy cookie/token values into chat.

The 14D offline helper scripts are ignored local diagnostics under api/.venv, not production modules. Standard normal startup (when the port is free) remains:

```powershell
api/.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --env-file C:/Users/ASHTAMI/MediSaathi/medisaathi/.env --no-access-log
# Separate terminal in frontend:
npm.cmd run dev
```

## Exact 14E source/documentation inventory

Modified:

- api/main.py
- api/sessions.py
- api/section_routes.py
- api/README.md
- frontend/README.md
- frontend/src/App.tsx
- frontend/src/components/ImageUploader.tsx
- frontend/src/lib/prescriptions.ts
- frontend/src/pages/PrescriptionFlow.tsx
- frontend/src/pages/PrescriptionFlow.test.tsx
- frontend/src/pages/PrescriptionSections.test.tsx

Created:

- api/prescription_summary.py
- api/tests/test_workspace_restore.py
- api/ACCOUNTS_PLAN_14E.md
- api/WORKSPACE_14E.md
- frontend/src/components/PrescriptionExplanation.tsx
- frontend/src/lib/explanationCopy.ts
- frontend/src/lib/workspaceClient.test.ts
- frontend/src/pages/CurrentWorkspace.tsx
- frontend/src/pages/WorkspaceRestore.test.tsx

Ignored local diagnostics: api/.venv/14e_update_ui.py, 14e_route_pages.py, 14e_finish_ui.py, 14e_start.ps1, 14e_proxy_verify.py, runtime logs, test temporary directories and normal build/cache output. Original AI worktree, all medisaathi implementations, Person 3's engine and the existing guard/authorization/result records are unchanged. Nothing is staged, committed, merged or pushed.
