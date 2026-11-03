import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from workflow import BASE, validate

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for path in BASE.glob("*.csv"): shutil.copy(path, self.base / path.name)
        shutil.copytree(BASE / "evidence", self.base / "evidence")

    def change(self, name, mutator):
        path = self.base / name
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f); fields = reader.fieldnames; rows = list(reader)
        mutator(rows)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

    def test_pilot_passes_structure(self):
        errors, summary = validate(self.base)
        self.assertEqual(errors, [])
        self.assertEqual(summary["medicine"]["eligible_delhi"], 0)
        self.assertEqual(summary["lab"]["eligible_delhi"], 0)

    def test_pilot_fails_target(self):
        errors, _ = validate(self.base, True)
        self.assertTrue(any("target incomplete" in e for e in errors))

    def test_invalid_amounts(self):
        for amount in ("-1", "0", "NaN", "Infinity", "1.001"):
            with self.subTest(amount=amount):
                self.change("medicine_prices.csv", lambda rows: rows[0].update(display_price_inr=amount))
                self.assertTrue(any("invalid positive INR" in e for e in validate(self.base)[0]))

    def test_pack_mismatch(self):
        self.change("medicine_prices.csv", lambda rows: rows[0].update(pack_size="10 tablets"))
        self.assertTrue(any("pack differs" in e for e in validate(self.base)[0]))

    def test_spoofed_domain(self):
        self.change("medicine_prices.csv", lambda rows: rows[0].update(source_url="https://www.1mg.com.evil.test/x"))
        self.assertTrue(any("domain" in e for e in validate(self.base)[0]))

    def test_fabricated_delhi_confirmation(self):
        self.change("medicine_prices.csv", lambda rows: rows[0].update(location_status="confirmed"))
        self.assertTrue(any("confirmed location" in e for e in validate(self.base)[0]))

    def test_evidence_missing(self):
        (self.base / "evidence" / "1mg-list.json").unlink()
        self.assertTrue(any("evidence" in e for e in validate(self.base)[0]))

    def test_duplicate(self):
        self.change("medicine_prices.csv", lambda rows: rows.append(rows[0].copy()))
        self.assertTrue(any("duplicate" in e for e in validate(self.base)[0]))

    def test_missing_price_requires_reason(self):
        self.change("medicine_prices.csv", lambda rows: rows[0].update(price_type="missing",display_price_inr="",notes=""))
        self.assertTrue(any("blank with reason" in e for e in validate(self.base)[0]))

    def test_evidence_path_escape(self):
        self.change("medicine_prices.csv", lambda rows: rows[0].update(evidence_file="../outside.json"))
        self.assertTrue(any("within evidence" in e for e in validate(self.base)[0]))

if __name__ == "__main__":
    unittest.main()
