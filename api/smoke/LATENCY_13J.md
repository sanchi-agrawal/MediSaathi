# Milestone 13J: OCR timing and loading experience

## Available baseline and limits

The retained second-attempt artifact reports HTTP 503 / provider_server_error after **11.38 seconds**. This is a failed diagnostic request, not a successful OCR latency baseline. No retained successful live phase timings were available for this audit, and no new provider call was made. The first historical failure took 2.526 seconds without provider status; neither establishes successful extraction speed.

The registered fictional image is **541 x 721**, **390061 pixels**, **553584 bytes**. Ten local full validation runs had median **4.760 ms**, min 4.417 ms, max 13.160 ms. This is an offline measurement on this machine, not a network/upload/Gemini benchmark. Local decoding of this fixture is small compared with the historical failed-request wait; this does not locate every bottleneck in a successful request.

## Implemented

- Added private, request-local numeric observation in the existing reader: image validation, configuration, normalization, Gemini request and client setup. Observer failure cannot change extraction output/errors. No public signature, prompt, schema, medical field, uncertainty/null behavior or retry contract changed.
- Added API performance metadata for upload/body-read/validation, verified image size/dimensions, Gemini SDK time, client construction, normalization, server extraction and summed server processing. The server processing sum excludes browser network time and the gap between upload/analyze requests; the browser measures click-to-response wall time separately.
- Count accepted Analyze attempts, rejected duplicates for running/succeeded analyses, SDK invocations per attempt/cumulatively, and schema retries. The guarded transport additionally observes physical HTTP requests. Normal-reader SDK invocations are not labelled as independently observed physical sends.
- Added numeric-only allowlisted INFO logger events: no records, image contents/hashes, names, filenames, headers, session IDs, credentials or exception strings. Configure the `api.ocr_metrics` logger at INFO through trusted server logging configuration for console output; response metadata is available regardless. Measurements stay in existing session memory, with no new result cache or persistent medical storage.
- Added a synchronous browser operation lock before React renders its disabled button. Same-tick duplicate clicks cannot create multiple uploads/new analyses. Backend revision/state checks still reject concurrent duplicate work; counters make those rejections visible.
- Added request cancellation/response invalidation on source replacement/unmount. Browser cancellation cannot recall an already delivered Gemini request. No automatic retry or Analyze follows cancellation. New images still need an explicit click.
- Added elapsed seconds, upload/validation and waiting-for-extraction messages, a pending-request explanation after 20 seconds, and completed browser upload/extraction/total timing. No progress percentages or ETA claims. Confirmation/explanations remain invalidated by source/record edits.
- Removed one redundant backend snapshot copy during revision validation; current-analysis checks remain under the session lock.

## Retry and duplicate findings

Normal reader SDK retry attempts remain 1, with no API/quota/network retry. One additional generate_content invocation is allowed after malformed JSON/normalization failure. Offline tests demonstrate two SDK invocations and one schema retry in that case. Historical telemetry cannot show whether a particular successful live extraction used it; new counters will.

The consumed 13H context remains limited to one SDK invocation/physical send, with its guards untouched. Error text distinguishes explicit user retry from automatic API/network retry and warns against retrying a consumed guarded attempt.

Rerenders, elapsed updates and image previews do not trigger extraction. The same-analysis backend guard existed already; the frontend lock closes the pre-render window in which duplicate uploads could create separate analysis IDs.

## Pending optimization decisions

The reader constructs/closes a Gemini client per extraction, preventing connection-pool reuse on later extractions. Setup time is now measured. No shared cross-user client or credential cache was introduced. Evaluate lifecycle, credentials, threading and measured overhead before reuse; reuse does not shorten first-request provider inference.

No prompt edits, model switch, output-schema changes, new OCR engine, silent cache, image transform or weakened limits. The fixture is small; additional compression/resizing risks small strength/dosage text and breaks its registered hash. For unusually large future images, evaluate a user-visible fictional candidate with side-by-side text-legibility checks and explicit authorization before implementing transformations. Preserve original bytes and review safeguards.

## Verified versus expected

Final checks: **898 combined Python tests passed, 21 frontend tests passed, production build/TypeScript checks passed**. One non-failing Starlette test-client deprecation warning remains. Windows denied pytest's shared temporary directory on one run; rerunning in a fresh ignored workspace-local virtual-environment directory passed. No medical/app failure was hidden by that test-infrastructure rerun.

Verified offline: one upload/Analyze on same-tick duplicate clicks; one extractor invocation for concurrent duplicate API requests; elapsed updates without retries; isolated numeric telemetry detects schema retries; original ten-field/null and confirmation behavior passes offline tests.

Expected: less wasted work from accidental submissions and clearer pending-request feedback. **No verified improvement to live Gemini inference or successful live end-to-end latency is claimed.**

## Next controlled benchmark (fresh authorization required)

Preserve both consumed guards/artifacts. Register and authorize one new request using the same fictional PNG, model, prompt and schema, no schema retry, and the timing code loaded. Capture browser/API phase times, SDK/physical-call counts, status and retry count without logging medical content. A successful request establishes a phase baseline, not median/p95 or a speedup. A before/after comparison requires separately authorized matched calls and field-by-field correctness review before compression, prompt changes or client reuse. No benchmark was run here and no server was restarted.

## Exact changed files

- `medisaathi/reader.py` (private telemetry only; user-owned AI module)
- `api/ocr_metrics.py` (new)
- `api/main.py`
- `api/sessions.py`
- `api/smoke/second_attempt.py` (timing hooks only; guard/single-call cap unchanged)
- `api/tests/test_ocr_metrics.py` (new)
- `frontend/src/lib/prescriptions.ts`
- `frontend/src/pages/PrescriptionFlow.tsx`
- `frontend/src/pages/PrescriptionFlow.test.tsx`
- `api/smoke/LATENCY_13J.md` (this report)

No teammate scheduling/pricing/Streamlit file, credential file, consumed guard or historical diagnostic artifact was modified. No stage/commit/merge/push or provider request occurred.
