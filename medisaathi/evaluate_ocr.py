"""Offline word OCR evaluation, separate from prescription extraction.

Comparison normalization: NONE. Case, whitespace, punctuation and Unicode
code points are preserved. CER is micro-averaged: total Levenshtein edits /
total reference characters, and can exceed 1. No model or network is included.
Dataset files must remain outside the repository. Supplying a predictor is an
explicit caller decision; do not connect a cloud predictor without approval.
"""

import csv
import random
from pathlib import Path
from typing import Protocol


SAFE_ERROR_CATEGORIES = frozenset({
    "quota_or_rate_limit", "api_error", "network_error",
    "configuration_error", "image_validation_error", "unexpected_prediction_error",
})


def _error_category(exception: Exception) -> str:
    """Map explicit adapter exception types, never messages or arbitrary attributes.

    Import lazily so offline evaluators using other predictors need not load the
    Gemini adapter. Importing the adapter itself does not make network requests.
    """
    from gemini_word_ocr import (
        WordAPIError, WordConfigurationError, WordImageError,
        WordNetworkError, WordQuotaError,
    )

    # Specific API subclasses must be checked before their parent class.
    for error_type, category in (
        (WordQuotaError, "quota_or_rate_limit"),
        (WordNetworkError, "network_error"),
        (WordConfigurationError, "configuration_error"),
        (WordImageError, "image_validation_error"),
        (WordAPIError, "api_error"),
    ):
        if isinstance(exception, error_type):
            return category
    return "unexpected_prediction_error"


def _api_diagnostics(exception: Exception) -> tuple:
    """Copy validated scalars from known adapter errors, never SDK details."""
    from gemini_word_ocr import WordAPIError

    if not isinstance(exception, WordAPIError):
        return None, None
    code = getattr(exception, "http_status_code", None)
    stage = getattr(exception, "failure_stage", None)
    return (
        code if type(code) is int and 100 <= code <= 599 else None,
        stage if type(stage) is str and stage in
        ("api_request", "response_validation") else None,
    )


class EvaluationInputError(ValueError):
    """Dataset labels, paths or evaluation options are invalid."""


class WordPredictor(Protocol):
    """A callable receiving one image's bytes and returning its transcription."""

    def __call__(self, image_bytes: bytes) -> str:
        ...


def levenshtein_distance(reference: str, prediction: str) -> int:
    """Standard unit-cost character insertion/deletion/substitution distance.

    Dynamic programming retains only two rows, using O(min(n, m)) memory.
    Characters mean Python Unicode code points, not bytes or grapheme clusters.
    """
    if not isinstance(reference, str) or not isinstance(prediction, str):
        raise TypeError("Reference and prediction must be strings.")
    if len(reference) < len(prediction):
        reference, prediction = prediction, reference
    previous = list(range(len(prediction) + 1))
    for i, ref_char in enumerate(reference, 1):
        current = [i]
        for j, pred_char in enumerate(prediction, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (ref_char != pred_char)))
        previous = current
    return previous[-1]


def load_labels(dataset_path, split: str = "test") -> list[dict]:
    """Read only the selected supplied split; reject bad rows before inference.

    Empty references are invalid because CER needs reference characters.
    Whitespace-only references are invalid, but nonblank text is never stripped.
    Image existence is checked here; image decoding is the predictor's concern.
    """
    if split not in ("train", "test"):
        raise EvaluationInputError("split must be 'train' or 'test'.")
    root = Path(dataset_path)
    prefix = split.title()
    image_dir = (root / f"{prefix}_Set").resolve()
    labels = root / f"{prefix}_Label.csv"
    result, seen = [], set()
    try:
        with labels.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != ["Images", "Text"]:
                raise EvaluationInputError("CSV header must be Images,Text.")
            for line, row in enumerate(reader, 2):
                filename, reference = row.get("Images"), row.get("Text")
                if (None in row or not filename or filename != filename.strip()
                        or filename in (".", "..") or any(c in filename for c in '/\\:')
                        or not reference or not reference.strip()):
                    raise EvaluationInputError(f"Invalid label row {line}.")
                if filename in seen:
                    raise EvaluationInputError(f"Duplicate filename at row {line}.")
                image_path = (image_dir / filename).resolve()
                if image_path.parent != image_dir or not image_path.is_file():
                    raise EvaluationInputError(f"Missing or unsafe image at row {line}.")
                seen.add(filename)
                result.append({"filename": filename, "reference": reference,
                               "image_path": image_path})
    except (OSError, UnicodeError, csv.Error):
        raise EvaluationInputError("Cannot read the selected split's label CSV.") from None
    if not result:
        raise EvaluationInputError("The selected split has no label rows.")
    return result


