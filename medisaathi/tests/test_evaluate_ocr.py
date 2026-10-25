"""Fictional labels and byte fixtures only; no OCR model or API is used."""

import csv
import random

import pytest


@pytest.mark.parametrize("code", [400, 403, 404, 429, 500, None])
def test_report_http_diagnostics(dataset, code):
    import json
    from gemini_word_ocr import WordAPIError, WordQuotaError

    def broken(image):
        cls = WordQuotaError if code == 429 else WordAPIError
        raise cls("private-body https://secret", http_status_code=code,
                  failure_stage="api_request")
    report = evaluate_ocr(dataset, broken)
    for row in report["records"]:
        assert row["http_status_code"] == code
        assert row["failure_stage"] == "api_request"
        assert row["error"] == "prediction_failed"
        assert row["error_category"] == ("quota_or_rate_limit" if code == 429 else "api_error")
    assert "private-body" not in json.dumps(report)
    assert "https://" not in json.dumps(report)


def test_report_response_validation_and_mutated_metadata(dataset):
    from gemini_word_ocr import WordAPIError

    def invalid(image):
        raise WordAPIError("private", failure_stage="response_validation")
    row = evaluate_ocr(dataset, invalid)["records"][0]
    assert row["failure_stage"] == "response_validation"
    assert row["http_status_code"] is None

    def mutated(image):
        error = WordAPIError("private")
        error.http_status_code = "https://secret"
        error.failure_stage = {"raw": "private"}
        raise error
    report = evaluate_ocr(dataset, mutated)
    assert all(r["http_status_code"] is None and r["failure_stage"] is None for r in report["records"])
    assert "private" not in str(report)


def test_success_and_legacy_errors_have_null_diagnostics(dataset):
    from gemini_word_ocr import WordAPIError

    for prediction in ("", "AB"):
        report = evaluate_ocr(dataset, lambda image: prediction)
        assert all(r["http_status_code"] is None and r["failure_stage"] is None for r in report["records"])
    def old(image):
        raise WordAPIError("safe")
    report = evaluate_ocr(dataset, old)
    assert all(r["http_status_code"] is None and r["failure_stage"] is None for r in report["records"])
    assert report["error_count"] == 3

from evaluate_ocr import EvaluationInputError, evaluate_ocr, levenshtein_distance, load_labels


def write_split(root, prefix, rows):
    directory = root / f"{prefix}_Set"
    directory.mkdir(exist_ok=True)
    with (root / f"{prefix}_Label.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Images", "Text"])
        writer.writerows(rows)
    for name, text in rows:
        if name and '/' not in name and '\\' not in name:
            (directory / name).write_bytes(text.encode("utf-8"))


@pytest.fixture
def dataset(tmp_path):
    # These are mock bytes, not medical images. Predictor simply decodes them.
    write_split(tmp_path, "Test", [("a.jpg", "AB"), ("b.jpg", "CDEF"), ("c.jpg", "Gh")])
    write_split(tmp_path, "Train", [("train.jpg", "TrainingOnly")])
    return tmp_path


@pytest.mark.parametrize("reference,prediction,distance", [
    ("", "", 0), ("abc", "", 3), ("", "abc", 3),
    ("kitten", "sitting", 3), ("abc", "axc", 1), ("ab", "ba", 2),
    ("दवा", "दवा", 0), ("A", "a", 1), ("AB", "A B", 1),
])
def test_distance(reference, prediction, distance):
    assert levenshtein_distance(reference, prediction) == distance
    assert levenshtein_distance(prediction, reference) == distance


def test_metrics(dataset):
    predictions = {b"AB": "AB", b"CDEF": "CDF", b"Gh": ""}
    report = evaluate_ocr(dataset, predictions.__getitem__)
    assert report["exact_match_accuracy"] == pytest.approx(1 / 3)
    assert report["character_error_rate"] == pytest.approx(3 / 8)
    assert report["total_character_edits"] == 3
    assert report["evaluated_count"] == 3
    assert report["error_count"] == 0
    assert report["records"][2]["prediction"] == ""
    assert report["records"][0]["correct"] is True


