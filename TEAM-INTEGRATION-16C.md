# Milestone 16C — additive team integration

Date: 2026-10-31. Worktree: `C:\Users\ASHTAMI\MediSaathi-TeamIntegration`.
Branch: `integration/team-16b`. HEAD remains
`ca54919d2a2d020fc2798ff5ce6ceccc4351972b`. Nothing staged or committed.

## Implemented behavior

- Confirmed medicines can explicitly request Person 2 catalogue candidates on My
  medicines. Known salt/strength/form/release conflicts are rejected. Missing
  details remain review-required. All choices are separate from the strict ten
  source fields, namespaced as `person2:catalogue:...`, and require a separate
  selection click. Selection is bound to the current server session, analysis and
  medicine revision. Returning to My medicines restores that selection without OCR.
  Example catalogue identities are unverified even when selected. No cheaper
  alternatives or medical substitutions are enabled.
- Medicine pricing and Lab costs expose the audited dataset's exact read-only
  lookup. Catalogue IDs here belong to the audited dataset and are never joined
  automatically to Person 2 IDs. Known items show **No verified Delhi price
  available**. Ambiguous identities, missing items and service failures are
  distinct. Raw source medicine/test names, specimens, variants and unknowns
  remain unchanged in the prescription and Investigations workspace. No lab test
  is inferred or equated to another test. No comparison, fee, saving, basket or
  alternative recommendation is enabled. Audited verified Delhi quotes: **0**.
- Approved schedules expose **Reminder Preview — Notifications not enabled.**
  Every active slot needs an explicitly entered user clock preference. No clock
  is derived from morning/night. Entries use Asia/Kolkata (+05:30), the current
  server date/time, approved doses and approved course dates, covering at most
  seven upcoming days. Completed courses have no upcoming entries. Refill notes
  reuse Person 3's pure `refill_alerts()` function. No SQLite connection, global
  dose-log replacement, dose marking, polling, outbound sender or Telegram call.
  Preferences/previews are not saved; returning requires explicitly preparing a
  new preview. Schedule results themselves restore from the existing session.
- New panels retain the existing styling and provide Hindi headings/help where
  implemented. Existing English/Hindi/Hinglish prescription explanations are
  unchanged. The whole dashboard is not claimed to be fully translated.

## API contracts

All existing cookie, Origin/action-header, no-store, session TTL, independent
confirmation and revision protections remain. No new authentication is claimed.

| Route | Behavior |
| --- | --- |
| GET `/api/matching/current` | Restore current confirmed medicine candidate state |
| POST `/api/prescriptions/{id}/matching` | Explicit identification, body `{revision}`; repeated current request retains selection |
| POST `/api/prescriptions/{id}/matching/selection` | `{revision, medicine_ref, candidate_id}`; only current server-offered candidates accepted |
| GET `/api/pricing/catalogue?kind=medicine\|lab` | Audited identity catalogue and zero verified quote count |
| POST `/api/pricing/lookup` | `{kind, item_id}` or `{kind, name}`; exact lookup, availability only |
| POST `/api/prescriptions/{id}/reminder-preview` | Current medicine/instruction/scheduling revisions, association ID and explicit `clock_times` |

Request schemas forbid extra fields. Preview clients verify response bindings and
refuse stale results. Source changes clear matching state and revoke scheduling;
plan/association changes invalidate previews through scheduling revisions and UI
remounts. Scheduling, AI extraction, assistant and confirmation contracts remain
unchanged. Only the already-approved server-side schedule supplies preview doses.

## Pinned imports and provenance

`api/vendor/provenance.json` lists 32 exact imported files and SHA-256 hashes.
They were verified byte-for-byte against Git, not copied from teammates' dirty
working directories:

- Person 2 `5758fb01a164c13e0f38735ec83fadea2d4f890c`: matcher, its example medicine
  catalogue and manual matcher test. No example pharmacy settings, pharmacy price
  CSV, basket optimizer or alternatives module is imported or enabled.
- Person 3 `e95a03166779fe2dbe501e868f9e8b4ee3025360`: unchanged reminders module and
  companion tests. Only the pure refill helper is used by the API.
- Audited dataset `3f9664b`: unchanged Python lookup/audit/workflow, tests,
  manifest-bound catalogues/observations/evidence and handoff documentation.
  Provisional/conflicting observations remain audit evidence, never price results.
  Audit/export CLI functions are not called by API routes.

