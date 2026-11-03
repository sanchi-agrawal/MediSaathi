import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from schedule import (ScheduleError, build_schedule, packs_needed,
                      parse_duration, parse_pattern)

START = date(2026, 10, 21)
NAN, INF = float("nan"), float("inf")


def med(pattern="1-0-1", days=5, form="tablet", qty=None, unit=None, **kw):
    r = {"name": "Test", "frequency_pattern": pattern, "duration_days": days,
         "form": form, "confirmed": True, "needs_review": False}
    if qty is not None:
        r["dose_quantity"] = qty
    if unit is not None:
        r["dose_unit"] = unit
    r.update(kw)
    return r


def needs_input(r):
    assert r["status"] == "needs_input" and r["reason"]
    for k in ("total_units", "end_date", "units_per_day", "doses_by_slot"):
        assert k not in r          # no partial or guessed schedule


# ---------- confirmation gates ----------

def test_unconfirmed_record_is_rejected():
    needs_input(build_schedule(med(confirmed=False), START))


def test_missing_confirmed_key_is_rejected():
    r = med()
    del r["confirmed"]
    needs_input(build_schedule(r, START))


@pytest.mark.parametrize("bad", ["True", 1, "yes", None])
def test_confirmed_must_be_exactly_true(bad):
    needs_input(build_schedule(med(confirmed=bad), START))


def test_needs_review_blocks_even_if_confirmed():
    needs_input(build_schedule(med(needs_review=True), START))


@pytest.mark.parametrize("bad", [None, "False", 0, NAN])
def test_needs_review_must_be_exactly_false(bad):
    needs_input(build_schedule(med(needs_review=bad), START))


def test_unconfirmed_sos_is_also_rejected():
    needs_input(build_schedule(med("SOS", confirmed=False), START))


# ---------- happy paths ----------

def test_1_0_1_tablet_5_days_is_10():
    r = build_schedule(med("1-0-1", 5), START)
    assert r["status"] == "ok" and r["units_per_day"] == 2
    assert r["total_units"] == 10 and r["unit"] == "tablet"
    assert r["end_date"] == date(2026, 10, 25)


def test_one_day_course_ends_same_day():
    assert build_schedule(med("1-0-0", 1), START)["end_date"] == START


def test_half_tablets():
    r = build_schedule(med("0.5-0-0.5", 5), START)
    assert r["units_per_day"] == 1 and r["total_units"] == 5


def test_half_tablet_once_daily_fractional_total():
    assert build_schedule(med("0.5-0-0", 5), START)["total_units"] == 2.5


def test_four_part_pattern_capsule():
    r = build_schedule(med("1-1-1-1", 2, form="capsule"), START)
    assert r["units_per_day"] == 4 and r["unit"] == "capsule"


def test_pattern_spaces_and_case():
    assert parse_pattern("1 - 0 - 1")[0] == "numeric"
    assert parse_pattern("bd") == parse_pattern("BD")


@pytest.mark.parametrize("abbr,per_day", [("OD", 1), ("BD", 2), ("TDS", 3), ("QID", 4), ("HS", 1)])
def test_abbreviations_with_explicit_dose(abbr, per_day):
    r = build_schedule(med(abbr, 10, qty=1, unit="tablet"), START)
    assert r["units_per_day"] == per_day and r["total_units"] == per_day * 10


def test_hs_goes_to_bedtime_slot():
    r = build_schedule(med("HS", 3, qty=1, unit="tablet"), START)
    assert r["doses_by_slot"] == {"morning": 0, "noon": 0, "night": 0, "bedtime": 1}


def test_syrup_with_explicit_ml():
    r = build_schedule(med("BD", 5, form="syrup", qty=5, unit="ml"), START)
    assert r["unit"] == "ml" and r["units_per_day"] == 10 and r["total_units"] == 50


def test_unit_aliases_normalised():
    r = build_schedule(med("OD", 3, form="syrup", qty="5", unit="mL"), START)
    assert r["unit"] == "ml" and r["total_units"] == 15


def test_sos_has_no_schedule():
    r = build_schedule(med("SOS", None), START)
    assert r["status"] == "as_needed" and "total_units" not in r


