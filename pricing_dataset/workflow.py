"""Offline collection validation. No network requests or model clients."""
import argparse
import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE = Path(__file__).resolve().parent
DOMAINS = {"tata_1mg": {"www.1mg.com", "1mg.com"},
           "pharmeasy": {"pharmeasy.in", "www.pharmeasy.in"},
           "apollo_247": {"www.apollo247.com", "apollo247.com"}}
PRICE_FIELDS = "observation_id,item_id,platform,source_url,source_kind,collected_date,requested_city,observed_city,location_status,currency,pack_size,display_price_inr,mrp_inr,price_type,conditions,availability,panel_count,comparability,evidence_file,notes".split(",")

def today():
    try:
        return datetime.now(ZoneInfo("Asia/Kolkata")).date()
    except ZoneInfoNotFoundError:
        from datetime import timezone, timedelta
        return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()

def read(base, name):
    with (base / name).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"{name}: missing/duplicate headers")
        rows = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError(f"{name}: malformed row width")
        return reader.fieldnames, rows

def eligible(row):
    return (row["location_status"] == "confirmed"
            and row["observed_city"] == "Delhi"
            and bool(row["display_price_inr"])
            and row["price_type"] == "displayed"
            and row["comparability"] == "exact_listing"
            and row["availability"] not in {"blocked", "unavailable", "not_displayed"})

def validate(base=BASE, require_target=False):
    errors, summary = [], {}
    all_ids = set()
    for kind, target in (("medicine", 30), ("lab", 10)):
        headers, catalogue = read(base, f"{kind}_catalogue.csv")
        required = {"item_id", "source_url", "verified_date", "verification_status",
                    "product_name" if kind == "medicine" else "investigation_name"}
        if kind == "medicine":
            required.add("pack_size")
        if not required <= set(headers):
            errors.append(f"{kind}: missing catalogue columns")
            continue
        ids = {}
        for c in catalogue:
            key = c["item_id"]
            if not key or key in ids:
                errors.append(f"{kind}: empty/duplicate catalogue ID {key}")
            ids[key] = c
            if not c["source_url"] or c["verification_status"] != "verified_identity":
                errors.append(f"{key}: catalogue identity not verified")
            if urlsplit(c["source_url"]).hostname not in set().union(*DOMAINS.values()):
                errors.append(f"{key}: invalid catalogue domain")
            try:
                d = date.fromisoformat(c["verified_date"])
                if d > today(): raise ValueError()
            except ValueError:
                errors.append(f"{key}: invalid/future verification date")
        headers, rows = read(base, f"{kind}_prices.csv")
        if headers != PRICE_FIELDS:
            errors.append(f"{kind}: price schema differs from contract")
            continue
        seen, platforms, covered, observed = set(), {}, set(), set()
        for r in rows:
            oid, key = r["observation_id"], r["item_id"]
            def fail(message):
                errors.append(f"{oid or '(empty ID)'}: {message}")
            if not oid or oid in all_ids:
                fail("empty/duplicate observation ID")
            all_ids.add(oid)
            if key not in ids: fail("unknown item_id")
            sig = (key, r["platform"], r["collected_date"], r["pack_size"], r["observed_city"])
            if sig in seen: fail("duplicate item/platform/day/pack/location observation")
            seen.add(sig)
            platforms.setdefault(key, set()).add(r["platform"])
            url = urlsplit(r["source_url"])
            if url.scheme != "https" or url.hostname not in DOMAINS.get(r["platform"], set()) or url.username:
                fail("invalid source URL/platform domain")
            if r["source_kind"] != "public_page": fail("source is not a public page")
            if r["currency"] != "INR": fail("currency must be INR")
            if r["requested_city"] != "Delhi": fail("requested city must be Delhi")
            if r["location_status"] not in {"confirmed", "different_city", "unconfirmed"}:
                fail("invalid location_status")
            if r["location_status"] == "confirmed" and r["observed_city"] != "Delhi":
                fail("confirmed location must be Delhi")
            if r["location_status"] == "different_city" and r["observed_city"] in {"", "Delhi"}:
                fail("different_city requires a non-Delhi city")
            if r["location_status"] == "unconfirmed" and r["observed_city"]:
                fail("unconfirmed city must be blank")
            try:
                d = date.fromisoformat(r["collected_date"])
                if d > today(): raise ValueError()
            except ValueError:
                fail("invalid/future collection date")
            amounts = {}
            for field in ("display_price_inr", "mrp_inr"):
                if r[field]:
                    try:
                        amount = Decimal(r[field])
                        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal(".01")):
                            raise ValueError()
                        amounts[field] = amount
                    except (InvalidOperation, ValueError):
                        fail(f"invalid positive INR amount: {field}")
            if len(amounts) == 2 and amounts["display_price_inr"] > amounts["mrp_inr"]:
                fail("display price exceeds MRP; resolve conflict before entry")
            if r["price_type"] not in {"displayed", "conditional_offer", "missing"}:
                fail("invalid price_type")
            if r["price_type"] == "missing":
                if r["display_price_inr"] or not r["notes"]:
                    fail("missing price must be blank with reason")
            elif not r["display_price_inr"]:
                fail("priced observation requires price")
            if r["price_type"] == "conditional_offer" and not r["conditions"]:
                fail("conditional offer requires conditions")
            if r["availability"] not in {"not_verified", "available", "unavailable", "blocked", "not_displayed"}:
                fail("invalid availability")
            if r["availability"] in {"blocked", "not_displayed"} and r["display_price_inr"]:
                fail("blocked/not displayed price must be blank")
            if r["comparability"] not in {"exact_listing", "panel_variant", "unresolved"}:
                fail("invalid comparability")
            if not r["pack_size"]: fail("missing pack/investigation size")
            if kind == "medicine" and key in ids and r["pack_size"] != ids[key]["pack_size"]:
                fail("pack differs from catalogue")
            if r["panel_count"] and (not r["panel_count"].isdigit() or int(r["panel_count"]) < 1):
                fail("invalid panel_count")
            try:
                rel = Path(r["evidence_file"])
                path = (base / rel).resolve()
                if rel.is_absolute() or not path.is_relative_to((base / "evidence").resolve()):
                    raise ValueError("evidence must stay within evidence/")
                evidence = json.loads(path.read_text(encoding="utf-8"))
                if (evidence["source_url"] != r["source_url"]
                    or evidence["collected_date"] != r["collected_date"]
                    or evidence["observed_city"] != r["observed_city"]
                    or not evidence["method"] or r not in evidence["facts"]):
                    raise ValueError("evidence does not match observation")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                fail(f"invalid/missing evidence: {exc}")
            if r["display_price_inr"] and r["location_status"] == "confirmed":
                observed.add(key)
            if eligible(r): covered.add(key)
        if any(len(p) > 3 for p in platforms.values()):
            errors.append(f"{kind}: more than three platforms for an item")
        summary[kind] = dict(target=target, catalogue=len(catalogue), observations=len(rows),
                             delhi_observed=len(observed), eligible_delhi=len(covered))
        if require_target and (len(catalogue) != target or len(covered) != target):
            errors.append(f"{kind}: target incomplete ({len(covered)}/{target} eligible Delhi items)")
    return errors, summary

