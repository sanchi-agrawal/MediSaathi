"""Session-local AI orchestration and guarded handoffs. No Streamlit dependency.

Construct one AIIntegration per trusted frontend session. Construction, snapshot,
review and explanation do not request extraction. Only run_sections, retry_section
and execute call the selected injected/default extractor. Never cache this object
globally across users. Public snapshots are copies, not writable authority.

FrontendEvents is a SERVER-SIDE capability: keep it out of HTTP input/session JSON.
Its register_* methods must only run in genuine user-event handlers after review.
No Python library can prove a physical click or defend against malicious code
holding that capability. One-use opaque tokens bind those trusted registrations;
booleans, caller fingerprints and model flags cannot authorize a handoff.

Only simple decimal doses, literal English named slots and integer day durations
are eligible for the provisional schedule handoff. Fractions, ranges, tapers,
OD/PRN, unresolved conflicts and clock-to-slot conversion are deliberately blocked.
Actual arithmetic belongs to Person 3. Downstream callables are trusted project
functions, not arbitrary user code. No expiry status or safety claim is computed.
extractor_invocations counts Python extractor invocations, NOT Gemini requests.
"""
import copy
import hashlib
import json
import math
import re
import threading
import uuid
from datetime import date
from decimal import Decimal

import assistant
import investigations
import medication_instructions as medication
import reader
import strip

SECTIONS = ("medicines", "instructions", "investigations")
SCOPES = SECTIONS + ("strip",)
SCHEMA_VERSION = "ai-integration-v1"
SCHEMAS = {"medicines": "reader-ten-fields-v1", "instructions": medication.SCHEMA_VERSION,
           "investigations": investigations.SCHEMA_VERSION, "strip": strip.SCHEMA_VERSION}
MESSAGES = {
    "invalid_input": "The integration input is invalid.",
    "invalid_state": "This action is not available in the current state.",
    "stale_result": "The source or reviewed information changed. Review the current analysis again.",
    "confirmation_required": "Explicit current user confirmation is required.",
    "association_required": "Explicit current medicine-to-instruction association is required.",
    "unsafe_schedule": "Scheduling needs explicit, valid and consistent dose, unit, duration and slots.",
    "ambiguous_order": "Clarify the prescribed investigation and variant before pricing.",
    "unavailable": "This teammate integration is not configured.",
    "downstream_error": "The requested teammate operation could not complete.",
    "image_validation_error": "Use a valid single-frame PNG/JPEG within the existing image limits.",
    "configuration_error": "Configure the local Gemini key and model before extraction.",
    "quota_or_rate_limit": "The extraction quota or rate limit was reached. No automatic retry was made.",
    "network_error": "The extraction service could not be reached. No automatic retry was made.",
    "api_error": "The extraction service could not complete this section.",
    "invalid_response": "The extraction response did not satisfy its expected contract.",
    "unexpected_error": "This extraction section could not complete.",
}
_UNSAFE_INSTRUCTIONS = {
    "blurred", "clipped", "unreadable", "unclear_medicine_association", "ambiguous_dose",
    "variable_dose", "tapering_instruction", "conflicting_source_text", "unsupported_source_value",
    "dose_not_explicit", "duplicate_instruction", "repeated_medicine", "conflicting_instructions",
    "missing_source_text", "duration_range", "frequency_requires_clarification",
    "variable_or_tapering_instruction",
}
_UNSAFE_ORDERS = {"blurred", "clipped", "unreadable", "ordering_unclear", "variant_unclear",
                  "conflicting_source_text", "unsupported_source_value", "duplicate_entry",
                  "repeated_test_name", "potentially_conflicting_entries", "conflicting_order_mentions"}


class IntegrationError(ValueError):
    """Safe public category/message; never embeds supplied values or exceptions."""

    def __init__(self, category):
        self.category = category
        super().__init__(MESSAGES[category])


def _json_value(value, *, allow_dates=False):
    if allow_dates and type(value) is date:
        return
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item, allow_dates=allow_dates)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item, allow_dates=allow_dates)
        return
    raise IntegrationError("invalid_input")


