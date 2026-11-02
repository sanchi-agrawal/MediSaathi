"""Synthetic-only infrastructure tests: no weights, training, inference or GPU."""

import json
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image
import pytest

import trocr_training as training


@pytest.fixture
def frozen_inputs(tmp_path):
    train = tmp_path / "dataset" / "Train_Set"
    train.mkdir(parents=True)
    rows = []
    for i in range(40):
        name = f"sample{i:03}.png"
        with Image.new("L", (4, 4), i) as image:
            image.save(train / name)
        a, b, _ = training.image_fingerprints(train / name)
        rows.append(dict(filename=name, reference=f" Fictional-{i}! ", file_sha256=a,
                         rgb_sha256=b, group_id=name, partition="train"))
    # Excluded images have metadata but no file, proving they aren't read.
    for i, name in enumerate(sorted(training.EXCLUDED), 100):
        rows.append(dict(filename=name, reference="conflict", file_sha256=f"{i:064x}",
                         rgb_sha256=f"{i:064x}", group_id=name, partition="train"))
    for i in range(100):
        rows.append(dict(filename=f"validation{i}.jpg", reference="Never train", file_sha256=f"{i+1000:064x}",
                         rgb_sha256=f"{i+1000:064x}", group_id=f"val{i}", partition="validation"))
    split = {"schema_version": 1, "status": "frozen", "source_split": "train", "review_complete": True,
             "seed": 42, "records": rows, "conflicting_reference_groups": [sorted(training.EXCLUDED)]}
    sp, bp = tmp_path / "split_manifest.json", tmp_path / "baseline100_manifest.json"
    data = json.dumps(split).encode()
    sp.write_bytes(data)
    baseline = {"status": "frozen", "source_split": "train", "split_manifest_sha256": training.sha256(data),
                "model": training.MODEL, "revision": training.REVISION, "decoding": training.DECODING,
                "filenames": [r["filename"] for r in rows if r["partition"] == "validation"]}
    bp.write_text(json.dumps(baseline), encoding="utf-8")
    return sp, bp, train


def test_selection_reproducible_preserves_rows(frozen_inputs):
    sp, bp, train = frozen_inputs
    bundle = training.load_training_manifest(sp, bp)
    state = random.getstate()
    selected = training.select_sanity_records(bundle)
    assert selected == training.select_sanity_records(bundle)
    assert random.getstate() == state
    assert len(selected) == len({r["group_id"] for r in selected}) == 32
    assert all(r["partition"] == "train" and r["filename"] not in training.EXCLUDED for r in selected)
    original = {r["filename"]: r for r in bundle["records"]}
    assert all(row == original[row["filename"]] for row in selected)
    assert all(row["reference"].startswith(" ") and row["reference"].endswith("! ") for row in selected)
    assert training.preflight(sp, bp, train)["selected_count"] == 32


def test_duplicate_group_representative(frozen_inputs):
    bundle = training.load_training_manifest(*frozen_inputs[:2])
    bundle["records"][1]["group_id"] = bundle["records"][0]["group_id"]
    selected = training.select_sanity_records(bundle)
    assert len({r["group_id"] for r in selected}) == 32
    assert "sample001.png" not in [r["filename"] for r in selected]


@pytest.mark.parametrize("kind", ["hash", "provisional", "leakage", "duplicate_baseline", "unknown_conflict"])
def test_manifest_integrity_rejection(frozen_inputs, kind):
    sp, bp, _ = frozen_inputs
    split = json.loads(sp.read_text())
    base = json.loads(bp.read_text())
    if kind == "hash":
        base["split_manifest_sha256"] = "0" * 64
    elif kind == "provisional":
        split["status"] = "provisional"
    elif kind == "leakage":
        split["records"][-1]["group_id"] = split["records"][0]["group_id"]
    elif kind == "duplicate_baseline":
        base["filenames"][-1] = base["filenames"][0]
    else:
        split["conflicting_reference_groups"] = [["new-conflict.png"]]
    sp.write_text(json.dumps(split))
    if kind != "hash":
        base["split_manifest_sha256"] = training.sha256(sp.read_bytes())
    bp.write_text(json.dumps(base))
    with pytest.raises(ValueError):
        training.load_training_manifest(sp, bp)


