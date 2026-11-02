"""Training-only TrOCR preparation and gated baseline execution.

prepare writes provisional artifacts; freeze applies explicitly approved reviews.
run requires separately approved frozen manifests; importing never loads torch.
Difference hashes find review candidates, not evidence of image duplication.
"""

import argparse
import csv
import hashlib
import json
import io
import os
import random
import struct
import sys
import time
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path

from PIL import Image

from evaluate_ocr import levenshtein_distance, load_labels

MODEL = "microsoft/trocr-small-handwritten"
REVISION = "b4648cfa171985a6745f37ddd637e98c0da958ac"
DECODING = {"max_new_tokens": 32, "num_beams": 1, "do_sample": False}
VERSION = 1
MAX_CANDIDATE_CHECKS = 2_000_000
FREEZE_ALGORITHM = "review-union-find-whole-group-greedy80-v1"
REVIEW_NOTE = "User-confirmed matching handwriting strokes, spacing, and visual structure."


def _read_csv_bytes(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    rows = list(reader)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("Invalid CSV columns.")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Malformed CSV row.")
    return reader.fieldnames, rows


def _approved_review(candidate_bytes, review_bytes, records, expected_pairs):
    """Compare every review column shared with candidates; preserve extra columns."""
    candidate_fields, candidates = _read_csv_bytes(candidate_bytes)
    fields, reviews = _read_csv_bytes(review_bytes)
    required = {"pair_number", "filename_a", "filename_b", "reference_a", "reference_b",
                "hamming_distance", "crosses_provisional_split", "partition_a", "partition_b",
                "decision", "notes"}
    if not required <= set(fields) or len(candidates) != expected_pairs or len(reviews) != expected_pairs:
        raise ValueError("Review count or columns do not match approved candidates.")
    lookup = {r["filename"]: r for r in records}
    approved, seen, candidate_seen = [], set(), set()
    expected = {}
    for number, pair in enumerate(candidates, 1):
        key = (pair["filename_a"], pair["filename_b"])
        unordered = tuple(sorted(key))
        if unordered in candidate_seen or key[0] == key[1]:
            raise ValueError("Repeated candidate pair.")
        candidate_seen.add(unordered)
        a, b = (lookup[name] for name in key)
        if (pair["reference_a"] != a["reference"] or pair["reference_b"] != b["reference"]
                or pair["crosses_provisional_split"] != str(a["partition"] != b["partition"])
                or int(pair["hamming_distance"]) != (int(a["dhash64"], 16) ^ int(b["dhash64"], 16)).bit_count()):
            raise ValueError("Candidate metadata does not match preparation.")
        expected[key] = (number, pair)
    for row in reviews:
        key = (row["filename_a"], row["filename_b"])
        if key not in expected or key in seen:
            raise ValueError("Missing, extra or repeated review pair.")
        seen.add(key)
        number, pair = expected[key]
        if row["pair_number"] != str(number):
            raise ValueError("Review pair number mismatch.")
        for field in set(candidate_fields) & set(fields):
            if row[field] != pair[field]:
                raise ValueError("Review metadata mismatch.")
        for side in ("a", "b"):
            if row[f"partition_{side}"] != lookup[row[f"filename_{side}"]]["partition"]:
                raise ValueError("Review partition mismatch.")
        if row["decision"] not in ("", "confirmed_duplicate") or row["notes"] not in ("", REVIEW_NOTE):
            raise ValueError("Nonblank review decision or note conflicts; no files changed.")
        updated = dict(row, decision="confirmed_duplicate", notes=REVIEW_NOTE)
        approved.append(updated)
    approved.sort(key=lambda row: int(row["pair_number"]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(approved)
    return approved, stream.getvalue().encode("utf-8")


def reviewed_groups(records, reviews):
    """Union exact and visually confirmed edges, including transitive chains."""
    parent = {r["filename"]: r["filename"] for r in records}
    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name
    edges = [(g[0], name) for g in exact_groups(records) for name in g[1:]]
    edges += [(r["filename_a"], r["filename_b"]) for r in reviews]
    for a, b in edges:
        parent[find(b)] = find(a)
    groups = defaultdict(list)
    for name in sorted(parent):
        groups[find(name)].append(name)
    return sorted(groups.values(), key=lambda group: group[0])


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _commit_freeze(output, split_bytes, baseline_bytes, review_bytes):
    """Stage/fsync all bytes, publish exclusively under a lock, rollback on failure.

    Multiple paths cannot be atomically renamed together. The run command refuses
    a freeze lock. A process/power crash leaves the lock for manual recovery;
    ordinary failures remove published files. No existing final file is replaced.
    """
    lock = output / ".freeze.lock"
    targets = [output / "split_manifest.json", output / "baseline100_manifest.json"]
    staged, published = [], []
    with lock.open("x", encoding="utf-8") as stream:
        stream.write("Freeze in progress. Do not run baseline; inspect before recovering a stale lock.\n")
    try:
        if any(path.exists() for path in targets):
            raise FileExistsError("Finalized manifests already exist.")
        for data in (split_bytes, baseline_bytes, review_bytes):
            with tempfile.NamedTemporaryFile(dir=output, prefix=".freeze-", suffix=".tmp", delete=False) as stream:
                staged.append(Path(stream.name))
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        for temporary, target in zip(staged, targets):
            # Same-volume hard link is an exclusive create, never an overwrite.
            os.link(temporary, target)
            published.append(target)
        os.replace(staged[2], output / "near_duplicate_review.csv")
    except BaseException:
        for path in reversed(published):
            path.unlink()
        raise
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
        lock.unlink()


def freeze(output, expected_pairs=22):
    """Apply the explicitly approved all-confirmed review and finalize seed 42."""
    output = Path(output).resolve()
    repo = Path(__file__).resolve().parents[1]
    if output == repo or repo in output.parents:
        raise ValueError("Final manifests must remain outside Git.")
    if any((output / name).exists() for name in ("split_manifest.json", "baseline100_manifest.json", ".freeze.lock")):
        raise FileExistsError("Finalized manifests or freeze lock already exist.")
    provisional_bytes = (output / "provisional_split_manifest.json").read_bytes()
    provisional = json.loads(provisional_bytes)
    if (provisional.get("status") != "provisional" or provisional.get("source_split") != "train"
            or provisional.get("seed") != 42 or provisional.get("schema_version") != VERSION):
        raise ValueError("Unexpected preparation metadata.")
    root = Path(provisional["dataset_path"]).resolve()
    if output == root or root in output.parents:
        raise ValueError("Do not write into the source dataset.")
    csv_bytes = (root / "Train_Label.csv").read_bytes()
    if sha256(csv_bytes) != provisional["label_csv_sha256"]:
        raise ValueError("Training CSV hash changed.")
    records = sorted(provisional["records"], key=lambda r: r["filename"])
    source = sorted(load_labels(root, "train"), key=lambda r: r["filename"])
    if [(r["filename"], r["reference"]) for r in records] != [(r["filename"], r["reference"]) for r in source]:
        raise ValueError("Source coverage or reference labels changed.")
    for row, original in zip(records, source):
        if image_fingerprints(original["image_path"]) != (row["file_sha256"], row["rgb_sha256"], row["dhash64"]):
            raise ValueError("Source image hashes changed.")
    candidate_bytes = (output / "near_duplicate_candidates.csv").read_bytes()
    review_source = (output / "near_duplicate_review.csv").read_bytes()
    reviews, review_bytes = _approved_review(candidate_bytes, review_source, records, expected_pairs)
    groups = reviewed_groups(records, reviews)
    shuffled = list(groups)
    random.Random(42).shuffle(shuffled)
    target, count, validation = round(len(records) * .2), 0, set()
    for group in shuffled:
        if abs(count + len(group) - target) < abs(count - target):
            validation.update(group)
            count += len(group)
    group_ids = {name: group[0] for group in groups for name in group}
    records = [dict(row, group_id=group_ids[row["filename"]],
                    partition="validation" if row["filename"] in validation else "train") for row in records]
    lookup = {r["filename"]: r for r in records}
    if len(lookup) != len(source) or any(lookup[r["filename_a"]]["partition"] != lookup[r["filename_b"]]["partition"] for r in reviews):
        raise ValueError("Coverage or confirmed-duplicate leakage failure.")
    duplicate_groups = [group for group in groups if len(group) > 1]
    conflicts = [group for group in duplicate_groups if len({lookup[n]["reference"] for n in group}) > 1]
    checks = {"source_coverage_verified": True, "source_hashes_verified": True,
              "cross_partition_duplicate_groups": 0, "review_pair_count": len(reviews)}
    split = {**provisional, "status": "frozen", "review_complete": True,
             "grouping_algorithm_version": FREEZE_ALGORITHM, "records": records,
             "train_count": len(records)-count, "validation_count": count,
             "group_count": len(groups), "duplicate_group_count": len(duplicate_groups),
             "duplicate_images_involved": sum(map(len, duplicate_groups)),
             "duplicate_groups": duplicate_groups, "conflicting_reference_groups": conflicts,
             "validation_checks": checks, "writer_independence": "unknown",
             "review_provenance": "User approved pairs 01-22 as confirmed_duplicate after visual review.",
             "source_hashes": {"provisional_manifest": sha256(provisional_bytes),
                               "candidate_csv": sha256(candidate_bytes),
                               "review_before": sha256(review_source), "review_approved": sha256(review_bytes)}}
    validate_manifest(split)
    selected = sorted(random.Random(42).sample(sorted(
        [r for r in records if r["partition"] == "validation"], key=lambda r: r["filename"]), 100),
        key=lambda r: r["filename"])
    split_bytes = _json_bytes(split)
    baseline = {"schema_version": VERSION, "status": "frozen", "source_split": "train",
                "seed": 42, "model": MODEL, "revision": REVISION, "decoding": DECODING,
                "split_manifest_sha256": sha256(split_bytes), "selection_algorithm": "sorted validation; Random(42).sample(100); sort filenames",
                "filenames": [r["filename"] for r in selected], "records": selected,
                "validation_checks": checks, "grouping_algorithm_version": FREEZE_ALGORITHM}
    if len(set(baseline["filenames"])) != 100:
        raise ValueError("Baseline selection must contain 100 unique images.")
    # Detect edits made during the preflight before entering the commit phase.
    if (output / "near_duplicate_review.csv").read_bytes() != review_source:
        raise ValueError("Review changed during preflight.")
    _commit_freeze(output, split_bytes, _json_bytes(baseline), review_bytes)
    return {key: split[key] for key in ("train_count", "validation_count", "group_count",
            "duplicate_group_count", "duplicate_images_involved", "validation_checks") } | {
                "baseline_count": 100, "conflicting_reference_group_count": len(conflicts)}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def image_fingerprints(path):
    """Hash bytes and dimension-prefixed decoded RGB; also compute dHash64."""
    data = path.read_bytes()
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as source:
            source.load()
            rgb = source.convert("RGB")
        try:
            pixels = sha256(struct.pack(">II", *rgb.size) + rgb.tobytes())
            small = rgb.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            values = small.tobytes()
            small.close()
            dhash = 0
            for y in range(8):
                for x in range(8):
                    dhash = (dhash << 1) | (values[y * 9 + x] > values[y * 9 + x + 1])
        finally:
            rgb.close()
    return sha256(data), pixels, f"{dhash:016x}"


def exact_groups(records):
    """Union records sharing byte OR RGB hashes, including transitive links."""
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for field in ("file_sha256", "rgb_sha256"):
        seen = {}
        for i, row in enumerate(records):
            value = row[field]
            if value in seen:
                parent[find(i)] = find(seen[value])
            else:
                seen[value] = i
    groups = defaultdict(list)
    for i, row in enumerate(records):
        groups[find(i)].append(row["filename"])
    return sorted((sorted(group) for group in groups.values()), key=lambda group: group[0])


def near_candidates(records):
    """Find dHash distance <=3 with four exact 16-bit bucket indexes.

    Any pair within 3 bits shares at least one band. Only bucket collisions are
    compared; a resource cap aborts rather than silently dropping candidates.
    Uniform/low-detail images can still produce large buckets or false matches.
    """
    buckets = defaultdict(list)
    checked = set()
    result = []
    for i, row in enumerate(records):
        value = int(row["dhash64"], 16)
        for band in range(4):
            key = (band, (value >> (band * 16)) & 65535)
            for j in buckets[key]:
                pair = (j, i)
                if pair in checked:
                    continue
                checked.add(pair)
                if len(checked) > MAX_CANDIDATE_CHECKS:
                    raise ValueError("Candidate-check cap exceeded; no outputs written.")
                other = records[j]
                distance = (value ^ int(other["dhash64"], 16)).bit_count()
                if distance <= 3 and row["group_id"] != other["group_id"]:
                    result.append({"filename_a": other["filename"], "filename_b": row["filename"],
                                   "reference_a": other["reference"], "reference_b": row["reference"],
                                   "hamming_distance": distance,
                                   "crosses_provisional_split": other["partition"] != row["partition"],
                                   "review_decision": "unresolved"})
            buckets[key].append(i)
    return sorted(result, key=lambda pair: (pair["filename_a"], pair["filename_b"])), len(checked)


def write_json_exclusive(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(dataset, output, seed=42):
    """Read only Train_Set/Train_Label.csv; never relabel, copy or move images."""
    root, output = Path(dataset).resolve(), Path(output).resolve()
    repo = Path(__file__).resolve().parents[1]
    if output == repo or repo in output.parents or output == root or root in output.parents:
        raise ValueError("Outputs must be outside the repository and source dataset.")
    names = ("preparation_report.json", "provisional_split_manifest.json", "near_duplicate_candidates.csv")
    if any((output / name).exists() for name in names):
        raise FileExistsError("Preparation output exists; refusing overwrite.")
    records = []
    for row in sorted(load_labels(root, "train"), key=lambda row: row["filename"]):
        byte_hash, rgb_hash, dhash = image_fingerprints(row["image_path"])
        records.append({"filename": row["filename"], "reference": row["reference"],
                        "file_sha256": byte_hash, "rgb_sha256": rgb_hash, "dhash64": dhash})
    groups = exact_groups(records)
    shuffled = list(groups)
    random.Random(seed).shuffle(shuffled)
    target = round(len(records) * 0.2)
    validation, count = set(), 0
    for group in shuffled:
        if abs(count + len(group) - target) < abs(count - target):
            validation.update(group)
            count += len(group)
    group_ids = {name: group[0] for group in groups for name in group}
    for row in records:
        row["group_id"] = group_ids[row["filename"]]
        row["partition"] = "validation" if row["filename"] in validation else "train"
    by_name = {row["filename"]: row for row in records}
    duplicates = [{"filenames": group, "conflicting_references":
                   len({by_name[name]["reference"] for name in group}) > 1}
                  for group in groups if len(group) > 1]
    candidates, checks = near_candidates(records)
    manifest = {"schema_version": VERSION, "status": "provisional", "source_split": "train",
                "dataset_path": str(root), "seed": seed, "python_version": sys.version.split()[0],
                "label_csv_sha256": sha256((root / "Train_Label.csv").read_bytes()),
                "split_method": "sorted exact groups; Random(seed).shuffle; greedy nearest 20%",
                "records": records}
    report = {"status": "provisional", "image_count": len(records),
              "train_count": len(records) - count, "validation_count": count,
              "exact_duplicate_groups": duplicates,
              "conflicting_duplicate_group_count": sum(g["conflicting_references"] for g in duplicates),
              "near_candidate_count": len(candidates), "bucket_pair_checks": checks,
              "cross_partition_candidate_count": sum(p["crosses_provisional_split"] for p in candidates),
              "near_method": "dHash64 grayscale 9x8 Lanczos; distance <=3; 4x16-bit band index",
              "review_required": True, "writer_independence": "unknown",
              "baseline_selected": False}
    output.mkdir(parents=True, exist_ok=True)
    write_json_exclusive(output / names[0], report)
    write_json_exclusive(output / names[1], manifest)
    fields = ["filename_a", "filename_b", "reference_a", "reference_b", "hamming_distance",
              "crosses_provisional_split", "review_decision"]
    with (output / names[2]).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)
    return report


def validate_manifest(manifest):
    """Validate frozen split integrity before model loading; reject provisional."""
    if (manifest.get("schema_version") != VERSION or manifest.get("status") != "frozen"
            or manifest.get("source_split") != "train" or manifest.get("review_complete") is not True):
        raise ValueError("An approved frozen training-derived manifest is required.")
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Manifest records are missing.")
    names, assignments = set(), {}
    for row in records:
        name = row.get("filename", "")
        if (not isinstance(name, str) or not name or any(c in name for c in '/\\:')
                or name in (".", "..") or name in names
                or not isinstance(row.get("reference"), str) or not row["reference"].strip()
                or row.get("partition") not in ("train", "validation")):
            raise ValueError("Invalid or duplicate manifest record.")
        names.add(name)
        for field in ("file_sha256", "rgb_sha256", "group_id"):
            value = row.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError("Missing group or hash.")
            if field != "group_id" and (len(value) != 64 or any(c not in '0123456789abcdef' for c in value)):
                raise ValueError("Invalid SHA-256.")
            key = (field, value)
            if key in assignments and assignments[key] != row["partition"]:
                raise ValueError("Duplicate group crosses partitions.")
            assignments[key] = row["partition"]
    if sum(r["partition"] == "validation" for r in records) < 100:
        raise ValueError("At least 100 validation images are required.")
    return records


def score_predictions(records):
    """Same strict exact-match, micro CER and supplementary casefold definitions."""
    if not records or any(not isinstance(r["reference"], str) or not r["reference"].strip()
                          or not isinstance(r["prediction"], str) for r in records):
        raise ValueError("Nonempty references and string predictions are required.")
    edits = sum(levenshtein_distance(r["reference"], r["prediction"]) for r in records)
    characters = sum(len(r["reference"]) for r in records)
    return {"evaluated_count": len(records), "total_character_edits": edits,
            "total_reference_characters": characters,
            "exact_match_accuracy": sum(r["prediction"] == r["reference"] for r in records) / len(records),
            "character_error_rate": edits / characters,
            "case_insensitive_accuracy": sum(r["prediction"].casefold() == r["reference"].casefold()
                                             for r in records) / len(records),
            "comparison_normalization": "none"}


def available_ram_gib():
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "extended")]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("Cannot measure RAM.")
    return status.avail_phys / 1024**3


def _load_runtime():
    """Lazy imports only; this helper never loads weights or downloads files."""
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    from importlib.metadata import version
    return torch, TrOCRProcessor, VisionEncoderDecoderModel, version


def _predict_image(row, root, processor, model, torch):
    """One raw prediction or a safe failure record; MemoryError stops the run."""
    began = time.perf_counter()
    stage = "image_decode_error"
    prediction, error = "", None
    image = None
    preprocessed = began
    inference_started = None
    try:
        with Image.open(root / "Train_Set" / row["filename"]) as source:
            image = source.convert("RGB")
        stage = "preprocessing_error"
        pixels = processor(images=image, return_tensors="pt").pixel_values.to("cpu")
        preprocessed = time.perf_counter()
        inference_started = preprocessed
        stage = "generation_error"
        with torch.inference_mode():
            ids = model.generate(pixels, **DECODING)
        stage = "decoding_error"
        prediction = processor.batch_decode(ids, skip_special_tokens=True)[0]
        if not isinstance(prediction, str):
            raise TypeError("Non-string prediction")
    except MemoryError:
        raise RuntimeError("Memory exhausted; partial results retained, no completed summary.") from None
    except Exception:
        prediction, error = "", stage
    finally:
        if image is not None:
            image.close()
    ended = time.perf_counter()
    return {"filename": row["filename"], "reference": row["reference"],
            "prediction": prediction, "correct": prediction == row["reference"],
            "edit_distance": levenshtein_distance(row["reference"], prediction),
            "error_category": error, "success": error is None,
            "preprocessing_seconds": (preprocessed if inference_started is not None else ended) - began,
            "inference_seconds": ended - inference_started if inference_started is not None else 0.0,
            "total_image_seconds": ended - began}


def _validate_complete_results(results, selected):
    """Never publish a completed summary for a partial/duplicated result set."""
    if (len(selected) != 100 or len(results) != 100
            or len({r["filename"] for r in results}) != 100
            or [(r["filename"], r["reference"]) for r in results] !=
               [(r["filename"], r["reference"]) for r in selected]):
        raise ValueError("Completed summary requires all 100 selected results exactly once.")
    allowed = {"image_decode_error", "preprocessing_error", "generation_error", "decoding_error"}
    for row in results:
        error = row["error_category"]
        if (error is not None and error not in allowed
                or row["success"] != (error is None)
                or error is not None and row["prediction"] != ""):
            raise ValueError("Invalid failure record.")


def run_baseline(manifest_path):
    """Future baseline: requires frozen split_manifest and baseline100_manifest.

    Does not create either manifest. Frozen baseline must list the exact seeded
    100 validation filenames. No model downloads: use pinned local cache only.
    """
    path = Path(manifest_path).resolve()
    if path.with_name(".freeze.lock").exists():
        raise ValueError("Freeze lock present; finalization or recovery must finish first.")
    if path.name != "baseline100_manifest.json":
        raise ValueError("Use an approved baseline100_manifest.json.")
    baseline = json.loads(path.read_text(encoding="utf-8"))
    split_path = path.with_name("split_manifest.json")
    split_bytes = split_path.read_bytes()
    split = json.loads(split_bytes)
    records = validate_manifest(split)
    if (baseline.get("status") != "frozen" or baseline.get("split_manifest_sha256") != sha256(split_bytes)
            or baseline.get("model") != MODEL or baseline.get("revision") != REVISION
            or baseline.get("decoding") != DECODING or baseline.get("seed") != 42):
        raise ValueError("Frozen baseline metadata does not match approved settings.")
    selected = sorted(random.Random(42).sample(sorted(
        [r for r in records if r["partition"] == "validation"], key=lambda r: r["filename"]), 100),
        key=lambda r: r["filename"])
    if baseline.get("filenames") != [r["filename"] for r in selected]:
        raise ValueError("Baseline selection does not match frozen validation subset.")
    output = path.parent
    if any((output / name).exists() for name in ("predictions.jsonl", "summary.json")):
        raise FileExistsError("Baseline results already exist.")
    root = Path(split["dataset_path"])
    if sha256((root / "Train_Label.csv").read_bytes()) != split["label_csv_sha256"]:
        raise ValueError("Training CSV changed.")
    for row in selected:
        image_path = (root / "Train_Set" / row["filename"]).resolve()
        if image_path.parent != (root / "Train_Set").resolve():
            raise ValueError("Unsafe image path.")
        if image_fingerprints(image_path)[:2] != (row["file_sha256"], row["rgb_sha256"]):
            raise ValueError("Selected image changed.")
    started = time.perf_counter()
    ram = {"before_dependencies_gib": available_ram_gib()}
    if ram["before_dependencies_gib"] < 3:
        raise RuntimeError("Less than 3 GiB RAM available before dependencies.")
    torch, processor_class, model_class, version = _load_runtime()
    processor = processor_class.from_pretrained(MODEL, revision=REVISION, use_fast=False, local_files_only=True)
    ram["before_weights_gib"] = available_ram_gib()
    if ram["before_weights_gib"] < 3:
        raise RuntimeError("Less than 3 GiB RAM available immediately before model weights.")
    model = model_class.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to("cpu")
    model.eval()
    ram["after_loading_gib"] = available_ram_gib()
    if ram["after_loading_gib"] < 1:
        raise RuntimeError("Insufficient RAM after model loading; inference not started.")
    results = []
    inference_started = time.perf_counter()
    with (output / "predictions.jsonl").open("x", encoding="utf-8") as stream:
        for row in selected:
            if available_ram_gib() < 1:
                raise RuntimeError("Insufficient RAM; partial predictions retained, no summary.")
            result = _predict_image(row, root, processor, model, torch)
            # Flush and fsync each complete row so interruption retains prior rows.
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            results.append(result)
    inference_runtime = time.perf_counter() - inference_started
    ram["after_inference_gib"] = available_ram_gib()
    _validate_complete_results(results, selected)
    successful = sum(row["success"] for row in results)
    failures = defaultdict(int)
    for row in results:
        if row["error_category"]:
            failures[row["error_category"]] += 1
    summary = {**score_predictions(results), "status": "completed", "model": MODEL, "revision": REVISION,
               "successful_count": successful, "failed_count": 100 - successful,
               "correct_count": sum(row["correct"] for row in results),
               "failure_categories": dict(failures), "available_ram": ram,
               "decoding": DECODING, "use_fast": False, "batch_size": 1, "device": "cpu",
               "local_files_only": True, "eval_mode": True, "inference_mode": True,
               "total_runtime_seconds": time.perf_counter() - started,
               "inference_runtime_seconds": inference_runtime,
               "mean_inference_seconds": sum(r["inference_seconds"] for r in results) / 100,
               "mean_total_image_seconds": sum(r["total_image_seconds"] for r in results) / 100,
               "baseline_manifest_sha256": sha256(path.read_bytes()),
               "split_manifest_sha256": sha256(split_bytes),
               "generation_defaults": model.generation_config.to_dict(),
               "versions": {name: version(name) for name in
                            ("torch", "transformers", "Pillow", "numpy", "sentencepiece", "protobuf")}}
    write_json_exclusive(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--dataset", required=True)
    prep.add_argument("--output", required=True)
    prep.add_argument("--seed", type=int, default=42)
    freezing = sub.add_parser("freeze")
    freezing.add_argument("--output", required=True)
    run = sub.add_parser("run")
    run.add_argument("--manifest", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        report = prepare(args.dataset, args.output, args.seed)
    elif args.command == "freeze":
        report = freeze(args.output)
    else:
        report = run_baseline(args.manifest)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