def _fingerprint(value):
    try:
        _json_value(value)
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise IntegrationError("invalid_input") from None


def _codes(value):
    return (type(value) is list and all(type(v) is str and bool(v.strip()) for v in value)
            and len(set(value)) == len(value))


def _text(value):
    return value is None or (type(value) is str and bool(value.strip()))


def _validate(scope, payload, image_hash):
    """Validate FINAL module contracts without re-normalizing or repairing data."""
    _fingerprint(payload)
    if scope == "medicines":
        try:
            assistant.records_fingerprint(payload)
        except assistant.AssistantInputError:
            raise IntegrationError("invalid_input") from None
        return
    if scope in ("instructions", "investigations"):
        name = "instructions" if scope == "instructions" else "investigations"
        fields = medication.INSTRUCTION_FIELDS if scope == "instructions" else investigations.INVESTIGATION_FIELDS
        text_fields = medication.TEXT_FIELDS if scope == "instructions" else investigations.TEXT_FIELDS
        identity = "instruction_id" if scope == "instructions" else "investigation_id"
        if (type(payload) is not dict or set(payload) != {
                "schema_version", "source_image_sha256", name, "issues", "confirmation_required"}
                or payload["schema_version"] != SCHEMAS[scope]
                or payload["source_image_sha256"] != image_hash
                or payload["confirmation_required"] is not True
                or not _codes(payload["issues"]) or type(payload[name]) is not list):
            raise IntegrationError("invalid_input")
        ids = set()
        for item in payload[name]:
            if (type(item) is not dict or set(item) != fields
                    or any(not _text(item[field]) for field in text_fields)
                    or type(item[identity]) is not str or not item[identity].strip()
                    or item[identity] in ids or type(item["needs_review"]) is not bool
                    or item["confirmation_required"] is not True or not _codes(item["uncertainty_reasons"])):
                raise IntegrationError("invalid_input")
            ids.add(item[identity])
        return
    expected = {"schema_version", "medicine_name", "batch_number", "product_association",
                "raw_expiry_text", "expiry", "confidence", "confidence_kind", "needs_review",
                "issues", "date_observations", "confirmation_required"}
    if (type(payload) is not dict or set(payload) != expected or payload["schema_version"] != SCHEMAS[scope]
            or payload["confirmation_required"] is not True or type(payload["needs_review"]) is not bool
            or not _codes(payload["issues"]) or type(payload["date_observations"]) is not list
            or payload["product_association"] not in ("single_product", "multiple_products", "unclear")
            or any(not _text(payload[k]) for k in ("medicine_name", "batch_number", "raw_expiry_text"))
            or payload["confidence_kind"] != "uncalibrated"):
        raise IntegrationError("invalid_input")
    confidence = payload["confidence"]
    if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
        raise IntegrationError("invalid_input")
    expiry = payload["expiry"]
    if expiry is not None:
        try:
            if type(expiry) is not dict or set(expiry) != {"year", "month", "day", "precision", "iso"}:
                raise ValueError
            if type(expiry["year"]) is not int or type(expiry["month"]) is not int:
                raise ValueError
            if expiry["precision"] == "month" and expiry["day"] is None:
                date(expiry["year"], expiry["month"], 1)  # validation only; no expiry day is inferred
                expected_iso = f'{expiry["year"]:04}-{expiry["month"]:02}'
            elif expiry["precision"] == "day" and type(expiry["day"]) is int:
                expected_iso = date(expiry["year"], expiry["month"], expiry["day"]).isoformat()
            else:
                raise ValueError
            if expiry["iso"] != expected_iso:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise IntegrationError("invalid_input") from None
    for item in payload["date_observations"]:
        fields = {"raw_label", "raw_date_text", "raw_text", "association", "confidence",
                  "uncertain", "label_kind", "parsed_date", "parse_issues"}
        if (type(item) is not dict or set(item) != fields
                or any(not _text(item[k]) for k in ("raw_label", "raw_date_text", "raw_text"))
                or item["association"] not in ("same_product", "unclear")
                or type(item["uncertain"]) is not bool
                or item["label_kind"] not in ("expiry", "manufacturing", "batch", "use_before", "unknown")
                or not _codes(item["parse_issues"])):
            raise IntegrationError("invalid_input")
        confidence = item["confidence"]
        if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
            raise IntegrationError("invalid_input")
        if item["parsed_date"] is not None:
            # Public parser checks date shape/calendar without calculating status.
            parsed = strip.parse_expiry_text(item["raw_date_text"]) if item["raw_date_text"] else {"expiry": None}
            if item["parsed_date"] != parsed["expiry"]:
                raise IntegrationError("invalid_input")
    if expiry is not None:
        observations = [item for item in payload["date_observations"] if item["label_kind"] == "expiry"]
        if (payload["product_association"] != "single_product" or not observations
                or any(item["association"] != "same_product" or item["parsed_date"] != expiry
                       for item in observations)):
            raise IntegrationError("invalid_input")


