"""Synthetic/mock evaluation only: no real reader, credentials, or network."""

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

import evaluate_printed_prescriptions as evaluation


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline evaluation attempted network access")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    directory = tmp_path_factory.mktemp("printed-evaluation") / "new-fixtures"
    truth = evaluation.generate_fixtures(directory)
    return directory, truth


def run(fixtures, change=None, cases=None):
    directory, truth = fixtures
    perfect = evaluation.mock_predictor(truth)

    def predictor(image):
        output = perfect(image)
        return change(output) if change else output

    return evaluation.evaluate_cases(truth, predictor, directory, cases)


def first_case(fixtures, change=None):
    return run(fixtures, change, ["printed_01"])


def test_fixture_inventory_and_coverage(fixtures):
    directory, truth = fixtures
    assert evaluation.load_ground_truth(directory) == truth
    assert len(truth["cases"]) == 13
    assert sum(len(c["medicines"]) for c in truth["cases"]) == 26
    assert len(list(directory.iterdir())) == 14
    assert {c["layout"] for c in truth["cases"]} >= {
        "single_column", "numbered", "tabular", "two_column", "wrapped_line"}
    records = [m["expected_fields"] for c in truth["cases"] for m in c["medicines"]]
    assert {r["form"] for r in records} == {"tablet", "capsule", "syrup", "drops"}
    assert {r["frequency_pattern"] for r in records} >= {"OD", "BD", "TDS", "SOS", None}
    assert any(r["strength"] is None for r in records)
    assert any(r["salt"] is not None for r in records)
    assert any(r["salt"] is None for r in records)
    for case in truth["cases"]:
        assert case["fictional"] is True
        assert case["patient_information"] == "none"
        assert evaluation.sha256((directory / case["image"]).read_bytes()) == case["image_sha256"]
        with Image.open(directory / case["image"]) as image:
            image.load()
            assert image.size == (1800, 1500)
            assert image.format in ("PNG", "JPEG")
    assert truth["rendering"]["banner"] == evaluation.BANNER


def test_weeks_remain_null(fixtures):
    case = fixtures[1]["cases"][11]
    record = case["medicines"][0]
    assert "2 weeks" in record["expected_fields"]["raw_text"]
    assert record["expected_fields"]["duration_days"] is None
    assert record["review_required"] is True


def test_committed_fixture_annotations_match_rendering_definitions():
    # Includes hash/decode verification of the actual 13 delivered images.
    truth = evaluation.load_ground_truth()
    for case, definition in zip(truth["cases"], evaluation.fixture_definitions()):
        for field in ("case_id", "image", "source_text", "medicines", "layout"):
            assert case[field] == definition[field]


def test_perfect_extraction(fixtures):
    report = run(fixtures)
    assert report["field_accuracy"] == {"correct": 156, "total": 156, "accuracy": 1.0}
    assert report["six_field_record_accuracy"]["correct"] == 26
    assert report["medicine_detection"] == {
        "matched": 26, "missing": 0, "extra": 0, "precision": 1, "recall": 1}
    assert report["non_null_field_accuracy"]["accuracy"] == 1
    assert report["review_flag_compliance"]["accuracy"] == 1
    assert report["ten_field_contract_validity"]["records"]["correct"] == 26
    assert report["ten_field_contract_validity"]["cases"]["correct"] == 13
    assert report["negative_control"]["accuracy"] == 1
    assert report["unsupported_value_errors"] == 0
    assert report["ambiguous_alignment_cases"] == []
    assert report["confirmation_required"] is True


def test_reordered_medicines_leave_metrics_unchanged(fixtures):
    original = run(fixtures)
    reordered = run(fixtures, lambda records: list(reversed(records)))
    for field in original:
        if field != "results":
            assert reordered[field] == original[field]


@pytest.mark.parametrize("field,wrong", [
    ("name", "Fictional-Wrong"), ("strength", "99 mg"), ("form", "capsule"),
    ("frequency_pattern", "BD"), ("duration_days", 7), ("timing", "before food"),
    ("duration_days", 3.0), ("duration_days", True), ("duration_days", "3"),
    ("name", "fictional-alba"), ("strength", "10  mg"), ("frequency_pattern", "OD "),
])
def test_wrong_fields_are_exact_type_aware(fixtures, field, wrong):
    def change(records):
        records[0][field] = wrong
        return records
    report = first_case(fixtures, change)
    assert report["field_accuracy"]["correct"] == 5
    assert report["field_scores"][field]["correct"] == 0
    assert report["six_field_record_accuracy"]["accuracy"] == 0