def evaluate_ocr(dataset_path, predictor: WordPredictor, *, split="test",
                 sample_size=None, seed=42) -> dict:
    """Evaluate a fixed-seed subset without touching the dataset or writing files.

    None selects all rows; an explicit sample size must be between 1 and N.
    Subsets are selected from filename-sorted rows using a local Random instance.
    Failed predictions count as empty strings (all reference characters deleted),
    remain in metric denominators, and receive an error flag. Exception messages
    are deliberately omitted. A valid empty string is also scored as deletions.
    error_category contains only allowlisted diagnostics, or None on success.
    empty_prediction describes the stored string, including failure placeholders;
    pair it with error=None to identify a successful blank response. Whitespace
    alone is flagged as empty but is preserved for strict scoring. Supplementary
    case-insensitive accuracy applies casefold() only; strict metrics are unchanged.
    """
    if not callable(predictor):
        raise EvaluationInputError("predictor must be callable.")
    if type(seed) is not int:
        raise EvaluationInputError("seed must be an integer.")
    labels = sorted(load_labels(dataset_path, split), key=lambda row: row["filename"])
    if sample_size is not None:
        if type(sample_size) is not int or not 1 <= sample_size <= len(labels):
            raise EvaluationInputError("sample_size must be between 1 and the split size.")
        labels = sorted(random.Random(seed).sample(labels, sample_size),
                        key=lambda row: row["filename"])
    records = []
    for row in labels:
        error = None
        error_category = None
        http_status_code = failure_stage = None
        try:
            image = row["image_path"].read_bytes()
            if not image:
                raise OSError("Empty image")
        except OSError:
            prediction, error = "", "image_read_failed"
            error_category = "image_validation_error"
        else:
            try:
                prediction = predictor(image)
                if not isinstance(prediction, str):
                    prediction, error = "", "invalid_prediction_type"
                    error_category = "unexpected_prediction_error"
            except Exception as exc:
                prediction, error = "", "prediction_failed"
                error_category = _error_category(exc)
                http_status_code, failure_stage = _api_diagnostics(exc)
        reference = row["reference"]
        records.append({"filename": row["filename"], "reference": reference,
                        "prediction": prediction, "correct": prediction == reference,
                        "edit_distance": levenshtein_distance(reference, prediction),
                        "error": error, "error_category": error_category,
                        "http_status_code": http_status_code, "failure_stage": failure_stage,
                        "empty_prediction": not prediction.strip()})
    correct = sum(record["correct"] for record in records)
    edits = sum(record["edit_distance"] for record in records)
    characters = sum(len(record["reference"]) for record in records)
    return {"split": split, "seed": seed, "comparison_normalization": "none",
            "evaluated_count": len(records), "correct_count": correct,
            "error_count": sum(record["error"] is not None for record in records),
            "total_character_edits": edits, "total_reference_characters": characters,
            "exact_match_accuracy": correct / len(records),
            "case_insensitive_accuracy": sum(
                record["prediction"].casefold() == record["reference"].casefold()
                for record in records
            ) / len(records),
            "character_error_rate": edits / characters, "records": records}
