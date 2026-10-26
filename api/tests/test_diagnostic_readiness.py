"""13G readiness audit. Every provider response is synthetic and offline."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors

from api.dependencies import reader
from api.smoke.diagnostics import safe_failure_diagnostics
from api.smoke.persistence import persist_result
from api.smoke.server import create_smoke_app
from api.tests.test_smoke import FIXTURE, analyze, client_for, upload


@pytest.mark.parametrize("error,category,code,upstream",[
    (errors.ClientError(400,{}),"provider_bad_request",400,"ClientError"),
    (errors.ClientError(401,{}),"authentication_error",401,"ClientError"),
    (errors.ClientError(403,{}),"permission_error",403,"ClientError"),
    (errors.ClientError(404,{}),"model_or_resource_unavailable",404,"ClientError"),
    (errors.ClientError(422,{}),"provider_client_error",422,"ClientError"),
    (errors.ClientError(429,{}),"quota_or_rate_limit",429,"ClientError"),
    (errors.ServerError(500,{}),"provider_server_error",500,"ServerError"),
    (errors.ServerError(503,{}),"provider_server_error",503,"ServerError"),
    (httpx.ReadTimeout("fake-private-content"),"network_timeout",None,"TimeoutError"),
    (httpx.ConnectError("fake-private-content"),"network_error",None,"HTTPError"),
])
def test_actual_reader_wraps_without_losing_captured_status(monkeypatch,tmp_path,error,category,code,upstream):
    monkeypatch.setattr(reader,"_configuration",lambda:("fake-offline-key","gemini-offline-test"))
    factory=MagicMock()
    sdk=factory.return_value.__enter__.return_value
    sdk.models.generate_content.side_effect=error
    monkeypatch.setattr(reader.genai,"Client",factory)
    marker=tmp_path/"synthetic-attempt.json"
    client=client_for(create_smoke_app("live",result_path=marker))
    result=analyze(client,upload(client,FIXTURE.read_bytes()).json()).json()
    assert result["status"] == "failed" and result["error"]["category"] == "api_error"
    diagnostics=json.loads(marker.read_text())["diagnostics"]
    assert diagnostics["category"] == category
    assert diagnostics["provider_http_status"] == code
    assert diagnostics["upstream_exception_type"] == upstream
    assert sdk.models.generate_content.call_count == 1  # no API/transport-error retry
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert sdk.models.generate_content.call_args.kwargs["model"] == "gemini-offline-test"
    assert "fake-private-content" not in marker.read_text()
    assert "fake-offline-key" not in marker.read_text()


def test_existing_schema_retry_is_explicitly_detected_not_hidden(monkeypatch):
    monkeypatch.setattr(reader,"_configuration",lambda:("fake-offline-key","gemini-offline-test"))
    factory=MagicMock()
    sdk=factory.return_value.__enter__.return_value
    sdk.models.generate_content.side_effect=[SimpleNamespace(text="bad JSON"),SimpleNamespace(text="[]")]
    monkeypatch.setattr(reader.genai,"Client",factory)
    assert reader.read_prescription(FIXTURE.read_bytes()) == []
    assert sdk.models.generate_content.call_count == 2  # retained medical extraction contract


def test_status_survives_outer_transport_wrapper_and_both_chain_branches():
    api=errors.ClientError(429,{"message":"fake-private-content"})
    transport=httpx.ConnectError("fake-private-content")
    transport.__context__=api
    outer=reader.PrescriptionAPIError("safe boundary")
    outer.__cause__=ValueError("unrelated wrapper")
    outer.__context__=transport
    assert safe_failure_diagnostics(outer)["provider_http_status"] == 429


def test_http_status_error_is_not_misclassified_as_network_failure():
    request=httpx.Request("POST","https://offline.invalid/never-called",headers={"secret":"fake-private-content"})
    response=httpx.Response(403,request=request,text="fake-private-content")
    error=httpx.HTTPStatusError("fake-private-content",request=request,response=response)
    result=safe_failure_diagnostics(error)
    assert result["provider_http_status"] == 403 and result["category"] == "permission_error"
    assert "fake-private-content" not in json.dumps(result)


def test_atomic_persistence_failure_keeps_consumed_guard(monkeypatch,tmp_path):
    marker=tmp_path/"guard.json"
    original=b'{"status":"started","extractor_invocations":1}'
    marker.write_bytes(original)
    def denied(*args):
        raise OSError("synthetic replacement failure")
    monkeypatch.setattr(os,"replace",denied)
    with pytest.raises(OSError):
        persist_result(marker,{"status":"failed","diagnostics":{"provider_http_status":429}})
    assert marker.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_completed_diagnostics_survive_process_exit(tmp_path):
    destination=tmp_path/"process-result.json"
    code='''
import socket,sys
from unittest.mock import MagicMock
from api.dependencies import reader
from google.genai import errors
from api.smoke.server import create_smoke_app
from api.tests.test_smoke import FIXTURE,analyze,client_for,upload
def no_network(*a,**k): raise AssertionError("network forbidden")
socket.create_connection=no_network
reader._configuration=lambda:("fake-offline-key","gemini-offline-test")
factory=MagicMock()
factory.return_value.__enter__.return_value.models.generate_content.side_effect=errors.ServerError(503,{"message":"fake-private-content"})
reader.genai.Client=factory
client=client_for(create_smoke_app("live",result_path=sys.argv[1]))
result=analyze(client,upload(client,FIXTURE.read_bytes()).json()).json()
assert result["status"]=="failed"
'''
    env={k:v for k,v in os.environ.items() if k not in ("GEMINI_API_KEY","GEMINI_MODEL")}
    finished=subprocess.run([sys.executable,"-c",code,str(destination)],
        cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,text=True,timeout=30)
    assert finished.returncode == 0, "Offline subprocess failed"
    report=json.loads(destination.read_text())
    assert report["status"] == "failed"
    assert report["diagnostics"]["provider_http_status"] == 503
    assert report["diagnostics"]["upstream_exception_type"] == "ServerError"
    assert "fake-private-content" not in destination.read_text()
    assert "fake-offline-key" not in destination.read_text()
    with pytest.raises(RuntimeError,match="already recorded"):
        create_smoke_app("live",result_path=destination)


def test_existing_consumed_original_guard_cannot_be_reused():
    # Read only: no synthetic test may ever replace or remove this original file.
    original=Path(__file__).resolve().parents[1]/"smoke/live_result.json"
    if not original.exists():
        pytest.skip("Original local attempt artifact is not present in this checkout")
    before=original.read_bytes()
    with pytest.raises(RuntimeError,match="already recorded"):
        create_smoke_app("live")
    assert original.read_bytes() == before
