# MediSaathi frontend · Milestones 13D / 13E

**Milestone 13L:** `/dashboard/expiry` now connects strip upload, OCR, raw-label review, conservative server-side reparsing and explicit confirmation. See [api/STRIP_13L.md](../api/STRIP_13L.md). Browser and live strip OCR verification remain pending; no safety-to-take judgment or prescription association is supplied.

**Milestone 13K:** prescription-analysis checkboxes now connect medicines, dosage instructions and prescribed investigations to independent API operations and review/confirmation panels. See [api/SECTIONS_13K.md](../api/SECTIONS_13K.md). Instructions/investigations below are no longer inactive in the normal prescription API; separate dashboard summaries and guarded diagnostic-server capabilities remain limited as documented.

Milestone 13E connects the real medicines workflow through the additive Python API. Follow [api/README.md](../api/README.md) for current setup, exact file inventory, routes and session constraints. Start Python first, then run `npm.cmd run dev` here and open **http://localhost:5173/dashboard/analysis**. The Secure cookie uses the browser's localhost exception; deployment requires HTTPS. Vite proxies `/api` to `127.0.0.1:8000`.

Standalone React + TypeScript + Vite frontend. Tailwind v4 supplies theme tokens and utilities; the shared stylesheet defines the custom responsive design. React Router supplies routes and Lucide React supplies icons. The anatomy illustration is an original procedural SVG, lazy-loaded with interactive organ selection and perspective rotation; it is not a clinical or true 3D anatomical model.

## Run locally

Requirements: Node 22.21+ (or a compatible current Node release) and npm.

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The local integration needs the Python API running; see api/README.md.

```sh
npm run check
npm test
npm run build
npm run preview
```

Production output: `dist/`. Static hosting must rewrite application routes to `index.html`. Vite's development/preview servers are for local use.

## Pages

- `/`: landing, interactive stylized anatomy, features and workflow
- `/login`, `/signup`: native validated UI-only forms; no network submission or saved account/session
- `/dashboard`: overview with honest empty states
- `/dashboard/analysis`: real medicines Upload → Gemini OCR → Review → Save → Confirm → Explain; English/Hindi/Hinglish explanations through the existing offline assistant
- `/dashboard/medicines`, `/dashboard/investigations`: integration placeholders
- `/dashboard/expiry`: independent strip-image input and preview
- `/dashboard/schedule`, `/dashboard/lab-costs`: teammate integration placeholders
- `/dashboard/settings`: temporary local explanation preference
- Unknown paths: recovery page

## Working browser interactions

Responsive navigation; page search; anatomy organ selection and perspective slider; form validation and password visibility; image upload/drop and device-dependent camera capture; PNG/JPEG signature checks, 10 MiB and 8 million pixel limits, browser decode checks; preview zoom, rotation, replacement and removal; explicit medicines extraction; ten-field editable review; saved-review and server confirmation states; English/Hindi/Hinglish explanations. Local edits clear confirmation/explanation immediately. Browser data stays in component memory, while the API holds a bounded, temporary demo session. Preview rotation does not modify image bytes. Object URLs are revoked on replacement/unmount. Asynchronous validation and extraction ignore superseded sources.

Browser checks are early feedback only. The existing Python validator remains authoritative for actual format, full decompression, single-frame requirements and safe image limits. Browser decode does not establish that text is legible. Handwritten extraction is experimental. No OCR runs in JavaScript.

## Milestone 13E connection

The API now connects medicines extraction, review, server confirmation and explanations. Authentication, dashboard summary data, dosage-instruction extraction, investigations, strip extraction, scheduling, reminders, matching and pricing remain inactive. No prices, patient statistics or medical claims are fabricated.

`src/lib/prescriptions.ts` provides the connected medicines HTTP client, runtime contract checks and cookie credentials. `src/pages/PrescriptionFlow.tsx` renders real extraction and review states; `Analysis.tsx` is a compatibility re-export. `src/lib/api.ts` retains the shared record types and inactive future-scope/auth clients. No existing Python public interface is changed.

## Next integration work

1. Completed: six AI modules and their six tests copied byte-for-byte from `2e6eee1`, without replacing teammate files or merging branches.
2. Completed for local demo: one `AIIntegration` per opaque HttpOnly/Secure/SameSite cookie session, revision checks and server-side `FrontendEvents`. Production authentication remains future work.
3. Completed: medicines-only Upload → Review → Save → Confirm → Explain. Responses are checked at runtime; null values remain unknown and input changes invalidate confirmation.
4. Expand to separately selected instruction/investigation extraction and strip scope. Preserve schema envelopes, original source text, issue codes and uncertainty warnings. Confirm each scope separately. Distinguish success with empty/unknown data from validation, configuration, network, quota, API and malformed-response errors. Only explicit analysis/retry actions may call Gemini.
5. Delegate matching/pricing to Person 2 and all scheduling/reminder arithmetic and delivery to Person 3. Add user isolation and authenticated server review/confirmation tests before enabling these operations.
6. Integrate real server-verified authentication. Keep Gemini keys exclusively on Python; never use VITE-prefixed secret variables. Protect APIs independently of browser route visibility.

The supplied palette and written layout requirements guide the design. No reference image was available, so screenshot fidelity could not be assessed. Browser visual QA was blocked by the Computer Use URL-detection policy; production builds, offline tests and HTTP proxy verification are separate checks. No live Gemini request has been tested manually.

## Source inventory

Configuration: `.gitignore`, `package.json`, `package-lock.json`, `index.html`, `tsconfig.json`, `vite.config.ts`.

Application: `src/main.tsx`, `src/App.tsx`, `src/styles.css`.

Components: `src/components/ui.tsx`, `Anatomy.tsx`, `DashboardLayout.tsx`, `ImageUploader.tsx`.

Pages: `src/pages/Landing.tsx`, `Auth.tsx`, `Overview.tsx`, `Analysis.tsx`, `Workspace.tsx`.

Service boundary and checks: `src/lib/api.ts`, `image.ts`, `image.test.ts`.

Documentation: this `README.md`. Generated `node_modules/`, `dist/`, and TypeScript build metadata are ignored. No Python sources are modified.
