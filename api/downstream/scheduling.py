"""Bridge guarded AIIntegration handoffs to unchanged Person 3 arithmetic."""
import copy
from datetime import date, timedelta
from decimal import Decimal
from api.dependencies import AIIntegration, reader
import schedule as engine
from .models import EngineRefusal, EngineSuccess, PublicSuccess, Plan


def validate_public_result(payload, medicine, plan):
    """Revalidate at the HTTP boundary, including injected trusted callbacks."""
    if type(payload) is not dict:
        raise ValueError("Invalid scheduler result")
    if payload.get("status") != "ok":
        return EngineRefusal.model_validate(payload).model_dump()
    checked = PublicSuccess.model_validate(payload)
    start = date.fromisoformat(plan["start_date"])
    dose = Decimal(str(plan["dose_quantity"]))
    slots = plan["administrations_by_slot"]
    if checked.name != (medicine["name"] or "unknown") or checked.unit != plan["dose_unit"] or checked.start_date != start or checked.duration_days != plan["duration_days"]:
        raise ValueError("Scheduler result disagrees with approved plan")
    for slot, value in checked.doses_by_slot.model_dump().items():
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
    plan = Plan.model_validate(request["plan"]).model_dump()
    start = date.fromisoformat(plan["start_date"])
    if start.isoformat() != plan["start_date"]:
        raise ValueError("Invalid scheduling date")
    engine_unit = "ml" if plan["dose_unit"] == "mL" else plan["dose_unit"]
    # Temporary input only: do not overwrite source fields or needs_review.
    medicine.update(confirmed=True, dose_quantity=plan["dose_quantity"], dose_unit=engine_unit)
    result = engine.build_schedule(medicine, start)
    if type(result) is not dict:
        raise ValueError("Invalid scheduler output")
    if result.get("status") != "ok":
        checked = EngineRefusal.model_validate(result)
        return {"name": checked.name, "status": checked.status,
                "reason": "The engine requires clarification; return to prescription review. No schedule was generated."}
    checked = EngineSuccess.model_validate(result)
    if checked.name != (medicine["name"] or "unknown") or checked.unit != engine_unit or checked.start_date != start or checked.duration_days != plan["duration_days"]:
        raise ValueError("Scheduler output disagrees with approved plan")
    payload = checked.model_dump()
    payload["unit"] = plan["dose_unit"]  # only validated ml -> mL conversion
    return validate_public_result(payload, request["medicine"], plan)

def integration_factory():
    return AIIntegration(downstream={"schedule": schedule_handoff})
