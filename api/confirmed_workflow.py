"""One source-bound prescription review; one date-only course generation.

Acknowledgements are created on the server only after validating a current
whole-review submission. Legacy scope/association APIs remain compatible.
"""
import copy
import secrets
from datetime import date,datetime,timezone
from typing import Literal
from fastapi import Request, HTTPException
from pydantic import Field,field_validator
from .downstream.models import Strict, DerivedSchedule
from .downstream.automatic import prepare
from .downstream.scheduling import validate_public_result
from .downstream.association_proposals import proposals
from .medicine_review import requirements, VERIFY_FIELDS
from .section_routes import metadata, invalidate
from .sessions import COOKIE
from .dependencies import IntegrationError
from confirmed_frequency import reviewed_semantic_timing, NAMED_SLOTS


class ReviewedPair(Strict):
    medicine_ref:str=Field(min_length=1,max_length=128)
    instruction_id:str=Field(min_length=1,max_length=128)
    slots:list[Literal['morning','afternoon','evening','night','bedtime']]=Field(max_length=5)

class WholeReview(Strict):
    medicine_revision:str
    instruction_revision:str
    records:list[dict]=Field(max_length=200)
    instructions:dict
    pairs:list[ReviewedPair]=Field(max_length=200)
    # Explicit resolutions within this same review, never silently clear flags.
    resolved_records:list[int]=Field(max_length=200)
    resolved_instructions:list[str]=Field(default_factory=list,max_length=200)
    acknowledge:Literal[True]
    @field_validator('acknowledge',mode='before')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('Explicit review required')
        return value

class Generate(Strict):
    snapshot_id:str
    start_date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')

def reject(status,category,message):
    raise HTTPException(status,detail={'category':category,'message':message})

