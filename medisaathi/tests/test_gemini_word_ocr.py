"""Offline adapter tests: fictional generated images and a mocked SDK client."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import httpx
import pytest
from google.genai import errors
from PIL import Image

import gemini_word_ocr as word


@pytest.mark.parametrize("code", [400, 403, 404, 429, 500, None])
def test_http_status_diagnostics(code, offline):
    failure = errors.APIError(code, {"error": {"message": "private-body https://secret"}})
    offline[1].models.generate_content.side_effect = failure
    expected = word.WordQuotaError if code == 429 else word.WordAPIError
    with pytest.raises(expected) as captured:
        word.transcribe_word(image_bytes())
    assert captured.value.http_status_code == code
    assert captured.value.failure_stage == "api_request"
    assert "private-body" not in str(captured.value)
    assert offline[1].models.generate_content.call_count == (3 if code == 500 else 1)


@pytest.mark.parametrize("error_type", [word.WordAPIError, word.WordQuotaError, word.WordNetworkError])
@pytest.mark.parametrize("code", [True, "403", 0, 600, 403.0, None])
def test_diagnostic_validation_and_old_construction(error_type, code):
    old = error_type("safe message")
    assert isinstance(old, word.WordAPIError)
    assert str(old) == "safe message"
    assert old.http_status_code is None and old.failure_stage is None
    error = error_type("safe", http_status_code=code, failure_stage="https://unsafe")
    assert error.http_status_code is None and error.failure_stage is None


def test_response_validation_stage(offline):
    offline[1].models.generate_content.return_value.text = 42
    with pytest.raises(word.WordAPIError) as captured:
        word.transcribe_word(image_bytes())
    assert captured.value.failure_stage == "response_validation"
    assert captured.value.http_status_code is None


def test_network_stage_without_status(offline):
    offline[1].models.generate_content.side_effect = httpx.ConnectError("private")
    with pytest.raises(word.WordNetworkError) as captured:
        word.transcribe_word(image_bytes())
    assert captured.value.http_status_code is None
    assert captured.value.failure_stage == "api_request"


def image_bytes(format="PNG"):
    output = BytesIO()
    with Image.new("RGB", (8, 8), "white") as image:
        image.save(output, format=format)
    return output.getvalue()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(word, "sleep", MagicMock())
    factory = MagicMock()
    monkeypatch.setattr(word.genai, "Client", factory)
    monkeypatch.setattr(word, "dotenv_values", lambda path: {
        "GEMINI_API_KEY": "fictional-secret", "GEMINI_MODEL": "fictional-model"})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("Network forbidden"))
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.return_value = SimpleNamespace(text="Fictword")
    return factory, client


@pytest.mark.parametrize("code", [500, 502, 503, 504])
@pytest.mark.parametrize("retries", [1, 2])
def test_transient_success_after_retry(code, retries, offline):
    failure = errors.APIError(code, {"error": {"message": "private-secret"}})
    request = offline[1].models.generate_content
    request.side_effect = [failure] * retries + [SimpleNamespace(text="Fictword")]
    assert word.transcribe_word(image_bytes()) == "Fictword"
    assert request.call_count == retries + 1
    assert word.sleep.call_args_list == [call(delay) for delay in (1, 2)[:retries]]
    assert all(c == request.call_args_list[0] for c in request.call_args_list)
    offline[0].return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_retry_exhaustion(code, offline):
    request = offline[1].models.generate_content
    request.side_effect = errors.APIError(code, {"error": {"message": "private-secret"}})
    with pytest.raises(word.WordAPIError) as captured:
        word.transcribe_word(image_bytes())
    assert request.call_count == 3
    assert word.sleep.call_args_list == [call(1), call(2)]
    assert captured.value.http_status_code == code
    assert captured.value.failure_stage == "api_request"
    assert "private-secret" not in str(captured.value)


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429, 501, 505, None])
def test_nonretryable_http(code, offline):
    offline[1].models.generate_content.side_effect = errors.APIError(code, {})
    expected = word.WordQuotaError if code == 429 else word.WordAPIError
    with pytest.raises(expected):
        word.transcribe_word(image_bytes())
    offline[1].models.generate_content.assert_called_once()
    word.sleep.assert_not_called()


def test_immediate_success_without_sleep(offline):
    assert word.transcribe_word(image_bytes()) == "Fictword"
    offline[1].models.generate_content.assert_called_once()
    word.sleep.assert_not_called()


@pytest.mark.parametrize("failure", [httpx.ConnectError("private"), TimeoutError("private")])
def test_network_no_sleep(failure, offline):
    offline[1].models.generate_content.side_effect = failure
    with pytest.raises(word.WordNetworkError):
        word.transcribe_word(image_bytes())
    offline[1].models.generate_content.assert_called_once()
    word.sleep.assert_not_called()


def test_validation_failures_no_sleep(monkeypatch, offline):
    with pytest.raises(word.WordImageError):
        word.transcribe_word(b"corrupt")
    monkeypatch.setattr(word, "dotenv_values", lambda path: {})
    with pytest.raises(word.WordConfigurationError):
        word.transcribe_word(image_bytes())
    offline[0].assert_not_called()
    word.sleep.assert_not_called()


def test_response_validation_no_sleep(offline):
    offline[1].models.generate_content.return_value.text = 123
    with pytest.raises(word.WordAPIError) as captured:
        word.transcribe_word(image_bytes())
    assert captured.value.failure_stage == "response_validation"
    offline[1].models.generate_content.assert_called_once()
    word.sleep.assert_not_called()


def test_nonretryable_after_transient_stops_immediately(offline):
    offline[1].models.generate_content.side_effect = [
        errors.APIError(503, {}), errors.APIError(429, {})]
    with pytest.raises(word.WordQuotaError) as captured:
        word.transcribe_word(image_bytes())
    assert captured.value.http_status_code == 429
    assert offline[1].models.generate_content.call_count == 2
    word.sleep.assert_called_once_with(1)


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_transcription_request(format, mime, offline):
    factory, client = offline
    image = image_bytes(format)
    assert word.transcribe_word(image) == "Fictword"
    client.models.generate_content.assert_called_once()
    request = client.models.generate_content.call_args.kwargs
    assert request["model"] == "fictional-model"
    assert request["contents"][1].inline_data.data == image
    assert request["contents"][1].inline_data.mime_type == mime
    assert request["config"].response_mime_type == "text/plain"
    assert request["config"].response_json_schema is None
    assert "Do not correct spelling" in request["config"].system_instruction
    options = factory.call_args.kwargs
    assert options["http_options"].retry_options.attempts == 1
    assert options["vertexai"] is False and options["enterprise"] is False
    factory.return_value.__exit__.assert_called_once()


def test_preserves_nonempty_text_exactly(offline):
    offline[1].models.generate_content.return_value.text = "  Fict-wrd 10\n"
    assert word.transcribe_word(image_bytes()) == "  Fict-wrd 10\n"


@pytest.mark.parametrize("text", [None, "", " \n\t"])
def test_empty_response(text, offline):
    offline[1].models.generate_content.return_value.text = text
    assert word.transcribe_word(image_bytes()) == ""
    offline[1].models.generate_content.assert_called_once()


def test_invalid_response_type(offline):
    offline[1].models.generate_content.return_value.text = 123
    with pytest.raises(word.WordAPIError, match="invalid transcription"):
        word.transcribe_word(image_bytes())


@pytest.mark.parametrize("image", [None, b"", "image", b"invalid", b"\xff\xd8"])
def test_invalid_input_before_client(image, offline):
    with pytest.raises(word.WordImageError):
        word.transcribe_word(image)
    offline[0].assert_not_called()


def test_unsupported_format(offline):
    with pytest.raises(word.WordImageError, match="PNG or JPEG"):
        word.transcribe_word(image_bytes("GIF"))
    offline[0].assert_not_called()


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_corrupt_image(format, offline):
    with pytest.raises(word.WordImageError):
        word.transcribe_word(image_bytes(format)[:30])
    offline[0].assert_not_called()


@pytest.mark.parametrize("limit,value", [("MAX_IMAGE_BYTES", 10), ("MAX_IMAGE_PIXELS", 4)])
def test_large_image(limit, value, monkeypatch, offline):
    monkeypatch.setattr(word, limit, value)
    with pytest.raises(word.WordImageError):
        word.transcribe_word(image_bytes())
    offline[0].assert_not_called()


@pytest.mark.parametrize("missing", ["GEMINI_API_KEY", "GEMINI_MODEL"])
def test_missing_configuration(missing, monkeypatch, offline):
    values = {"GEMINI_API_KEY": "fictional-secret", "GEMINI_MODEL": "fictional-model"}
    values.pop(missing)
    monkeypatch.setattr(word, "dotenv_values", lambda path: values)
    with pytest.raises(word.WordConfigurationError):
        word.transcribe_word(image_bytes())
    offline[0].assert_not_called()


def test_environment_precedence(monkeypatch, offline):
    monkeypatch.setenv("GEMINI_API_KEY", "fictional-env-secret")
    monkeypatch.setenv("GEMINI_MODEL", "fictional-env-model")
    word.transcribe_word(image_bytes())
    assert offline[0].call_args.kwargs["api_key"] == "fictional-env-secret"
    assert offline[1].models.generate_content.call_args.kwargs["model"] == "fictional-env-model"


@pytest.mark.parametrize("failure", [
    errors.APIError(429, {"error": {"message": "fictional-secret"}}),
    errors.APIError(403, {"error": {"message": "fictional-secret"}}),
    httpx.ConnectError("fictional-secret"), httpx.ReadTimeout("fictional-secret"),
])
def test_api_failures_no_retry_or_secret(failure, offline):
    offline[1].models.generate_content.side_effect = failure
    with pytest.raises(word.WordAPIError) as captured:
        word.transcribe_word(image_bytes())
    assert "fictional-secret" not in str(captured.value)
    assert captured.value.__suppress_context__
    offline[1].models.generate_content.assert_called_once()
    offline[0].return_value.__exit__.assert_called_once()


def test_client_creation_failure(offline):
    offline[0].side_effect = httpx.ConnectError("fictional-secret")
    with pytest.raises(word.WordAPIError, match="Could not reach"):
        word.transcribe_word(image_bytes())
    offline[1].models.generate_content.assert_not_called()


def test_evaluator_connection_with_fictional_data(tmp_path, offline):
    from evaluate_ocr import evaluate_ocr

    (tmp_path / "Test_Set").mkdir()
    (tmp_path / "Test_Set" / "fictional.png").write_bytes(image_bytes())
    (tmp_path / "Test_Label.csv").write_text("Images,Text\nfictional.png,Fictword\n", encoding="utf-8")
    report = evaluate_ocr(tmp_path, word.transcribe_word, sample_size=1, seed=42)
    assert report["exact_match_accuracy"] == 1
    assert report["character_error_rate"] == 0
    offline[1].models.generate_content.assert_called_once()


@pytest.mark.parametrize("failure,expected_type,category", [
    (errors.APIError(429, {"error": {"message": "private-secret"}}), word.WordQuotaError, "quota_or_rate_limit"),
    (errors.APIError(403, {"error": {"message": "private-secret"}}), word.WordAPIError, "api_error"),
    (httpx.ConnectError("private-secret"), word.WordNetworkError, "network_error"),
])
def test_typed_failures_reach_evaluator(tmp_path, offline, failure, expected_type, category):
    from evaluate_ocr import evaluate_ocr

    offline[1].models.generate_content.side_effect = failure
    with pytest.raises(expected_type) as captured:
        word.transcribe_word(image_bytes())
    assert isinstance(captured.value, word.WordAPIError)  # Old catch blocks still work.
    assert "private-secret" not in str(captured.value)
    offline[1].models.generate_content.reset_mock()
    (tmp_path / "Test_Set").mkdir()
    (tmp_path / "Test_Set" / "a.png").write_bytes(image_bytes())
    (tmp_path / "Test_Label.csv").write_text("Images,Text\na.png,Fictional\n", encoding="utf-8")
    row = evaluate_ocr(tmp_path, word.transcribe_word)["records"][0]
    assert row["error"] == "prediction_failed"
    assert row["error_category"] == category
    assert "private-secret" not in str(row)
    offline[1].models.generate_content.assert_called_once()


def test_blank_adapter_response_reaches_evaluator_as_success(tmp_path, offline):
    from evaluate_ocr import evaluate_ocr

    offline[1].models.generate_content.return_value.text = " \n"
    (tmp_path / "Test_Set").mkdir()
    (tmp_path / "Test_Set" / "a.png").write_bytes(image_bytes())
    (tmp_path / "Test_Label.csv").write_text("Images,Text\na.png,Fictional\n", encoding="utf-8")
    report = evaluate_ocr(tmp_path, word.transcribe_word)
    row = report["records"][0]
    assert row["prediction"] == "" and row["empty_prediction"] is True
    assert row["error"] is None and row["error_category"] is None
    assert report["error_count"] == 0
    assert report["character_error_rate"] == 1
