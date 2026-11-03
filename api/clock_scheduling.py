"""Clock preferences over existing independently confirmed prescription records.

No extraction, frequency interpretation, linking or clinical edits happen here.
The existing named timing confirmation establishes the administration count.
"""
import copy
import re
from datetime import date,timedelta
from decimal import Decimal
from fastapi import Request
from pydantic import Field
from .downstream.models import Strict,Binding,DerivedSchedule,CountPlan
from .downstream.automatic import prepare
from .downstream.scheduling import validate_public_result
from .dependencies import IntegrationError
from .medicine_review import requirements
from confirmed_frequency import explicit_days,canonical_unit

def food_text(value):
    # Display only literal food-related phrases, not the frequency/source code.
    phrases=re.findall(r'\b(?:before|after|with)\s+(?:food|meals?)\b|\bon\s+an?\s+empty\s+stomach\b|खाने\s*(?:से\s*पहले|के\s*बाद|के\s*साथ)|खाली\s*पेट',value or '',re.I)
    return ' · '.join(phrases) or None


class ClockInput(Strict):
    medicine_ref:str=Field(min_length=1,max_length=128)
    clock_times:list[str]=Field(min_length=1,max_length=5)

class ClockRequest(Binding):
    start_date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$',max_length=10)
    medicines:list[ClockInput]=Field(min_length=1,max_length=200)

