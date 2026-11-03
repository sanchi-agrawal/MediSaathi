"""Explicit, selected-medicine Gemini assembly over trusted bilingual facts.

The model may select only approved fact IDs. Free model clinical claims are never
rendered. No source image, prescription instructions or patient data is sent.
"""
import copy
import hashlib
import json
import httpx
from fastapi import Request,HTTPException
from pydantic import Field
from .downstream.models import Strict
from .dependencies import reader
from .sessions import COOKIE
from .section_routes import metadata
from .drug_information import identify,FIELDS,SOURCES,VERSION,approved_facts

class MedicineExplanationRequest(Strict):
    revision:str=Field(min_length=1,max_length=128)
    record_index:int=Field(ge=0,le=199)
    language:str=Field(pattern=r'^(en|hi)$')

def fail(status,category,message):raise HTTPException(status,detail={'category':category,'message':message})

def generate(ingredient,language):
    try:key,model=reader._configuration()
    except reader.ReaderConfigurationError:fail(503,'configuration_error','Gemini explanation is not configured on the Python server.')
    try:
        schema={'type':'object','additionalProperties':False,'required':['language','fact_ids'],'properties':{'language':{'type':'string','enum':[language]},'fact_ids':{'type':'array','items':{'type':'string','enum':list(FIELDS)},'minItems':len(FIELDS),'maxItems':len(FIELDS)}}}
        facts=approved_facts(ingredient,language)
        with reader.genai.Client(api_key=key,http_options=reader.types.HttpOptions(timeout=30_000,retry_options=reader.types.HttpRetryOptions(attempts=1))) as client:
            result=client.models.generate_content(model=model,contents=json.dumps({'ingredient':ingredient,'language':language,'approved_facts':facts},ensure_ascii=False),config=reader.types.GenerateContentConfig(system_instruction='Assemble a complete patient education card using only the provided approved facts. Return every fact ID exactly once, including all precautions and urgent signs. No diagnoses, doses, new facts or instructions. Return only the JSON schema.',response_mime_type='application/json',response_json_schema=schema,temperature=0))
        if not isinstance(result.text,str) or len(result.text)>8000:raise ValueError
        data=json.loads(result.text)
        if type(data) is not dict or set(data)!={'language','fact_ids'} or data['language']!=language or type(data['fact_ids']) is not list or len(data['fact_ids'])!=len(FIELDS) or set(data['fact_ids'])!=set(FIELDS):raise ValueError
        return [{'key':field,'text':facts[field]} for field in FIELDS]
    except reader.errors.APIError as exc:
        code=getattr(exc,'code',None)
        if code==429:fail(429,'quota_or_rate_limit','Gemini quota or rate limit prevented this explanation. No automatic retry was made.')
        fail(502,'provider_error','Gemini could not generate this explanation. Check server access and model configuration. No automatic retry was made.')
    except (httpx.HTTPError,ConnectionError,TimeoutError):fail(504,'network_error','Gemini could not be reached. No automatic retry was made.')
    except (ValueError,TypeError,AttributeError):fail(502,'invalid_response','Gemini returned unsupported explanation content. No clinical claims were accepted and no automatic retry was made.')
    except Exception:fail(502,'provider_error','The medicine explanation provider failed. No automatic retry was made.')

def register_patient_explanations(app,store):
    @app.post('/api/prescriptions/{analysis_id}/medicines/explain')
    def explain(analysis_id:str,body:MedicineExplanationRequest,request:Request):
        session=store.get(request.cookies.get(COOKIE))
        if not session:fail(401,'session_expired','Open the current authenticated workspace again.')
        with session.lock:
            snap=session.ai.snapshot();root=snap['prescription']
            if not session.prescription_active or not root or root['analysis_id']!=analysis_id or body.revision!=session.revision:fail(409,'stale_result','The prescription changed. Load its current reviewed records.')
            if not session.reviewed or session.confirmed_revision!=session.revision or 'medicines' not in snap['confirmed_scopes']:fail(409,'confirmation_required','Confirm the current medicine review before requesting an explanation.')
            records=root['sections']['medicines']['reviewed'] or []
            if body.record_index>=len(records):fail(422,'invalid_input','Choose a medicine in the current prescription.')
            medicine=records[body.record_index];ingredient=identify(medicine)
            ins=metadata(session,root,'instructions')
            context=[analysis_id,session.revision,body.record_index,body.language,medicine,VERSION]
            key=hashlib.sha256(json.dumps(context,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if key in session.patient_explanations:result=copy.deepcopy(session.patient_explanations[key]);result['cached']=True
            else:
                result={'status':'explained' if ingredient else 'identity_uncertain','record_index':body.record_index,'language':body.language,
                    'medicine_name':medicine['name'],'ingredient':ingredient,'identity_basis':'exact_generic_or_documented_product_match' if ingredient else None,
                    'sections':generate(ingredient,body.language) if ingredient else [],'sources':SOURCES[ingredient] if ingredient else [],
                    'reference_version':VERSION,'cached':False}
                # At most one current context per medicine/language (200 × 2).
                # Do not evict another unchanged medicine's reusable explanation.
                for old_key,old in list(session.patient_explanations.items()):
                    if old['record_index']==body.record_index and old['language']==body.language:
                        del session.patient_explanations[old_key]
                session.patient_explanations[key]=copy.deepcopy(result)
            linked=None
            if ins['confirmed_revision']==ins['revision'] and 'instructions' in snap['confirmed_scopes']:
                ref=f'medicine_{body.record_index+1:03}'
                links=[v for v in snap['associations'].values() if v['medicine_ref']==ref]
                if len(links)==1:
                    linked=next((v for v in root['sections']['instructions']['reviewed']['instructions'] if v['instruction_id']==links[0]['instruction_id']),None)
            return {**result,'analysis_id':analysis_id,'revision':session.revision,'context_revision':key,
                'prescription':{'original_medicine_text':medicine['raw_text'],'confirmed_linked_instruction':copy.deepcopy(linked)}}
