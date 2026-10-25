"""Streamlit-free controller for milestone 12D:
Upload -> Extract medicines -> Review ten fields -> Confirm -> Explain.

app.py is a thin view over these functions. ``state`` is any mutable mapping
(``st.session_state`` in the app, a plain dict in tests).

Rules this module enforces:
* One AIIntegration per session (ensure_session). It is the only confirmation
  authority; needs_review is data, never proof of confirmation.
* The adapter only ever receives the original ten-field records. Dose quantity
  and unit live in a separate parallel structure and never reach the adapter.
* The extraction (``ai_original_json``) is an immutable JSON string; edits live
  in the editor widget and are re-derived on every run.
* Any edit, new upload or removal invalidates confirmation (UI and adapter).
* Extraction runs only on an explicit analyze()/retry(). Explanation runs only
  after a valid confirmation; switching language never re-extracts.
* Scheduling, reminders, pricing, instructions, investigations and strip OCR
  are not wired here. build_schedule() below always raises.
"""
import copy
import hashlib
import json
import math
import os
from io import BytesIO
from pathlib import Path

import assistant
from ai_integration import AIIntegration, IntegrationError

BASE = Path(__file__).resolve().parent
MOCK_PATH = BASE / "sample_prescriptions" / "mock_prescription.json"
SAMPLE_IMAGE_PATH = BASE / "sample_prescriptions" / "fictional_demo.png"

SCOPE = "medicines"
FIELDS = assistant.FIELDS                      # the ten reader fields, in order
DOSE_FIELDS = ("dose_quantity", "dose_unit")   # separate structure, never sent to the adapter
EDITOR_COLUMNS = FIELDS + DOSE_FIELDS
TEXT_FIELDS = assistant.TEXT_FIELDS
FORM_OPTIONS = ("tablet", "capsule", "syrup", "drops")
LANGUAGES = assistant.LANGUAGES

_DEFAULTS = {
    "ai_adapter": None, "ai_events": None,
    "ai_source": None,            # "upload" | "sample" | None
    "ai_uploader_sha": None,      # last value seen from the file uploader widget
    "ai_image_bytes": None, "ai_image_sha": None,
    "ai_analysis_id": None,
    "ai_status": "idle",          # idle | ready | extracted | failed
    "ai_error": None,             # {"category", "message"}: safe adapter text only
    "ai_original_json": None,     # immutable extraction result
    "ai_generation": 0,           # bumps on each new extraction -> new editor key
    "ai_confirmed_view": None,    # fingerprint of the records+doses the user confirmed
    "ai_explanations": None,      # {language: explanation payload}
}


class FlowError(ValueError):
    """A message that is safe to show the user. Never embeds user or model text."""

    def __init__(self, message, category="invalid_state"):
        super().__init__(message)
        self.message, self.category = message, category


class SliceDisabledError(RuntimeError):
    """Scheduling/refill is intentionally inactive in this integration slice."""


def build_schedule(*args, **kwargs):
    """Legacy schedule entry point. Disabled, including direct calls."""
    raise SliceDisabledError("Scheduling is not active in this integration slice.")


# ---------------------------------------------------------------- session / adapter
def mock_extractor(image_bytes):
    """Offline extractor used when MEDISAATHI_MOCK_AI=1 (demo or tests). No network."""
    records = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    if type(records) is not list:
        raise ValueError("mock prescription must be a list of ten-field records")
    return records


def adapter_factory():
    """The only place an AIIntegration is constructed. Tests may replace it."""
    if os.environ.get("MEDISAATHI_MOCK_AI") == "1":
        return AIIntegration(extractors={SCOPE: mock_extractor})
    return AIIntegration()


def ensure_session(state):
    for key, default in _DEFAULTS.items():
        if key not in state:
            state[key] = default
    if state["ai_adapter"] is None:
        adapter = adapter_factory()
        state["ai_adapter"] = adapter
        state["ai_events"] = adapter.frontend_events()   # server-side capability
    return state["ai_adapter"]


def _fail(state, error):
    state["ai_error"] = {"category": error.category, "message": str(error)}


def _clear_view(state):
    state["ai_analysis_id"] = None
    state["ai_status"] = "idle"
    state["ai_error"] = None
    state["ai_original_json"] = None
    state["ai_generation"] += 1
    state["ai_confirmed_view"] = None
    state["ai_explanations"] = None


def _parked_png():
    from PIL import Image
    with BytesIO() as out:
        with Image.new("RGB", (4, 4), "white") as image:
            image.save(out, format="PNG")
        return out.getvalue()


