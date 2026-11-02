"""Synthetic, offline tests. No model loading or downloads."""

import csv
import json
import random

import pytest
from PIL import Image, PngImagePlugin

import trocr_baseline as baseline


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    # Simulate a separate repository so tests can use pytest's sandbox temp dir.
    monkeypatch.setattr(baseline, "__file__", str(tmp_path / "repo" / "medisaathi" / "trocr_baseline.py"))
    root = tmp_path / "source"
    (root / "Train_Set").mkdir(parents=True)
    rows = []
    for i in range(15):
        filename = f"p{i:03}.png"
        rng = random.Random(i)
        with Image.new("RGB", (16, 16)) as image:
            image.putdata([tuple(rng.randrange(256) for _ in range(3)) for _ in range(256)])
            image.save(root / "Train_Set" / filename)
        rows.append((filename, f" Word-{i} "))
    # Identical pixels in two differently encoded files, with conflicting labels.
    with Image.open(root / "Train_Set" / "p000.png") as image:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("synthetic", "different metadata")
        image.save(root / "Train_Set" / "copy.png", pnginfo=metadata)
    rows.append(("copy.png", "Different"))
    with (root / "Train_Label.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Images", "Text"])
        writer.writerows(rows)
    return root


def test_preparation_deterministic_and_group_integrity(dataset, tmp_path):
    out1, out2 = tmp_path / "a", tmp_path / "b"
    first = baseline.prepare(dataset, out1)
    second = baseline.prepare(dataset, out2)
    assert first == second
    assert (out1 / "provisional_split_manifest.json").read_bytes() == (out2 / "provisional_split_manifest.json").read_bytes()
    manifest = json.loads((out1 / "provisional_split_manifest.json").read_text())
    rows = {r["filename"]: r for r in manifest["records"]}
    assert rows["p000.png"]["reference"] == " Word-0 "
    assert rows["copy.png"]["partition"] == rows["p000.png"]["partition"]
    assert rows["copy.png"]["file_sha256"] != rows["p000.png"]["file_sha256"]
    assert rows["copy.png"]["rgb_sha256"] == rows["p000.png"]["rgb_sha256"]
    assert first["conflicting_duplicate_group_count"] == 1
    assert not (out1 / "split_manifest.json").exists()
    assert not (out1 / "baseline100_manifest.json").exists()
    assert first["image_count"] == first["train_count"] + first["validation_count"]


def test_overwrite_protection(dataset, tmp_path):
    output = tmp_path / "output"
    baseline.prepare(dataset, output)
    original = (output / "preparation_report.json").read_bytes()
    with pytest.raises(FileExistsError):
        baseline.prepare(dataset, output)
    assert (output / "preparation_report.json").read_bytes() == original


def test_output_not_in_dataset(dataset):
    with pytest.raises(ValueError):
        baseline.prepare(dataset, dataset / "outputs")


def test_candidate_index_matches_small_brute_force():
    rng = random.Random(42)
    hashes = [rng.getrandbits(64) for _ in range(40)]
    hashes += [hashes[0] ^ 7, hashes[1] ^ (1 << 35)]
    rows = [{"filename": f"p{i:03}", "reference": "fictional", "group_id": str(i),
             "partition": "train", "dhash64": f"{value:016x}"} for i, value in enumerate(hashes)]
    found, checks = baseline.near_candidates(rows)
    expected = {(rows[j]["filename"], rows[i]["filename"]) for i in range(len(rows)) for j in range(i)
                if (hashes[i] ^ hashes[j]).bit_count() <= 3}
    assert {(r["filename_a"], r["filename_b"]) for r in found} == expected
    assert checks < len(rows) * (len(rows) - 1) // 2


def test_candidate_cap_fails_closed(monkeypatch):
    monkeypatch.setattr(baseline, "MAX_CANDIDATE_CHECKS", 0)
    rows = [{"dhash64": "0000000000000000"} for _ in range(2)]
    with pytest.raises(ValueError, match="cap"):
        baseline.near_candidates(rows)


