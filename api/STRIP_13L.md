# Milestone 13L: isolated medicine-strip review

The normal API and `/dashboard/expiry` now support explicit upload, analyze, review, save and confirmation. No live Gemini call or browser verification was performed in this milestone. Guarded diagnostic launchers remain medicines-only; consumed attempt guards do not authorize strip OCR.

## API

All operations use the existing opaque HttpOnly/Secure demo-session cookie, same-origin action header and CORS policy. This is not account authentication. Each session retains one AIIntegration with independent prescription and strip roots.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | /api/strips | Validate original raw PNG/JPEG bytes and create a strip analysis |
| DELETE | /api/strips/current | Invalidate access to the current strip workflow |
| GET | /api/strips/{analysis_id} | Read current strip snapshot |
| POST | /api/strips/{analysis_id}/analyze | Explicit new or failed extraction only |
| POST | /api/strips/{analysis_id}/invalidate | Rotate revision and remove review/confirmation |
| PUT | /api/strips/{analysis_id}/review | Save raw corrections through the existing parser |
| POST | /api/strips/{analysis_id}/confirm | Server-owned acknowledgement of current saved review |

Use existing POST /api/session before uploading. Analyze, invalidate, review and confirm require current revision. IDs and revisions are scoped to the cookie session. Extraction executes outside the session lock; duplicate jobs are rejected and late results cannot attach to replacement images.

## Contract and safeguards

AIIntegration invokes the existing strip.read_strip extractor. Review invokes strip.normalize_strip_response offline. Neither original module is changed. Review accepts only printed medicine name, batch number, product association inside the photo, and raw label/date/line/association for each original observation. Derived dates, confidence and parser flags are rejected as browser input. Every observation must remain present; source confidence, uncertainty and image-quality issues are preserved.

Unknowns, manufacturing/batch dates, USE BEFORE, ambiguous numeric dates and conflicting expiry dates retain the original conservative semantics. A readable month has no inferred day. No current-date comparison, medicine safety judgment, prescription association, inventory, reminder or schedule is created. Confirmation acknowledges reviewed text and may still contain unresolved warnings.

Replacing or clearing one workflow preserves the other. API active flags tombstone cleared roots: IDs and confirmations become inaccessible through these routes, but inactive source bytes may remain in the session's RAM until root replacement or session expiry/pruning. Clear is not a secure-memory-erasure guarantee. This avoids changing AIIntegration's public contract or replacing the shared adapter and erasing the other workflow.

## Frontend

The existing validated uploader supplies PNG/JPEG and device-dependent camera capture, local preview, zoom and rotation. Original bytes are sent only on explicit Analyze. Review panels show original observations, editable raw text, nulls, parser warnings and confidence marked uncalibrated. Unsaved edits hide the selected parsed expiry and immediately disable confirmation. Save reparses on Python; explicit acknowledgement and successful server confirmation are required. Failed extraction differs from successful extraction with unknown expiry. Retry is explicit; there is no automatic API/network retry or mock fallback.

## Verification

- 926 Python tests passed (907 existing plus 19 strip API cases).
- 39 frontend tests passed (30 existing plus 9 strip UI/client cases).
- TypeScript and Vite production build passed.
- Existing FastAPI test-client deprecation warning remains.
- No live provider calls, browser automation, server restarts or attempt-guard changes.

Manual verification remains: open `/dashboard/expiry` against the normal configured API; check responsive layout, camera on target device, Secure cookie on localhost, original-byte upload, conflict/unknown displays, Save then Confirm, invalidation after edits and image replacement, and preservation of prescription review. A live strip OCR request needs a separately authorized fictional fixture test; old diagnostic guards must not be reused or cleared. This milestone adds no new provider-attempt guard. The normal extractor's existing malformed-output retry behavior is unchanged, so do not assume one Analyze equals one provider request when authorizing a future benchmark.

## Local startup

From repository root, with existing server-only Gemini configuration loaded:

```powershell
api/.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

From `frontend`:

```powershell
npm.cmd run dev
```

Open `http://localhost:5173/dashboard/expiry`. Vite proxies /api to port 8000. Ensure an old guarded smoke process is not occupying that port; do not reset its guard. Startup itself does not invoke extraction.

## Exact source/documentation inventory for this milestone

Modified:

- api/main.py
- api/models.py
- api/sessions.py
- api/section_routes.py
- api/README.md
- frontend/README.md
- frontend/src/pages/Workspace.tsx

Created:

- api/strip_routes.py
- api/tests/test_strip_api.py
- api/STRIP_13L.md
- frontend/src/lib/strip.ts
- frontend/src/lib/strip.test.ts
- frontend/src/pages/ExpiryScanner.tsx
- frontend/src/pages/ExpiryScanner.test.tsx
- frontend/src/strip.css

Build-generated frontend/dist and TypeScript incremental output are ignored. No teammate Python implementation, original AI worktree, extraction/parser contract or Git history is changed. The workspace already had untracked API/frontend and AI files before this milestone; git status alone does not identify this milestone's edits.
