# MediSaathi 13E · medicines HTTP adapter

**Checkpoint 14B:** see [CHECKPOINT_14B.md](CHECKPOINT_14B.md) for the reviewed source inventory, AI provenance and runtime exclusions. Historical smoke readiness reports are records of earlier milestones, not new execution authorization; guards and authorization artifacts are deliberately absent from Git. The current normal API includes the independent 13K and 13L scopes described below.

**Milestone 13L:** the normal API now includes an isolated medicine-strip OCR/review/confirmation workflow. See [STRIP_13L.md](STRIP_13L.md) for routes, raw-only review contracts, session retention details, tests and remaining manual verification. Guarded diagnostic launchers remain medicines-only.


**Milestone 13K update:** the normal API now supports independent medicines, dosage-instruction and prescribed-investigation scopes. See [SECTIONS_13K.md](SECTIONS_13K.md) for the new routes, contracts, UI, tests and live-verification limits. Guarded smoke/diagnostic launchers remain restricted to medicines; their consumed guards do not authorize new section calls.

**Milestone 13K update:** the normal API now supports independent medicines, dosage-instruction and prescribed-investigation scopes. See [SECTIONS_13K.md](SECTIONS_13K.md) for the new routes, contracts, UI, tests and live-verification limits. Guarded smoke/diagnostic launchers remain restricted to medicines; their consumed guards do not authorize new section calls.

This local demo connects React to the existing `AIIntegration`. Gemini extracts prescription medicines. The existing offline `assistant.py` explains explicitly confirmed text in English, Hindi or Hinglish. This is not authentication or a production healthcare service.

For the current **one-attempt live Gemini smoke test**, use [smoke/README.md](smoke/README.md). Its `--mode live` command loads the existing original-worktree credentials into Python only, preserves the one-attempt guard, and never falls back to mocks. The generic `uvicorn api.main:app` command below is the normal API and does **not** include that smoke-test guard or load the other worktree's `.env` automatically.

## Start on Windows (repository root)

```powershell
python -m venv api/.venv
api/.venv/Scripts/python.exe -m pip install -r api/requirements.lock.txt
```

Configure `GEMINI_API_KEY` and `GEMINI_MODEL` in the **Python process environment**, or in the existing ignored `medisaathi/.env`. Supply your own permitted model name; the adapter does not choose a model or enable billing. Never put Gemini credentials in frontend environment variables, JavaScript, Git, or browser storage. No credentials are included in this milestone.

