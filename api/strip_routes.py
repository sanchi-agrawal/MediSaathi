"""Isolated strip workflow over the existing OCR, parser and confirmation scope."""
from io import BytesIO
import secrets
from time import perf_counter

from fastapi import HTTPException, Request
from PIL import Image
from starlette.concurrency import run_in_threadpool

from .dependencies import IntegrationError, reader
from .models import RevisionRequest, StripReviewRequest
from .sessions import COOKIE
from .ocr_metrics import Measurements, elapsed_ms
import strip


def reject(status,category,message):
    raise HTTPException(status,detail={"category":category,"message":message})


def invalidate(state):
    state.update(revision=secrets.token_urlsafe(24),reviewed=False,confirmed_revision=None)


def register_strip_routes(app,store,enabled_sections):
    def load(request):
        if "strip" not in enabled_sections:
            reject(404,"unavailable","Strip OCR is not enabled on this server.")
        session=store.get(request.cookies.get(COOKIE))
        if session is None:
            reject(401,"session_expired","Demo session missing or expired.")
        return session

    def current(session,analysis_id,revision=None):
        snap=session.ai.snapshot();root=snap["strip"]
        if not session.strip_active or root is None or root["analysis_id"]!=analysis_id:
            reject(409,"stale_result","This strip image is no longer current.")
        state=session.strip_state
        if revision is not None and revision!=state["revision"]:
            reject(409,"stale_result","Strip details changed. Review the current snapshot again.")
        return snap,state

    def view(session):
        snap=session.ai.snapshot();root=snap["strip"]
        section=root["sections"]["strip"];state=session.strip_state
        return {"analysis_id":root["analysis_id"],"revision":state["revision"],"scope":"strip",
                "status":section["status"],"original_payload":section["payload"],"payload":section["reviewed"],
                "error":section["safe_error"],"reviewed":state["reviewed"],
                "confirmed":state["reviewed"] and state["confirmed_revision"]==state["revision"]
                    and "strip" in snap["confirmed_scopes"],
                "extractor_invocations":section["extractor_invocations"],
                "performance":dict(state.get("performance",{}))}

    @app.post("/api/strips")
    async def upload(request:Request):
        session=load(request);started=perf_counter();data=bytearray()
        async for chunk in request.stream():
            if len(data)+len(chunk)>reader.MAX_IMAGE_BYTES:
                reject(413,"image_validation_error","Image exceeds the 10 MiB limit.")
            data.extend(chunk)
        if request.headers.get("content-type","").split(";")[0] not in ("image/png","image/jpeg"):
            reject(415,"image_validation_error","Use raw PNG or JPEG image bytes.")
        def accept():
            with session.lock:
                # Changing the strip image never replaces the prescription root.
                session.strip_active=False;session.strip_state={}
                metrics=Measurements()
                with metrics.scope():
                    root=session.ai.start_strip(bytes(data))
                session.strip_state={"analysis_id":root["analysis_id"],"performance":metrics.snapshot()}
                invalidate(session.strip_state)
                with Image.open(BytesIO(data)) as image:
                    width,height=image.size
                session.strip_state["performance"].update(upload_ms=elapsed_ms(started),image_bytes=len(data),image_width=width,image_height=height)
                session.strip_active=True
                return view(session)
        return await run_in_threadpool(accept)

    @app.delete("/api/strips/current")
    def clear(request:Request):
        session=load(request)
        with session.lock:
            session.strip_active=False;session.strip_state={}
        return {"status":"cleared"}

    @app.get("/api/strips/{analysis_id}")
    def status(analysis_id:str,request:Request):
        session=load(request)
        with session.lock:
            current(session,analysis_id)
            return view(session)

    @app.post("/api/strips/{analysis_id}/analyze")
    def analyze(analysis_id:str,body:RevisionRequest,request:Request):
        session=load(request)
        with session.lock:
            snap,state=current(session,analysis_id,body.revision)
            status=snap["strip"]["sections"]["strip"]["status"]
            if status not in ("not_requested","failed"):
                reject(409,"invalid_state","Only new or failed strip extraction can be explicitly analyzed.")
            invalidate(state)
            job=session.ai.begin_section("strip",analysis_id=analysis_id,retry=status=="failed")
            adapter=session.ai
        started=perf_counter()
        adapter.execute(job)
        with session.lock:
            _,state=current(session,analysis_id)
            state["performance"]["server_extraction_ms"]=elapsed_ms(started)
            return view(session)

    @app.post("/api/strips/{analysis_id}/invalidate")
    def mark_dirty(analysis_id:str,body:RevisionRequest,request:Request):
        session=load(request)
        with session.lock:
            _,state=current(session,analysis_id,body.revision)
            invalidate(state)
            return view(session)

    @app.put("/api/strips/{analysis_id}/review")
    def review(analysis_id:str,body:StripReviewRequest,request:Request):
        session=load(request)
        with session.lock:
            snap,state=current(session,analysis_id,body.revision)
            invalidate(state)
            section=snap["strip"]["sections"]["strip"]
            if section["status"]!="succeeded":
                reject(409,"invalid_state","Run strip extraction before reviewing its observations.")
            existing=section["reviewed"]
            if len(body.date_observations)!=len(existing["date_observations"]):
                reject(422,"invalid_input","Preserve every extracted date observation while reviewing.")
            observations=[]
            for edited,original in zip(body.date_observations,existing["date_observations"]):
                # Confidence/uncertainty are source metadata, not browser claims.
                observations.append({**edited.model_dump(),"confidence":original["confidence"],
                                     "uncertain":original["uncertain"]})
            transcription={"medicine_name":body.medicine_name,"batch_number":body.batch_number,
                "product_association":body.product_association,"date_observations":observations,
                "quality_issues":[q for q in strip.QUALITY_ISSUES if q in existing["issues"]],
                "confidence":existing["confidence"],"uncertain":"uncertain_extraction" in existing["issues"]}
            try:
                normalized=strip.normalize_strip_response(transcription)
                session.ai.review("strip",normalized)
            except strip.StripValidationError:
                raise IntegrationError("invalid_input") from None
            state["reviewed"]=True
            return view(session)

    @app.post("/api/strips/{analysis_id}/confirm")
    def confirm(analysis_id:str,body:RevisionRequest,request:Request):
        session=load(request)
        with session.lock:
            _,state=current(session,analysis_id,body.revision)
            if not state["reviewed"]:
                reject(409,"confirmation_required","Save and explicitly review strip details before confirming.")
            event=session.ai.frontend_events().register_acknowledgement("strip")
            session.ai.confirm("strip",event=event)
            session.ai.confirmed_strip()  # guarded snapshot only; no downstream operation
            state["confirmed_revision"]=state["revision"]
            return view(session)