# ---------------------------------------------------------------- upload
def begin_upload(state, data, source):
    """Start a NEW analysis. Never extracts. Invalidates every old approval/result."""
    adapter = ensure_session(state)
    _clear_view(state)
    state["ai_image_bytes"] = state["ai_image_sha"] = state["ai_source"] = None
    try:
        root = adapter.start_prescription(data)
    except IntegrationError as error:
        _fail(state, error)
        return False
    state["ai_image_bytes"] = data
    state["ai_image_sha"] = hashlib.sha256(data).hexdigest()
    state["ai_source"] = source
    state["ai_analysis_id"] = root["analysis_id"]
    state["ai_status"] = "ready"
    return True


def remove_upload(state):
    """Upload removed: clear the view and invalidate the adapter by parking it on
    a blank analysis (the adapter has no public 'clear'; start_* is the reset)."""
    adapter = ensure_session(state)
    _clear_view(state)
    state["ai_image_bytes"] = state["ai_image_sha"] = state["ai_source"] = None
    try:
        adapter.start_prescription(_parked_png())
    except IntegrationError:
        pass


def sync_upload(state, data):
    """Call every run with the uploader's bytes (or None). Acts only on a change."""
    ensure_session(state)
    current = hashlib.sha256(data).hexdigest() if data is not None else None
    if current == state["ai_uploader_sha"]:
        return
    state["ai_uploader_sha"] = current
    if current is None:
        if state["ai_source"] == "upload":      # a sample is not removed by an empty uploader
            remove_upload(state)
        return
    begin_upload(state, data, "upload")


def load_sample(state):
    ensure_session(state)
    try:
        data = SAMPLE_IMAGE_PATH.read_bytes()
    except OSError:
        _clear_view(state)
        state["ai_error"] = {"category": "invalid_input", "message": "The sample image is not available."}
        return False
    return begin_upload(state, data, "sample")


# ---------------------------------------------------------------- extraction
def _absorb(state):
    adapter = state["ai_adapter"]
    prescription = adapter.snapshot()["prescription"]
    if prescription is None or prescription["analysis_id"] != state["ai_analysis_id"]:
        _fail(state, IntegrationError("stale_result"))
        return
    section = prescription["sections"][SCOPE]
    if section["status"] == "succeeded":
        state["ai_original_json"] = json.dumps(section["payload"], allow_nan=False)
        state["ai_status"] = "extracted"
        state["ai_error"] = None
        state["ai_generation"] += 1
        state["ai_confirmed_view"] = None
        state["ai_explanations"] = None
    elif section["status"] == "failed":
        state["ai_status"] = "failed"
        state["ai_error"] = dict(section["safe_error"])


def analyze(state):
    """Explicit Analyze click: one run_sections(("medicines",)). Idempotent."""
    adapter = ensure_session(state)
    if state["ai_status"] != "ready":
        return
    try:
        adapter.run_sections((SCOPE,), analysis_id=state["ai_analysis_id"])
    except IntegrationError as error:
        _fail(state, error)
        return
    _absorb(state)


def retry(state):
    """Explicit retry of a failed extraction: exactly one more extractor call."""
    adapter = ensure_session(state)
    if state["ai_status"] != "failed":
        return
    try:
        adapter.retry_section(SCOPE, analysis_id=state["ai_analysis_id"])
    except IntegrationError as error:
        _fail(state, error)
        return
    _absorb(state)


def original_records(state):
    return json.loads(state["ai_original_json"])        # fresh copy every time


def baseline_rows(state):
    """Editor starting rows: the ten original fields plus EMPTY dose columns."""
    return [dict(record, dose_quantity=None, dose_unit=None) for record in original_records(state)]


# ---------------------------------------------------------------- review
def _missing(value):
    if value is None or (isinstance(value, float) and value != value):
        return True
    return type(value).__name__ in ("NAType", "NaTType")


