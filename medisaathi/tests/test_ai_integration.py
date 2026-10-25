"""Fictional end-to-end handoffs; extractors and teammate functions are injected."""
import copy
import hashlib
import socket
import uuid
from datetime import date
from io import BytesIO
from unittest.mock import MagicMock

import httpx
import pytest
from PIL import Image

import ai_integration as module
import assistant
import reader
import medication_instructions as medication
import investigations
import strip


def image_bytes(color="white"):
    with BytesIO() as data:
        with Image.new("RGB", (4, 4), color) as im:im.save(data, format="PNG")
        return data.getvalue()


def medicine():
    return dict(raw_text="Fictional-A take 1 tablet BD morning and night for 3 days",
        name="Fictional-A", salt=None, strength=None, form="tablet", frequency_pattern="BD",
        duration_days=3, timing="morning and night", confidence=0.9, needs_review=True)


def instructions(data):
    return dict(schema_version=medication.SCHEMA_VERSION,
        source_image_sha256=hashlib.sha256(data).hexdigest(), instructions=[dict(
            instruction_id="instruction_001", medicine_name_raw="Fictional-A", raw_text=medicine()["raw_text"],
            dose_quantity_raw="1", dose_unit_raw="tablet", frequency_raw="BD", route_raw=None,
            timing_raw="morning and night", duration_raw="3 days", uncertainty_reasons=["missing_information"],
            needs_review=True, confirmation_required=True)], issues=["missing_information"], confirmation_required=True)


def investigation_data(data):
    return dict(schema_version=investigations.SCHEMA_VERSION,
        source_image_sha256=hashlib.sha256(data).hexdigest(), investigations=[dict(
            investigation_id="investigation_001", test_name_raw="CBC", raw_text="Order CBC with ESR; tomorrow",
            order_context_raw="Order", specimen_raw=None, variant_raw="with ESR", timing_raw="tomorrow",
            uncertainty_reasons=["missing_information"], needs_review=True, confirmation_required=True)],
        issues=["missing_information"], confirmation_required=True)


def strip_data(data):
    return strip.normalize_strip_response(dict(medicine_name="Fictional-A", batch_number="DEMO-001",
        product_association="single_product", date_observations=[dict(raw_label="EXP", raw_date_text="08/2027",
        raw_text="EXP 08/2027", association="same_product", confidence=0.95, uncertain=False)],
        quality_issues=[], confidence=0.95, uncertain=False))


def plan():
    return dict(dose_quantity=1, dose_unit="tablet", duration_days=3,
        administrations_by_slot=dict(morning=1, noon=0, night=1, bedtime=0), start_date="2026-10-25")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a, **k):pytest.fail("External network/API access forbidden")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(reader.genai, "Client", forbidden)


@pytest.fixture
def setup():
    extractors = {"medicines": MagicMock(side_effect=lambda data: [medicine()]),
        "instructions": MagicMock(side_effect=instructions),
        "investigations": MagicMock(side_effect=investigation_data), "strip": MagicMock(side_effect=strip_data)}
    downstream = {key: MagicMock(return_value={"status": "ok"}) for key in (
        "schedule", "medicine_matching", "medicine_pricing", "lab_pricing", "reminders")}
    downstream["explain"] = MagicMock(wraps=assistant.explain_prescription)
    downstream["schedule"].return_value = {"status": "ok", "total_units": 6,
        "unit": "tablet", "end_date": date(2026, 10, 27)}
    adapter = module.AIIntegration(extractors=extractors, downstream=downstream)
    return adapter, adapter.frontend_events(), extractors, downstream


def analyze(setup, sections=module.SECTIONS):
    adapter, ui, extractors, downstream = setup
    root = adapter.start_prescription(image_bytes())
    adapter.run_sections(sections, analysis_id=root["analysis_id"])
    return root["analysis_id"]


def confirm(adapter, ui, *scopes):
    for scope in scopes:
        adapter.confirm(scope, event=ui.register_acknowledgement(scope))


def linked(setup):
    adapter, ui, _, _ = setup
    analyze(setup)
    confirm(adapter, ui, "medicines", "instructions")
    event = ui.register_association("medicine_001", "instruction_001")
    return adapter.associate("medicine_001", "instruction_001", event=event)


def scheduled(setup):
    adapter, ui, _, _ = setup
    link = linked(setup);payload = plan()
    return adapter.schedule(link, payload, event=ui.register_schedule_approval(link, payload))


