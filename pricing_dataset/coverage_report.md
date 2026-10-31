# Milestone 15B coverage

Audit date: 2026-10-31. Observations remain dated 2026-10-30.
Offline audit of preserved evidence; no new prices collected or live-price claims.

Verified Delhi medicine quotes: **0**.
Verified Delhi lab quotes: **0**.
Comparable exact variants across two or more platforms: **0**.
Normalized unit prices: none; no eligible exact peers exist.

## Classification

| State | Count |
|---|---:|
| ambiguous | 10 |
| conflicting | 1 |
| provisional | 9 |
| unavailable | 0 |
| verified | 0 |

## Every excluded observation

| ID | State | Reasons |
|---|---|---|
| MP001 | provisional | availability_not_verified, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| MP002 | provisional | availability_not_verified, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| MP003 | provisional | availability_not_verified, concentration_denominator_not_captured, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| MP004 | provisional | availability_not_verified, delhi_not_confirmed, identity_incomplete, ingredient_not_captured |
| MP005 | provisional | availability_not_verified, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| MP006 | provisional | availability_not_verified, concentration_denominator_not_captured, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| MP007 | provisional | availability_not_verified, concentration_denominator_not_captured, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| MP008 | provisional | availability_not_verified, delhi_not_confirmed, identity_incomplete, ingredient_not_captured |
| MP009 | provisional | availability_not_verified, conditional_or_unresolved_offer, delhi_not_confirmed, identity_incomplete, ingredient_not_captured, strength_not_fully_captured |
| LP001 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP002 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP003 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP004 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP005 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP006 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP007 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP008 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP009 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP010 | ambiguous | assay_method_not_captured, availability_not_verified, conditional_or_unresolved_offer, identity_incomplete, panel_components_not_captured, preparation_not_captured, specimen_not_captured |
| LP011 | conflicting | assay_method_not_captured, availability_not_verified, cbc_30_vs_24_parameters, conflicting_price_information, identity_incomplete, panel_components_not_captured, preparation_not_captured, primary_price_399_vs_city_table_430, specimen_not_captured, variant_not_exact |

## Identity and location assessment

- MP001-MP008: exact display names/packs only, Gurgaon not Delhi. Ingredient not captured; several numeric strengths lack explicit units or liquid concentration denominators. MED005 has no strength. Historical catalogue label verified_identity means displayed identity only, not an integration-ready pharmaceutical identity.
- MP009: Dolo 650/15 tablets shares a catalogue item with MP001, but has no selected pincode and requires order above INR 1000. Composition and strength unit are not captured in the retained evidence.
- LP001-LP010: Delhi city listing, coupon-dependent prices. Specimen, assay method, full analyte list and preparation are not captured in retained JSON; parameter count alone cannot establish equivalence. Single-test counts also do not prove assay identity.
- LP011: CBC, Delhi, 30 parameters versus PharmEasy 24. INR 399 primary block versus INR 430 in city table is unresolved. Specimen and full panel are absent from saved evidence. Conflicting classification takes precedence over ambiguous identity.
- No Apollo Pharmacy observations exist. Apollo Pharmacy is a separate source identifier/domain if later explicitly added; it is never silently relabelled Apollo 24|7.
- All stock states are not_verified. No record is classified unavailable merely because its Delhi price is unverified.
- Classification precedence: unavailable explicit missing/blocked listing; conflicting; ambiguous identity/variant; provisional other gaps; verified only when all gates pass.

## Integration readiness

The read-only interface and empty verified subset are ready for integration of honest empty states. This pilot cannot support a cheapest-price ranking or cross-platform savings claims.
Use lookup.py through the contract in HANDOFF.md. Raw prices are available for audit only, never returned as verified quotes.
Dates have day precision; no timestamp or freshness is invented. Missing price is null/absent, never zero. MRP is not a selling quote. Fees are unknown.
A source/CSV consistency check is not independent verification of a historical web page. Evidence consists of collector transcriptions, not snapshots.

## Reproduce

python -B -m pricing_dataset.audit --export
python -B -m unittest discover -s pricing_dataset -p "test_*.py"

Raw files and evidence hashes are pinned in audit_reviews.json; changes require a new audit. Re-export is deterministic. All outputs are derived, raw files are preserved.
