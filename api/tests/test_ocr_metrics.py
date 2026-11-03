"""Numeric-only timings, duplicate guards and unchanged OCR output; offline SDK."""
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.genai import errors

from api.dependencies import reader
from api.main import create_app
from api.ocr_metrics import Measurements,log_metrics
from api.tests.test_prescriptions import HEADERS,make_client,upload,post
from api.tests.test_smoke import FIXTURE
from fastapi.testclient import TestClient


def sdk(monkeypatch,responses):
    factory=MagicMock()
    client=factory.return_value.__enter__.return_value
    client.models.generate_content.side_effect=responses
    monkeypatch.setattr(reader.genai,"Client",factory)
    monkeypatch.setattr(reader,"_configuration",lambda:("fake-offline-key","fake-offline-model"))
    return factory,client


def test_stages_count_schema_retry_without_changing_records(monkeypatch):
    _,client=sdk(monkeypatch,[SimpleNamespace(text="invalid-json"),SimpleNamespace(text="[]")])
    metrics=Measurements()
    with metrics.scope():
        assert reader.read_prescription(FIXTURE.read_bytes())==[]
    values=metrics.snapshot()
    assert values["gemini_sdk_invocations"]==2 and values["malformed_response_retries"]==1
    assert client.models.generate_content.call_count==2
    for key in ("image_validation_ms","client_setup_ms","gemini_request_ms","normalization_ms"):
        assert values[key]>=0
    assert "provider_http_requests" not in values
    assert "fake-offline-key" not in json.dumps(values)


def test_api_failure_one_invocation_and_timing_is_retained(monkeypatch):
    factory,_=sdk(monkeypatch,[errors.ServerError(503,{"message":"fake-medical-private"})])
    metrics=Measurements()
    with metrics.scope(),pytest.raises(reader.PrescriptionAPIError):
        reader.read_prescription(FIXTURE.read_bytes())
    assert metrics.snapshot()["gemini_sdk_invocations"]==1
    assert metrics.snapshot()["malformed_response_retries"]==0
    assert metrics.snapshot()["gemini_request_ms"]>=0
    assert factory.call_args.kwargs["http_options"].retry_options.attempts==1


def test_metrics_allowlist_ignores_source_fields_and_observer_failure(monkeypatch,caplog):
    caplog.set_level(logging.INFO,logger="api.ocr_metrics")
    metrics=Measurements()
    metrics.record("patient_name",123)
    metrics.record("gemini_request_ms",float("nan"))
    metrics.record("gemini_request_ms","fake-medical-private")
    log_metrics("extraction",{"patient_name":"fake-medical-private","api_key":"fake-key","gemini_request_ms":7})
    assert "gemini_request_ms" in caplog.text
    assert "patient_name" not in metrics.snapshot()
    assert "fake-medical-private" not in caplog.text and "fake-key" not in caplog.text
    sdk(monkeypatch,[SimpleNamespace(text="[]")])
    def broken(*args):
        raise RuntimeError("telemetry failure")
    with reader._timing_scope(broken):
        assert reader.read_prescription(FIXTURE.read_bytes())==[]


def test_metrics_scope_is_thread_local_and_resets():
    barrier=threading.Barrier(2)
    def collect(number):
        metrics=Measurements()
        with metrics.scope():
            barrier.wait(timeout=5)
            reader._observe("gemini_sdk_invocations",number)
        reader._observe("gemini_sdk_invocations",999)
        return metrics.snapshot()["gemini_sdk_invocations"]
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(collect,[1,2]))==[1,2]


def test_api_reports_upload_and_extraction_timings(monkeypatch):
    sdk(monkeypatch,[SimpleNamespace(text="[]")])
    app=create_app()
    client=TestClient(app,base_url="https://localhost",headers=HEADERS)
    client.post("/api/session")
    state=upload(client,FIXTURE.read_bytes())
    metrics=state["performance"]
    assert metrics["image_bytes"]==553584 and metrics["image_width"]==541 and metrics["image_height"]==721
    assert metrics["upload_ms"]>=metrics["upload_validation_ms"]>=0
    result=post(client,state,"analyze").json()
    metrics=result["performance"]
    assert result["status"]=="succeeded" and result["records"]==[]
    assert metrics["gemini_sdk_invocations"]==1
    assert metrics["server_processing_ms"]>=metrics["server_extraction_ms"]>=metrics["gemini_request_ms"]
    assert metrics["malformed_response_retries"]==0
    assert "records" not in metrics and "analysis_id" not in metrics


def test_concurrent_duplicate_analyze_is_detected_without_second_extraction():
    entered=threading.Event();finish=threading.Event();calls=[]
    def extract(_):
        calls.append(1);entered.set()
        assert finish.wait(5)
        return []
    client,_=make_client(extract)
    state=upload(client)
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(post,client,state,"analyze")
        assert entered.wait(5)
        assert post(client,state,"analyze").status_code==409
        finish.set()
        result=first.result(timeout=5).json()
    assert len(calls)==1 and result["performance"]["duplicate_analysis_rejections"]==1
    assert post(client,result,"analyze").status_code==409


def test_explicit_failed_retry_is_distinct_from_schema_retry_and_duplicate(monkeypatch):
    sdk(monkeypatch,[errors.ServerError(503,{"message":"fake-private"}),SimpleNamespace(text="[]")])
    client=TestClient(create_app(),base_url="https://localhost",headers=HEADERS)
    client.post("/api/session")
    first=post(client,upload(client,FIXTURE.read_bytes()),"analyze").json()
    assert first["status"]=="failed" and first["performance"]["analysis_attempts"]==1
    second=post(client,first,"analyze").json()
    assert second["status"]=="succeeded"
    assert second["performance"]["analysis_attempts"]==2
    assert second["performance"]["total_gemini_sdk_invocations"]==2
    assert second["performance"]["malformed_response_retries"]==0
    assert second["performance"]["duplicate_analysis_rejections"]==0
