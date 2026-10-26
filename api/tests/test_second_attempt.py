"""13H offline preparation tests: real SDK serialization, mock HTTP transport."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import httpx
import pytest
from google import genai

from api.dependencies import reader
from api.smoke.second_attempt import (ATTEMPT_ID,MODEL,Attempt,AttemptBlocked,
    OneRequestTransport,create_diagnostic_app,extract_once,prepare)
from api.tests.test_smoke import FIXTURE, client_for, upload

REAL_CLIENT=genai.Client


def setup_attempt(tmp_path, *, authorized=False):
    first=tmp_path/"original.json"
    first.write_text(json.dumps({"status":"failed","extractor_invocations":1}))
    directory=tmp_path/"second"
    manifest=prepare(directory,fixture=FIXTURE,original_guard=first)
    if authorized:
        # SYNTHETIC authorization in an isolated temporary directory only.
        (directory/"execution_authorization.json").write_text(json.dumps({
            "attempt_id":ATTEMPT_ID,"fixture_sha256":manifest["fixture_sha256"],"model":MODEL,
            "max_provider_calls":1,"execution_authorized":True,"authorized_by":"user",
            "authorization_reference":"offline-test-only-not-live-authorization",
            "expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}))
    return Attempt(directory,fixture=FIXTURE,original_guard=first)


@pytest.fixture
def sdk(monkeypatch):
    # The API conftest blocks SDK calls by default. Permit the real serializer
    # here only with a per-test MockTransport; sockets remain prohibited.
    monkeypatch.setattr(genai,"Client",REAL_CLIENT)
    monkeypatch.setattr(reader,"_configuration",lambda:("fake-offline-key",MODEL))


def response_with_text(text):
    return httpx.Response(200,json={"candidates":[{"content":{"role":"model","parts":[{"text":text}]}}]})


def test_prepared_guard_is_disabled_and_never_resets_first(tmp_path):
    attempt=setup_attempt(tmp_path)
    before=attempt.original_guard.read_bytes()
    assert attempt.manifest["execution_authorized"] is False
    with pytest.raises(AttemptBlocked,match="disabled"):
        attempt.authorize()
    with pytest.raises(AttemptBlocked,match="disabled"):
        create_diagnostic_app(attempt)
    with pytest.raises(AttemptBlocked,match="disabled"):
        extract_once(FIXTURE.read_bytes(),attempt)
    assert not (attempt.directory/"consumed.json").exists()
    assert attempt.original_guard.read_bytes()==before


@pytest.mark.parametrize("mutation",[
    {"model":"other-model"},{"attempt_id":"different"},{"max_provider_calls":2},
    {"max_provider_calls":True},{"fixture_sha256":"wrong"},{"execution_authorized":False},
    {"authorization_reference":""},{"expires_at":"2000-01-01T00:00:00+00:00"}])
def test_mismatched_or_expired_authorization_refused(tmp_path,mutation):
    attempt=setup_attempt(tmp_path,authorized=True)
    path=attempt.directory/"execution_authorization.json"
    auth=json.loads(path.read_text());auth.update(mutation);path.write_text(json.dumps(auth))
    with pytest.raises(AttemptBlocked):
        attempt.authorize()
    assert not (attempt.directory/"consumed.json").exists()


def test_one_request_and_result_contains_no_content(tmp_path,sdk):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    def mock(request):
        calls.append(request)
        assert request.url.path==f"/v1beta/models/{MODEL}:generateContent"
        return response_with_text('[]')
    assert extract_once(FIXTURE.read_bytes(),attempt,transport=httpx.MockTransport(mock))==[]
    assert len(calls)==1
    report=json.loads((attempt.directory/"diagnostic_result.json").read_text())
    assert set(report)=={"attempt_id","status","category","provider_http_status","started_at","elapsed_seconds"}
    assert report["status"]=="succeeded"
    assert "fake-offline-key" not in json.dumps(report)
    assert (attempt.directory/"consumed.json").is_file()
    with pytest.raises(AttemptBlocked,match="consumed"):
        extract_once(FIXTURE.read_bytes(),attempt,transport=httpx.MockTransport(mock))
    assert len(calls)==1


@pytest.mark.parametrize("text",['bad JSON','{}','[{"invented_dose":99}]'])
def test_malformed_output_never_retries(tmp_path,sdk,text):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    def mock(request):
        calls.append(1)
        return response_with_text(text)
    with pytest.raises(reader.ModelResponseError):
        extract_once(FIXTURE.read_bytes(),attempt,transport=httpx.MockTransport(mock))
    assert len(calls)==1
    report=json.loads((attempt.directory/"diagnostic_result.json").read_text())
    assert report["category"]=="invalid_response"
    assert text not in json.dumps(report)


@pytest.mark.parametrize("code,category",[(400,"provider_bad_request"),(401,"authentication_error"),
    (403,"permission_error"),(404,"model_or_resource_unavailable"),(429,"quota_or_rate_limit"),
    (503,"provider_server_error")])
def test_provider_errors_single_call_safe_persistence(tmp_path,sdk,code,category):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    def mock(request):
        calls.append(1)
        return httpx.Response(code,json={"error":{"code":code,"message":"fake-sensitive-response"}})
    with pytest.raises(reader.PrescriptionAPIError):
        extract_once(FIXTURE.read_bytes(),attempt,transport=httpx.MockTransport(mock))
    assert len(calls)==1
    report=json.loads((attempt.directory/"diagnostic_result.json").read_text())
    assert report["category"]==category and report["provider_http_status"]==code
    assert "fake-sensitive-response" not in json.dumps(report)


@pytest.mark.parametrize("error",[httpx.ReadTimeout("fake-private"),httpx.ConnectError("fake-private")])
def test_network_failure_consumes_allowance_without_retry(tmp_path,sdk,error):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    def mock(request):
        calls.append(1)
        raise error
    with pytest.raises(reader.PrescriptionAPIError):
        extract_once(FIXTURE.read_bytes(),attempt,transport=httpx.MockTransport(mock))
    assert len(calls)==1
    assert (attempt.directory/"consumed.json").exists()
    report=(attempt.directory/"diagnostic_result.json").read_text()
    assert "fake-private" not in report


def test_concurrent_extractors_across_sessions_only_one_sends(tmp_path,sdk):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    entered=threading.Event();release=threading.Event()
    def mock(request):
        calls.append(1);entered.set()
        assert release.wait(5)
        return response_with_text('[]')
    def call():
        # Separate Attempt objects simulate separately constructed sessions.
        other=Attempt(attempt.directory,fixture=FIXTURE,original_guard=attempt.original_guard)
        try:
            return extract_once(FIXTURE.read_bytes(),other,transport=httpx.MockTransport(mock))
        except (AttemptBlocked,reader.ReaderConfigurationError):
            return "blocked"
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(call)
        assert entered.wait(5)
        second=pool.submit(call)
        assert second.result(timeout=5)=="blocked"
        release.set()
        assert first.result(timeout=5)==[]
    assert len(calls)==1
    assert json.loads((attempt.directory/"diagnostic_result.json").read_text())["status"]=="succeeded"


def test_cross_process_reservation_is_exclusive_and_persistent(tmp_path):
    attempt=setup_attempt(tmp_path,authorized=True)
    script='''
import sys
from api.smoke.second_attempt import Attempt,AttemptBlocked
a=Attempt(sys.argv[1],fixture=sys.argv[2],original_guard=sys.argv[3])
try: a.reserve()
except AttemptBlocked: raise SystemExit(3)
'''
    command=[sys.executable,"-c",script,str(attempt.directory),str(FIXTURE),str(attempt.original_guard)]
    env={k:v for k,v in os.environ.items() if k not in ("GEMINI_API_KEY","GEMINI_MODEL")}
    processes=[subprocess.Popen(command,cwd=Path(__file__).resolve().parents[2],env=env,
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    codes=[]
    for process in processes:
        process.communicate(timeout=30);codes.append(process.returncode)
    assert sorted(codes)==[0,3]
    fresh=Attempt(attempt.directory,fixture=FIXTURE,original_guard=attempt.original_guard)
    with pytest.raises(AttemptBlocked,match="consumed"):
        fresh.reserve()
    reservation=json.loads((attempt.directory/"consumed.json").read_text())
    assert reservation["provider_call_budget_consumed"]==1


def test_transport_rejects_second_physical_send_even_if_sdk_retries(tmp_path):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    transport=OneRequestTransport(attempt,httpx.MockTransport(lambda r:calls.append(1) or httpx.Response(200)))
    request=httpx.Request("POST",f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")
    transport.handle_request(request)
    with pytest.raises(AttemptBlocked,match="consumed"):
        transport.handle_request(request)
    assert len(calls)==1


def test_fixture_and_model_mismatch_do_not_consume_budget(tmp_path,sdk,monkeypatch):
    attempt=setup_attempt(tmp_path,authorized=True)
    with pytest.raises(reader.ImageInputError):
        extract_once(b"bad-image",attempt)
    monkeypatch.setattr(reader,"_configuration",lambda:("fake-offline-key","wrong-model"))
    with pytest.raises(reader.ReaderConfigurationError):
        extract_once(FIXTURE.read_bytes(),attempt)
    assert not (attempt.directory/"consumed.json").exists()


def test_startup_status_upload_do_not_invoke_sdk(tmp_path,monkeypatch):
    attempt=setup_attempt(tmp_path,authorized=True)
    def denied(*args,**kwargs):
        raise AssertionError("No SDK invocation allowed")
    monkeypatch.setattr(genai,"Client",denied)
    client=client_for(create_diagnostic_app(attempt))
    assert client.get("/api/diagnostic/status").status_code==200
    assert upload(client,FIXTURE.read_bytes()).status_code==200
    assert not (attempt.directory/"consumed.json").exists()


def test_new_guard_never_mutates_registered_original(tmp_path):
    attempt=setup_attempt(tmp_path,authorized=True)
    before=hashlib.sha256(attempt.original_guard.read_bytes()).hexdigest()
    attempt.reserve()
    assert hashlib.sha256(attempt.original_guard.read_bytes()).hexdigest()==before


def test_reservation_write_failure_blocks_network_and_stays_consumed(tmp_path,monkeypatch):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    transport=OneRequestTransport(attempt,httpx.MockTransport(lambda r:calls.append(1) or httpx.Response(200)))
    def denied(*args):
        raise OSError("synthetic flush failure")
    monkeypatch.setattr(os,"fsync",denied)
    request=httpx.Request("POST",f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")
    with pytest.raises(OSError):
        transport.handle_request(request)
    assert calls==[]
    assert (attempt.directory/"consumed.json").exists()
    with pytest.raises(AttemptBlocked,match="consumed"):
        attempt.authorize()


def test_diagnostic_persists_after_process_exit(tmp_path):
    attempt=setup_attempt(tmp_path,authorized=True)
    script='''
import sys,socket,httpx
from api.smoke.second_attempt import Attempt,extract_once,MODEL
from api.dependencies import reader
def denied(*a,**k): raise AssertionError("external network forbidden")
socket.create_connection=denied
reader._configuration=lambda:("fake-offline-key",MODEL)
attempt=Attempt(sys.argv[1],fixture=sys.argv[2],original_guard=sys.argv[3])
def mock(request):
    return httpx.Response(429,json={"error":{"code":429,"message":"fake-secret-body"}})
try: extract_once(attempt.fixture.read_bytes(),attempt,transport=httpx.MockTransport(mock))
except reader.PrescriptionAPIError: pass
'''
    env={k:v for k,v in os.environ.items() if k not in ("GEMINI_API_KEY","GEMINI_MODEL")}
    result=subprocess.run([sys.executable,"-c",script,str(attempt.directory),str(FIXTURE),str(attempt.original_guard)],
        cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,"Offline subprocess failed"
    report=(attempt.directory/"diagnostic_result.json").read_text()
    assert json.loads(report)["provider_http_status"]==429
    assert json.loads(report)["category"]=="quota_or_rate_limit"
    assert "fake-secret-body" not in report and "fake-offline-key" not in report
    with pytest.raises(AttemptBlocked,match="consumed"):
        attempt.authorize()


@pytest.mark.parametrize("method,url",[
    ("GET","https://generativelanguage.googleapis.com/v1beta/models"),
    ("POST","https://generativelanguage.googleapis.com/v1beta/models/other-model:generateContent"),
    ("POST",f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?extra=1"),
    ("POST",f"http://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")])
def test_other_endpoints_never_reach_provider(tmp_path,method,url):
    attempt=setup_attempt(tmp_path,authorized=True)
    calls=[]
    transport=OneRequestTransport(attempt,httpx.MockTransport(lambda r:calls.append(1) or httpx.Response(200)))
    with pytest.raises(AttemptBlocked,match="endpoint"):
        transport.handle_request(httpx.Request(method,url))
    assert calls==[] and not (attempt.directory/"consumed.json").exists()


def test_preparation_cannot_overwrite_registered_guard(tmp_path):
    attempt=setup_attempt(tmp_path)
    before=(attempt.directory/"guard.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(attempt.directory,fixture=FIXTURE,original_guard=attempt.original_guard)
    assert (attempt.directory/"guard.json").read_bytes()==before
