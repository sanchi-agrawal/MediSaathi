"""Explicit mock/live loopback smoke runner. No extraction during startup.

Live mode uses real reader.read_prescription with a persistent one-attempt guard.
Only the verified fictional fixture (including lossless PNG re-encoding) is allowed.
Keys are loaded into the Python process only. No mock fallback exists in live mode.
"""
import argparse
import hashlib
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import threading
import time

from dotenv import dotenv_values
from PIL import Image
import uvicorn

from api.dependencies import AIIntegration, IntegrationError, reader
from api.main import create_app, fail
from api.smoke.diagnostics import safe_failure_diagnostics
from api.smoke.persistence import persist_result

ROOT = Path(__file__).resolve().parent


def pixel_identity(data):
    # Keep actual decode/byte/pixel/frame validation authoritative and unchanged.
    reader._validate_image(data)
    with Image.open(BytesIO(data)) as image:
        image.load()
        rgb = image.convert("RGBA")
        return image.size, hashlib.sha256(rgb.tobytes()).hexdigest()


def fixture_validator(fixture):
    expected = pixel_identity(fixture)

    def validate(data):
        # Pixel identity permits changed PNG compression/metadata, not changed
        # medical content. A mismatch is a smoke policy rejection, not bad PNG.
        try:
            actual = pixel_identity(data)
        except reader.ImageInputError:
            raise IntegrationError("image_validation_error") from None
        if actual != expected:
            fail(422, "smoke_fixture_required",
                 "This controlled smoke test accepts only api/smoke/fictional_demo.png "
                 "or a lossless copy with identical pixels. Select that fictional PNG.")
    return validate


def load_credentials(path=None):
    values = dotenv_values(path) if path else {}
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL"):
        if not os.getenv(name) and values.get(name):
            os.environ[name] = values[name]
    key, model = reader._configuration()
    return bool(key), model


def create_smoke_app(mode, *, fixture=None, result_path=None):
    fixture = (ROOT / "fictional_demo.png").read_bytes() if fixture is None else fixture
    result_path = ROOT / "live_result.json" if result_path is None else Path(result_path)
    validate_fixture = fixture_validator(fixture)
    if mode not in ("mock", "live"):
        raise ValueError("Use explicit mock or live mode")
    if mode == "live" and result_path.exists():
        raise RuntimeError("A live attempt is already recorded. No additional extraction allowed.")
    lock = threading.Lock()
    used = False

    def extract(data):
        nonlocal used
        # Defense in depth: validated again even when called outside HTTP.
        validate_fixture(data)
        if mode == "mock":
            return [dict(raw_text="Tab Dolo 650 1-0-1 x 5 days After food", name="Dolo",
                         salt=None, strength="650", form="tablet", frequency_pattern="1-0-1",
                         duration_days=5, timing="After food", confidence=None, needs_review=True)]
        with lock:
            if used:
                raise reader.ReaderConfigurationError("The one live extraction allowance is consumed.")
            used = True
            # Exclusive creation also prevents a second process consuming the same
            # allowance. Reserve before reader entry, including on failed attempts.
            try:
                with result_path.open("x", encoding="utf-8") as marker:
                    json.dump({"mode":"live", "status":"started", "extractor_invocations":1}, marker)
                    marker.flush()
                    os.fsync(marker.fileno())
            except FileExistsError:
                raise reader.ReaderConfigurationError("The one live extraction allowance is consumed.") from None
        started = time.perf_counter()
        report = {"mode":"live", "extractor_invocations":1,
                  "uploaded_sha256":hashlib.sha256(data).hexdigest()}
        try:
            records = reader.read_prescription(data)
            report.update(status="succeeded", records=records,
                          unexpected_fields=[sorted(set(r)-set(reader.FIELDS)) for r in records],
                          null_fields=[sorted(k for k,v in r.items() if v is None) for r in records],
                          review_flags=[r["needs_review"] for r in records])
            return records
        except Exception as error:
            diagnostics = safe_failure_diagnostics(error)
            report.update(status="failed", error_type=diagnostics["exception_type"],
                          diagnostics=diagnostics)
            # No str(error), traceback, response body, headers, cookies, or key.
            logging.getLogger(__name__).warning("Live OCR failure diagnostics: %s",
                                               json.dumps(diagnostics,sort_keys=True))
            raise
        finally:
            report["latency_seconds"] = round(time.perf_counter()-started,3)
            persist_result(result_path,report)
            print("Live smoke attempt completed:",report["status"],report["latency_seconds"],
                  "seconds; allowance consumed",flush=True)

    app = create_app(factory=lambda: AIIntegration(extractors={"medicines":extract}),
                     upload_validator=validate_fixture,enabled_sections=("medicines",))

    @app.get("/api/smoke/status")
    def smoke_status():
        configured = False
        model = None
        if mode == "live":
            try:
                configured, model = load_credentials()
            except reader.ReaderConfigurationError:
                pass
        return {"mode":mode, "gemini_configured":configured, "model":model,
                "live_attempt_available":mode == "live" and not used and not result_path.exists(),
                "fixture":"api/smoke/fictional_demo.png", "automatic_api_retry":False}

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("mock", "live"), required=True)
    parser.add_argument("--credentials-file", type=Path)
    args = parser.parse_args()
    if args.mode == "live":
        present, model = load_credentials(args.credentials_file)
        print("Server configuration loaded: key present =",present,"model =",model,flush=True)
    app = create_smoke_app(args.mode)
    print("SMOKE MODE:",args.mode,"- loopback only; real session/review/confirmation logic",flush=True)
    uvicorn.run(app,host="127.0.0.1",port=8000,access_log=False)


if __name__ == "__main__":
    main()
