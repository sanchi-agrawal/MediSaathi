"""Fictional offline fixtures; no API credentials or network are needed."""

import copy
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
from google.genai import errors
from PIL import Image

import reader

import pytest

from reader import FIELDS, ImageInputError, ModelResponseError, normalize_model_response, read_prescription


@pytest.fixture
def medicine():
    return dict(raw_text="Tab Fictional-A; ingredient Example-X; 10mg; BD; 3 days; after food",
                name="Fictional-A", salt="Example-X", strength="10mg", form="tablet",
                frequency_pattern="BD", duration_days=3, timing="after food",
                confidence=0.95, needs_review=False)


@pytest.fixture(autouse=True)
def offline_client(monkeypatch):
    # Every test gets a fake client and fake credentials; no real .env is read.
    factory = MagicMock()
    monkeypatch.setattr(reader.genai, "Client", factory)
    monkeypatch.setattr(reader, "dotenv_values", lambda path: {
        "GEMINI_API_KEY": "fictional-secret", "GEMINI_MODEL": "fictional-model"
    })
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    # Also fail closed if code accidentally bypasses the mocked SDK client.
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("Network forbidden"))
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.return_value = SimpleNamespace(text="[]")
    return factory, client


def image_bytes(format="PNG"):
    output = BytesIO()
    with Image.new("RGB", (4, 4), "white") as image:
        image.save(output, format=format)
    return output.getvalue()


def test_valid_record_preserved_without_mutation(medicine):
    original = copy.deepcopy(medicine)
    assert normalize_model_response([medicine]) == [original]
    assert medicine == original
    assert normalize_model_response(json.dumps([medicine])) == [original]


def test_missing_fields_become_none():
    result = normalize_model_response([{"raw_text": "???? BD", "frequency_pattern": "BD"}])[0]
    assert set(result) == set(FIELDS)
    assert result["name"] is None and result["confidence"] is None
    assert result["frequency_pattern"] == "BD"
    assert result["needs_review"] is True


def test_blank_and_uncertain_fields(medicine):
    medicine["name"] = "  "
    medicine["needs_review"] = False
    result = normalize_model_response([medicine])[0]
    assert result["name"] is None
    assert result["needs_review"] is True


@pytest.mark.parametrize("changes", [{"confidence": 0.5}, {"needs_review": True}, {"salt": None}])
def test_review_rules(medicine, changes):
    medicine.update(changes)
    assert normalize_model_response([medicine])[0]["needs_review"] is True


@pytest.mark.parametrize("response", ["not json", "{}", None, 42, [None], [{"extra": 1}]])
def test_malformed_response(response):
    with pytest.raises(ModelResponseError):
        normalize_model_response(response)


@pytest.mark.parametrize("field,value", [
    ("duration_days", True), ("duration_days", "3"), ("duration_days", -1),
    ("confidence", True), ("confidence", float("nan")), ("confidence", 1.1),
    ("needs_review", "false"), ("name", 123), ("form", "injection"),
])
def test_invalid_field_types(medicine, field, value):
    medicine[field] = value
    with pytest.raises(ModelResponseError):
        normalize_model_response([medicine])


def test_empty_list_is_no_detected_records():
    assert normalize_model_response([]) == []


@pytest.mark.parametrize("image", [None, b"", "image", b"garbage", b"\x89PNG\r\n\x1a\n"])
def test_empty_corrupt_or_invalid_image(image, offline_client):
    with pytest.raises(ImageInputError):
        read_prescription(image)
    offline_client[0].assert_not_called()


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_supported_images_and_schema(format, mime, medicine, offline_client):
    factory, client = offline_client
    client.models.generate_content.return_value.text = json.dumps([medicine])
    data = image_bytes(format)
    assert read_prescription(data) == [medicine]
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "fictional-model"
    assert call["contents"][1].inline_data.mime_type == mime
    assert call["contents"][1].inline_data.data == data
    schema = call["config"].response_json_schema["items"]
    assert set(schema["properties"]) == set(FIELDS)
    assert set(schema["required"]) == set(FIELDS)
    assert schema["additionalProperties"] is False
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1
    factory.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_truncated_image(format, offline_client):
    with pytest.raises(ImageInputError):
        read_prescription(image_bytes(format)[:30])
    offline_client[0].assert_not_called()


def test_unsupported_image(offline_client):
    with pytest.raises(ImageInputError, match="Unsupported"):
        read_prescription(image_bytes("GIF"))
    offline_client[0].assert_not_called()


def test_file_size_limit(monkeypatch, offline_client):
    monkeypatch.setattr(reader, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(ImageInputError, match="10 MiB"):
        read_prescription(image_bytes())
    offline_client[0].assert_not_called()


def test_pixel_limit(monkeypatch, offline_client):
    monkeypatch.setattr(reader, "MAX_IMAGE_PIXELS", 4)
    with pytest.raises(ImageInputError, match="pixel"):
        read_prescription(image_bytes())
    offline_client[0].assert_not_called()


@pytest.mark.parametrize("missing", ["GEMINI_API_KEY", "GEMINI_MODEL"])
def test_missing_configuration(missing, monkeypatch, offline_client):
    config = {"GEMINI_API_KEY": "fictional-secret", "GEMINI_MODEL": "fictional-model"}
    config.pop(missing)
    monkeypatch.setattr(reader, "dotenv_values", lambda path: config)
    with pytest.raises(reader.ReaderConfigurationError):
        read_prescription(image_bytes())
    offline_client[0].assert_not_called()


def test_invalid_json_retries_once(medicine, offline_client):
    client = offline_client[1]
    client.models.generate_content.side_effect = [
        SimpleNamespace(text="bad JSON"), SimpleNamespace(text=json.dumps([medicine]))]
    assert read_prescription(image_bytes()) == [medicine]
    assert client.models.generate_content.call_count == 2


@pytest.mark.parametrize("text", ["bad JSON", "{}", None, '[{"confidence": 99}]'])
def test_invalid_output_stops_after_retry(text, offline_client):
    client = offline_client[1]
    client.models.generate_content.return_value.text = text
    with pytest.raises(ModelResponseError, match="one retry"):
        read_prescription(image_bytes())
    assert client.models.generate_content.call_count == 2


def test_missing_response_fields_are_normalized(offline_client):
    offline_client[1].models.generate_content.return_value.text = '[{"raw_text":"???? BD"}]'
    record = read_prescription(image_bytes())[0]
    assert set(record) == set(FIELDS)
    assert record["name"] is None and record["needs_review"] is True


@pytest.mark.parametrize("failure", [
    errors.APIError(429, {"error": {"message": "fictional-secret"}}),
    errors.APIError(403, {"error": {"message": "fictional-secret"}}),
    httpx.ConnectError("fictional-secret"),
    httpx.ReadTimeout("fictional-secret"),
])
def test_api_failures_are_safe_and_not_retried(failure, offline_client):
    client = offline_client[1]
    client.models.generate_content.side_effect = failure
    with pytest.raises(reader.PrescriptionAPIError) as captured:
        read_prescription(image_bytes())
    assert "fictional-secret" not in str(captured.value)
    assert captured.value.__suppress_context__
    assert client.models.generate_content.call_count == 1


def test_client_creation_failure_is_safe(offline_client):
    offline_client[0].side_effect = httpx.ConnectError("fictional-secret")
    with pytest.raises(reader.PrescriptionAPIError, match="Could not reach"):
        read_prescription(image_bytes())
