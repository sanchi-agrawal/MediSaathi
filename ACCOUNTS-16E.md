# Milestone 16E — provider-backed accounts, setup and acceptance

**Not complete / not live-verified.** The user confirmed that no Supabase project
exists yet. Real signup, email delivery, login, logout and PostgreSQL RLS cannot
be verified until that project is configured. No real auth, Gemini or Telegram
request was made during implementation. Offline tests simulate the provider;
they are not evidence of a working hosted account or a real database policy.

## Implemented

Supabase Auth REST password/refresh and email-OTP flows run through FastAPI using
httpx. Supabase owns password security; there is no application password database.
Supported endpoints: signup, email verification, login, forgot/reset password,
logout, me and configuration status. The Python server verifies the user through
Supabase `/user` on protected operations. A verified email and a non-anonymous
UUID identity are required. Privileged/service-role keys are rejected.

The browser receives only an opaque random `medisaathi_account` handle, in a
Secure/HttpOnly/SameSite=Strict cookie scoped to `/api`. Only a digest of that
handle indexes bounded server RAM. Provider access/refresh tokens stay in that
RAM. Refreshes are serialized. Logout revokes the BFF handle and its workspace,
expires cookies and attempts provider refresh-token revocation. Password reset
revokes all local handles for that user and requests global provider sign-out.
Provider JWTs already issued may live until their expiry; they never reach the
frontend. Local handles are authoritative for this application's API access.

Configured account mode protects existing OCR/review/confirmation/association/
schedule/matching/strip/pricing routes as well as account APIs. The backend maps
the verified account session to its own server workspace and ignores supplied
anonymous workspace cookie authority. Login never adopts anonymous records.
Explicitly save a prescription uploaded/reviewed in your authenticated workspace.

CSRF uses the existing exact Origin plus custom action-header boundary. Auth JSON
is bounded to 16 KiB; account continuation to 16 MiB, with existing authoritative
image validation still enforced. Auth flows are rate-limited per client IP and
hashed email/IP (8/minute) plus 30/minute per IP. Provider limits also apply.
Errors are generic; provider error bodies, headers, keys, passwords and tokens
are neither returned nor logged by these modules. Do not enable HTTP-body debug
logging or weaken the existing credentialed CORS boundary.

The Sign In/Sign Up pages now use provider calls, loading/failure states and
English/Hindi controls, with explicit setup-unavailable messaging until configured.
They no longer pretend client validation creates an account. Protected account
routes redirect to login, profile/sign-out uses the verified identity, and UI
language uses the existing non-sensitive preference across same-origin pages.
No passwords, session tokens or medical records enter localStorage.

## Durable archive model and safety

Apply `api/accounts/migrations/001_archives.sql` in your own Supabase project.
Table `public.prescription_archives` has:

- `id`, `owner_id` (FK to auth.users), immutable `version` and schema version.
- `payload_ciphertext`: application-encrypted Fernet JSON; no plaintext medical
  data or image data in database columns.
- Server-created timestamps and a 30-day access expiry.

RLS is enabled and forced. `auth.uid() = owner_id` gates SELECT/INSERT/DELETE;
expired rows cannot be selected. Anonymous grants are revoked. UPDATE is not
granted: saving creates a new immutable version. The application uses the user's
JWT for PostgREST, never a service-role key, and adds owner predicates/checks.

Encrypted snapshots keep original OCR separate from reviewed medicines,
instructions and investigations, plus current revision/confirmation metadata,
explicit associations, approved schedules/refill calculations and capture time.
Capture time is not claimed to be the original confirmation-event timestamp.
Source images are saved only with the user's separate image consent. The archive
key stays outside the DB; retain it securely or archives cannot be decrypted.

My Prescriptions provides explicit Save, View, Continue Review and Delete. A view
is historical, not current approval authority. Continue Review validates the
saved original/reviewed payloads using public AIIntegration methods. It creates
a NEW analysis/revision, clears all confirmations, associations, schedules and
explanations, and never calls an extractor or restores browser-supplied approval
claims. Users reconfirm each scope and approve scheduling again. The original
archived IDs/revisions remain in history. If the encrypted source image was not
saved, the user must reselect the exact original validated image (hash checked).
Strip state remains separate. No AI/assistant/schedule module was modified.

The archive survives a backend restart in PostgreSQL. BFF sessions and current
workspaces are RAM-only: after a restart, sign in again and open saved history.
Nothing is auto-saved. Deleting an archive deletes that saved DB version; it does
not claim erasure of a separate live RAM workspace or provider backups. Logging
out removes that login's active workspace. Expired rows need a configured physical
cleanup schedule and provider backup-retention policy before a real-data rollout.

## Exact setup required (user action)

