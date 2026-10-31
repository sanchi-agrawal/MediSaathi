# MediSaathi pricing collection
Independent of frontend. Python 3.12 standard library only; no dependencies, model calls or Gemini requests.

Run from the worktree:
    python pricing_dataset/workflow.py validate
    python pricing_dataset/workflow.py report
    python pricing_dataset/workflow.py validate --require-target
    python -m unittest discover -s pricing_dataset -p "test_*.py"

The target gate fails until 30 medicines and 10 investigations each have an eligible Delhi observation. Up to three platforms per item is a maximum, not a promise of 120 prices.

## Collection procedure
1. Choose collection_targets.csv candidates. Candidates are a research queue, not verified catalogue records.
2. Browse normal public pages on Tata 1mg, Apollo 24|7 or PharmEasy. Check current site terms/access rules before further collection. No automated network fetching is implemented. Stop on robots restrictions, login, CAPTCHA, denial or rate limits; record the outcome in access_log.csv. No private APIs or bypasses. Search snippets are discovery only.
3. Select Delhi through normal location controls when possible. Record the actual displayed city. Use unconfirmed/different_city otherwise. A Delhi city URL establishes city context, not pincode serviceability.
4. Verify exact product, strength, formulation and pack. Never infer composition from brand. Different medicine packs/strengths are separate items. Lab families are not identical panels; retain panel_count and comparability.
5. Transcribe primary displayed price and labelled MRP separately. Blank means unknown, never zero. Never derive selling prices from discount percentages. Preserve coupon, membership and order-threshold conditions. Availability and fees are separate and must not be inferred.
6. Save small evidence JSON under evidence/ with source_url, collected_date, method, observed_city and facts containing full observations. These are human factual transcriptions, not independently authenticated snapshots. Retain screenshots where allowed; avoid medical prose. Dates use Asia/Kolkata collection/review day, not crawl/update dates.
7. Append unique observation_id rows to prices CSV and verified identities to catalogue. Missing/unavailable/blocked prices remain blank with price_type=missing and a reason in notes. Never invent source product URLs.
8. Run validate, tests and report. Review evidence and identity matches manually before release. Validation checks consistency, not independent source authenticity.

## Semantics
item_id is the stable join key. INR amounts are per listed pack/investigation, never silently per tablet.
location_status: confirmed (Delhi), different_city, unconfirmed.
price_type: displayed, conditional_offer, missing.
comparability: exact_listing, panel_variant, unresolved.
availability: not_verified, available, unavailable, blocked, not_displayed.
source_kind: public_page.
No shipping, collection fee or final payable amount is inferred. Historical observations remain dated; refresh by appending new IDs, not overwriting history. At most three distinct platforms per item; multiple dates per platform allowed.
A valid pilot is not a complete verified Delhi dataset. Read collection_report.md.

## Milestone 15B integration
Use HANDOFF.md and pricing_dataset.lookup.lookup for integration. verified_quotes.json is intentionally empty; coverage_report.md explains all exclusions. Legacy workflow.py validation is structural only. Run python -B -m pricing_dataset.audit --export and the unittest suite from the worktree root. Original raw files/evidence and collection_report.md are preserved and hash-pinned.
