"""Offline synthetic generation and frozen-score regression checks."""

import copy
import json
import shutil
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

import evaluate_printed_prescriptions as original
import printed_benchmark as benchmark


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Network forbidden in printed benchmark tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    directory = tmp_path_factory.mktemp("scale-benchmark") / "printed150"
    truth = benchmark.generate(directory)
    return directory, truth


def test_deterministic_independent_source_plan():
    first = benchmark.definitions()
    assert first == benchmark.definitions(42)
    assert first != benchmark.definitions(43)
    assert len(first) == 150
    assert len({c["case_seed"] for c in first}) == 150
    assert len({c["case_id"] for c in first}) == 150
    assert Counter(c["medicine_count"] for c in first) == {0: 10, 1: 28, 2: 28, 3: 28, 4: 28, 5: 28}
    records = [m["expected_fields"] for c in first for m in c["medicines"]]
    assert len(records) == 420 and len({r["name"] for r in records}) == 420
    old_names = {m["expected_fields"]["name"] for c in original.fixture_definitions() for m in c["medicines"]}
    assert not old_names.intersection(r["name"] for r in records)
    assert all(r["name"].startswith("Fictional-") for r in records)


@pytest.mark.parametrize("seed", [True, -1, 2**32, "42", None])
def test_invalid_seeds_rejected(seed):
    with pytest.raises(ValueError, match="Seed"):
        benchmark.definitions(seed)


def test_heldout_templates_and_balanced_factors():
    cases = benchmark.definitions()
    development = [c for c in cases if c["cohort"] == "development"]
    holdout = [c for c in cases if c["cohort"] == "template_holdout"]
    assert len(development) == 120 and len(holdout) == 30
    assert {c["template"] for c in development} == set(benchmark.DEVELOPMENT)
    assert {c["template"] for c in holdout} == set(benchmark.HOLDOUT)
    assert not set(benchmark.DEVELOPMENT).intersection(benchmark.HOLDOUT)
    assert not set(benchmark.HOLDOUT).intersection(c["layout"] for c in original.fixture_definitions())
    assert Counter(c["font_family"] for c in cases) == dict.fromkeys(benchmark.FONT_FAMILIES, 30)
    assert Counter(c["quality"] for c in cases) == dict.fromkeys(benchmark.QUALITY_LEVELS, 50)
    assert Counter(c["background"] for c in cases) == dict.fromkeys(benchmark.BACKGROUNDS, 30)
    assert {c["variation"] for c in cases} == {1, 2, 3}
    assert all(c["fictional"] is True and c["patient_information"] == "none" for c in cases)


def test_annotations_come_only_from_printed_sources():
    records, weeks = [], []
    for case in benchmark.definitions():
        for item, lines in zip(case["medicines"], case["source_blocks"]):
            record = item["expected_fields"]
            records.append(record)
            assert set(record) == set(original.EXTRACTED_FIELDS)
            assert record["raw_text"] == "\n".join(lines)
            for field in ("name", "salt", "strength", "form", "frequency_pattern", "timing"):
                if record[field] is not None:
                    assert record[field] in record["raw_text"]
            assert item["review_required"] == any(v is None for v in record.values())
            if item["duration_kind"] == "weeks":
                weeks.append(item)
                assert record["duration_days"] is None
                assert "weeks" in record["raw_text"]
                assert item["review_required"] is True
            elif item["duration_kind"] == "missing":
                assert record["duration_days"] is None and item["duration_source"] is None
    assert weeks
    assert {r["form"] for r in records} == {None, "tablet", "capsule", "syrup", "drops"}
    assert {r["frequency_pattern"] for r in records} == set(benchmark.FREQUENCIES) | {None}
    assert any(r["salt"] is None for r in records)
    assert any(r["salt"] is not None for r in records)
    assert any(r["strength"] is None for r in records)


def test_150_images_hashes_inventory_and_metadata(fixtures):
    directory, truth = fixtures
    assert benchmark.validate(directory) == truth
    assert len(list(directory.iterdir())) == 151
    assert len({c["image_sha256"] for c in truth["cases"]}) == 150
    assert truth["policy"] == original.POLICY
    assert truth["policy_sha256"] == benchmark._digest(original.POLICY)
    assert truth["provenance"]["original13_ground_truth_sha256"] == original.sha256(
        (original.DEFAULT_FIXTURES / "ground_truth.json").read_bytes())
    assert len({v["sha256"] for k, v in truth["provenance"]["fonts"].items() if k != "header"}) == 5
    for case in truth["cases"]:
        path = directory / case["image"]
        assert original.sha256(path.read_bytes()) == case["image_sha256"]
        with Image.open(path) as image:
            image.load()
            assert image.mode == "RGB"
            assert image.width * image.height <= 8_000_000
            assert path.stat().st_size <= 10 * 1024 * 1024
        for line in case["rendered_lines"]:
            assert line["bounds"][2] <= case["size"][0]
            assert line["bounds"][3] <= case["size"][1]
        assert any(line["text"] == original.BANNER for line in case["rendered_lines"])


