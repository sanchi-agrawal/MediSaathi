# Milestone 14B: reviewed local source checkpoint

This checkpoint preserves milestones 13D through 13L on feature/ai-frontend, based on fe578ef. It does not integrate scheduling, pricing or reminders and does not authorize any provider request. No teammate tracked implementation or original AI worktree file is changed.

## Provenance and review

The six AI modules and their six test suites originated at feature/ai-pipeline commit 2e6eee1. Five modules and all six suites still match that commit after newline normalization. reader.py additionally contains the reviewed 13J request-local numeric timing hooks; public signatures, prompts, schemas, null semantics, confirmation and retry behavior are retained. See smoke/LATENCY_13J.md.

The only binary is smoke/fictional_demo.png: visually verified fictional, no patient identifiers, fully decoded PNG with no EXIF. Its only PNG metadata is numeric dpi/gamma/srgb rendering information. No real medical image is included. The local candidate scan found no credential/token/private-key literal; the session cookie-name constant is not a cookie value or authentication credential.

The API/frontend ignore rules exclude environment variants. The whole smoke/attempts directory is ignored, including the previously visible guard.json. Original and second-attempt guards, consumed markers, authorizations and diagnostic outcomes remain on disk and are excluded; their checksums must remain unchanged. Historical smoke reports are documentation, not authorization to rerun them. A fresh checkout will not contain those guards and must not be treated as inheriting an old live allowance.

Other excluded artifacts: api/.venv (including local audit scripts and test temporary directories), node_modules, frontend/dist, TypeScript incremental output, Python/pytest caches, local environment files, and temporary diagnostic output. No runtime cookies, tokens, provider responses or session images are included.

## Verification and limits

Checkpoint verification passed: 926 combined offline Python tests, 39 frontend tests, TypeScript/Vite production build, staged whitespace check and staged credential/path review. The Python run retains one non-failing Starlette test-client deprecation warning. All five existing runtime guard/authorization/result files retained their original checksums. The commit identity is reported with the checkpoint delivery.

The existing API tests block live client/network access and the AI suites use mocks. No live Gemini call or browser verification belongs to this checkpoint. Existing demo-auth, in-memory session and API-vs-internal invalidation limitations remain as audited in 14A. The duplicate SectionReviewRequest declaration is preserved here; no functional cleanup is mixed into this source checkpoint.

## Exact reviewed inventory: 82 files

Every path below is explicitly staged. No directory-wide or all-files staging is used. This inventory includes itself.

```text
api/.gitignore
api/CHECKPOINT_14B.md
api/README.md
api/SECTIONS_13K.md
api/STRIP_13L.md
api/__init__.py
api/dependencies.py
api/main.py
api/models.py
api/ocr_metrics.py
api/requirements.lock.txt
api/requirements.txt
api/section_routes.py
api/sessions.py
api/smoke/FAILURE_REPORT.md
api/smoke/LATENCY_13J.md
api/smoke/READINESS_13G.md
api/smoke/READINESS_13I.md
api/smoke/README.md
api/smoke/SECOND_ATTEMPT_13H.md
api/smoke/diagnostics.py
api/smoke/fictional_demo.png
api/smoke/persistence.py
api/smoke/second_attempt.py
api/smoke/server.py
api/strip_routes.py
api/tests/conftest.py
api/tests/test_diagnostic_readiness.py
api/tests/test_ocr_metrics.py
api/tests/test_prescriptions.py
api/tests/test_second_attempt.py
api/tests/test_sections.py
api/tests/test_smoke.py
api/tests/test_smoke_diagnostics.py
api/tests/test_strip_api.py
frontend/.gitignore
frontend/README.md
frontend/index.html
frontend/package-lock.json
frontend/package.json
frontend/src/App.tsx
frontend/src/components/Anatomy.tsx
frontend/src/components/DashboardLayout.tsx
frontend/src/components/ImageUploader.tsx
frontend/src/components/SectionReview.tsx
frontend/src/components/ui.tsx
frontend/src/lib/api.ts
frontend/src/lib/image.test.ts
frontend/src/lib/image.ts
frontend/src/lib/prescriptions.test.ts
frontend/src/lib/prescriptions.ts
frontend/src/lib/sections.test.ts
frontend/src/lib/sections.ts
frontend/src/lib/strip.test.ts
frontend/src/lib/strip.ts
frontend/src/main.tsx
frontend/src/pages/Analysis.tsx
frontend/src/pages/Auth.tsx
frontend/src/pages/ExpiryScanner.test.tsx
frontend/src/pages/ExpiryScanner.tsx
frontend/src/pages/Landing.tsx
frontend/src/pages/Overview.tsx
frontend/src/pages/PrescriptionFlow.test.tsx
frontend/src/pages/PrescriptionFlow.tsx
frontend/src/pages/PrescriptionSections.test.tsx
frontend/src/pages/Workspace.tsx
frontend/src/strip.css
frontend/src/styles.css
frontend/tsconfig.json
frontend/vite.config.ts
medisaathi/ai_integration.py
medisaathi/assistant.py
medisaathi/investigations.py
medisaathi/medication_instructions.py
medisaathi/reader.py
medisaathi/strip.py
medisaathi/tests/test_ai_integration.py
medisaathi/tests/test_assistant.py
medisaathi/tests/test_investigations.py
medisaathi/tests/test_medication_instructions.py
medisaathi/tests/test_reader.py
medisaathi/tests/test_strip.py
```
