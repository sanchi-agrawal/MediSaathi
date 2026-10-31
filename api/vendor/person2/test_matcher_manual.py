
from matcher import match_medicine


catalog = [
    {
        "catalog_id": "MED001",
        "name": "Dolo 650",
        "salt": "Paracetamol",
        "strength": "650 mg",
        "form": "tablet",
    },
    {
        "catalog_id": "MED002",
        "name": "Cetirizine 10 mg",
        "salt": "Cetirizine",
        "strength": "10 mg",
        "form": "tablet",
    },
]


# Test 1: Exact medicine name should match.
result = match_medicine(
    {"name": "Dolo 650", "salt": "Paracetamol",
     "strength": "650 mg", "form": "tablet",
     "needs_review": False},
    catalog,
)
print("Test 1 — Exact match:", result["status"], result["catalog_id"])
assert result["status"] == "matched"
assert result["catalog_id"] == "MED001"


# Test 2: Unclear medicine must not be automatically matched.
result = match_medicine(
    {"name": "unclear", "needs_review": True},
    catalog,
)
print("Test 2 — Unclear medicine:", result["status"])
assert result["status"] == "unmatched"


# Test 3: Incompatible strength must not match.
result = match_medicine(
    {"name": "Dolo 650", "salt": "Paracetamol",
     "strength": "500 mg", "form": "tablet",
     "needs_review": False},
    catalog,
)
print("Test 3 — Conflicting strength:", result["status"])
assert result["status"] == "unmatched"

print("\nAll manual checks passed!")
