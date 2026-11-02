"""Deterministic 150-case printed benchmark preparation; no network/model imports.

CLI: generate --output NEW_DIRECTORY, verify --directory DIRECTORY,
mock --directory DIRECTORY [--cases scale_001 ...]. Live execution is disabled.
The separate 120/30 cohorts are template holdouts, not a training split: no
model is trained. All prescriptions are fictional and require confirmation.
"""

import argparse
import copy
import hashlib
import json
import random
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from PIL import __version__ as PILLOW_VERSION

from evaluate_printed_prescriptions import (
    BANNER, DEFAULT_FIXTURES, EXTRACTED_FIELDS, POLICY, SCORED_FIELDS,
    _valid_value, mock_predictor, score_validated_cases, sha256,
)


VERSION = "printed150-v1"
CASE_COUNT = 150
MEDICINE_COUNT = 420
SEED = 42
DEVELOPMENT = ("ruled_rows", "sectioned_blocks", "receipt", "form_panels")
HOLDOUT = ("staggered_cards", "landscape_bands")
FONT_FAMILIES = ("sans", "serif", "humanist", "mono", "book")
QUALITY_LEVELS = ("clean", "scan", "camera")
BACKGROUNDS = ("white", "cream", "blue", "gray", "ruled")
FREQUENCIES = ("OD", "BD", "TDS", "SOS", "1-0-1", "0-0-1", "1-1-1")
PAPERS = {"white": "#ffffff", "cream": "#fffbed", "blue": "#f0f7fc",
          "gray": "#f1f1f1", "ruled": "#fffef9"}


def _seed(seed):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed must be an integer between 0 and 2**32-1.")


def _case_seed(seed, number):
    return int.from_bytes(hashlib.sha256(f"{VERSION}:{seed}:{number}".encode()).digest()[:8], "big")


def _shuffled(values, seed):
    result = list(values)
    random.Random(seed).shuffle(result)
    return result


