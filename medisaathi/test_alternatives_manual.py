
from alternatives import find_cheaper_alternatives


catalog = [
    {
        "catalog_id": "MED001",
        "name": "Medicine A",
        "salt": "Paracetamol",
        "strength": "500 mg",
        "form": "tablet",
        "pack_size": 10,
    },
    {
        "catalog_id": "MED002",
        "name": "Medicine B",
        "salt": "Paracetamol",
        "strength": "500 mg",
        "form": "tablet",
        "pack_size": 10,
    },
    {
        "catalog_id": "MED003",
        "name": "Medicine C",
        "salt": "Paracetamol",
        "strength": "650 mg",
        "form": "tablet",
        "pack_size": 10,
    },
]

price_records = [
    {
        "catalog_id": "MED002",
        "pack_size": 10,
        "price_inr": 40,
        "pharmacy": "Pharmacy A",
    },
    {
        "catalog_id": "MED003",
        "pack_size": 10,
        "price_inr": 20,
        "pharmacy": "Pharmacy A",
    },
]

results = find_cheaper_alternatives(
    selected_medicine=catalog[0],
    selected_unit_price=5.00,
    catalog=catalog,
    price_records=price_records,
)

assert len(results) == 1, "Expected exactly one valid alternative"
assert results[0]["catalog_id"] == "MED002", "Wrong alternative returned"
assert results[0]["unit_price"] == 4.00, "Unit price calculation is incorrect"
assert "doctor or pharmacist" in results[0]["disclaimer"].lower()

print("Cheaper alternative:", results[0]["name"])
print("Unit price: Rs.", results[0]["unit_price"])
print("Safety disclaimer:", results[0]["disclaimer"])
print("All alternative tests passed!")
