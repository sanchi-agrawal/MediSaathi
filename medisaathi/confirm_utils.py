"""Helpers for the Confirm screen (Person 3). No Streamlit imports, so they can be tested.

Keeps all ten reader fields, keeps any extra fields (such as dose_quantity and
dose_unit from the instruction extractor), and tells the app when a confirmation
no longer matches what is on screen.
"""
import json
import math

import pandas as pd

from schedule import (UNIT_ALIASES, ScheduleError, _normalise_unit, _to_fraction,
                      parse_duration, MAX_DOSE_QUANTITY)

READER_FIELDS = ["raw_text", "name", "salt", "strength", "form", "frequency_pattern",
                 "duration_days", "timing", "confidence", "needs_review"]
DOSE_FIELDS = ["dose_quantity", "dose_unit"]    # always shown so the user can fill them
UNIT_OPTIONS = sorted(set(UNIT_ALIASES.values()))
READ_ONLY_FIELDS = ["raw_text", "confidence"]   # evidence from the reader, not editable


def _is_missing(v):
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _native(v):
    """NaN / pandas NA / empty string -> None; numpy scalars -> plain Python."""
    if _is_missing(v):
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def extra_fields(records):
    """Fields beyond the ten reader fields, in order of first appearance."""
    extras = []
    for r in records:
        for k in r:
            if k not in READER_FIELDS and k not in DOSE_FIELDS and k != "confirmed" and k not in extras:
                extras.append(k)
    return extras


def records_to_df(records):
    """Build the editable table. Rows whose duration or review flag cannot be trusted
    are marked needs_review = True so the user must look at them."""
    extras = extra_fields(records)
    columns = READER_FIELDS + DOSE_FIELDS + extras
    rows = []
    for r in records:
        row = {k: _native(r.get(k)) for k in columns}
        # duration: keep only a clear whole number of days
        dur = r.get("duration_days")
        if _native(dur) is not None:
            try:
                row["duration_days"] = parse_duration(dur)
            except ScheduleError:
                row["duration_days"] = None
                row["needs_review"] = True
        # dose quantity / unit: keep only clear, supported values
        qty = _native(r.get("dose_quantity"))
        if qty is not None:
            try:
                row["dose_quantity"] = float(_to_fraction(qty, "Dose quantity", MAX_DOSE_QUANTITY))
            except ScheduleError:
                row["dose_quantity"] = None
                row["needs_review"] = True
        unit = _native(r.get("dose_unit"))
        if unit is not None:
            try:
                row["dose_unit"] = _normalise_unit(unit)
            except ScheduleError:
                row["dose_unit"] = None
                row["needs_review"] = True
        # review flag: anything but an explicit False means 'check this row'
        row["needs_review"] = False if r.get("needs_review") is False and row["needs_review"] is not True else True
        rows.append(row)
    df = pd.DataFrame(rows, columns=columns)
    df["duration_days"] = pd.array(df["duration_days"], dtype="Int64")
    df["dose_quantity"] = pd.to_numeric(df["dose_quantity"], errors="coerce").astype(float)
    df["dose_unit"] = df["dose_unit"].astype(object)
    df["needs_review"] = df["needs_review"].astype(bool)
    return df


def df_to_records(df):
    """Edited table -> list of plain-Python dicts (no NaN, no numpy types)."""
    records = []
    for row in df.to_dict("records"):
        rec = {k: _native(v) for k, v in row.items()}
        rec["needs_review"] = rec.get("needs_review") is True
        records.append(rec)
    return records


def snapshot(records):
    """Stable text form of a record list, used to detect edits after confirming."""
    return json.dumps(records, sort_keys=True, default=str)


def review_blockers(records):
    """Names of rows still marked needs_review."""
    return [r.get("name") or "unnamed row" for r in records if r.get("needs_review") is not False]


def confirm(records):
    """Return confirmed copies of the records, or raise if any row still needs review."""
    blockers = review_blockers(records)
    if blockers:
        raise ValueError("Rows still need review: " + ", ".join(blockers))
    return [{**r, "confirmed": True} for r in records]


def is_confirmation_current(confirmed_snapshot, records):
    """True only if the table on screen is exactly what the user confirmed."""
    return confirmed_snapshot is not None and confirmed_snapshot == snapshot(records)
