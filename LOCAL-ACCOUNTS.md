# MediSaathi local accounts

Real local email/password verification, independent of Supabase and demo-access
endpoints. This is a single-computer implementation, not a public deployment.

## Routes

Existing Supabase routes remain unchanged under `/api/auth/*`. The selected local
server blocks them and all anonymous `/api/demo-access/*` routes. Normal Sign Up
and Sign In use:

- `POST /api/local-auth/signup`: `full_name`, `email`, `password`.
- `POST /api/local-auth/login`: `email`, `password`.
- `GET /api/local-auth/me`: current authenticated user, or JSON 401.
- `POST /api/local-auth/logout`: revoke the current session and remove its cookie.
- `GET /api/local-info`: authenticated local-mode and medical-storage information.

All mutation requests require an exact configured loopback Origin on port 5177
and `X-MediSaathi-Action: review`. The existing Vite `/api` proxy covers every
route; do not send requests to unproxied `/auth` paths. Errors use JSON
`detail.category`, including `email_exists`, `invalid_credentials`, `rate_limited`,
`session_expired`, `invalid_input` and `storage_unavailable`.

## Storage and security

Default database: `api/runtime/local-accounts.sqlite3`, ignored by Git. Optional
absolute override: `MEDISAATHI_LOCAL_DB`. No migration command is needed.

Tables:

- `users`: UUID, full name, case-normalized unique email, Argon2id password hash,
  UTC epoch creation timestamp.
- `sessions`: SHA-256 hash of a random 256-bit opaque token, owning user UUID,
  creation/expiry timestamps. Only the browser receives the raw token.
- `auth_limits`: hashed source IP and a persistent 30-attempt/15-minute window.
  Trusted proxy headers are not accepted; a shared local proxy shares this limit.

Passwords use argon2-cffi's high-level PasswordHasher defaults with random salts,
verification and rehash checks. New passwords require 6–128 characters in this prototype only. Six characters is
a prototype compromise, not suitable for deployment with real patient data. Password
confirmation happens in the form; passwords are never put in React state,
localStorage, application logs or SQLite. They necessarily travel in the login
request to the local server for hashing/verification. Forms clear their fields
during submission. Identity always comes from server `/me`, never the email text.

Cookie: `medisaathi_local_auth`, HttpOnly, SameSite=Strict, Path=/api, eight-hour
absolute expiry. Logout deletes the database session and its temporary workspace;
the old token cannot be replayed. Successful login rotates this browser's session.
Other users/sessions cannot supply workspace authority via anonymous cookies.
Cross-tab auth-change notices carry no identity, password or token.

Plain HTTP on loopback deliberately uses a non-Secure local auth cookie. HTTPS
requests enable Secure; set `MEDISAATHI_LOCAL_HTTPS=1` for TLS reverse-proxy use.
This flag does not configure TLS. Use HTTPS for any deployment beyond a trusted
local machine; the provided commands bind the API only to loopback. Original
demo/provider cookie settings are unchanged. Restrict OS access to the runtime
directory: the SQLite identity database is not encrypted at rest. Do not expose
this development server publicly. Email ownership verification, recovery, MFA,
account deletion and production operations are not implemented.

## Medical data

Only users and session hashes are durable. Medical images, OCR records,
confirmations, associations and schedules remain in separate in-memory
workspaces, one per authenticated session, with the existing 30-minute workspace
expiry. Logout and API restart discard medical workspaces. The same account
logging in again starts an empty workspace. No anonymous records are migrated.
Old medical IDs/revisions cannot authorize a new session. Do not use real patient
data. There is no durable prescription-history feature in this local mode.

`api.local_server:app` defaults to the registered fictional images and mocked
extractors; matching, review, confirmation, scheduling and strip safety logic
stay unchanged. No notification delivery is enabled. The original live backend
and Supabase source remain available but unused. `MEDISAATHI_LOCAL_OFFLINE=0`
selects the unchanged real integration factory instead; this requires the
existing server-side Gemini configuration and explicit user-triggered analysis.
No provider request occurs at startup. Do not use that setting for offline tests.

## Exact PowerShell restart commands

Stop the existing Vite terminal with **Ctrl+C** before restarting it. Never start
a second server or let Vite silently select a different port.