def test_initialization_snapshot_and_navigation_do_not_extract(setup):
    adapter, ui, extractors, _ = setup
    assert adapter.snapshot()["prescription"] is None
    adapter.start_prescription(image_bytes());adapter.snapshot();adapter.frontend_events()
    assert all(e.call_count == 0 for e in extractors.values())


@pytest.mark.parametrize("sections", [("medicines",), ("instructions",), ("investigations",), module.SECTIONS])
def test_explicit_section_selection_and_one_identical_byte_source(setup, sections):
    adapter, ui, extractors, _ = setup
    data = image_bytes();root = adapter.start_prescription(data)
    adapter.run_sections(sections, analysis_id=root["analysis_id"])
    for scope, extractor in extractors.items():
        assert extractor.call_count == int(scope in sections)
        if scope in sections:assert extractor.call_args.args == (data,)
    view = adapter.snapshot()["prescription"]
    assert view["source_image_sha256"] == hashlib.sha256(data).hexdigest()
    for scope in module.SECTIONS:
        assert view["sections"][scope]["status"] == ("succeeded" if scope in sections else "not_requested")
    adapter.run_sections(sections, analysis_id=root["analysis_id"])
    assert all(extractors[s].call_count == 1 for s in sections)


@pytest.mark.parametrize("selection", [[], ["unknown"], ["medicines", "medicines"], ["strip", "medicines"], "medicines"])
def test_invalid_selection_has_zero_extractor_calls(setup, selection):
    adapter, ui, extractors, _ = setup
    root = adapter.start_prescription(image_bytes())
    with pytest.raises(module.IntegrationError):adapter.run_sections(selection, analysis_id=root["analysis_id"])
    assert all(e.call_count == 0 for e in extractors.values())


def test_original_and_reviewed_payloads_are_distinct_and_copies(setup):
    adapter, ui, extractors, _ = setup
    original = [medicine()];extractors["medicines"].side_effect = None;extractors["medicines"].return_value = original
    analyze(setup, ("medicines",));view = adapter.snapshot()
    original[0]["name"] = "mutated extractor object"
    edited = view["prescription"]["sections"]["medicines"]["reviewed"]
    edited[0]["name"] = "Reviewed fictional name";adapter.review("medicines", edited)
    edited[0]["name"] = "mutated caller copy"
    state = adapter.snapshot()["prescription"]["sections"]["medicines"]
    assert state["payload"][0] == medicine()
    assert state["reviewed"][0]["name"] == "Reviewed fictional name"


def test_successful_empty_results_are_not_failures(setup):
    adapter, ui, extractors, _ = setup
    extractors["medicines"].side_effect = lambda data: []
    extractors["investigations"].side_effect = lambda data: dict(investigation_data(data), investigations=[])
    analyze(setup, ("medicines", "investigations"))
    confirm(adapter, ui, "medicines", "investigations")
    section = adapter.snapshot()["prescription"]["sections"]["medicines"]
    assert section["status"] == "succeeded" and section["payload"] == [] and section["safe_error"] is None
    assert adapter.explain()["payload"]["status"] == "empty"


def test_partial_failure_and_explicit_retry_preserve_success(setup):
    adapter, ui, extractors, _ = setup
    extractors["instructions"].side_effect = medication.MedicationNetworkError("private URL")
    identity = analyze(setup)
    before = adapter.snapshot()["prescription"]["sections"]
    assert before["instructions"]["status"] == "failed" and before["instructions"]["payload"] is None
    assert before["instructions"]["reviewed"] is None
    assert before["instructions"]["safe_error"]["category"] == "network_error"
    confirm(adapter, ui, "medicines", "investigations")
    adapter.run_sections(("instructions",), analysis_id=identity)
    assert extractors["instructions"].call_count == 1
    extractors["instructions"].side_effect = instructions
    adapter.retry_section("instructions", analysis_id=identity)
    after = adapter.snapshot()
    assert after["prescription"]["sections"]["medicines"] == before["medicines"]
    assert after["prescription"]["sections"]["instructions"]["status"] == "succeeded"
    assert after["confirmed_scopes"] == ["investigations", "medicines"]
    assert extractors["instructions"].call_count == 2
    with pytest.raises(module.IntegrationError):adapter.retry_section("medicines", analysis_id=identity)


@pytest.mark.parametrize("error,category,stop", [
    (reader.ReaderConfigurationError("secret"), "configuration_error", True),
    (medication.MedicationQuotaError("secret"), "quota_or_rate_limit", True),
    (investigations.InvestigationConfigurationError("secret"), "configuration_error", True),
    (reader.PrescriptionAPIError("quota secret"), "api_error", False),
    (reader.ModelResponseError("secret"), "invalid_response", False),
    (RuntimeError("secret server URL"), "unexpected_error", False)])