def frozen():
    return {"schema_version": 1, "status": "frozen", "source_split": "train", "review_complete": True,
            "records": [{"filename": f"p{i}.jpg", "reference": "A", "group_id": str(i),
                         "file_sha256": f"{i:064x}", "rgb_sha256": f"{i:064x}",
                         "partition": "validation"} for i in range(100)]}


def test_frozen_manifest_validation():
    manifest = frozen()
    assert len(baseline.validate_manifest(manifest)) == 100
    manifest["status"] = "provisional"
    with pytest.raises(ValueError):
        baseline.validate_manifest(manifest)


@pytest.mark.parametrize("field", ["group_id", "file_sha256", "rgb_sha256"])
def test_manifest_rejects_cross_partition_groups(field):
    manifest = frozen()
    row = dict(manifest["records"][0], filename="training.jpg", partition="train")
    row["group_id"] = "new"
    row["file_sha256"] = "f" * 64
    row["rgb_sha256"] = "e" * 64
    row[field] = manifest["records"][0][field]
    manifest["records"].append(row)
    with pytest.raises(ValueError, match="crosses"):
        baseline.validate_manifest(manifest)


@pytest.mark.parametrize("change", [{"filename": "../unsafe.jpg"}, {"reference": ""},
                                     {"file_sha256": "bad"}, {"partition": "test"}])
def test_invalid_manifest_records(change):
    manifest = frozen()
    manifest["records"][0].update(change)
    with pytest.raises(ValueError):
        baseline.validate_manifest(manifest)


def test_metrics():
    report = baseline.score_predictions([
        {"reference": "AB", "prediction": "AB"},
        {"reference": "Cd", "prediction": "cd"},
        {"reference": "EF", "prediction": ""}])
    assert report["exact_match_accuracy"] == pytest.approx(1 / 3)
    assert report["character_error_rate"] == 0.5
    assert report["case_insensitive_accuracy"] == pytest.approx(2 / 3)
    assert baseline.score_predictions([{"reference": " A-b ", "prediction": "a b"}])["case_insensitive_accuracy"] == 0


def test_run_rejects_provisional_without_model_loading(tmp_path):
    path = tmp_path / "baseline100_manifest.json"
    path.write_text('{}')
    manifest = frozen()
    manifest["status"] = "provisional"
    (tmp_path / "split_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="frozen"):
        baseline.run_baseline(path)


def review_inputs():
    records = [{"filename": f"p{i}.png", "reference": f" Word {i} ",
                "partition": "train", "dhash64": f"{i:016x}",
                "file_sha256": f"{i:064x}", "rgb_sha256": f"{i:064x}"} for i in range(3)]
    candidates = "filename_a,filename_b,reference_a,reference_b,hamming_distance,crosses_provisional_split\np0.png,p1.png, Word 0 , Word 1 ,1,False\np1.png,p2.png, Word 1 , Word 2 ,2,False\n"
    review = "pair_number,filename_a,filename_b,reference_a,reference_b,hamming_distance,crosses_provisional_split,partition_a,partition_b,decision,notes\n1,p0.png,p1.png, Word 0 , Word 1 ,1,False,train,train,,\n2,p1.png,p2.png, Word 1 , Word 2 ,2,False,train,train,,\n"
    return records, candidates.encode(), review.encode()


def test_review_preserves_labels_and_transitive_groups():
    records, candidates, review = review_inputs()
    approved, data = baseline._approved_review(candidates, review, records, 2)
    assert all(r["decision"] == "confirmed_duplicate" for r in approved)
    assert approved[0]["reference_a"] == " Word 0 "
    assert baseline.reviewed_groups(records, approved) == [["p0.png", "p1.png", "p2.png"]]
    assert b"User-confirmed" in data


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "label", "decision", "note", "malformed"])
def test_invalid_review_rejected(change):
    records, candidates, review = review_inputs()
    lines = review.decode().splitlines(keepends=True)
    if change == "missing":
        review = ''.join(lines[:-1]).encode()
    elif change == "duplicate":
        review = (lines[0] + lines[1] + lines[1]).encode()
    elif change == "extra":
        review += lines[1].encode()
    elif change == "label":
        review = review.replace(b" Word 0 ", b"altered")
    elif change == "decision":
        review = review.replace(b"train,train,,", b"train,train,distinct,")
    elif change == "note":
        review = review.replace(b"train,train,,", b"train,train,,my existing note")
    else:
        review = review.replace(b"train,train,,", b"train")
    with pytest.raises((ValueError, csv.Error)):
        baseline._approved_review(candidates, review, records, 2)


