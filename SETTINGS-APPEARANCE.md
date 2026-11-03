# Local prototype settings and appearance

The latest requested password policy is **6–128 characters**, superseding the
earlier eight-character request. Six-character passwords are a **prototype-only
compromise** and are not suitable for deployment with real patient data. Argon2id
hashing, random opaque tokens, hashed-token storage, rate limiting, expiry,
HttpOnly/SameSite cookies and configured Secure-cookie handling are unchanged.
Existing password hashes/accounts need no migration or password reset. Login
continues verifying existing credentials; only new-password creation/change uses
the six-character floor. There is no ten-character maximum.

## Settings

Open `/dashboard/settings` through the sidebar or profile menu.

- Profile reads the authenticated backend's full name/email. Only the display
  name can be updated; user ID and email cannot be changed through this endpoint.
- Appearance switches the entire website between the original dark navy/coral
  theme and the new white/purple light theme. Only the non-sensitive preference
  is saved as `medisaathi.appearance` in localStorage.
- Language uses the existing English/हिंदी preference and translation store.
- Account & Security verifies the current password before changing it. The new
  password must be 6–128 characters and match its frontend confirmation. A change
  revokes **every session for that account**, clears this cookie and sends the
  user to Sign In. Session expiry and account creation timestamps come from `/me`.
- Privacy explains persistent identity versus temporary prescriptions. Explicit
  consent can clear the current session's medicine/instruction/investigation,
  strip and schedule workspace without deleting the account or another session.
- Danger Zone opens a native modal confirmation dialog. Deletion requires the
  current password and explicit consent; it redirects to Sign Up only after
  server success. Password fields are uncontrolled and cleared during submission.

Forgotten-password/email-based recovery is still unavailable. The local
`/reset-password` recovery screen remains accurately unavailable; a signed-in
user can use the current-password-verified change form in Settings. No insecure
reset endpoint or provider was introduced. The unused Supabase reset contracts
remain unchanged.

## API and ownership

Existing `/api/local-auth/signup`, `/login`, `/me`, `/logout` paths remain.
Additive mutation routes:

| Route under `/api/local-auth` | JSON body | Result |
| --- | --- | --- |
| `/profile` | `full_name` | Updated authenticated user |
| `/change-password` | `current_password`, `new_password` | Password changed, all sessions revoked |
| `/clear-workspace` | `confirm: true` | Current temporary workspace removed |
| `/delete-account` | `current_password`, `confirm: true` | Account/session rows deleted and cookie cleared |

All require a live authenticated cookie plus the existing allowed Origin and
`X-MediSaathi-Action: review` mutation protection. Strict schemas reject forged
user IDs/email changes and reject missing/false/non-boolean deletion consent.
Password verification remains Argon2; password changes and deletion are rate
limited. Login and destructive mutations are serialized with a SQLite
`BEGIN IMMEDIATE` transaction, preventing old credentials from creating a
session concurrently with a password change or deletion.

Deletion transactionally removes only the authenticated user's `sessions` rows
and `users` row. The corresponding in-memory workspaces are discarded after the
transaction commits. Other users are untouched. A database failure rolls back
account/session changes and leaves the cookie/workspace active for recovery;
the UI shows failure, not deletion success. The shared IP-based `auth_limits`
table is not account-owned and retains its normal bounded security window.

No SQLite schema/column migration is required. `created_at` already existed and
is now included in `/me`. The same ignored
`api/runtime/local-accounts.sqlite3` file remains in use. No existing users were
reset or deleted during implementation. Automated backend tests use temporary
databases. A separate HTTP smoke test created and deleted only its own newly
registered fictional account.

There is **no durable medical archive in local mode**. Deletion does not claim
to purge external archives, backups, provider storage, system logs or forensic
copies of database files. The response explicitly reports
`medical_archives_deleted: false`. No external storage service is contacted.

## Theme implementation

`theme-tokens.css` centralizes the existing dark colors and their light
equivalents. Its semantic palette uses the requested #FCFAFF background, white
cards, #F3EEFF secondary surfaces, #7C3AED primary, #5B21B6 dark purple,
#C4B5FD lavender, #221535 text, #6B6080 secondary text and #E9DDF8 borders.
Danger, warning and confirmed-success colors remain semantically distinct.

All existing application stylesheets reference central tokens rather than
embedding their own color values. `theme.css` handles light surfaces, forms,
sidebar/navbar, cards, review panels, tables and alerts. Settings/dialog styling
uses the same tokens. The full-height authentication illustration retains its
original dark overlay and colors; the form side follows the selected theme.
Anatomical model/medical image assets are unchanged.

The index bootstrap restores the theme before application startup, with a
matching initial background. Theme changes animate colors only, respect reduced
motion, and do not change layout dimensions. Cross-tab storage events synchronize
preferences. Existing language behavior, authentication and clinical data remain
separate from appearance preferences.

## Verification

- Full Python suite: **1,094 passed, 1 skipped**, 13 subtests. Existing absent
  diagnostic-artifact skip and Starlette test-client warning remain.
- Full frontend suite: **178 passed across 25 files**.
- TypeScript and production build passed. Main/anatomy chunk-size warnings remain.
- Boundary tests cover 5-character rejection, 6/7/8/128-character acceptance and
  129-character rejection; existing credentials still log in.
- Tests cover name ownership, password verification/all-session revocation,
  explicit deletion consent, cross-user isolation, deletion rollback and
  unchanged medical workflow/confirmation rules.
- UI tests cover Hindi Settings, theme persistence, clear-workspace consent,
  successful/failed deletion and unchanged identity after failures. Theme tests
  check central-token coverage, prepaint restoration and readable palette
  contrast. Actual HTTP through port 5177 verified signup/profile/change/clear/
  deletion/rejected login after deletion using one throwaway account.
- No interactive browser or screenshot QA was performed. Check desktop/mobile
  light-mode presentation manually before a public demo; do not claim visual QA
  from unit tests. No Gemini, Supabase or Telegram requests were made.

The dedicated local API on 8005 was restarted to load these changes. SQLite
identity survives; an API restart clears temporary medical workspaces. Existing
PowerShell launch commands in `LOCAL-ACCOUNTS.md` still apply. The frontend uses
the existing 5177 → 8005 `/api` proxy. No new dependencies were installed.

## Files changed for this task

- `api/local_auth.py`
- `api/tests/test_local_settings.py` (new)
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/lib/localAccounts.ts`
- `frontend/src/lib/passwordPolicy.ts` (new)
- `frontend/src/lib/theme.ts` (new)
- `frontend/src/lib/theme.test.tsx` (new)
- `frontend/src/lib/settingsHindi.ts` (new)
- `frontend/src/lib/language.ts`
- `frontend/src/components/LocalAccounts.tsx`
- `frontend/src/pages/Settings.tsx` (new)
- `frontend/src/pages/Settings.test.tsx` (new)
- `frontend/src/pages/LocalAccounts.test.tsx`
- `frontend/src/theme-tokens.css` (new)
- `frontend/src/theme.css` (new)
- `frontend/src/settings.css` (new)
- `frontend/src/styles.css`
- `frontend/src/anatomy.css`
- `frontend/src/dashboard-typography.css`
- `frontend/src/demo-login.css`
- `frontend/src/strip.css`
- `frontend/src/schedule.css`
- `LOCAL-ACCOUNTS.md`
- `SETTINGS-APPEARANCE.md` (this file)

Ignored edit/audit helpers and smoke tests remain under `api/.venv/`. Runtime
databases, diagnostic guards, source medical assets and original teammate
worktrees are excluded/untouched. No files were staged, committed or pushed.
