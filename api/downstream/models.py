"""Strict requests and scheduler results. Browser approval claims are forbidden."""
from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)

Number = Annotated[int | float, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[int | float, Field(gt=0, allow_inf_nan=False)]

class Slots(Strict):
    morning: Annotated[int, Field(ge=0, le=1)]
    noon: Annotated[int, Field(ge=0, le=1)]
    night: Annotated[int, Field(ge=0, le=1)]
    bedtime: Annotated[int, Field(ge=0, le=1)]

class Doses(Strict):
    morning: Number
    noon: Number
    night: Number
    bedtime: Number

class Plan(Strict):
    dose_quantity: Annotated[int | float, Field(gt=0, le=1000, allow_inf_nan=False)]
    dose_unit: Literal["tablet", "capsule", "mL", "drop"]
    duration_days: Annotated[int, Field(ge=1, le=365)]
    administrations_by_slot: Slots
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", max_length=10)

class Binding(Strict):
    medicine_revision: str = Field(min_length=1, max_length=128)
    instruction_revision: str = Field(min_length=1, max_length=128)
    scheduling_revision: str = Field(min_length=1, max_length=128)

class AssociationRequest(Binding):
    medicine_ref: str = Field(min_length=1, max_length=128)
    instruction_id: str = Field(min_length=1, max_length=128)

class LinkedRequest(Binding):
    association_id: str = Field(min_length=1, max_length=128)

class PlanRequest(LinkedRequest):
    plan: Plan

class EngineSuccess(Strict):
    name: str
    status: Literal["ok"]
    reason: None
    doses_by_slot: Doses
    units_per_day: Positive
    duration_days: Annotated[int, Field(ge=1, le=365)]
    total_units: Positive
    unit: Literal["tablet", "capsule", "ml", "drop"]
    start_date: date
    end_date: date
    refill_date: date | None

class EngineRefusal(Strict):
    name: str
    status: Literal["needs_input", "as_needed"]
    reason: str = Field(min_length=1)

class PublicSuccess(EngineSuccess):
    unit: Literal["tablet", "capsule", "mL", "drop"]

class DerivedSchedule(Strict):
    derived_id: str = Field(min_length=1)
    payload: PublicSuccess | EngineRefusal
