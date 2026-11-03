"""Numeric-only OCR performance metadata. Never receives medical records."""
import logging
import math
from time import perf_counter

from .dependencies import reader

PHASES = {"image_validation_ms", "configuration_ms", "client_setup_ms",
          "gemini_request_ms", "normalization_ms"}
COUNTERS = {"gemini_sdk_invocations", "malformed_response_retries"}


class Measurements:
    def __init__(self):
        self.values = {name: 0 for name in PHASES | COUNTERS}

    def record(self, name, value):
        if (name not in PHASES | COUNTERS | {"provider_http_requests"} or type(value) not in (int, float)
                or not math.isfinite(value) or value < 0):
            return
        self.values[name] = self.values.get(name, 0) + value

    def snapshot(self):
        return {key: round(value, 3) for key, value in self.values.items()}

    def scope(self):
        return reader._timing_scope(self.record)


def elapsed_ms(started):
    return round((perf_counter() - started) * 1000, 3)


def log_metrics(stage, values):
    # Emit only known technical fields, never identifiers, filenames, model
    # output, errors, image hashes, request headers, session IDs or records.
    if stage not in ("upload", "extraction", "duplicate_rejected"):
        return
    allowed = PHASES | COUNTERS | {"provider_http_requests", "upload_ms", "server_extraction_ms", "server_processing_ms",
        "upload_validation_ms", "image_bytes", "image_width", "image_height",
        "duplicate_analysis_rejections", "analysis_attempts", "total_gemini_sdk_invocations"}
    safe = {k: v for k, v in values.items() if k in allowed
            and type(v) in (int, float) and math.isfinite(v) and v >= 0}
    logging.getLogger(__name__).info("OCR performance %s %s", stage, safe)
