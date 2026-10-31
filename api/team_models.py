"""Strict additive integration requests; source records remain unchanged."""
from typing import Literal
from pydantic import Field
from .downstream.models import Strict, LinkedRequest

class MedicineBinding(Strict):
    revision: str = Field(min_length=1,max_length=128)

class CandidateSelection(MedicineBinding):
    medicine_ref: str = Field(pattern=r'^medicine_[0-9]{3,}$',max_length=128)
    candidate_id: str = Field(min_length=1,max_length=128)

class PriceLookup(Strict):
    kind: Literal['medicine','lab']
    item_id: str | None = Field(default=None,min_length=1,max_length=128)
    name: str | None = Field(default=None,min_length=1,max_length=300)

class PreviewRequest(LinkedRequest):
    clock_times: dict[str,str] = Field(max_length=4)
