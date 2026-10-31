
import csv
from pathlib import Path

catalog_path = Path("data") / "medicines.csv"

with catalog_path.open("r", encoding="utf-8", newline="") as file:
    medicines = list(csv.DictReader(file))

print("Total medicines:", len(medicines))
print("First medicine:", medicines[0])

assert len(medicines) == 10
assert medicines[0]["catalog_id"] == "MED001"
assert medicines[0]["name"] == "Dolo 650"

print("Catalog test passed!")
