"""15B audit and reproducible export. Raw CSV/evidence are never modified."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .workflow import BASE, read, today, validate

SCHEMA_VERSION = "15B.1"
STATES = {"verified", "provisional", "unavailable", "ambiguous", "conflicting"}
RAW_FILES = ["medicine_catalogue.csv", "medicine_prices.csv", "lab_catalogue.csv",
             "lab_prices.csv", "collection_report.md"]

def digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def source_manifest(base):
    paths = RAW_FILES + [str(p.relative_to(base)).replace("\\", "/")
                         for p in sorted((base / "evidence").glob("*.json"))]
    return {p: hashlib.sha256((base / p).read_bytes()).hexdigest() for p in paths}

def identity_key(kind, meta):
    """No inferred concentration, generic substitutions, or panel-count matching."""
    required = (("ingredient", "strength", "dosage_form", "pack_quantity", "pack_unit")
                if kind == "medicine" else
                ("analytes", "specimen", "method", "preparation"))
    if not meta.get("identity_confirmed") or any(not meta.get(k) for k in required):
        return None
    if kind == "medicine":
        try:
            q = Decimal(str(meta["pack_quantity"]))
            if not q.is_finite() or q <= 0:
                return None
        except Exception:
            return None
        if meta["pack_unit"] not in {"tablet", "capsule", "ml", "g", "sachet"}:
            return None
        return tuple(str(meta[k]).strip().casefold() for k in required)
    if not isinstance(meta["analytes"], list) or not all(isinstance(a, str) and a.strip() for a in meta["analytes"]):
        return None
    return (tuple(sorted(a.strip().casefold() for a in meta["analytes"])),
            *(str(meta[k]).strip().casefold() for k in required[1:]))

def normalized_unit_price(row, meta, *, comparable=False):
    """Only for fully matched medicine peers; never per lab parameter."""
    if not comparable or not identity_key("medicine", meta):
        return None
    amount = Decimal(row["display_price_inr"]) / Decimal(str(meta["pack_quantity"]))
    return {"amount_inr": str(amount.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)),
            "unit": meta["pack_unit"], "rounding": "ROUND_HALF_UP_4dp"}

def classify(kind, row, review):
    meta = review["identity"]
    reasons = list(review["reasons"])
    key = identity_key(kind, meta)
    if not key:
        reasons.append("identity_incomplete")
    if row["location_status"] != "confirmed" or row["observed_city"] != "Delhi":
        reasons.append("delhi_not_confirmed")
    if row["price_type"] != "displayed" or review["offer"] != "unconditional":
        reasons.append("conditional_or_unresolved_offer")
    if row["comparability"] != "exact_listing":
        reasons.append("variant_not_exact")
    if row["availability"] == "not_verified":
        reasons.append("availability_not_verified")
    if row["availability"] in {"unavailable", "blocked", "not_displayed"} or not row["display_price_inr"]:
        state = "unavailable"
        reasons.append("price_or_listing_unavailable")
    elif review["conflict"] or review["offer"] == "conflicting":
        state = "conflicting"
        reasons.append("conflicting_price_information")
    elif review["ambiguous"] or row["comparability"] != "exact_listing":
        state = "ambiguous"
    elif reasons:
        state = "provisional"
    else:
        state = "verified"
    return state, sorted(set(reasons)), key

def load_audit(base=BASE):
    base = Path(base)
    errors, _ = validate(base)
    if errors:
        raise ValueError("raw_validation_failed: " + "; ".join(errors))
    review_doc = json.loads((base / "audit_reviews.json").read_text(encoding="utf-8"))
    if review_doc["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported_review_version")
    if review_doc["raw_manifest"] != source_manifest(base):
        raise ValueError("raw_manifest_changed: re-audit required")
    reviews = review_doc["reviews"]
    if not isinstance(reviews, list) or len({r["observation_id"] for r in reviews}) != len(reviews):
        raise ValueError("duplicate_review")
    review_map = {r["observation_id"]: r for r in reviews}
    items, audits, rows_by_id, keys = [], [], {}, {}
    for kind in ("medicine", "lab"):
        _, catalogue = read(base, f"{kind}_catalogue.csv")
        _, observations = read(base, f"{kind}_prices.csv")
        for c in catalogue:
            items.append({"kind": kind, "item_id": c["item_id"],
                          "name": c["product_name" if kind == "medicine" else "investigation_name"],
                          "pack_size": c.get("pack_size")})
        for row in observations:
            oid = row["observation_id"]
            review = review_map.get(oid)
            if not review or review["raw_sha256"] != digest(row):
                raise ValueError(f"{oid}: missing_or_stale_review")
            if not date.fromisoformat(row["collected_date"]) <= date.fromisoformat(review["audited_at"]) <= today():
                raise ValueError(f"{oid}: future_audit")
            if review["offer"] not in {"unconditional", "conditional", "unresolved", "conflicting"}:
                raise ValueError(f"{oid}: invalid_offer_review")
            if not isinstance(review["conflict"], bool) or not isinstance(review["ambiguous"], bool):
                raise ValueError(f"{oid}: invalid_review_flags")
            if not isinstance(review["reasons"], list) or not all(isinstance(r, str) and r for r in review["reasons"]):
                raise ValueError(f"{oid}: invalid_review_reasons")
            state, reasons, key = classify(kind, row, review)
            audits.append({"observation_id": oid, "kind": kind, "item_id": row["item_id"],
                           "classification": state, "reasons": reasons,
                           "platform": row["platform"], "source_url": row["source_url"],
                           "city": row["observed_city"] or None,
                           "observed_at": row["collected_date"], "observed_at_precision": "date",
                           "price_basis": row["pack_size"], "identity": review["identity"],
                           "panel_count": row["panel_count"] or None,
                           "evidence_file": row["evidence_file"], "audited_at": review["audited_at"]})
            rows_by_id[oid] = row
            keys[oid] = key
    if set(review_map) != set(rows_by_id):
        raise ValueError("orphan_review")
    # Same item/platform/date/location must not conceal multiple contradictory offers.
    groups = defaultdict(list)
    for a in audits:
        r = rows_by_id[a["observation_id"]]
        groups[(r["item_id"], r["platform"], r["collected_date"], r["observed_city"])].append(a)
    for group in groups.values():
        prices = {Decimal(rows_by_id[a["observation_id"]]["display_price_inr"]) for a in group
                  if rows_by_id[a["observation_id"]]["display_price_inr"]}
        if len(prices) > 1:
            for a in group:
                a["classification"] = "conflicting"
                a["reasons"] = sorted(set(a["reasons"] + ["conflicting_offers"]))
    quotes = []
    for a in audits:
        if a["classification"] != "verified":
            continue
        r = rows_by_id[a["observation_id"]]
        quotes.append({"observation_id": a["observation_id"], "kind": a["kind"],
                       "item_id": a["item_id"], "source": {"platform": r["platform"], "url": r["source_url"]},
                       "city": "Delhi", "currency": "INR",
                       "price_inr": str(Decimal(r["display_price_inr"]).quantize(Decimal(".01"))),
                       "price_basis": r["pack_size"], "observed_at": r["collected_date"],
                       "observed_at_precision": "date", "historical": True,
                       "availability": r["availability"], "fees_included": None,
                       "normalized_unit_price": None, "identity": a["identity"]})
    # Only contemporaneous exact variants from distinct platforms form comparisons.
    comparable = defaultdict(list)
    for q in quotes:
        comparable[(q["kind"], q["item_id"], q["observed_at"], keys[q["observation_id"]])].append(q)
    comparisons = []
    for (kind, item_id, observed_at, _), group in comparable.items():
        if len({q["source"]["platform"] for q in group}) < 2:
            continue
        comparisons.append({"kind": kind, "item_id": item_id, "observed_at": observed_at,
                            "observation_ids": [q["observation_id"] for q in group],
                            "platforms": sorted({q["source"]["platform"] for q in group})})
        if kind == "medicine":
            for q in group:
                q["normalized_unit_price"] = normalized_unit_price(rows_by_id[q["observation_id"]],
                                                                   q["identity"], comparable=True)
    return {"schema_version": SCHEMA_VERSION, "historical": True,
            "items": items, "observations": audits, "quotes": quotes,
            "comparisons": comparisons, "raw_manifest": review_doc["raw_manifest"]}

def export(base=BASE):
    base = Path(base)
    data = load_audit(base)
    def save(name, value):
        (base / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    save("observation_audit.json", data)
    save("verified_quotes.json", {k: data[k] for k in ("schema_version", "historical", "quotes", "comparisons", "raw_manifest")})
    counts = Counter(a["classification"] for a in data["observations"])
    reasons = Counter(r for a in data["observations"] for r in a["reasons"])
    coverage = {"schema_version": SCHEMA_VERSION, "audited_at": "2026-10-31",
                "raw_observations": len(data["observations"]),
                "verified_medicine_quotes": sum(q["kind"] == "medicine" for q in data["quotes"]),
                "verified_lab_quotes": sum(q["kind"] == "lab" for q in data["quotes"]),
                "classifications": {s: counts[s] for s in sorted(STATES)},
                "exclusion_reason_counts": dict(sorted(reasons.items())),
                "comparisons": data["comparisons"],
                "excluded": [{"observation_id": a["observation_id"], "classification": a["classification"],
                              "reasons": a["reasons"]} for a in data["observations"] if a["classification"] != "verified"]}
    save("coverage.json", coverage)
    lines = ["# Milestone 15B coverage", "", "Audit date: 2026-10-31. Observations remain dated 2026-10-30.",
             "Offline audit of preserved evidence; no new prices collected or live-price claims.",
             "", f"Verified Delhi medicine quotes: **{coverage['verified_medicine_quotes']}**.",
             f"Verified Delhi lab quotes: **{coverage['verified_lab_quotes']}**.",
             f"Comparable exact variants across two or more platforms: **{len(data['comparisons'])}**.",
             "Normalized unit prices: none; no eligible exact peers exist.", "",
             "## Classification", "", "| State | Count |", "|---|---:|"]
    lines += [f"| {s} | {counts[s]} |" for s in sorted(STATES)]
    lines += ["", "## Every excluded observation", "", "| ID | State | Reasons |", "|---|---|---|"]
    lines += [f"| {a['observation_id']} | {a['classification']} | {', '.join(a['reasons'])} |"
              for a in data["observations"] if a["classification"] != "verified"]
    lines += ["", "## Identity and location assessment", "",
              "- MP001-MP008: exact display names/packs only, Gurgaon not Delhi. Ingredient not captured; several numeric strengths lack explicit units or liquid concentration denominators. MED005 has no strength. Historical catalogue label verified_identity means displayed identity only, not an integration-ready pharmaceutical identity.",
              "- MP009: Dolo 650/15 tablets shares a catalogue item with MP001, but has no selected pincode and requires order above INR 1000. Composition and strength unit are not captured in the retained evidence.",
              "- LP001-LP010: Delhi city listing, coupon-dependent prices. Specimen, assay method, full analyte list and preparation are not captured in retained JSON; parameter count alone cannot establish equivalence. Single-test counts also do not prove assay identity.",
              "- LP011: CBC, Delhi, 30 parameters versus PharmEasy 24. INR 399 primary block versus INR 430 in city table is unresolved. Specimen and full panel are absent from saved evidence. Conflicting classification takes precedence over ambiguous identity.",
              "- No Apollo Pharmacy observations exist. Apollo Pharmacy is a separate source identifier/domain if later explicitly added; it is never silently relabelled Apollo 24|7.",
              "- All stock states are not_verified. No record is classified unavailable merely because its Delhi price is unverified.",
              "- Classification precedence: unavailable explicit missing/blocked listing; conflicting; ambiguous identity/variant; provisional other gaps; verified only when all gates pass.",
              "", "## Integration readiness", "",
              "The read-only interface and empty verified subset are ready for integration of honest empty states. This pilot cannot support a cheapest-price ranking or cross-platform savings claims.",
              "Use lookup.py through the contract in HANDOFF.md. Raw prices are available for audit only, never returned as verified quotes.",
              "Dates have day precision; no timestamp or freshness is invented. Missing price is null/absent, never zero. MRP is not a selling quote. Fees are unknown.",
              "A source/CSV consistency check is not independent verification of a historical web page. Evidence consists of collector transcriptions, not snapshots.",
              "", "## Reproduce", "",
              "python -B -m pricing_dataset.audit --export",
              "python -B -m unittest discover -s pricing_dataset -p \"test_*.py\"",
              "", "Raw files and evidence hashes are pinned in audit_reviews.json; changes require a new audit. Re-export is deterministic. All outputs are derived, raw files are preserved.", ""]
    (base / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")
    return coverage

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    if args.export:
        print(json.dumps(export(), indent=2))
    else:
        print(json.dumps(load_audit(), indent=2))