def register_confirmed_workflow(app,store):
    def load(request):
        session=store.get(request.cookies.get(COOKIE))
        if session is None:reject(401,'session_expired','Sign in and open the current prescription again.')
        return session

    def current(session,analysis_id=None):
        root=session.ai.snapshot()['prescription']
        if not session.prescription_active or not root:reject(404,'no_current_prescription','Upload a prescription first.')
        if analysis_id is not None and analysis_id!=root['analysis_id']:reject(409,'stale_result','The prescription changed. Return to review.')
        return root,metadata(session,root,'instructions')

    def snapshot(session):
        root,ins=current(session)
        saved=session.confirmed_prescription
        if saved and (saved['analysis_id']!=root['analysis_id'] or saved['medicine_revision']!=session.revision or saved['instruction_revision']!=ins['revision'] or saved['scheduling_revision']!=session.scheduling_revision or session.confirmed_revision!=session.revision or ins['confirmed_revision']!=ins['revision'] or not {'medicines','instructions'}.issubset(session.ai.snapshot()['confirmed_scopes'])):
            session.confirmed_prescription=None;session.generated_course=None;saved=None
        return copy.deepcopy(saved)

    @app.get('/api/prescription-review/current')
    def review_current(request:Request):
        session=load(request)
        with session.lock:
            root,ins=current(session)
            med=root['sections']['medicines'];instruction=root['sections']['instructions']
            records=med['reviewed'] or med['payload'] or []
            envelope=instruction['reviewed'] or instruction['payload']
            proposed=proposals(records,(envelope or {}).get('instructions',[]),[])
            pairs=[]
            for p in proposed:
                index=int(p['medicine_ref'].removeprefix('medicine_'))-1
                item=next((i for i in (envelope or {}).get('instructions',[]) if i['instruction_id']==p['instruction_id']),None)
                timing=reviewed_semantic_timing(records[index],item) if item else None
                pairs.append({**p,'slots':timing['slots'] if timing else []})
            return {'analysis_id':root['analysis_id'],'medicine_revision':session.revision,'instruction_revision':ins['revision'],
                'records':records,'instructions':envelope,'pairs':pairs,'review_requirements':requirements(med['payload'],records),
                'medicine_status':med['status'],'instruction_status':instruction['status'],
                'snapshot':snapshot(session),'recognition_mode':app.state.recognition_mode}

    @app.post('/api/prescriptions/{analysis_id}/review/confirm-all')
    def confirm_all(analysis_id:str,body:WholeReview,request:Request):
        session=load(request)
        with session.lock:
            root,ins=current(session,analysis_id)
            if body.medicine_revision!=session.revision or body.instruction_revision!=ins['revision']:reject(409,'stale_result','The source changed. Reload the prescription review.')
            if root['sections']['medicines']['status']!='succeeded' or root['sections']['instructions']['status']!='succeeded':reject(409,'extraction_required','Analyze medicines and instructions before confirming.')
            original=root['sections']['medicines']['payload'] or []
            prior=root['sections']['medicines']['reviewed'] or original
            if len(body.records)!=len(original):reject(422,'invalid_input','Review the current extracted records without changing their identities.')
            checked=requirements(original,body.records)
            for i,record in enumerate(body.records):
                if record.get('confidence')!=original[i]['confidence']:reject(422,'unresolved_review','Original confidence cannot be changed.')
                clearing=record.get('needs_review') is False and (prior[i]['needs_review'] is True or original[i]['needs_review'] is True and any(record.get(f)!=prior[i].get(f) for f in VERIFY_FIELDS))
                if clearing and (i not in body.resolved_records or not checked[i]['can_resolve']):reject(422,'unresolved_review','Verify all source fields; missing, uncertain or unsupported values remain unresolved.')
            refs=[p.medicine_ref for p in body.pairs];ids=[p.instruction_id for p in body.pairs]
            valid_refs={f'medicine_{i:03}' for i in range(1,len(body.records)+1)}
            if len(set(refs))!=len(refs) or len(set(ids))!=len(ids) or not set(refs)<=valid_refs:reject(422,'association_conflict','Select a unique instruction for each medicine in prescription review.')
            prior_items=(root['sections']['instructions']['reviewed'] or root['sections']['instructions']['payload'] or {}).get('instructions',[])
            for item in body.instructions.get('instructions',[]):
                previous=next((v for v in prior_items if v['instruction_id']==item.get('instruction_id')),None)
                if previous and previous['needs_review'] is True and item.get('needs_review') is False:
                    reject(422,'unresolved_review','Instruction flags require explicit source-validated resolution, not a changed boolean.')
            # Invalidate before any mutation/validation; rejected edits cannot retain approvals.
            session.invalidate();invalidate(ins);session.explanation=None
            try:
                session.ai.review('medicines',body.records)
                session.ai.review('instructions',body.instructions)
                for scope in ('medicines','instructions'):
                    event=session.ai.frontend_events().register_acknowledgement(scope)
                    session.ai.confirm(scope,event=event)
                session.reviewed=True;session.confirmed_revision=session.revision
                ins.update(reviewed=True,confirmed_revision=ins['revision'])
                def bind_reviewed_pairs():
                    linked=[]
                    for pair in body.pairs:
                        event=session.ai.frontend_events().register_association(pair.medicine_ref,pair.instruction_id)
                        identity=session.ai.associate(pair.medicine_ref,pair.instruction_id,event=event)
                        if pair.slots:
                            event=session.ai.frontend_events().register_slot_confirmation(identity,pair.slots)
                            session.ai.confirm_named_slots(identity,pair.slots,event=event)
                        linked.append({'association_id':identity,'medicine_ref':pair.medicine_ref,'instruction_id':pair.instruction_id})
                    return linked
                associations=bind_reviewed_pairs()
                if body.resolved_instructions:
                    # Resolve only as part of this genuine source review. First
                    # exercise the existing clinical guard with the flag INTACT.
                    # Missing/ambiguous dose, unit, duration, slots, unsafe reasons
                    # or source evidence cannot qualify. Original OCR stays intact.
                    requested=set(body.resolved_instructions)
                    if len(requested)!=len(body.resolved_instructions):reject(422,'invalid_input','Instruction review identities must be unique.')
                    candidate=copy.deepcopy(session.ai.snapshot()['prescription']['sections']['instructions']['reviewed'])
                    candidates=prepare(session,body.records,candidate['instructions'],associations)
                    for identity in requested:
                        item=next((v for v in candidate['instructions'] if v['instruction_id']==identity),None)
                        original_item=next((v for v in (root['sections']['instructions']['payload'] or {}).get('instructions',[]) if v['instruction_id']==identity),None)
                        entry=next((v for v in candidates if v['association'] and v['association']['instruction_id']==identity),None)
                        if not item or not original_item or set(original_item['uncertainty_reasons'])!={'missing_information'} or item['needs_review'] is not True or not entry or entry['issues'] or not entry['template']:
                            reject(422,'unresolved_review','Instruction resolution requires verified source-backed dose, unit, duration and named timing; unresolved clinical information remains blocked.')
                        session.ai._schedule_request(entry['association']['association_id'],{**entry['template'],'start_date':date.today().isoformat()})
                        item['needs_review']=False
                    session.ai.review('instructions',candidate)
                    event=session.ai.frontend_events().register_acknowledgement('instructions')
                    session.ai.confirm('instructions',event=event)
                    associations=bind_reviewed_pairs()
                session.scheduling_state={'status':'associated','associations':associations}
                latest=session.ai.snapshot()['prescription']['sections']
                meds=latest['medicines']['reviewed'];items=latest['instructions']['reviewed']['instructions']
                entries=prepare(session,meds,items,associations)
                for index,entry in enumerate(entries):
                    item=next((v for v in items if entry['association'] and v['instruction_id']==entry['association']['instruction_id']),{})
                    if item.get('needs_review') is True:
                        entry['issues'].append('instruction_review_flag');entry['template']=None
                    fields={'association_required':f'review-pair-{index}','dose_quantity_missing':f'review-instruction-{index}-dose_quantity_raw','dose_unit_missing':f'review-instruction-{index}-dose_unit_raw','duration_missing':f'review-instruction-{index}-duration_raw','duration_unsupported':f'review-instruction-{index}-duration_raw','notation_confirmation_required':f'review-slots-{index}'}
                    target=fields.get(next(iter(entry['issues']),''),f'medicine-{index}')
                    entry.update(name=meds[index]['name'],dose_quantity=item.get('dose_quantity_raw'),dose_unit=item.get('dose_unit_raw'),duration=item.get('duration_raw'),food_timing=item.get('timing_raw'),original_text=item.get('raw_text'),review_path=f'/dashboard/analysis#{target}')
                saved={'snapshot_id':secrets.token_urlsafe(24),'confirmed_at':datetime.now(timezone.utc).isoformat(),'analysis_id':analysis_id,'medicine_revision':session.revision,
                    'instruction_revision':ins['revision'],'scheduling_revision':session.scheduling_revision,'confirmed':True,'medicines':entries}
                session.confirmed_prescription=saved
                return copy.deepcopy(saved)
            except Exception:
                session.invalidate();invalidate(ins)
                raise

    @app.get('/api/confirmed-prescription/current')
    def confirmed_current(request:Request):
        session=load(request)
        with session.lock:
            return {'snapshot':snapshot(session),'course':copy.deepcopy(session.generated_course)}

    @app.post('/api/confirmed-prescription/generate')
    def generate(body:Generate,request:Request):
        session=load(request)
        with session.lock:
            saved=snapshot(session)
            if not saved or saved['snapshot_id']!=body.snapshot_id:reject(409,'stale_result','Confirm the current prescription review before generating a schedule.')
            try:
                if date.fromisoformat(body.start_date).isoformat()!=body.start_date:raise ValueError
            except ValueError:reject(422,'invalid_start_date','Choose a valid start date.')
            if session.generated_course and session.generated_course['start_date']==body.start_date:return copy.deepcopy(session.generated_course)
            session.generated_course=None
            session.scheduling_state.pop('result',None)
            session.scheduling_state['course_results']=[]
            eligible=[m for m in saved['medicines'] if not m['issues'] and m['template']]
            if not eligible:reject(409,'additional_review_required','Required prescription fields are unresolved. Return to prescription review.')
            root,_=current(session);meds=root['sections']['medicines']['reviewed'];results=[]
            pending=[]
            try:
                for entry in eligible:
                    link=entry['association']['association_id']
                    if session.ai.confirmed_named_slots(link)!=entry['confirmed_slots']:reject(409,'stale_result','The confirmed timing changed. Return to review.')
                    plan={**copy.deepcopy(entry['template']),'start_date':body.start_date}
                    event=session.ai.frontend_events().register_schedule_approval(link,plan)
                    derived=DerivedSchedule.model_validate(session.ai.schedule(link,plan,event=event)).model_dump()
                    index=int(entry['medicine_ref'].removeprefix('medicine_'))-1
                    result=validate_public_result(derived['payload'],meds[index],plan)
                    if result['status']!='ok':reject(409,'additional_review_required','The schedule engine requires further prescription review.')
                    results.append({'medicine_ref':entry['medicine_ref'],'slots':entry['confirmed_slots'],'result':result})
                    pending.append({'association':entry['association'],'plan':plan,'result':derived})
            except IntegrationError:
                raise
            except (ValueError,TypeError,KeyError):
                reject(502,'invalid_response','The scheduler returned invalid output. No course is available.')
            session.scheduling_state['course_results']=pending
            session.scheduling_state.update(status='succeeded',association=pending[-1]['association'],plan=pending[-1]['plan'],result=pending[-1]['result'])
            course={'snapshot_id':saved['snapshot_id'],'start_date':body.start_date,'results':results,'blocked':[m for m in saved['medicines'] if m['issues']]}
            session.generated_course=copy.deepcopy(course)
            return course