def test_reproducible_image_bytes_across_fonts_layouts_and_quality(fixtures, tmp_path):
    directory, truth = fixtures
    # Every template and quality is represented in this bounded byte regression.
    indices = set()
    for template in benchmark.DEVELOPMENT + benchmark.HOLDOUT:
        indices.add(next(i for i, c in enumerate(truth["cases"]) if c["template"] == template))
    for quality in benchmark.QUALITY_LEVELS:
        indices.add(next(i for i, c in enumerate(truth["cases"]) if c["quality"] == quality))
    for index in sorted(indices):
        case = truth["cases"][index]
        target = tmp_path / case["image"]
        metadata = benchmark.render(case, target)
        assert metadata == case["rendered_lines"]
        assert target.read_bytes() == (directory / case["image"]).read_bytes()


def test_overwrite_protection(fixtures):
    directory, truth = fixtures
    before = original.sha256((directory / "ground_truth.json").read_bytes())
    with pytest.raises(FileExistsError):
        benchmark.generate(directory)
    case = truth["cases"][0]
    with pytest.raises(FileExistsError):
        benchmark.render(case, directory / case["image"])
    assert original.sha256((directory / "ground_truth.json").read_bytes()) == before


def test_failed_generation_does_not_publish_partial_directory(monkeypatch, tmp_path):
    output = tmp_path / "new-benchmark"
    def fail(*args, **kwargs):
        raise ValueError("Synthetic rendering failure")
    monkeypatch.setattr(benchmark, "render", fail)
    with pytest.raises(ValueError, match="rendering failure"):
        benchmark.generate(output)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_perfect_mock_all_denominators_and_one_call_per_case(fixtures):
    directory, truth = fixtures
    perfect = original.mock_predictor(truth)
    calls = []
    def predictor(data):
        calls.append(original.sha256(data))
        return perfect(data)
    report = benchmark.evaluate(directory, predictor)
    assert len(calls) == len(set(calls)) == 150
    assert report["field_accuracy"] == {"correct": 2520, "total": 2520, "accuracy": 1.0}
    assert report["non_null_field_accuracy"]["total"] == benchmark.describe(truth)["non_null_scored_fields"]
    assert report["six_field_record_accuracy"]["correct"] == 420
    assert report["medicine_detection"] == {"matched": 420, "missing": 0, "extra": 0, "precision": 1, "recall": 1}
    assert report["negative_control"] == {"correct": 10, "total": 10, "accuracy": 1.0}
    assert report["ten_field_contract_validity"]["records"]["correct"] == 420
    assert report["review_flag_compliance"]["accuracy"] == 1
    assert report["unsupported_value_errors"] == 0
    assert report["original13_results_included"] is False
    cohort_fields = [r["field_accuracy"] for r in report["cohort_reports"].values()]
    assert sum(f["total"] for f in cohort_fields) == 2520
    assert sum(f["correct"] for f in cohort_fields) == 2520


def test_request_failures_retained_and_redacted(fixtures):
    directory, _ = fixtures
    calls = []
    def fail(data):
        calls.append(data)
        raise RuntimeError("SECRET server payload https://private.invalid/?key=secret")
    report = benchmark.evaluate(directory, fail)
    assert len(calls) == 150
    assert report["request_failures"] == 150
    assert report["field_accuracy"] == {"correct": 0, "total": 2520, "accuracy": 0}
    assert report["medicine_detection"]["missing"] == 420
    assert report["negative_control"]["correct"] == 0
    assert "SECRET" not in json.dumps(report)
    assert all(r["error"] == "prediction_failed" for r in report["results"])
    assert sum(r["request_failures"] for r in report["cohort_reports"].values()) == 150


@pytest.mark.parametrize("mode", ["wrong", "type", "missing", "extra", "malformed", "reordered"])
def test_subset_scoring_regressions(fixtures, mode):
    directory, truth = fixtures
    case = next(c for c in truth["cases"] if c["medicine_count"] == 3)
    perfect = original.mock_predictor(truth)
    def predictor(data):
        output = perfect(data)
        if mode == "wrong":
            output[0]["name"] += " "
        elif mode == "type":
            output[0]["duration_days"] = True
        elif mode == "missing":
            output.pop()
        elif mode == "extra":
            output.append(copy.deepcopy(output[0]))
        elif mode == "malformed":
            return {"medicines": output}
        else:
            output.reverse()
        return output
    report = benchmark.evaluate(directory, predictor, [case["case_id"]])
    expected = {"wrong": (17, 18), "type": (17, 18), "missing": (12, 18),
                "extra": (18, 24), "malformed": (0, 18), "reordered": (18, 18)}[mode]
    assert (report["field_accuracy"]["correct"], report["field_accuracy"]["total"]) == expected


