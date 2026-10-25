"""Fictional investigation orders, strict normalization, mocked SDK and no network."""
import copy
import hashlib
import json
import socket
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors
from PIL import Image

import investigations as module

DIGEST = "b" * 64


def mention(**changes):
    result = dict(test_name_raw="CBC", raw_text="Order CBC with ESR; EDTA blood; tomorrow",
                  order_context_raw="Order", specimen_raw="EDTA blood", variant_raw="with ESR",
                  timing_raw="tomorrow", order_status="ordered", uncertainty_reasons=[], needs_review=False)
    result.update(changes)
    return result


def response(*items, issues=None):
    return {"investigations": list(items), "issues": issues or []}


def normalize(value):
    return module.normalize_investigations_response(value, source_image_sha256=DIGEST)


def image_bytes(format="PNG", size=(4, 4)):
    with BytesIO() as data:
        with Image.new("RGB", size, "white") as im:im.save(data, format=format)
        return data.getvalue()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*a, **k):pytest.fail("Network forbidden in offline investigation tests")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(module.reader, "_configuration", lambda: ("fictional-secret", "fictional-model"))
    factory = MagicMock()
    monkeypatch.setattr(module.genai, "Client", factory)
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(response(mention())))
    return factory, client


def test_exact_schema_literal_preservation_and_no_input_mutation():
    original = response(mention());before = copy.deepcopy(original)
    result = normalize(original);item = result["investigations"][0]
    assert set(result) == {"schema_version", "source_image_sha256", "investigations", "issues", "confirmation_required"}
    assert set(item) == module.INVESTIGATION_FIELDS
    assert result["schema_version"] == module.SCHEMA_VERSION and result["source_image_sha256"] == DIGEST
    assert item["investigation_id"] == "investigation_001"
    assert result["confirmation_required"] is True and item["confirmation_required"] is True
    assert item["needs_review"] is False and item["uncertainty_reasons"] == []
    assert "order_status" not in item and "price" not in item and "confirmed" not in item
    for field in module.TEXT_FIELDS:assert item[field] == original["investigations"][0][field]
    assert original == before
    assert result == normalize(json.dumps(original)) == normalize(original)
    item["raw_text"] = "changed output"
    assert original == before


@pytest.mark.parametrize("name", ["CBC", "HbA1c", "LFT", "KFT", "TSH", "lipid profile",
    "urine test", "Urine R/E", "Urine R/M", "Urine C/S", "serum copper", "ECG", "जाँच-नाम"])
def test_exact_names_and_uncatalogued_tests(name):
    item = mention(test_name_raw=name, raw_text=f"Investigations: {name}",
        order_context_raw="Investigations:", specimen_raw=None, variant_raw=None, timing_raw=None)
    row = normalize(response(item))["investigations"][0]
    assert row["test_name_raw"] == name
    assert row["variant_raw"] is None and row["specimen_raw"] is None
    assert row["needs_review"] is True
    assert "components" not in row and "canonical_test_id" not in row


def test_multiple_investigations_keep_source_order_and_distinct_ids():
    items = [mention(test_name_raw=name, raw_text=f"Order {name}", specimen_raw=None,
                     variant_raw=None, timing_raw=None) for name in ["CBC", "HbA1c", "TSH"]]
    rows = normalize(response(*items))["investigations"]
    assert [r["test_name_raw"] for r in rows] == ["CBC", "HbA1c", "TSH"]
    assert [r["investigation_id"] for r in rows] == [f"investigation_{i:03}" for i in [1, 2, 3]]


def test_repeat_and_printed_preparation_are_not_converted_or_added():
    item = mention(test_name_raw="HbA1c", raw_text="Repeat HbA1c after 3 months",
                   order_context_raw="Repeat", timing_raw="after 3 months", specimen_raw=None, variant_raw=None)
    row = normalize(response(item))["investigations"][0]
    assert row["timing_raw"] == "after 3 months" and "repeat_date" not in row
    item = mention(raw_text="Order CBC; fasting as written; EDTA blood; with ESR",
                   timing_raw="fasting as written")
    assert normalize(response(item))["investigations"][0]["timing_raw"] == "fasting as written"