def test_safe_classification_and_reliable_stopping_only(setup, error, category, stop):
    adapter, ui, extractors, _ = setup
    extractors["medicines"].side_effect = error
    analyze(setup)
    state = adapter.snapshot()["prescription"]
    assert state["sections"]["medicines"]["safe_error"]["category"] == category
    assert extractors["instructions"].call_count == int(not stop)
    assert "secret" not in str(state)
    if stop:assert state["stop_reason"] == category


def test_invalid_public_output_and_cross_image_payload_fail_closed(setup):
    adapter, ui, extractors, _ = setup
    extractors["instructions"].side_effect = lambda data: dict(instructions(data), source_image_sha256="f"*64)
    extractors["medicines"].side_effect = lambda data: [{**medicine(), "confirmed": True}]
    analyze(setup)
    sections = adapter.snapshot()["prescription"]["sections"]
    for scope in ("medicines", "instructions"):
        assert sections[scope]["status"] == "failed" and sections[scope]["payload"] is None
        assert sections[scope]["safe_error"]["category"] == "invalid_response"


def test_unique_analysis_and_stale_or_foreign_job_rejection(setup):
    adapter, ui, _, _ = setup
    first = adapter.start_prescription(image_bytes());uuid.UUID(first["analysis_id"])
    job = adapter.begin_section("medicines", analysis_id=first["analysis_id"])
    assert adapter.snapshot()["prescription"]["sections"]["medicines"]["status"] == "running"
    second = adapter.start_prescription(image_bytes("black"))
    assert first["analysis_id"] != second["analysis_id"] and first["source_image_sha256"] != second["source_image_sha256"]
    with pytest.raises(module.IntegrationError, match="changed"):adapter.complete_section(job, payload=[medicine()])
    with pytest.raises(module.IntegrationError):adapter.complete_section(object(), payload=[medicine()])
    third = adapter.start_prescription(image_bytes("black"))
    assert second["analysis_id"] != third["analysis_id"]
    assert all(s["payload"] is None for s in adapter.snapshot()["prescription"]["sections"].values())


def test_new_source_during_extraction_does_not_receive_old_result(setup):
    adapter, ui, extractors, _ = setup
    def late(data):
        adapter.start_prescription(image_bytes("black"))
        return [medicine()]
    extractors["medicines"].side_effect = late
    with pytest.raises(module.IntegrationError):analyze(setup, ("medicines",))
    assert adapter.snapshot()["prescription"]["sections"]["medicines"]["status"] == "not_requested"


@pytest.mark.parametrize("event", [True, False, None, {}, {"acknowledged": True, "records_fingerprint": "fake"}, "fake", object()])
def test_client_claims_and_foreign_tokens_are_not_acknowledgement(setup, event):
    adapter, ui, _, _ = setup
    analyze(setup, ("medicines",))
    with pytest.raises(module.IntegrationError):adapter.confirm("medicines", event=event)
    assert adapter.snapshot()["confirmed_scopes"] == []


def test_one_use_scope_bound_and_foreign_adapter_events(setup):
    adapter, ui, _, _ = setup
    analyze(setup)
    token = ui.register_acknowledgement("medicines")
    with pytest.raises(module.IntegrationError):adapter.confirm("instructions", event=token)
    token = ui.register_acknowledgement("medicines");adapter.confirm("medicines", event=token)
    with pytest.raises(module.IntegrationError):adapter.confirm("medicines", event=token)
    other = module.AIIntegration()
    with pytest.raises(module.IntegrationError):other.confirm("medicines", event=ui.register_acknowledgement("medicines"))


@pytest.mark.parametrize("field,value", [("raw_text", "Edited source"), ("name", "Edited name"),
    ("salt", "Explicit ingredient"), ("strength", "10mg"), ("form", "capsule"),
    ("frequency_pattern", "TDS"), ("duration_days", 4), ("timing", "morning"),
    ("confidence", 0.8), ("needs_review", False)])
def test_every_medicine_field_edit_invalidates_confirmation_links_and_results(setup, field, value):
    adapter, ui, _, _ = setup
    result = scheduled(setup)
    token = ui.register_acknowledgement("medicines")
    edited = adapter.snapshot()["prescription"]["sections"]["medicines"]["reviewed"]
    edited[0][field] = value;adapter.review("medicines", edited)
    state = adapter.snapshot()
    assert "medicines" not in state["confirmed_scopes"] and state["associations"] == {}
    assert result["derived_id"] not in state["derived"]
    with pytest.raises(module.IntegrationError):adapter.confirm("medicines", event=token)


