
from duplicate_checker import find_duplicate_salts

medicines = [
    {
        "name": "Medicine A",
        "salt": "Paracetamol",
        "needs_review": False,
    },
    {
        "name": "Medicine B",
        "salt": "  paracetamol  ",
        "needs_review": False,
    },
    {
        "name": "Medicine C",
        "salt": "Cetirizine",
        "needs_review": False,
    },
    {
        "name": "Unconfirmed Medicine",
        "salt": "Cetirizine",
        "needs_review": True,
    },
]

results = find_duplicate_salts(medicines)

assert len(results) == 1, "Expected one duplicate-salt warning"
assert results[0]["salt"] == "paracetamol"
assert results[0]["count"] == 2
assert "doctor or pharmacist" in results[0]["warning"].lower()

print("Duplicate salt:", results[0]["salt"])
print("Medicines flagged:", results[0]["count"])
print("Warning:", results[0]["warning"])
print("All duplicate-salt tests passed!")
