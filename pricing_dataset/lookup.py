"""Narrow read-only historical lookup, suitable for a thin FastAPI wrapper."""
from pathlib import Path
from .audit import BASE, SCHEMA_VERSION, identity_key, load_audit

def _name(value):
    return " ".join(value.casefold().split())

def lookup(*, kind, item_id=None, name=None, city="Delhi", base=BASE):
    """Exact ID or exact case/whitespace-normalized catalogue name; no fuzzy/salt matching."""
    result = {"schema_version": SCHEMA_VERSION, "state": "error", "historical": True,
              "item": None, "candidates": [], "quotes": [], "comparisons": [],
              "reasons": [], "error_code": None}
    if (kind not in ("medicine", "lab") or city != "Delhi"
        or (item_id is None) == (name is None)
        or any(v is not None and (not isinstance(v, str) or not v.strip()) for v in (item_id, name))):
        result["error_code"] = "invalid_request"
        return result
    try:
        data = load_audit(Path(base))
        matches = [i for i in data["items"] if i["kind"] == kind
                   and ((item_id is not None and i["item_id"] == item_id)
                        or (name is not None and _name(i["name"]) == _name(name)))]
        if not matches:
            result["state"] = "no_match"
            return result
        if len(matches) > 1:
            result.update(state="ambiguous", candidates=matches, reasons=["multiple_exact_catalogue_matches"])
            return result
        item = matches[0]
        result["item"] = item
        audits = [a for a in data["observations"] if a["kind"] == kind and a["item_id"] == item["item_id"]]
        quotes = [q for q in data["quotes"] if q["kind"] == kind and q["item_id"] == item["item_id"]]
        # Never silently choose among multiple exact variant signatures for one ID.
        identities = {identity_key(kind, q["identity"]) for q in quotes}
        if len(identities) > 1:
            result.update(state="ambiguous", reasons=["multiple_verified_variants"])
            return result
        if quotes:
            # Most recent historical observation per platform; no claim of current freshness.
            latest = {}
            for q in sorted(quotes, key=lambda q: (q["observed_at"], q["observation_id"])):
                latest[q["source"]["platform"]] = q
            result.update(state="matched", quotes=list(latest.values()))
            selected = {q["observation_id"] for q in result["quotes"]}
            result["comparisons"] = [g for g in data["comparisons"] if set(g["observation_ids"]) <= selected]
        else:
            result["state"] = "unavailable"
            result["reasons"] = sorted({r for a in audits for r in a["reasons"]} or {"no_verified_delhi_quote"})
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ArithmeticError):
        result["error_code"] = "dataset_invalid"
        return result
