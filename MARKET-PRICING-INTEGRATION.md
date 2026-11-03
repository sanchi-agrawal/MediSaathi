# Medicine market pricing integration

## Existing work and cause of unavailable pricing

Person 2's implementation was already integrated: `api/vendor/person2/matcher.py`, its `data/medicines.csv`, the safe wrapper `api/team_matching.py`, and `api/team_routes.py`. The available Person 2 source tip is `5758fb01a164c13e0f38735ec83fadea2d4f890c` (`origin/price-data`). The separate historical pricing audit is on `feature/pricing-dataset` at `3f9664b`; its `pricing_dataset/HANDOFF.md`, `workflow.py`, `audit.py` and `lookup.py` are already present. No merge, cherry-pick or source-worktree edits were needed. Remote metadata was not refreshed.

The old medicine-pricing page intentionally accepted **zero verified quotes only**, with a disabled comparison action. Its catalogue had exact-name/ID lookup only. That behavior was correct for the old audited evidence but could not display this workbook's provisional observations. The old verified gate remains unchanged, including its lab page and all old datasets. `git diff feature/pricing-dataset -- pricing_dataset` showed no tracked modifications to those preserved files.

An additive workbook adapter reuses the existing price platform registry and name normalization without falsely satisfying missing evidence requirements. A separate provisional listings contract does not promote any row into verified quotes. Vite's default target was also wrong for the specified local runtime: it used 8000. Defaults now use frontend 5177 and backend 8005; an explicit proxy environment override remains supported.

## Workbook and import

Actual file: `C:\Users\ASHTAMI\Downloads\Medicine_Catalogue_and_Prices_Complete.xlsx`.

Actual headers:

- Medicine Catalogue: `med_id`, `brand_name`, `salt`, `strength`, `dosage_form`, `manufacturer`.
- Price Observations: `obs_id`, `med_id`, `platform`, `listed_name`, `mrp_inr`, `selling_price_inr`, `availability`, `city`, `url`, `category`.

`pricing_dataset/market.py` imports to `pricing_dataset/market_listings.json`. The exported data includes the workbook SHA-256, source filename, exact raw rows and validated normalized records. Runtime needs only this repository JSON, not Downloads, Excel or an additional dependency.

| Validation | Result |
| --- | ---: |
| Medicines accepted | 30 |
| Observations accepted | 90 |
| Rejected | 0 |
| Provisional | 90 |
| Tata 1mg | 30 |
| Apollo 24/7 / Apollo Pharmacy | 30 |
| PharmEasy | 30 |
| Delhi | 81 |
| Gurgaon | 9 |
| Recorded in stock | 89 |
| Recorded out of stock | 1 |
| Selling price above MRP | 0 |

Two numeric XML values (`80.59999999999999`, `91.34999999999999`) have Excel serialization tails. A documented tolerance of 0.000000001 INR permits normalization to paise; exact originals remain in `raw`, with `excel_numeric_precision_normalized` warnings. Genuine sub-paise prices, negative/nonfinite values, bad references, duplicate IDs/listings and unsupported/unsafe URLs fail validation. An above-MRP record, if introduced, stays provisional with a visible conflict warning, not an equivalent ranked offer.

No medicine ID remapping: workbook `ms_med_*` IDs remain separate from the audited `MED*` and matcher `person2:catalogue:*` namespaces. No speculative crosswalk. Re-importing the same workbook is deterministic/idempotent; a different workbook hash requires explicit reconciliation. Existing CSVs, evidence, verified export and price audit files were not overwritten.

Dates, pack sizes, delivery pincodes and independent verification remain unknown. No unit prices, savings or cheapest-offer recommendation. Sorting only changes the display order of provisional listed prices. Location and recorded availability remain explicit. Source URLs are copied exactly, validated against platform hosts, and opened with `noopener noreferrer`. No shopping-site requests were made.

## API and ownership

All routes run in the existing `api.local_server:app`; there is no pricing server.

- `POST /api/session`: establish/reuse current authenticated workspace, through existing local-auth middleware.
- `GET /api/pricing/listings/catalogue?q=Dolo%20650`: actual catalogue suggestions, metadata and coverage.
- `POST /api/pricing/listings/lookup`: strict body `{ "item_id": "ms_med_0002" }`; actual product and provisional observations. Unknown IDs yield `no_match`.
- Existing `GET /api/pricing/catalogue?kind=medicine`, `POST /api/pricing/lookup`, `GET /api/matching/current` and prescription matching/selection endpoints remain unchanged and available.

