"""13H preparation: separately authorized, strictly one-HTTP-request diagnostic.

No global patching and no normal-reader change. This diagnostic context reuses
the reader's validator, prompt, schema and normalizer, with one SDK invocation.
An exclusive durable reservation at the HTTP transport also caps physical calls.
Importing this module, preparing it and starting its app never extracts anything.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time

import httpx
from google import genai
from google.genai import errors, types
import uvicorn

from api.dependencies import AIIntegration, reader
from api.main import create_app, fail
from api.smoke.diagnostics import safe_failure_diagnostics
from api.smoke.persistence import persist_result
from api.smoke.server import load_credentials

ATTEMPT_ID = "13h-20261026-b47e69c18a2f"
MODEL = "gemini-3.1-flash-lite"
ROOT = Path(__file__).resolve().parent
ATTEMPT_DIR = ROOT / "attempts" / ATTEMPT_ID


class AttemptBlocked(RuntimeError):
    """Fixed safe messages only; never contains credentials/provider text."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exclusive_json(path, payload):
    # Existence alone blocks competitors even during a crash/partial write.
    # Never remove or overwrite a reservation, including on an I/O failure.
    with Path(path).open("x",encoding="utf-8") as stream:
        json.dump(payload,stream,sort_keys=True,allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def prepare(directory=ATTEMPT_DIR, *, fixture=ROOT/"fictional_demo.png", original_guard=ROOT/"live_result.json"):
    directory=Path(directory)
    reader._validate_image(Path(fixture).read_bytes())
    original=json.loads(Path(original_guard).read_text(encoding="utf-8"))
    if original.get("status") != "failed" or original.get("extractor_invocations") != 1:
        raise AttemptBlocked("The original consumed attempt must be preserved.")
    manifest={"attempt_id":ATTEMPT_ID,"model":MODEL,"max_provider_calls":1,
              "fixture_sha256":digest(fixture),"original_guard_sha256":digest(original_guard),
              "scope":"preparation_only","execution_authorized":False,
              "prepared_at":datetime.now(timezone.utc).isoformat()}
    directory.mkdir(parents=True,exist_ok=True)
    exclusive_json(directory/"guard.json",manifest)
    return manifest


class Attempt:
    def __init__(self, directory=ATTEMPT_DIR, *, fixture=ROOT/"fictional_demo.png", original_guard=ROOT/"live_result.json"):
        self.directory=Path(directory)
        self.fixture=Path(fixture)
        self.original_guard=Path(original_guard)
        self.manifest=json.loads((self.directory/"guard.json").read_text(encoding="utf-8"))
        self.lock=threading.Lock()
        self.assert_integrity()

    def assert_integrity(self):
        m=self.manifest
        if (m.get("attempt_id")!=ATTEMPT_ID or m.get("model")!=MODEL or
                type(m.get("max_provider_calls")) is not int or m["max_provider_calls"]!=1 or
                m.get("scope")!="preparation_only" or m.get("execution_authorized") is not False or
                digest(self.fixture)!=m.get("fixture_sha256") or
                digest(self.original_guard)!=m.get("original_guard_sha256")):
            raise AttemptBlocked("Attempt identity, fixture, model or original guard does not match.")
        if json.loads((self.directory/"guard.json").read_text(encoding="utf-8")) != m:
            raise AttemptBlocked("Prepared guard changed; refusing execution.")

    def authorize(self):
        self.assert_integrity()
        if (self.directory/"consumed.json").exists():
            raise AttemptBlocked("Second-attempt allowance is consumed.")
        path=self.directory/"execution_authorization.json"
        if not path.is_file():
            raise AttemptBlocked("Execution is disabled: separate explicit user authorization is required.")
        auth=json.loads(path.read_text(encoding="utf-8"))
        if set(auth)!={"attempt_id","fixture_sha256","model","max_provider_calls","execution_authorized",
                       "authorized_by","authorization_reference","expires_at"}:
            raise AttemptBlocked("Authorization record is invalid.")
        if (auth["attempt_id"]!=ATTEMPT_ID or auth["fixture_sha256"]!=self.manifest["fixture_sha256"] or
                auth["model"]!=MODEL or type(auth["max_provider_calls"]) is not int or
                auth["max_provider_calls"]!=1 or auth["execution_authorized"] is not True or
                auth["authorized_by"]!="user" or not isinstance(auth["authorization_reference"],str) or
                not auth["authorization_reference"].strip()):
            raise AttemptBlocked("Authorization does not match this one-call attempt.")
        try:
            expiry=datetime.fromisoformat(auth["expires_at"])
            valid=expiry.tzinfo is not None and expiry>datetime.now(timezone.utc)
        except (ValueError,TypeError):
            valid=False
        if not valid:
            raise AttemptBlocked("Execution authorization is expired or invalid.")
        return digest(path)

    def validate_image(self,data):
        reader._validate_image(data)
        if hashlib.sha256(data).hexdigest()!=self.manifest["fixture_sha256"]:
            raise AttemptBlocked("Use the exact registered fictional PNG for this second attempt.")

    def reserve(self):
        with self.lock:
            authorization_sha=self.authorize()
            try:
                exclusive_json(self.directory/"consumed.json",{
                    "attempt_id":ATTEMPT_ID,"provider_call_budget_consumed":1,
                    "authorization_sha256":authorization_sha,
                    "reserved_at":datetime.now(timezone.utc).isoformat()})
            except FileExistsError:
                raise AttemptBlocked("Second-attempt allowance is consumed.") from None


class OneRequestTransport(httpx.BaseTransport):
    def __init__(self, attempt, underlying):
        self.attempt=attempt
        self.underlying=underlying
        self.reserved=False

    def handle_request(self,request):
        url=request.url
        if (request.method!="POST" or url.scheme!="https" or
                url.host!="generativelanguage.googleapis.com" or url.port not in (None,443) or
                url.path!=f"/v1beta/models/{MODEL}:generateContent" or url.query):
            raise AttemptBlocked("Only the registered model generation endpoint is permitted.")
        self.attempt.reserve()  # durable cross-process cap BEFORE network I/O
        self.reserved=True
        reader._observe("provider_http_requests",1)
        return self.underlying.handle_request(request)

    def close(self):
        self.underlying.close()


def extract_once(data,attempt,*,transport=None):
    # Deliberately no retry loop and no modification of reader.read_prescription.
    attempt.authorize()
    attempt.validate_image(data)
    key,model=reader._configuration()
    if model!=MODEL:
        raise reader.ReaderConfigurationError("Configured model does not match the registered diagnostic model.")
    started=time.perf_counter()
    report={"attempt_id":ATTEMPT_ID,"status":"failed","category":"unexpected_backend_error",
            "provider_http_status":None,"started_at":datetime.now(timezone.utc).isoformat()}
    guarded_transport=None
    try:
        with reader._measure("client_setup_ms"):
            underlying=transport if transport is not None else httpx.HTTPTransport(retries=0)
            guarded_transport=OneRequestTransport(attempt,underlying)
            configured_http=httpx.Client(transport=guarded_transport,follow_redirects=False,
                                        trust_env=False,timeout=30)
        with configured_http as http:
            with reader._measure("client_setup_ms"):
                configured_client=genai.Client(api_key=key,vertexai=False,enterprise=False,
                    http_options=types.HttpOptions(api_version="v1beta",
                        base_url="https://generativelanguage.googleapis.com",httpx_client=http,
                        timeout=30_000,retry_options=types.HttpRetryOptions(attempts=1)))
            with configured_client as client:
                reader._observe("gemini_sdk_invocations",1)
                with reader._measure("gemini_request_ms"):
                    response=client.models.generate_content(model=MODEL,
                        contents=["Extract the visible medicine lines.",
                                  types.Part.from_bytes(data=data,mime_type=reader._validate_image(data))],
                        config=types.GenerateContentConfig(system_instruction=reader.SYSTEM_INSTRUCTION,
                            response_mime_type="application/json",response_json_schema=reader.RESPONSE_SCHEMA,
                            temperature=0))
                records=reader.normalize_model_response(response.text)
                report.update(status="succeeded",category="succeeded")
                return records
    except Exception as error:
        safe=safe_failure_diagnostics(error)
        report.update(category=safe["category"],provider_http_status=safe["provider_http_status"])
        if isinstance(error,errors.APIError):
            raise reader.PrescriptionAPIError("The diagnostic provider request failed. See sanitized diagnostics.") from None
        if isinstance(error,(httpx.HTTPError,ConnectionError,TimeoutError)):
            raise reader.PrescriptionAPIError("The diagnostic transport request failed. No retry was made.") from None
        if isinstance(error,AttemptBlocked):
            report["category"]="attempt_blocked"
            raise reader.ReaderConfigurationError("Diagnostic allowance unavailable. No retry is permitted.") from None
        raise
    finally:
        report["elapsed_seconds"]=round(time.perf_counter()-started,3)
        # Exactly allowlisted metadata; never persist records, response text,
        # image bytes, prompt, keys, headers or exception strings.
        # Only the owner of the exclusive reservation writes the outcome.
        # A concurrent refused call must not overwrite its diagnostic result.
        if guarded_transport is not None and guarded_transport.reserved:
            persist_result(attempt.directory/"diagnostic_result.json",report)


def create_diagnostic_app(attempt):
    attempt.authorize()  # fails closed before server creation if not authorized
    def validate(data):
        try:
            attempt.validate_image(data)
        except AttemptBlocked:
            fail(422,"diagnostic_fixture_required","Select the exact registered fictional PNG.")
        except reader.ImageInputError:
            fail(422,"image_validation_error","Use a valid single-frame PNG/JPEG within existing limits.")
    app=create_app(factory=lambda:AIIntegration(extractors={"medicines":lambda data:extract_once(data,attempt)}),
                   upload_validator=validate,enabled_sections=("medicines",))
    @app.get("/api/diagnostic/status")
    def status():
        return {"attempt_id":ATTEMPT_ID,"model":MODEL,"max_provider_calls":1,
                "consumed":(attempt.directory/"consumed.json").exists(),"mode":"single-call-diagnostic"}
    return app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true",help="Read-only readiness check; no credentials or network")
    parser.add_argument("--credentials-file",type=Path)
    args=parser.parse_args()
    attempt=Attempt()
    try:
        attempt.authorize()
    except AttemptBlocked as error:
        print(str(error))
        raise SystemExit(2) from None
    if args.check:
        print("Authorization valid; no server or provider call started.")
        return
    # No CLI authorization switch exists. A matching, separately approved
    # authorization record must already exist; preparation never creates one.
    _,model=load_credentials(args.credentials_file)
    if model!=MODEL:
        raise SystemExit("Configured model does not match the registered model.")
    app=create_diagnostic_app(attempt)
    uvicorn.run(app,host="127.0.0.1",port=8000,access_log=False)


if __name__=="__main__":
    main()
