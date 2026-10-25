"""Schedule engine (Person 3), strict version.

Rules (the engine never guesses):
  1. Only records the user has confirmed (confirmed is exactly True) are scheduled,
     and only if needs_review is exactly False.
  2. Every quantity must be explicit: either written in the pattern for tablets and
     capsules (1-0-1), or given as dose_quantity + dose_unit by the extractor.
     Abbreviations (OD, BD, ...) say how often, not how much, so they need dose_quantity.
     Liquids, drops and anything else are never assumed to be ml or one unit.
  3. Durations must be one clear whole number of days (or weeks / months written
     explicitly). Ranges like "5-7 days" are rejected.
  4. Non-finite, negative, zero, boolean or oversized values are rejected.
Anything missing or unclear returns status 'needs_input' with a reason and NO schedule.
"""
import math
import re
from datetime import date, timedelta
from fractions import Fraction

SLOTS = ["morning", "noon", "night", "bedtime"]

# How OFTEN each abbreviation means. Cross-check with a trusted reference before shipping.
ABBREVIATIONS = {
    "OD": ("morning",),
    "BD": ("morning", "night"),
    "BID": ("morning", "night"),
    "TDS": ("morning", "noon", "night"),
    "TID": ("morning", "noon", "night"),
    "QID": ("morning", "noon", "night", "bedtime"),
    "HS": ("bedtime",),
}
AS_NEEDED = {"SOS", "PRN"}

# Units the engine accepts. Agree this list with the extractor (Person 1).
UNIT_ALIASES = {
    "tablet": "tablet", "tablets": "tablet", "tab": "tablet", "tabs": "tablet",
    "capsule": "capsule", "capsules": "capsule", "cap": "capsule", "caps": "capsule",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml", "millilitres": "ml",
    "milliliters": "ml",
    "drop": "drop", "drops": "drop",
    "puff": "puff", "puffs": "puff",
    "sachet": "sachet", "sachets": "sachet",
}
SOLID_FORMS = {"tablet": "tablet", "tablets": "tablet", "tab": "tablet",
               "capsule": "capsule", "capsules": "capsule", "cap": "capsule"}

LONG_TERM_DAYS = 30
REFILL_BUFFER_DAYS = 3
MAX_DURATION_DAYS = 365
MAX_SLOT_QUANTITY = 20
MAX_DOSE_QUANTITY = 1000

_NUMBER = re.compile(r"^\d+(\.\d+)?$")
_DURATION = re.compile(
    r"^(?:x\s*)?(\d+)\s*(days?|d|weeks?|wks?|w|months?|m)?$", re.IGNORECASE)


class ScheduleError(ValueError):
    """Raised for anything unclear. build_schedule turns it into needs_input."""


# ---------- small helpers ----------