def report(base=BASE):
    errors, summary = validate(base)
    lines = ["# Collection report", "", f"Report generated: {today()} (Asia/Kolkata).",
             "Pilot collection/review date: 2026-10-30. INR. Requested location: Delhi, India.",
             "", "**Status: pilot; full verified Delhi target NOT achieved.**", "",
             "| Type | Target | Verified identities | Observations | Delhi items with displayed amounts (including conditional) | Eligible unconditional Delhi items |",
             "|---|---:|---:|---:|---:|---:|"]
    for kind, s in summary.items():
        lines.append(f"| {kind} | {s['target']} | {s['catalogue']} | {s['observations']} | {s['delhi_observed']} | {s['eligible_delhi']} |")
    lines += ["", f"Structural validation: {'FAIL' if errors else 'PASS'}.",
              "Completion gate requires one unconditional exact-listing Delhi observation per item; three-platform coverage is optional.",
              "", "## Findings and exclusions",
              "- Tata 1mg: 8 medicine identities and prices from a public brand listing. Page location is Gurgaon; excluded from Delhi coverage. Exact displayed pack text retained. No MRP inferred when no struck-through amount is shown.",
              "- PharmEasy medicine: Dolo 650, 15 tablets, INR 23.56, MRP INR 32.28; offer requires order above INR 1000. Pincode unselected, excluded from Delhi coverage.",
              "- PharmEasy labs: 10 Delhi investigation families with coupon-discount listing amounts. Eligibility and collection fees not established, so these are conditional observations, not unconditional payable quotes.",
              "- Apollo 24|7 CBC: primary INR 399/MRP INR 998, while the city table states Delhi INR 430. Unresolved conflict. Panel includes 30 parameters versus PharmEasy's 24; marked panel_variant and excluded from direct comparison.",
              "- No stock availability, delivery/collection charges, composition or sample requirements inferred.",
              "- Evidence JSON contains normalized factual transcriptions of opened public pages, not full snapshots or independent authentication. Prices are historical observations and can change.",
              "- No authenticated access, bypasses, automated scraping, Gemini calls, frontend edits, commits or pushes performed.",
              "", "## Remaining collection",
              "- Verify remaining 22 medicine candidates in collection_targets.csv; pending candidates are absent from the verified catalogue.",
              "- Establish Delhi via normal location controls for medicine observations.",
              "- Obtain unconditional Delhi prices or explicitly retain conditional/missing states; resolve Apollo conflict and match lab panel contents before cross-platform comparison.",
              "- Research Tata 1mg lab and Apollo medicine matches; no unavailable price has been filled or inferred. Apollo lab navigation points medicine users to apollopharmacy.in; that domain was not silently treated as Apollo 24|7.",
              "- Review each platform's current access terms before further collection; stop and log restrictions rather than bypass them.",
              "", "## Reproduce",
              "Run workflow.py validate, workflow.py report, and workflow.py validate --require-target from pricing_dataset/ using Python 3.12.",
              "The final command intentionally returns nonzero for this pilot. Structural PASS is not dataset completion or source authentication.", ""]
    if errors: lines += ["## Validation errors", *[f"- {e}" for e in errors]]
    (base / "collection_report.md").write_text("\n".join(lines), encoding="utf-8")
    return errors, summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "report"])
    parser.add_argument("--require-target", action="store_true")
    args = parser.parse_args()
    errors, summary = report() if args.command == "report" else validate(require_target=args.require_target)
    print(json.dumps({"summary": summary, "errors": errors}, indent=2))
    raise SystemExit(bool(errors))
