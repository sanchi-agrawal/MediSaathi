import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schedule import (ScheduleError, build_schedule, packs_needed,
                      parse_duration, parse_pattern)

START = date(2026, 10, 21)


def med(pattern, days, form="tablet"):
    return {"name": "Test", "frequency_pattern": pattern,
            "duration_days": days, "form": form}


def test_1_0_1_for_5_days_is_10_tablets():
    r = build_schedule(med("1-0-1", 5), START)
    assert r["units_per_day"] == 2
    assert r["total_units"] == 10


def test_end_date_is_start_plus_days_minus_one():
    r = build_schedule(med("1-0-1", 5), START)
    assert r["end_date"] == date(2026, 10, 25)


def test_one_day_course_ends_same_day():
    r = build_schedule(med("OD", 1), START)
    assert r["end_date"] == START


def test_0_0_1_bedtime_style():
    r = build_schedule(med("0-0-1", 7), START)
    assert r["doses_by_slot"]["night"] == 1
    assert r["total_units"] == 7


def test_half_tablets():
    r = build_schedule(med("0.5-0-0.5", 5), START)
    assert r["units_per_day"] == 1
    assert r["total_units"] == 5


def test_half_tablet_once_daily_gives_fractional_total():
    r = build_schedule(med("0.5-0-0", 5), START)
    assert r["total_units"] == 2.5


@pytest.mark.parametrize("abbr,per_day", [
    ("OD", 1), ("BD", 2), ("TDS", 3), ("QID", 4), ("HS", 1)])
def test_abbreviations(abbr, per_day):
    r = build_schedule(med(abbr, 10), START)
    assert r["units_per_day"] == per_day
    assert r["total_units"] == per_day * 10


def test_hs_is_bedtime_slot():
    assert parse_pattern("HS")["bedtime"] == 1


def test_lowercase_and_spaces_are_fine():
    assert parse_pattern(" b d ".replace(" ", "")) == parse_pattern("BD")
    assert parse_pattern("1 - 0 - 1")["night"] == 1


def test_four_part_pattern():
    r = build_schedule(med("1-1-1-1", 2), START)
    assert r["units_per_day"] == 4


def test_sos_has_no_schedule():
    r = build_schedule(med("SOS", 5), START)
    assert r["status"] == "as_needed"
    assert "total_units" not in r


def test_missing_duration_asks_user():
    r = build_schedule(med("BD", None), START)
    assert r["status"] == "needs_input"


def test_missing_pattern_asks_user():
    r = build_schedule(med(None, 5), START)
    assert r["status"] == "needs_input"


def test_garbage_pattern_raises_in_parser_and_asks_in_builder():
    with pytest.raises(ScheduleError):
        parse_pattern("take it sometimes")
    assert build_schedule(med("abc", 5), START)["status"] == "needs_input"


def test_nan_from_pandas_counts_as_missing():
    r = build_schedule(med("BD", float("nan")), START)
    assert r["status"] == "needs_input"


def test_duration_text():
    assert parse_duration("5 days") == 5
    assert parse_duration("2 weeks") == 14
    assert parse_duration("1 month") == 30
    assert parse_duration(None) is None


def test_refill_date_for_long_term():
    r = build_schedule(med("1-0-0", 30), START)
    assert r["end_date"] == date(2026, 11, 19)
    assert r["refill_date"] == date(2026, 11, 16)


def test_no_refill_date_for_short_course():
    assert build_schedule(med("BD", 5), START)["refill_date"] is None


def test_syrup_units_are_ml():
    r = build_schedule(med("5-0-5", 5, form="syrup"), START)
    assert r["unit"] == "ml"
    assert r["total_units"] == 50


def test_packs_needed_rounds_up():
    assert packs_needed(10, 10) == 1
    assert packs_needed(11, 10) == 2
    assert packs_needed(30, 15) == 2
