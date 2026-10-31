"""Session-bound candidates, audited availability and side-effect-free previews."""
import copy,re
from datetime import date,datetime,timedelta,timezone
from fastapi import Request
from .sessions import COOKIE
from .section_routes import reject,metadata
from .team_models import MedicineBinding,CandidateSelection,PriceLookup,PreviewRequest
from .team_matching import identify
from .vendor.person3.reminders import refill_alerts
from pricing_dataset.lookup import lookup
IST=timezone(timedelta(hours=5,minutes=30),'Asia/Kolkata')
def schedule_date(value):
    # Scheduling state uses validated native dates; HTTP snapshots use ISO strings.
    if type(value) is date:return value
    return date.fromisoformat(value)

def register_team_routes(app,store,enabled_sections):
    def load(request):
        session=store.get(request.cookies.get(COOKIE))
        if session is None:reject(401,'session_expired','Open a prescription in the current demo session.')
        return session
    def medicine_context(s,analysis_id=None,revision=None):
        snap=s.ai.snapshot();root=snap['prescription']
        if not s.prescription_active or root is None or analysis_id is not None and root['analysis_id']!=analysis_id or revision is not None and revision!=s.revision:
            reject(409,'stale_result','Prescription or medicine revision changed. Reload current records.')
        if not s.reviewed or s.confirmed_revision!=s.revision or 'medicines' not in snap['confirmed_scopes']:
            reject(409,'confirmation_required','Independently confirm the current medicine review first.')
        return root
    def matching_view(s,root):
        state=s.matching_state
        if state.get('analysis_id')!=root['analysis_id'] or state.get('revision')!=s.revision:state={}
        return {'analysis_id':root['analysis_id'],'revision':s.revision,'records':copy.deepcopy(state.get('records',[])),
                'state':'ready' if state else 'not_requested'}
    @app.get('/api/matching/current')
    def matching_current(request:Request):
        s=load(request)
        with s.lock:return matching_view(s,medicine_context(s))
    @app.post('/api/prescriptions/{analysis_id}/matching')
    def match(analysis_id:str,body:MedicineBinding,request:Request):
        s=load(request)
        with s.lock:
            root=medicine_context(s,analysis_id,body.revision)
            state=matching_view(s,root)
            if state['state']=='ready':return state
            try:
                records=[{'medicine_ref':f'medicine_{i+1:03d}','name':m['name'],**identify(m)} for i,m in enumerate(root['sections']['medicines']['reviewed'])]
            except Exception:
                reject(503,'catalogue_unavailable','Catalogue candidates are unavailable. No selection was made.')
            s.matching_state={'analysis_id':analysis_id,'revision':s.revision,'records':records}
            return matching_view(s,root)
    @app.post('/api/prescriptions/{analysis_id}/matching/selection')
    def select(analysis_id:str,body:CandidateSelection,request:Request):
        s=load(request)
        with s.lock:
            root=medicine_context(s,analysis_id,body.revision);state=matching_view(s,root)
            row=next((r for r in state['records'] if r['medicine_ref']==body.medicine_ref),None)
            if row is None or not any(c['candidate_id']==body.candidate_id for c in row['candidates']):
                reject(409,'invalid_candidate','Select a candidate from the current server-generated list.')
            for r in s.matching_state['records']:
                if r['medicine_ref']==body.medicine_ref:r['selected']=body.candidate_id
            return matching_view(s,root)
    @app.get('/api/pricing/catalogue')
    def pricing_catalogue(kind:str,request:Request):
        load(request)
        if kind not in ('medicine','lab'):reject(422,'invalid_input','Choose medicine or lab.')
        try:
            from pricing_dataset.audit import load_audit
            data=load_audit()
            if data['quotes']:reject(503,'reaudit_required','New quotes require integration review.')
            return {'items':[item for item in data['items'] if item['kind']==kind],'verified_delhi_quote_count':0,'comparisons_enabled':False}
        except Exception:reject(503,'dataset_unavailable','Audited catalogue could not be validated. No price is displayed.')
    @app.post('/api/pricing/lookup')
    def price(body:PriceLookup,request:Request):
        load(request);result=lookup(kind=body.kind,item_id=body.item_id,name=body.name)
        if result['state']=='error':reject(503 if result['error_code']=='dataset_invalid' else 422,'dataset_unavailable' if result['error_code']=='dataset_invalid' else 'invalid_input','The read-only price lookup could not be validated.')
        if result['quotes']:reject(503,'reaudit_required','New verified quotes require a separate integration review.')
        return {**result,'comparisons_enabled':False,'message':'No verified Delhi price available' if result['item'] else 'Choose an exact audited catalogue item; no identity or price was inferred.'}
    @app.post('/api/prescriptions/{analysis_id}/reminder-preview')
    def preview(analysis_id:str,body:PreviewRequest,request:Request):
        s=load(request)
        with s.lock:
            root=medicine_context(s,analysis_id,body.medicine_revision)
            snap=s.ai.snapshot();ins=metadata(s,root,'instructions');state=s.scheduling_state
            if 'instructions' not in enabled_sections or body.instruction_revision!=ins['revision'] or body.scheduling_revision!=s.scheduling_revision:
                reject(409,'stale_result','Schedule or source revision changed. Reload scheduling.')
            if not ins['reviewed'] or ins['confirmed_revision']!=ins['revision'] or 'instructions' not in snap['confirmed_scopes']:
                reject(409,'confirmation_required','Confirm the current instructions first.')
            if state.get('status')!='succeeded' or not state.get('association') or state['association']['association_id']!=body.association_id or not state.get('result') or state['result']['payload']['status']!='ok':
                reject(409,'approval_required','An approved current schedule is required for a reminder preview.')
            p=copy.deepcopy(state['result']['payload']);active={slot for slot,amount in p['doses_by_slot'].items() if amount>0}
            if set(body.clock_times)!=active or any(not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',v) for v in body.clock_times.values()):
                reject(422,'clock_times_required','Enter a valid clock time for each active slot. Generic slots do not imply clock times.')
            if len(set(body.clock_times.values()))!=len(active):reject(422,'conflicting_times','Distinct administration slots need distinct preference times.')
            now=datetime.now(IST);today=now.date();start=schedule_date(p['start_date']);end=schedule_date(p['end_date'])
            first=max(today,start);last=min(end,first+timedelta(days=6));doses=[]
            for offset in range(max(0,(last-first).days+1)):
                day=first+timedelta(days=offset)
                for slot in active:
                    due=datetime.fromisoformat(day.isoformat()+'T'+body.clock_times[slot]).replace(tzinfo=IST)
                    if due>=now:doses.append({'slot':slot,'due_at':due.isoformat(),'amount':p['doses_by_slot'][slot],'unit':p['unit']})
            p.update(start_date=start,end_date=end,refill_date=schedule_date(p['refill_date']) if p['refill_date'] else None)
            return {'analysis_id':analysis_id,'medicine_revision':s.revision,'instruction_revision':ins['revision'],'scheduling_revision':s.scheduling_revision,'association_id':body.association_id,
                    'state':'ready' if doses else 'no_upcoming_doses','timezone':'Asia/Kolkata','window_days':7,
                    'clock_times':body.clock_times,'doses':sorted(doses,key=lambda d:(d['due_at'],d['slot'])),
                    'refill_notes':refill_alerts([p],today),'notifications_enabled':False,
                    'notice':'Reminder Preview — Notifications not enabled. Clock times are your preferences, not medical instructions. Preview covers at most seven days.'}
