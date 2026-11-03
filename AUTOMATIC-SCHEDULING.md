# Date-only scheduling from confirmed source records

The old UI duplicated dose/unit/duration/slot data in a manual plan. `unsafe_schedule` correctly rejected plans that did not match confirmed source text, including missing fields, unsupported abbreviations or inconsistent slots. Removing those safety checks would not fix missing clinical information.

The new Schedule page shows read-only confirmed details and a blank start-date picker. Generate My Schedule is an explicit approval of those displayed inputs. It re-fetches current confirmations/revisions, then uses the existing plan-review and approval routes for each explicitly linked medicine. The server still creates acknowledgement events; browser approval claims are not trusted.

## Association data-flow fix

The reported all-Unknown display is reproducible when confirmed instruction records exist but no explicit association has been saved: the old screen only looked up instructions through an association, then rendered null placeholders. This does not prove an individual's instruction section was extracted or confirmed; medicine extraction is a separate scope and the analysis UI initially selects medicines only. No user cookie or live patient record was inspected to infer missing clinical data.

The scheduling response now includes `instruction_state` (extraction/review/confirmation) and read-only `association_proposals`. When both scopes are current and confirmed, an exact unique medicine-name match (case/whitespace normalization only), also present in the instruction source, proposes a pair. Duplicate names, multiple instructions, unmatched names and already-used instructions are never auto-approved. The user explicitly confirms each displayed proposal through the existing revision-bound association POST. There is no association side effect on GET, page load, translation or OCR completion.

Review now shows extraction/confirmation prerequisites even before instructions are confirmed. Scheduling no longer labels all clinical details Unknown for an absent link; it explains whether a confirmed instruction is missing or awaits link approval. After server approval, the existing linked-record projection supplies read-only dose/unit/frequency/timing/duration. Missing dose quantity and unit have separate blockers and field links. No extra extraction or Gemini request is triggered by this fix.

Files modified for this follow-up: `api/downstream/association_proposals.py`, `api/downstream/automatic.py`, `api/downstream_routes.py`, `api/tests/test_association_proposals.py`, `api/tests/test_automatic_schedule.py`, `frontend/src/components/ScheduleAssociations.tsx`, `frontend/src/components/ScheduleAssociations.test.tsx`, `frontend/src/lib/scheduling.ts`, `frontend/src/lib/scheduleHindi.ts`, `frontend/src/pages/PrescriptionFlow.tsx`, `frontend/src/pages/Schedule.tsx`, `frontend/src/pages/Schedule.test.tsx`, `frontend/src/pages/BilingualWorkflow.test.tsx`, and this document. Ignored local editing helpers remain under `api/.venv`.

Explicit medicine–instruction selection now lives at the bottom of Prescription Analysis, after both scopes are independently confirmed. Multiple one-to-one pairs are retained without name-based matching. Adding/changing a pair clears prior schedule results; prescription edits clear links and approvals through the existing invalidation path.

`GET /api/scheduling/current` additively returns `associations`, `automatic` candidate templates/blocking codes, and `course_results`. Templates omit start date. Preparation reads only confirmed records and invokes the existing private `AIIntegration._schedule_request` safety validator without consuming an event, running the engine, or generating a schedule. A current-date probe is used solely for validation and is never returned as a proposed course date. This dependency on a private validator is isolated in `api/downstream/automatic.py`; changes to that internal contract require regression testing.

The strict ten medicine fields and independent instruction payload are unchanged. No doses come from strength; no time slots come from abbreviation alone. Missing values have no defaults. The unchanged gate supports only its existing literal English slots and BD/BID/TDS/TID/QID/HS forms with consistent source evidence. Hindi UI support does not silently normalize unsupported Hindi clinical instructions; such cases remain blocked. Fractions, ranges, tapers, PRN/OD and ambiguous clock times remain unsupported.

The shared selected start date applies to all linked medicines in this course. Different start dates require separate course handling, which is not implemented. Each approved medicine keeps its own dose, slots and duration. Multi-medicine calculations use sequential guarded requests, not an atomic transaction; a later failure may leave earlier valid calculations server-side. The UI hides results on failure and offers state refresh, never inventing completion. Reminder preferences remain a separate optional preview using the currently active approved result; no notification delivery is enabled.

Review links target the unresolved instruction field or explicit-association section. English/Hindi labels and localized calculated dates are provided; original clinical source strings and names remain unchanged. Results use time-of-day slots, not invented clock times. The optional reminder preview is unchanged and accepts explicit user clock preferences separately.

Tests use fictional records and mocked extractors only. Human browser visual verification and live OCR are not part of this change. Local account storage, authentication, Gemini configuration, original scheduling engine and diagnostic attempt guards are unchanged. Medical workspaces remain temporary server memory. Restart the existing API with the real/offline command documented in REAL-OCR-STARTUP.md to load the new backend routes; startup makes no provider call.

## Files changed for this workflow

- `api/downstream/automatic.py`
- `api/downstream_routes.py`
- `api/tests/test_automatic_schedule.py`
- `frontend/src/components/ScheduleAssociations.tsx`
- `frontend/src/components/SectionReview.tsx`
- `frontend/src/lib/scheduling.ts`
- `frontend/src/lib/scheduleHindi.ts`
- `frontend/src/lib/language.ts`
- `frontend/src/pages/Schedule.tsx`
- `frontend/src/pages/Schedule.test.tsx`
- `frontend/src/pages/PrescriptionFlow.tsx`
- `frontend/src/pages/BilingualWorkflow.test.tsx`
- `frontend/src/pages/WorkspaceRestore.test.tsx`
- `AUTOMATIC-SCHEDULING.md`

An ignored editing helper under `api/.venv/update_schedule.py` was used locally; it is not application source. No files were staged or committed. Verification: 1,143 Python tests passed, one skipped, 13 subtests passed; frontend tests and production build also passed. The build retains its existing bundle-size warning.
