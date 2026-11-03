"""Strict requests and scheduler results. Browser approval claims are forbidden."""
from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field,field_validator

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

class SlotsEvening(Slots):
    evening:Annotated[int,Field(ge=0,le=1)]

class PlanEvening(Plan):
    administrations_by_slot:SlotsEvening

class CountPlan(Strict):
    dose_quantity:Annotated[int|float,Field(gt=0,le=1000,allow_inf_nan=False)]
    dose_unit:Literal['tablet','capsule','mL','drop']
    duration_days:Annotated[int,Field(ge=1,le=365)]
    administrations_per_day:Annotated[int,Field(ge=1,le=5)]
    start_date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$',max_length=10)

class Binding(Strict):
    medicine_revision: str = Field(min_length=1, max_length=128)
    instruction_revision: str = Field(min_length=1, max_length=128)
    scheduling_revision: str = Field(min_length=1, max_length=128)

class AssociationRequest(Binding):
    medicine_ref: str = Field(min_length=1, max_length=128)
    instruction_id: str = Field(min_length=1, max_length=128)

class LinkedRequest(Binding):
    association_id: str = Field(min_length=1, max_length=128)

class SlotsConfirmationRequest(LinkedRequest):
    slots:list[Literal['morning','afternoon','night','bedtime']]=Field(min_length=1,max_length=4)

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

class DosesEvening(Doses):
    evening:Number

class EngineSuccessEvening(EngineSuccess):
    doses_by_slot:DosesEvening

class PublicSuccessEvening(PublicSuccess):
    doses_by_slot:DosesEvening

class CountEngineSuccess(EngineSuccess):
    doses_by_slot:dict[str,Positive]
    @field_validator('doses_by_slot')
    @classmethod
    def ordered_count(cls,value):
        if not 1<=len(value)<=5 or set(value)!={f'administration_{i+1}' for i in range(len(value))}:raise ValueError('Invalid administration result')
        return value

class CountPublicSuccess(CountEngineSuccess):
    unit:Literal['tablet','capsule','mL','drop']

class DerivedSchedule(Strict):
    derived_id: str = Field(min_length=1)
    payload: PublicSuccess | PublicSuccessEvening | CountPublicSuccess | EngineRefusal