def test_null_review_and_week_semantics(fixtures):
    directory, truth = fixtures
    case = next(c for c in truth["cases"] if any(m["duration_kind"] == "weeks" for m in c["medicines"]))
    perfect = original.mock_predictor(truth)
    def predictor(data):
        records = perfect(data)
        for item, record in zip(case["medicines"], records):
            if item["duration_kind"] == "weeks":
                record["duration_days"] = 14
                record["needs_review"] = False
        return records
    report = benchmark.evaluate(directory, predictor, [case["case_id"]])
    assert report["unsupported_value_errors"] >= 1
    assert report["field_scores"]["duration_days"]["accuracy"] < 1
    assert report["review_flag_compliance"]["accuracy"] < 1


def test_no_medicine_control_contributes_no_field_credit(fixtures):
    directory, truth = fixtures
    case = next(c for c in truth["cases"] if c["medicine_count"] == 0)
    report = benchmark.evaluate(directory, lambda _: [], [case["case_id"]])
    assert report["field_accuracy"] == {"correct": 0, "total": 0, "accuracy": None}
    assert report["negative_control"]["accuracy"] == 1
    fake = original.mock_predictor(truth)((directory / truth["cases"][0]["image"]).read_bytes())[0]
    extra = benchmark.evaluate(directory, lambda _: [fake], [case["case_id"]])
    assert extra["negative_control"]["accuracy"] == 0
    assert extra["field_accuracy"] == {"correct": 0, "total": 6, "accuracy": 0}


@pytest.mark.parametrize("kind", ["annotation", "policy", "extra_file", "image", "missing_image"])
def test_tampering_blocks_every_predictor_call(fixtures, tmp_path, kind):
    source, _ = fixtures
    target = tmp_path / "tampered"
    shutil.copytree(source, target)
    path = target / "ground_truth.json"
    truth = json.loads(path.read_text(encoding="utf-8"))
    first_image = target / truth["cases"][0]["image"]
    if kind == "annotation":
        truth["cases"][0]["medicines"][0]["expected_fields"]["name"] = "Changed"
        path.write_text(json.dumps(truth), encoding="utf-8")
    elif kind == "policy":
        truth["policy"]["threshold"] = "changed"
        path.write_text(json.dumps(truth), encoding="utf-8")
    elif kind == "extra_file":
        (target / "unexpected.txt").write_text("Unexpected", encoding="utf-8")
    elif kind == "image":
        first_image.write_bytes(first_image.read_bytes() + b"changed")
    else:
        first_image.unlink()
    def forbidden(_):
        pytest.fail("Predictor ran before fixture integrity validation")
    with pytest.raises((ValueError, FileNotFoundError)):
        benchmark.evaluate(target, forbidden)


def test_unknown_or_repeated_cases_rejected(fixtures):
    directory, _ = fixtures
    for case_ids in (["printed_01"], ["scale_001", "scale_001"]):
        with pytest.raises(ValueError, match="selection"):
            benchmark.evaluate(directory, lambda _: [], case_ids)


def test_original_13_case_interface_remains_unchanged():
    truth = original.load_ground_truth()
    report = original.evaluate_cases(truth, original.mock_predictor(truth))
    assert report["case_count"] == 13
    assert report["field_accuracy"] == {"correct": 156, "total": 156, "accuracy": 1.0}
    assert report["policy"] == original.POLICY


def test_live_command_disabled(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        benchmark.main(["live", "--directory", str(tmp_path)])
    assert error.value.code == 2
    assert "disabled" in capsys.readouterr().err


def test_cli_verify_and_mock_subset(fixtures, capsys):
    directory, _ = fixtures
    benchmark.main(["verify", "--directory", str(directory)])
    summary = json.loads(capsys.readouterr().out)
    assert summary["cases"] == 150 and summary["medicines"] == 420
    benchmark.main(["mock", "--directory", str(directory), "--cases", "scale_015"])
    report = json.loads(capsys.readouterr().out)
    assert report["case_count"] == 1
    assert report["mode"] == "mock_only_NOT_measured_OCR_accuracy"


def test_import_is_lazy_and_has_no_sdk_or_training_dependency():
    root = Path(benchmark.__file__).parent
    code = "import sys; import printed_benchmark; assert 'reader' not in sys.modules; assert 'google.genai' not in sys.modules; assert 'torch' not in sys.modules"
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