def _safe_error(error):
    mappings = (
        ((reader.ReaderConfigurationError, medication.MedicationConfigurationError,
          investigations.InvestigationConfigurationError, strip.StripConfigurationError), "configuration_error"),
        ((medication.MedicationQuotaError, investigations.InvestigationQuotaError, strip.StripQuotaError), "quota_or_rate_limit"),
        ((medication.MedicationNetworkError, investigations.InvestigationNetworkError, strip.StripNetworkError), "network_error"),
        ((reader.ImageInputError, medication.MedicationImageError, investigations.InvestigationImageError, strip.StripImageError), "image_validation_error"),
        ((reader.ModelResponseError, medication.MedicationResponseError,
          investigations.InvestigationResponseError, strip.StripResponseError), "invalid_response"),
        ((reader.PrescriptionAPIError, medication.MedicationAPIError,
          investigations.InvestigationAPIError, strip.StripAPIError), "api_error"),
    )
    category = next((name for classes, name in mappings if isinstance(error, classes)), "unexpected_error")
    if isinstance(error, IntegrationError):
        category = "invalid_response"
    return {"category": category, "message": MESSAGES[category]}


class FrontendEvents:
    """Trusted server capability; NEVER expose this registrar to model/client data."""

    def __init__(self, adapter):
        self._adapter = adapter

    def register_acknowledgement(self, scope):
        return self._adapter._register("confirm", scope, None)

    def register_association(self, medicine_ref, instruction_id):
        return self._adapter._register("associate", "instructions", [medicine_ref, instruction_id])

    def register_schedule_approval(self, link_id, plan):
        return self._adapter._register("schedule", "instructions", [link_id, plan])


