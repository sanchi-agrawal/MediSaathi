# Milestone 14F: integration verification and safe local checkpoint

Audit date: 2026-10-28, Asia/Calcutta. Branch: feature/scheduling-integration. Base: 40ab046. The checkpoint preserves the reviewed 14C scheduling, 14D error/readiness work and 14E session workspace/multilingual work plus one narrowly tested 14F view fix. No major integration, real account implementation or database is added.

## Actual browser status — NOT VERIFIED

Computer Use was initialized using the installed computer-use skill. Chrome was discovered, but the first browser action was stopped by the tool: it could not determine the current browser URL confidently enough to enforce policy. No further browser input or alternative UI-automation workaround was attempted. No browser workflow, screenshot layout, camera behavior, Chrome cookie acceptance or hard refresh is claimed as verified. Input outcome before the tool stopped is not treated as a successful workflow.

This limitation applies to every browser workflow below. HTTP tests and jsdom/component tests are distinct evidence, not substitutes labelled as human/browser success.

## Verification evidence

| Workflow | Evidence that passed | Actual browser |
| --- | --- | --- |
| Upload/extraction | Fictional provider-blocked fixture through Vite, API tests, React upload tests | Unverified |
| Independent review/confirmation | Actual API endpoints through Vite with separate medicine/instruction revisions; API/component tests | Unverified |
| English/Hindi/Hinglish | Three distinct actual controlled backend payloads through Vite; visible jsdom language tests | Unverified |
| Analysis → Medicines → Schedule → Analysis | React Router remount test plus current/schedule HTTP restoration reads | Unverified |
| Refresh restoration | Repeat current snapshot/image reads and component remount tests | Hard browser refresh unverified |
| Explicit association | HTTP association after both confirmations; stale/cross-session/forgery API cases | Unverified |
| Saved-plan review / separate approval | HTTP review produces no result until approval; replay rejected | Unverified |
| Correct schedule/refill | Fixture engine returns 2 tablets/day, 6 total, 2026-10-28 through 2026-10-30, null refill; API tests also cover 30-day refill and mL conversion | Unverified |
| Editing/invalidation | HTTP source invalidation revokes schedule access; API/component tests cover plan, source, association, clear and late-response changes | Unverified |
| Separate strip workflow | Mocked strip API/frontend suites cover review, confirmation, conflicts, unknowns, failures, image validation and prescription independence | Unverified; current browser fixture does not enable strip scope |

The HTTP test used only localhost:5174's existing provider-blocked fictional fixture for upload/extraction/confirmation/scheduling. It verified limited fixture scopes before extraction and sent no OCR request to the normal configured API. Cookie values stayed in test-client memory and were never printed. Normal localhost:5173 received health and empty-session isolation checks only. No real patient image or record was used. Fictional sample data is not evidence of Gemini accuracy or live performance.

Final results:

- **991 Python tests passed**, all offline. One existing Starlette test-client deprecation warning remains.
- **76 frontend tests passed** (75 existing plus the confirmed expired-session regression).
- TypeScript/Vite production build passed.
- Git whitespace check and staged audit must pass before the local commit; actual commit identity is reported in the delivery response.
- No Gemini/provider call, guard reset, original AI worktree modification or push occurred.

## Confirmed defect fixed

Explicit Restore current session could receive no active session after expiry/clear while leaving previously loaded records, confirmation, explanation and source preview visible. A new component regression failed against that behavior.

The fix clears the stale local server workspace and remounts its image preview only when a previous server snapshot was loaded. It does not create a replacement session, rerun OCR, call a server clear, alter confirmation rules or discard a new local upload on the initial empty-session check. The first implementation caused a file-input remount race in existing upload tests; the reset was narrowed and the entire frontend suite then passed. The regression proves stale records, explanation, server-confirmed display and preview disappear while no upload/extractor call occurs.

Only PrescriptionFlow.tsx and WorkspaceRestore.test.tsx have new functional/test changes in 14F; the other checkpoint changes were reviewed 14C–14E work. No Person 3 engine or original AI module was modified.

## Safe checkpoint audit

The exact allowlist below contains 37 text source/test/documentation files. Stage paths explicitly from the reviewed manifest, never git add -A or directory-wide git add. Review the actual staged blobs, not only working files. Check that every blob matches the reviewed source, that only the allowlist is present and that medisaathi/ is absent from the staged diff.