def test_invalid_review_also_revokes_approval_without_overwriting_source(setup):
    adapter, ui, _, _ = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    edited = [medicine()];edited[0]["duration_days"] = 3.0
    with pytest.raises(module.IntegrationError):adapter.review("medicines", edited)
    state = adapter.snapshot()
    assert state["confirmed_scopes"] == []
    assert state["prescription"]["sections"]["medicines"]["payload"] == [medicine()]


def test_all_other_scope_edits_invalidate_only_relevant_confirmation(setup):
    adapter, ui, _, _ = setup
    analyze(setup)
    root = adapter.start_strip(image_bytes("black"));adapter.run_sections(("strip",), analysis_id=root["analysis_id"])
    confirm(adapter, ui, *module.SCOPES)
    for scope, collection, field in [("instructions", "instructions", "route_raw"),
                                     ("investigations", "investigations", "specimen_raw")]:
        edited = adapter.snapshot()["prescription"]["sections"][scope]["reviewed"]
        edited[collection][0][field] = "Reviewed literal text"
        adapter.review(scope, edited)
        assert scope not in adapter.snapshot()["confirmed_scopes"]
    edited = adapter.snapshot()["strip"]["sections"]["strip"]["reviewed"]
    edited["batch_number"] = "DEMO-002";adapter.review("strip", edited)
    assert adapter.snapshot()["confirmed_scopes"] == ["medicines"]


@pytest.mark.parametrize("language", ["en", "hi", "hinglish"])
def test_real_assistant_contract_and_no_extra_extraction_on_language_change(setup, language):
    adapter, ui, extractors, downstream = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    result = adapter.explain(language=language)
    assert result["payload"]["language"] == language
    args, kwargs = downstream["explain"].call_args
    assert args[0] == [medicine()] and len(args[0][0]) == 10
    assert set(kwargs["confirmation"]) == {"acknowledged", "records_fingerprint", "confirmed_fields"}
    assert extractors["medicines"].call_count == 1
    assert extractors["instructions"].call_count == extractors["investigations"].call_count == 0


def test_downstream_calls_blocked_before_invocation(setup):
    adapter, ui, _, downstream = setup
    analyze(setup)
    for operation in [adapter.explain, adapter.match_medicines, adapter.price_investigations,
                      lambda: adapter.schedule("none", plan(), event=True), lambda: adapter.prepare_reminders("none")]:
        with pytest.raises(module.IntegrationError):operation()
    assert all(fn.call_count == 0 for fn in downstream.values())


def test_unknown_salt_stays_unknown_and_downstream_cannot_mutate_medicines(setup):
    adapter, ui, _, downstream = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    def match(request):
        assert request["payload"][0]["salt"] is None
        request["payload"][0]["salt"] = "catalogue field must stay separate"
        return {"catalogue_match": None}
    downstream["medicine_matching"].side_effect = match
    adapter.match_medicines()
    assert adapter.snapshot()["prescription"]["sections"]["medicines"]["reviewed"][0]["salt"] is None


def test_no_default_or_fuzzy_association_and_plan_needs_fresh_event(setup):
    adapter, ui, _, downstream = setup
    analyze(setup);confirm(adapter, ui, "medicines", "instructions")
    assert adapter.snapshot()["associations"] == {}
    with pytest.raises(module.IntegrationError):adapter.schedule("none", plan(), event=True)
    with pytest.raises(module.IntegrationError):adapter.associate("medicine_002", "instruction_001", event=True)
    link = adapter.associate("medicine_001", "instruction_001",
        event=ui.register_association("medicine_001", "instruction_001"))
    with pytest.raises(module.IntegrationError):adapter.schedule(link, plan(), event=True)
    request = plan();event = ui.register_schedule_approval(link, request);request["dose_quantity"] = 2
    with pytest.raises(module.IntegrationError):adapter.schedule(link, request, event=event)
    downstream["schedule"].assert_not_called()


