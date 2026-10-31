# Milestone 16B: frontend checkpoint and selective integration plan

Audit date: 2026-10-31. Parent checkpoint: `185000588e066ea1093c8f52596e0eb1ac47a279`.

Current source changes preserve the licensed anatomical organs, translucent skin,
real cortical brain, responsive layout, typography and English/Hindi landing UI.
Authentication-page source has no changes since the parent: login/signup remain
explicit UI previews, `authClient.connected` is false, and passwords are not sent
or saved. Accounts and durable prescription storage remain unimplemented.
Only the interface-language preference is stored in localStorage; prescription
data and authentication tokens are not stored there.

## Verification and licenses

- 96 frontend tests passed across 15 files.
- TypeScript and Vite production build passed. Existing anatomy chunk warning:
  approximately 642 kB uncompressed / 165 kB gzip, lazy-loaded.
- All three actual GLBs decoded using the shipped WASM decoder. Cerebrum SHA-256
  matches the source manifest. Geometry projection checks passed at four assumed
  canvas sizes; these are numerical checks, not browser visual verification.
- BodyParts3D organs/skin and adapted cortex: CC BY-SA 2.1 Japan; creator,
  distributor, source URLs, adaptation notes, source hashes and license links are
  shipped in `public/models/ATTRIBUTION.txt`, `LICENSE-BodyParts3D.txt` and
  `brain-sources.json`. UI links to attribution. Upstream notices checked:
  https://github.com/yamz8/human-body-simulator#bodyparts3d-skin-and-organ-assets
  and https://github.com/Kevin-Mattheus-Moerman/BodyParts3D/blob/main/LICENSE_content.
- No restricted Sketchfab, mixed-license skeleton, noncommercial or patient assets
  are included. Historical milestone reports describe earlier states; 14L and
  current source supersede them.
- Draco wrapper and WASM match the installed Three.js glTF decoder byte-for-byte;
  Apache 2.0 notice accompanies them. Three.js MIT and Noto Sans Devanagari SIL OFL
  notices are additionally included under `public/licenses/` for built distributions.
- No browser visual verification, Gemini calls or Telegram calls in this milestone.

## Excluded material

No `.env`, credentials, account tokens, cookies, medical records/images, runtime
authorization/guards, provider responses, virtual environments, node_modules,
build output, downloaded STL cache, test caches or tsbuildinfo enter the checkpoint.
The existing ignored runtime files remain in place. No teammate Python source is
changed. Source and lockfile text were reviewed and scanned for secret patterns.

## Isolated worktree

After the audited local commit, create `integration/team-16b` at that exact commit
in `C:\Users\ASHTAMI\MediSaathi-TeamIntegration`. Do not copy environments,
credentials or runtime state. The original frontend, AI and pricing worktrees
retain their own branches and files. Commit hash and clean-worktree verification
are reported in the delivery message. No teammate files are imported in 16B.

## Pinned selective imports for a later implementation milestone

### Person 2: `5758fb01a164c13e0f38735ec83fadea2d4f890c`

Candidate source modules, unchanged from this exact commit:

- `medisaathi/matcher.py`: `match_medicine(medicine, catalog)` with explicit
  matched / needs_confirmation / unmatched states; rapidfuzz dependency.
- `medisaathi/pricing.py`: pack arithmetic, delivery totals and
  `optimize_catalog_basket(medicines, price_records, pharmacy_settings)`.
- `medisaathi/price_data.py`: pandas CSV loading; relative module data directory.
- `medisaathi/alternatives.py`: same-salt/strength/form comparison with switching
  disclaimer; absolute `from pricing` import must resolve in an isolated namespace.
- `medisaathi/duplicate_checker.py`: same-salt review warnings, not interaction advice.

Candidate companion tests (standalone manual scripts, not a complete API suite):

- `medisaathi/test_matcher_manual.py`
- `medisaathi/test_pricing_manual.py`
- `medisaathi/test_catalog_manual.py`
- `medisaathi/test_alternatives_manual.py`
- `medisaathi/test_duplicate_checker_manual.py`

Keep these pinned data files in a separate example/unverified catalogue directory,
never the verified price source:

- `medisaathi/data/medicines.csv`: reference catalogue, not live quotes.
- `medisaathi/data/pharmacies.csv`: example Pharmacy A/B/C delivery settings.
- `medisaathi/data/pharmacy_prices.csv`: header only; no collected price rows.

Import future source into a clearly namespaced vendor directory with provenance
and byte hashes, preserving teammates' code. Resolve absolute imports and sibling
data paths deliberately before exposing routes. Do not import their app.py,
requirements.txt wholesale, .env examples or sample prescriptions. No lab-price
implementation exists in this pinned tree. Reconcile dependencies additively.

