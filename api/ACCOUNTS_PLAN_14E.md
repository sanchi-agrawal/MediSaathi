# 14E account persistence plan — proposed, not implemented

## Current delivery and blocker

Authentication is **demo-only** and storage is **session-memory only**. The login/signup forms do not create accounts, authenticate, send credentials or protect data. The current cookie isolates anonymous demo sessions, not authenticated users. No real account A/B or durable-restart security claim is made. No account history or real logout has been fabricated.

The repository has no configured OIDC integration, provider registration, authenticated principal, database/repository layer or migrations. A usable provider issuer/client registration, approved callback origin, database and encryption/retention configuration have not been supplied. Dependencies for an authentication client/ORM are also absent. Installing packages alone would not establish these requirements. The user explicitly allowed completing navigation/languages with this plan when secure accounts were not ready.

AIIntegration has no public durable-checkpoint import API. Its IDs, confirmation bindings and trusted event receipts are private, per-instance state. Copying JSON confirmed flags into a new instance, pickling instances or writing its private dictionaries would bypass the current contract. A reviewed public restore boundary coordinated with Person 1 is a release blocker for restoring current approval authority across processes. Until then, persisted history can be read-only and Continue Review must explicitly require a fresh review/confirmation workflow; it must not pretend old approvals authorize new scheduling.

## Proposed implementation

Use provider-managed signup/login (OIDC authorization-code flow with PKCE) through a maintained backend client such as Authlib's [Starlette OIDC integration](https://docs.authlib.org/en/1.7.1/oauth2/client/web/starlette.html). Select and pin a supported version during implementation; the linked API reference is not a package-install instruction. Passwords, recovery and MFA stay with the provider. Never implement password storage in this app.

Use PostgreSQL for durable application data. Enforce owner predicates in every repository operation and add [row-level security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) as defense in depth. Run application queries under a non-owner, non-superuser role without BYPASSRLS; migration and administration roles must be separate. Policy tests must use the actual application role. These are future choices, not installed or configured services.

### Identity/session boundary

1. Map verified `(issuer, subject)` to an internal UUID; never use a browser-supplied user_id or email as ownership authority.
2. Validate OIDC issuer, audience, signature, expiration, nonce/state and PKCE with the maintained client. Keep short-lived login flow state server-side. If cross-site callback needs a temporary SameSite=Lax cookie, use a separate scoped/short-lived opaque flow handle, not a weakened application/demo cookie. Establish a rotated Secure/HttpOnly application session after callback.
3. Store only a digest of the random session handle in a server-side session table, linked to user_id, creation/expiry/revocation and auth epoch. Keep provider tokens server-side, encrypted if retained; no localStorage or JS-readable credential cookie.
4. Add `require_user` to every account record/image/review/confirmation/association/schedule route. Scope data and result IDs to that principal and bind revisions inside transactions. Do not rely on CORS or opaque record IDs for authorization.
5. Implement POST logout with CSRF protection: revoke the server session/auth epoch, expire its exact cookie and evict corresponding in-memory adapters. Outstanding mutations must recheck revocation before commit. Previously delivered data cannot be recalled.

### Data model

| Table | Required authority/binding fields |
| --- | --- |
| users | user_id, unique issuer/subject, created_at |
| account_sessions | handle_digest, user_id, expires_at, revoked_at, auth_epoch |
| prescriptions | prescription_id, user_id, stable public analysis_id, source version/hash, created_at, updated_at, deleted_at |
| section_versions | prescription_id/user_id FK, scope, revision, payload fingerprint, reviewed JSON, original extraction JSON, timestamps |
| confirmations | prescription_id/user_id, scope/revision/fingerprint, acknowledgement time, authenticated principal/auth epoch |
| associations | prescription_id/user_id, medicine reference, instruction ID, both source revisions, explicit acknowledgement time |
| schedule_plans | association_id/user_id, exact approved plan, plan_revision, source binding, approval time |
| schedules | user_id/prescription_id, plan/source bindings, strict validated engine payload, engine version, generated_at, revoked_at |
| source_images | user_id/prescription_id/source binding, private encrypted object reference, retention/consent/deletion metadata |

Preserve ten-field medicine JSON exactly, including nulls. Store instructions and investigations separately; never add dose/confirmed fields to medicine records. Use composite owner-aware FKs or equivalent repository constraints for associations/derived results. A transaction checks current revisions, writes changes and revokes dependent confirmations/associations/plans/results atomically. Approved history must be distinguishable from current authority. A process restart must not resurrect an approval whose source or plan changed.

### Restore boundary and explicit adoption

Define a versioned, validated server-only checkpoint format and public restore operation with Person 1 before enabling durable confirmation restoration. Preserve public analysis IDs, source hashes, scope revisions, fingerprints, owner identity and scheduler version. Never accept imported approval authority from browser JSON. Reject unsupported schema/checkpoints; require renewed confirmation where exact verification is impossible. Test restart restoration, stale results, tampered snapshots and software upgrades before enabling it.

Anonymous records are not silently copied on login. Offer explicit “Save this current demo prescription to my account” consent. Read the current anonymous source from its server cookie, never from trusted browser JSON; rotate session authority and write ownership transactionally. Reconfirm records under the authenticated principal and revoke the anonymous associations/approvals rather than promoting anonymous boolean claims to account authority.

### Images, retention and deployment

Use private object storage, TLS and managed encryption/key access. Bind encrypted data to the owner/record/version; keep encryption keys outside the repository and database. Never expose public image URLs or source content in logs. Require owner/session checks for streaming images, Cache-Control:no-store and short-lived access where signed URLs are used. Store no image in localStorage.

Before deployment choose and publish retention/deletion/backup windows, consent rules and storage region. Implement and test scheduled deletion, owner-triggered deletion and backup lifecycle; do not claim immediate erasure before it is measured. Limit image access separately from durable text retention. Add request/body limits, rate limits, monitoring with technical-only metadata, encrypted backups and restore drills. No legal compliance claim is implied by this design.

### Files and routes to implement next

- api/auth/oidc.py, sessions.py, dependencies.py: provider flow, verified principal, server-side sessions/revocation.
- api/storage/models.py, repository.py and migrations/: owner/revision-aware durable schema and transactions.
- api/storage/images.py: private image encryption/access/deletion lifecycle.
- api/account_routes.py: GET /api/account/me; GET/POST /api/account/prescriptions; owner-checked view/review/confirm/associate/schedule/image/delete routes; explicit anonymous adoption; POST /api/auth/logout.
- Reviewed AI checkpoint adapter: public contract coordinated before authority restore; no private-state writes.
- frontend/src/pages/Auth.tsx: provider redirects and real session status, removing demo labels only after implementation passes.
- frontend/src/pages/MyPrescriptions.tsx: real owner-scoped history with View, Continue Review and Schedule links. No fabricated history in the current demo.
- Frontend account transport/provider: credentialed calls, no token storage, logout clears runtime workspace and outstanding requests.

## Release acceptance tests

Use two independent authenticated users and the real database role. A cannot list/read/edit/confirm/associate/schedule/delete B's IDs or retrieve B's image even with forged owner IDs and valid A credentials. Test absent/expired/revoked sessions, CSRF/state/nonce failures, logout during work, explicit adoption consent, transactional revocation on every relevant edit and server restarts. Only exact verified durable bindings may restore current authority; all other histories require reconfirmation. Verify deletion/backup behavior, encryption/key failures and private image access. Keep all OCR providers mocked in automated suites.

No account endpoint, database table, provider dependency or persistent medical storage is implemented by this plan.