def test_null_null_scores_but_missing_medicine_gets_no_free_null_credit(fixtures):
    perfect = run(fixtures, cases=["printed_10"])
    assert perfect["field_accuracy"]["correct"] == 12
    missing = run(fixtures, lambda records: [], ["printed_10"])
    assert missing["field_accuracy"] == {"correct": 0, "total": 12, "accuracy": 0}
    assert missing["non_null_field_accuracy"]["correct"] == 0
    assert missing["non_null_field_accuracy"]["total"] < 12


def test_invented_null_field_is_unsupported(fixtures):
    def change(records):
        records[0]["duration_days"] = 14
        records[0]["salt"] = "Invented-Ingredient"
        return records
    report = run(fixtures, change, ["printed_12"])
    assert report["field_accuracy"]["correct"] == 5
    assert report["unsupported_value_errors"] == 2


def test_predicted_null_is_wrong_for_printed_value(fixtures):
    def change(records):
        records[0]["strength"] = None
        return records
    report = first_case(fixtures, change)
    assert report["field_accuracy"]["correct"] == 5
    assert report["non_null_field_accuracy"]["correct"] == 5


def test_missing_and_extra_medicines_penalize_all_six_fields(fixtures):
    missing = run(fixtures, lambda records: records[:2], ["printed_02"])
    assert missing["medicine_detection"]["missing"] == 1
    assert missing["field_accuracy"] == {"correct": 12, "total": 18, "accuracy": 12 / 18}
    extra = first_case(fixtures, lambda records: records + copy.deepcopy(records))
    assert extra["medicine_detection"]["extra"] == 1
    assert extra["field_accuracy"] == {"correct": 6, "total": 12, "accuracy": 0.5}
    assert extra["six_field_record_accuracy"]["total"] == 2


def test_completely_unrelated_medicine_is_missing_plus_extra(fixtures):
    def change(records):
        records[0]["raw_text"] = "ZZZZZZZZZZ"
        return records
    report = first_case(fixtures, change)
    assert report["medicine_detection"]["missing"] == 1
    assert report["medicine_detection"]["extra"] == 1
    assert report["field_accuracy"]["total"] == 12
    assert report["field_accuracy"]["correct"] == 0


def test_blank_raw_text_cannot_align(fixtures):
    def change(records):
        records[0]["raw_text"] = None
        return records
    assert first_case(fixtures, change)["medicine_detection"]["matched"] == 0


def test_alignment_threshold_is_frozen():
    # Exactly half is permitted; greater than half is excluded.
    assert evaluation.match_medicines([{"raw_text": "abcd"}], [{"raw_text": "abxy"}])["pairs"] == [(0, 0)]
    assert evaluation.match_medicines([{"raw_text": "abcd"}], [{"raw_text": "axyz"}])["pairs"] == []
    assert evaluation.POLICY["threshold"].startswith("distance / max(text lengths) <= 1/2")


def test_whitespace_collapsing_is_alignment_only(fixtures):
    def change(records):
        records[0]["raw_text"] = records[0]["raw_text"].replace(" ", "\n  ")
        records[0]["name"] += " "
        return records
    report = first_case(fixtures, change)
    assert report["medicine_detection"]["matched"] == 1
    assert report["field_scores"]["name"]["correct"] == 0


def test_ambiguous_alignment_is_flagged_and_reproducible():
    refs = [{"raw_text": "same", "name": "A"}, {"raw_text": "same", "name": "B"}]
    preds = [{"raw_text": "same", "name": "B"}, {"raw_text": "same", "name": "A"}]
    alignment = evaluation.match_medicines(refs, preds)
    assert alignment["ambiguous"] is True
    assert alignment["pairs"] == [(0, 1), (1, 0)]
    assert evaluation.match_medicines(refs, list(reversed(preds)))["pairs"] == [(0, 0), (1, 1)]


def test_matching_global_cardinality_instead_of_greedy():
    refs = [{"raw_text": "aaaa"}, {"raw_text": "aabb"}]
    preds = [{"raw_text": "aabc"}, {"raw_text": "aaaa"}]
    result = evaluation.match_medicines(refs, preds)
    assert result["pairs"] == [(0, 1), (1, 0)]