def test_refill_date_for_long_term():
    r = build_schedule(med("1-0-0", 30), START)
    assert r["end_date"] == date(2026, 11, 19) and r["refill_date"] == date(2026, 11, 16)


def test_no_refill_for_short_course():
    assert build_schedule(med("1-0-1", 5), START)["refill_date"] is None


# ---------- nothing is inferred ----------

def test_abbreviation_without_dose_quantity_needs_input():
    needs_input(build_schedule(med("BD", 5), START))


def test_syrup_numeric_pattern_not_assumed_ml():
    needs_input(build_schedule(med("5-0-5", 5, form="syrup"), START))


def test_drops_and_syringe_forms_not_assumed():
    needs_input(build_schedule(med("1-0-1", 5, form="drops"), START))
    needs_input(build_schedule(med("1-0-1", 5, form="syringe"), START))


def test_missing_form_needs_input():
    needs_input(build_schedule(med("1-0-1", 5, form=None), START))


def test_missing_pattern_needs_input():
    needs_input(build_schedule(med(None), START))


def test_dose_quantity_without_unit_or_unit_without_quantity():
    needs_input(build_schedule(med("BD", qty=1), START))
    needs_input(build_schedule(med("BD", unit="tablet"), START))


def test_pattern_and_dose_quantity_conflict():
    needs_input(build_schedule(med("5-0-5", 5, form="syrup", qty=5, unit="ml"), START))


def test_form_and_unit_conflict():
    needs_input(build_schedule(med("BD", 5, form="tablet", qty=5, unit="ml"), START))


@pytest.mark.parametrize("unit", ["syringe", "units", "IU", "mg", "spoon"])
def test_unsupported_units_rejected(unit):
    needs_input(build_schedule(med("BD", 5, form="syrup", qty=1, unit=unit), START))


# ---------- invalid / non-finite quantities ----------

@pytest.mark.parametrize("qty", [0, -1, NAN, INF, -INF, True, "abc", "nan", "inf", "1e2", 5000])
def test_bad_dose_quantity_rejected(qty):
    needs_input(build_schedule(med("BD", 5, form="syrup", qty=qty, unit="ml"), START))


@pytest.mark.parametrize("pat", ["nan-0-1", "inf-0-1", "1-0-inf", "1e1-0-1", "-1-0-1",
                                 "0-0-0", "1-0", "1-0-1-0-1", "take it", "99-0-1", "True-0-1"])
def test_bad_patterns_rejected(pat):
    needs_input(build_schedule(med(pat), START))


def test_parse_pattern_raises_on_nonfinite():
    for bad in ("nan-0-1", "inf-0-0"):
        with pytest.raises(ScheduleError):
            parse_pattern(bad)


# ---------- durations ----------

@pytest.mark.parametrize("bad", ["5-7 days", "5 to 7 days", "5-7", "57-", "5,7", "5 days 7",
                                 "1.5 weeks", "0", 0, -3, NAN, INF, True, 400, "400",
                                 "", None, "for a while", 5.5, "10000000000"])
def test_bad_durations_rejected(bad):
    needs_input(build_schedule(med("1-0-1", bad), START))


def test_range_is_not_read_as_57():
    with pytest.raises(ScheduleError):
        parse_duration("5-7 days")


@pytest.mark.parametrize("good,days", [(5, 5), (5.0, 5), ("5", 5), ("5 days", 5),
                                       ("x 5 days", 5), ("2 weeks", 14), ("1 month", 30),
                                       (365, 365)])
def test_good_durations(good, days):
    assert parse_duration(good) == days


def test_nan_from_pandas_is_missing():
    needs_input(build_schedule(med("1-0-1", NAN), START))


# ---------- other ----------

def test_start_date_must_be_a_date():
    with pytest.raises(TypeError):
        build_schedule(med(), "2026-10-21")


def test_packs_needed_rounds_up():
    assert packs_needed(10, 10) == 1 and packs_needed(11, 10) == 2 and packs_needed(30, 15) == 2


@pytest.mark.parametrize("t,p", [(0, 10), (10, 0), (-1, 10), (NAN, 10), (10, INF), (True, 10), ("10", 10)])
def test_packs_needed_rejects_bad_numbers(t, p):
    with pytest.raises(ValueError):
        packs_needed(t, p)
