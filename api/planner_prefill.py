"""Read-only reviewed workspace data for the website-only demo planner.

No OCR, association writes, eligibility endpoint, schedule approval or engine call.
"""
from decimal import Decimal,InvalidOperation
import hashlib,json,re,time
from fastapi import Request,HTTPException
from .sessions import COOKIE
from .section_routes import metadata
from .dependencies import IntegrationError
from ai_integration import _unsafe_instruction
from confirmed_count import literal_count
from confirmed_frequency import canonical_unit,explicit_days
from prescription_language import ascii_digits,explicit_days as explicit_hindi_days

def norm(value):return ' '.join((value or '').casefold().split())

def explicit_names(medicine):
    names={norm(medicine.get('name'))}
    raw=medicine.get('raw_text') or ''
    # Only a visibly bilingual parenthesis supplies an alternate written name.
    match=re.fullmatch(r'\s*(.+?)\s+[0-9०-९]+\s*मि\.?\s*ग्रा\.?\s*\([A-Za-z][A-Za-z .-]*?\s+[0-9०-९]+\s*(?:mg|g|mcg)\)\s*',raw,re.I)
    if match:names.add(norm(match[1]))
    return names-{''}

def view(session):
    empty={'analysis_id':None,'medicines':[],'contract':'reviewed-planner-prefill-v1'}
    if session is None or not session.prescription_active:return empty
    root=session.ai.snapshot()['prescription']
    if root is None:return empty
    sections=root['sections'];meds=sections['medicines']['reviewed'] or sections['medicines']['payload'] or []
    envelope=sections['instructions']['reviewed'] or {'instructions':[],'issues':[]}
    instructions=envelope['instructions'];ins_state=metadata(session,root,'instructions')
    result=[];links=session.ai.snapshot()['associations']
    for index,med in enumerate(meds,1):
        ref=f'medicine_{index:03}';missing=[];item=None;count=None;relationship=None
        if not session.reviewed:missing.append('medicine_review')
        if not ins_state['reviewed']:missing.append('instruction_review')
        if not missing:
            linked=[(key,value) for key,value in links.items() if value['medicine_ref']==ref]
            if len(linked)==1:
                identity,link=linked[0]
                try:
                    slots=session.ai.confirmed_named_slots(identity)
                    receipt=session.ai.confirmed_daily_count(identity)
                    item=next((v for v in instructions if v['instruction_id']==link['instruction_id']),None)
                    count=len(slots) if slots else receipt['count'] if receipt else None
                    relationship='confirmed_link'
                except IntegrationError:missing.append('instruction_relationship')
            else:
                # A read-only exact join, never a fuzzy/substitution decision or
                # an association acknowledgement. Duplicate names stay unknown.
                aliases=explicit_names(med)
                matches=[v for v in instructions if norm(v['medicine_name_raw']) in aliases]
                unique=all(not aliases.intersection(explicit_names(v)) for v in meds if v is not med)
                if len(matches)==1 and unique:item=matches[0];relationship='unique_reviewed_name'
                else:missing.append('instruction_relationship')
        quantity=None;unit=None;days=None
        if not med['name']:missing.append('medicine_name')
        if item is not None:
            if _unsafe_instruction(envelope,item):missing.append('instruction_uncertainty')
            raw=item['raw_text'] or ''
            for field,reason in (('dose_quantity_raw','dose_quantity'),('dose_unit_raw','dose_unit'),('duration_raw','duration_days')):
                if not item[field] or item[field] not in raw:missing.append(reason)
            try:
                text=ascii_digits(item['dose_quantity_raw'] or '')
                number=Decimal(text)
                if not re.fullmatch(r'(?:0|[1-9]\d*)(?:\.\d+)?',text) or not number.is_finite() or not 0<number<=1000:raise ValueError
                if not item['dose_unit_raw'] or not re.search(r'(?<![\w/])'+re.escape(text)+r'\s*'+re.escape(item['dose_unit_raw'])+r'(?![\w/])',ascii_digits(raw)):raise ValueError
                quantity=float(number)
            except (InvalidOperation,ValueError):missing.append('dose_quantity')
            unit=canonical_unit(item['dose_unit_raw']) or {'गोली':'tablet','गोलियाँ':'tablet','कैप्सूल':'capsule','बूँद':'drop','बूंद':'drop'}.get(item['dose_unit_raw'])
            if unit not in ('tablet','capsule','mL','drop','dose'):unit=None;missing.append('dose_unit')
            # A form does not establish a dose, but an explicit contradiction
            # between a solid form and administration unit requires correction.
            if med['form'] in ('tablet','capsule') and unit and med['form']!=unit:missing.append('dose_unit')
            days=explicit_days(item['duration_raw']) or explicit_hindi_days(item['duration_raw'])
            if days is None or not 1<=days<=366:days=None;missing.append('duration_days')
            if count is None:
                receipt=literal_count(med,item)
                if receipt:count=receipt['count']
            if count is None or not 1<=count<=12:count=None;missing.append('administrations_per_day')
        else:
            missing.extend(['dose_quantity','dose_unit','duration_days','administrations_per_day'])
        record={'medicine_ref':ref,'name':med['name'],'quantity':quantity,'unit':unit,'days':days,
            'administrations_per_day':count,'relationship':relationship,'instruction_id':item['instruction_id'] if item else None,
            'missing':sorted(set(missing)),'eligible':not missing}
        fingerprint=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        result.append({**record,'fingerprint':fingerprint})
    return {'analysis_id':root['analysis_id'],'medicine_revision':session.revision,'instruction_revision':ins_state['revision'],
        'medicines':result,'contract':'reviewed-planner-prefill-v1'}

def register_planner_prefill(app,store):
    @app.get('/api/planner/prescription')
    def current(request:Request):
        handle=request.cookies.get(COOKIE);session=store.get(handle)
        owner=None;service=getattr(app.state,'local_accounts',None)
        if service is not None:
            # Middleware has replaced browser cookies with this verified
            # workspace handle. Return its actual owner to prevent a tab/account
            # switch race from caching another account's source under an old UI.
            with service.lock:
                key=next((key for key,value in service.workspaces.items() if value==handle),None)
                with service.connect() as db:
                    row=db.execute('SELECT user_id FROM sessions WHERE token_hash=? AND expires_at>?',(key,int(time.time()))).fetchone() if key else None
                if row:owner=row['user_id']
            if owner is None:raise HTTPException(401,detail={'category':'session_expired','message':'Sign in again.'})
        if session is None:return {**view(None),'owner_id':owner}
        with session.lock:return {**view(session),'owner_id':owner}