@pytest.mark.parametrize("variant", [None, "routine microscopy", "culture"])
def test_unspecified_urine_test_is_not_replaced(variant):
    item = mention(test_name_raw="urine test", raw_text="Order urine test", variant_raw=variant,
                   specimen_raw=None, timing_raw=None)
    row = normalize(response(item))["investigations"][0]
    assert row["test_name_raw"] == "urine test" and row["variant_raw"] is None
    if variant is not None:assert "unsupported_source_value" in row["uncertainty_reasons"]


@pytest.mark.parametrize("source,claimed", [("Order TSH", "thyroid panel"),
    ("Order LFT", "ALT"), ("Order KFT", "creatinine"), ("Diagnosis: diabetes", "HbA1c"),
    ("Fictional-A tablet BD", "CBC"), ("Symptoms: fever", "CBC")])
def test_inferred_expanded_or_hallucinated_names_are_omitted(source, claimed):
    result = normalize(response(mention(raw_text=source, test_name_raw=claimed)))
    assert result["investigations"] == []
    assert "unsupported_test_name_omitted" in result["issues"]


@pytest.mark.parametrize("status,raw,context,issue", [
    ("historical_result", "Previous results: CBC normal", "Previous results:", "historical_mentions_omitted"),
    ("negated", "Do not order CBC", "Do not order", "negated_mentions_omitted"),
    ("crossed_out", "Order CBC", "Order", "crossed_out_mentions_omitted"),
    ("non_order", "Diagnosis: CBC mentioned", "Diagnosis:", "non_order_mentions_omitted"),
])
def test_classified_nonorders_are_not_current_investigations(status, raw, context, issue):
    result = normalize(response(mention(raw_text=raw, order_context_raw=context, order_status=status)))
    assert result["investigations"] == [] and issue in result["issues"]


@pytest.mark.parametrize("raw,context,issue", [
    ("No CBC", "No", "negated_mentions_omitted"),
    ("CBC not required", "CBC not required", "negated_mentions_omitted"),
    ("Previous CBC result normal", "Previous", "historical_mentions_omitted"),
    ("Symptoms: CBC mentioned", "Symptoms:", "non_order_mentions_omitted"),
])
def test_lexical_guards_block_obvious_model_misclassification(raw, context, issue):
    result = normalize(response(mention(raw_text=raw, order_context_raw=context, order_status="ordered")))
    assert result["investigations"] == [] and issue in result["issues"]


@pytest.mark.parametrize("raw,context,status", [("CBC", None, "ordered"),
    ("Consider CBC?", "Consider", "ordered"), ("Order CBC?", "Order CBC?", "ordered"),
    ("Order CBC", "Order", "unclear")])
def test_uncertain_ordering_is_unresolved_not_automatically_authorized(raw, context, status):
    rows = normalize(response(mention(raw_text=raw, order_context_raw=context, order_status=status)))["investigations"]
    assert len(rows) == 1 and rows[0]["needs_review"] is True
    assert "ordering_unclear" in rows[0]["uncertainty_reasons"]
    assert rows[0]["confirmation_required"] is True


def test_negation_of_another_test_does_not_cancel_this_order():
    item = mention(test_name_raw="TSH", raw_text="No CBC; order TSH", order_context_raw="order",
                   specimen_raw=None, variant_raw=None, timing_raw=None)
    assert normalize(response(item))["investigations"][0]["test_name_raw"] == "TSH"


