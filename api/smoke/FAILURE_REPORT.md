# First live attempt: read-only diagnosis

## Confirmed evidence

- The original `live_result.json` records `mode=live`, one extractor invocation, `status=failed`, `error_type=PrescriptionAPIError`, latency 2.526 seconds.
- The existing server output only says the live attempt failed in 2.526 seconds and the allowance was consumed. It has no provider HTTP status, SDK exception type or sanitized provider category.
- A read-only `/api/smoke/status` check confirms the existing live process has Gemini configuration, reports model `gemini-3.1-flash-lite`, and has no remaining live attempt. No analysis/retry endpoint was invoked during diagnosis.
- The guard file's SHA-256 was checked before and after investigation and remained unchanged. It was not reset, overwritten, deleted or supplemented with guessed diagnostics. The server was not restarted; no upload/review/confirmation mutation was made.

## What can and cannot be concluded

The known failure is inside the reader's Gemini API/transport boundary. `reader.read_prescription` translates both `google.genai.errors.APIError` and `(httpx.HTTPError, ConnectionError, TimeoutError)` into `PrescriptionAPIError`. Its original underlying exception is suppressed from ordinary traceback display with `raise ... from None`. The prior smoke runner recorded only the translated exception type.

`AIIntegration._safe_error` maps that exception to `api_error`. It does not distinguish prescription quota/network failures as the instruction/investigation exception classes do. The FastAPI analyze handler returns the failed section snapshot; the generic UI message is therefore not itself a provider HTTP error code.

The recorded failure does **not** identify quota/rate limits, model/resource availability, authentication/permissions, bad request arguments, network/timeout, or provider server failure. The provider HTTP status is unavailable. No specific cause should be asserted from the 2.526-second duration.

The final error is not classified as an image error, reader configuration error, `ModelResponseError`, invalid normalized payload, or unexpected FastAPI exception. That narrows the final failing boundary, but cannot rule out an earlier invalid response followed by the reader's existing schema-validation retry before this API/transport error. One extractor invocation is not proof of exactly one physical HTTP request.

The live process was launched with `gemini-3.1-flash-lite`, and the unchanged reader passes its configured model directly to `generate_content(model=model, ...)`. No fallback model exists in that path. This establishes the selected model, not that the provider accepted it. The request-attempt path was entered; whether a request reached Google's service or a response was received cannot be proved from the retained diagnostics, because transport errors produce the same exception.

No live correction/retry is justified by a confirmed root cause yet. The diagnostic gap is confirmed; a quota/model/network fix is not. Any future live request needs new explicit authorization and a separate deliberate guard policy. This investigation does not grant that authorization or reset the current guard.

## Narrow diagnostic improvement (offline only)

Added `api/smoke/diagnostics.py`. While a future exception is actively being handled, it inspects a bounded `__cause__`/`__context__` chain and retains only allowlisted categories and numeric HTTP status. Python retains context even with `from None`; the old completed exception cannot be reconstructed after it has been discarded.

Categories distinguish quota (429), authentication (401), permission (403), model-or-resource availability (404), bad request (400, deliberately ambiguous), provider server errors, network/timeout, response validation, local configuration/image validation, and unknown backend errors. No exception messages, response bodies, tracebacks, headers, cookies, images or credentials are serialized. Public AI module contracts and UI failure categories are unchanged.

The smoke runner records/logs this safe object for future handled failures. The existing live process was left intact and has not loaded this source change; these additions cannot retroactively diagnose its first failure or enable another attempt.

## Changed files

- `api/smoke/diagnostics.py` (new)
- `api/smoke/server.py` (sanitized diagnostics at the existing catch boundary)
- `api/tests/test_smoke_diagnostics.py` (new offline synthetic-exception regressions)
- `api/smoke/README.md` (consumed-attempt notice)
- `api/smoke/FAILURE_REPORT.md` (this report)

The original reader, AIIntegration, FastAPI adapter, teammate code, credential files, and original attempt record are unchanged. No external API request, browser automation, commit, merge, push, or guard reset occurred.