def test_insufficient_groups(frozen_inputs):
    bundle = training.load_training_manifest(*frozen_inputs[:2])
    bundle["records"] = bundle["records"][:10]
    with pytest.raises(training.TrainingInputError):
        training.select_sanity_records(bundle)


@pytest.mark.parametrize("kind", ["validation", "excluded", "unsafe_path", "wrong_root", "hash"])
def test_training_image_enforcement(frozen_inputs, kind):
    bundle = training.load_training_manifest(*frozen_inputs[:2])
    row = dict(bundle["records"][0])
    root = frozen_inputs[2]
    if kind == "validation": row["partition"] = "validation"
    if kind == "excluded": row["filename"] = sorted(training.EXCLUDED)[0]
    if kind == "unsafe_path": row["filename"] = "../sample.png"
    if kind == "wrong_root": root = root.parent / "Test_Set"
    if kind == "hash": row["rgb_sha256"] = "0" * 64
    with pytest.raises(training.TrainingInputError):
        training.checked_image(row, root)


def tokenizer(ids=None):
    tok = MagicMock()
    tok.return_value = {"input_ids": [0, 10, 2] if ids is None else ids}
    tok.pad_token_id, tok.eos_token_id, tok.bos_token_id = 1, 2, 0
    return tok


def test_label_padding_exact_input():
    tok = tokenizer()
    assert training.encode_labels("  Fictional-X! ", tok, 6) == [0, 10, 2, -100, -100, -100]
    tok.assert_called_once_with("  Fictional-X! ", add_special_tokens=True, truncation=False, padding=False)


@pytest.mark.parametrize("ids,limit", [([0, 3, 4, 5, 2], 4), ([0, 3], 4), ([], 4)])
def test_label_overflow_or_missing_eos(ids, limit):
    with pytest.raises(training.TrainingInputError):
        training.encode_labels("Fictional", tokenizer(ids), limit)


def decoder_model():
    return SimpleNamespace(config=SimpleNamespace(pad_token_id=None, decoder_start_token_id=None,
        decoder=SimpleNamespace(vocab_size=100)), generation_config=SimpleNamespace(
            decoder_start_token_id=2, pad_token_id=1, eos_token_id=2))


def test_decoder_settings():
    model, tok = decoder_model(), tokenizer()
    assert training.validate_decoder_tokens(model, tok)["decoder_start_token_id"] == 2
    model.generation_config.pad_token_id = 99
    with pytest.raises(training.TrainingInputError):
        training.validate_decoder_tokens(model, tok)


def test_rgb_processor_encoding(frozen_inputs):
    row = training.load_training_manifest(*frozen_inputs[:2])["records"][0]
    processor = MagicMock()
    processor.tokenizer = tokenizer()
    def encode(**kwargs):
        assert kwargs["images"].mode == "RGB"
        return SimpleNamespace(pixel_values=["fake-pixels"])
    processor.side_effect = encode
    encoded = training.encode_example(row, frozen_inputs[2], processor, 4)
    assert encoded == {"pixel_values": "fake-pixels", "labels": [0, 10, 2, -100]}


def test_incomplete_accumulation_windows():
    windows = training.accumulation_windows(11, 3, 2, 42)
    assert [list(map(len, window)) for window in windows] == [[3, 3], [3, 2]]
    assert sorted(i for w in windows for batch in w for i in batch) == list(range(11))
    assert windows == training.accumulation_windows(11, 3, 2, 42)
    assert training.window_weights(windows[-1]) == [.6, .4]
    # Loss/gradient weighting of a short window must not divide by full capacity.
    assert sum(loss * weight for loss, weight in zip([2, 4], training.window_weights(windows[-1]))) == pytest.approx(2.8)
    tail = training.accumulation_windows(10, 3, 3, 42)[-1]
    assert list(map(len, tail)) == [1] and training.window_weights(tail) == [1.0]


