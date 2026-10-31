import json
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from confirm_utils import (READ_ONLY_FIELDS, UNIT_OPTIONS, confirm, df_to_records,
                           is_confirmation_current, records_to_df,
                           review_blockers, snapshot)
import reminders
from schedule import build_schedule

load_dotenv()

MOCK_PATH = Path("sample_prescriptions/mock_prescription.json")

st.set_page_config(page_title="MediSaathi", page_icon="💊", layout="wide")
st.markdown("<style>html, body, [class*='css'] {font-size: 18px;}</style>",
            unsafe_allow_html=True)
st.title("💊 MediSaathi")
st.warning("Reminder and information tool, not medical advice. "
           "Prices shown are SAMPLE DATA collected by hand.")


def read_prescription(image_bytes):
    """Placeholder. Replace with reader.read_prescription once integrated."""
    return json.loads(MOCK_PATH.read_text())


# ---------- session state ----------
for key, default in {"medicines": None, "file_key": None, "upload_id": 0,
                     "confirmed_records": None, "confirmed_snapshot": None}.items():
    st.session_state.setdefault(key, default)


def reset_confirmation():
    st.session_state.confirmed_records = None
    st.session_state.confirmed_snapshot = None


def load_medicines(records):
    """Any new set of medicines: drop old confirmation and old editor edits."""
    st.session_state.medicines = records
    st.session_state.upload_id += 1      # new editor key -> old edits discarded
    reset_confirmation()


tab_upload, tab_confirm, tab_results, tab_rem = st.tabs(
    ["1. Upload", "2. Confirm", "3. Results", "4. Reminders"])

# ---------- 1. Upload ----------
with tab_upload:
    file = st.file_uploader("Photo of prescription", type=["jpg", "jpeg", "png"])
    if file:
        file_key = f"{file.name}:{file.size}"
        if file_key != st.session_state.file_key:     # a different file was chosen
            st.session_state.file_key = file_key
            load_medicines(None)                       # clears medicines and confirmation
        st.image(file, width=400)
        if st.button("Read prescription"):
            load_medicines(read_prescription(file.getvalue()))
            st.success("Done. Open the Confirm tab.")
    if st.button("Use sample prescription (demo)"):
        st.session_state.file_key = None
        load_medicines(read_prescription(None))
        st.success("Sample loaded. Open the Confirm tab.")

# ---------- 2. Confirm ----------
with tab_confirm:
    if not st.session_state.medicines:
        st.info("Upload a prescription first.")
    else:
        st.caption("Check every row against the prescription. Fix anything wrong. "
                   "Blank or unclear fields: please check with your doctor. "
                   "Untick 'needs_review' on a row only after you have checked it.")
        df = records_to_df(st.session_state.medicines)
        edited = st.data_editor(
            df, num_rows="dynamic", width="stretch", disabled=READ_ONLY_FIELDS,
            key=f"editor_{st.session_state.upload_id}",
            column_config={
                "duration_days": st.column_config.NumberColumn(min_value=1, step=1),
                "dose_quantity": st.column_config.NumberColumn(
                    "dose_quantity", min_value=0.0, help="How much per dose, as written on the prescription"),
                "dose_unit": st.column_config.SelectboxColumn(
                    "dose_unit", options=UNIT_OPTIONS, help="Unit for that quantity"),
                "needs_review": st.column_config.CheckboxColumn(
                    help="Tick means 'not checked yet'. Untick after checking."),
            })
        current = df_to_records(edited)

        # Any change after confirming cancels the confirmation.
        if (st.session_state.confirmed_snapshot is not None
                and not is_confirmation_current(st.session_state.confirmed_snapshot, current)):
            reset_confirmation()
            st.warning("You changed something after confirming. Please confirm again.")

        blockers = review_blockers(current)
        if blockers:
            st.error("Still needs your review: " + ", ".join(blockers))

        if st.button("Confirm all", disabled=bool(blockers)):
            st.session_state.confirmed_records = confirm(current)
            st.session_state.confirmed_snapshot = snapshot(current)

        if st.session_state.confirmed_snapshot is not None:
            st.success("Confirmed. Open the Results tab.")

