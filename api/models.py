from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: str = Field(min_length=1, max_length=128)


class ReviewRequest(RevisionRequest):
    # Deliberately retain raw JSON primitives. AIIntegration validates EXACT field
    # sets and types without Pydantic coercion, null filling or medical inference.
    records: list[dict] = Field(max_length=200)


class ExplanationRequest(RevisionRequest):
    language: Literal["en", "hi", "hinglish"]


class SectionReviewRequest(RevisionRequest):
    payload: dict


class StripObservationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    raw_label: str | None
    raw_date_text: str | None
    raw_text: str | None
    association: Literal["same_product", "unclear"]


class StripReviewRequest(RevisionRequest):
    medicine_name: str | None
    batch_number: str | None
    product_association: Literal["single_product", "multiple_products", "unclear"]
    date_observations: list[StripObservationEdit] = Field(max_length=200)


class SectionReviewRequest(RevisionRequest):
    payload: dict