def _plain(value):
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()          # representation only: np.int64 -> int, np.bool_ -> bool
    return value


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def frame_to_state(rows, unit_options):
    """Validate the WHOLE edited table. Returns (records, doses, errors).

    Nulls stay null; nothing is guessed or coerced (a whole-number float such as
    5.0 becomes 5 only for duration_days, because the editor stores it that way).
    On any error, records/doses are empty and errors lists safe messages that
    never echo cell contents."""
    units, records, doses, errors = tuple(unit_options), [], [], []
    for n, row in enumerate(rows, start=1):
        bad = []
        if not isinstance(row, dict) or any(c not in row for c in EDITOR_COLUMNS):
            errors.append(f"Row {n}: a column is missing.")
            continue
        record = {}
        for field in FIELDS:
            value = _plain(row[field])
            if field in TEXT_FIELDS:
                if _missing(value):
                    value = None
                elif type(value) is not str or not value.strip():
                    bad.append(f"{field} must be text or left blank")
                elif field == "form" and value not in FORM_OPTIONS:
                    bad.append("form must be tablet, capsule, syrup, drops or blank")
            elif field == "duration_days":
                if _missing(value):
                    value = None
                elif type(value) is float and value.is_integer():
                    value = int(value)
                if value is not None and (type(value) is not int or value < 1):
                    bad.append("duration_days must be a whole number of days (1 or more) or blank")
            elif field == "confidence":
                if _missing(value):
                    value = None
                elif not _number(value) or not 0 <= value <= 1:
                    bad.append("confidence must be between 0 and 1 or blank")
            elif field == "needs_review":
                if type(value) is not bool:
                    bad.append("needs_review must be ticked or unticked")
            record[field] = value
        quantity, unit = _plain(row["dose_quantity"]), _plain(row["dose_unit"])
        quantity = None if _missing(quantity) else quantity
        unit = None if _missing(unit) else unit
        if quantity is not None and (not _number(quantity) or quantity < 0):
            bad.append("dose_quantity must be a number of 0 or more, or blank")
        if unit is not None and unit not in units:
            bad.append("dose_unit must be one of the listed units or blank")
        errors.extend(f"Row {n}: {message}." for message in bad)
        records.append(record)
        doses.append({"dose_quantity": quantity, "dose_unit": unit})
    if not errors:
        try:
            assistant.records_fingerprint(records)
        except assistant.AssistantInputError:
            errors.append("The edited list does not satisfy the prescription record contract.")
    return ([], [], errors) if errors else (records, doses, [])


def current_view(records, doses, errors):
    """Fingerprint of exactly what the user sees (records AND separate doses)."""
    if errors:
        return None
    text = json.dumps({"records": records, "doses": doses}, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def needs_acknowledgement(records):
    """Unknown (null) values or rows still flagged needs_review need an explicit tick."""
    return any(r[f] is None for r in records for f in FIELDS) or any(r["needs_review"] for r in records)


def sync_review(state, records, doses, errors):
    """Call every run with the current editor contents. If anything changed since
    the user confirmed, drop the confirmation in the UI and in the adapter."""
    if state["ai_confirmed_view"] is None:
        return False
    if current_view(records, doses, errors) == state["ai_confirmed_view"]:
        return False
    state["ai_confirmed_view"] = None
    state["ai_explanations"] = None
    adapter = ensure_session(state)
    try:
        adapter.review(SCOPE, [None])            # always invalid -> adapter drops confirmation
    except IntegrationError:
        pass
    if not errors:
        try:
            adapter.review(SCOPE, records)       # keep the adapter's reviewed snapshot current
        except IntegrationError:
            pass
    return True


def confirm(state, records, doses, errors, *, unknowns_acknowledged):
    """Genuine user confirmation. Call ONLY from a button handler."""
    adapter = ensure_session(state)
    if state["ai_status"] != "extracted":
        raise FlowError("There is nothing to confirm yet.")
    if errors:
        raise FlowError("Fix the problems listed above before confirming.", "invalid_input")
    if needs_acknowledgement(records) and not unknowns_acknowledged:
        raise FlowError("Tick the box to say you checked the blank or unclear values.",
                        "confirmation_required")
    try:
        adapter.review(SCOPE, records)                       # the exact ten-field records only
        event = state["ai_events"].register_acknowledgement(SCOPE)   # one-use token
        adapter.confirm(SCOPE, event=event)
    except IntegrationError as error:
        raise FlowError(str(error), error.category) from None
    state["ai_confirmed_view"] = current_view(records, doses, errors)
    state["ai_explanations"] = {}


def is_confirmed(state, view):
    if view is None or state["ai_confirmed_view"] != view or state["ai_adapter"] is None:
        return False
    return SCOPE in state["ai_adapter"].snapshot()["confirmed_scopes"]


def get_explanation(state, view, language):
    """adapter.explain only after valid confirmation; cached so a language switch
    never re-extracts and does not repeat identical explain calls."""
    if language not in LANGUAGES:
        raise FlowError("Choose English, Hindi or Hinglish.", "invalid_input")
    if not is_confirmed(state, view):
        raise FlowError("Confirm your medicines first.", "confirmation_required")
    cache = state["ai_explanations"]
    if cache is None:
        cache = state["ai_explanations"] = {}
    if language not in cache:
        try:
            cache[language] = state["ai_adapter"].explain(language=language)["payload"]
        except IntegrationError as error:
            raise FlowError(str(error), error.category) from None
    return copy.deepcopy(cache[language])