def test_explicit_valid_schedule_only_delegates_and_reminders_need_current_schedule(setup):
    adapter, ui, _, downstream = setup
    downstream["schedule"].return_value = {"status": "ok", "total_units": 6,
        "unit": "tablet", "end_date": date(2026, 10, 27)}
    result = scheduled(setup)
    request = downstream["schedule"].call_args.args[0]
    assert request["plan"] == plan() and request["medicine"] == medicine()
    assert "total_units" not in request  # no duplicate engine/calculation
    assert result["payload"]["end_date"] == date(2026, 10, 27)
    adapter.prepare_reminders(result["derived_id"])
    downstream["reminders"].assert_called_once()
    adapter.clear_associations()
    with pytest.raises(module.IntegrationError):adapter.prepare_reminders(result["derived_id"])


@pytest.mark.parametrize("field,value", [("dose_quantity", None), ("dose_quantity", True),
    ("dose_quantity", 0), ("dose_quantity", -1), ("dose_quantity", float("nan")),
    ("dose_quantity", float("inf")), ("dose_quantity", "1"), ("dose_unit", None),
    ("dose_unit", "mg"), ("duration_days", 3.0), ("duration_days", "5-7 days"),
    ("duration_days", 4), ("administrations_by_slot", {}),
    ("administrations_by_slot", dict(morning=1, noon=0, night=0, bedtime=0)),
    ("start_date", "tomorrow")])
def test_unsafe_plan_values_block_before_downstream(setup, field, value):
    adapter, ui, _, downstream = setup
    link = linked(setup);request = plan();request[field] = value
    # Nonfinite values cannot even obtain an event receipt.
    with pytest.raises(module.IntegrationError):
        token = ui.register_schedule_approval(link, request)
        adapter.schedule(link, request, event=token)
    downstream["schedule"].assert_not_called()


@pytest.mark.parametrize("field,value", [("frequency_raw", "OD"), ("frequency_raw", "SOS"),
    ("frequency_raw", "1-0-1"), ("duration_raw", "5-7 days"), ("duration_raw", "2 weeks"),
    ("dose_quantity_raw", "½"), ("dose_unit_raw", None), ("timing_raw", "08:00 and 20:00"),
    ("raw_text", medicine()["raw_text"] + " then reduce"),
    ("uncertainty_reasons", ["conflicting_instructions"])])
def test_ambiguous_ranges_tapers_and_conflicts_block_even_if_acknowledged(setup, field, value):
    adapter, ui, _, downstream = setup
    analyze(setup)
    edited = adapter.snapshot()["prescription"]["sections"]["instructions"]["reviewed"]
    edited["instructions"][0][field] = value
    adapter.review("instructions", edited);confirm(adapter, ui, "medicines", "instructions")
    link = adapter.associate("medicine_001", "instruction_001",
        event=ui.register_association("medicine_001", "instruction_001"))
    request = plan()
    with pytest.raises(module.IntegrationError):
        adapter.schedule(link, request, event=ui.register_schedule_approval(link, request))
    downstream["schedule"].assert_not_called()


@pytest.mark.parametrize("field,value", [("test_name_raw", None), ("order_context_raw", None),
    ("variant_raw", None), ("uncertainty_reasons", ["ordering_unclear"]),
    ("uncertainty_reasons", ["conflicting_order_mentions"]), ("uncertainty_reasons", ["variant_unclear"])])
def test_lab_pricing_needs_confirmed_unambiguous_order_and_variant(setup, field, value):
    adapter, ui, _, downstream = setup
    analyze(setup, ("investigations",))
    edited = adapter.snapshot()["prescription"]["sections"]["investigations"]["reviewed"]
    edited["investigations"][0][field] = value
    adapter.review("investigations", edited);confirm(adapter, ui, "investigations")
    with pytest.raises(module.IntegrationError):adapter.price_investigations()
    downstream["lab_pricing"].assert_not_called()


def test_lab_handoff_preserves_names_unknown_specimen_timing_and_provenance(setup):
    adapter, ui, _, downstream = setup
    analyze(setup, ("investigations",));confirm(adapter, ui, "investigations")
    adapter.price_investigations();request = downstream["lab_pricing"].call_args.args[0]
    item = request["payload"]["investigations"][0]
    assert item["test_name_raw"] == "CBC" and item["specimen_raw"] is None
    assert item["variant_raw"] == "with ESR" and item["timing_raw"] == "tomorrow"
    assert request["source_image_sha256"] == hashlib.sha256(image_bytes()).hexdigest()