def test_backward_scaling_of_incomplete_window():
    recorded = []
    class FakeLoss:
        def __init__(self, value): self.value = value
        def detach(self): return self
        def item(self): return self.value
        def __mul__(self, scale): return FakeLoss(self.value * scale)
        def backward(self): recorded.append(self.value)
    window = [[0, 1, 2], [3, 4]]
    average = training.backward_window(window, lambda ids: FakeLoss(2 if ids[0] == 0 else 4))
    assert average == pytest.approx(2.8)
    assert recorded == pytest.approx([1.2, 1.6])
    recorded.clear()
    with pytest.raises(training.TrainingStopped):
        training.backward_window([[0]], lambda ids: FakeLoss(float('nan')))
    assert recorded == []


def test_training_refuses_existing_output_before_runtime(frozen_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(training, "__file__", str(tmp_path / "repo" / "medisaathi" / "trocr_training.py"))
    monkeypatch.setattr(training, "_runtime", lambda: pytest.fail("Runtime imported"))
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        training.train_sanity(*frozen_inputs, output)


def test_training_stops_without_gpu(frozen_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(training, "__file__", str(tmp_path / "repo" / "medisaathi" / "trocr_training.py"))
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    monkeypatch.setattr(training, "_runtime", lambda: (fake_torch, None, None, None))
    with pytest.raises(training.TrainingStopped, match="cuda_unavailable"):
        training.train_sanity(*frozen_inputs, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True])
def test_finite_safeguard(value):
    with pytest.raises(training.TrainingStopped):
        training.require_finite(value)


@pytest.mark.parametrize("count,passed", [(0, False), (30, False), (31, True), (32, True)])
def test_memorization_gate(count, passed):
    report = training.sanity_gate(count)
    assert report["passed"] is passed
    assert report["full_training_authorized"] is False


def test_checkpoint_metadata_and_overwrite(frozen_inputs, tmp_path):
    bundle = training.load_training_manifest(*frozen_inputs[:2])
    selected = training.select_sanity_records(bundle)
    metadata = training.checkpoint_metadata(bundle, selected, training.TrainingConfig(), 50, "checkpoint", {})
    assert metadata["revision"] == training.REVISION and metadata["optimizer_step"] == 50
    assert "reference" not in json.dumps(metadata)
    assert "Never train" not in json.dumps(metadata)
    model, processor, optimizer, torch = (MagicMock() for _ in range(4))
    def save_model(path, **kwargs):
        path.mkdir()
        (path / "model.safetensors").write_bytes(b"synthetic weights")
    model.save_pretrained.side_effect = save_model
    torch.save.side_effect = lambda state, path: path.write_bytes(b"synthetic optimizer")
    target = tmp_path / "checkpoint"
    training.save_checkpoint(target, model, processor, optimizer, torch, metadata)
    hashes = json.loads((target / "checksums.json").read_text())
    assert all(training.sha256((target / name).read_bytes()) == value for name, value in hashes.items())
    with pytest.raises(FileExistsError):
        training.save_checkpoint(target, model, processor, optimizer, torch, metadata)


def test_failed_checkpoint_cleanup(tmp_path):
    model = MagicMock()
    model.save_pretrained.side_effect = RuntimeError("synthetic")
    with pytest.raises(RuntimeError):
        training.save_checkpoint(tmp_path / "target", model, MagicMock(), MagicMock(), MagicMock(), {})
    assert list(tmp_path.iterdir()) == []


def test_preflight_does_not_import_runtime(frozen_inputs, monkeypatch):
    monkeypatch.setattr(training, "_runtime", lambda: pytest.fail("Runtime imported"))
    sp, bp, train = frozen_inputs
    assert training.preflight(sp, bp, train)["distinct_groups"] == 32


def test_import_has_no_torch_or_cloud_imports():
    result = subprocess.run([sys.executable, "-B", "-c",
        "import sys; import trocr_training; assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules; assert 'google.genai' not in sys.modules; print('lazy import OK')"],
        capture_output=True, text=True, check=True, cwd=Path(training.__file__).parent)
    assert "lazy import OK" in result.stdout


def test_notebook_unexecuted():
    path = Path(training.__file__).parent / "notebooks" / "trocr_cloud_pilot.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and cell["outputs"] == []
            compile(''.join(cell["source"]), '<notebook-cell>', 'exec')