```powershell
api/.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://localhost:5173/dashboard/analysis**. Vite forwards `/api` to `127.0.0.1:8000`; do not navigate directly to the API to begin a workflow. `npm.cmd` avoids Windows PowerShell's restriction on npm.ps1.

The cookie is always `Secure; HttpOnly; SameSite=Strict; Path=/api`, with no Domain attribute. Local development relies on the browser's localhost exception for Secure cookies. Use exactly `localhost` for the frontend. If your browser does not support that exception, serve the frontend/API through locally trusted HTTPS; do not disable the Secure flag. Non-local deployments require HTTPS. `vite preview` does not proxy the API and is not the integration server.

## Workflow

1. Choose a privacy-approved or fictional PNG/JPEG image. Image preview is local. Zoom and rotation do not alter original bytes.
2. Choose **Analyze with AI**. The browser creates/reuses a demo session, uploads raw image bytes, then explicitly requests medicines extraction. Upload/status/review/confirmation/explanation do not invoke OCR. No automatic Gemini retry occurs in the UI; the existing reader's validated-response retry behavior is unchanged.
3. Compare all ten fields with the image. Original OCR text is displayed separately. Blank edited text is represented as null. Confidence and `needs_review` remain visible, read-only extraction metadata.
4. Choose **Save reviewed records**, acknowledge the current records including unknown values/warnings, then choose **Confirm medicines**. The confirmed state appears only after server success. Empty successful extraction can also be explicitly reviewed and confirmed; it is different from extraction failure.
5. Select English, Hindi or Hinglish and request an explanation. Server `text` fields are rendered as plain React text, never HTML and never unescaped. The output does not authorize scheduling or medicine changes.

Changing an image clears local records/confirmation/explanation immediately and requests server reset if a current analysis exists. The next upload waits for that reset. Editing a saved/confirmed record clears local confirmation and explanation immediately, calls the invalidation route, then requires a new saved review and explicit confirmation. Server invalidation rotates the API revision, clears the API confirmation gate and cached explanation, and blocks explanation until reconfirmed. Saving changed records additionally invokes `AIIntegration.review`, which invalidates the underlying module's confirmation/derived values. No endpoint exposes an underlying derived result independently of the API gate. Requests already delivered cannot be recalled, but late responses cannot attach to a replacement image in the UI or server.

## Routes

All mutation requests require an exact allowed `Origin` and `X-MediSaathi-Action: review`. JSON request objects forbid extra top-level fields. All responses are `Cache-Control: no-store`. Validation errors omit the submitted medical input.

| Method / path | Body | Behavior |
|---|---|---|
| `GET /api/health` | — | Demo mode, enabled scope |
| `POST /api/session` | — | Create/reuse opaque cookie session; no session token in JSON |
| `POST /api/prescriptions` | Raw `image/png` or `image/jpeg` bytes | Bounded upload; existing image validator; new analysis/revision |
| `DELETE /api/prescriptions/current` | — | Tombstone prescription access and API approvals; preserve the separate strip workflow; see 13L retention details |
| `GET /api/prescriptions/{id}` | — | Current medicines status, original/reviewed records, safe failure and revision |
| `POST /api/prescriptions/{id}/analyze` | `{revision}` | Explicit new extraction or explicit retry of a failed extraction |
| `POST /api/prescriptions/{id}/invalidate` | `{revision}` | Invalidate the API review/confirmation gate and explanation |
| `PUT /api/prescriptions/{id}/review` | `{revision, records}` | Strict existing ten-field validation and `AIIntegration.review` |
| `POST /api/prescriptions/{id}/confirm` | `{revision}` | Register and consume a server-owned acknowledgement event |
| `POST /api/prescriptions/{id}/explanation` | `{revision, language}` | Existing confirmed-snapshot explanation, bound to analysis/revision |

No scheduling, reminder, matching or pricing routes are exposed. Instruction/investigation and strip routes were added in 13K/13L; see the linked scope documentation above. Existing authentication screens stay demo-only.

## Session and concurrency model

- One `AIIntegration` per demo session; an application-owned store holds at most 64 sessions. Opaque IDs use `secrets.token_urlsafe(32)`. Each session expires 30 minutes after creation and is removed on the next store access. There is no disk persistence; stop/restart clears all sessions. Lazy TTL cleanup is not an immediate secure-memory erasure guarantee.
- Single Uvicorn worker only. This in-memory model does not support multiple workers/replicas, production identity, durable records, or multi-device ownership. Browser tabs share the cookie; revisions reject stale tab mutations.
- Analysis IDs and revisions are always checked against the cookie session. Server locks protect compound review/confirmation actions. Extraction runs outside the session lock; existing `AIIntegration` job bindings reject late results for a replaced image.
- A request cannot submit trusted `FrontendEvents`, acknowledgement claims, confirmation fingerprints or extra medicine fields. The confirm route accepts only the current API revision and creates the event server-side after a saved review. This is an explicit UI request, not proof of a physical human click or identity.
- CORS uses explicit origins and credentials. Defaults: `http://localhost:5173`, `http://127.0.0.1:5173`; customize the comma-separated `MEDISAATHI_ORIGINS` Python environment variable for a trusted HTTPS frontend. Wildcards are rejected. Hostnames are limited to loopback/test hostnames; deliberate deployment work is needed before hosting elsewhere.
- Raw image streaming is bounded at 10 MiB even without Content-Length. Existing Python rules enforce actual PNG/JPEG decoding, single frames and 8 million pixels. MIME metadata never bypasses byte validation. OCR legibility and handwriting remain uncertain and require user review.
- The public local demo has no production access control, quotas or distributed session storage. Keep it bound to loopback. Do not expose it publicly without adding those controls.

## Offline verification

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'medisaathi'
api/.venv/Scripts/python.exe -m pytest api/tests medisaathi/tests -q
cd frontend
npm.cmd test
npm.cmd run build
```

The API tests inject fictional extractors and block live Gemini/client network use. The six imported AI suites retain their original mocks. No live Gemini requests are part of automated tests. The installed Starlette release emits a test-client deprecation warning for httpx; all tests pass.

## Provenance and exact 13E source inventory

Initially copied byte-for-byte from `2e6eee1`, with no history merge. The later 13J reader adds private numeric timing instrumentation; all other listed modules and six AI test files still match that commit. See the 14B provenance review:

- `medisaathi/{ai_integration,reader,assistant,medication_instructions,investigations,strip}.py`
- `medisaathi/tests/test_{ai_integration,reader,assistant,medication_instructions,investigations,strip}.py`

Added adapter files: `api/__init__.py`, `.gitignore`, `dependencies.py`, `models.py`, `sessions.py`, `main.py`, `requirements.txt`, `requirements.lock.txt`, `README.md`, `tests/conftest.py`, `tests/test_prescriptions.py`.

Added frontend files: `frontend/src/lib/prescriptions.ts`, `prescriptions.test.ts`, `frontend/src/pages/PrescriptionFlow.tsx`, `PrescriptionFlow.test.tsx`.

Modified frontend files: `frontend/package.json`, `package-lock.json`, `vite.config.ts`, `README.md`, `src/App.tsx`, `src/lib/api.ts`, `src/pages/Analysis.tsx` (compatibility re-export), `src/pages/Landing.tsx`, `src/components/ImageUploader.tsx`, `src/styles.css`.

Existing tracked Python files belonging to teammates are untouched. The source AI worktree was not modified. No branch switch, merge, commit, stage, reset, clean or push was performed.