Cookies are included on same-origin fetches. Existing server-side authentication/origin controls are retained. Browser-supplied prices, verification claims or extra fields are rejected. Public catalogue data is not sourced from another user's private prescription workspace. Validation and operational failures return JSON; no fake fallback listings are supplied.

## Frontend

`/dashboard/medicine-pricing` now uses `MarketPricing`. Search by brand, ingredient, strength and form is case-insensitive and token-prefix based: Cetirizine does not match only the embedded substring in Levocetirizine. Results show full identities and require explicit product selection. Cards display source product name, MRP, dataset selling price, recorded availability, city, provisional status and exact source URL. Platform/location/availability filters and list-price sorting work. Async stale responses are discarded; explicit retry actions handle failures.

The existing sidebar route remains available. A dashboard card was added. The existing matching component now exposes a Compare Prices link for each confirmed prescription medicine. It prefills the name and carries `medicine_ref`; it does not silently reuse a matcher ID as a workbook ID or select a substitute. No prescription extraction, fields, confirmation status, layout or medical actions were changed. English/Hindi use the existing language store; themes inherit existing palette tokens, and layout uses responsive grids.

## Tests and limitations

- Full Python suite: **1,249 passed, 1 skipped, 13 subtests passed**.
- Final focused dataset/API tests: **40 passed, 13 subtests passed**, including the final token-search change and authenticated real HTTP integration.
- Full frontend suite: **247 passed**, 35 files.
- Production build: **passed**; existing large-chunk warning remains.
- `git diff --check`: passed; existing CRLF conversion notices only.
- Actual `api.local_server:app` was loaded with a temporary SQLite account database. A real loopback HTTP server exercised sign-in/session establishment, catalogue discovery, Dolo selection, all 30 product lookups/90 mapped rows and JSON validation errors. Two-user access was checked. External network/Gemini calls were forbidden. Test server terminated afterward; no account database or long-running service was replaced.
- Browser/visual verification and external source-page opening were **not performed**. Responsive CSS and Hindi/theme behavior passed component tests; actual viewport rendering still needs the manual check below.
- Imported facts are not independently verified live market offers. Catalogue composition is workbook metadata, not a verified clinical identity or substitution recommendation.
- No new dependencies, database changes, scheduling changes, provider calls, commits, pushes, merges or worktree switches.

## Exact files changed for this task

New:

- `pricing_dataset/market.py`
- `pricing_dataset/market_listings.json`
- `api/market_routes.py`
- `api/tests/test_market_pricing.py`
- `frontend/src/lib/marketPricing.ts`
- `frontend/src/lib/marketPricing.test.ts`
- `frontend/src/lib/marketPricingHindi.ts`
- `frontend/src/pages/MarketPricing.tsx`
- `frontend/src/pages/MarketPricing.test.tsx`
- `frontend/src/market-pricing.css`
- `MARKET-PRICING-INTEGRATION.md`

Modified (only pricing-related changes; earlier uncommitted work retained):

- `api/team_routes.py`
- `frontend/src/components/MedicineMatching.tsx`
- `frontend/src/lib/language.ts`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/Overview.tsx`
- `frontend/src/pages/TeamIntegration.test.tsx` (retains tests for legacy audited gate, adds prescription link test)
- `frontend/vite.config.ts`

## Start the complete application

Stop any existing instance in its own terminal with Ctrl+C first; do not run competing servers on the same ports. Restarting the API preserves local registered accounts but clears temporary prescription workspaces.

API PowerShell (real OCR configuration stays server-side; startup makes no Gemini request):

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH="$PWD\api\.venv\deps"
$env:MEDISAATHI_LOCAL_OFFLINE='0'
$env:MEDISAATHI_LOCAL_HTTPS='0'
$python='C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

For an offline OCR demonstration, set `MEDISAATHI_LOCAL_OFFLINE='1'` instead. Pricing always uses the real imported workbook records in both modes; it never calls Gemini.

Frontend in a second PowerShell terminal:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET='http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Open `http://localhost:5177`, sign in, open the dashboard's price comparison card or Medicine pricing sidebar entry, search Dolo, select Dolo 650, inspect all three platform observations, apply filters and open a provided source link. Repeat in Hindi/light mode and at mobile width. From a confirmed medicine in the existing Prescription Analysis matching section, click Compare Prices; verify prefilled search and explicit product selection. Source prices may differ now; the app does not claim current verification.

Revalidate portable data without Excel:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-TeamIntegration
& 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe' -B -m pricing_dataset.market
```