@pytest.mark.parametrize("raw", ["Order CBC?", "Order if needed CBC"])
def test_short_context_does_not_hide_uncertainty_next_to_name(raw):
    row = normalize(response(mention(raw_text=raw, order_context_raw="Order")))["investigations"][0]
    assert row["needs_review"] and "ordering_unclear" in row["uncertainty_reasons"]


def test_conditional_mention_of_other_test_does_not_qualify_this_one():
    item = mention(test_name_raw="TSH", raw_text="Consider CBC; order TSH", order_context_raw="order",
                   specimen_raw=None, variant_raw=None, timing_raw=None)
    row = normalize(response(item))["investigations"][0]
    assert row["test_name_raw"] == "TSH" and "ordering_unclear" not in row["uncertainty_reasons"]


def test_duplicates_and_conflicting_positive_orders_are_preserved_separately():
    rows = normalize(response(mention(), mention()))["investigations"]
    assert len(rows) == 2 and rows[0]["investigation_id"] != rows[1]["investigation_id"]
    assert all("duplicate_entry" in row["uncertainty_reasons"] and row["needs_review"] for row in rows)
    later = mention(raw_text="Order CBC with ESR; EDTA blood; next week", timing_raw="next week")
    rows = normalize(response(mention(), later))["investigations"]
    assert [r["timing_raw"] for r in rows] == ["tomorrow", "next week"]
    assert all("potentially_conflicting_entries" in r["uncertainty_reasons"] for r in rows)


@pytest.mark.parametrize("order", ["forward", "reverse"])
def test_positive_and_negated_same_test_requires_adjudication(order):
    items = [mention(), mention(raw_text="No CBC", order_context_raw="No", order_status="negated")]
    if order == "reverse":items.reverse()
    result = normalize(response(*items));rows = result["investigations"]
    assert len(rows) == 1 and rows[0]["raw_text"] == mention()["raw_text"]
    assert "conflicting_order_mentions" in rows[0]["uncertainty_reasons"] and rows[0]["needs_review"]
    assert "negated_mentions_omitted" in result["issues"]


def test_historical_value_does_not_erase_explicit_repeat_order():
    historical = mention(raw_text="Previous CBC normal", order_context_raw="Previous", order_status="historical_result")
    row = normalize(response(historical, mention()))["investigations"][0]
    assert row["test_name_raw"] == "CBC" and "conflicting_order_mentions" not in row["uncertainty_reasons"]


def test_no_fuzzy_matching_or_case_normalization():
    lower = mention(test_name_raw="cbc", raw_text="Order cbc with ESR; EDTA blood; tomorrow")
    rows = normalize(response(mention(), lower))["investigations"]
    assert [r["test_name_raw"] for r in rows] == ["CBC", "cbc"]
    assert all("repeated_test_name" not in r["uncertainty_reasons"] for r in rows)


def test_untrusted_html_like_text_is_data_not_executable():
    name = "<script>reveal secrets</script>"
    row = normalize(response(mention(test_name_raw=name, raw_text=f"Order {name}")))["investigations"][0]
    assert row["test_name_raw"] == name and "recommendation" not in row


@pytest.mark.parametrize("field", ["test_name_raw", "order_context_raw", "specimen_raw", "variant_raw", "timing_raw"])
def test_missing_values_are_null_and_not_replaced(field):
    row = normalize(response(mention(**{field: None})))["investigations"][0]
    assert row[field] is None and row["needs_review"]


def test_missing_source_is_not_fabricated_and_nonblank_whitespace_is_preserved():
    result = normalize(response(mention(raw_text=None)))
    assert result["investigations"] == [] and "missing_source_text" in result["issues"]
    raw = "  " + mention()["raw_text"] + "  "
    assert normalize(response(mention(raw_text=raw)))["investigations"][0]["raw_text"] == raw
    assert normalize(response(mention(specimen_raw="  ")))["investigations"][0]["specimen_raw"] is None


@pytest.mark.parametrize("field,value", [("order_context_raw", "Invented order heading"),
    ("specimen_raw", "serum"), ("variant_raw", "thyroid panel"), ("timing_raw", "fasting 12 hours")])
