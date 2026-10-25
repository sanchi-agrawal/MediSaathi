import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from confirm_utils import (READER_FIELDS, confirm, df_to_records,
                           is_confirmation_current, records_to_df,
                           review_blockers, snapshot)

FULL = {"raw_text": "Tab Dolo 650 1-0-1 x 5 days", "name": "Dolo 650",
        "salt": "Paracetamol", "strength": "650 mg", "form": "tablet",
        "frequency_pattern": "1-0-1", "duration_days": 5, "timing": "after food",
        "confidence": 0.95, "needs_review": False,
        "dose_quantity": 1, "dose_unit": "tablet"}


def test_all_ten_reader_fields_are_kept():
    df = records_to_df([FULL])
    assert list(df.columns[:10]) == READER_FIELDS
    rec = df_to_records(df)[0]
    for f in READER_FIELDS:
        assert f in rec
    assert rec["raw_text"] == FULL["raw_text"] and rec["confidence"] == 0.95


def test_extra_extractor_fields_are_kept():
    rec = df_to_records(records_to_df([FULL]))[0]
    assert rec["dose_quantity"] == 1 and rec["dose_unit"] == "tablet"


def test_round_trip_changes_nothing_for_clean_row():
    rec = df_to_records(records_to_df([FULL]))[0]
    assert rec == FULL


def test_missing_fields_become_none_not_nan():
    rec = df_to_records(records_to_df([{"name": "X", "needs_review": False}]))[0]
    assert rec["duration_days"] is None and rec["salt"] is None
    assert not any(isinstance(v, float) and math.isnan(v) for v in rec.values())


def test_range_duration_is_blanked_and_flagged():
    rec = df_to_records(records_to_df([{**FULL, "duration_days": "5-7 days"}]))[0]
    assert rec["duration_days"] is None and rec["needs_review"] is True


def test_missing_or_non_bool_review_flag_means_review():
    r1 = {k: v for k, v in FULL.items() if k != "needs_review"}
    assert df_to_records(records_to_df([r1]))[0]["needs_review"] is True
    assert df_to_records(records_to_df([{**FULL, "needs_review": "no"}]))[0]["needs_review"] is True


def test_values_are_plain_python_types():
    rec = df_to_records(records_to_df([FULL]))[0]
    assert type(rec["duration_days"]) is int
    assert type(rec["needs_review"]) is bool


def test_confirm_blocked_while_rows_need_review():
    recs = [FULL, {**FULL, "name": "Syrup", "needs_review": True}]
    assert review_blockers(recs) == ["Syrup"]
    with pytest.raises(ValueError):
        confirm(recs)


def test_confirm_marks_rows_confirmed():
    out = confirm([FULL])
    assert out[0]["confirmed"] is True and "confirmed" not in FULL


def test_edit_after_confirm_invalidates():
    snap = snapshot([FULL])
    assert is_confirmation_current(snap, [FULL])
    assert not is_confirmation_current(snap, [{**FULL, "duration_days": 6}])
    assert not is_confirmation_current(snap, [FULL, FULL])


def test_no_snapshot_means_not_confirmed():
    assert not is_confirmation_current(None, [FULL])


def test_dose_columns_always_present_even_if_reader_has_none():
    rec = {k: v for k, v in FULL.items() if k not in ("dose_quantity", "dose_unit")}
    df = records_to_df([rec])
    assert "dose_quantity" in df.columns and "dose_unit" in df.columns
    out = df_to_records(df)[0]
    assert out["dose_quantity"] is None and out["dose_unit"] is None


def test_unusable_dose_values_are_blanked_and_flagged():
    for bad in ({"dose_quantity": "abc"}, {"dose_quantity": -2}, {"dose_unit": "syringe"}):
        rec = df_to_records(records_to_df([{**FULL, **bad}]))[0]
        assert rec["needs_review"] is True


def test_dose_unit_is_normalised():
    rec = df_to_records(records_to_df([{**FULL, "dose_unit": "mL"}]))[0]
    assert rec["dose_unit"] == "ml"


def test_user_can_add_dose_and_it_schedules():
    from datetime import date
    from schedule import build_schedule
    row = {**FULL, "name": "Syrup", "form": "syrup", "frequency_pattern": "BD",
           "duration_days": 2, "dose_quantity": None, "dose_unit": None}
    edited = df_to_records(records_to_df([row]))[0]
    assert build_schedule(confirm([edited])[0], date(2026, 10, 25))["status"] == "needs_input"
    edited.update(dose_quantity=5.0, dose_unit="ml")
    r = build_schedule(confirm([edited])[0], date(2026, 10, 25))
    assert r["status"] == "ok" and r["units_per_day"] == 10 and r["total_units"] == 20
    assert r["end_date"] == date(2026, 10, 26)


def test_nan_dose_quantity_is_treated_as_missing():
    rec = df_to_records(records_to_df([{**FULL, "dose_quantity": float("nan")}]))[0]
    assert rec["dose_quantity"] is None
