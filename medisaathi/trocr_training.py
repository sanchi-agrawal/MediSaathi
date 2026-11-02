"""Opt-in 32-image TrOCR sanity training; imports perform no model/GPU work.

Only train_sanity() loads weights/trains; preflight verifies local inputs only.
Frozen manifests are never edited. No upload, packaging, full-training or resume
operation is provided. Cloud upload requires separate privacy/permission review.
"""

import argparse
import json
import math
import os
import random
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from trocr_baseline import MODEL, REVISION, DECODING, image_fingerprints, sha256, validate_manifest

EXCLUDED = frozenset({"P2504.jpg", "P2830.jpg", "P2510.jpg", "P2887.jpg",
                      "P2513.jpg", "P3002.jpg", "P2516.jpg", "P3026.jpg"})
ATTRIBUTION = {
    "title": "RxHandBD: A Handwritten Prescription Word Image Dataset",
    "contributor": "Md Masudul Islam", "version": 3,
    "doi": "10.17632/dsb5r6vskg.3", "license": "CC BY 4.0",
    "source": "https://data.mendeley.com/datasets/dsb5r6vskg/3",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "changes": "Training-derived duplicate-aware partition; eight conflicting-label exclusions; labels unchanged.",
    "privacy": "License is not consent or proof of de-identification. Review before cloud upload.",
}


class TrainingInputError(ValueError):
    """Inputs fail an integrity or configuration check."""