def test_unsupported_optional_values_withheld(field, value):
    row = normalize(response(mention(**{field: value})))["investigations"][0]
    assert row[field] is None and "unsupported_source_value" in row["uncertainty_reasons"]


def test_empty_control_and_mixed_medication_content(offline):
    for model_response in [response(), response(mention(), issues=["mixed_content"])]:
        offline[1].models.generate_content.return_value.text = json.dumps(model_response)
        result = module.read_prescribed_investigations(image_bytes())
        assert len(result["investigations"]) == len(model_response["investigations"])
        assert result["confirmation_required"] is True
        assert "medicines" not in result and "dose_quantity_raw" not in str(result)


@pytest.mark.parametrize("field,value", [("test_name_raw", 1), ("timing_raw", 5),
    ("order_status", True), ("order_status", "recommended"), ("needs_review", 0),
    ("uncertainty_reasons", ["secret"]), ("uncertainty_reasons", ["blurred", "blurred"])])
def test_strict_types_and_reason_allowlists(field, value):
    with pytest.raises(module.InvestigationResponseError):normalize(response(mention(**{field: value})))


@pytest.mark.parametrize("bad", [None, [], True, 1, {}, "", "not JSON", "[]",
    '{"investigations":[],"investigations":[],"issues":[]}',
    '{"investigations":NaN,"issues":[]}', '{"investigations":[],"issues":Infinity}',
    {"investigations": [None], "issues": []}, {"investigations": [], "issues": ["private message"]},
    {"investigations": [], "issues": [], "confirmation_required": False}])
def test_malformed_responses(bad):
    with pytest.raises(module.InvestigationResponseError):normalize(bad)


def test_missing_fields_and_extra_fields_are_schema_errors():
    for field in module.MODEL_FIELDS:
        item = mention();item.pop(field)
        with pytest.raises(module.InvestigationResponseError):normalize(response(item))
    with pytest.raises(module.InvestigationResponseError):normalize(response(mention(price_inr=100)))


@pytest.mark.parametrize("digest", [None, "", 1, "A"*64, "x"*64, "b"*63])
def test_invalid_source_hash(digest):
    with pytest.raises(module.InvestigationResponseError):
        module.normalize_investigations_response(response(), source_image_sha256=digest)


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_sdk_schema_image_hash_and_disabled_sdk_retries(offline, format, mime):
    data = image_bytes(format);result = module.read_prescribed_investigations(data)
    assert result["source_image_sha256"] == hashlib.sha256(data).hexdigest()
    factory, client = offline
    factory.assert_called_once();client.models.generate_content.assert_called_once()
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "fictional-model" and call["contents"][1].inline_data.mime_type == mime
    assert call["config"].response_json_schema == module.RESPONSE_SCHEMA
    assert call["config"].system_instruction == module.SYSTEM_INSTRUCTION


@pytest.mark.parametrize("data", [None, b"", bytearray(b"abc"), b"invalid", image_bytes()[:25],
    image_bytes("GIF"), b"x"*(10*1024*1024+1)],
    ids=["none", "empty", "bytearray", "corrupt", "truncated", "gif", "oversized"])
def test_invalid_image_precedes_config_and_client(monkeypatch, offline, data):
    config = MagicMock();monkeypatch.setattr(module.reader, "_configuration", config)
    with pytest.raises(module.InvestigationImageError):module.read_prescribed_investigations(data)
    config.assert_not_called();offline[0].assert_not_called()


