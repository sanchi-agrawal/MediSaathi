"""Session/revision-bound associations and separately approved scheduling."""
import copy
import secrets
from datetime import date
from fastapi import HTTPException, Request
from pydantic import ValidationError
from .dependencies import IntegrationError
from .downstream.models import AssociationRequest, Binding, LinkedRequest, PlanRequest, DerivedSchedule
from .downstream.scheduling import validate_public_result
from .section_routes import metadata
from .sessions import COOKIE

def reject(status, category, message):
    raise HTTPException(status, detail={"category": category, "message": message})

def register_downstream_routes(app, store, enabled_sections):
    def load(request):
        if not {"medicines", "instructions"}.issubset(enabled_sections):
            reject(503, "unavailable", "Scheduling is unavailable on this diagnostic server.")
        session = store.get(request.cookies.get(COOKIE))
        if session is None:
            reject(401, "session_expired", "Open prescription analysis to start a demo session.")
        return session

    def context(session, analysis_id=None, body=None, require=False):
        snap = session.ai.snapshot()
        root = snap["prescription"]
        if not session.prescription_active or root is None:
            reject(409, "invalid_state", "Upload, review and confirm medicines and instructions first.")
        if analysis_id is not None and root["analysis_id"] != analysis_id:
            reject(409, "stale_result", "This prescription is no longer current.")
        ins = metadata(session, root, "instructions")
        if body is not None and (body.medicine_revision != session.revision or body.instruction_revision != ins["revision"] or body.scheduling_revision != session.scheduling_revision):
            reject(409, "stale_result", "The source, association or plan changed. Reload scheduling.")
        ready = (session.reviewed and session.confirmed_revision == session.revision and "medicines" in snap["confirmed_scopes"]
                 and ins["reviewed"] and ins["confirmed_revision"] == ins["revision"] and "instructions" in snap["confirmed_scopes"])
        if require and not ready:
            reject(409, "confirmation_required", "Confirm current medicines and instructions independently first.")
        return root, ins, bool(ready)

    def view(session):
        root, ins, ready = context(session)
        state = session.scheduling_state if ready else {}
        return {"analysis_id": root["analysis_id"], "medicine_revision": session.revision,
                "instruction_revision": ins["revision"], "scheduling_revision": session.scheduling_revision,
                "ready": ready, "status": state.get("status", "ready" if ready else "blocked"),
                "medicines": root["sections"]["medicines"]["reviewed"] or [],
                "instructions": (root["sections"]["instructions"]["reviewed"] or {}).get("instructions", []),
                "instruction_issues": (root["sections"]["instructions"]["reviewed"] or {}).get("issues", []),
                "association": copy.deepcopy(state.get("association")), "plan": copy.deepcopy(state.get("plan")),
                "result": copy.deepcopy(state.get("result")), "error": copy.deepcopy(state.get("error"))}

    def linked(session, analysis_id, body):
        context(session, analysis_id, body, require=True)
        association = session.scheduling_state.get("association")
        if not association or association["association_id"] != body.association_id:
            reject(409, "association_required", "Explicitly associate the current medicine and instruction first.")
        return association

    prefix = "/api/prescriptions/{analysis_id}"

    @app.get("/api/scheduling/current")
    def status(request: Request):
        session = load(request)
        with session.lock:
            return view(session)

    @app.post(prefix + "/associations")
    def associate(analysis_id: str, body: AssociationRequest, request: Request):
        session = load(request)
        with session.lock:
            context(session, analysis_id, body, require=True)
            session.invalidate_scheduling()
            event = session.ai.frontend_events().register_association(body.medicine_ref, body.instruction_id)
            identity = session.ai.associate(body.medicine_ref, body.instruction_id, event=event)
            session.scheduling_state = {"status": "associated", "association": {
                "association_id": identity, "medicine_ref": body.medicine_ref, "instruction_id": body.instruction_id}}
            return view(session)

    @app.delete(prefix + "/associations")
    def clear(analysis_id: str, body: Binding, request: Request):
        session = load(request)
        with session.lock:
            context(session, analysis_id, body)
            session.invalidate_scheduling()
            return view(session)

    @app.post(prefix + "/schedule/invalidate")
    def invalidate(analysis_id: str, body: LinkedRequest, request: Request):
        session = load(request)
        with session.lock:
            association = linked(session, analysis_id, body)
            session.scheduling_state = {"status": "associated", "association": association}
            session.scheduling_revision = secrets.token_urlsafe(24)
            return view(session)

    @app.put(prefix + "/schedule/review")
    def review(analysis_id: str, body: PlanRequest, request: Request):
        session = load(request)
        with session.lock:
            association = linked(session, analysis_id, body)
            session.scheduling_state = {"status": "associated", "association": association}
            session.scheduling_revision = secrets.token_urlsafe(24)
            try:
                if date.fromisoformat(body.plan.start_date).isoformat() != body.plan.start_date:
                    raise ValueError
            except ValueError:
                reject(422, "invalid_input", "Choose a valid ISO start date.")
            session.scheduling_state.update(status="reviewed", plan=body.plan.model_dump())
            return view(session)

    @app.post(prefix + "/schedule/approve")
    def approve(analysis_id: str, body: LinkedRequest, request: Request):
        session = load(request)
        with session.lock:
            association = linked(session, analysis_id, body)
            state = session.scheduling_state
            if state.get("status") != "reviewed" or not state.get("plan"):
                reject(409, "approval_required", "Save a plan before separately approving generation.")
            plan = copy.deepcopy(state["plan"])
            session.scheduling_revision = secrets.token_urlsafe(24)
            state.pop("result", None)
            state.update(status="failed", error={"category": "downstream_error", "message": "Schedule generation did not complete."})
            try:
                event = session.ai.frontend_events().register_schedule_approval(association["association_id"], plan)
                result = session.ai.schedule(association["association_id"], plan, event=event)
                result = DerivedSchedule.model_validate(result).model_dump()
                root, _, _ = context(session, analysis_id, require=True)
                index = int(association["medicine_ref"].removeprefix("medicine_")) - 1
                result["payload"] = validate_public_result(result["payload"], root["sections"]["medicines"]["reviewed"][index], plan)
            except IntegrationError as error:
                state["error"] = {"category": error.category, "message": str(error)}
                raise
            except (ValidationError, TypeError, ValueError):
                session.invalidate_scheduling()
                session.scheduling_state = {"status": "failed", "error": {"category": "invalid_response", "message": "Scheduler output was invalid. No schedule is available."}}
                reject(502, "invalid_response", "Scheduler output was invalid. No schedule is available.")
            state.update(status="succeeded" if result["payload"]["status"] == "ok" else "needs_input", result=result, error=None)
            return view(session)
