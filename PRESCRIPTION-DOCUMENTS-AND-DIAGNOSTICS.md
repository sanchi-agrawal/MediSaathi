# Prescription documents and extraction diagnostics

## Findings

The reported 17-second failure cannot be retrospectively classified. The normal
reader wrapped Google HTTP errors and transport failures in PrescriptionAPIError;
AIIntegration returned the same `api_error` for all of them. No retained normal
server diagnostic for that request was found. Elapsed time does not establish
quota, model, credential or network failure. Planner prefill is a separate
read-only endpoint and does not call or modify extraction.

The existing server environment contains a Gemini key (value never printed) and
model `gemini-3.1-flash-lite`. Installed google-genai 2.33.0 supports the existing
client arguments. Presence and SDK compatibility do not prove key validity,
model access or quota. No live provider request was made in this task.

## Upload and extraction

- Existing authenticated `POST /api/prescriptions` accepts the bounded raw file
  body; `X-MediSaathi-Filename` carries a percent-encoded filename. This retains
  the bounded streaming transport rather than introducing multipart buffering.
- PNG/JPEG retain existing full decode, single-frame, 10 MiB/8-million-pixel
  validation and original bytes sent to the reader.
- PDF: genuine header/EOF and parser validation, unencrypted/unrepaired, 1–3
  pages. Render all pages in a subprocess, maximum 15 seconds, 512 MiB process
  memory, at most 2 million pixels/page and up to 144 dpi. All numbered pages
  go into one existing Gemini request per selected extraction section. Pages
  are never silently omitted or records deduplicated by medicine name.
- DOCX: validate ZIP/main OOXML content type; at most 200 entries, 8 MiB total
  uncompressed, 2 MiB per member, bounded compression ratio and XML node count.
  Reject encryption, unsafe member paths, macros, embedded objects and DTDs.
  Read paragraph/table-cell text in document order without executing content.
- TXT: strict UTF-8 (optional BOM), nonblank, no unsupported binary controls.
  Extracted DOCX/TXT text is at most 256 KiB, passed literally to the same Gemini
  structured extraction and normalization, preserving Hindi and source wording.
- All files: maximum 10 MiB; extension, declared type and detected content must
  agree (empty/octet-stream MIME allowed for browser compatibility).
- Offline fixture/guarded runners remain image-only and explicitly reject
  documents; they never fabricate OCR results for arbitrary files.

Reader public arguments and medicine/instruction schemas are unchanged. A
request-local source context binds validated text/pages to a rendered preview
hash. Existing review, source revision, independent confirmations and ownership
checks still apply. Original document hash/type/name/page count are a sidecar;
strict ten-field medicine records gain no fields. Per-record page citations are
not supported by that schema: pages are labeled at provider input, not invented
as output fields. Cross-page clinical interpretation still requires review.

PDF/DOCX/TXT original bytes are not retained after preparation. Session RAM holds
the rendered preview plus pages or extracted text until replacement, clear,
expiry or process exit. The existing image-restoration endpoint returns a PNG
preview for documents. PDF preview shows page one; text previews show the first
portion, while extraction receives the entire bounded source. Keep the original
file available when reviewing later pages. No documents or records are added to
SQLite or browser localStorage.

Dependencies: PyMuPDF 1.28.2 (AGPL/commercial licensing) and defusedxml 0.7.1.
Review PyMuPDF's license before distributing a deployment; this task does not
change the repository license.

## Safe failure diagnostics

The existing allowlisted smoke classifier is reused while exception context is
still available. Normal extraction persists fixed diagnostic category/stage,
allowlisted exception type, numeric provider status when available, scope and
UTC timestamp to ignored `api/runtime/extraction-errors.jsonl`. No exception
message, body, image, document text, filename, hash, account/session ID, cookie,
header or credential is written. Smoke guards and their records are unchanged.

