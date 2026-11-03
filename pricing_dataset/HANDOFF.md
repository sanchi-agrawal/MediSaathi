# Person 2 handoff: historical Delhi pricing

Milestone 15B prepares an offline read-only integration boundary. It does not provide live pricing, procurement advice, or a currently serviceable quote.

Verified subset: verified_quotes.json (empty intentionally).
Full record decisions: observation_audit.json.
Coverage and every exclusion: coverage.json / coverage_report.md.
Original collection_report.md and all four original CSVs/evidence remain byte-for-byte preserved.

## Python contract

From the worktree root:

    from pricing_dataset.lookup import lookup
    result = lookup(kind="medicine", item_id="MED001", city="Delhi")
    result = lookup(kind="lab", name="CBC Test", city="Delhi")

Use exactly one of item_id or name. kind is medicine or lab. Only Delhi is supported. Names match exact catalogue names after case folding and whitespace normalization; no partial, fuzzy, ingredient, synonym or salt substitution. Stable IDs are preferred.

The function reads and validates local CSV/evidence/reviews on every call. It does not write, fetch, call models or trust an unchecked export. Missing/corrupt/stale data fails closed. For this small pilot it deliberately revalidates rather than caching mutable files.

Return object fields:

- schema_version: "15B.1"
- state: matched | no_match | ambiguous | unavailable | error
- historical: true
- item: {kind, item_id, name, pack_size} or null
- candidates: exact catalogue matches only for ambiguous names
- quotes: verified quotes only, otherwise []
- comparisons: contemporaneous exact variants on 2+ distinct platforms only
- reasons: machine-readable exclusion codes
- error_code: invalid_request | dataset_invalid | null

State meanings:
matched = exact identity with one or more verified historical quotes.
no_match = requested identity absent; no unavailable-price inference.
ambiguous = multiple exact catalogue identities or verified variants; no automatic choice.
unavailable = identity found, but no verified Delhi quote; does NOT mean out of stock.
error = invalid request or dataset integrity/validation failure. A wrapper should log operational errors separately; don't show filesystem details to end users.

Each valid quote includes:
observation_id, kind, item_id, source {platform,url}, city, currency,
price_inr (positive decimal string), price_basis (per listed pack/investigation),
observed_at ("YYYY-MM-DD"), observed_at_precision ("date"), historical (true),
availability, fees_included (null when unknown), identity, normalized_unit_price.

observed_at is the original collection date; audit date is not a price refresh.
An observed date has no fabricated time-of-day. Source snapshot and availability are historical.
No missing value is replaced with zero. MRP is excluded from quotes and ranking.
Prices exclude unverified fees; do not label them final payable amounts.
All current pilot calls for known items return unavailable with quotes=[].

## Suggested thin FastAPI endpoint

GET /api/pricing?kind=medicine&item_id=MED001&city=Delhi

Call lookup with query arguments and return its JSON. Suggested HTTP mapping:
200 for matched/no_match/ambiguous/unavailable; 422 for invalid_request;
503 for dataset_invalid. The wrapper, endpoint, frontend and deployment are Person 2's work; none are changed here.

React should display "No verified Delhi price available" for unavailable,
"Choose an exact product/test" for ambiguous, and "Historical price observed on [date]"
beside every quote. Only comparison groups may drive cross-platform savings/ranking.
A single verified quote is a historical reference, not a comparison.

## Verification policy

Medicine identity requires explicit ingredient, strength with units/concentration,
dosage form, pack quantity/unit and confirmed exact match; same brand string is insufficient.
Lab identity requires full analytes, specimen, method and preparation; same family/count is insufficient.
Verified price requires confirmed Delhi context, explicit unconditional selling price,
available listing, no unresolved conflicts and complete identity.
Non-Delhi, unconfirmed, conditional, incomplete or conflicting observations stay in audit only.
Manual reviews bind to SHA-256 of each raw row and the full raw/evidence manifest.
This guards staleness, not malicious rewriting or independent source authenticity.

Classification precedence: unavailable > conflicting > ambiguous > provisional > verified.
The lookup state unavailable describes eligible quote coverage, distinct from audit classification unavailable.

Unit normalization is computed only for verified contemporaneous exact medicine variants
with peers on two or more platforms, from explicit pack quantity/unit using Decimal.
Four decimal places, ROUND_HALF_UP; pack price remains authoritative.
No liquid concentration conversions, cross-strength comparisons or per-lab-parameter prices.
Across dates, lookup returns latest historical quote per platform; comparisons must share a date.
Apollo Pharmacy, if collected later, needs its own explicit platform/domain registration;
no existing price is attributed to it.

## Reproduce

    python -B -m pricing_dataset.audit --export
    python -B -m unittest discover -s pricing_dataset -p "test_*.py"

Legacy workflow.py validate checks raw structure only; it is not the 15B integration gate.
Use load_audit/lookup and verified_quotes.json for integration. Do not regenerate the preserved
collection_report.md unless deliberately re-auditing its changed hash.
No new web collection, frontend/scheduling edits, Gemini requests, push or merge in this milestone.