1. Create a Supabase project and keep its project URL and **publishable** key in
   the server configuration only. A legacy anon key is also supported. No
   service-role/secret key or JWT signing secret is required by this application.
2. Enable Email/password signups and **Confirm email**. Set Site URL to
   `http://localhost:5176` for the isolated acceptance run. Use HTTPS for a public
   deployment. Keep Secure cookies enabled; localhost browser acceptance must be
   tested in Chrome rather than assumed from TestClient.
3. In Auth Email Templates, use OTP-code templates instead of implicit token links:

   Confirm signup body:
   ```html
   <p>Your MediSaathi verification code: {{ .Token }}</p>
   <p>Enter it at http://localhost:5176/verify-email</p>
   ```
   Reset password body:
   ```html
   <p>Your MediSaathi recovery code: {{ .Token }}</p>
   <p>Enter it at http://localhost:5176/reset-password</p>
   ```
   Do not put access/refresh tokens or OTPs in application URLs. Configure SMTP
   for your intended recipients; Supabase's default SMTP restricts recipient
   addresses and rates. No email-delivery success is claimed until tested.
4. Run the SQL migration in the project's SQL editor. Verify RLS policies and
   grants as an ordinary authenticated user, not an administrator/service role.
5. Copy `api/accounts/config.example` to the ignored `api/.env` only if absent.
   Fill the URL/key locally. Generate the archive encryption key once without
   printing it. Keep that file private and unchanged across restarts.

Required server variables:

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | HTTPS project origin |
| `SUPABASE_PUBLISHABLE_KEY` | Project publishable key (or legacy `SUPABASE_ANON_KEY`) |
| `MEDISAATHI_ARCHIVE_KEY` | Fernet key for durable medical snapshots/images |
| `MEDISAATHI_FICTIONAL_OCR=1` | Acceptance mode: real accounts, registered fictional OCR, Google SDK blocked |
| `MEDISAATHI_API_PORT=8004` | Dedicated local API, avoiding existing 8000/8002 processes |
| `MEDISAATHI_ORIGINS=http://localhost:5176,http://127.0.0.1:5176` | Exact accepted frontend origins |
| `MEDISAATHI_GEMINI_ENV_FILE` (optional) | Existing private file; run entrypoint reads only Gemini key/model fields |

The last variable is unnecessary for fictional acceptance mode. Normal mode
preserves server-side Gemini configuration; no live OCR is authorized by setup.
Do not create `VITE_*` credential variables. The only new public Vite variable is
the non-sensitive account-test banner flag.

## Local commands after creating the project

Use the existing tested interpreter/dependencies (does not modify the old worktree).
For another machine, make a virtual environment here and install `api/requirements.txt`.

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$python = 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
if (!(Test-Path api/.env)) { Copy-Item api/accounts/config.example api/.env }
# Edit api/.env locally to set your real project URL and publishable key.
# Replace only the key placeholder; this command does not print a secret:
& $python -c "from pathlib import Path; from cryptography.fernet import Fernet; p=Path('api/.env'); s=p.read_text(encoding='utf8'); p.write_text(s.replace('GENERATE_ONCE_AND_KEEP_PRIVATE',Fernet.generate_key().decode()),encoding='utf8')"
$env:PYTHONPATH = "$PWD\api\.venv\deps"
& $python -m api.accounts.run
```

Second terminal:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8004'
$env:VITE_MEDISAATHI_ACCOUNT_TEST = '1'
npm.cmd run dev -- --port 5176 --strictPort
```

Open `http://localhost:5176/signup`. This is NOT the offline-only 5175 server,
which intentionally keeps accounts unavailable. No Supabase SDK token storage is
initialized in the browser. Startup never signs in, sends email or calls Gemini.
For normal real-extraction mode, explicitly unset `MEDISAATHI_FICTIONAL_OCR`, use
the appropriate API port/proxy/origins and unset the account-test banner. Do not
send a live Gemini request without fresh authorization.

## Browser/live-provider acceptance checklist — NOT YET VERIFIED

1. Confirm `/api/auth/status` reports configuration present; distinguish this
   from a successful provider/database check. Without config, forms must be
   disabled with a setup-unavailable explanation and no fake success.
2. Register fictional User A with a real test inbox. Confirm no application login
   cookie is issued on signup. Verify email with the received code, then sign in.
   Inspect that only the opaque Secure/HttpOnly/SameSite=Strict account cookie is
   present, with no tokens in storage. Verify redirect, profile and Hindi labels.
3. Refresh and navigate; session remains valid without storing tokens in JS.
   Invalid password/expired code must fail generically. Request a reset, use the
   recovery code, check old sessions fail and the new password works.