Provider categories exposed to the UI include `quota_exceeded`,
`authentication_error`, `permission_denied`, `model_unavailable`,
`provider_bad_request`, `provider_error`, `extraction_timeout`, `network_error`.
Existing `configuration_error`, `image_validation_error`, `invalid_response`
(schema failure), `unexpected_error` (internal error) and unknown `api_error`
remain distinguishable. Unknown historical errors are not assigned a guessed
provider status. English/Hindi UI supports the new categories.

No provider/network retry was added. SDK attempts remain one; the existing
single malformed-response validation retry remains bounded and instrumented.
The frontend stops later selected sections after a service/configuration failure
and preserves already successful sections. New OCR still requires Analyze.

## Run the real local application

Stop only the API process you previously started (Ctrl+C), then in PowerShell:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
# Only needed on an environment without the new dependencies:
& $python -m pip install --target "$PWD\api\.venv\deps" 'PyMuPDF==1.28.2' 'defusedxml==0.7.1'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

Second PowerShell window:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

The existing Vite `/api` proxy targets 127.0.0.1:8005. Local HTTP cookie handling
is unchanged. Restart clears temporary prescription workspaces; accounts and
the existing browser-local manual planner are not migrated or modified.

## Verification boundary

Offline tests use synthetic inputs and mocked Google SDK responses, including
real bounded PDF rendering and loopback HTTP signup → upload → analyze → review
→ confirm → restore. The loopback test uses an isolated temporary database and
ephemeral port, not the running account database or port 8005. It verifies the
existing planner-prefill read endpoint remains compatible without changing it.

Browser access host was unavailable. No real browser interaction or live Gemini
document recognition is claimed. Manual check: sign in at localhost:5177, upload
each supported synthetic file, verify no request until Analyze, analyze only when
authorized, review original text/unknowns, save and independently confirm each
section. Check a later PDF page against the original file. On any failure check
the safe category; do not mistake failed/empty/unconfirmed results for success.

Final verification: full Python suite 1,289 passed, one skipped, 13 subtests;
the subsequently added loopback HTTP test separately passed. Frontend 300 passed;
production build passed (existing large-chunk advisory). `git diff --check`
passed. Existing Starlette/httpx deprecation warning remains.

## Exact source files touched in this task

API:
- `api/main.py`
- `api/section_routes.py`
- `api/sessions.py`
- `api/requirements.txt`
- `api/requirements.lock.txt`
- `api/document_worker.py` (new)
- `api/prescription_documents.py` (new)
- `api/extraction_diagnostics.py` (new)
- `api/tests/test_prescription_documents.py` (new)
- `api/tests/test_document_http.py` (new)
- `api/tests/test_extraction_diagnostics.py` (new)
- `api/tests/test_local_real_ocr.py`
- `api/tests/test_prescriptions.py`
- `api/tests/test_diagnostic_readiness.py`
- `api/tests/test_smoke_diagnostics.py`

AI adapter source:
- `medisaathi/reader.py`
- `medisaathi/medication_instructions.py`
- `medisaathi/ai_integration.py`
- `medisaathi/document_input.py` (new)
- `medisaathi/extraction_errors.py` (new)

Frontend:
- `frontend/src/components/ImageUploader.tsx`
- `frontend/src/lib/prescriptions.ts`
- `frontend/src/lib/prescriptionFile.ts` (new)
- `frontend/src/lib/prescriptionFile.test.ts` (new)
- `frontend/src/lib/documentHindi.ts` (new)
- `frontend/src/lib/language.ts`
- `frontend/src/pages/PrescriptionFlow.tsx`
- `frontend/src/pages/PrescriptionFlow.test.tsx`
- `frontend/src/pages/DocumentUpload.test.tsx` (new)

Documentation: this file (new). Existing unrelated worktree changes were retained.
Ignored dependency installs, build/test output and sanitized runtime diagnostics
are not source changes. No account database, scheduler, pricing, expiry, original
AI worktree or persistent attempt guard was changed. No commit or push.