def register_clock_scheduling(app,load,context,reject):
    def state(session):
        root,ins,ready=context(session)
        sections=root['sections'];medicines=sections['medicines']['reviewed'] or []
        instructions=(sections['instructions']['reviewed'] or {}).get('instructions',[])
        # Recover genuine current AIIntegration links, not frontend success text
        # or exact-name guesses. The capability getters verify scope bindings.
        links=[]
        if ready:
            for identity,link in session.ai.snapshot()['associations'].items():
                session.ai.confirmed_named_slots(identity)
                links.append({'association_id':identity,'medicine_ref':link['medicine_ref'],'instruction_id':link['instruction_id']})
            session.scheduling_state['associations']=copy.deepcopy(links)
        prepared=prepare(session,medicines,instructions,links,interpret_proposals=False) if ready else []
        # Literal daily counts were established in the ordinary confirmed
        # association action, never parsed or guessed by this scheduling route.
        for entry in prepared:
            if entry['confirmed_slots'] or not entry['association']:continue
            link=entry['association'];count=session.ai.confirmed_daily_count(link['association_id'])
            if not count:continue
            entry.update(count=count['count'],confirmed_slots=count.get('slots',[]))
            entry['issues']=[issue for issue in entry['issues'] if issue!='administration_count_unconfirmed']
            if entry['issues']:continue
            item=next((v for v in instructions if v['instruction_id']==link['instruction_id']),{})
            try:
                candidate=CountPlan.model_validate({'dose_quantity':float(Decimal(item.get('dose_quantity_raw') or 'NaN')),
                    'dose_unit':canonical_unit(item.get('dose_unit_raw')),'duration_days':explicit_days(item.get('duration_raw')),
                    'administrations_per_day':count['count'],'start_date':date.today().isoformat()}).model_dump()
                session.ai._schedule_request(link['association_id'],candidate,count_mode=True)
                entry.update(template={k:v for k,v in candidate.items() if k!='start_date'},issues=[],count_mode=True,count=count['count'],confirmed_slots=count.get('slots',[]))
            except (ValueError,TypeError,ArithmeticError,IntegrationError):
                entry['issues']=[issue for issue in entry['issues'] if issue!='administration_count_unconfirmed']+['source_requires_clarification']
        entries=[]
        review_details=requirements(sections['medicines']['payload'],medicines)
        for index,medicine in enumerate(medicines,1):
            ref=f'medicine_{index:03}'
            entry=next((v for v in prepared if v['medicine_ref']==ref),None)
            item=next((v for v in instructions if entry and entry['association'] and v['instruction_id']==entry['association']['instruction_id']),{})
            plan=entry['template'] if entry else None
            issue=next(iter(entry['issues']),'') if entry else 'confirmation_required'
            field={'administration_count_unconfirmed':'frequency_raw','duration_missing':'duration_raw','duration_unsupported':'duration_raw','dose_unit_missing':'dose_unit_raw'}.get(issue,'dose_quantity_raw')
            review_path='/dashboard/analysis#instruction-review' if not ready else '/dashboard/analysis#schedule-associations' if not entry or not entry['association'] else '/dashboard/analysis#review-'+entry['association']['instruction_id']+'-'+field
            if entry and 'medicine_review_flag' in entry['issues']:review_path='/dashboard/analysis'
            entries.append({'medicine_ref':ref,'name':medicine['name'],
                'dose_quantity':item.get('dose_quantity_raw') if ready else None,
                'dose_unit':item.get('dose_unit_raw') if ready else None,
                'duration_days':medicine['duration_days'] if ready and medicine['duration_days']==explicit_days(item.get('duration_raw')) else None,
                'food_timing':food_text(item.get('timing_raw')) if ready else None,
                'slots':entry['confirmed_slots'] if entry else [],
                'administrations_per_day':entry.get('count',len(entry['confirmed_slots'])) if entry else 0,
                'eligible':bool(plan and not entry['issues']),
                'review_details':review_details[index-1] if medicine.get('needs_review') is True else None,
                'issues':entry['issues'] if entry else ['confirmation_required'],
                'review_path':review_path})
        return root,prepared,{'analysis_id':root['analysis_id'],'medicine_revision':session.revision,
            'instruction_revision':ins['revision'],'scheduling_revision':session.scheduling_revision,
            'ready':ready,'medicines':entries,'course':copy.deepcopy(session.scheduling_state.get('clock_course')),
            'timezone':'Asia/Kolkata','contract':'confirmed-clock-schedule-v1'}

    @app.get('/api/clock-scheduling/current')
    def current(request:Request):
        session=load(request)
        with session.lock:return state(session)[2]

    @app.post('/api/prescriptions/{analysis_id}/schedule/clock-generate')
    def generate(analysis_id:str,body:ClockRequest,request:Request):
        session=load(request)
        with session.lock:
            context(session,analysis_id,body,require=True)
            root,prepared,view=state(session)
            # Validate a replacement before replacing the current calendar.
            # An invalid preference submission is not a prescription edit.
            try:
                start=date.fromisoformat(body.start_date)
                if start.isoformat()!=body.start_date:raise ValueError
            except ValueError:reject(422,'invalid_start_date','Choose a valid calendar start date.')
            eligible=[v for v in prepared if v['template'] and not v['issues']]
            supplied={v.medicine_ref:v.clock_times for v in body.medicines}
            if not eligible:reject(409,'additional_review_required','Confirmed dose, duration and administration count are required. Return to Prescription Review.')
            if len(supplied)!=len(body.medicines) or set(supplied)!={v['medicine_ref'] for v in eligible}:
                reject(422,'invalid_clock_times','Provide times for each eligible medicine exactly once. Do not add administrations or unconfirmed medicines.')
            for entry in eligible:
                times=supplied[entry['medicine_ref']]
                if len(times)!=entry.get('count',len(entry['confirmed_slots'])) or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',v) for v in times) or len(set(times))!=len(times):
                    reject(422,'invalid_clock_times','Choose one distinct HH:MM clock time for each confirmed administration.')
                if times!=sorted(times):
                    reject(422,'invalid_clock_times','Enter times in the displayed order within the same course day. Overnight course-day changes require clarification.')
            pending=[];courses=[]
            try:
                for entry in eligible:
                    plan={**copy.deepcopy(entry['template']),'start_date':body.start_date}
                    identity=entry['association']['association_id']
                    event=session.ai.frontend_events().register_schedule_approval(identity,plan)
                    derived=DerivedSchedule.model_validate(session.ai.schedule(identity,plan,event=event,count_mode=entry.get('count_mode',False))).model_dump()
                    index=int(entry['medicine_ref'].removeprefix('medicine_'))-1
                    result=validate_public_result(derived['payload'],root['sections']['medicines']['reviewed'][index],plan)
                    if result['status']!='ok':reject(409,'additional_review_required','Prescription information requires clarification. No clock schedule was generated.')
                    times=supplied[entry['medicine_ref']]
                    administrations=[{'slot':entry['confirmed_slots'][i] if entry['confirmed_slots'] else None,'time':clock,'quantity':plan['dose_quantity'],'unit':plan['dose_unit']} for i,clock in enumerate(times)]
                    days=[{'date':(start+timedelta(days=i)).isoformat(),
                        'administrations':[{**a,'at':(start+timedelta(days=i)).isoformat()+'T'+a['time']+':00+05:30'} for a in administrations]} for i in range(result['duration_days'])]
                    courses.append({'medicine_ref':entry['medicine_ref'],'result':result,'clock_times':times,'days':days})
                    pending.append({'association':entry['association'],'plan':plan,'result':derived})
            except IntegrationError:raise
            except (ValueError,TypeError,KeyError):reject(502,'invalid_response','The schedule engine returned invalid output. No clock schedule is available.')
            course={'start_date':body.start_date,'timezone':'Asia/Kolkata','medicines':courses,
                'blocked':[v for v in view['medicines'] if not v['eligible']],
                'medicine_revision':session.revision,'instruction_revision':view['instruction_revision'],'scheduling_revision':session.scheduling_revision}
            session.scheduling_state.update(status='succeeded',course_results=pending,clock_course=copy.deepcopy(course),
                association=pending[-1]['association'],plan=pending[-1]['plan'],result=pending[-1]['result'])
            return course