API terminal (this checkout's installed interpreter and isolated dependency path):

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$listeners = @(Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue)
foreach ($listener in $listeners) {
  $apiProcess = Get-CimInstance Win32_Process -Filter ("ProcessId = " + $listener.OwningProcess)
  if ($apiProcess.CommandLine -notmatch 'uvicorn api\.(local_server|hackathon_demo):app.*--port 8005') {
    throw 'Port 8005 belongs to an unexpected process. Inspect it before stopping it.'
  }
  Stop-Process -Id $listener.OwningProcess
}
$env:PYTHONPATH = "$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE = '1'
$env:MEDISAATHI_LOCAL_HTTPS = '0'
$env:MEDISAATHI_LOCAL_DB = "$PWD\api\runtime\local-accounts.sqlite3"
& 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe' -m uvicorn api.local_server:app --host 127.0.0.1 --port 8005 --no-access-log --no-proxy-headers
```

Frontend terminal:

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8005'
$env:VITE_MEDISAATHI_LOCAL_AUTH = '1'
$env:VITE_MEDISAATHI_DEMO_ACCESS = '0'
$env:VITE_MEDISAATHI_OFFLINE_DEMO = '1'
$env:VITE_MEDISAATHI_ACCOUNT_TEST = '0'
npm.cmd run dev -- --port 5177 --strictPort
```

Open **http://localhost:5177/signup**. Local auth is the frontend default; setting
`VITE_MEDISAATHI_LOCAL_AUTH=0` explicitly restores the previous selectable modes.
No Supabase keys or SMTP setup are needed. Added dependency:
`argon2-cffi>=25.1,<26` (installed into `api/.venv/deps`, with its cffi bindings).
For a new installation use an isolated venv and `pip install -r api/requirements.txt`.

## Browser verification checklist

1. Register a fictional name/email and a new password of at least 12 characters.
   Confirm the matching-password validation, name, initials and dashboard redirect.
2. Refresh and navigate between dashboard pages; confirm the registered name stays.
3. Switch English/हिंदी and check the actual greeting and auth/profile labels.
4. Log out. Direct `/dashboard` navigation must return to Sign In. Wrong-password
   sign-in must fail; correct-password sign-in must recover the registered name.
5. Duplicate registration must be rejected; no arbitrary password may grant access.
6. Restart only the API. Existing account/session identity should restore, while
   the medical workspace starts empty. Accounts remain in the same SQLite file.
7. Use a separate browser profile for user B. `/me` and medical records must belong
   to that session. Old IDs from A must fail in B. Check cross-tab account switches.
8. Use only `api/.venv/demo16c/fictional-prescription.png` and `fictional-strip.png`
   for the existing offline review/confirm/explain/schedule/expiry flow.
9. Inspect cookie flags without copying its value. No token should appear in
   localStorage. Browser interaction and screenshot verification remain manual.

## Source files changed for local authentication

Verification: full Python suite **1,077 passed, 1 skipped**, 13 subtests; final
targeted local-auth suite **11 passed**; frontend **145 passed across 21 files**;
production build passed. Existing diagnostic-artifact skip, Starlette test-client
deprecation and anatomy bundle-size warning remain. A real HTTP check through
localhost:5177 verified registration, credential rejection, cookie restoration,
login/me/logout; tests used actual SQLite/Argon2. No interactive browser test was
performed. No Gemini, Supabase or Telegram calls were made.

- `api/local_auth.py` (new)
- `api/local_server.py` (new)
- `api/tests/test_local_auth.py` (new)
- `api/requirements.txt`
- `api/.gitignore`
- `frontend/src/lib/localAccounts.ts` (new)
- `frontend/src/lib/localAccountState.test.tsx` (new)
- `frontend/src/components/LocalAccounts.tsx` (new)
- `frontend/src/components/SessionAccess.tsx`
- `frontend/src/components/Personalization.tsx`
- `frontend/src/components/DashboardLayout.tsx`
- `frontend/src/pages/LocalAccounts.test.tsx` (new)
- `frontend/src/App.tsx`
- `LOCAL-ACCOUNTS.md` (this file)

Ignored runtime outputs include the SQLite database, isolated dependency installs,
test scratch directories, and `api/.venv/check_local_http.py` used for an HTTP
proxy smoke check with a throwaway account. The test account was removed. No
Supabase source, AI/medical modules, scheduling engine, attempt guards or teammate
worktrees were changed for this task. No changes were staged, committed or pushed.


## Settings and appearance update

See `SETTINGS-APPEARANCE.md` for the current password policy, profile/password
changes, transactional account deletion, temporary-workspace clearing, light/dark
themes, exact changed-file list and latest verification. Forgot-password recovery
remains unavailable; current-password-verified changes are available in Settings.