def test_splits_and_subset(dataset):
    before = random.getstate()
    first = evaluate_ocr(dataset, bytes.decode, sample_size=2, seed=15)
    second = evaluate_ocr(dataset, bytes.decode, sample_size=2, seed=15)
    assert first == second
    assert random.getstate() == before
    assert first["evaluated_count"] == 2
    assert all(row["filename"] != "train.jpg" for row in first["records"])
    train = evaluate_ocr(dataset, bytes.decode, split="train")
    assert train["records"][0]["reference"] == "TrainingOnly"


def test_no_normalization(tmp_path):
    write_split(tmp_path, "Test", [("a.jpg", " A-b ")])
    report = evaluate_ocr(tmp_path, lambda image: "a-b")
    assert report["records"][0]["reference"] == " A-b "
    assert report["exact_match_accuracy"] == 0
    assert report["comparison_normalization"] == "none"


@pytest.mark.parametrize("prediction", [None, 123, b"AB"])
def test_invalid_prediction_types(dataset, prediction):
    report = evaluate_ocr(dataset, lambda image: prediction)
    assert report["error_count"] == 3
    assert report["character_error_rate"] == 1
    assert report["exact_match_accuracy"] == 0


def test_predictor_exception(dataset):
    def broken(image):
        raise RuntimeError("private detail")
    report = evaluate_ocr(dataset, broken)
    assert report["error_count"] == 3
    assert "private detail" not in str(report)
    assert all(row["error"] == "prediction_failed" for row in report["records"])


def test_empty_image(dataset):
    (dataset / "Test_Set" / "a.jpg").write_bytes(b"")
    report = evaluate_ocr(dataset, bytes.decode)
    assert report["error_count"] == 1
    assert report["records"][0]["error"] == "image_read_failed"


def test_missing_image(dataset):
    (dataset / "Test_Set" / "a.jpg").unlink()
    with pytest.raises(EvaluationInputError, match="Missing"):
        load_labels(dataset)


@pytest.mark.parametrize("rows", [[], [("a.jpg", "")], [("a.jpg", "  ")],
                                    [("../a.jpg", "A")], [("a.jpg", "A"), ("a.jpg", "B")]])
def test_invalid_labels(tmp_path, rows):
    write_split(tmp_path, "Test", rows)
    with pytest.raises(EvaluationInputError):
        load_labels(tmp_path)


@pytest.mark.parametrize("content", ["Wrong,Header\na.jpg,A\n", "Images,Text\na.jpg\n",
                                      'Images,Text\n"unterminated', "Images,Text\na.jpg,A,extra\n"])
def test_malformed_csv(tmp_path, content):
    (tmp_path / "Test_Label.csv").write_text(content, encoding="utf-8")
    with pytest.raises(EvaluationInputError):
        load_labels(tmp_path)


@pytest.mark.parametrize("options", [{"split": "validation"}, {"sample_size": 0},
                                      {"sample_size": 4}, {"sample_size": True},
                                      {"seed": "42"}])
def test_invalid_options(dataset, options):
    with pytest.raises(EvaluationInputError):
        evaluate_ocr(dataset, bytes.decode, **options)


def test_missing_csv(tmp_path):
    with pytest.raises(EvaluationInputError, match="CSV"):
        load_labels(tmp_path)


def test_cer_can_exceed_one(dataset):
    report = evaluate_ocr(dataset, lambda image: "X" * 20)
    assert report["character_error_rate"] > 1


def test_non_callable_predictor(dataset):
    with pytest.raises(EvaluationInputError):
        evaluate_ocr(dataset, None)