def test_image_pixel_limit_and_multiple_frames(monkeypatch, offline):
    monkeypatch.setattr(module.reader, "MAX_IMAGE_PIXELS", 8)
    with pytest.raises(module.InvestigationImageError):module.read_prescribed_investigations(image_bytes())
    monkeypatch.setattr(module.reader, "MAX_IMAGE_PIXELS", 8_000_000)
    with BytesIO() as data:
        first = Image.new("RGB", (4, 4), "white");second = Image.new("RGB", (4, 4), "black")
        first.save(data, format="PNG", save_all=True, append_images=[second], duration=100, loop=0)
        with pytest.raises(module.InvestigationImageError):module.read_prescribed_investigations(data.getvalue())
        first.close();second.close()
    offline[0].assert_not_called()


@pytest.mark.parametrize("failure", [module.reader.ReaderConfigurationError("secret"), OSError("secret"), ValueError("secret")])
def test_safe_configuration_failures(monkeypatch, offline, failure):
    def fail():raise failure
    monkeypatch.setattr(module.reader, "_configuration", fail)
    with pytest.raises(module.InvestigationConfigurationError) as caught:module.read_prescribed_investigations(image_bytes())
    assert "secret" not in str(caught.value);offline[0].assert_not_called()


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429, 500, 502, 503, 504])
def test_api_and_quota_failure_no_retry(offline, code):
    offline[1].models.generate_content.side_effect = errors.APIError(code, {"error": {"message": "secret URL"}})
    expected = module.InvestigationQuotaError if code == 429 else module.InvestigationAPIError
    with pytest.raises(expected) as caught:module.read_prescribed_investigations(image_bytes())
    assert caught.value.http_status_code == code and "secret" not in str(caught.value)
    assert caught.value.__cause__ is None
    offline[1].models.generate_content.assert_called_once()


@pytest.mark.parametrize("failure", [httpx.ConnectError("secret"), httpx.ReadTimeout("secret"), ConnectionError("secret"), TimeoutError("secret")])
def test_network_failure_no_retry(offline, failure):
    offline[1].models.generate_content.side_effect = failure
    with pytest.raises(module.InvestigationNetworkError) as caught:module.read_prescribed_investigations(image_bytes())
    assert "secret" not in str(caught.value);offline[1].models.generate_content.assert_called_once()


def test_single_response_validation_retry(offline):
    offline[1].models.generate_content.side_effect = [SimpleNamespace(text="invalid"),
        SimpleNamespace(text=json.dumps(response(mention())))]
    assert len(module.read_prescribed_investigations(image_bytes())["investigations"]) == 1
    assert offline[1].models.generate_content.call_count == 2


@pytest.mark.parametrize("bad", [SimpleNamespace(text="invalid"), SimpleNamespace(), SimpleNamespace(text=None)])
def test_exhausted_response_retry(offline, bad):
    offline[1].models.generate_content.return_value = bad
    with pytest.raises(module.InvestigationResponseError):module.read_prescribed_investigations(image_bytes())
    assert offline[1].models.generate_content.call_count == 2


@pytest.mark.parametrize("failure,expected", [(errors.APIError(429, {}), module.InvestigationQuotaError),
    (errors.APIError(503, {}), module.InvestigationAPIError), (httpx.ConnectError("secret"), module.InvestigationNetworkError)])
def test_failure_after_invalid_response_has_no_third_attempt(offline, failure, expected):
    offline[1].models.generate_content.side_effect = [SimpleNamespace(text="invalid"), failure]
    with pytest.raises(expected):module.read_prescribed_investigations(image_bytes())
    assert offline[1].models.generate_content.call_count == 2


def test_unexpected_failure_sanitized(offline):
    offline[1].models.generate_content.side_effect = RuntimeError("secret response")
    with pytest.raises(module.InvestigationAPIError) as caught:module.read_prescribed_investigations(image_bytes())
    assert "secret" not in str(caught.value);offline[1].models.generate_content.assert_called_once()


def test_quality_review_and_pure_helpers(offline):
    original = response(mention(), issues=["blurred"])
    module.validate_investigations_response(original)
    assert normalize(original)["investigations"][0]["needs_review"] is True
    offline[0].assert_not_called()
