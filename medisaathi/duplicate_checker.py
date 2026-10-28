
"""Detect duplicate active ingredients in a prescription."""

def find_duplicate_salts(medicines):
    """Return groups of medicines that share the same active ingredient.

    This function only flags duplicates for review. It does not diagnose
    interactions or recommend stopping or changing any medicine.
    """
    if not isinstance(medicines, list):
        raise TypeError("medicines must be a list")

    salts = {}

    for medicine in medicines:
        if not isinstance(medicine, dict):
            continue

        if medicine.get("needs_review") is True:
            continue

        salt = medicine.get("salt")

        if not salt or not str(salt).strip():
            continue

        normalized_salt = " ".join(str(salt).casefold().split())

        salts.setdefault(normalized_salt, []).append(medicine)

    duplicates = []

    for salt, matching_medicines in salts.items():
        if len(matching_medicines) > 1:
            duplicates.append({
                "salt": salt,
                "medicines": matching_medicines,
                "count": len(matching_medicines),
                "warning": (
                    "Multiple medicines have the same active ingredient. "
                    "Please review this with your doctor or pharmacist."
                ),
            })

    return duplicates
