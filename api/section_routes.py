"""Independent instruction/investigation HTTP scopes over unchanged AIIntegration."""
import secrets
from time import perf_counter
from typing import Literal

from fastapi import HTTPException, Request

from .models import RevisionRequest, SectionReviewRequest
from .ocr_metrics import Measurements, elapsed_ms
from .sessions import COOKIE

ExtraScope = Literal["instructions", "investigations"]
EXTRA_SCOPES = ("instructions", "investigations")


def reject(status, category, message):
    raise HTTPException(status, detail={"category":category,"message":message})


def metadata(session, root, scope):
    state = session.section_states.get(scope)
    if state is None or state["analysis_id"] != root["analysis_id"]:
        state = {"analysis_id":root["analysis_id"],"revision":secrets.token_urlsafe(24),
                 "reviewed":False,"confirmed_revision":None,"performance":{}}
        session.section_states[scope] = state
    return state


def invalidate(state):
    state.update(revision=secrets.token_urlsafe(24),reviewed=False,confirmed_revision=None)


def section_view(session, snap, scope):
    root=snap["prescription"]
    state=metadata(session,root,scope)
    section=root["sections"][scope]
    return {"analysis_id":root["analysis_id"],"scope":scope,"revision":state["revision"],
            "status":section["status"],"original_payload":section["payload"],
            "payload":section["reviewed"],"error":section["safe_error"],
            "reviewed":state["reviewed"],"confirmed":state["reviewed"]
            and state["confirmed_revision"]==state["revision"] and scope in snap["confirmed_scopes"],
            "extractor_invocations":section["extractor_invocations"],
            "performance":dict(state["performance"])}


def register_section_routes(app, store, enabled_sections):
    def load(request, analysis_id, scope, revision=None):
        if scope not in enabled_sections:
            reject(404,"unavailable","This extraction scope is not enabled on this server.")
        session=store.get(request.cookies.get(COOKIE))
        if session is None:
            reject(401,"session_expired","Demo session missing or expired. Start a new analysis.")
        return session

    def current(session, analysis_id, scope, revision=None):
        snap=session.ai.snapshot()
        root=snap["prescription"]
        if not session.prescription_active or root is None or root["analysis_id"]!=analysis_id:
            reject(409,"stale_result","This prescription is no longer current.")
        state=metadata(session,root,scope)
        if revision is not None and state["revision"]!=revision:
            reject(409,"stale_result","This section changed. Review the current section again.")
        return snap,state

    prefix="/api/prescriptions/{analysis_id}/sections/{scope}"

    @app.get(prefix)
    def status(analysis_id:str,scope:ExtraScope,request:Request):
        session=load(request,analysis_id,scope)
        with session.lock:
            snap,_=current(session,analysis_id,scope)
            return section_view(session,snap,scope)

    @app.post(prefix+"/analyze")
    def analyze(analysis_id:str,scope:ExtraScope,body:RevisionRequest,request:Request):
        session=load(request,analysis_id,scope)
        with session.lock:
            snap,state=current(session,analysis_id,scope,body.revision)
            status=snap["prescription"]["sections"][scope]["status"]
            if status not in ("not_requested","failed"):
                reject(409,"invalid_state","Only a new or failed section may be explicitly analyzed.")
            invalidate(state)
            job=session.ai.begin_section(scope,analysis_id=analysis_id,retry=status=="failed")
            adapter=session.ai
        started=perf_counter();measurements=Measurements()
        with measurements.scope():
            adapter.execute(job)
        with session.lock:
            snap,state=current(session,analysis_id,scope)
            state["performance"]={"server_extraction_ms":elapsed_ms(started)}
            return section_view(session,snap,scope)

    @app.post(prefix+"/invalidate")
    def mark_dirty(analysis_id:str,scope:ExtraScope,body:RevisionRequest,request:Request):
        session=load(request,analysis_id,scope)
        with session.lock:
            snap,state=current(session,analysis_id,scope,body.revision)
            invalidate(state)
            return section_view(session,snap,scope)

    @app.put(prefix+"/review")
    def review(analysis_id:str,scope:ExtraScope,body:SectionReviewRequest,request:Request):
        session=load(request,analysis_id,scope)
        with session.lock:
            _,state=current(session,analysis_id,scope,body.revision)
            invalidate(state)
            records=body.payload.get(scope)
            if type(records) is not list or len(records)>200:
                reject(422,"invalid_input","Use the current section envelope with at most 200 records.")
            # Full original envelopes, exact fields, nulls, source binding, IDs
            # and uncertainty flags are validated by the existing adapter.
            session.ai.review(scope,body.payload)
            state["reviewed"]=True
            return section_view(session,session.ai.snapshot(),scope)

    @app.post(prefix+"/confirm")
    def confirm(analysis_id:str,scope:ExtraScope,body:RevisionRequest,request:Request):
        session=load(request,analysis_id,scope)
        with session.lock:
            _,state=current(session,analysis_id,scope,body.revision)
            if not state["reviewed"]:
                reject(409,"confirmation_required","Save and explicitly review this section before confirming.")
            event=session.ai.frontend_events().register_acknowledgement(scope)
            session.ai.confirm(scope,event=event)
            state["confirmed_revision"]=state["revision"]
            return section_view(session,session.ai.snapshot(),scope)