No `medisaathi/` file changed. Original frontend is clean at its checkpoint;
original AI/pricing working files were not written. Five original runtime
guard/authorization/result files were verified unchanged. No secrets, images,
database, build output or runtime authorization is proposed as source.

## Verification

- Full offline Python suite: **1,037 passed, 1 skipped**, 13 subtests passed. One
  existing Starlette/httpx deprecation warning. The skipped diagnostic-readiness
  test requires the original local attempt artifact, intentionally absent from
  this isolated checkout; original guards were not copied or reset.
- Unchanged Person 3 reminder companion tests: **22 passed**, fake senders and
  in-memory SQLite only. These test the vendor module, not enabled API persistence.
- Unchanged Person 2 matcher script: **3 checks passed**.
- Frontend: **105 passed across 16 files**.
- TypeScript and production build: passed. Existing lazy anatomy chunk warning
  remains (~642 kB uncompressed / 165 kB gzip). No model/landing redesign.
- FastAPI TestClient fictional flow: upload, explicit extraction, separate section
  review/confirmation, Hindi/English/Hinglish, catalogue selection, association,
  plan save/approval, real schedule engine, reminder preview, separate strip
  save/confirmation, navigation state reads, stale and cross-session rejection.
- Actual HTTP: frontend returns 200 at `localhost:5175`; proxied `/api/demo-info`
  reaches the offline fixture on `127.0.0.1:8002` and reports Gemini/delivery false.
- **No actual browser interaction or screenshot inspection performed.** HTTP and
  jsdom results do not establish browser cookie acceptance, camera behavior,
  keyboard/touch rendering, anatomy visual acceptance or hard-refresh behavior.
- No Gemini, model-listing or Telegram request was made.

Confirmed defects fixed during implementation: native Python scheduler dates
were initially treated as ISO strings by the new preview adapter; the adapter
now handles both validated native dates and ISO representations. A Windows
helper's default encoding corrupted route/test punctuation; affected files were
rewritten with explicit UTF-8 while preserving checkpoint content. Standard Vite
environment types were added for the offline-mode notice.

## Run the already-prepared OFFLINE demo

Two separate PowerShell terminals. Do not run these on top of existing listeners.
The isolated offline demo is already running at the end of this milestone; these
are restart commands. No browser was opened automatically.