def test_strip_scope_independent_confirmations_events_and_no_expiry_status(setup):
    adapter, ui, _, _ = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    root = adapter.start_strip(image_bytes("black"));adapter.run_sections(("strip",), analysis_id=root["analysis_id"])
    with pytest.raises(module.IntegrationError):adapter.confirmed_strip()
    token = ui.register_acknowledgement("strip")
    adapter.start_prescription(image_bytes())  # does not revoke a pending strip event
    adapter.confirm("strip", event=token)
    result = adapter.confirmed_strip()
    assert result["source_image_sha256"] == hashlib.sha256(image_bytes("black")).hexdigest()
    assert "expired" not in result["payload"] and "safe_to_use" not in result["payload"]
    assert result["payload"]["expiry"]["day"] is None
    adapter.start_strip(image_bytes())
    with pytest.raises(module.IntegrationError):adapter.confirmed_strip()


def test_stale_downstream_result_is_not_published(setup):
    adapter, ui, _, downstream = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    def late(request):
        adapter.start_prescription(image_bytes("black"))
        return {"status": "old result"}
    downstream["medicine_matching"].side_effect = late
    with pytest.raises(module.IntegrationError):adapter.match_medicines()
    assert adapter.snapshot()["derived"] == {}


def test_association_changed_during_schedule_rejects_late_result(setup):
    adapter, ui, _, downstream = setup
    link = linked(setup)
    downstream["schedule"].side_effect = lambda request: (adapter.clear_associations() or {"status": "ok"})
    request = plan()
    with pytest.raises(module.IntegrationError):
        adapter.schedule(link, request, event=ui.register_schedule_approval(link, request))
    assert adapter.snapshot()["derived"] == {}


def test_safe_downstream_error_and_no_missing_default_integration(setup):
    adapter, ui, _, downstream = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    downstream["medicine_matching"].side_effect = RuntimeError("private key and response body")
    with pytest.raises(module.IntegrationError) as caught:adapter.match_medicines()
    assert caught.value.category == "downstream_error" and "private" not in str(caught.value)
    assert adapter.snapshot()["derived"] == {}


@pytest.mark.parametrize("data", [None, b"", b"corrupt"])
def test_new_invalid_source_clears_old_approval(setup, data):
    adapter, ui, _, _ = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    with pytest.raises(module.IntegrationError):adapter.start_prescription(data)
    assert adapter.snapshot()["confirmed_scopes"] == [] and adapter.snapshot()["prescription"] is None


def test_reentrant_job_cannot_extract_twice(setup):
    adapter, ui, extractors, _ = setup
    root = adapter.start_prescription(image_bytes())
    job = adapter.begin_section("medicines", analysis_id=root["analysis_id"])
    def reentrant(data):
        with pytest.raises(module.IntegrationError):adapter.execute(job)
        return [medicine()]
    extractors["medicines"].side_effect = reentrant
    adapter.execute(job)
    with pytest.raises(module.IntegrationError):adapter.execute(job)
    assert extractors["medicines"].call_count == 1
    section = adapter.snapshot()["prescription"]["sections"]["medicines"]
    assert section["extractor_invocations"] == 1


def test_new_approved_plan_invalidates_previous_schedule_and_reminders(setup):
    adapter, ui, _, downstream = setup
    first = scheduled(setup)
    reminder = adapter.prepare_reminders(first["derived_id"])
    link = next(iter(adapter.snapshot()["associations"]))
    request = plan();request["start_date"] = "2026-10-26"
    second = adapter.schedule(link, request, event=ui.register_schedule_approval(link, request))
    derived = adapter.snapshot()["derived"]
    assert first["derived_id"] not in derived and reminder["derived_id"] not in derived
    assert second["derived_id"] in derived
    with pytest.raises(module.IntegrationError):adapter.prepare_reminders(first["derived_id"])


def test_reassociation_requires_new_plan_approval(setup):
    adapter, ui, _, downstream = setup
    link = linked(setup);request = plan()
    approval = ui.register_schedule_approval(link, request)
    new_link = adapter.associate("medicine_001", "instruction_001",
        event=ui.register_association("medicine_001", "instruction_001"))
    assert new_link != link and link not in adapter.snapshot()["associations"]
    with pytest.raises(module.IntegrationError):adapter.schedule(new_link, request, event=approval)
    downstream["schedule"].assert_not_called()


@pytest.mark.parametrize("raw", ["Do not order CBC with ESR; tomorrow", "Previous CBC with ESR; tomorrow",
    "Consider CBC with ESR; tomorrow", "Order CBC? with ESR; tomorrow"])
