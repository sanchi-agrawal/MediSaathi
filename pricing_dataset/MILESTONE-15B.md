# Milestone 15B checkpoint

Audit date: 2026-10-31. Branch: feature/pricing-dataset.
Base: main at 4cd507e (Initial scaffold). Local checkpoint only; no push or merge.

## Result
20 original price observations audited. Verified medicine quotes: 0. Verified lab quotes: 0.
Comparable medicine products across platforms: 0. Comparable lab variants across platforms: 0.
Classifications: 9 provisional, 10 ambiguous, 1 conflicting, 0 unavailable, 0 verified.
No normalized comparison unit prices are emitted.
All original CSVs, original collection report, and source evidence are preserved byte-for-byte.
SHA-256 manifest validates the 5 raw dataset files plus 4 evidence files.

## Why excluded
8 Tata 1mg records show Gurgaon. PharmEasy medicine has no selected location and an order-threshold offer.
10 PharmEasy labs have conditional coupon prices and incomplete variant/specimen/assay evidence.
Apollo CBC has INR 399 versus INR 430 on the same historical source, and 30 versus 24 parameters across platforms.
Every exclusion is itemized in coverage_report.md and machine-readable coverage.json.

## Validation
30 unittest cases pass: original 10 plus 20 integration tests.
Tests cover exact names/IDs, ambiguity, malformed requests, known-item unavailability,
successful synthetic quotes, invalid/nonfinite/zero prices, duplicate observations,
missing source URLs, missing evidence, location/pack/strength/form mismatch,
conditional and conflicting offers, missing prices, staleness, normalization,
read-only lookup and deterministic export.
All synthetic prices/identities are confined to temporary test directories.
Raw structural validation passes. Staged raw blobs must exactly match all 9 pinned SHA-256 hashes; scoped Git attributes disable newline conversion for raw provenance. Legacy original-target gate still fails as expected.
No network collection or Gemini requests performed.

## Exact milestone file changes
All paths below are relative to pricing_dataset/:

Added:
- .gitattributes (preserve raw provenance bytes across checkouts)
- __init__.py
- audit.py
- audit_reviews.json
- lookup.py
- test_integration.py
- observation_audit.json
- verified_quotes.json
- coverage.json
- coverage_report.md
- HANDOFF.md
- MILESTONE-15B.md

Updated:
- README.md (15B integration entry point only)

Unmodified original pilot files included in the first local checkpoint because the pilot was untracked:
- .gitignore
- access_log.csv
- collection_targets.csv
- medicine_catalogue.csv
- medicine_prices.csv
- lab_catalogue.csv
- lab_prices.csv
- collection_report.md
- workflow.py
- test_workflow.py
- evidence/1mg-list.json
- evidence/pe-dolo.json
- evidence/pe-labs.json
- evidence/apollo-cbc.json

Checkpoint inventory is 27 files, all within pricing_dataset/. No secrets, caches, temporary
scripts or unrelated worktrees belong in the checkpoint. Temporary setup helpers remain
outside the repository and are not staged. Commit hash is reported separately after creation.

## Person 2
Recommended minimal endpoint: GET /api/pricing?kind=medicine&item_id=MED001&city=Delhi.
Call pricing_dataset.lookup.lookup; no FastAPI/frontend files are added in this worktree.
State is matched, no_match, ambiguous, unavailable, or error.
Valid quotes carry source, city, price_basis and observed_at with historical=true.
See HANDOFF.md for exact fields and HTTP/UI handling. A known identity without an eligible quote
is unavailable, not a zero price or an out-of-stock assertion.
