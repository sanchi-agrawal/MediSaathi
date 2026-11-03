"""Session/revision-bound associations and separately approved scheduling."""
import copy
import secrets
from datetime import date
from fastapi import HTTPException, Request
from pydantic import ValidationError
from .dependencies import IntegrationError
from .downstream.models import AssociationRequest, Binding, LinkedRequest, PlanRequest, DerivedSchedule,SlotsConfirmationRequest
from .downstream.scheduling import validate_public_result
from .section_routes import metadata
from .sessions import COOKIE
from .downstream.automatic import prepare
from .downstream.association_proposals import proposals
from .clock_scheduling import register_clock_scheduling

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
        # Clock courses have their own response contract. Keep the restored
        # review/association client's legacy four-slot plan contract intact.
        clock_course=bool(state.get('clock_course'))
        return {"analysis_id": root["analysis_id"], "medicine_revision": session.revision,
                "instruction_revision": ins["revision"], "scheduling_revision": session.scheduling_revision,
                "ready": ready, "status": 'associated' if clock_course else state.get("status", "ready" if ready else "blocked"),"timing_contract":"confirmed-named-slots-v1",
                "medicines": root["sections"]["medicines"]["reviewed"] or [],
                "instructions": (root["sections"]["instructions"]["reviewed"] or {}).get("instructions", []),
                "instruction_issues": (root["sections"]["instructions"]["reviewed"] or {}).get("issues", []),
                "association": copy.deepcopy(state.get("association")), "plan": None if clock_course else copy.deepcopy(state.get("plan")),
                "result": None if clock_course else copy.deepcopy(state.get("result")), "error": copy.deepcopy(state.get("error")),
                "associations": copy.deepcopy(state.get('associations', [state['association']] if state.get('association') else [])),
                "automatic": prepare(session, root['sections']['medicines']['reviewed'] or [],
                    (root['sections']['instructions']['reviewed'] or {}).get('instructions',[]),
                    state.get('associations',[state['association']] if state.get('association') else [])) if ready else [],
                "course_results": [] if clock_course else copy.deepcopy(state.get('course_results',[])),
                "instruction_state":{"status":root['sections']['instructions']['status'],
                    "reviewed":ins['reviewed'],"confirmed":ins['confirmed_revision']==ins['revision'] and 'instructions' in session.ai.snapshot()['confirmed_scopes']},
                "association_proposals":proposals(root['sections']['medicines']['reviewed'] or [],
                    (root['sections']['instructions']['reviewed'] or {}).get('instructions',[]),
                    state.get('associations',[])) if ready else []}

    def linked(session, analysis_id, body):
        context(session, analysis_id, body, require=True)
        state=session.scheduling_state
        association = next((a for a in state.get('associations',[state['association']] if state.get('association') else []) if a['association_id']==body.association_id),None)
        if not association:
            reject(409, "association_required", "Explicitly associate the current medicine and instruction first.")
        return association

    prefix = "/api/prescriptions/{analysis_id}"
    register_clock_scheduling(app,load,context,reject)

    @app.post(prefix+'/schedule/slots/confirm')
    def confirm_slots(analysis_id:str,body:SlotsConfirmationRequest,request:Request):
        session=load(request)
        with session.lock:
            association=linked(session,analysis_id,body)
            if session.ai.confirmed_named_slots(association['association_id'])==body.slots:return view(session)
            event=session.ai.frontend_events().register_slot_confirmation(association['association_id'],body.slots)
            session.ai.confirm_named_slots(association['association_id'],body.slots,event=event)
            state=session.scheduling_state
            state.update(status='associated',association=association,plan=None,result=None,course_results=[])
            session.scheduling_revision=secrets.token_urlsafe(24)
            return view(session)

    @app.post(prefix+'/schedule/notation/confirm')
    def confirm_notation(analysis_id:str,body:LinkedRequest,request:Request):
        session=load(request)
        with session.lock:
            association=linked(session,analysis_id,body)
            event=session.ai.frontend_events().register_notation_confirmation(association['association_id'])
            session.ai.confirm_three_slot_notation(association['association_id'],event=event)
            state=session.scheduling_state
            state['notation_confirmed']=list(set(state.get('notation_confirmed',[])+[association['association_id']]))
            state.update(status='associated',association=association,plan=None,result=None,course_results=[])
            session.scheduling_revision=secrets.token_urlsafe(24)
            return view(session)

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
            prior=session.scheduling_state.get('associations',[])
            if any(a['medicine_ref']==body.medicine_ref and a['instruction_id']==body.instruction_id for a in prior):
                reject(409,'association_exists','This pair is already confirmed. Refresh the confirmed links.')
            if any(a['medicine_ref']==body.medicine_ref or a['instruction_id']==body.instruction_id for a in prior):
                reject(409,'association_conflict','A selected record already has a confirmed link. Explicitly clear links before correcting it.')
            event = session.ai.frontend_events().register_association(body.medicine_ref, body.instruction_id)
            identity = session.ai.associate(body.medicine_ref, body.instruction_id, event=event)
            association={"association_id": identity, "medicine_ref": body.medicine_ref, "instruction_id": body.instruction_id}
            session.scheduling_revision=secrets.token_urlsafe(24)
            session.scheduling_state = {"status": "associated", "association": association,
                "notation_confirmed":session.scheduling_state.get('notation_confirmed',[]),
                "associations":[a for a in prior if a['medicine_ref']!=body.medicine_ref and a['instruction_id']!=body.instruction_id]+[association]}
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
            session.scheduling_state = {"status": "associated", "association": association,
                "associations":session.scheduling_state.get('associations',[association]),"notation_confirmed":session.scheduling_state.get('notation_confirmed',[])}
            session.scheduling_revision = secrets.token_urlsafe(24)
            return view(session)

    @app.put(prefix + "/schedule/review")
    def review(analysis_id: str, body: PlanRequest, request: Request):
        session = load(request)
        with session.lock:
            association = linked(session, analysis_id, body)
            previous=session.scheduling_state
            same_start=not previous.get('plan') or previous['plan']['start_date']==body.plan.start_date
            session.scheduling_state = {"status": "associated", "association": association,
                "notation_confirmed":previous.get('notation_confirmed',[]),
                "associations":previous.get('associations',[association]),
                "course_results":[r for r in previous.get('course_results',[]) if same_start and r['association']['association_id']!=association['association_id']]}
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
            if state.get('association',{}).get('association_id')!=association['association_id']:
                reject(409,'stale_result','Review this association before approving it.')
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
            if result['payload']['status']=='ok':
                state.setdefault('course_results',[]).append({'association':association,'plan':plan,'result':result})
            return view(session)