Required adapter boundaries: confirmed ten-field medicines stay unchanged;
catalogue choices are separate explicitly verified associations. Pricing quantities
come only from valid approved schedules. Enforce finite numeric values, positive
integer pack sizes, complete baskets, bounded optimization size and verified price
provenance/date/pincode. Partial baskets must never appear to price the entire
prescription. No prices means unavailable, not zero. Add API isolation, revision,
malformed-result and nonfinite-input tests before exposing the modules. Matching
scores are string similarity, not clinical equivalence or independent confirmation.

### Person 3: `e95a03166779fe2dbe501e868f9e8b4ee3025360`

Candidates:

- `medisaathi/reminders.py`: dose-log helpers, mark-taken, overdue/refill display,
  message builders; retain unchanged source in a vendor namespace initially.
- `medisaathi/tests/test_reminders.py`: companion tests use in-memory SQLite and
  injected senders. Review/run only with network disabled.

Do not replace `medisaathi/schedule.py` or `confirm_utils.py`: they are byte-identical
between this pinned commit and the current checkpoint. Existing guarded React/API
scheduling remains authoritative. Their existing tests need no duplicate imports.
Do not import Streamlit app.py or its confirmation path: it mixes dose fields into
medicine tables and cannot replace the independent AIIntegration scopes.

Block direct use of default `medisaathi.db`: no user/session ownership columns and
`load_schedule` deletes the entire dose log. Future adapter must isolate storage
per authorized session/user, bind approved schedule revisions, convert ISO dates
back to validated date objects, invalidate dependent logs on edits and treat clock
times as user preferences. Telegram sender functions remain unreachable; no sender
from environment, polling job or delivery route is enabled by this preparation.
Real delivery needs separate explicit authorization and account/isolation design.

## Recommended implementation order and blockers

1. Preserve checkpoint and clean isolated worktree (16B).
2. Vendor exact selected modules/tests with provenance in a later milestone.
3. Add safe confirmed-catalogue matching; add numerical/complete-basket guards.
4. Obtain verified price records and actual pharmacy settings before price results.
5. Add isolated, revision-bound dose-log UI using approved schedules; keep delivery off.
6. Implement maintained authentication and durable owned storage before multi-user deployment.

Unverified catalogue data, empty pharmacy prices, absent lab pricing and reminder
storage ownership are integration blockers, not checkpoint blockers. Browser
acceptance and actual GPU performance remain pending. No wholesale merge is needed.

## Exact checkpoint inventory

The remaining inventory is appended from the explicitly reviewed source manifest.
- `frontend/.gitignore`
- `frontend/CHECKPOINT-16B.md`
- `frontend/MILESTONE-14H.md`
- `frontend/MILESTONE-14J.md`
- `frontend/MILESTONE-14K.md`
- `frontend/MILESTONE-14K-BRAIN.md`
- `frontend/MILESTONE-14L.md`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/public/draco/draco_decoder.wasm`
- `frontend/public/draco/draco_wasm_wrapper.js`
- `frontend/public/draco/LICENSE.txt`
- `frontend/public/draco/README.md`
- `frontend/public/licenses/Noto-Sans-Devanagari-OFL.txt`
- `frontend/public/licenses/Three-MIT.txt`
- `frontend/public/models/anatomy-cerebrum.glb`
- `frontend/public/models/anatomy-organs.glb`
- `frontend/public/models/anatomy-skin.glb`
- `frontend/public/models/ATTRIBUTION.txt`
- `frontend/public/models/brain-sources.json`
- `frontend/public/models/LICENSE-BodyParts3D.txt`
- `frontend/scripts/build-brain.mjs`
- `frontend/scripts/fetch-brain-sources.py`
- `frontend/scripts/verify-anatomy.cjs`
- `frontend/scripts/verify-anatomy-framing.mjs`
- `frontend/src/anatomy.css`
- `frontend/src/App.tsx`
- `frontend/src/components/Anatomy.test.tsx`
- `frontend/src/components/Anatomy.tsx`
- `frontend/src/components/anatomyAppearance.test.ts`
- `frontend/src/components/anatomyAppearance.ts`
- `frontend/src/components/AnatomyFallback.tsx`
- `frontend/src/components/LanguageToggle.tsx`
- `frontend/src/components/ui.tsx`
- `frontend/src/lib/language.ts`
- `frontend/src/main.tsx`
- `frontend/src/pages/Landing.test.tsx`
- `frontend/src/pages/Landing.tsx`