Exclude all .env variants, credentials, cookies/tokens, virtual environments (including local diagnostic scripts), node_modules, build output, caches, provider responses, generated fixture images, source/session runtime state, and the entire smoke/attempts runtime tree. No binary image or medical record file is added by this checkpoint. The diagnostic marker/code-name references in documentation are not runtime authorizations. The reviewed cookie-name constant is not a cookie value.

All five original existing guard/authorization/result files retain their recorded checksums. Source and staged scans cover credential/private-key/token patterns and unintended file types; the original .env is neither read into documentation nor copied into source. Existing tracked medisaathi files, including schedule.py, app.py, confirm_utils.py and AIIntegration/assistant interfaces, remain unchanged. Git metadata fetch does not switch branches or touch original-worktree working files.

Expected local commit message, exactly as authorized:

`feat(integration): add guarded scheduling and persistent session workspace`

Here “persistent session workspace” means navigation/refresh restoration within the same RAM-only demo session. It does **not** mean durable storage or authenticated account persistence.

## Exact checkpoint filenames

```text
api/ACCOUNTS_PLAN_14E.md
api/BROWSER_14D.md
api/README.md
api/SCHEDULING_14C.md
api/VERIFICATION_14F.md
api/WORKSPACE_14E.md
api/downstream/__init__.py
api/downstream/models.py
api/downstream/scheduling.py
api/downstream_routes.py
api/main.py
api/prescription_summary.py
api/section_routes.py
api/sessions.py
api/tests/test_browser_readiness.py
api/tests/test_downstream.py
api/tests/test_workspace_restore.py
frontend/README.md
frontend/src/App.tsx
frontend/src/components/ImageUploader.tsx
frontend/src/components/PrescriptionExplanation.tsx
frontend/src/lib/explanationCopy.ts
frontend/src/lib/prescriptions.ts
frontend/src/lib/scheduling.test.ts
frontend/src/lib/scheduling.ts
frontend/src/lib/sections.ts
frontend/src/lib/workflowEvents.test.ts
frontend/src/lib/workflowEvents.ts
frontend/src/lib/workspaceClient.test.ts
frontend/src/pages/CurrentWorkspace.tsx
frontend/src/pages/PrescriptionFlow.test.tsx
frontend/src/pages/PrescriptionFlow.tsx
frontend/src/pages/PrescriptionSections.test.tsx
frontend/src/pages/Schedule.test.tsx
frontend/src/pages/Schedule.tsx
frontend/src/pages/WorkspaceRestore.test.tsx
frontend/src/schedule.css
```

## Teammate availability

Remote metadata was fetched successfully. Advertised heads are c=fe578ef, feature/ai-frontend=40ab046, feature/ai-pipeline=2e6eee1 and main=4cd507e. No Person 2 matching/medicine-pricing/lab-pricing implementation was found in the fetched remote branches or relevant file history. This does not say whether Person 2 has unpublished local work. No pricing integration or fabricated catalogue/cost is enabled.

## Before the October 30 demonstration

1. Complete human-browser checks using the labelled fictional setup and manual steps in WORKSPACE_14E.md/BROWSER_14D.md. Verify real Chrome Secure-cookie acceptance, page refresh, navigation, language switching, approval and source-edit invalidation. The UI automation failure remains unresolved.
2. Verify the separate strip UI with a dedicated mocked strip setup/manual test. The existing prescription fixture intentionally excludes strip; do not click its Analyze on a normal live backend under this no-provider milestone. API/component strip tests pass.
3. Present signup/login as demo-only. Records live in one process's memory for 30 minutes and disappear on restart/expiry. Keep to one Uvicorn worker/loopback. See ACCOUNTS_PLAN_14E.md for authenticated durable storage and the required safe approval restore boundary.
4. Keep scheduling limited to supported explicit decimal/unit/day/named-slot inputs. Flagged needs_review medicines and unsupported/ambiguous/taper/PRN cases remain blocked. No notification delivery, inventory, medicine association inference or pricing is available.
5. Treat historical live smoke readiness reports as history, not fresh execution permission. Preserve consumed guards. A real OCR demonstration needs separately authorized inputs/provider budget; none was tested here.

The existing local fixture scripts/images/logs remain ignored under api/.venv. They are local diagnostics, not committed deployment assets. The committed tests retain fictional extractors and fixtures for reproducible offline verification.