def test_request_failures_remain_in_every_denominator(fixtures):
    def fail(_):
        raise RuntimeError("SECRET /private/path?token=hidden server response")
    report = run(fixtures, fail)
    assert report["request_failures"] == 13
    assert report["medicine_detection"]["missing"] == 26
    assert report["field_accuracy"] == {"correct": 0, "total": 156, "accuracy": 0}
    assert report["six_field_record_accuracy"]["total"] == 26
    assert report["review_flag_compliance"]["correct"] == 0
    assert report["ten_field_contract_validity"]["cases"]["correct"] == 0
    assert report["negative_control"]["accuracy"] == 0
    assert "SECRET" not in json.dumps(report)
    assert all(c["error"] == "prediction_failed" for c in report["results"])


@pytest.mark.parametrize("value", [None, {}, "[]", 2])
def test_malformed_model_output_is_not_repaired(fixtures, value):
    report = first_case(fixtures, lambda _: value)
    assert report["results"][0]["error"] == "invalid_output"
    assert report["results"][0]["raw_output"] == value
    assert report["field_accuracy"]["total"] == 6
    assert report["field_accuracy"]["correct"] == 0


def test_non_dictionary_record_counts_as_extra_and_invalid(fixtures):
    report = first_case(fixtures, lambda _: ["invalid record"])
    assert report["medicine_detection"]["missing"] == 1
    assert report["medicine_detection"]["extra"] == 1
    assert report["ten_field_contract_validity"]["records"]["correct"] == 0
    assert report["results"][0]["raw_output"] == ["invalid record"]


def test_non_finite_output_fails_without_fabricating_values(fixtures):
    def change(records):
        records[0]["confidence"] = float("nan")
        return records
    result = first_case(fixtures, change)["results"][0]
    assert result["error"] == "invalid_output"
    assert result["raw_output_preserved"] is False
    assert result["raw_output"] is None


def test_extreme_confidence_is_invalid_without_aborting_evaluation(fixtures):
    def change(records):
        records[0]["confidence"] = 10 ** 1000
        return records
    report = first_case(fixtures, change)
    assert report["ten_field_contract_validity"]["records"]["correct"] == 0
    assert report["field_accuracy"]["correct"] == 6


@pytest.mark.parametrize("modification", ["missing", "extra", "bool_duration", "bad_confidence", "bad_review"])
def test_exact_ten_field_contract(fixtures, modification):
    def change(records):
        if modification == "missing":
            del records[0]["salt"]
        elif modification == "extra":
            records[0]["confirmed"] = True
        elif modification == "bool_duration":
            records[0]["duration_days"] = True
        elif modification == "bad_confidence":
            records[0]["confidence"] = 2.0
        else:
            records[0]["needs_review"] = "true"
        return records
    report = first_case(fixtures, change)
    assert report["ten_field_contract_validity"]["records"]["correct"] == 0
    assert report["ten_field_contract_validity"]["cases"]["correct"] == 0


def test_expected_missing_field_requires_review_even_high_confidence(fixtures):
    def change(records):
        for record in records:
            record["needs_review"] = False
        return records
    report = run(fixtures, change, ["printed_09"])
    assert report["review_flag_compliance"] == {"correct": 0, "total": 2, "accuracy": 0}
    assert report["field_accuracy"]["accuracy"] == 1
    assert report["confirmation_required"] is True


@pytest.mark.parametrize("confidence", [None, 0.1, "uncertain"])
def test_returned_uncertainty_requires_review_on_otherwise_complete_record(fixtures, confidence):
    def change(records):
        records[0]["confidence"] = confidence
        records[0]["needs_review"] = False
        return records
    report = first_case(fixtures, change)
    assert report["review_flag_compliance"] == {"correct": 0, "total": 1, "accuracy": 0}


def test_missing_scored_key_does_not_equal_expected_null(fixtures):
    def change(records):
        del records[0]["duration_days"]
        return records
    report = run(fixtures, change, ["printed_12"])
    assert report["field_scores"]["duration_days"]["correct"] == 0
    assert report["ten_field_contract_validity"]["records"]["correct"] == 0


def test_non_json_types_are_rejected_without_silent_conversion(fixtures):
    result = first_case(fixtures, lambda records: tuple(records))["results"][0]
    assert result["error"] == "invalid_output"
    assert result["raw_output_preserved"] is False


def test_ambiguous_case_is_reported_without_discarding_outputs(fixtures):
    report = first_case(fixtures, lambda records: records + copy.deepcopy(records))
    assert report["ambiguous_alignment_cases"] == ["printed_01"]
    assert len(report["results"][0]["raw_output"]) == 2


