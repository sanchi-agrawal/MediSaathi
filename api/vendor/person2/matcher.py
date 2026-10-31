
import re

from rapidfuzz import fuzz, process

AUTO_MATCH_THRESHOLD = 85
REVIEW_THRESHOLD = 60

UNUSABLE_NAMES = {"", "unclear", "unknown", "n/a", "none", "null"}
UNNECESSARY_WORDS = {"tab", "cap", "syp"}
DETAIL_FIELDS = ("salt", "strength", "form")


def normalize_name(name):
    """Normalize medicine text by removing dosage abbreviations and punctuation."""
    if not isinstance(name, str):
        return ""

    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    words = name.split()
    words = [word for word in words if word not in UNNECESSARY_WORDS]

    return " ".join(words)


def _empty_result(message):
    """Return a consistent result when a medicine cannot be matched."""
    return {
        "status": "unmatched",
        "catalog_id": None,
        "matched_name": None,
        "score": 0,
        "candidates": [],
        "message": message,
    }


def _details_are_compatible(medicine, catalog_item):
    """Reject candidates that conflict with known salt, strength, or form."""
    for field in DETAIL_FIELDS:
        prescription_value = medicine.get(field)
        catalog_value = catalog_item.get(field)

        if prescription_value and catalog_value:
            prescription_detail = normalize_name(str(prescription_value))
            catalog_detail = normalize_name(str(catalog_value))

            if prescription_detail != catalog_detail:
                return False

    return True


def match_medicine(medicine, catalog):
    """
    Match a prescription medicine against catalog brand names and salts.

    Scores:
        85-100: automatic match, with user verification
        60-84: user confirmation required
        Below 60: unmatched; manual selection is needed

    Medicines marked needs_review are never automatically matched.
    Known salt, strength, and form conflicts are rejected.
    """
    if not isinstance(medicine, dict):
        raise TypeError("medicine must be a dictionary")

    if not isinstance(catalog, list):
        raise TypeError("catalog must be a list")

    prescription_name = normalize_name(medicine.get("name"))

    if medicine.get("needs_review") or prescription_name in UNUSABLE_NAMES:
        return _empty_result(
            "Medicine details need review before matching."
        )

    valid_entries = [
        item
        for item in catalog
        if isinstance(item, dict)
        and item.get("catalog_id") is not None
        and (
            normalize_name(item.get("name"))
            or normalize_name(item.get("brand"))
            or normalize_name(item.get("salt"))
        )
    ]

    if not valid_entries:
        return _empty_result("No usable catalog entries were found.")

    compatible_entries = [
        item
        for item in valid_entries
        if _details_are_compatible(medicine, item)
    ]

    if not compatible_entries:
        return _empty_result(
            "No catalog entries match the known medicine details."
        )

    # Compare the prescription text against both the brand/name and salt.
    # Keep the stronger score so salt-based searches are also supported.
    candidate_names = []
    candidate_scores = []

    for item in compatible_entries:
        brand_name = normalize_name(
            item.get("brand") or item.get("name")
        )
        catalog_name = normalize_name(item.get("name"))
        salt_name = normalize_name(item.get("salt"))

        names_to_compare = {
            name
            for name in (brand_name, catalog_name, salt_name)
            if name
        }

        best_score = max(
            (
                fuzz.WRatio(prescription_name, name)
                for name in names_to_compare
            ),
            default=0,
        )

        candidate_names.append(catalog_name or brand_name)
        candidate_scores.append(round(best_score))

    # Rank entries by their best brand/name/salt similarity score.
    ranked_indices = sorted(
        range(len(compatible_entries)),
        key=lambda index: candidate_scores[index],
        reverse=True,
    )[:5]

    candidates = []

    for index in ranked_indices:
        item = compatible_entries[index]
        candidates.append(
            {
                "catalog_id": item["catalog_id"],
                "name": item.get("name") or item.get("brand"),
                "brand": item.get("brand"),
                "salt": item.get("salt"),
                "strength": item.get("strength"),
                "form": item.get("form"),
                "score": candidate_scores[index],
            }
        )

    if not candidates:
        return _empty_result("No usable matching candidates were found.")

    best = candidates[0]
    score = best["score"]

    if score >= AUTO_MATCH_THRESHOLD:
        return {
            "status": "matched",
            "catalog_id": best["catalog_id"],
            "matched_name": best["name"],
            "score": score,
            "candidates": candidates,
            "message": (
                "Automatic match found. Please verify the medicine details."
            ),
        }

    if score >= REVIEW_THRESHOLD:
        return {
            "status": "needs_confirmation",
            "catalog_id": None,
            "matched_name": None,
            "score": score,
            "candidates": candidates,
            "message": (
                "Please choose the correct medicine from the candidates."
            ),
        }

    return {
        "status": "unmatched",
        "catalog_id": None,
        "matched_name": None,
        "score": score,
        "candidates": candidates,
        "message": (
            "No sufficiently close match. Select a medicine manually."
        ),
    }