def _letters(number):
    return "".join(chr(65 + (number // divisor) % 26) for divisor in (676, 26, 1))


def _medicine(rng, serial):
    syllables = ("zu", "ve", "ki", "ro", "na", "fu", "mi", "po", "ta", "lo")
    name = "Fictional-" + "".join(rng.choice(syllables) for _ in range(3)).capitalize() + "-" + _letters(serial)
    form = rng.choice(("tablet", "capsule", "syrup", "drops", None))
    strength = rng.choice(("10 mg", "5mg", "0.5 mg", "250 mcg", "2 mg/mL", "5 mg/5 mL", None))
    frequency = rng.choice(FREQUENCIES + (None, None))
    duration_kind = rng.choice(("days", "days", "days", "weeks", "missing"))
    days = rng.choice((1, 3, 5, 7, 10)) if duration_kind == "days" else None
    duration_text = (f"{days} " + ("day" if days == 1 else "days")) if days else None
    if duration_kind == "weeks":
        duration_text = f"{rng.choice((1, 2, 3))} weeks"
    timing = rng.choice(("before food", "after food", "bedtime", None, None))
    salt = "Example-Ingredient-" + _letters(serial) if rng.randrange(4) == 0 else None
    return {
        "raw_text": "", "name": name, "salt": salt, "strength": strength,
        "form": form, "frequency_pattern": frequency, "duration_days": days, "timing": timing,
    }, duration_text, duration_kind


def _source_lines(record, duration_text, template, variation):
    labels = {"name": "Medicine", "form": "Form", "strength": "Strength",
              "frequency_pattern": "Pattern", "duration": "Duration", "timing": "Timing", "salt": "Ingredient"}
    order = ["name", "form", "strength", "frequency_pattern", "duration", "timing", "salt"]
    if variation == 2:
        order = ["name", "strength", "form", "timing", "frequency_pattern", "duration", "salt"]
    if template in HOLDOUT:
        order = ["name", "frequency_pattern", "duration", "form", "strength", "timing", "salt"]
    lines = []
    for key in order:
        value = duration_text if key == "duration" else record[key]
        if value is not None:
            label = labels[key].upper() if variation == 3 else labels[key]
            lines.append(f"{label}: {value}")
    if template == "ruled_rows":
        return ["; ".join(lines)]
    if template == "sectioned_blocks":
        return [lines[0]] + ["; ".join(lines[1:])]
    return lines


def definitions(seed=SEED):
    """Balanced independent factors; each medicine gets a fresh fictional name."""
    _seed(seed)
    templates = (_shuffled([t for t in DEVELOPMENT for _ in range(30)], seed + 1)
                 + _shuffled([t for t in HOLDOUT for _ in range(15)], seed + 2))
    fonts = _shuffled(list(FONT_FAMILIES) * 30, seed + 3)
    qualities = _shuffled(list(QUALITY_LEVELS) * 50, seed + 4)
    backgrounds = _shuffled(list(BACKGROUNDS) * 30, seed + 5)
    counts = iter(_shuffled(list(range(1, 6)) * 28, seed + 6))
    cases, serial = [], 0
    for number in range(1, CASE_COUNT + 1):
        case_seed = _case_seed(seed, number)
        rng = random.Random(case_seed)
        template, quality = templates[number - 1], qualities[number - 1]
        control = number % 15 == 0
        count = 0 if control else next(counts)
        variation = 1 + rng.randrange(3)
        medicines, blocks = [], []
        for _ in range(count):
            record, duration_text, duration_kind = _medicine(rng, serial)
            serial += 1
            lines = _source_lines(record, duration_text, template, variation)
            record["raw_text"] = "\n".join(lines)
            medicines.append({"expected_fields": record,
                              "review_required": any(v is None for v in record.values()),
                              "duration_source": duration_text, "duration_kind": duration_kind})
            blocks.append(lines)
        size = [1000, 2400] if template == "receipt" else [2200, 1600] if template == "landscape_bands" else [1600, 1900]
        if quality == "camera":
            angle, shear = rng.uniform(-1.7, 1.7), rng.uniform(-0.012, 0.012)
            perspective = [rng.uniform(-0.000004, 0.000004) for _ in range(2)]
        else:
            angle, shear, perspective = 0.0, 0.0, [0.0, 0.0]
        extension = ".png" if quality == "clean" else ".jpg"
        cases.append({
            "case_id": f"scale_{number:03d}", "image": f"scale_{number:03d}{extension}",
            "fictional": True, "patient_information": "none", "case_seed": case_seed,
            "cohort": "development" if number <= 120 else "template_holdout",
            "template": template, "variation": variation, "font_family": fonts[number - 1],
            "quality": quality, "background": backgrounds[number - 1], "size": size,
            "medicine_count": count, "source_blocks": blocks,
            "source_text": [r["expected_fields"]["raw_text"] for r in medicines] or ["No medicines listed."],
            "medicines": medicines,
            "generation": {"body_font_size": rng.choice((26, 28, 30)), "rotation_degrees": angle,
                           "shear": shear, "perspective": perspective,
                           "blur_radius": 0.0 if quality == "clean" else 0.3 if quality == "scan" else 0.55,
                           "downsample_scale": 1.0 if quality == "clean" else 0.9 if quality == "scan" else 0.8,
                           "contrast": 1.0 if quality == "clean" else 0.92,
                           "jpeg_quality": None if quality == "clean" else 84 if quality == "scan" else 68,
                           "noise_specks": 0 if quality == "clean" else 450},
        })
    assert serial == MEDICINE_COUNT
    return cases


def _fonts():
    choices = {
        "sans": ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        "serif": ("C:/Windows/Fonts/times.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        "humanist": ("C:/Windows/Fonts/calibri.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        "mono": ("C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        "book": ("C:/Windows/Fonts/georgia.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"),
        "header": ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    }
    paths = {}
    for family, options in choices.items():
        path = next((Path(p) for p in options if Path(p).is_file()), None)
        if path is None:
            raise ValueError(f"Missing readable font for {family}; no fonts will be downloaded.")
        paths[family] = path
    return paths


def _wrapped(draw, text, width, font):
    lines, line = [], ""
    for word in text.split(" "):
        if draw.textlength(word, font=font) > width:
            raise ValueError("Word exceeds rendering box; refuse clipped text.")
        trial = (line + " " + word).lstrip()
        if line and draw.textlength(trial, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def _block(draw, lines, box, font, color, rendered, medicine_index):
    x, y, right, bottom = box
    line_height = font.size + 9
    for source_line in lines:
        for line in _wrapped(draw, source_line, right - x, font):
            if y + line_height > bottom:
                raise ValueError("Source text exceeds rendering box; refuse clipped text.")
            bounds = draw.textbbox((x, y), line, font=font)
            if bounds[0] < x - 2 or bounds[2] > right + 2 or bounds[3] > bottom:
                raise ValueError("Glyph exceeds rendering box.")
            draw.text((x, y), line, font=font, fill=color)
            rendered.append({"medicine_index": medicine_index, "text": line,
                             "bounds": list(bounds), "box": list(box)})
            y += line_height
    return y


def render(case, destination, fonts=None):
    """Render one declared case. Never infer annotations from generated pixels."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Image exists; nothing overwritten.")
    fonts = fonts or _fonts()
    width, height = case["size"]
    paper = PAPERS[case["background"]]
    image = Image.new("RGB", (width, height), paper)
    draw = ImageDraw.Draw(image)
    rng = random.Random(case["case_seed"] + 71)
    if case["background"] == "ruled":
        for y in range(230, height - 120, 45):
            draw.line((85, y, width - 85, y), fill="#dce8f1")
    for _ in range(case["generation"]["noise_specks"]):
        x, y = rng.randrange(width), rng.randrange(height)
        draw.ellipse((x, y, x + 1, y + 1), fill="#d8d8d8")
    header = ImageFont.truetype(str(fonts["header"]), 27 if width == 1000 else 36)
    body = ImageFont.truetype(str(fonts[case["font_family"]]), case["generation"]["body_font_size"])
    small = ImageFont.truetype(str(fonts["sans"]), 22)
    rendered = []
    _block(draw, [BANNER], (90, 65, width - 90, 150), header, "#702000", rendered, None)
    _block(draw, [f"Synthetic typed fixture | {case['case_id']}", "Entirely invented text. No patient information."],
           (100, 145, width - 100, 230), small, "#333333", rendered, None)
    blocks = case["source_blocks"] or [["No medicines listed."]]
    count = len(blocks)
    top, bottom = 270, height - 170
    template = case["template"]
    if template == "staggered_cards":
        rows = (count + 1) // 2
        card_height = (bottom - top - 40) // rows
        for index, lines in enumerate(blocks):
            column, row = index % 2, index // 2
            left = 100 + column * ((width - 180) // 2)
            y = top + row * card_height + column * 26
            right = left + (width - 260) // 2
            draw.rounded_rectangle((left, y, right, y + card_height - 24), radius=16, outline="#8696a8", width=2)
            _block(draw, lines, (left + 18, y + 20, right - 18, y + card_height - 42), body,
                   "#111111", rendered, index if case["medicines"] else None)
    elif template == "landscape_bands":
        band_height = (bottom - top) // count
        for index, lines in enumerate(blocks):
            y = top + index * band_height
            draw.rectangle((95, y, width - 95, y + band_height - 15), outline="#8d9b9b", width=2)
            groups = (lines[:3], lines[3:5], lines[5:])
            column_width = (width - 240) // 3
            for column, group in enumerate(groups):
                x = 115 + column * column_width
                _block(draw, group, (x, y + 14, x + column_width - 25, y + band_height - 28),
                       body, "#111111", rendered, index if case["medicines"] else None)
    elif template == "form_panels":
        panel_height = (bottom - top) // count
        for index, lines in enumerate(blocks):
            y = top + index * panel_height
            draw.rectangle((95, y, width - 95, y + panel_height - 15), outline="#929292", width=2)
            middle = 1 + (len(lines) - 1 + 1) // 2
            _block(draw, lines[:middle], (115, y + 12, width // 2 - 20, y + panel_height - 28),
                   body, "#111111", rendered, index if case["medicines"] else None)
            _block(draw, lines[middle:], (width // 2 + 15, y + 12, width - 115, y + panel_height - 28),
                   body, "#111111", rendered, index if case["medicines"] else None)
    else:
        slot_height = (bottom - top) // count
        for index, lines in enumerate(blocks):
            y = top + index * slot_height
            left = 110 + (30 if template == "sectioned_blocks" and index % 2 else 0)
            if template == "ruled_rows":
                draw.line((100, y + slot_height - 25, width - 100, y + slot_height - 25), fill="#b0b0b0", width=2)
            _block(draw, lines, (left, y, width - 110, y + slot_height - 30), body,
                   "#111111", rendered, index if case["medicines"] else None)
    _block(draw, ["Every extracted field requires user confirmation."],
           (100, height - 115, width - 100, height - 50), small, "#333333", rendered, None)
    settings = case["generation"]
    if settings["rotation_degrees"]:
        image = image.rotate(settings["rotation_degrees"], resample=Image.Resampling.BICUBIC,
                             expand=False, fillcolor=paper)
    if case["quality"] == "camera":
        g, h = settings["perspective"]
        image = image.transform(image.size, Image.Transform.PERSPECTIVE,
                                (1, settings["shear"], -5, 0, 1, -5, g, h),
                                resample=Image.Resampling.BICUBIC, fillcolor=paper)
    scale = settings["downsample_scale"]
    if scale != 1:
        image = image.resize((round(width * scale), round(height * scale)), Image.Resampling.BICUBIC)
        image = image.resize((width, height), Image.Resampling.BICUBIC)
    if settings["blur_radius"]:
        image = image.filter(ImageFilter.GaussianBlur(settings["blur_radius"]))
    image = ImageEnhance.Contrast(image).enhance(settings["contrast"])
    with destination.open("xb") as stream:
        if destination.suffix == ".jpg":
            image.save(stream, format="JPEG", quality=settings["jpeg_quality"], subsampling=0, optimize=False)
        else:
            image.save(stream, format="PNG", compress_level=6, optimize=False)
    image.close()
    return rendered


def _json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def generate(output, seed=SEED):
    """Publish only a fully generated/validated new directory; refuse overwrite."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Benchmark destination exists; nothing overwritten.")
    cases, fonts = definitions(seed), _fonts()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=output.name + ".preparing-", dir=output.parent))
    try:
        for case in cases:
            path = temporary / case["image"]
            case["rendered_lines"] = render(case, path, fonts)
            case["image_sha256"] = sha256(path.read_bytes())
        original = DEFAULT_FIXTURES / "ground_truth.json"
        truth = {
            "schema_version": VERSION, "benchmark_id": VERSION, "master_seed": seed,
            "case_count": CASE_COUNT, "medicine_count": MEDICINE_COUNT,
            "policy": copy.deepcopy(POLICY), "policy_sha256": _digest(POLICY),
            "ground_truth_fields": list(EXTRACTED_FIELDS), "banner": BANNER,
            "cohorts": {"development": {"cases": 120, "templates": list(DEVELOPMENT)},
                        "template_holdout": {"cases": 30, "templates": list(HOLDOUT)}},
            "provenance": {
                "generator_version": VERSION, "generator_sha256": sha256(Path(__file__).read_bytes()),
                "scorer_sha256": sha256(Path(__file__).with_name("evaluate_printed_prescriptions.py").read_bytes()),
                "python_version": sys.version.split()[0], "pillow_version": PILLOW_VERSION,
                "fonts": {family: {"filename": path.name, "sha256": sha256(path.read_bytes())}
                          for family, path in fonts.items()},
                "randomness": "CPython random.Random; per-case SHA-256-derived seed; independently shuffled factors",
                "render_pipeline": ["paper and seeded specks", "warning and declared source blocks",
                                    "rotation (no canvas expansion)", "inverse perspective map for camera",
                                    "downsample then restore with bicubic", "Gaussian blur", "contrast", "encode"],
                "perspective_convention": "Pillow inverse coefficients (1, shear, -5, 0, 1, -5, g, h)",
                "encoding": {"png_compress_level": 6, "jpeg_subsampling": 0, "optimize": False},
                "source_reading_order": "within each medicine: left column top-to-bottom, then subsequent columns",
                "original13_ground_truth_sha256": sha256(original.read_bytes()),
                "original13_relationship": "Separate benchmark; no original images, names, or predictions reused.",
                "scope": "Synthetic typed images only; no training or handwritten OCR.",
                "confidence": "No measured confidence ground truth; mock confidence 0.95 is illustrative.",
                "limitations": ["Reproduction requires the recorded font bytes and rendering versions.",
                                "Procedural distortions approximate camera effects, not real-world camera diversity.",
                                "Human readability review is required before live evaluation.",
                                "Holdout templates remain separate; do not tune reader prompts using their results."],
            },
            "cases": cases,
        }
        _json(temporary / "ground_truth.json", truth)
        validate(temporary)
        if output.exists():
            raise FileExistsError("Benchmark destination appeared; nothing overwritten.")
        temporary.rename(output)
        return truth
    finally:
        if temporary.exists():
            # Delete only the exact temporary directory created above, under the checked parent.
            if temporary.parent.resolve() != output.parent or not temporary.name.startswith(output.name + ".preparing-"):
                raise RuntimeError("Unsafe temporary cleanup refused.")
            shutil.rmtree(temporary)


def validate(directory):
    """Validate recipe, exact labels, cohorts, complete inventory and image bytes."""
    directory = Path(directory)
    truth = json.loads((directory / "ground_truth.json").read_text(encoding="utf-8"))
    if (truth.get("schema_version") != VERSION or truth.get("benchmark_id") != VERSION
            or truth.get("policy") != POLICY or truth.get("policy_sha256") != _digest(POLICY)):
        raise ValueError("Unknown benchmark version or changed frozen scoring policy.")
    if (truth.get("case_count") != CASE_COUNT or truth.get("medicine_count") != MEDICINE_COUNT
            or truth.get("ground_truth_fields") != list(EXTRACTED_FIELDS) or truth.get("banner") != BANNER):
        raise ValueError("Changed benchmark contract.")
    expected_cases = definitions(truth.get("master_seed"))
    cases = truth.get("cases")
    if type(cases) is not list or len(cases) != CASE_COUNT:
        raise ValueError("Expected exactly 150 cases.")
    inventory = {"ground_truth.json"}
    hashes, names = set(), set()
    for actual, expected in zip(cases, expected_cases):
        # Includes every label, source line, missing field and generation parameter.
        if any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError("Case metadata/annotation differs from the deterministic source recipe.")
        filename = actual["image"]
        if filename in inventory or Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise ValueError("Unsafe or duplicate image filename.")
        inventory.add(filename)
        digest = actual.get("image_sha256")
        if type(digest) is not str or len(digest) != 64 or digest in hashes:
            raise ValueError("Missing or repeated image hash.")
        hashes.add(digest)
        path = directory / filename
        if sha256(path.read_bytes()) != digest:
            raise ValueError("Fixture image hash mismatch; evaluation refused.")
        with Image.open(path) as image:
            if image.format != ("PNG" if path.suffix == ".png" else "JPEG") or list(image.size) != actual["size"]:
                raise ValueError("Unexpected image encoding or dimensions.")
            image.load()
        for item in actual["medicines"]:
            record = item["expected_fields"]
            if set(record) != set(EXTRACTED_FIELDS) or not all(_valid_value(f, v) for f, v in record.items()):
                raise ValueError("Invalid exact-field annotation.")
            if record["name"] in names:
                raise ValueError("Medicine content reused across independent cases.")
            names.add(record["name"])
        if not actual.get("rendered_lines") or not any(line["text"] == BANNER for line in actual["rendered_lines"]):
            raise ValueError("Missing warning-banner rendering metadata.")
        rendered_by_index = {i: [] for i in range(len(actual["medicines"]))}
        for line in actual["rendered_lines"]:
            index = line.get("medicine_index")
            bounds, box = line["bounds"], line["box"]
            if not (0 <= bounds[0] <= bounds[2] <= actual["size"][0]
                    and 0 <= bounds[1] <= bounds[3] <= actual["size"][1]
                    and bounds[2] <= box[2] + 2 and bounds[3] <= box[3]):
                raise ValueError("Clipped source rendering metadata.")
            if index is not None:
                if type(index) is not int or index not in rendered_by_index:
                    raise ValueError("Invalid rendered medicine index.")
                rendered_by_index[index].append(line["text"])
        for i, item in enumerate(actual["medicines"]):
            # Physical wrapping may add line breaks; exact words/punctuation must survive.
            if " ".join(" ".join(rendered_by_index[i]).split()) != " ".join(item["expected_fields"]["raw_text"].split()):
                raise ValueError("Rendered source differs from annotation.")
    if {p.name for p in directory.iterdir()} != inventory:
        raise ValueError("Benchmark contents differ from explicit allowlist.")
    if len(names) != MEDICINE_COUNT:
        raise ValueError("Wrong total medicine count.")
    return truth


def evaluate(directory, predictor, case_ids=None):
    """Validate all fixtures before reusing the frozen scorer. No SDK imported."""
    truth = validate(directory)
    report = score_validated_cases(truth, predictor, directory, case_ids)
    report["benchmark_id"] = VERSION
    report["original13_results_included"] = False
    cohorts = {}
    included = {r["case_id"] for r in report["results"]}
    # Replay already returned records for cohort metrics, never invoke predictor twice.
    results = {c["case_id"]: c for c in report["results"]}
    ids_by_hash = {c["image_sha256"]: c["case_id"] for c in truth["cases"]}
    def replay(data):
        result = results[ids_by_hash[sha256(data)]]
        if result["error"] == "prediction_failed":
            raise RuntimeError("Saved failed prediction.")
        return copy.deepcopy(result["raw_output"])
    for cohort in ("development", "template_holdout"):
        ids = [c["case_id"] for c in truth["cases"] if c["cohort"] == cohort and c["case_id"] in included]
        cohorts[cohort] = score_validated_cases(truth, replay, directory, ids)
    report["cohort_reports"] = cohorts
    return report


def describe(truth):
    return {
        "benchmark_id": VERSION, "cases": len(truth["cases"]),
        "medicines": sum(len(c["medicines"]) for c in truth["cases"]),
        "negative_controls": sum(not c["medicines"] for c in truth["cases"]),
        "cohorts": dict(Counter(c["cohort"] for c in truth["cases"])),
        "templates": dict(Counter(c["template"] for c in truth["cases"])),
        "qualities": dict(Counter(c["quality"] for c in truth["cases"])),
        "formats": dict(Counter(Path(c["image"]).suffix for c in truth["cases"])),
        "non_null_scored_fields": sum(m["expected_fields"][f] is not None for c in truth["cases"]
                                      for m in c["medicines"] for f in SCORED_FIELDS),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generation = sub.add_parser("generate")
    generation.add_argument("--output", required=True, type=Path)
    generation.add_argument("--seed", default=SEED, type=int)
    for command in ("verify", "mock", "live"):
        child = sub.add_parser(command)
        child.add_argument("--directory", required=True, type=Path)
        if command != "verify":
            child.add_argument("--cases", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "live":
        parser.error("Live evaluation is disabled; obtain separate approval before implementation/execution.")
    if args.command == "generate":
        print(json.dumps(describe(generate(args.output, args.seed)), indent=2))
    elif args.command == "verify":
        print(json.dumps(describe(validate(args.directory)), indent=2))
    else:
        truth = validate(args.directory)
        report = evaluate(args.directory, mock_predictor(truth), args.cases)
        report["mode"] = "mock_only_NOT_measured_OCR_accuracy"
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