def test_transaction_rolls_back_second_publish_failure(tmp_path, monkeypatch):
    review = tmp_path / "near_duplicate_review.csv"
    review.write_bytes(b"original")
    original = baseline.os.link
    def broken(source, target):
        if target.name == "baseline100_manifest.json":
            raise OSError("synthetic failure")
        original(source, target)
    monkeypatch.setattr(baseline.os, "link", broken)
    with pytest.raises(OSError):
        baseline._commit_freeze(tmp_path, b"{}", b"{}", b"updated")
    assert review.read_bytes() == b"original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["near_duplicate_review.csv"]


def test_transaction_rolls_back_review_replace_failure(tmp_path, monkeypatch):
    (tmp_path / "near_duplicate_review.csv").write_bytes(b"original")
    def broken(*args):
        raise OSError("synthetic review failure")
    monkeypatch.setattr(baseline.os, "replace", broken)
    with pytest.raises(OSError):
        baseline._commit_freeze(tmp_path, b"{}", b"{}", b"updated")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["near_duplicate_review.csv"]
    assert (tmp_path / "near_duplicate_review.csv").read_bytes() == b"original"


def test_transaction_overwrite_and_lock_protection(tmp_path):
    final = tmp_path / "split_manifest.json"
    final.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        baseline._commit_freeze(tmp_path, b"new", b"new", b"new")
    assert final.read_bytes() == b"keep"
    assert not (tmp_path / ".freeze.lock").exists()


