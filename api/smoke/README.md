# Milestone 13F: guarded real Gemini smoke test

**Current attempt: consumed and failed. Do not click Analyze/Retry or restart a live attempt.** See [FAILURE_REPORT.md](FAILURE_REPORT.md). The launch/manual steps below document setup; they are not authorization to repeat the request or remove the guard.

## Root cause and fix

`fictional_demo.png` is a valid PNG: 541 x 721, 390061 pixels, one frame, 553584 bytes. Pillow verify, full decode and the existing `reader._validate_image` all pass. It matches the committed fictional fixture from `2e6eee1`.

The old mock runner compared the upload's SHA-256 against the exact PNG file bytes. A losslessly re-encoded copy had identical pixels and passed real image validation, but failed that extra allowlist and raised `reader.ImageInputError`. AIIntegration consequently displayed a misleading generic image-validation error. Reproduction against the old running mock server: committed bytes succeeded; a valid re-encoding passed upload and failed extraction with `image_validation_error`.

The frontend sends the original `File` as raw image bytes, not multipart or JSON. FastAPI streams those bytes with a hard 10 MiB cap. Preview zoom/rotation does not alter them. No transport transformation was found; the observed error occurs in the mock runner's extra fixture policy after upload.

The corrected smoke runner validates the unchanged format/byte/pixel/frame/decode rules, then compares decoded dimensions and RGBA pixel identity. Lossless re-encoding is accepted. A different image is rejected before extraction with `smoke_fixture_required` and clear instructions, rather than claiming the image is corrupt. The exact local file chosen in Chrome was not inspected; this reproduction establishes the runner defect, not the identity of the user's previous upload.

The fixture restriction applies only to this controlled smoke runner. The regular API continues to accept PNG/JPEG using the original backend rules. Use the provided PNG for this test; a lossy JPEG conversion can change pixels and fail the smoke policy.

## Start REAL mode

From `C:\Users\ASHTAMI\MediSaathi-Frontend`:

```powershell
api/.venv/Scripts/python.exe -m api.smoke.server --mode live --credentials-file C:/Users/ASHTAMI/MediSaathi/medisaathi/.env
```

This reads only `GEMINI_API_KEY` and `GEMINI_MODEL` from the existing original-worktree `.env`, filling absent Python-process environment variables. It does not copy or edit `.env`, expose keys, or add frontend environment variables. It verifies configuration locally without calling Gemini. Startup prints key presence and the configured model identifier, never the key. An existing process environment takes precedence over the supplied file.

In another terminal:

```powershell
cd C:/Users/ASHTAMI/MediSaathi-Frontend/frontend
npm.cmd run dev
```

Use **http://localhost:5173/dashboard/analysis**. Vite forwards `/api` to the sole loopback API on port 8000. `/api/smoke/status` reports the actual mode, configuration presence, model and whether the one live allowance remains. It never exposes the key. No startup, status, session, upload, review, confirm or explanation action starts extraction.

`uvicorn api.main:app` is the normal unguarded API, not the command for this test. `--mode mock` is explicitly mocked extraction, not real Gemini. Live mode has no mock fallback.

## Manual browser steps — no browser automation performed

1. Reload the prescription page. The old mock server's session and analysis IDs no longer exist; do not retry a stale result from that server.
2. Choose **Upload image** and select exactly `C:\Users\ASHTAMI\MediSaathi-Frontend\api\smoke\fictional_demo.png`. It is labelled fictional and contains no real patient information.
3. In Chrome DevTools Application/Cookies, check the `medisaathi_demo` cookie after the Analyze action creates the session: Secure, HttpOnly, SameSite Strict, path `/api`. Do not share the cookie value. The backend preserves all flags. Actual Chrome cookie acceptance has not been inspected; HTTP header checks alone do not establish browser acceptance. Localhost relies on the browser's Secure-cookie exception; non-local deployment requires trusted HTTPS.
4. Click **Analyze with AI once**. This is the only step permitted to call real Gemini. No request has been sent by the agent.
5. If extraction succeeds, compare all ten fields with the image, preserve unknowns, save review, acknowledge, confirm, and request English/Hindi/Hinglish explanations.
6. Test an edit: confirmation and explanations must clear. Save and explicitly confirm again before explaining.
7. A different image must clear prior state; this guarded test will reject other pixels with `smoke_fixture_required`. Do not attempt a second live analysis.
8. On quota/network/API failure, stop and report the safe category. No automatic API retry or mock fallback occurs. The allowance stays consumed even if the request fails. The existing reader's schema-validation retry behavior is unchanged; it never retries quota, network or API errors.

## One-attempt protection

Live mode exclusively creates `api/smoke/live_result.json` **before** entering reader extraction. Thread locking and exclusive file creation prevent multiple invocations, including across process restarts. An existing marker prevents a new live runner from starting. Do not remove/reset the marker to obtain another attempt. It is ignored by Git and contains only the permitted fictional result metadata, never secrets or raw provider errors. Quota availability is not established by the configuration check; only the user's single request can establish provider availability.

## Verification for this fix

- 34 API tests pass, including fixture decoding, lossless re-encoding, explicit policy rejection, byte preservation, unchanged limits, credential loading, and consumed allowance after success/failure.
- 825 combined Python tests pass; one non-failing Starlette test-client deprecation warning.
- 19 frontend tests pass, including sending the original File unchanged.
- Frontend TypeScript/production build passes.
- Running Vite proxy reaches the live-mode status endpoint. HTTP session headers retain Secure/HttpOnly/SameSite Strict; explicit HTTP cookie reuse and upload work. This is not a Chrome cookie test.
- Zero live OCR analyses performed. Actual model access/quota, extraction accuracy and genuine browser confirmation remain for the user's click/review.

Changed files for this fix: `api/main.py`, `api/.gitignore`, `api/smoke/server.py`, `api/tests/test_smoke.py`, `frontend/src/lib/prescriptions.test.ts`, `api/README.md`, and this `api/smoke/README.md`. No original AI module, teammate scheduling/pricing file, credential file or Git history was changed.
