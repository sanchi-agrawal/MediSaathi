# MediSaathi deployment preparation: fictional-data preview

This is a **fictional-data-only public preview**, not a service for real patient records. The current local account implementation uses a six-character minimum password, has no email verification or password recovery, and stores active prescription workspaces and uploaded documents in process memory. Account records use SQLite. Render's default filesystem is ephemeral, so SQLite accounts disappear after restart or redeploy unless a persistent disk is deliberately configured. Even with a disk, active prescriptions are not durable. Use one Uvicorn worker; multiple workers do not share workspaces.

No deployment, commit or push is performed by this preparation. The uncommitted frontend, API, AI and pricing files must be reviewed and committed before either host can build them. Do not upload real patient data to this preview.

## Render web service

- Repository root: repository root (the Python `api`, `medisaathi`, and `pricing_dataset` directories must all be present).
- Runtime: Python; `.python-version` selects Python 3.12.11.
- Build command: `pip install -r api/requirements.lock.txt`
- Start command: `uvicorn api.local_server:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/health`
- Instance count / workers: one.

Set these environment variables in Render, not in Git or Vercel:

| Name | Value or purpose |
| --- | --- |
| `MEDISAATHI_DEPLOYMENT_MODE` | `preview`; enables fail-fast HTTPS/origin/host checks and Secure auth cookies |
| `MEDISAATHI_LOCAL_OFFLINE` | `0` for real Gemini OCR; `1` only if intentionally using the registered offline fixtures |
| `MEDISAATHI_ORIGINS` | Exact HTTPS Vercel frontend origin, without a path or trailing slash; comma-separated exact origins if needed |
| `MEDISAATHI_TRUSTED_HOSTS` | Exact Render API hostname; include the frontend hostname only if the proxy forwards that Host header. No scheme or wildcard |
| `MEDISAATHI_LOCAL_DB` | Explicit SQLite file path, e.g. `/tmp/medisaathi-preview/accounts.sqlite3` for disposable fictional accounts |
| `GEMINI_API_KEY` | Secret Gemini key, server side only |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |

`MEDISAATHI_LOCAL_HTTPS=1` is optional in preview mode; preview mode already forces Secure cookies. Do not set any `VITE_GEMINI_*` variable. The existing Python `reader.py` also supports a local `.env` for development, but Render must use its environment settings.

For accounts that survive restarts, provision a Render persistent disk and point `MEDISAATHI_LOCAL_DB` inside its mount path. This **does not** make prescription workspaces durable or make the service suitable for real patients. Before real patient use, migrate identity and owner-scoped prescription data to a durable database and private object storage, add retention/deletion controls and backups, strengthen account policy and verification/recovery, and review privacy/security requirements. A persistent disk is single-instance storage and is not a substitute for that work.

The API keeps at most 64 workspaces per process and expires them after 30 minutes. Uploads are bounded and held in RAM; clearing a prescription removes its image/document state. A process restart discards all workspaces. Sanitized extraction diagnostics go to ignored `api/runtime/` and may also disappear on Render's ephemeral filesystem. Do not expose or publish runtime files.

## Vercel frontend

- Project root directory: `frontend`
- Framework preset: Vite
- Install command: `npm ci`
- Build command: `npm run build`
- Output directory: `dist`
- `VITE_MEDISAATHI_LOCAL_AUTH=1`
- `VITE_MEDISAATHI_PREVIEW=1` to display the fictional-data-only warning in English or Hindi.

The application already calls relative `/api/...` paths with `credentials: 'include'`. Vite's proxy in `vite.config.ts` is for local development only. Once Render supplies its actual HTTPS URL, copy `frontend/vercel.json.template` to `frontend/vercel.json` and replace `REPLACE_WITH_RENDER_HOST.onrender.com` with the exact Render hostname. Review that file before committing. The first rewrite must forward `/api/:path*` to the same `/api/:path*` on Render; the SPA fallback to `/index.html` must remain second. Never route `/api` through the SPA fallback. Do not put the Gemini key in this file or any Vite variable.

The browser should see authentication cookies on the Vercel origin because requests are made to the same-origin `/api` path. The backend accepts only the configured exact Origin and custom action header on mutations. Test the final Vercel rewrite with signup, `/api/local-auth/me`, a fictional upload, refresh, and logout before inviting users. A direct browser call from Vercel to the Render hostname is a different-origin path and is not the configured flow. Preview deployment URLs change; use a stable frontend domain or explicitly add each exact preview origin to Render and redeploy.

## Controlled launch checks

1. Review and commit the intended uncommitted source, tests, static catalogue JSON, and deployment files. Exclude `.env`, SQLite files, runtime logs, images containing patient information, caches, virtual environments, `node_modules`, and `dist`.
2. Create the Render web service from the reviewed commit. Set the variables above and verify `/api/health` over HTTPS. Keep the service at one worker.
3. Put the exact Render hostname in `frontend/vercel.json`, review the API rewrite order, then deploy the frontend from the reviewed commit with `VITE_MEDISAATHI_PREVIEW=1`.
4. From the Vercel site, use fictional credentials and a fictional prescription to verify signup/login, a Secure HttpOnly cookie, `/api/local-auth/me`, upload, mocked or explicitly authorized real extraction, refresh, and logout. Check that API failures are JSON rather than the SPA HTML.
5. Do not use actual patient data. Do not enable notification delivery or treat provisional medicine prices as live offers.

The local reverse-proxy tests cover exact HTTPS Origin, trusted Host, Secure/HttpOnly/SameSite cookie, workspace creation, logout and rejection of a different Origin. They do not prove Vercel's deployed external rewrite behavior; that requires the final hostnames and a browser test.
