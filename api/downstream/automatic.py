"""Clinical readiness from current confirmed named slots; no frequency reparse."""
from datetime import date
from decimal import Decimal
import re
from api.dependencies import IntegrationError
from .models import Plan,PlanEvening
from confirmed_frequency import timing_proposal,engine_slot_flags,explicit_days,canonical_unit,three_slots,same_frequency

def prepare(session,medicines,instructions,associations,*,interpret_proposals=True):
    entries=[]
    for index,medicine in enumerate(medicines,1):
        ref=f'medicine_{index:03}';link=next((a for a in associations if a['medicine_ref']==ref),None)
        item=next((i for i in instructions if link and i['instruction_id']==link['instruction_id']),None)
        issues=[];plan=None;confirmed=None;proposal=None
        if not link or not item:issues.append('association_required')
        else:
            confirmed=session.ai.confirmed_named_slots(link['association_id'])
            if not confirmed and not interpret_proposals:
                issues.append('administration_count_unconfirmed')
            elif not confirmed:
                # Interpretation is confined to the review/proposal layer.
                proposal=timing_proposal(medicine,item)
                if proposal:issues.append('notation_confirmation_required')
                else:
                    if not item.get('frequency_raw') or not same_frequency(item['frequency_raw'],medicine.get('frequency_pattern')):issues.append('frequency_conflict')
                    if item.get('frequency_raw') and not three_slots(item['frequency_raw']) and item['frequency_raw'] not in ('BD','BID','TDS','TID','QID','HS'):issues.append('frequency_unsupported')
                    if not item.get('timing_raw') and not three_slots(item.get('frequency_raw')):issues.append('timing_missing')
                    if not issues:issues.append('source_requires_clarification')
            # General extraction completeness is not a scheduling approval.
            # Links above are current confirmed capabilities. The actual source
            # dose/unit/duration/timing gates below decide clinical readiness;
            # salt/confidence and legacy OCR text remain diagnostic only.
            if not medicine.get('name'):issues.append('medicine_name_missing')
            if not item.get('dose_quantity_raw'):issues.append('dose_quantity_missing')
            elif not re.fullmatch(r'(?:0|[1-9]\d*)(?:\.\d+)?',item['dose_quantity_raw']):issues.append('quantity_unsupported')
            if not item.get('dose_unit_raw'):issues.append('dose_unit_missing')
            if not item.get('duration_raw') or medicine.get('duration_days') is None:issues.append('duration_missing')
            elif not explicit_days(item['duration_raw']):issues.append('duration_unsupported')
            if not issues:
                try:
                    model=PlanEvening if 'evening' in confirmed else Plan
                    candidate=model.model_validate(dict(dose_quantity=float(Decimal(item['dose_quantity_raw'])),dose_unit=canonical_unit(item['dose_unit_raw']),duration_days=explicit_days(item['duration_raw']),start_date=date.today().isoformat(),administrations_by_slot=engine_slot_flags(confirmed))).model_dump()
                    session.ai._schedule_request(link['association_id'],candidate)
                    plan={k:v for k,v in candidate.items() if k!='start_date'}
                except (ValueError,TypeError,ArithmeticError,IntegrationError):issues.append('source_requires_clarification')
        entries.append(dict(medicine_ref=ref,association=link,template=plan,issues=issues,confirmed_slots=confirmed or [],proposed_slots=confirmed or (proposal['slots'] if proposal else [])))
    return entries
