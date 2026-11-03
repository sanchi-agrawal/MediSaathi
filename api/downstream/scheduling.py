"""Bridge guarded AIIntegration handoffs to unchanged Person 3 arithmetic."""
import copy
from datetime import date, timedelta
from decimal import Decimal
from api.dependencies import AIIntegration, reader
import schedule as engine
from .models import EngineRefusal, EngineSuccess, PublicSuccess, Plan,PlanEvening,EngineSuccessEvening,PublicSuccessEvening
from .models import CountPlan,CountEngineSuccess,CountPublicSuccess
from confirmed_frequency import engine_slot_flags


def validate_public_result(payload, medicine, plan):
    """Revalidate at the HTTP boundary, including injected trusted callbacks."""
    if type(payload) is not dict:
        raise ValueError("Invalid scheduler result")
    if payload.get("status") != "ok":
        return EngineRefusal.model_validate(payload).model_dump()
    counted='administrations_per_day' in plan
    checked = (CountPublicSuccess if counted else PublicSuccessEvening if 'evening' in payload.get('doses_by_slot',{}) else PublicSuccess).model_validate(payload)
    start = date.fromisoformat(plan["start_date"])
    dose = Decimal(str(plan["dose_quantity"]))
    slots = {f'administration_{i+1}':1 for i in range(plan['administrations_per_day'])} if counted else plan["administrations_by_slot"]
    if checked.name != (medicine["name"] or "unknown") or checked.unit != plan["dose_unit"] or checked.start_date != start or checked.duration_days != plan["duration_days"]:
        raise ValueError("Scheduler result disagrees with approved plan")
    doses=checked.doses_by_slot if counted else checked.doses_by_slot.model_dump()
    if set(doses)!=set(slots):raise ValueError('Schedule administration count disagrees with confirmed source')
    for slot, value in doses.items():
        if Decimal(str(value)) != dose * slots[slot]:
            raise ValueError("Scheduler slots disagree with explicit timing")
    per_day = dose * sum(slots.values())
    if not per_day or Decimal(str(checked.units_per_day)) != per_day or Decimal(str(checked.total_units)) != per_day * plan["duration_days"]:
        raise ValueError("Scheduler quantities disagree with approved plan")
    end = start + timedelta(days=plan["duration_days"] - 1)
    refill = end - timedelta(days=engine.REFILL_BUFFER_DAYS) if plan["duration_days"] >= engine.LONG_TERM_DAYS else None
    if checked.end_date != end or checked.refill_date != refill:
        raise ValueError("Scheduler dates disagree with approved plan")
    return checked.model_dump()

def schedule_handoff(request):
    # Called only through AIIntegration.schedule after its source/approval gates.
    medicine = copy.deepcopy(request["medicine"])
    if set(medicine) != set(reader.FIELDS):
        raise ValueError("Invalid scheduling handoff")
    counted='confirmed_count' in request
    plan = (CountPlan if counted else PlanEvening if 'evening' in request['plan'].get('administrations_by_slot',{}) else Plan).model_validate(request["plan"]).model_dump()
    if counted and request['confirmed_count']!=plan['administrations_per_day']:raise ValueError('Plan disagrees with confirmed daily count')
    if not counted and engine_slot_flags(request['confirmed_slots'])!=plan['administrations_by_slot']:
        raise ValueError('Plan disagrees with confirmed named slots')
    start = date.fromisoformat(plan["start_date"])
    if start.isoformat() != plan["start_date"]:
        raise ValueError("Invalid scheduling date")
    engine_unit = "ml" if plan["dose_unit"] == "mL" else plan["dose_unit"]
    # This is a distinct clinical-plan DTO, not a reclassified OCR record.
    # AIIntegration has already required current independently confirmed scopes,
    # an explicit bound association and source-supported dose/unit/duration/count.
    # Keep the original ten fields and OCR flag untouched in request['medicine'].
    engine_input=dict(name=medicine['name'],form=medicine['form'],
        duration_days=plan['duration_days'],dose_quantity=plan['dose_quantity'],
        dose_unit=engine_unit,confirmed=True,needs_review=False)
    result = engine.build_schedule(engine_input,start,confirmed_count=request['confirmed_count']) if counted else engine.build_schedule(engine_input, start, request['confirmed_slots'])
    if type(result) is not dict:
        raise ValueError("Invalid scheduler output")
    if result.get("status") != "ok":
        checked = EngineRefusal.model_validate(result)
        return {"name": checked.name, "status": checked.status,
                "reason": "The engine requires clarification; return to prescription review. No schedule was generated."}
    checked = (CountEngineSuccess if counted else EngineSuccessEvening if 'evening' in result.get('doses_by_slot',{}) else EngineSuccess).model_validate(result)
    if checked.name != (medicine["name"] or "unknown") or checked.unit != engine_unit or checked.start_date != start or checked.duration_days != plan["duration_days"]:
        raise ValueError("Scheduler output disagrees with approved plan")
    payload = checked.model_dump()
    payload["unit"] = plan["dose_unit"]  # only validated ml -> mL conversion
    return validate_public_result(payload, request["medicine"], plan)

def integration_factory():
    return AIIntegration(downstream={"schedule": schedule_handoff})
