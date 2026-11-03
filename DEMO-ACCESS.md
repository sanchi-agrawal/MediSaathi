# Working temporary demo access — not account authentication

Open **http://localhost:5177/**, choose Sign In, and enter any properly formatted
fictional email plus a nonempty fictional password. Valid details request a
temporary server demo session and open `/dashboard`. Log Out revokes that session
and returns to `/login`. English/Hindi selection remains available.

This does not verify email/password identity or create an account. The email is
used only for format validation and is not retained. The password is checked only
for nonemptiness in the form and cleared before any asynchronous request; it is
never copied into application state, sent to Python or stored. Login JSON contains
only email. Server schema rejects password/identity claims as extra fields.

Temporary state is isolated in server RAM, behind an opaque Secure/HttpOnly/
SameSite=Strict `/api` cookie named `medisaathi_hackathon`. Refresh restores access
while its absolute session lifetime (up to 30 minutes) is valid. Expiry, logout
or API restart removes access; login again starts a new empty workspace. No
session credentials or medical records are stored in localStorage. Only the
existing non-sensitive interface-language preference uses localStorage.

The email does not own or identify records. No account history or database routes
are usable here; those endpoints are blocked. This server accepts the registered
fictional prescription/strip fixtures, uses mocked OCR and the real existing
review/confirmation/scheduling interfaces, and blocks Google SDK construction.
No Supabase configuration, SMTP, Supabase call, Gemini call or Telegram delivery
is needed. Other demos' cookies and account cookies cannot grant access.

The Supabase files remain intact for future work. Demo mode is explicit:
`api.hackathon_demo:app` plus `VITE_MEDISAATHI_DEMO_ACCESS=1`. Without that flag,
the account implementation remains selected. Do not present this mode as real
authentication or use it to store real patient information.

## Run locally (two PowerShell terminals)

The dedicated API/UI were started during this task. Do not start duplicate
listeners. These commands restart the demo if it has stopped.

Backend:
```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH = "$PWD\api\.venv\deps"
& 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe' -m uvicorn api.hackathon_demo:app --host 127.0.0.1 --port 8005 --no-access-log
```

Frontend:
```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8005'
$env:VITE_MEDISAATHI_DEMO_ACCESS = '1'
$env:VITE_MEDISAATHI_OFFLINE_DEMO = '1'
$env:VITE_MEDISAATHI_ACCOUNT_TEST = '0'
npm.cmd run dev -- --port 5177 --strictPort
```

The existing dependencies are installed locally. On another computer, install
`api/requirements.txt` in an isolated virtual environment and run `npm.cmd ci`
under frontend. No environment credentials are required for this demo.

Use `api/.venv/demo16c/fictional-prescription.png` and `fictional-strip.png`.
If missing, generate them locally with `python -m api.demo_fixture --write-fixtures`.
All separate medicine/instruction/investigation and strip confirmations remain
required. Associations and schedule approval remain explicit; edits invalidate
dependent results. Logged-out/expired cookie replay cannot retrieve a workspace.

## Verification

- Backend: **1,059 passed, 1 skipped**, 13 subtests. Skip is the existing diagnostic
  test whose original guard artifact is intentionally absent from this checkout.
- Frontend: **127 passed across 18 files**. Actual demo-mode production build passed.
- Existing anatomy chunk-size and Starlette test-client warnings remain.
- Offline tests cover login, cookie flags, refresh, logout/replay, expiry,
  capacity/errors/CSRF, invalid forms, other cookie/session isolation and the
  fictional prescription/section/scheduling/strip flow. Frontend tests verify
  password clearing before request, email-only transport, duplicate-submit
  prevention, cookie restoration failure, English/Hindi, redirect and logout.
- Actual localhost HTTP/proxy verification is recorded in the task delivery.
  Programmatic cookie forwarding does not establish Chrome cookie acceptance.
- No browser interaction/screenshot verification was performed. In Chrome, use
  `localhost:5177`, confirm the demo notice, sign in, refresh, review fictional
  data, log out, and confirm direct dashboard navigation returns to login. If the
  browser rejects the Secure localhost cookie, the UI reports failure instead of
  showing a false session; no production cookie security setting was weakened.

## Exact files changed for this request

- `api/hackathon_demo.py`
- `api/tests/test_demo_access.py`
- `frontend/src/lib/demoAccess.ts`
- `frontend/src/pages/DemoSignIn.tsx`
- `frontend/src/pages/DemoAccess.test.tsx`
- `frontend/src/components/SessionAccess.tsx`
- `frontend/src/App.tsx` — select demo facade only when explicitly enabled.
- `frontend/src/components/DashboardLayout.tsx` — demo profile/logout and hide account history in demo mode.
- `DEMO-ACCESS.md`

Prior uncommitted account integration and typography work is preserved. No
teammate, AI, scheduler, pricing, expiry-parser or diagnostic-guard changes. No
staging, commits, merges or pushes were performed.

## Session personalization

Demo Sign Up requires Full Name, Email Address, Password and Confirm Password.
The browser validates the name and password match and clears both password
fields synchronously before making a request. Only email and display_name are
sent to POST /api/demo-access/signup; no password is sent or stored.
The display name is unverified presentation metadata in the current server RAM
session, not an account identity. GET /api/demo-access/status restores it across
navigation and refresh. Logout, expiry and backend restart remove it. Direct
demo sign-in rotates the session and starts without a name, even for the same
email. Dashboard greetings never derive a name from email. Future configured
Supabase accounts use server-verified user metadata instead.

After updating Python code, restart the dedicated 8005 demo API using the command
above. The split-screen illustration and all medical workflow guards are unchanged.