def test_clear_review_flags_do_not_turn_negated_historical_or_questioned_text_into_order(setup, raw):
    adapter, ui, _, downstream = setup
    analyze(setup, ("investigations",))
    edited = adapter.snapshot()["prescription"]["sections"]["investigations"]["reviewed"]
    item = edited["investigations"][0]
    item.update(raw_text=raw, order_context_raw=raw, uncertainty_reasons=[], needs_review=False)
    edited["issues"] = []
    adapter.review("investigations", edited);confirm(adapter, ui, "investigations")
    with pytest.raises(module.IntegrationError):adapter.price_investigations()
    downstream["lab_pricing"].assert_not_called()


def test_duplicate_orders_stay_blocked_when_only_flags_are_removed(setup):
    adapter, ui, _, downstream = setup
    analyze(setup, ("investigations",))
    edited = adapter.snapshot()["prescription"]["sections"]["investigations"]["reviewed"]
    other = copy.deepcopy(edited["investigations"][0]);other["investigation_id"] = "investigation_002"
    edited["investigations"].append(other)
    adapter.review("investigations", edited);confirm(adapter, ui, "investigations")
    with pytest.raises(module.IntegrationError):adapter.price_investigations()
    downstream["lab_pricing"].assert_not_called()


def test_mutated_display_confirmation_is_not_authority(setup):
    adapter, ui, _, downstream = setup
    analyze(setup, ("medicines",))
    display = adapter.snapshot();display["confirmed_scopes"] = ["medicines"]
    display["prescription"]["sections"]["medicines"]["reviewed"][0]["needs_review"] = False
    with pytest.raises(module.IntegrationError):adapter.match_medicines()
    downstream["medicine_matching"].assert_not_called()


@pytest.mark.parametrize("mutation", ["extra_key", "wrong_schema", "duplicate_id", "nonfinite"])
def test_final_extractor_contract_validation_is_strict(setup, mutation):
    adapter, ui, extractors, _ = setup
    def invalid(data):
        result = instructions(data)
        if mutation == "extra_key":result["instructions"][0]["confirmed"] = True
        elif mutation == "wrong_schema":result["schema_version"] = "other-schema"
        elif mutation == "duplicate_id":result["instructions"].append(copy.deepcopy(result["instructions"][0]))
        else:result["instructions"][0]["dose_quantity_raw"] = float("nan")
        return result
    extractors["instructions"].side_effect = invalid
    analyze(setup, ("instructions",))
    section = adapter.snapshot()["prescription"]["sections"]["instructions"]
    assert section["status"] == "failed" and section["payload"] is None
    assert section["safe_error"]["category"] == "invalid_response"


def test_unknown_values_acknowledged_without_replacement_and_valid_empty_lab_handoff(setup):
    adapter, ui, extractors, downstream = setup
    extractors["investigations"].side_effect = lambda data: dict(investigation_data(data), investigations=[])
    analyze(setup);confirm(adapter, ui, "medicines", "instructions", "investigations")
    assert adapter.snapshot()["prescription"]["sections"]["instructions"]["reviewed"]["instructions"][0]["route_raw"] is None
    adapter.price_investigations()
    assert downstream["lab_pricing"].call_args.args[0]["payload"]["investigations"] == []


def test_missing_teammate_function_is_controlled_without_default_side_effects(setup):
    adapter, ui, extractors, downstream = setup
    isolated = module.AIIntegration(extractors=extractors)
    root = isolated.start_prescription(image_bytes());isolated.run_sections(("medicines",), analysis_id=root["analysis_id"])
    confirm(isolated, isolated.frontend_events(), "medicines")
    with pytest.raises(module.IntegrationError) as caught:isolated.match_medicines()
    assert caught.value.category == "unavailable"


@pytest.mark.parametrize("mutation", ["bad_observation", "bad_date", "false_confirmation"])
def test_strip_final_contract_validation(setup, mutation):
    adapter, ui, extractors, _ = setup
    def invalid(data):
        result = strip_data(data)
        if mutation == "bad_observation":result["date_observations"] = [{}]
        elif mutation == "bad_date":result["expiry"]["day"] = 31
        else:result["confirmation_required"] = False
        return result
    extractors["strip"].side_effect = invalid
    root = adapter.start_strip(image_bytes());adapter.run_sections(("strip",), analysis_id=root["analysis_id"])
    section = adapter.snapshot()["strip"]["sections"]["strip"]
    assert section["status"] == "failed" and section["safe_error"]["category"] == "invalid_response"


def test_strip_new_source_preserves_confirmed_prescription(setup):
    adapter, ui, _, _ = setup
    analyze(setup, ("medicines",));confirm(adapter, ui, "medicines")
    pending = ui.register_acknowledgement("medicines")
    adapter.start_strip(image_bytes("black"))
    adapter.confirm("medicines", event=pending)
    assert adapter.snapshot()["confirmed_scopes"] == ["medicines"]


