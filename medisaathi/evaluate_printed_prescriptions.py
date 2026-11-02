"""Offline, fictional printed-prescription fixtures and extraction evaluation.

No reader/SDK is imported. `mock` uses known fixture records, not measured OCR.
`live` is a reserved, disabled command; a separately approved milestone is needed.
All extracted fields require human confirmation before downstream use.
"""

import argparse
import copy
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION


VERSION = "printed-eval-v1"
BANNER = "FICTIONAL DEMO — NOT FOR MEDICAL USE"
FIELDS = (
    "raw_text", "name", "salt", "strength", "form", "frequency_pattern",
    "duration_days", "timing", "confidence", "needs_review",
)
EXTRACTED_FIELDS = FIELDS[:8]
SCORED_FIELDS = ("name", "strength", "form", "frequency_pattern", "duration_days", "timing")
DEFAULT_FIXTURES = Path(__file__).parent / "sample_prescriptions" / "printed_eval"
POLICY = {
    "version": VERSION,
    "matching": "maximum-cardinality then minimum-total-normalized-Levenshtein",
    "alignment_text": "raw_text; whitespace collapsed for alignment ONLY; case-sensitive",
    "threshold": "distance / max(text lengths) <= 1/2; missing/blank raw_text has no edge",
    "tie_break": "reference source order, then canonical JSON prediction order; ties reported",
    "scoring": "exact value AND Python type; no case/whitespace/punctuation/spelling normalization",
    "field_denominator": "6 * (matched + missing + extra); failures count as missing",
    "non_null_denominator": "all non-null expected scored fields, including missing medicines",
    "unsupported_values": "matched extraction fields expected null but predicted non-null; extras separate",
    "review_flags": "expected incomplete records and returned incomplete/low-confidence records require true",
    "negative_control": "separate pass requires successful empty list; extras also penalize field scores",
    "confirmation": "mandatory for every record, independent of needs_review",
    "weeks": "duration_days=null for weeks; never convert",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _medicine(name, strength=None, form=None, frequency=None, days=None,
              timing=None, salt=None, weeks=None):
    """Declare fictional visible text first; annotate only those printed values."""
    parts = [value for value in (form, name, strength, frequency) if value is not None]
    if days is not None:
        parts.append(f"{days} days")
    if weeks is not None:
        parts.append(f"{weeks} weeks")
    if timing is not None:
        parts.append(timing)
    if salt is not None:
        parts.append(f"ingredient: {salt}")
    raw = "; ".join(parts)
    return {
        "raw_text": raw, "name": name, "salt": salt, "strength": strength,
        "form": form, "frequency_pattern": frequency,
        "duration_days": days, "timing": timing,
    }


def fixture_definitions():
    """Twelve cases (26 medicines) and one negative control, all invented."""
    m = _medicine
    definitions = [
        ("single_column", [m("Fictional-Alba", "10 mg", "tablet", "OD", 3,
                             "after food", "Example-Ingredient-A")]),
        ("numbered", [m("Fictional-Bero", "20 mg", "tablet", "BD", 5),
                      m("Fictional-Cavo", "5 mg", "capsule", "OD", 4),
                      m("Fictional-Demi", "2 mg/mL", "drops", "SOS", 2)]),
        ("tabular", [m("Fictional-Elo", "15 mg", "tablet", "TDS", 3, "before food"),
                     m("Fictional-Favi", "25 mg", "capsule", "BD", 6, "after food"),
                     m("Fictional-Garo", "8 mg/5 mL", "syrup", "OD", 4, "bedtime")]),
        ("two_column", [m("Fictional-Havi", "12 mg", "tablet", "1-0-1", 7),
                        m("Fictional-Ilo", "6 mg", "capsule", "0-0-1", 3)]),
        ("wrapped_line", [m("Fictional-Javo", "30 mg", "tablet", "BD", 5,
                            "after food", "Example-Ingredient-J"),
                          m("Fictional-Kemi", "4 mg/mL", "drops", "SOS", 2,
                            "bedtime")]),
        ("single_column", [m("Fictional-Loro", "10 mg", "tablet", "OD", 3),
                           m("Fictional-Mavi", "20 mg", "capsule", "BD", 4),
                           m("Fictional-Nelo", "5 mg/5 mL", "syrup", "TDS", 5),
                           m("Fictional-Oro", "1 mg/mL", "drops", "SOS", 2)]),
        ("numbered", [m("Fictional-Pavo", "7 mg", "tablet", "OD", 2),
                      m("Fictional-Qemi", "9 mg", "capsule", "BD", 3),
                      m("Fictional-Relo", "3 mg/5 mL", "syrup", "TDS", 4)]),
        ("single_column", [m("Fictional-Savi", "2 mg/mL", "drops", "SOS")]),
        ("numbered", [m("Fictional-Toro", form="tablet", frequency="BD", days=3),
                      m("Fictional-Umi", form="capsule", frequency="OD", days=4)]),
        ("two_column", [m("Fictional-Velo", "10 mg", "tablet"),
                        m("Fictional-Wavi", "5 mg/5 mL", "syrup", "BD")]),
        ("wrapped_line", [m("Fictional-Xoro", "11 mg", "tablet", "OD", 6,
                            "before food", "Example-Ingredient-X"),
                          m("Fictional-Yemi", "13 mg", "capsule", "BD", 3,
                            "after food")]),
        ("single_column", [m("Fictional-Zavi", "14 mg", "tablet", "OD", weeks=2)]),
        ("no_medicine", []),
    ]
    cases = []
    for index, (layout, medicines) in enumerate(definitions, 1):
        if layout == "tabular":
            for record in medicines:
                # Table cells have no printed separator between columns. Preserve
                # their actual visible punctuation in a row-wise transcription.
                record["raw_text"] = " ".join([
                    f"{record['form']}; {record['name']}; {record['strength']}",
                    record["frequency_pattern"], f"{record['duration_days']} days",
                    record["timing"],
                ])
        if layout == "wrapped_line":
            for record in medicines:
                record["raw_text"] = record["raw_text"].replace("; ", ";\n", 3)
        case_id = f"printed_{index:02d}"
        cases.append({
            "case_id": case_id, "image": case_id + (".jpg" if index % 3 == 0 else ".png"),
            "layout": layout, "fictional": True, "patient_information": "none",
            "source_text": [record["raw_text"] for record in medicines] or ["No medicines listed."],
            "medicines": [{"expected_fields": record,
                           "review_required": any(value is None for value in record.values())}
                          for record in medicines],
            "annotation_notes": [
                "Source text follows each medicine's reading order; visual line wrapping is not semantic.",
                "Names and ingredient placeholders are entirely fictional. All fields require confirmation.",
            ] + (["2 weeks is visible; duration_days intentionally null (reader does not convert)."]
                 if index == 12 else []),
        })
    return cases


def _font_paths():
    # Exact font bytes are recorded, rather than claiming cross-font identical pixels.
    for regular, bold in [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]:
        if Path(regular).is_file() and Path(bold).is_file():
            return Path(regular), Path(bold)
    raise ValueError("Readable TrueType fonts unavailable; specify an approved rendering environment.")


def _draw_wrapped(draw, text, x, y, width, font, line_height=45):
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            trial = (line + " " + word).lstrip()
            if draw.textlength(trial, font=font) > width and line:
                draw.text((x, y), line, font=font, fill="black")
                y += line_height
                line = word
            else:
                line = trial
        draw.text((x, y), line, font=font, fill="black")
        y += line_height
    return y


def _render(case, destination, fonts):
    regular, bold = fonts
    canvas = Image.new("RGB", (1800, 1500), "white")
    draw = ImageDraw.Draw(canvas)
    header = ImageFont.truetype(str(bold), 44)
    body = ImageFont.truetype(str(regular), 32)
    small = ImageFont.truetype(str(regular), 26)
    draw.rectangle((0, 0, 1800, 110), fill="#fff1cc")
    draw.text((45, 28), BANNER, font=header, fill="#702000")
    draw.text((50, 140), f"Typed extraction fixture | {case['case_id']} | {case['layout']}",
              font=body, fill="black")
    draw.text((50, 200), "Invented text for software testing. No patient information.",
              font=small, fill="black")
    records = [item["expected_fields"] for item in case["medicines"]]
    if case["layout"] == "tabular":
        widths = [650, 170, 220, 330, 270]
        headings = ["Medicine / form / strength", "Pattern", "Duration", "Timing", "Ingredient"]
        for row in range(len(records) + 1):
            x, y = 50, 300 + row * 150
            if row == 0:
                cells = headings
            else:
                r = records[row - 1]
                cells = [f"{r['form']}; {r['name']}; {r['strength']}",
                         r["frequency_pattern"], f"{r['duration_days']} days",
                         r["timing"], r["salt"] or ""]
            for text, width in zip(cells, widths):
                draw.rectangle((x, y, x + width, y + 150), outline="#555555", width=2)
                _draw_wrapped(draw, text or "", x + 12, y + 18, width - 24, small, 38)
                x += width
    elif case["layout"] == "two_column":
        for index, record in enumerate(records):
            x = 50 + index * 870
            draw.rectangle((x, 290, x + 830, 1000), outline="#777777", width=2)
            _draw_wrapped(draw, record["raw_text"], x + 20, 325, 790, body)
    else:
        y = 300
        for index, text in enumerate(case["source_text"], 1):
            if case["layout"] == "numbered":
                text = f"{index}. " + text
            y = _draw_wrapped(draw, text, 60, y, 1680, body) + 65
        if y > 1350:
            raise ValueError("Fixture text exceeds page; rendering refused.")
    draw.text((50, 1410), "Every extracted field must be confirmed by the user.", font=small, fill="black")
    if destination.suffix == ".jpg":
        canvas.save(destination, format="JPEG", quality=95, subsampling=0, optimize=False)
    else:
        canvas.save(destination, format="PNG", compress_level=9, optimize=False)
    canvas.close()


def generate_fixtures(directory):
    """Create a NEW fixture directory; refuse every existing destination."""
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError("Fixture destination exists; nothing overwritten.")
    fonts = _font_paths()
    cases = fixture_definitions()
    directory.mkdir(parents=True, exist_ok=False)
    for case in cases:
        image_path = directory / case["image"]
        _render(case, image_path, fonts)
        case["image_sha256"] = sha256(image_path.read_bytes())
    truth = {
        "schema_version": VERSION, "policy": POLICY,
        "rendering": {"pillow_version": PILLOW_VERSION, "size": [1800, 1500],
                      "fonts": [{"filename": p.name, "sha256": sha256(p.read_bytes())} for p in fonts],
                      "banner": BANNER, "randomness": "none"},
        "ground_truth_fields": list(EXTRACTED_FIELDS),
        "confidence": "No ground-truth probability; mock 0.95 is illustrative only.",
        "cases": cases,
    }
    (directory / "ground_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return truth


def _valid_value(field, value):
    if field == "needs_review":
        return type(value) is bool
    if value is None:
        return True
    if field == "confidence":
        return type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)
    if field == "duration_days":
        return type(value) is int and value > 0
    if field == "form":
        return value in ("tablet", "capsule", "syrup", "drops") and type(value) is str
    return type(value) is str and bool(value.strip())


def contract_valid(record):
    return (type(record) is dict and set(record) == set(FIELDS)
            and all(_valid_value(field, record[field]) for field in FIELDS))


def load_ground_truth(directory=DEFAULT_FIXTURES):
    """Validate the version, annotation structure, file inventory, and image hashes."""
    directory = Path(directory)
    truth = json.loads((directory / "ground_truth.json").read_text(encoding="utf-8"))
    if truth.get("schema_version") != VERSION or truth.get("policy") != POLICY:
        raise ValueError("Unrecognized or changed evaluation policy.")
    cases = truth.get("cases", [])
    if len(cases) != 13 or len({c["case_id"] for c in cases}) != 13:
        raise ValueError("Expected 13 uniquely identified cases.")
    if len({c["image"] for c in cases}) != 13:
        raise ValueError("Expected 13 unique fixture images.")
    if sum(not c["medicines"] for c in cases) != 1:
        raise ValueError("Expected exactly one no-medicine control.")
    allowed = {"ground_truth.json"} | {c["image"] for c in cases}
    if {p.name for p in directory.iterdir()} != allowed:
        raise ValueError("Fixture inventory differs from the explicit allowlist.")
    for case in cases:
        filename = case["image"]
        if (Path(filename).name != filename or "/" in filename or "\\" in filename
                or Path(filename).suffix not in (".png", ".jpg")):
            raise ValueError("Unsafe or unsupported fixture filename.")
        if case.get("fictional") is not True or case.get("patient_information") != "none":
            raise ValueError("Only declared fictional fixtures are permitted.")
        if len(case["medicines"]) > 8:
            raise ValueError("Alignment supports at most eight reference medicines per case.")
        for item in case["medicines"]:
            record = item["expected_fields"]
            if set(record) != set(EXTRACTED_FIELDS) or not all(
                _valid_value(field, value) for field, value in record.items()
            ):
                raise ValueError("Invalid ground-truth annotation.")
            if item.get("review_required") is not any(value is None for value in record.values()):
                raise ValueError("Inconsistent ground-truth review requirement.")
        if case["source_text"] != ([m["expected_fields"]["raw_text"] for m in case["medicines"]]
                                   or ["No medicines listed."]):
            raise ValueError("Source text and annotation disagree.")
        image_path = directory / filename
        if sha256(image_path.read_bytes()) != case["image_sha256"]:
            raise ValueError("Fixture-image hash mismatch; evaluation refused.")
        with Image.open(image_path) as image:
            if image.format not in ("PNG", "JPEG"):
                raise ValueError("Unsupported fixture encoding.")
            image.load()
    return truth


def edit_distance(left, right):
    """Standard character-level Levenshtein distance, unit edit costs."""
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        following = [i]
        for j, b in enumerate(right, 1):
            following.append(min(row[j] + 1, following[-1] + 1, row[j - 1] + (a != b)))
        row = following
    return row[-1]


def _alignment_text(record):
    raw = record.get("raw_text") if type(record) is dict else None
    return " ".join(raw.split()) if type(raw) is str else ""


def match_medicines(expected, predicted):
    """Globally optimal bounded-reference matching; no greedy/order-based scoring.

    Dynamic programming takes O(P * G * 2**G) for G <= 8 references.
    Exact rational costs avoid floating-point tie-breaking inconsistencies.
    """
    if len(expected) > 8:
        raise ValueError("Too many reference medicines for frozen alignment method.")
    ordered = sorted(enumerate(predicted), key=lambda pair: (
        json.dumps(pair[1], sort_keys=True, ensure_ascii=False, allow_nan=False), pair[0]))
    # mask -> (cost, chosen (reference, sorted prediction) pairs, equal-best count)
    states = {0: (Fraction(0), (), 1)}
    for j, (_, prediction) in enumerate(ordered):
        next_states = dict(states)
        right = _alignment_text(prediction)
        # Cache each text-pair distance once, preserving the frozen costs/ties.
        costs = []
        for reference in expected:
            left = _alignment_text(reference)
            costs.append(Fraction(edit_distance(left, right), max(len(left), len(right)))
                         if left and right else None)
        for mask, (cost, pairs, ways) in states.items():
            for i, reference in enumerate(expected):
                if mask & (1 << i):
                    continue
                distance = costs[i]
                if distance is None or distance > Fraction(1, 2):
                    continue
                target = mask | (1 << i)
                candidate = (cost + distance, tuple(sorted(pairs + ((i, j),))), ways)
                old = next_states.get(target)
                if old is None or candidate[0] < old[0]:
                    next_states[target] = candidate
                elif candidate[0] == old[0]:
                    next_states[target] = (old[0], min(old[1], candidate[1]), min(2, old[2] + ways))
        states = next_states
    best_count = max(mask.bit_count() for mask in states)
    finalists = [value for mask, value in states.items() if mask.bit_count() == best_count]
    best_cost = min(value[0] for value in finalists)
    finalists = [v for v in finalists if v[0] == best_cost]
    chosen = min(finalists, key=lambda value: value[1])
    return {
        "pairs": [(i, ordered[j][0]) for i, j in chosen[1]],
        "ambiguous": sum(value[2] for value in finalists) > 1,
        "distance": str(best_cost),
    }


def _exact(expected, predicted):
    return type(expected) is type(predicted) and expected == predicted


def _predicted_review_required(record):
    """Mirror reader uncertainty rules without modifying its returned values."""
    if type(record) is not dict:
        return True
    confidence = record.get("confidence")
    return (any(record.get(f) is None for f in FIELDS if f != "needs_review")
            or not _valid_value("confidence", confidence)
            or confidence is None or confidence < 0.8)


def _ratio(correct, total):
    return {"correct": correct, "total": total, "accuracy": correct / total if total else None}


def evaluate_cases(truth, predictor, directory=DEFAULT_FIXTURES, case_ids=None):
    """Evaluate a bytes -> list[dict] callback; CLI supplies only an offline mock.

    A caller may inject a fake or, in a separately approved future workflow, a
    reader. This function itself imports no SDK and reads no credentials.
    JSON-compatible returned records are preserved verbatim, without repair.
    Exception messages are never retained. No scheduling/pricing is evaluated.
    """
    verified = load_ground_truth(directory)  # Includes every hash BEFORE any callback.
    if verified != truth:
        raise ValueError("In-memory ground truth differs from validated fixtures.")
    return score_validated_cases(truth, predictor, directory, case_ids)


def score_validated_cases(truth, predictor, directory, case_ids=None):
    """Shared frozen scoring; callers MUST validate their own fixture manifest first.

    The original evaluate_cases() still validates the original 13-case format.
    Other benchmark versions can validate a different inventory, then reuse
    this exact scoring body without changing denominators or medical values.
    """
    all_ids = {c["case_id"] for c in truth["cases"]}
    if case_ids is not None and (len(set(case_ids)) != len(case_ids) or not set(case_ids) <= all_ids):
        raise ValueError("Unknown or repeated case selection.")
    cases = [c for c in truth["cases"] if case_ids is None or c["case_id"] in case_ids]
    field_correct = dict.fromkeys(SCORED_FIELDS, 0)
    slots = matched = missing = extra = known_correct = known_total = records_correct = 0
    valid_records = returned_records = valid_cases = request_failures = unsupported = 0
    review_correct = review_total = negative_correct = negative_total = 0
    case_results = []
    for case in cases:
        expected = [m["expected_fields"] for m in case["medicines"]]
        error, raw_output, preserved = None, None, True
        try:
            raw_output = predictor((Path(directory) / case["image"]).read_bytes())
        except Exception:
            error = "prediction_failed"
        if error is None:
            try:
                # Verifies that preservation/reporting will not silently coerce types or NaN.
                encoded = json.dumps(raw_output, ensure_ascii=False, allow_nan=False)
                if json.loads(encoded) != raw_output:
                    error, raw_output, preserved = "invalid_output", None, False
                elif type(raw_output) is not list:
                    error = "invalid_output"
            except (TypeError, ValueError, OverflowError):
                error, raw_output, preserved = "invalid_output", None, False
        predictions = raw_output if error is None else []
        alignment = match_medicines(expected, predictions)
        k = len(alignment["pairs"])
        n_missing, n_extra = len(expected) - k, len(predictions) - k
        case_slots = k + n_missing + n_extra
        slots += case_slots
        matched += k
        missing += n_missing
        extra += n_extra
        request_failures += error is not None
        returned_records += len(predictions)
        valid = [contract_valid(p) for p in predictions]
        valid_records += sum(valid)
        case_contract = error is None and all(valid)
        valid_cases += case_contract
        known_total += sum(r[f] is not None for r in expected for f in SCORED_FIELDS)
        review_total += sum(item["review_required"] for item in case["medicines"])
        details = []
        for i, j in alignment["pairs"]:
            reference, prediction = expected[i], predictions[j]
            scores = {f: f in prediction and _valid_value(f, prediction[f])
                      and _exact(reference[f], prediction[f]) for f in SCORED_FIELDS}
            for field, correct in scores.items():
                field_correct[field] += correct
                known_correct += correct and reference[field] is not None
            records_correct += all(scores.values())
            unsupported += sum(reference[f] is None and prediction.get(f) is not None
                               for f in EXTRACTED_FIELDS)
            required = case["medicines"][i]["review_required"]
            if not required and _predicted_review_required(prediction):
                required = True
                review_total += 1
            review_correct += required and prediction.get("needs_review") is True
            details.append({"expected_index": i, "prediction_index": j, "field_correct": scores})
        matched_predictions = {j for _, j in alignment["pairs"]}
        for j, prediction in enumerate(predictions):
            if j not in matched_predictions and _predicted_review_required(prediction):
                review_total += 1
                review_correct += type(prediction) is dict and prediction.get("needs_review") is True
        if not expected:
            negative_total += 1
            negative_correct += error is None and len(predictions) == 0
        case_results.append({
            "case_id": case["case_id"], "raw_output": copy.deepcopy(raw_output),
            "raw_output_preserved": preserved, "error": error,
            "matched": k, "missing": n_missing, "extra": n_extra,
            "alignment": alignment, "field_results": details, "contract_valid": case_contract,
        })
    return {
        "evaluation_version": VERSION, "policy": copy.deepcopy(POLICY),
        "ground_truth_sha256": sha256((Path(directory) / "ground_truth.json").read_bytes()),
        "policy_sha256": sha256(json.dumps(POLICY, sort_keys=True).encode("utf-8")),
        "case_count": len(cases), "request_failures": request_failures,
        "medicine_detection": {"matched": matched, "missing": missing, "extra": extra,
                               "precision": matched / (matched + extra) if matched + extra else None,
                               "recall": matched / (matched + missing) if matched + missing else None},
        "field_scores": {f: _ratio(v, slots) for f, v in field_correct.items()},
        "field_accuracy": _ratio(sum(field_correct.values()), slots * 6),
        "non_null_field_accuracy": _ratio(known_correct, known_total),
        "six_field_record_accuracy": _ratio(records_correct, slots),
        "review_flag_compliance": _ratio(review_correct, review_total),
        "ten_field_contract_validity": {"records": _ratio(valid_records, returned_records),
                                        "cases": _ratio(valid_cases, len(cases))},
        "unsupported_value_errors": unsupported,
        "negative_control": _ratio(negative_correct, negative_total),
        "ambiguous_alignment_cases": [c["case_id"] for c in case_results if c["alignment"]["ambiguous"]],
        "results": case_results,
        "confirmation_required": True,
        "scope": "extraction only; excludes scheduling, dates, quantities, prices, reminders",
    }


def mock_predictor(truth):
    """Perfect simulated extraction, not an OCR accuracy measurement."""
    outputs = {case["image_sha256"]: [dict(item["expected_fields"], confidence=0.95,
                                          needs_review=item["review_required"])
                                     for item in case["medicines"]] for case in truth["cases"]}
    return lambda image_bytes: copy.deepcopy(outputs[sha256(image_bytes)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "verify", "mock", "live"))
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "live":
        parser.error("Live evaluation is DISABLED in Milestone 6B; separate implementation approval required.")
    if args.command == "generate":
        truth = generate_fixtures(args.fixtures)
        print(json.dumps({"created_cases": len(truth["cases"])}))
    elif args.command == "verify":
        truth = load_ground_truth(args.fixtures)
        print(json.dumps({"verified_images": len(truth["cases"]),
                          "medicines": sum(len(c["medicines"]) for c in truth["cases"])}))
    else:
        truth = load_ground_truth(args.fixtures)
        report = evaluate_cases(truth, mock_predictor(truth), args.fixtures, args.cases)
        report["mode"] = "mock_only_NOT_measured_OCR_accuracy"
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