class AIIntegration:
    """Private session state is authority; snapshot() returns display-only copies."""

    def __init__(self, *, extractors=None, downstream=None):
        self._lock = threading.RLock()
        self._extractors = {"medicines": reader.read_prescription,
            "instructions": medication.read_medication_instructions,
            "investigations": investigations.read_prescribed_investigations, "strip": strip.read_strip}
        self._downstream = {"explain": assistant.explain_prescription}
        for supplied, target in ((extractors, self._extractors), (downstream, self._downstream)):
            if supplied is not None:
                allowed = set(SCOPES) if target is self._extractors else {
                    "explain", "schedule", "medicine_matching", "medicine_pricing", "lab_pricing", "reminders"}
                if type(supplied) is not dict or any(k not in allowed or not callable(v) for k, v in supplied.items()):
                    raise IntegrationError("invalid_input")
                target.update(supplied)
        self._prescription = self._strip = None
        self._images, self._events, self._jobs = {}, {}, {}
        self._executing = set()
        self._confirmations, self._links, self._derived = {}, {}, {}
        self._plan_epochs = {}

    def frontend_events(self):
        """Give this capability only to trusted application event handlers."""
        return FrontendEvents(self)

    def _root(self, scope):
        if scope not in SCOPES:
            raise IntegrationError("invalid_input")
        root = self._strip if scope == "strip" else self._prescription
        if root is None:
            raise IntegrationError("invalid_state")
        return root

    def _section(self, scope):
        return self._root(scope)["sections"][scope]

    def _invalidate(self, scope):
        self._confirmations.pop(scope, None)
        for token, receipt in list(self._events.items()):
            if receipt[1] == scope or (receipt[0] != "confirm" and scope in ("medicines", "instructions")):
                del self._events[token]
        if scope in ("medicines", "instructions"):
            self._links.clear()
            self._plan_epochs.clear()
        for key, item in list(self._derived.items()):
            if scope in item["scopes"] or (scope in ("medicines", "instructions") and item["purpose"] == "reminders"):
                del self._derived[key]

    def _start(self, kind, image_bytes):
        scopes = ("strip",) if kind == "strip" else SECTIONS
        with self._lock:
            for scope in scopes:
                self._invalidate(scope)
            if kind == "strip":
                self._strip = None
            else:
                self._prescription = None
            self._images.pop(kind, None)
            try:
                reader._validate_image(image_bytes)
            except reader.ImageInputError:
                raise IntegrationError("image_validation_error") from None
            root = {"schema_version": SCHEMA_VERSION, "analysis_id": uuid.uuid4().hex,
                "source_image_sha256": hashlib.sha256(image_bytes).hexdigest(), "stop_reason": None,
                "sections": {scope: {"status": "not_requested", "payload": None, "reviewed": None,
                                      "safe_error": None, "extractor_invocations": 0} for scope in scopes}}
            self._images[kind] = image_bytes
            if kind == "strip":
                self._strip = root
            else:
                self._prescription = root
            # Old jobs may finish, but can never attach to the new analysis.
            return copy.deepcopy(root)

    def start_prescription(self, image_bytes):
        return self._start("prescription", image_bytes)

    def start_strip(self, image_bytes):
        return self._start("strip", image_bytes)

    def snapshot(self):
        with self._lock:
            return copy.deepcopy({"prescription": self._prescription, "strip": self._strip,
                "confirmed_scopes": sorted(self._confirmations), "associations": self._links,
                "derived": {k: v["payload"] for k, v in self._derived.items()}})

    def begin_section(self, scope, *, analysis_id, retry=False):
        """Return an opaque job for server-side execution; does not extract."""
        with self._lock:
            root, section = self._root(scope), self._section(scope)
            if root["analysis_id"] != analysis_id:
                raise IntegrationError("stale_result")
            expected = "failed" if retry else "not_requested"
            if section["status"] != expected:
                raise IntegrationError("invalid_state")
            self._invalidate(scope)
            section.update(status="running", payload=None, reviewed=None, safe_error=None)
            root["stop_reason"] = None
            job = object()
            self._jobs[job] = (scope, analysis_id, self._images["strip" if scope == "strip" else "prescription"])
            return job

    def _job(self, job):
        if type(job) is not object or job not in self._jobs:
            raise IntegrationError("invalid_input")
        scope, analysis_id, data = self._jobs[job]
        root = self._strip if scope == "strip" else self._prescription
        if root is None or root["analysis_id"] != analysis_id or self._section(scope)["status"] != "running":
            self._jobs.pop(job, None)
            self._executing.discard(job)
            raise IntegrationError("stale_result")
        return scope, analysis_id, data

    def complete_section(self, job, *, payload=None, error=None):
        """Trusted server callback; stale/foreign/completed jobs are rejected."""
        with self._lock:
            scope, _, _ = self._job(job)
            section, root = self._section(scope), self._root(scope)
            if error is None:
                try:
                    _validate(scope, payload, root["source_image_sha256"])
                except IntegrationError as invalid:
                    error = invalid
            self._jobs.pop(job)
            self._executing.discard(job)
            if error is not None:
                section.update(status="failed", payload=None, reviewed=None, safe_error=_safe_error(error))
                if section["safe_error"]["category"] in ("configuration_error", "quota_or_rate_limit"):
                    root["stop_reason"] = section["safe_error"]["category"]
            else:
                section.update(status="succeeded", payload=copy.deepcopy(payload),
                               reviewed=copy.deepcopy(payload), safe_error=None)
            return copy.deepcopy(section)

    def execute(self, job):
        with self._lock:
            scope, _, data = self._job(job)
            if job in self._executing:
                raise IntegrationError("invalid_state")
            self._executing.add(job)
            self._section(scope)["extractor_invocations"] += 1
        try:
            payload = self._extractors[scope](data)
        except Exception as error:
            return self.complete_section(job, error=error)
        return self.complete_section(job, payload=payload)

    def run_sections(self, sections, *, analysis_id):
        """Explicit sequential extraction. Never re-extract succeeded/failed sections."""
        if (type(sections) not in (tuple, list) or not sections
                or any(type(s) is not str or s not in SCOPES for s in sections)
                or len(set(sections)) != len(sections) or ("strip" in sections and len(sections) != 1)):
            raise IntegrationError("invalid_input")
        for scope in sections:
            with self._lock:
                if self._root(scope)["analysis_id"] != analysis_id:
                    raise IntegrationError("stale_result")
                status = self._section(scope)["status"]
            if status in ("succeeded", "failed"):
                continue
            result = self.execute(self.begin_section(scope, analysis_id=analysis_id))
            if result["safe_error"] and result["safe_error"]["category"] in ("configuration_error", "quota_or_rate_limit"):
                with self._lock:
                    self._root(scope)["stop_reason"] = result["safe_error"]["category"]
                break
        return self.snapshot()

    def retry_section(self, scope, *, analysis_id):
        """One explicit extractor invocation; successful sections are preserved."""
        return self.execute(self.begin_section(scope, analysis_id=analysis_id, retry=True))

    def review(self, scope, payload):
        with self._lock:
            root, section = self._root(scope), self._section(scope)
            if section["status"] != "succeeded":
                raise IntegrationError("invalid_state")
            try:
                _validate(scope, payload, root["source_image_sha256"])
            except IntegrationError:
                self._invalidate(scope)
                raise
            if _fingerprint(payload) != _fingerprint(section["reviewed"]):
                self._invalidate(scope)
                section["reviewed"] = copy.deepcopy(payload)
            return copy.deepcopy(section["reviewed"])

    def _binding(self, scope):
        root, section = self._root(scope), self._section(scope)
        if section["status"] != "succeeded":
            raise IntegrationError("invalid_state")
        return _fingerprint({"analysis_id": root["analysis_id"], "source": root["source_image_sha256"],
                             "schema": SCHEMAS[scope], "reviewed": section["reviewed"]})

    def _pair_binding(self):
        return [self._binding("medicines"), self._binding("instructions")]

    def _register(self, purpose, scope, data):
        with self._lock:
            binding = self._binding(scope) if purpose == "confirm" else self._pair_binding()
            token = object()
            self._events[token] = (purpose, scope, binding, _fingerprint(data))
            return token

    def _consume(self, event, purpose, scope, data):
        if type(event) is not object or event not in self._events:
            raise IntegrationError("confirmation_required")
        receipt = self._events.pop(event)
        binding = self._binding(scope) if purpose == "confirm" else self._pair_binding()
        if receipt != (purpose, scope, binding, _fingerprint(data)):
            raise IntegrationError("confirmation_required")

    def confirm(self, scope, *, event):
        with self._lock:
            self._consume(event, "confirm", scope, None)
            self._confirmations[scope] = self._binding(scope)

    def _require(self, scope):
        if self._confirmations.get(scope) != self._binding(scope):
            raise IntegrationError("confirmation_required")
        return self._section(scope)["reviewed"]

    def _handoff(self, scope):
        payload = self._require(scope)
        root = self._root(scope)
        return {"schema_version": SCHEMAS[scope], "analysis_id": root["analysis_id"],
                "source_image_sha256": root["source_image_sha256"],
                "reviewed_fingerprint": _fingerprint(payload), "payload": copy.deepcopy(payload)}

    def _call(self, purpose, scopes, request, *, expected, kwargs=None, link_id=None, derived_id=None, plan_epoch=None):
        with self._lock:
            bindings = {scope: self._binding(scope) for scope in scopes}
            if bindings != expected or (link_id is not None and link_id not in self._links) or (
                    derived_id is not None and derived_id not in self._derived) or (
                    plan_epoch is not None and self._plan_epochs.get(link_id) != plan_epoch):
                raise IntegrationError("stale_result")
            for scope in scopes:
                self._require(scope)
            function = self._downstream.get(purpose)
            if function is None:
                raise IntegrationError("unavailable")
        try:
            result = function(copy.deepcopy(request), **copy.deepcopy(kwargs or {}))
            _json_value(result, allow_dates=True)
        except Exception:
            raise IntegrationError("downstream_error") from None
        with self._lock:
            if (link_id is not None and link_id not in self._links) or (
                    derived_id is not None and derived_id not in self._derived) or (
                    plan_epoch is not None and self._plan_epochs.get(link_id) != plan_epoch):
                raise IntegrationError("stale_result")
            for scope, binding in bindings.items():
                if self._binding(scope) != binding or self._confirmations.get(scope) != binding:
                    raise IntegrationError("stale_result")
            identity = uuid.uuid4().hex
            self._derived[identity] = {"purpose": purpose, "scopes": scopes,
                                      "payload": copy.deepcopy(result), "bindings": bindings,
                                      "link_id": link_id, "plan_epoch": plan_epoch,
                                      "schedule_context": copy.deepcopy(request) if purpose == "schedule" else None}
            return {"derived_id": identity, "payload": copy.deepcopy(result)}

    def explain(self, *, language="en"):
        with self._lock:
            records = copy.deepcopy(self._require("medicines"))
            if language not in assistant.LANGUAGES or type(language) is not str:
                raise IntegrationError("invalid_input")
            metadata = {"acknowledged": True, "records_fingerprint": assistant.records_fingerprint(records),
                        "confirmed_fields": [list(assistant.FIELDS) for _ in records]}
            expected = {"medicines": self._binding("medicines")}
        return self._call("explain", ("medicines",), records,
                          expected=expected, kwargs={"confirmation": metadata, "language": language})

    def match_medicines(self):
        with self._lock:
            request = self._handoff("medicines")
            if any(record["name"] is None for record in request["payload"]):
                raise IntegrationError("invalid_input")
            expected = {"medicines": self._binding("medicines")}
        return self._call("medicine_matching", ("medicines",), request, expected=expected)

    def price_investigations(self):
        with self._lock:
            request = self._handoff("investigations")
            payload = request["payload"]
            if any(code in _UNSAFE_ORDERS for code in payload["issues"]):
                raise IntegrationError("ambiguous_order")
            names = []
            for item in payload["investigations"]:
                if (not all(item[k] for k in ("test_name_raw", "raw_text", "order_context_raw", "variant_raw"))
                        or set(item["uncertainty_reasons"]) & _UNSAFE_ORDERS):
                    raise IntegrationError("ambiguous_order")
                # Recheck source semantics through the existing OFFLINE normalizer.
                # Never store/merge its normalized values into reviewed snapshots.
                model_item = {field: item[field] for field in investigations.TEXT_FIELDS}
                model_item.update(order_status="ordered", uncertainty_reasons=[], needs_review=False)
                checked = investigations.normalize_investigations_response(
                    {"investigations": [model_item], "issues": []},
                    source_image_sha256=request["source_image_sha256"])["investigations"]
                if (len(checked) != 1 or set(checked[0]["uncertainty_reasons"]) & _UNSAFE_ORDERS
                        or any(checked[0][field] != item[field] for field in investigations.TEXT_FIELDS)):
                    raise IntegrationError("ambiguous_order")
                names.append(item["test_name_raw"])
            if len(set(names)) != len(names):
                raise IntegrationError("ambiguous_order")
            expected = {"investigations": self._binding("investigations")}
        return self._call("lab_pricing", ("investigations",), request, expected=expected)

    def confirmed_strip(self):
        with self._lock:
            return copy.deepcopy(self._handoff("strip"))

    def associate(self, medicine_ref, instruction_id, *, event):
        with self._lock:
            meds, instructions = self._require("medicines"), self._require("instructions")["instructions"]
            refs = {f"medicine_{i:03}": i - 1 for i in range(1, len(meds) + 1)}
            if type(medicine_ref) is not str or medicine_ref not in refs or not any(
                    item["instruction_id"] == instruction_id for item in instructions):
                raise IntegrationError("association_required")
            self._consume(event, "associate", "instructions", [medicine_ref, instruction_id])
            for identity, link in list(self._links.items()):
                if link["medicine_ref"] == medicine_ref or link["instruction_id"] == instruction_id:
                    del self._links[identity]
            # Association changes invalidate every derived schedule/reminder, not text confirmation.
            self._plan_epochs.clear()
            for identity, value in list(self._derived.items()):
                if value["purpose"] in ("schedule", "reminders", "medicine_pricing"):
                    del self._derived[identity]
            for token, receipt in list(self._events.items()):
                if receipt[0] in ("associate", "schedule"):
                    del self._events[token]
            identity = uuid.uuid4().hex
            self._links[identity] = {"medicine_ref": medicine_ref, "medicine_index": refs[medicine_ref],
                "instruction_id": instruction_id, "bindings": self._pair_binding()}
            return identity

    def clear_associations(self):
        """Trusted UI calls this when its association selection is cleared/changed."""
        with self._lock:
            self._links.clear()
            self._plan_epochs.clear()
            for key, result in list(self._derived.items()):
                if result["purpose"] in ("schedule", "reminders", "medicine_pricing"):
                    del self._derived[key]
            for token, receipt in list(self._events.items()):
                if receipt[0] in ("associate", "schedule"):
                    del self._events[token]

    def _schedule_request(self, link_id, plan):
        meds, envelope = self._require("medicines"), self._require("instructions")
        if type(link_id) is not str or link_id not in self._links or self._links[link_id]["bindings"] != self._pair_binding():
            raise IntegrationError("association_required")
        link = self._links[link_id]
        medicine = meds[link["medicine_index"]]
        item = next(r for r in envelope["instructions"] if r["instruction_id"] == link["instruction_id"])
        required = {"dose_quantity", "dose_unit", "duration_days", "administrations_by_slot", "start_date"}
        try:
            _fingerprint(plan)
            if type(plan) is not dict or set(plan) != required:
                raise ValueError
            if set(item["uncertainty_reasons"]) & _UNSAFE_INSTRUCTIONS or set(envelope["issues"]) & _UNSAFE_INSTRUCTIONS:
                raise ValueError
            source = item["raw_text"] or ""
            if re.search(r"\b(?:then|taper|reduce|alternate|increase|decrease|if|or|not|except|SOS|PRN)\b|\d\s*[-–]\s*\d",
                         source + " " + (medicine["raw_text"] or ""), re.IGNORECASE):
                raise ValueError
            if not all(item[k] for k in ("raw_text", "dose_quantity_raw", "dose_unit_raw", "duration_raw", "timing_raw", "frequency_raw")):
                raise ValueError
            if item["frequency_raw"] not in ("BD", "BID", "TDS", "TID", "QID", "HS") or medicine["frequency_pattern"] != item["frequency_raw"]:
                raise ValueError
            number = plan["dose_quantity"]
            if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
                raise ValueError
            if not re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", item["dose_quantity_raw"]):
                raise ValueError
            if Decimal(str(number)) != Decimal(item["dose_quantity_raw"]):
                raise ValueError
            units = {"tablet": "tablet", "capsule": "capsule", "syrup": "mL", "drops": "drop"}
            if plan["dose_unit"] != item["dose_unit_raw"] or plan["dose_unit"] != units.get(medicine["form"]):
                raise ValueError
            if not re.search(r"(?<![\w/])" + re.escape(item["dose_quantity_raw"]) + r"\s*"
                             + re.escape(item["dose_unit_raw"]) + r"(?![\w/])", source):
                raise ValueError
            duration = re.fullmatch(r"([1-9]\d*) days?", item["duration_raw"])
            if (not duration or type(plan["duration_days"]) is not int
                    or plan["duration_days"] != int(duration.group(1))
                    or medicine["duration_days"] != plan["duration_days"]):
                raise ValueError
            slots = plan["administrations_by_slot"]
            if (type(slots) is not dict or set(slots) != {"morning", "noon", "night", "bedtime"}
                    or any(type(v) is not int or v not in (0, 1) for v in slots.values()) or not any(slots.values())):
                raise ValueError
            for slot, count in slots.items():
                mentioned = bool(re.search(r"\b" + slot + r"\b", item["timing_raw"], re.IGNORECASE))
                if count != int(mentioned):
                    raise ValueError
            expected_count = {"BD": 2, "BID": 2, "TDS": 3, "TID": 3, "QID": 4, "HS": 1}
            if sum(slots.values()) != expected_count[item["frequency_raw"]]:
                raise ValueError
            if any(item[k] not in item["raw_text"] for k in (
                    "dose_quantity_raw", "dose_unit_raw", "duration_raw", "frequency_raw", "timing_raw")):
                raise ValueError
            if type(plan["start_date"]) is not str or date.fromisoformat(plan["start_date"]).isoformat() != plan["start_date"]:
                raise ValueError
        except (ValueError, TypeError, OverflowError, IntegrationError):
            raise IntegrationError("unsafe_schedule") from None
        return {"analysis_id": self._prescription["analysis_id"],
                "source_image_sha256": self._prescription["source_image_sha256"], "association_id": link_id,
                "medicine_ref": link["medicine_ref"], "medicine": copy.deepcopy(medicine),
                "instruction": copy.deepcopy(item), "plan": copy.deepcopy(plan)}

    def schedule(self, link_id, plan, *, event):
        with self._lock:
            request = self._schedule_request(link_id, plan)
            self._consume(event, "schedule", "instructions", [link_id, plan])
            expected = {s: self._binding(s) for s in ("medicines", "instructions")}
            epoch = uuid.uuid4().hex
            self._plan_epochs[link_id] = epoch
            for key, value in list(self._derived.items()):
                if value["link_id"] == link_id and value["purpose"] in ("schedule", "reminders", "medicine_pricing"):
                    del self._derived[key]
        return self._call("schedule", ("medicines", "instructions"), request,
                          expected=expected, link_id=link_id, plan_epoch=epoch)

    def _current_schedule(self, schedule_result_id):
        if type(schedule_result_id) is not str:
            raise IntegrationError("invalid_input")
        derived = self._derived.get(schedule_result_id)
        if (derived is None or derived["purpose"] != "schedule"
                or type(derived["payload"]) is not dict or derived["payload"].get("status") != "ok"):
            raise IntegrationError("invalid_state")
        quantity = derived["payload"].get("total_units")
        unit = derived["payload"].get("unit")
        try:
            valid = (type(quantity) in (int, float) and math.isfinite(quantity) and quantity > 0
                     and type(unit) is str and unit == derived["schedule_context"]["plan"]["dose_unit"])
        except OverflowError:
            valid = False
        if not valid:
            raise IntegrationError("unsafe_schedule")
        return derived

    def prepare_reminders(self, schedule_result_id):
        with self._lock:
            derived = self._current_schedule(schedule_result_id)
            request = {"schedule_result_id": schedule_result_id, "schedule": copy.deepcopy(derived["payload"])}
            expected = {s: self._binding(s) for s in ("medicines", "instructions")}
            link_id, epoch = derived["link_id"], derived["plan_epoch"]
        return self._call("reminders", ("medicines", "instructions"), request,
                          expected=expected, derived_id=schedule_result_id, link_id=link_id, plan_epoch=epoch)

    def price_medicines(self, schedule_result_id):
        """Total-price handoff only; quantities must come from Person 3, not AI."""
        with self._lock:
            derived = self._current_schedule(schedule_result_id)
            context = derived["schedule_context"]
            self._require("medicines")
            request = {"analysis_id": context["analysis_id"],
                "source_image_sha256": context["source_image_sha256"],
                "medicine_ref": context["medicine_ref"], "association_id": context["association_id"],
                "medicine": copy.deepcopy(context["medicine"]), "schedule_result_id": schedule_result_id,
                "schedule": copy.deepcopy(derived["payload"])}
            expected = {s: self._binding(s) for s in ("medicines", "instructions")}
            link_id, epoch = derived["link_id"], derived["plan_epoch"]
        return self._call("medicine_pricing", ("medicines", "instructions"), request,
                          expected=expected, derived_id=schedule_result_id, link_id=link_id, plan_epoch=epoch)