class TrainingStopped(RuntimeError):
    """Controlled training failure with a fixed, safe category."""


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = 42
    batch_size: int = 2
    accumulation_steps: int = 4
    max_steps: int = 200
    learning_rate: float = 1e-4
    weight_decay: float = 0.0
    max_grad_norm: float = 1.0
    max_label_length: int = 64
    checkpoint_every: int = 50
    diagnose_every: int = 50

    def validate(self):
        for name in ("batch_size", "accumulation_steps", "max_steps", "max_label_length",
                     "checkpoint_every", "diagnose_every"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise TrainingInputError("Training counts must be positive integers.")
        if self.seed != 42 or self.batch_size > 32 or self.max_steps > 200:
            raise TrainingInputError("This sanity experiment requires seed 42 and at most 200 steps.")
        for value in (self.learning_rate, self.weight_decay, self.max_grad_norm):
            require_finite(value)
        if self.learning_rate <= 0 or self.weight_decay < 0 or self.max_grad_norm <= 0:
            raise TrainingInputError("Invalid optimizer settings.")


def require_finite(value):
    """Reject invalid scalar loss/gradient measurements without logging values."""
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise TrainingStopped("nonfinite_loss_or_gradient")


def load_training_manifest(split_path, baseline_path):
    """Read immutable frozen bytes; check baseline link and partition authority."""
    split_path, baseline_path = Path(split_path), Path(baseline_path)
    if split_path.with_name(".freeze.lock").exists():
        raise TrainingInputError("Unfinished freeze transaction.")
    split_bytes, baseline_bytes = split_path.read_bytes(), baseline_path.read_bytes()
    split, baseline = json.loads(split_bytes), json.loads(baseline_bytes)
    records = validate_manifest(split)
    lookup = {row["filename"]: row for row in records}
    filenames = baseline.get("filenames", [])
    if (split.get("seed") != 42 or baseline.get("status") != "frozen"
            or baseline.get("source_split") != "train"
            or baseline.get("split_manifest_sha256") != sha256(split_bytes)
            or baseline.get("model") != MODEL or baseline.get("revision") != REVISION
            or baseline.get("decoding") != DECODING
            or len(filenames) != 100 or len(set(filenames)) != 100
            or any(name not in lookup or lookup[name]["partition"] != "validation" for name in filenames)):
        raise TrainingInputError("Frozen manifest integrity failure.")
    for group in split.get("conflicting_reference_groups", []):
        if any(name not in EXCLUDED for name in group):
            raise TrainingInputError("Unrecognized conflicting-label image; review exclusions first.")
    return {"records": records, "split_sha256": sha256(split_bytes),
            "baseline_sha256": sha256(baseline_bytes)}


def select_sanity_records(bundle):
    """One lexicographically first eligible representative per group, then seed 42."""
    representatives = {}
    for row in sorted(bundle["records"], key=lambda row: row["filename"]):
        if row["partition"] == "train" and row["filename"] not in EXCLUDED:
            representatives.setdefault(row["group_id"], row)
    if len(representatives) < 32:
        raise TrainingInputError("Need 32 eligible distinct training groups.")
    population = sorted(representatives.values(), key=lambda row: row["filename"])
    return [dict(row) for row in sorted(random.Random(42).sample(population, 32),
                                       key=lambda row: row["filename"])]


def checked_image(row, train_dir):
    """Never resolve through a source Test_Set or accept a validation/excluded row."""
    root = Path(train_dir).resolve()
    if row["partition"] != "train" or row["filename"] in EXCLUDED:
        raise TrainingInputError("Only eligible training records may be encoded.")
    path = (root / row["filename"]).resolve()
    if path.parent != root or root.name != "Train_Set":
        raise TrainingInputError("Unsafe or non-training image path.")
    if image_fingerprints(path)[:2] != (row["file_sha256"], row["rgb_sha256"]):
        raise TrainingInputError("Training image hash mismatch.")
    with Image.open(path) as source:
        return source.convert("RGB")


def validate_decoder_tokens(model, tokenizer):
    """Check actual token IDs without changing pretrained configuration."""
    config = model.config
    start = model.generation_config.decoder_start_token_id
    pad, eos = tokenizer.pad_token_id, tokenizer.eos_token_id
    vocab = config.decoder.vocab_size
    if (any(type(value) is not int or not 0 <= value < vocab for value in (start, pad, eos))
            or pad == eos or start not in (tokenizer.bos_token_id, eos)
            or config.pad_token_id not in (None, pad)
            or config.decoder_start_token_id not in (None, start)
            or model.generation_config.pad_token_id != pad
            or model.generation_config.eos_token_id != eos):
        raise TrainingInputError("Decoder/tokenizer special tokens disagree.")
    return {"decoder_start_token_id": start, "pad_token_id": pad, "eos_token_id": eos}


def encode_labels(text, tokenizer, max_length):
    """Tokenize full original text first; reject overflow instead of truncating."""
    if not isinstance(text, str) or not text.strip() or type(max_length) is not int or max_length < 2:
        raise TrainingInputError("Invalid label or label limit.")
    ids = tokenizer(text, add_special_tokens=True, truncation=False, padding=False)["input_ids"]
    if (not ids or any(type(value) is not int or value < 0 for value in ids)
            or ids[-1] != tokenizer.eos_token_id):
        raise TrainingInputError("Incomplete label tokenization.")
    if len(ids) > max_length:
        raise TrainingInputError("Label exceeds token limit; truncation rejected.")
    # Mask only appended padding positions, never genuine content-token positions.
    return ids + [-100] * (max_length - len(ids))


def encode_example(row, train_dir, processor, max_length):
    labels = encode_labels(row["reference"], processor.tokenizer, max_length)
    with checked_image(row, train_dir) as image:
        pixels = processor(images=image, return_tensors="pt").pixel_values[0]
    return {"pixel_values": pixels, "labels": labels}


def accumulation_windows(count, batch_size, accumulation_steps, seed):
    """One shuffled epoch, preserving incomplete final batches/windows."""
    if min(count, batch_size, accumulation_steps) < 1:
        raise TrainingInputError("Invalid accumulation dimensions.")
    order = list(range(count))
    random.Random(seed).shuffle(order)
    batches = [order[i:i + batch_size] for i in range(0, count, batch_size)]
    return [batches[i:i + accumulation_steps] for i in range(0, len(batches), accumulation_steps)]


def window_weights(window):
    """Average by examples, including a short last micro-batch."""
    total = sum(map(len, window))
    return [len(batch) / total for batch in window]


def backward_window(window, compute_loss):
    """Accumulate scaled micro-batch gradients; stop before a nonfinite backward."""
    average = 0.0
    for indices, weight in zip(window, window_weights(window)):
        loss = compute_loss(indices)
        scalar = loss.detach().item()
        require_finite(scalar)
        average += scalar * weight
        (loss * weight).backward()
    return average


def sanity_gate(correct_count, total=32):
    if type(correct_count) is not int or total != 32 or not 0 <= correct_count <= total:
        raise TrainingInputError("Sanity gate requires exactly 32 diagnostics.")
    return {"correct_count": correct_count, "evaluated_count": total,
            "exact_match_accuracy": correct_count / total, "passed": correct_count >= 31,
            "scope": "training_memorization_only", "full_training_authorized": False}


def _runtime():
    import numpy as np
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    return torch, np, TrOCRProcessor, VisionEncoderDecoderModel


def _seed_runtime(torch, np, seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


def _gpu_stats(torch):
    return {"allocated_bytes": torch.cuda.memory_allocated(),
            "reserved_bytes": torch.cuda.memory_reserved(),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated()}


def checkpoint_metadata(bundle, selected, config, step, status, tokens):
    """No reference strings, predictions, absolute dataset paths or secrets."""
    return {"schema_version": 1, "model": MODEL, "revision": REVISION,
            "split_sha256": bundle["split_sha256"], "baseline_sha256": bundle["baseline_sha256"],
            "subset": [{key: row[key] for key in ("filename", "file_sha256", "rgb_sha256", "group_id")}
                       for row in selected],
            "selection": "first eligible filename per group; sorted; Random(42).sample(32); sort",
            "config": asdict(config), "optimizer_step": step, "status": status,
            "decoder_tokens": tokens, "decoding": DECODING, "precision": "float32",
            "dataset_attribution": ATTRIBUTION, "resume_supported": False}


def save_checkpoint(target, model, processor, optimizer, torch, metadata):
    """Stage an inference-ready checkpoint, then rename; never overwrite."""
    target = Path(target)
    if target.exists():
        raise FileExistsError("Checkpoint exists; refusing overwrite.")
    temporary = Path(tempfile.mkdtemp(prefix=".checkpoint-", dir=target.parent))
    try:
        model.save_pretrained(temporary / "model", safe_serialization=True)
        processor.save_pretrained(temporary / "model")
        torch.save(optimizer.state_dict(), temporary / "optimizer.pt")
        (temporary / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
        hashes = {str(p.relative_to(temporary)): sha256(p.read_bytes())
                  for p in sorted(temporary.rglob("*")) if p.is_file()}
        (temporary / "checksums.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
        temporary.rename(target)
    except BaseException:
        shutil.rmtree(temporary)
        raise


def memorization_diagnostics(selected, train_dir, processor, model, torch):
    """Generated train-only exact matches, with raw strings kept out of logs."""
    previous = model.training
    correct = 0
    model.eval()
    try:
        with torch.inference_mode():
            for row in selected:
                with checked_image(row, train_dir) as image:
                    pixels = processor(images=image, return_tensors="pt").pixel_values.to("cuda")
                ids = model.generate(pixels, **DECODING)
                prediction = processor.batch_decode(ids, skip_special_tokens=True)[0]
                correct += prediction == row["reference"]
    finally:
        model.train(previous)
    return sanity_gate(correct, len(selected))


def preflight(split_path, baseline_path, train_dir):
    """Local files only: no torch imports, model loading, tokenization or uploads."""
    bundle = load_training_manifest(split_path, baseline_path)
    selected = select_sanity_records(bundle)
    for row in selected:
        with checked_image(row, train_dir):
            pass
    return {"selected_count": 32, "distinct_groups": len({r["group_id"] for r in selected}),
            "split_sha256": bundle["split_sha256"], "baseline_sha256": bundle["baseline_sha256"],
            "eligible_training_count": sum(r["partition"] == "train" and r["filename"] not in EXCLUDED
                                           for r in bundle["records"]),
            "filenames": [r["filename"] for r in selected], "status": "local_preflight_only"}


def train_sanity(split_path, baseline_path, train_dir, output_dir, config=None):
    """Explicitly opt-in CUDA training. Never called by import or preflight.

    This does NOT authorize cloud data upload. Permission/privacy review must
    precede execution. Each optimizer step accumulates one whole window; an
    incomplete last window is weighted by actual example count. No auto-resume,
    mixed precision, full-partition training, or automatic hyperparameter changes.
    """
    config = config or TrainingConfig()
    config.validate()
    bundle = load_training_manifest(split_path, baseline_path)
    selected = select_sanity_records(bundle)
    for row in selected:
        with checked_image(row, train_dir):
            pass
    output = Path(output_dir).resolve()
    repo = Path(__file__).resolve().parents[1]
    data_root = Path(train_dir).resolve().parent
    if output == repo or repo in output.parents or output == data_root or data_root in output.parents:
        raise TrainingInputError("Training outputs must be outside Git and source data.")
    if output.exists():
        raise FileExistsError("Use a fresh training-run directory; resume is unsupported.")
    torch, np, processor_class, model_class = _runtime()
    if not torch.cuda.is_available():
        raise TrainingStopped("cuda_unavailable")
    # Must be set before CUDA work for deterministic cuBLAS operations.
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    _seed_runtime(torch, np, config.seed)
    try:
        processor = processor_class.from_pretrained(MODEL, revision=REVISION, use_fast=False)
        model = model_class.from_pretrained(MODEL, revision=REVISION).to("cuda", dtype=torch.float32)
    except torch.cuda.OutOfMemoryError:
        raise TrainingStopped("cuda_out_of_memory_during_model_loading") from None
    except Exception:
        raise TrainingStopped("model_loading_failed") from None
    tokens = validate_decoder_tokens(model, processor.tokenizer)
    if config.max_label_length > model.config.decoder.max_position_embeddings:
        raise TrainingInputError("Label limit exceeds decoder capacity.")
    # Do not silently modify pretrained model config; pass shifted decoder inputs.
    encoded = [encode_example(row, train_dir, processor, config.max_label_length) for row in selected]
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    output.mkdir(parents=True, exist_ok=False)
    step, epoch = 0, 0
    status, failure, gate = "running", None, None
    started = time.perf_counter()
    from importlib.metadata import version
    metadata = checkpoint_metadata(bundle, selected, config, 0, status, tokens)
    metadata["environment"] = {"versions": {name: version(name) for name in
                               ("torch", "transformers", "Pillow", "numpy", "sentencepiece", "protobuf")},
                               "gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda,
                               "python": __import__("sys").version.split()[0],
                               "code_sha256": sha256(Path(__file__).read_bytes())}
    (output / "run_config.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    model.train()
    torch.cuda.reset_peak_memory_stats()
    try:
        with (output / "training_log.jsonl").open("x", encoding="utf-8") as log:
            while step < config.max_steps:
                for window in accumulation_windows(32, config.batch_size, config.accumulation_steps, config.seed + epoch):
                    optimizer.zero_grad(set_to_none=True)
                    step_started = time.perf_counter()
                    def compute_loss(indices):
                        pixels = torch.stack([encoded[i]["pixel_values"] for i in indices]).to("cuda")
                        labels = torch.tensor([encoded[i]["labels"] for i in indices], dtype=torch.long, device="cuda")
                        decoder_inputs = labels.new_full(labels.shape, tokens["pad_token_id"])
                        decoder_inputs[:, 0] = tokens["decoder_start_token_id"]
                        decoder_inputs[:, 1:] = labels[:, :-1]
                        decoder_inputs.masked_fill_(decoder_inputs == -100, tokens["pad_token_id"])
                        return model(pixel_values=pixels, labels=labels, decoder_input_ids=decoder_inputs).loss
                    window_loss = backward_window(window, compute_loss)
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm,
                                                         error_if_nonfinite=False)
                    require_finite(norm.item())
                    optimizer.step()
                    step += 1
                    record = {"optimizer_step": step, "epoch_index": epoch, "loss": window_loss,
                              "micro_batches": len(window), "examples": sum(map(len, window)),
                              "step_seconds": time.perf_counter() - step_started, **_gpu_stats(torch)}
                    if step % config.diagnose_every == 0 or step == config.max_steps:
                        gate = memorization_diagnostics(selected, train_dir, processor, model, torch)
                        record["training_memorization"] = gate
                    log.write(json.dumps(record, allow_nan=False) + "\n")
                    log.flush()
                    os.fsync(log.fileno())
                    if step % config.checkpoint_every == 0 or step == config.max_steps:
                        checkpoint = {**metadata, "optimizer_step": step, "status": "checkpoint",
                                      "training_memorization": gate}
                        save_checkpoint(output / f"checkpoint-{step:04}", model, processor, optimizer, torch, checkpoint)
                    if step == config.max_steps:
                        break
                epoch += 1
        status = "completed"
    except KeyboardInterrupt:
        status, failure = "interrupted", "user_interrupt"
    except torch.cuda.OutOfMemoryError:
        status, failure = "stopped", "cuda_out_of_memory"
    except TrainingStopped:
        status, failure = "stopped", "nonfinite_loss_or_gradient"
    except Exception:
        status, failure = "stopped", "training_runtime_error"
    finally:
        optimizer.zero_grad(set_to_none=True)
        report = {"status": status, "failure_category": failure, "optimizer_steps": step,
                  "runtime_seconds": time.perf_counter() - started, "gpu_memory": _gpu_stats(torch),
                  "training_memorization": gate, "full_training_authorized": False,
                  "checkpoint_policy": "Last completed checkpoint only; no automatic resume."}
        (output / "run_status.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # CLI intentionally exposes preflight only. Notebook training is explicit.
    parser.add_argument("command", choices=["preflight"])
    parser.add_argument("--split-manifest", required=True)
    parser.add_argument("--baseline-manifest", required=True)
    parser.add_argument("--train-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(preflight(args.split_manifest, args.baseline_manifest, args.train_dir), indent=2))


if __name__ == "__main__":
    main()
