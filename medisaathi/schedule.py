"""Schedule engine (Person 3).

Pure logic, no AI. Reads a medicine record (see section 7 of the plan) and works out
doses per slot, units per day, total units, end date and refill date.
"""
import math
from datetime import date, timedelta

SLOTS = ["morning", "noon", "night", "bedtime"]

# Standard abbreviations -> doses per slot. Cross-check with a trusted reference.
ABBREVIATIONS = {
    "OD": {"morning": 1, "noon": 0, "night": 0, "bedtime": 0},
    "BD": {"morning": 1, "noon": 0, "night": 1, "bedtime": 0},
    "BID": {"morning": 1, "noon": 0, "night": 1, "bedtime": 0},
    "TDS": {"morning": 1, "noon": 1, "night": 1, "bedtime": 0},
    "TID": {"morning": 1, "noon": 1, "night": 1, "bedtime": 0},
    "QID": {"morning": 1, "noon": 1, "night": 1, "bedtime": 1},
    "HS": {"morning": 0, "noon": 0, "night": 0, "bedtime": 1},
}
AS_NEEDED = {"SOS", "PRN"}
LONG_TERM_DAYS = 30   # courses this long or longer get a refill date
REFILL_BUFFER_DAYS = 3


class ScheduleError(ValueError):
    """Raised when a pattern cannot be understood. The app should ask the user."""


def _clean(value):
    """Turn NaN / empty strings (from pandas) into None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _num(x):
    """Return int when the number is whole, else float."""
    return int(x) if float(x).is_integer() else float(x)


def parse_pattern(pattern):
    """Return doses_by_slot dict, or None for 'as needed' (no schedule)."""
    pattern = _clean(pattern)
    if pattern is None:
        raise ScheduleError("No frequency written")
    text = str(pattern).upper().replace(" ", "").replace("½", "0.5")
    if text in AS_NEEDED:
        return None
    if text in ABBREVIATIONS:
        return dict(ABBREVIATIONS[text])
    parts = text.replace("–", "-").split("-")
    if len(parts) in (3, 4):
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise ScheduleError(f"Cannot read pattern '{pattern}'")
        if any(n < 0 for n in nums):
            raise ScheduleError(f"Cannot read pattern '{pattern}'")
        nums += [0.0] * (4 - len(nums))
        return {slot: _num(n) for slot, n in zip(SLOTS, nums)}
    raise ScheduleError(f"Cannot read pattern '{pattern}'")


def parse_duration(text):
    """'5 days' -> 5, '2 weeks' -> 14, '1 month' -> 30. Plain numbers are days."""
    text = _clean(text)
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text).lower().strip()
    digits = "".join(ch for ch in s if ch.isdigit() or ch == ".")
    if not digits:
        return None
    n = float(digits)
    if "month" in s:
        return int(n * 30)
    if "week" in s:
        return int(n * 7)
    return int(n)


def build_schedule(medicine, start_date):
    """medicine: dict following the medicine record. Returns a schedule result dict.

    status is 'ok', 'as_needed' or 'needs_input' (with a reason to show the user).
    """
    name = _clean(medicine.get("name")) or "unknown"
    result = {"name": name, "status": "ok", "reason": None}
    try:
        slots = parse_pattern(medicine.get("frequency_pattern"))
    except ScheduleError as e:
        return {**result, "status": "needs_input", "reason": str(e)}

    if slots is None:
        return {**result, "status": "as_needed",
                "reason": "As needed: no fixed schedule. Follow your doctor's advice."}

    duration = parse_duration(medicine.get("duration_days"))
    if duration is None or duration <= 0:
        return {**result, "status": "needs_input",
                "reason": "Duration not written. Please enter the number of days."}

    form = _clean(medicine.get("form"))
    unit = "ml" if form and str(form).lower() == "syrup" else "units"
    units_per_day = _num(sum(slots.values()))
    total_units = _num(units_per_day * duration)
    end_date = start_date + timedelta(days=duration - 1)
    refill_date = (end_date - timedelta(days=REFILL_BUFFER_DAYS)
                   if duration >= LONG_TERM_DAYS else None)

    return {**result, "doses_by_slot": slots, "units_per_day": units_per_day,
            "duration_days": duration, "total_units": total_units, "unit": unit,
            "start_date": start_date, "end_date": end_date,
            "refill_date": refill_date}


def packs_needed(total_units, pack_size):
    """Whole packs only. Kept here for convenience; Person 2's calculator owns pricing."""
    return math.ceil(total_units / pack_size)
