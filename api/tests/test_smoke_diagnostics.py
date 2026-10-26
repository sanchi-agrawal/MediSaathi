"""Synthetic exceptions only. No network requests or production guard writes."""
import json

import httpx
import pytest
from google.genai import errors

from api.dependencies import reader
from api.smoke.diagnostics import safe_failure_diagnostics
from api.smoke.server import create_smoke_app
from api.tests.test_smoke import FIXTURE, analyze, client_for, upload


def wrapped(upstream):
    try:
        raise upstream
    except Exception:
        try:
            raise reader.PrescriptionAPIError("safe reader error") from None
        except reader.PrescriptionAPIError as error:
            return error


@pytest.mark.parametrize("status,category",[(429,"quota_or_rate_limit"),(401,"authentication_error"),
    (403,"permission_error"),(404,"model_or_resource_unavailable"),(400,"provider_bad_request"),
    (503,"provider_server_error")])
def test_sanitized_provider_status_through_suppressed_context(status,category):
    upstream=errors.APIError(status,{"error":{"message":"DO-NOT-LOG-KEY-OR-BODY","status":"UNTRUSTED_SECRET"}})
    result=safe_failure_diagnostics(wrapped(upstream))
    assert result["category"] == category
    assert result["provider_http_status"] == status
    assert result["provider_response_observed"]
    assert result["exception_type"] == "PrescriptionAPIError"
    assert "DO-NOT-LOG" not in json.dumps(result) and "UNTRUSTED_SECRET" not in json.dumps(result)


@pytest.mark.parametrize("upstream,category",[(httpx.ReadTimeout("DO-NOT-LOG"),"network_timeout"),
    (httpx.ConnectError("DO-NOT-LOG"),"network_error"),(TimeoutError("DO-NOT-LOG"),"network_timeout")])
def test_transport_errors_do_not_claim_provider_response(upstream,category):
    result=safe_failure_diagnostics(wrapped(upstream))
    assert result["category"] == category
    assert result["provider_http_status"] is None and not result["provider_response_observed"]
    assert "DO-NOT-LOG" not in json.dumps(result)


def test_preserve_uncertainty_without_upstream_context():
    result=safe_failure_diagnostics(reader.PrescriptionAPIError("DO-NOT-LOG"))
    assert result["category"] == "api_or_transport_error_unknown"
    assert result["provider_http_status"] is None


@pytest.mark.parametrize("error,category",[(reader.ModelResponseError("DO-NOT-LOG"),"invalid_response"),
    (reader.ReaderConfigurationError("DO-NOT-LOG"),"configuration_error"),
    (reader.ImageInputError("DO-NOT-LOG"),"image_validation_error"),
    (ValueError("DO-NOT-LOG"),"unexpected_backend_error")])
def test_local_failure_categories(error,category):
    result=safe_failure_diagnostics(error)
    assert result["category"] == category
    assert "DO-NOT-LOG" not in json.dumps(result)


def test_cycles_are_bounded():
    error=reader.PrescriptionAPIError("DO-NOT-LOG")
    error.__context__=error
    assert safe_failure_diagnostics(error)["category"] == "api_or_transport_error_unknown"


def test_runner_logs_only_safe_fields_and_preserves_guard_on_failure(monkeypatch,tmp_path,caplog):
    calls=[]
    def fake_reader(data):
        calls.append(data)
        raise wrapped(errors.APIError(429,{"error":{"message":"DO-NOT-LOG"}}))
    monkeypatch.setattr(reader,"read_prescription",fake_reader)
    marker=tmp_path/"offline-only.json"
    client=client_for(create_smoke_app("live",result_path=marker))
    result=analyze(client,upload(client,FIXTURE.read_bytes()).json()).json()
    assert result["status"] == "failed" and result["error"]["category"] == "api_error"
    report=json.loads(marker.read_text())
    assert report["diagnostics"]["provider_http_status"] == 429
    assert report["diagnostics"]["category"] == "quota_or_rate_limit"
    assert "DO-NOT-LOG" not in marker.read_text() and "DO-NOT-LOG" not in caplog.text
    assert len(calls) == 1
    assert not client.get("/api/smoke/status").json()["live_attempt_available"]
    # The runner must still refuse to start with the consumed synthetic marker.
    with pytest.raises(RuntimeError,match="already recorded"):
        create_smoke_app("live",result_path=marker)