def test_needs_input_schedule_cannot_create_reminders_or_prices(setup):
    adapter, ui, _, downstream = setup
    downstream["schedule"].return_value = {"status": "needs_input"}
    result = scheduled(setup)
    with pytest.raises(module.IntegrationError):adapter.prepare_reminders(result["derived_id"])
    with pytest.raises(module.IntegrationError):adapter.price_medicines(result["derived_id"])
    downstream["reminders"].assert_not_called();downstream["medicine_pricing"].assert_not_called()


@pytest.mark.parametrize("quantity", [None, True, 0, -1, float("nan"), float("inf")])
def test_medicine_prices_require_actual_finite_schedule_quantity(setup, quantity):
    adapter, ui, _, downstream = setup
    # Nonfinite downstream data itself is rejected, before any pricing call.
    downstream["schedule"].return_value = {"status": "ok", "total_units": quantity, "unit": "tablet"}
    with pytest.raises(module.IntegrationError):
        result = scheduled(setup)
        adapter.price_medicines(result["derived_id"])
    downstream["medicine_pricing"].assert_not_called()


def test_quantity_handoff_preserves_salt_and_is_invalidated_with_plan(setup):
    adapter, ui, _, downstream = setup
    downstream["schedule"].return_value = {"status": "ok", "total_units": 6, "unit": "tablet"}
    result = scheduled(setup)
    price = adapter.price_medicines(result["derived_id"])
    request = downstream["medicine_pricing"].call_args.args[0]
    assert request["schedule"]["total_units"] == 6
    assert request["medicine"]["salt"] is None and request["medicine_ref"] == "medicine_001"
    adapter.clear_associations()
    assert price["derived_id"] not in adapter.snapshot()["derived"]
    with pytest.raises(module.IntegrationError):adapter.price_medicines(result["derived_id"])


def test_schedule_result_unit_mismatch_blocks_reminders_and_pricing(setup):
    adapter, ui, _, downstream = setup
    downstream["schedule"].return_value = {"status": "ok", "total_units": 6, "unit": "mg"}
    result = scheduled(setup)
    with pytest.raises(module.IntegrationError):adapter.price_medicines(result["derived_id"])
    with pytest.raises(module.IntegrationError):adapter.prepare_reminders(result["derived_id"])
    downstream["medicine_pricing"].assert_not_called();downstream["reminders"].assert_not_called()


def test_medicine_price_quantity_is_associated_with_only_the_selected_medicine(setup):
    adapter, ui, extractors, downstream = setup
    second = dict(medicine(), name="Fictional-B", form="syrup",
                  raw_text="Fictional-B take 5 mL BD morning and night for 3 days")
    extractors["medicines"].side_effect = lambda data: [medicine(), copy.deepcopy(second)]
    def two_instructions(data):
        result = instructions(data)
        result["instructions"].append(dict(result["instructions"][0], instruction_id="instruction_002",
            medicine_name_raw="Fictional-B", raw_text=second["raw_text"], dose_quantity_raw="5", dose_unit_raw="mL"))
        return result
    extractors["instructions"].side_effect = two_instructions
    analyze(setup, ("medicines", "instructions"));confirm(adapter, ui, "medicines", "instructions")
    link = adapter.associate("medicine_002", "instruction_002",
        event=ui.register_association("medicine_002", "instruction_002"))
    request = dict(plan(), dose_quantity=5, dose_unit="mL")
    downstream["schedule"].return_value = {"status": "ok", "total_units": 30, "unit": "mL"}
    result = adapter.schedule(link, request, event=ui.register_schedule_approval(link, request))
    adapter.price_medicines(result["derived_id"])
    priced = downstream["medicine_pricing"].call_args.args[0]
    assert priced["medicine"] == second and priced["medicine_ref"] == "medicine_002"
    assert "medicines" not in priced and priced["schedule"]["total_units"] == 30


def test_strip_review_cannot_create_date_without_matching_observation(setup):
    adapter, ui, _, _ = setup
    root = adapter.start_strip(image_bytes());adapter.run_sections(("strip",), analysis_id=root["analysis_id"])
    confirm(adapter, ui, "strip")
    edited = adapter.snapshot()["strip"]["sections"]["strip"]["reviewed"]
    edited["expiry"].update(year=2028, iso="2028-08")
    with pytest.raises(module.IntegrationError):adapter.review("strip", edited)
    assert "strip" not in adapter.snapshot()["confirmed_scopes"]