Backend (uses installed dependencies read-only from the existing interpreter;
rapidfuzz was installed separately under this worktree's ignored dependency path):

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH = "$PWD\api\.venv\deps"
$python = 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -m api.demo_fixture --write-fixtures
& $python -m uvicorn api.demo_fixture:app --host 127.0.0.1 --port 8002 --no-access-log
```

Frontend:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8002'
$env:VITE_MEDISAATHI_OFFLINE_DEMO = '1'
npm.cmd run dev -- --port 5175 --strictPort
```

Open `http://localhost:5175/dashboard/analysis`. The banner explicitly labels
mocked OCR. Fixture backend blocks Google SDK client construction, accepts only
the registered fictional prescription, and has a separate
`medisaathi_team16c` Secure/HttpOnly/SameSite=Strict cookie. Normal session cookies
are ignored and not overwritten. No credential file is loaded. Generated fixtures:

- `api/.venv/demo16c/fictional-prescription.png`
- `api/.venv/demo16c/fictional-strip.png`

For an independent environment, create a virtual environment inside this worktree
and install `api/requirements.txt`; use its Python instead. Frontend dependencies
are already copied locally; on another computer use `npm.cmd ci` under frontend.

Normal API entrypoint remains `api.main:app`, default port 8000 and allowed UI
origin 5173. It is separate from the offline demo. Gemini stays server-side; a
fresh authorization is required before any further live provider test. Remove
the offline UI flag and use the correct proxy target when intentionally switching
to the normal API. No live setup was exercised here.

Offline checks:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH = "$PWD\api\.venv\deps"
& 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp api/.venv/manual-tests
cd frontend
npm.cmd test
npm.cmd run build
```

## Five-minute fictional demo / browser acceptance checklist

1. **0:00–1:00:** Open the labelled offline URL; upload the fictional prescription,
   select medicines/instructions/investigations, click Analyze explicitly. Save
   and confirm each section separately. Unknown specimen/variant stays unknown.
2. **1:00–1:45:** Request Hindi, then English/Hinglish. Navigate My medicines;
   explicitly find candidates, inspect review warnings, select one. Navigate away
   and back; the server selection should restore. Refresh the page and verify the
   same confirmed workspace without another Analyze click.
3. **1:45–2:30:** Open Medicine pricing and Lab costs; choose exact audited items.
   Show the no-verified-Delhi-price result and disabled comparison. Do not equate
   the example catalogue ID with the audited dataset's similarly named ID.
4. **2:30–3:45:** On Schedule, explicitly associate medicine_001/instruction_001.
   Enter dose 1 tablet, duration 3 days, tomorrow as start, morning/night slots.
   Save, acknowledge, approve. Verify 2 tablets/day, 6 total, end start+2 days.
   Enter your own preference times (e.g. 08:15 and 20:30), then explicitly preview.
   Explain that these times are preferences; notifications are disabled.
5. **3:45–5:00:** Edit a schedule input and verify preview/result disappear.
   Then edit a source medicine; confirmation and scheduling must revoke. Open
   Expiry Scanner, upload the separate fictional strip, analyze/save/confirm.
   Verify month precision remains August 2027 without a fabricated expiry day or
   safe-to-take judgment. Prescription and strip stay separate.

## Remaining limitations

Browser acceptance above is pending. Accounts are still demo-only; session RAM
expires and does not survive API restart. No verified quotes, price comparison,
cheaper alternatives, real notification delivery or dose-status persistence.
Candidates require review and do not authorize substitution. Source schedule
ambiguity remains blocked by the existing safety gate. Camera/real OCR/manual
browser testing and GPU visual QA were not performed. The current original
backend/guard processes were not stopped or changed.

## Exact changed/source inventory

The inventory below includes this report; ignored dependencies, logs, PNGs,
scratch helpers, build output and test caches are intentionally excluded.

- TEAM-INTEGRATION-16C.md
- api/demo_fixture.py
- api/main.py
- api/requirements.txt
- api/sessions.py
- api/team_matching.py
- api/team_models.py
- api/team_routes.py
- api/tests/test_team_integration.py
- api/vendor/__init__.py
- api/vendor/person2/__init__.py
- api/vendor/person2/data/medicines.csv
- api/vendor/person2/matcher.py
- api/vendor/person2/test_matcher_manual.py
- api/vendor/person3/__init__.py
- api/vendor/person3/reminders.py
- api/vendor/person3/tests/test_reminders.py
- api/vendor/provenance.json
- frontend/src/App.tsx
- frontend/src/components/DashboardLayout.tsx
- frontend/src/components/MedicineMatching.tsx
- frontend/src/components/OfflineDemoNotice.tsx
- frontend/src/components/ReminderPreview.tsx
- frontend/src/lib/team.ts
- frontend/src/pages/CurrentWorkspace.tsx
- frontend/src/pages/Pricing.tsx
- frontend/src/pages/Schedule.tsx
- frontend/src/pages/TeamIntegration.test.tsx
- frontend/src/vite-env.d.ts
- frontend/vite.config.ts
- pricing_dataset/.gitattributes
- pricing_dataset/.gitignore
- pricing_dataset/HANDOFF.md
- pricing_dataset/MILESTONE-15B.md
- pricing_dataset/README.md
- pricing_dataset/__init__.py
- pricing_dataset/access_log.csv
- pricing_dataset/audit.py
- pricing_dataset/audit_reviews.json
- pricing_dataset/collection_report.md
- pricing_dataset/collection_targets.csv
- pricing_dataset/coverage.json
- pricing_dataset/coverage_report.md
- pricing_dataset/evidence/1mg-list.json
- pricing_dataset/evidence/apollo-cbc.json
- pricing_dataset/evidence/pe-dolo.json
- pricing_dataset/evidence/pe-labs.json
- pricing_dataset/lab_catalogue.csv
- pricing_dataset/lab_prices.csv
- pricing_dataset/lookup.py
- pricing_dataset/medicine_catalogue.csv
- pricing_dataset/medicine_prices.csv
- pricing_dataset/observation_audit.json
- pricing_dataset/test_integration.py
- pricing_dataset/test_workflow.py
- pricing_dataset/verified_quotes.json
- pricing_dataset/workflow.py
- pytest.ini
