"""Prescription OCR adapter. Never exposes trusted events or scheduling/pricing."""
import os
from io import BytesIO
from time import perf_counter
from PIL import Image

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .dependencies import AIIntegration, IntegrationError, reader
from .models import ExplanationRequest, ReviewRequest, RevisionRequest
from .sessions import COOKIE, TTL_SECONDS, SessionStore
from .ocr_metrics import Measurements, elapsed_ms, log_metrics
from .section_routes import EXTRA_SCOPES, register_section_routes, section_view
from .strip_routes import register_strip_routes

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def fail(status, category, message):
    raise HTTPException(status, detail={"category": category, "message": message})


def create_app(*, factory=AIIntegration, origins=None, session_limit=64, upload_validator=None,
               enabled_sections=("medicines", "instructions", "investigations", "strip")):
    app = FastAPI(title="MediSaathi local demo API", docs_url=None, redoc_url=None)
    store = SessionStore(factory, limit=session_limit)
    app.state.sessions = store
    app.state.enabled_sections = tuple(enabled_sections)
    register_section_routes(app,store,enabled_sections)
    register_strip_routes(app,store,enabled_sections)
    allowed = tuple(origins or os.getenv("MEDISAATHI_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(","))
    if any(origin == "*" for origin in allowed):
        raise ValueError("Explicit frontend origins are required")
    app.add_middleware(CORSMiddleware, allow_origins=list(allowed), allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Content-Type", "X-MediSaathi-Action"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def browser_boundary(request, call_next):
        # CORS is not CSRF protection. Require both an exact Origin and custom
        # header on every mutation, including session creation and raw upload.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("origin") not in allowed or request.headers.get("x-medisaathi-action") != "review":
                return JSONResponse({"detail": {"category": "origin_rejected", "message": "Use the configured MediSaathi frontend."}}, 403,
                                    headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        # FastAPI's default error body may echo medical input. Never return it.
        return JSONResponse({"detail": {"category": "invalid_input", "message": "Request fields or types are invalid."}}, 422)

    @app.exception_handler(IntegrationError)
    async def integration_error(_request, error):
        status = 409 if error.category in ("stale_result", "invalid_state", "confirmation_required") else 422
        if error.category == "downstream_error":
            status = 502
        return JSONResponse({"detail": {"category": error.category, "message": str(error)}}, status)

    def session_for(request):
        session = store.get(request.cookies.get(COOKIE))
        if session is None:
            fail(401, "session_expired", "Demo session missing or expired. Start a new analysis.")
        return session

    def current(session, analysis_id, revision=None):
        root = session.ai.snapshot()["prescription"]
        if not session.prescription_active or root is None or root["analysis_id"] != analysis_id or (revision is not None and revision != session.revision):
            fail(409, "stale_result", "This analysis or revision is no longer current. Review the latest image and records.")
        return root

    def view(session):
        snap = session.ai.snapshot()
        root = snap["prescription"]
        if not session.prescription_active or root is None:
            fail(404, "not_found", "No current prescription.")
        section = root["sections"]["medicines"]
        return {"analysis_id": root["analysis_id"], "revision": session.revision,
                "status": section["status"], "original_records": section["payload"],
                "records": section["reviewed"], "error": section["safe_error"],
                "reviewed": session.reviewed, "performance": dict(session.performance),
                "sections": {scope:section_view(session,snap,scope) for scope in EXTRA_SCOPES if scope in enabled_sections},
                "confirmed": session.reviewed and session.confirmed_revision == session.revision
                and "medicines" in snap["confirmed_scopes"]}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "local-demo", "scopes": list(enabled_sections)}

    @app.post("/api/session")
    def start_session(request: Request):
        existing = store.get(request.cookies.get(COOKIE))
        if existing is not None:
            return {"mode": "local-demo"}
        created = store.create()
        if created is None:
            fail(503, "capacity", "Demo session capacity reached. Try again later.")
        token, _ = created
        response = JSONResponse({"mode": "local-demo"})
        response.set_cookie(COOKIE, token, max_age=TTL_SECONDS, secure=True, httponly=True, samesite="strict", path="/api")
        return response

    @app.delete("/api/prescriptions/current")
    def clear(request: Request):
        session = session_for(request)
        with session.lock:
            # Transport tombstone blocks old prescription IDs while preserving
            # the independent strip root in this same trusted session adapter.
            session.prescription_active = False
            session.invalidate()
            session.performance = {}
            session.section_states = {}
        return {"status": "cleared"}

    @app.post("/api/prescriptions")
    async def upload(request: Request):
        started = perf_counter()
        session = session_for(request)
        # Raw bounded image body avoids unbounded multipart parser buffering.
        # Also bound actual streaming bytes, regardless of Content-Length.
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > reader.MAX_IMAGE_BYTES:
                fail(413, "image_validation_error", "Image exceeds the 10 MiB limit.")
            data.extend(chunk)
        if request.headers.get("content-type", "").split(";")[0] not in ("image/png", "image/jpeg"):
            fail(415, "image_validation_error", "Use PNG or JPEG image bytes.")
        def accept():
            with session.lock:
                measurements = Measurements()
                with measurements.scope():
                    if upload_validator is not None:
                        upload_validator(bytes(data))
                    session.invalidate()
                    session.ai.start_prescription(bytes(data))
                    session.prescription_active = True
                    session.section_states = {}
                # Dimensions are read only after authoritative full validation.
                with Image.open(BytesIO(data)) as image:
                    width, height = image.size
                session.performance = {"upload_ms": elapsed_ms(started),
                    "upload_validation_ms": measurements.snapshot()["image_validation_ms"],
                    "image_bytes": len(data), "image_width": width, "image_height": height,
                    "duplicate_analysis_rejections": 0, "analysis_attempts": 0}
                log_metrics("upload", session.performance)
                return view(session)
        return await run_in_threadpool(accept)

    @app.get("/api/prescriptions/{analysis_id}")
    def status(analysis_id: str, request: Request):
        session = session_for(request)
        with session.lock:
            current(session, analysis_id)
            return view(session)

    @app.post("/api/prescriptions/{analysis_id}/analyze")
    def analyze(analysis_id: str, body: RevisionRequest, request: Request):
        session = session_for(request)
        with session.lock:
            root = current(session, analysis_id)
            state = root["sections"]["medicines"]["status"]
            if state in ("running", "succeeded"):
                session.performance["duplicate_analysis_rejections"] = session.performance.get("duplicate_analysis_rejections", 0) + 1
                log_metrics("duplicate_rejected", session.performance)
            if body.revision != session.revision:
                fail(409, "stale_result", "This analysis or revision is no longer current. Review the latest image and records.")
            if state not in ("not_requested", "failed"):
                fail(409, "invalid_state", "Only new or failed extraction can be explicitly analyzed.")
            session.invalidate()
            job = session.ai.begin_section("medicines", analysis_id=analysis_id, retry=state == "failed")
            session.performance["analysis_attempts"] = session.performance.get("analysis_attempts", 0) + 1
            adapter = session.ai
        # Network calls run outside the session lock so status and replacement
        # uploads remain responsive. The adapter rejects stale job completion.
        started = perf_counter()
        measurements = Measurements()
        with measurements.scope():
            adapter.execute(job)
        with session.lock:
            current(session, analysis_id)
            measured = measurements.snapshot()
            session.performance["total_gemini_sdk_invocations"] = session.performance.get("total_gemini_sdk_invocations", 0) + measured["gemini_sdk_invocations"]
            session.performance.update(measured)
            session.performance["server_extraction_ms"] = elapsed_ms(started)
            session.performance["server_processing_ms"] = round(session.performance.get("upload_ms", 0) + session.performance["server_extraction_ms"], 3)
            log_metrics("extraction", session.performance)
            return view(session)

    @app.post("/api/prescriptions/{analysis_id}/invalidate")
    def invalidate(analysis_id: str, body: RevisionRequest, request: Request):
        session = session_for(request)
        with session.lock:
            current(session, analysis_id, body.revision)
            session.invalidate()
            return view(session)

    @app.put("/api/prescriptions/{analysis_id}/review")
    def review(analysis_id: str, body: ReviewRequest, request: Request):
        session = session_for(request)
        with session.lock:
            current(session, analysis_id, body.revision)
            # Invalidate BEFORE validation too; forged data cannot retain an API
            # confirmation or previously derived explanation.
            session.invalidate()
            session.ai.review("medicines", body.records)
            session.reviewed = True
            return view(session)

    @app.post("/api/prescriptions/{analysis_id}/confirm")
    def confirm(analysis_id: str, body: RevisionRequest, request: Request):
        session = session_for(request)
        with session.lock:
            current(session, analysis_id, body.revision)
            if not session.reviewed:
                fail(409, "confirmation_required", "Save and review the current medicine records before confirming.")
            # Body accepts ONLY revision. Records, booleans and event claims are
            # forbidden; bind an opaque server event to the CURRENT snapshot.
            event = session.ai.frontend_events().register_acknowledgement("medicines")
            session.ai.confirm("medicines", event=event)
            session.confirmed_revision = session.revision
            return view(session)

    @app.post("/api/prescriptions/{analysis_id}/explanation")
    def explain(analysis_id: str, body: ExplanationRequest, request: Request):
        session = session_for(request)
        with session.lock:
            current(session, analysis_id, body.revision)
            if not session.reviewed or session.confirmed_revision != session.revision:
                fail(409, "confirmation_required", "Confirm the current reviewed snapshot first.")
            result = session.ai.explain(language=body.language)
            session.explanation = result
            return {"analysis_id": analysis_id, "revision": session.revision, **result}

    return app


app = create_app()