4. In fictional acceptance mode only, upload the registered
   `api/.venv/demo16c/fictional-prescription.png`; extract, review, confirm scopes,
   explain, match/select, associate and approve schedule. Save explicitly through
   My Prescriptions, with/without image consent. Verify encrypted DB storage.
5. Restart API, sign in again, list/view the saved archive. Continue Review:
   exact image required if not stored, new analysis ID, no active confirmation,
   no restored schedule, no extra OCR call. Independently reconfirm/approve again.
6. Sign out; verify protected routes/API and replayed old cookie fail. Sign in as
   User B in a separate browser profile/incognito session. Try A's IDs for view,
   delete, continuation and working confirmation/scheduling: deny access. Verify
   RLS directly under B's JWT and that B cannot alter/insert A's owner ID.
7. Delete A's saved record as A. Re-query history and DB; check expiry/cleanup and
   backup policy separately. Do not claim immediate backup erasure.
8. Verify unrelated catalogue, zero-price state, reminder previews, strip scanning,
   English/Hindi/Hinglish and typography remain intact. No Telegram or unverified
   price comparison is enabled.

## Offline verification and remaining limitations

Automated provider and database tests use httpx MockTransport plus a durable
SQLite fixture representing PostgREST/RLS. They exercise real BFF transport,
encryption, cookies, refresh/logout, ownership, revision and fresh-resume code,
including a simulated backend restart, but DO NOT validate hosted Supabase or
execute the migration against PostgreSQL. Frontend tests cover real transport
wiring, protected routing, language, setup/failure, consent and history states.

Server sessions/rate limits are single-process RAM; run one API worker. Distributed
sessions/rate limits, physical retention cleanup, backup deletion, archive-key
rotation, deployment TLS/SMTP and real browser acceptance remain deployment work.
No production readiness or healthcare compliance claim is made. Existing schedule,
AI, teammate pricing modules and diagnostic guards are preserved. Typography
changes predating 16E remain uncommitted and preserved. No stage/commit/push.

Official references used: [Supabase Auth REST](https://supabase.github.io/auth/),
[password authentication](https://supabase.com/docs/guides/auth/passwords),
[email OTP templates](https://supabase.com/docs/guides/auth/auth-email-templates),
[SMTP restrictions](https://supabase.com/docs/guides/auth/auth-smtp),
[PostgreSQL RLS](https://supabase.com/docs/guides/database/postgres/row-level-security),
[Fernet](https://cryptography.io/en/latest/fernet/).

Final offline totals and exact changed-file inventory are appended after verification.


## Final verification results

- Full offline Python: **1,050 passed, 1 skipped**, 13 subtests passed. The skipped
  preexisting test needs an original diagnostic artifact intentionally not copied.
- Frontend: **117 passed** across 17 files; TypeScript/production build passed.
- Existing anatomy chunk-size and Starlette test-client warnings remain.
- Source/secret/built-bundle audit and `git diff --check`: passed. No staged files.
  All 32 pinned teammate/dataset source hashes and five original guard artifacts
  remain unchanged. Original frontend worktree is clean.
- Actual local HTTP: the refreshed offline server on 5175 returns account setup
  unavailable and login HTML 200. This is not real provider/browser verification.
- Real Supabase auth, delivery, PostgreSQL RLS, real two-user access and browser
  Secure-cookie acceptance: **not verified; blocked by the absent project**.
- 16E does not create/alter an external project, apply SQL or create credentials.
- History currently lists the most recent 100 archives; no pagination is claimed.

## Exact working-tree file inventory

This includes the prior dashboard typography CSS and its preserved layout import;
16E did not discard those changes. Generated files, logs, tests' synthetic databases,
source PNGs and installed environments remain ignored, not part of this inventory.

- `ACCOUNTS-16E.md`
- `api/accounts/__init__.py`
- `api/accounts/config.example`
- `api/accounts/fictional.py`
- `api/accounts/migrations/001_archives.sql`
- `api/accounts/provider.py`
- `api/accounts/routes.py`
- `api/accounts/run.py`
- `api/accounts/service.py`
- `api/accounts/storage.py`
- `api/demo_fixture.py`
- `api/main.py`
- `api/requirements.txt`
- `api/tests/test_accounts.py`
- `frontend/src/App.tsx`
- `frontend/src/components/AccountAccess.tsx`
- `frontend/src/components/DashboardLayout.tsx`
- `frontend/src/components/OfflineDemoNotice.tsx`
- `frontend/src/dashboard-typography.css`
- `frontend/src/lib/accounts.ts`
- `frontend/src/lib/authCopy.ts`
- `frontend/src/pages/AccountAuth.tsx`
- `frontend/src/pages/Accounts.test.tsx`
- `frontend/src/pages/Auth.tsx`
- `frontend/src/pages/MyPrescriptions.tsx`
- `frontend/src/pages/Workspace.tsx`