# ---------- 3. Results ----------
with tab_results:
    confirmed = st.session_state.confirmed_records
    if not confirmed:
        st.info("Confirm your medicines first.")
    else:
        t1, t2, t3 = st.tabs(["Schedule", "Prices", "Refill"])
        start = t1.date_input("Course starts on", value=date.today(), key="start_date")
        results = [build_schedule(m, start) for m in confirmed]

        with t1:
            rows = []
            for r in results:
                if r["status"] == "ok":
                    d = r["doses_by_slot"]
                    rows.append({
                        "Medicine": r["name"],
                        "Morning": d["morning"], "Noon": d["noon"],
                        "Night": d["night"], "Bedtime": d["bedtime"],
                        "Per day": f'{r["units_per_day"]} {r["unit"]}',
                        "Days": r["duration_days"],
                        "Total": f'{r["total_units"]} {r["unit"]}',
                        "Ends on": r["end_date"].strftime("%d %b %Y"),
                    })
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            for r in results:
                if r["status"] != "ok":
                    st.warning(f'{r["name"]}: {r["reason"]}')

        t2.write("Cheapest basket coming soon (Person 2).")

        with t3:
            refills = [r for r in results if r["status"] == "ok" and r["refill_date"]]
            if refills:
                for r in refills:
                    st.write(f'{r["name"]}: order again by '
                             f'{r["refill_date"].strftime("%d %b %Y")}')
            else:
                st.info("No long-term medicines (30 days or more) in this prescription.")


# ---------- 4. Reminders ----------
with tab_rem:
    confirmed = st.session_state.confirmed_records
    if not confirmed:
        st.info("Confirm your medicines first.")
    else:
        start = st.session_state.get("start_date", date.today())
        results = [build_schedule(m, start) for m in confirmed]

        with st.expander("Reminder times (your own settings, not medical advice)"):
            cols = st.columns(4)
            slot_times = {slot: cols[i].time_input(slot.capitalize(),
                                                   value=reminders.DEFAULT_SLOT_TIMES[slot],
                                                   key=f"time_{slot}")
                          for i, slot in enumerate(reminders.SLOTS)}

        # Rebuild the dose log when the confirmed prescription, start date or times change.
        key = (st.session_state.confirmed_snapshot, str(start), str(slot_times))
        conn = reminders.connect()
        if st.session_state.get("reminder_key") != key:
            reminders.load_schedule(conn, results, slot_times)
            st.session_state.reminder_key = key

        now = datetime.now()
        for alert in reminders.refill_alerts(results, now.date()):
            (st.warning if alert["level"] == "warning" else st.info)(alert["message"])

        st.subheader("Today")
        doses = reminders.todays_doses(conn, now.date())
        if not doses:
            st.info("No doses scheduled today. Check the course start date in Results.")
        for d in doses:
            due = datetime.fromisoformat(d["due_at"])
            amount = int(d["amount"]) if float(d["amount"]).is_integer() else d["amount"]
            label = f'{due.strftime("%I:%M %p")}  |  {d["medicine"]}  |  {amount} {d["unit"]}'
            c1, c2 = st.columns([4, 1])
            if d["status"] == "taken":
                c1.success(f"Taken: {label}")
            else:
                late = now > due + pd.Timedelta(minutes=reminders.GRACE_MINUTES)
                (c1.error if late else c1.write)(label + ("  (overdue)" if late else ""))
                if c2.button("Taken", key=f"taken_{d['id']}"):
                    reminders.mark_taken(conn, d["id"], now)
                    st.rerun()

        st.subheader("Caregiver alerts (Telegram)")
        sender = reminders.sender_from_env()
        if sender is None:
            st.caption("Telegram is not set up. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                       "to your .env file and restart the app.")
        b1, b2 = st.columns(2)
        if b1.button("Check for missed doses"):
            if sender is None:
                st.warning("Telegram is not set up, so nothing was sent.")
            else:
                sent = reminders.send_missed_alerts(conn, now, sender)
                st.success(f"Sent {len(sent)} alert(s).") if sent else st.info(
                    "No missed doses to report.")
        if b2.button("Simulate missed dose (demo)"):
            msg, ok = reminders.simulate_missed_dose(conn, sender)
            if msg is None:
                st.info("No pending doses to simulate.")
            elif ok:
                st.success("Demo alert sent to Telegram.")
                st.code(msg)
            else:
                st.warning("Message not sent (Telegram not set up or failed). Preview:")
                st.code(msg)
        st.caption("Alerts only say a dose was not marked as taken. "
                   "Reminder and information tool, not medical advice.")
        conn.close()
