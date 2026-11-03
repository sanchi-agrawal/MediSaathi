# Association confirmation and scheduling synchronization

## Reproduced defects

Instruction confirmation sets `confirmed_revision` but does not change the instruction revision. Prescription Review previously keyed its association panel only by medicine/instruction revisions. If it mounted after medicine confirmation but before instruction confirmation, it retained the old `ready=false` context even after the instruction was confirmed. A UI regression now confirms the instruction at the same revision and asserts the panel reloads immediately.

The panel also swallowed the concrete association error, used its cached scheduling revision, and relied on the POST response without reading back the active workspace. It did not notify an already-mounted Schedule page after a successful association. Those gaps made stale/failed linking hard to distinguish from successful persistence.

No private browser cookie or live prescription payload was inspected. These are offline-reproduced code defects; they do not prove which exact response the user's existing authenticated browser received. The current non-reloading API process must be restarted to load backend changes. It has intentionally not been stopped because restart discards its temporary prescription workspaces.

## Fixed request and state transitions

1. Review both scopes and explicitly confirm them independently.
2. The association panel reloads when instruction confirmation changes, even with an unchanged revision.
3. Before POST, fetch `/api/scheduling/current`. Reject changed analysis/source revisions or missing confirmation; use the current scheduling revision.
4. POST `/api/prescriptions/{analysis_id}/associations` with only medicine_revision, instruction_revision, scheduling_revision, medicine_ref and instruction_id. The normal origin/action header and auth cookie remain required.
5. Check the returned pair, then GET current state and verify the same pair and previous links remain. Only then show a success message and checkmarked source instruction.
6. Notify mounted Schedule views and other tabs to refresh through a PHI-free in-memory event. Own-tab broadcasts are deduplicated. No extraction/provider request is triggered.

The API rejects duplicate pairs (`association_exists`) and reused records (`association_conflict`) with HTTP 409, before consuming an event or changing valid links. Correcting a pair requires an explicit clear-all-links/schedules action. Ambiguous suggestions are never automatically approved; a deliberate manual selection remains possible under the existing independent confirmation gates.

## Safety limits

A saved association is not schedule approval. The example `1-0-1` remains unsupported by AIIntegration's existing schedule safety gate. It is not translated into morning/night doses. Source records whose original medicine `needs_review` flag remains true are also refused by the unchanged engine; preparation now reports this before generation rather than offering a misleading ready state. No source flag is cleared automatically, and the original read-only flag contract has not been changed. Resolving that flag through a new verified workflow is outside this fix.

Unambiguous supported confirmed records generate schedules using only a selected start date, through existing review/approval endpoints. Edits conservatively invalidate all related associations/schedules, not just one medicine. Accounts, Argon2 hashing, opaque auth tokens, Gemini configuration, OCR contracts and scheduling engine source remain unchanged. No Gemini or notification requests were made.

## Verification

- Offline API integration uses fictional Dolo/Cetirizine/Omeprazole records, mocked extractors and actual local authentication. It checks independent confirmation, exact saved pair IDs and revisions, current-state restoration, separate date-only schedules, invalidation, duplicates, conflicts and stale requests.
- UI tests cover unchanged-revision confirmation, verified POST/GET persistence, failure messages, mounted Schedule refresh, submitted fields, and Hindi/light-theme source preservation. Existing dark-theme tests remain.
- Automated tests are HTTP/TestClient and jsdom verification, not a human browser test or live OCR benchmark.

## Files changed

- `api/downstream_routes.py`
- `api/downstream/automatic.py`
- `api/tests/test_downstream.py`
- `api/tests/test_association_persistence_flow.py`
- `frontend/src/components/ScheduleAssociations.tsx`
- `frontend/src/components/ScheduleAssociations.test.tsx`
- `frontend/src/lib/workflowEvents.ts`
- `frontend/src/lib/scheduling.ts`
- `frontend/src/lib/scheduling.test.ts`
- `frontend/src/lib/language.ts`
- `frontend/src/lib/scheduleHindi.ts`
- `frontend/src/pages/PrescriptionFlow.tsx`
- `frontend/src/pages/PrescriptionSections.test.tsx`
- `frontend/src/pages/Schedule.tsx`
- `frontend/src/pages/Schedule.test.tsx`
- `ASSOCIATION-SAVE-FIX.md`

Ignored editing helpers were used under `api/.venv`; no files were staged or committed. Restart commands are in REAL-OCR-STARTUP.md. Do not trigger new OCR just to test navigation/restoration of an existing valid workspace.