def test_empty_negative_control_success_and_hallucination(fixtures):
    perfect = run(fixtures, cases=["printed_13"])
    assert perfect["field_accuracy"]["accuracy"] is None
    assert perfect["negative_control"]["accuracy"] == 1
    sample = evaluation.mock_predictor(fixtures[1])(
        (fixtures[0] / fixtures[1]["cases"][0]["image"]).read_bytes())
    wrong = run(fixtures, lambda _: sample, ["printed_13"])
    assert wrong["negative_control"]["accuracy"] == 0
    assert wrong["medicine_detection"]["extra"] == 1
    assert wrong["field_accuracy"] == {"correct": 0, "total": 6, "accuracy": 0}


def test_no_mutation_of_predictions_or_ground_truth(fixtures):
    directory, truth = fixtures
    before = copy.deepcopy(truth)
    output = evaluation.mock_predictor(truth)((directory / truth["cases"][0]["image"]).read_bytes())
    original = copy.deepcopy(output)
    report = evaluation.evaluate_cases(truth, lambda _: output, directory, ["printed_01"])
    assert truth == before and output == original
    assert report["results"][0]["raw_output"] == original
    report["results"][0]["raw_output"][0]["name"] = "Changed-copy"
    assert output == original


def test_image_tampering_prevents_callback(fixtures, tmp_path):
    directory, truth = fixtures
    altered = tmp_path / "tampered"
    altered.mkdir()
    for path in directory.iterdir():
        (altered / path.name).write_bytes(path.read_bytes())
    with (altered / truth["cases"][0]["image"]).open("ab") as stream:
        stream.write(b"tampered")
    def forbidden(_):
        pytest.fail("Callback must not run after hash mismatch")
    with pytest.raises(ValueError, match="hash mismatch"):
        evaluation.evaluate_cases(truth, forbidden, altered)


def test_ground_truth_changes_are_rejected(fixtures):
    directory, truth = fixtures
    changed = copy.deepcopy(truth)
    changed["cases"][0]["medicines"][0]["expected_fields"]["name"] = "Changed"
    with pytest.raises(ValueError, match="differs"):
        evaluation.evaluate_cases(changed, lambda _: [], directory)


@pytest.mark.parametrize("ids", [["unknown"], ["printed_01", "printed_01"]])
def test_invalid_selection_rejected(fixtures, ids):
    with pytest.raises(ValueError, match="selection"):
        run(fixtures, cases=ids)


def test_generation_refuses_overwrite_without_changes(fixtures):
    directory, _ = fixtures
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(FileExistsError, match="nothing overwritten"):
        evaluation.generate_fixtures(directory)
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}


def test_rendering_is_deterministic(fixtures, tmp_path):
    directory, truth = fixtures
    new_dir = tmp_path / "second-render"
    second = evaluation.generate_fixtures(new_dir)
    assert truth == second
    for path in directory.iterdir():
        assert path.read_bytes() == (new_dir / path.name).read_bytes()


def test_mock_cli_and_verify_only(fixtures, capsys):
    directory, _ = fixtures
    evaluation.main(["verify", "--fixtures", str(directory)])
    assert json.loads(capsys.readouterr().out) == {"verified_images": 13, "medicines": 26}
    evaluation.main(["mock", "--fixtures", str(directory), "--cases", "printed_01", "printed_02", "printed_03"])
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "mock_only_NOT_measured_OCR_accuracy"
    assert report["case_count"] == 3
    assert report["field_accuracy"]["total"] == 42


def test_live_cli_always_disabled(capsys):
    with pytest.raises(SystemExit) as error:
        evaluation.main(["live", "--cases", "printed_01", "printed_02", "printed_03"])
    assert error.value.code == 2
    assert "DISABLED" in capsys.readouterr().err


def test_import_does_not_load_reader_or_cloud_sdk():
    path = Path(evaluation.__file__).resolve()
    code = (
        "import importlib.util, sys; "
        f"s=importlib.util.spec_from_file_location('offline_eval', {str(path)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "assert 'reader' not in sys.modules; assert 'google.genai' not in sys.modules; "
        "assert 'torch' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_standard_character_edit_distance():
    assert evaluation.edit_distance("kitten", "sitting") == 3
    assert evaluation.edit_distance("", "abc") == 3
    assert evaluation.edit_distance("OD", "od") == 2