@pytest.fixture
def freeze_preparation(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "__file__", str(tmp_path / "repo" / "medisaathi" / "trocr_baseline.py"))
    root = tmp_path / "source"
    directory = root / "Train_Set"
    directory.mkdir(parents=True)
    records = []
    with (root / "Train_Label.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Images", "Text"])
        for i in range(510):
            name = f"p{i:04}.png"
            with Image.new("RGB", (2, 2), (i % 256, i // 256, 17)) as image:
                image.save(directory / name)
            a, b, d = baseline.image_fingerprints(directory / name)
            records.append(dict(filename=name, reference=f" W{i} ", file_sha256=a, rgb_sha256=b,
                                dhash64=d, group_id=name, partition="train"))
            writer.writerow([name, f" W{i} "])
    out = tmp_path / "output"
    out.mkdir()
    baseline.write_json_exclusive(out / "provisional_split_manifest.json", {
        "schema_version": 1, "status": "provisional", "source_split": "train", "seed": 42,
        "dataset_path": str(root), "label_csv_sha256": baseline.sha256((root / "Train_Label.csv").read_bytes()),
        "records": records})
    candidate_fields = ["filename_a", "filename_b", "reference_a", "reference_b", "hamming_distance", "crosses_provisional_split"]
    review_fields = ["pair_number"] + candidate_fields + ["partition_a", "partition_b", "decision", "notes"]
    pairs = []
    for i in range(22):
        a, b = records[i:i+2]
        pairs.append(dict(filename_a=a["filename"], filename_b=b["filename"], reference_a=a["reference"],
                          reference_b=b["reference"], hamming_distance=0, crosses_provisional_split="False"))
    for filename, fields, rows in (
        ("near_duplicate_candidates.csv", candidate_fields, pairs),
        ("near_duplicate_review.csv", review_fields, [dict(p, pair_number=i+1, partition_a="train", partition_b="train", decision="", notes="") for i,p in enumerate(pairs)])):
        with (out / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    return root, out


def test_full_freeze_deterministic_and_integrity(freeze_preparation, tmp_path):
    import shutil
    root, output = freeze_preparation
    second = tmp_path / "second"
    shutil.copytree(output, second)
    report = baseline.freeze(output)
    assert report == baseline.freeze(second)
    assert (output / "split_manifest.json").read_bytes() == (second / "split_manifest.json").read_bytes()
    assert (output / "baseline100_manifest.json").read_bytes() == (second / "baseline100_manifest.json").read_bytes()
    split = json.loads((output / "split_manifest.json").read_text())
    selected = json.loads((output / "baseline100_manifest.json").read_text())
    assert len(baseline.validate_manifest(split)) == 510
    assert report["duplicate_group_count"] == 1 and report["duplicate_images_involved"] == 23
    assert len(selected["filenames"]) == len(set(selected["filenames"])) == 100
    assert all(r["partition"] == "validation" for r in selected["records"])
    assert baseline.sha256((output / "split_manifest.json").read_bytes()) == selected["split_manifest_sha256"]
    with pytest.raises(FileExistsError):
        baseline.freeze(output)


@pytest.mark.parametrize("target", ["csv", "image"])
def test_source_changes_block_freeze(freeze_preparation, target):
    root, output = freeze_preparation
    changed = root / "Train_Label.csv" if target == "csv" else root / "Train_Set" / "p0000.png"
    changed.write_bytes(changed.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="hash"):
        baseline.freeze(output)
    assert not (output / "split_manifest.json").exists()
    assert not (output / "baseline100_manifest.json").exists()


@pytest.fixture
def fake_runtime():
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    processor = MagicMock()
    processor.batch_decode.return_value = ["fictional"]
    model = MagicMock()
    model.to.return_value = model
    model.generation_config.to_dict.return_value = {}
    processor_class, model_class = MagicMock(), MagicMock()
    processor_class.from_pretrained.return_value = processor
    model_class.from_pretrained.return_value = model
    torch = SimpleNamespace(inference_mode=nullcontext)
    return torch, processor_class, model_class, lambda name: "test-version"


@pytest.mark.parametrize("stage", ["image_decode_error", "preprocessing_error", "generation_error", "decoding_error"])
def test_per_image_safe_failures(dataset, fake_runtime, stage):
    torch, pc, mc, _ = fake_runtime
    processor, model = pc.from_pretrained(), mc.from_pretrained()
    filename = "missing.png" if stage == "image_decode_error" else "p000.png"
    if stage == "preprocessing_error":
        processor.side_effect = ValueError("secret path and payload")
    elif stage == "generation_error":
        model.generate.side_effect = RuntimeError("secret path and payload")
    elif stage == "decoding_error":
        processor.batch_decode.side_effect = ValueError("secret path and payload")
    result = baseline._predict_image({"filename": filename, "reference": "ABC"}, dataset, processor, model, torch)
    assert result["error_category"] == stage
    assert result["prediction"] == "" and not result["success"]
    assert result["correct"] is False and result["edit_distance"] == 3
    assert "secret" not in json.dumps(result)
    assert baseline.score_predictions([result])["character_error_rate"] == 1


def test_memory_error_is_fatal(dataset, fake_runtime):
    torch, pc, mc, _ = fake_runtime
    model = mc.from_pretrained()
    model.generate.side_effect = MemoryError("private")
    with pytest.raises(RuntimeError, match="Memory exhausted"):
        baseline._predict_image({"filename": "p000.png", "reference": "A"}, dataset, pc.from_pretrained(), model, torch)


@pytest.fixture
def run_setup(freeze_preparation, monkeypatch, fake_runtime):
    root, output = freeze_preparation
    baseline.freeze(output)
    monkeypatch.setattr(baseline, "_load_runtime", lambda: fake_runtime)
    monkeypatch.setattr(baseline, "available_ram_gib", lambda: 5.0)
    return root, output, fake_runtime


def test_full_mock_baseline_counts_and_overwrite(run_setup):
    root, output, runtime = run_setup
    selected = json.loads((output / "baseline100_manifest.json").read_text())["records"]
    processor = runtime[1].from_pretrained.return_value
    # Alternate exact matches and errors. All 100 remain in denominators.
    processor.batch_decode.side_effect = [([row["reference"]] if i % 2 == 0 else ValueError("private"))
                                         for i, row in enumerate(selected)]
    original_hashes = [baseline.sha256((output / name).read_bytes()) for name in ("split_manifest.json", "baseline100_manifest.json")]
    report = baseline.run_baseline(output / "baseline100_manifest.json")
    assert report["successful_count"] == report["failed_count"] == 50
    assert report["correct_count"] == 50 and report["evaluated_count"] == 100
    assert report["exact_match_accuracy"] == .5
    assert report["total_reference_characters"] == sum(len(r["reference"]) for r in selected)
    expected_edits = sum(len(r["reference"]) for i, r in enumerate(selected) if i % 2)
    assert report["character_error_rate"] == expected_edits / report["total_reference_characters"]
    assert report["failure_categories"] == {"decoding_error": 50}
    assert len(report["available_ram"]) == 4
    runtime[2].from_pretrained.assert_called_once_with(baseline.MODEL, revision=baseline.REVISION, local_files_only=True)
    runtime[2].from_pretrained.return_value.eval.assert_called_once()
    saved = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
    assert len(saved) == 100 and "private" not in str(saved)
    assert original_hashes == [baseline.sha256((output / name).read_bytes()) for name in ("split_manifest.json", "baseline100_manifest.json")]
    with pytest.raises(FileExistsError):
        baseline.run_baseline(output / "baseline100_manifest.json")


@pytest.mark.parametrize("measurements,model_called", [([2.9], False), ([5, 2.9], False), ([5, 5, .9], True)])
def test_ram_checkpoints_stop(run_setup, monkeypatch, measurements, model_called):
    _, output, runtime = run_setup
    values = iter(measurements)
    monkeypatch.setattr(baseline, "available_ram_gib", lambda: next(values))
    with pytest.raises(RuntimeError, match="RAM"):
        baseline.run_baseline(output / "baseline100_manifest.json")
    assert runtime[2].from_pretrained.called is model_called
    assert not (output / "summary.json").exists()
    assert not (output / "predictions.jsonl").exists()


def test_partial_predictions_survive_memory_stop(run_setup, monkeypatch):
    _, output, _ = run_setup
    values = iter([5, 5, 5, 5, .5])
    monkeypatch.setattr(baseline, "available_ram_gib", lambda: next(values))
    with pytest.raises(RuntimeError, match="partial"):
        baseline.run_baseline(output / "baseline100_manifest.json")
    assert len((output / "predictions.jsonl").read_text().splitlines()) == 1
    assert not (output / "summary.json").exists()
    with pytest.raises(FileExistsError):
        baseline.run_baseline(output / "baseline100_manifest.json")


@pytest.mark.parametrize("kind", ["partial", "duplicate", "reference"])
def test_complete_summary_validation(kind):
    selected = [{"filename": str(i), "reference": "A"} for i in range(100)]
    results = [dict(r, prediction="A", success=True, error_category=None) for r in selected]
    if kind == "partial":
        results.pop()
    elif kind == "duplicate":
        results[-1] = results[0]
    else:
        results[0]["reference"] = "changed"
    with pytest.raises(ValueError, match="100"):
        baseline._validate_complete_results(results, selected)


def test_model_loading_failure_does_not_publish(run_setup):
    _, output, runtime = run_setup
    runtime[2].from_pretrained.side_effect = RuntimeError("synthetic load failure")
    with pytest.raises(RuntimeError, match="synthetic load"):
        baseline.run_baseline(output / "baseline100_manifest.json")
    assert not (output / "predictions.jsonl").exists()
    assert not (output / "summary.json").exists()