def _clean(value):
    """NaN / empty string / None -> None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _out(fr):
    """Fraction -> int when whole, else float."""
    return int(fr) if fr.denominator == 1 else float(fr)


def _to_fraction(value, what, maximum):
    """Strictly turn a number or plain numeric string into a positive-or-zero Fraction."""
    if isinstance(value, bool):
        raise ScheduleError(f"{what} is not a valid number")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ScheduleError(f"{what} is not a valid number")
        text = repr(value)
    else:
        text = str(value).strip().replace("½", "0.5")
    if not _NUMBER.match(text):
        raise ScheduleError(f"{what} '{value}' is not a valid number")
    fr = Fraction(text)
    if fr > maximum:
        raise ScheduleError(f"{what} '{value}' is too large, please check it")
    return fr


# ---------- parsing ----------

def parse_pattern(pattern):
    """Return ('abbr', slots_tuple), ('numeric', {slot: Fraction}) or ('as_needed', None)."""
    pattern = _clean(pattern)
    if pattern is None:
        raise ScheduleError("No frequency written")
    text = str(pattern).upper().replace(" ", "")
    if text in AS_NEEDED:
        return "as_needed", None
    if text in ABBREVIATIONS:
        return "abbr", ABBREVIATIONS[text]
    parts = text.replace("–", "-").split("-")
    if len(parts) not in (3, 4):
        raise ScheduleError(f"Cannot read frequency '{pattern}'")
    nums = [_to_fraction(p, "Frequency", MAX_SLOT_QUANTITY) for p in parts]
    if not any(n > 0 for n in nums):
        raise ScheduleError(f"Frequency '{pattern}' has no doses")
    nums += [Fraction(0)] * (4 - len(nums))
    return "numeric", dict(zip(SLOTS, nums))


def parse_duration(value):
    """One clear whole number of days. Returns int days, or raises ScheduleError.

    Accepts 5, 5.0, '5', '5 days', '2 weeks', '1 month' (= 30 days).
    Rejects ranges ('5-7 days'), decimals, zero, negatives, NaN/inf, booleans.
    """
    value = _clean(value)
    if value is None:
        raise ScheduleError("Duration not written. Please enter the number of days.")
    if isinstance(value, bool):
        raise ScheduleError("Duration is not a valid number of days")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
            raise ScheduleError("Duration must be a whole number of days")
        days = int(value)
    else:
        m = _DURATION.match(str(value).strip())
        if not m:
            raise ScheduleError(
                f"Duration '{value}' is unclear. Enter one number of days.")
        n, unit = int(m.group(1)), (m.group(2) or "d").lower()
        if unit.startswith("w"):
            days = n * 7
        elif unit.startswith("m"):
            days = n * 30
        else:
            days = n
    if days <= 0:
        raise ScheduleError("Duration must be at least 1 day")
    if days > MAX_DURATION_DAYS:
        raise ScheduleError(f"Duration of {days} days is too long, please check it")
    return days


def _normalise_unit(unit):
    key = str(unit).strip().lower()
    if key not in UNIT_ALIASES:
        raise ScheduleError(
            f"Unit '{unit}' is not supported. Check with your doctor or pharmacist.")
    return UNIT_ALIASES[key]


# ---------- main entry point ----------

def build_schedule(medicine, start_date):
    """medicine: confirmed record (dict). Returns a result dict with a status:
    'ok', 'as_needed' or 'needs_input' (with a reason to show the user)."""
    if not isinstance(start_date, date):
        raise TypeError("start_date must be a datetime.date")
    name = _clean(medicine.get("name")) or "unknown"
    base = {"name": name, "status": "ok", "reason": None}

    def needs(reason):
        return {**base, "status": "needs_input", "reason": reason}

    # 1. Confirmation gates
    if medicine.get("confirmed") is not True:
        return needs("Not confirmed by the user yet.")
    if medicine.get("needs_review") is not False:
        return needs("Still marked 'needs review'. Check this medicine and clear the flag.")

    try:
        kind, slots = parse_pattern(medicine.get("frequency_pattern"))
        if kind == "as_needed":
            return {**base, "status": "as_needed",
                    "reason": "As needed: no fixed schedule. Follow your doctor's advice."}

        # 2. Explicit quantity and unit
        form = _clean(medicine.get("form"))
        solid = SOLID_FORMS.get(str(form).strip().lower()) if form else None
        qty_raw = _clean(medicine.get("dose_quantity"))
        unit_raw = _clean(medicine.get("dose_unit"))

        if qty_raw is not None or unit_raw is not None:
            if qty_raw is None or unit_raw is None:
                raise ScheduleError("Dose needs both a quantity and a unit.")
            qty = _to_fraction(qty_raw, "Dose quantity", MAX_DOSE_QUANTITY)
            if qty <= 0:
                raise ScheduleError("Dose quantity must be above zero")
            unit = _normalise_unit(unit_raw)
            if solid and unit != solid:
                raise ScheduleError(
                    f"Form is {solid} but dose unit is {unit}. Please check.")
            if kind == "abbr":
                doses = {s: (qty if s in slots else Fraction(0)) for s in SLOTS}
            else:  # numeric pattern: only 0/1 flags allowed alongside an explicit dose
                if any(v not in (0, 1) for v in slots.values()):
                    raise ScheduleError(
                        "Frequency and dose quantity conflict. Please check both.")
                doses = {s: qty * v for s, v in slots.items()}
        else:
            if kind == "abbr":
                raise ScheduleError(
                    "Dose quantity not written. Please enter how much per dose.")
            if not solid:
                raise ScheduleError(
                    "Quantity per dose and unit not written. Please enter them.")
            unit = solid
            doses = dict(slots)

        # 3. Duration
        duration = parse_duration(medicine.get("duration_days"))
    except ScheduleError as e:
        return needs(str(e))

    per_day = sum(doses.values(), Fraction(0))
    total = per_day * duration
    end_date = start_date + timedelta(days=duration - 1)
    refill_date = (end_date - timedelta(days=REFILL_BUFFER_DAYS)
                   if duration >= LONG_TERM_DAYS else None)

    return {**base,
            "doses_by_slot": {s: _out(v) for s, v in doses.items()},
            "units_per_day": _out(per_day), "duration_days": duration,
            "total_units": _out(total), "unit": unit,
            "start_date": start_date, "end_date": end_date,
            "refill_date": refill_date}


def packs_needed(total_units, pack_size):
    """Whole packs only. Rejects invalid numbers instead of guessing."""
    for label, v in (("total_units", total_units), ("pack_size", pack_size)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{label} must be a positive finite number")
    return math.ceil(total_units / pack_size)
