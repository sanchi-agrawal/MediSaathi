# Collection report

Report generated: 2026-10-30 (Asia/Kolkata).
Pilot collection/review date: 2026-10-30. INR. Requested location: Delhi, India.

**Status: pilot; full verified Delhi target NOT achieved.**

| Type | Target | Verified identities | Observations | Delhi items with displayed amounts (including conditional) | Eligible unconditional Delhi items |
|---|---:|---:|---:|---:|---:|
| medicine | 30 | 8 | 9 | 0 | 0 |
| lab | 10 | 10 | 11 | 10 | 0 |

Structural validation: PASS.
Completion gate requires one unconditional exact-listing Delhi observation per item; three-platform coverage is optional.

## Findings and exclusions
- Tata 1mg: 8 medicine identities and prices from a public brand listing. Page location is Gurgaon; excluded from Delhi coverage. Exact displayed pack text retained. No MRP inferred when no struck-through amount is shown.
- PharmEasy medicine: Dolo 650, 15 tablets, INR 23.56, MRP INR 32.28; offer requires order above INR 1000. Pincode unselected, excluded from Delhi coverage.
- PharmEasy labs: 10 Delhi investigation families with coupon-discount listing amounts. Eligibility and collection fees not established, so these are conditional observations, not unconditional payable quotes.
- Apollo 24|7 CBC: primary INR 399/MRP INR 998, while the city table states Delhi INR 430. Unresolved conflict. Panel includes 30 parameters versus PharmEasy's 24; marked panel_variant and excluded from direct comparison.
- No stock availability, delivery/collection charges, composition or sample requirements inferred.
- Evidence JSON contains normalized factual transcriptions of opened public pages, not full snapshots or independent authentication. Prices are historical observations and can change.
- No authenticated access, bypasses, automated scraping, Gemini calls, frontend edits, commits or pushes performed.

## Remaining collection
- Verify remaining 22 medicine candidates in collection_targets.csv; pending candidates are absent from the verified catalogue.
- Establish Delhi via normal location controls for medicine observations.
- Obtain unconditional Delhi prices or explicitly retain conditional/missing states; resolve Apollo conflict and match lab panel contents before cross-platform comparison.
- Research Tata 1mg lab and Apollo medicine matches; no unavailable price has been filled or inferred. Apollo lab navigation points medicine users to apollopharmacy.in; that domain was not silently treated as Apollo 24|7.
- Review each platform's current access terms before further collection; stop and log restrictions rather than bypass them.

## Reproduce
Run workflow.py validate, workflow.py report, and workflow.py validate --require-target from pricing_dataset/ using Python 3.12.
The final command intentionally returns nonzero for this pilot. Structural PASS is not dataset completion or source authentication.
