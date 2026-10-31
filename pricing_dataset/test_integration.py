"""All altered prices/identities below are synthetic temporary test fixtures."""
import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from pricing_dataset.audit import BASE, digest, export, identity_key, load_audit, normalized_unit_price, source_manifest
from pricing_dataset.lookup import lookup

META = {"identity_confirmed": True, "ingredient": "synthetic test ingredient",
        "strength": "650 mg", "dosage_form": "tablet", "pack_quantity": "15", "pack_unit": "tablet"}

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for p in BASE.glob("*.csv"): shutil.copy(p, self.base / p.name)
        shutil.copy(BASE / "collection_report.md", self.base / "collection_report.md")
        shutil.copy(BASE / "audit_reviews.json", self.base / "audit_reviews.json")
        shutil.copytree(BASE / "evidence", self.base / "evidence")

    def rows(self, kind):
        with (self.base / f"{kind}_prices.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def save_rows(self, kind, rows):
        with (self.base / f"{kind}_prices.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)

    def sync(self):
        """Only synthetic fixtures may self-approve evidence and reviews in tests."""
        doc = json.loads((self.base / "audit_reviews.json").read_text())
        reviews = {r["observation_id"]: r for r in doc["reviews"]}
        observations = self.rows("medicine") + self.rows("lab")
        by_file = {}
        for row in observations:
            by_file.setdefault(row["evidence_file"], []).append(row)
            if row["observation_id"] not in reviews:
                original = json.loads(json.dumps(doc["reviews"][0]))
                original["observation_id"] = row["observation_id"]
                doc["reviews"].append(original)
                reviews[row["observation_id"]] = original
            reviews[row["observation_id"]]["raw_sha256"] = digest(row)
        for name, rows in by_file.items():
            p = self.base / name
            evidence = json.loads(p.read_text())
            evidence.update(source_url=rows[0]["source_url"], collected_date=rows[0]["collected_date"],
                            observed_city=rows[0]["observed_city"], facts=rows)
            p.write_text(json.dumps(evidence), encoding="utf-8")
        doc["raw_manifest"] = source_manifest(self.base)
        (self.base / "audit_reviews.json").write_text(json.dumps(doc), encoding="utf-8")

    def set_review(self, oid, **values):
        p = self.base / "audit_reviews.json"
        doc = json.loads(p.read_text())
        next(r for r in doc["reviews"] if r["observation_id"] == oid).update(values)
        p.write_text(json.dumps(doc), encoding="utf-8")

    def promote(self, oid="MP001"):
        rows = self.rows("medicine")
        row = next(r for r in rows if r["observation_id"] == oid)
        old_evidence = self.base / row["evidence_file"]
        new_evidence = f"evidence/synthetic-{oid}.json"
        shutil.copy(old_evidence, self.base / new_evidence)
        row["evidence_file"] = new_evidence
        row.update(observed_city="Delhi", location_status="confirmed", availability="available",
                   price_type="displayed", conditions="")
        self.save_rows("medicine", rows)
        self.sync()
        self.set_review(oid, identity=META.copy(), reasons=[], ambiguous=False, conflict=False, offer="unconditional")

    def test_actual_audit_counts(self):
        data = load_audit(self.base)
        from collections import Counter
        self.assertEqual(Counter(a["classification"] for a in data["observations"]),
                         {"provisional": 9, "ambiguous": 10, "conflicting": 1})
        self.assertEqual(data["quotes"], [])
        self.assertEqual(data["comparisons"], [])

    def test_known_item_unavailable_not_zero(self):
        r = lookup(kind="medicine", item_id="MED001", base=self.base)
        self.assertEqual(r["state"], "unavailable")
        self.assertEqual(r["quotes"], [])
        self.assertIn("delhi_not_confirmed", r["reasons"])

    def test_no_match_and_no_fuzzy_matching(self):
        for name in ("Dolo", "Dolo 650", "unknown"):
            self.assertEqual(lookup(kind="medicine", name=name, base=self.base)["state"], "no_match")

    def test_name_case_whitespace(self):
        self.assertEqual(lookup(kind="medicine", name="  DOLO  650 tablet ", base=self.base)["item"]["item_id"], "MED001")

    def test_ambiguous_name(self):
        p = self.base / "medicine_catalogue.csv"
        with p.open(newline="") as f: rows = list(csv.DictReader(f))
        rows[1]["product_name"] = rows[0]["product_name"]
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        self.sync()
        r = lookup(kind="medicine", name="Dolo 650 Tablet", base=self.base)
        self.assertEqual(r["state"], "ambiguous")
        self.assertEqual(len(r["candidates"]), 2)

    def test_invalid_request(self):
        for kw in ({}, {"item_id": 9}, {"item_id": ""}, {"item_id": "MED001", "name": "Dolo"}, {"item_id": "MED001", "city": "Gurgaon"}):
            self.assertEqual(lookup(kind="medicine", base=self.base, **kw)["error_code"], "invalid_request")

    def test_matched_contract_synthetic(self):
        self.promote()
        r = lookup(kind="medicine", item_id="MED001", base=self.base)
        self.assertEqual(r["state"], "matched")
        q = r["quotes"][0]
        self.assertEqual(q["price_inr"], "31.00")
        self.assertEqual(q["city"], "Delhi")
        self.assertEqual(q["observed_at"], "2026-10-30")
        self.assertEqual(q["price_basis"], "15 tablets")
        self.assertTrue(q["source"]["url"].startswith("https://"))
        self.assertTrue(q["historical"])
        self.assertIsNone(q["normalized_unit_price"])

    def test_normalization_requires_exact_peers(self):
        row = {"display_price_inr": "31"}
        self.assertIsNone(normalized_unit_price(row, META))
        self.assertEqual(normalized_unit_price(row, META, comparable=True)["amount_inr"], "2.0667")
        self.assertIsNone(identity_key("medicine", {**META, "strength": None}))

    def test_two_platform_comparison_synthetic(self):
        self.promote()
        self.promote("MP009")
        data = load_audit(self.base)
        self.assertEqual(len(data["comparisons"]), 1)
        self.assertTrue(all(q["normalized_unit_price"] for q in data["quotes"]))

    def test_strength_and_form_not_interchangeable(self):
        self.promote()
        self.promote("MP009")
        self.set_review("MP009", identity={**META, "strength": "500 mg"})
        self.assertEqual(load_audit(self.base)["comparisons"], [])
        self.assertEqual(lookup(kind="medicine", item_id="MED001", base=self.base)["state"], "ambiguous")
        self.set_review("MP009", identity={**META, "dosage_form": "capsule"})
        self.assertEqual(load_audit(self.base)["comparisons"], [])

    def test_lab_count_is_not_identity(self):
        self.assertIsNone(identity_key("lab", {"identity_confirmed": True, "panel_count": 24}))
        meta = {"identity_confirmed": True, "analytes": ["A", "B"], "specimen": "serum", "method": "specified method", "preparation": "fasting"}
        self.assertNotEqual(identity_key("lab", meta), identity_key("lab", {**meta, "specimen": "urine"}))
        self.assertNotEqual(identity_key("lab", meta), identity_key("lab", {**meta, "analytes": ["A", "C"]}))

    def test_conditional_reviewer_cannot_promote(self):
        self.promote("MP009")
        rows = self.rows("medicine")
        rows[-1]["price_type"] = "conditional_offer"
        rows[-1]["conditions"] = "order above 1000"
        self.save_rows("medicine", rows); self.sync()
        self.assertEqual(load_audit(self.base)["quotes"], [])

    def test_conflict_overrides_eligible(self):
        self.promote()
        self.set_review("MP001", conflict=True)
        self.assertEqual(load_audit(self.base)["quotes"], [])
        self.assertEqual(load_audit(self.base)["observations"][0]["classification"], "conflicting")

    def test_conflicting_offer_review(self):
        self.promote()
        self.set_review("MP001", offer="conflicting")
        self.assertEqual(load_audit(self.base)["observations"][0]["classification"], "conflicting")

    def test_missing_urls_invalid_prices_duplicates_locations(self):
        for changes in ({"source_url": ""}, {"display_price_inr": "0"},
                        {"display_price_inr": "-1"}, {"display_price_inr": "NaN"},
                        {"display_price_inr": "Infinity"}, {"display_price_inr": "1.001"},
                        {"location_status": "confirmed"}, {"pack_size": "10 tablets"}):
            with self.subTest(changes=changes):
                rows = self.rows("medicine"); saved = [r.copy() for r in rows]
                rows[0].update(changes); self.save_rows("medicine", rows)
                self.assertEqual(lookup(kind="medicine", item_id="MED001", base=self.base)["error_code"], "dataset_invalid")
                self.save_rows("medicine", saved)
        rows = self.rows("medicine"); rows.append(rows[0].copy()); self.save_rows("medicine", rows)
        self.assertEqual(lookup(kind="medicine", item_id="MED001", base=self.base)["error_code"], "dataset_invalid")

    def test_explicit_missing_price_unavailable(self):
        rows = self.rows("medicine")
        rows[-1].update(display_price_inr="", price_type="missing", availability="unavailable", notes="Synthetic missing listing")
        self.save_rows("medicine", rows); self.sync()
        a = next(a for a in load_audit(self.base)["observations"] if a["observation_id"] == "MP009")
        self.assertEqual(a["classification"], "unavailable")
        self.assertEqual(lookup(kind="medicine", item_id="MED001", base=self.base)["quotes"], [])

    def test_conflicting_same_day_offers(self):
        rows = self.rows("lab")
        extra = rows[0].copy()
        extra.update(observation_id="SYNTHETIC_CONFLICT", pack_size="1 panel", display_price_inr="499")
        rows.append(extra)
        self.save_rows("lab", rows); self.sync()
        states = {a["observation_id"]: a["classification"] for a in load_audit(self.base)["observations"]}
        self.assertEqual(states["LP001"], "conflicting")
        self.assertEqual(states["SYNTHETIC_CONFLICT"], "conflicting")

    def test_stale_manifest_fails_closed(self):
        p = self.base / "collection_report.md"; p.write_text("changed")
        self.assertEqual(lookup(kind="lab", item_id="LAB009", base=self.base)["error_code"], "dataset_invalid")

    def test_missing_evidence_fails_closed(self):
        (self.base / "evidence" / "pe-labs.json").unlink()
        self.assertEqual(lookup(kind="lab", item_id="LAB009", base=self.base)["error_code"], "dataset_invalid")

    def test_lookup_read_only_and_export_deterministic(self):
        before = source_manifest(self.base)
        lookup(kind="medicine", item_id="MED001", base=self.base)
        export(self.base)
        first = (self.base / "verified_quotes.json").read_bytes()
        export(self.base)
        self.assertEqual(first, (self.base / "verified_quotes.json").read_bytes())
        self.assertEqual(before, source_manifest(self.base))

if __name__ == "__main__":
    unittest.main()