@pytest.mark.parametrize("type_name,category", [
    ("WordQuotaError", "quota_or_rate_limit"),
    ("WordAPIError", "api_error"),
    ("WordNetworkError", "network_error"),
    ("WordConfigurationError", "configuration_error"),
    ("WordImageError", "image_validation_error"),
    ("RuntimeError", "unexpected_prediction_error"),
])
def test_safe_failure_categories(dataset, type_name, category):
    import json
    import gemini_word_ocr as word
    from evaluate_ocr import SAFE_ERROR_CATEGORIES

    error_type = RuntimeError if type_name == "RuntimeError" else getattr(word, type_name)
    def broken(image):
        exc = error_type("secret-key https://private.example Authorization: private-body")
        exc.error_category = "https://unsafe.example/secret"
        raise exc
    report = evaluate_ocr(dataset, broken)
    for row in report["records"]:
        assert row["error"] == "prediction_failed"
        assert row["error_category"] == category
        assert row["error_category"] in SAFE_ERROR_CATEGORIES
        assert row["prediction"] == "" and row["empty_prediction"] is True
    saved = json.dumps(report)
    for sensitive in ("secret-key", "https://", "Authorization", "private-body", "Traceback"):
        assert sensitive not in saved
    assert report["error_count"] == 3
    assert report["character_error_rate"] == 1


@pytest.mark.parametrize("prediction", ["", " \t\n"])
def test_successful_blanks_are_not_exceptions(dataset, prediction):
    report = evaluate_ocr(dataset, lambda image: prediction)
    assert report["error_count"] == 0
    for row in report["records"]:
        assert row["error"] is None and row["error_category"] is None
        assert row["empty_prediction"] is True
        assert row["prediction"] == prediction


def test_supplementary_casefold_keeps_strict_metrics(dataset):
    report = evaluate_ocr(dataset, lambda image: image.decode().swapcase())
    assert report["exact_match_accuracy"] == 0
    assert report["character_error_rate"] == 1
    assert report["case_insensitive_accuracy"] == 1
    assert report["comparison_normalization"] == "none"
    assert all(row["correct"] is False for row in report["records"])


def test_casefold_is_not_whitespace_or_punctuation_normalization(tmp_path):
    write_split(tmp_path, "Test", [("a.jpg", " A-b ")])
    report = evaluate_ocr(tmp_path, lambda image: "a b")
    assert report["case_insensitive_accuracy"] == 0
    assert report["records"][0]["reference"] == " A-b "


def test_unicode_casefold(tmp_path):
    write_split(tmp_path, "Test", [("a.jpg", "Stra\u00dfe")])
    report = evaluate_ocr(tmp_path, lambda image: "STRASSE")
    assert report["case_insensitive_accuracy"] == 1
    assert report["exact_match_accuracy"] == 0


def test_old_report_fields_and_other_error_values(dataset):
    report = evaluate_ocr(dataset, bytes.decode)
    old_report = {"split", "seed", "comparison_normalization", "evaluated_count",
                  "correct_count", "error_count", "total_character_edits",
                  "total_reference_characters", "exact_match_accuracy", "character_error_rate", "records"}
    assert old_report <= report.keys()
    assert report["exact_match_accuracy"] == 1 and report["character_error_rate"] == 0
    old_record = {"filename", "reference", "prediction", "correct", "edit_distance", "error"}
    assert all(old_record <= row.keys() for row in report["records"])
    assert all(row["error_category"] is None and not row["empty_prediction"] for row in report["records"])
    invalid = evaluate_ocr(dataset, lambda image: None)["records"][0]
    assert invalid["error"] == "invalid_prediction_type"
    assert invalid["error_category"] == "unexpected_prediction_error"
    (dataset / "Test_Set" / "a.jpg").write_bytes(b"")
    unreadable = evaluate_ocr(dataset, bytes.decode)["records"][0]
    assert unreadable["error"] == "image_read_failed"
    assert unreadable["error_category"] == "image_validation_error"
