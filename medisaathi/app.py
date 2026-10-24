import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from schedule import build_schedule

MOCK_PATH = Path("sample_prescriptions/mock_prescription.json")
COLUMNS = ["name", "salt", "strength", "form", "frequency_pattern",
           "duration_days", "timing", "needs_review"]

st.set_page_config(page_title="MediSaathi", page_icon="💊", layout="wide")
st.markdown("<style>html, body, [class*='css'] {font-size: 18px;}</style>",
            unsafe_allow_html=True)

st.title("💊 MediSaathi")
st.warning("Reminder and information tool, not medical advice. "
           "Prices shown are SAMPLE DATA collected by hand.")


def read_prescription(image_bytes):
    """Placeholder. Replace with reader.read_prescription once Person 1 delivers."""
    return json.loads(MOCK_PATH.read_text())


if "medicines" not in st.session_state:
    st.session_state.medicines = None
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False

page = st.sidebar.radio("Go to", ["Upload", "Confirm", "Results"])

if page == "Upload":
    st.header("1. Upload your prescription")
    file = st.file_uploader("Photo of prescription", type=["jpg", "jpeg", "png"])
    if file:
        st.image(file, width=400)
        if st.button("Read prescription"):
            st.session_state.medicines = read_prescription(file.getvalue())
            st.session_state.confirmed = False
            st.success("Done. Go to the Confirm page.")
    if st.button("Use sample prescription (demo)"):
        st.session_state.medicines = read_prescription(None)
        st.session_state.confirmed = False
        st.success("Sample loaded. Go to the Confirm page.")

elif page == "Confirm":
    st.header("2. Check what was read")
    meds = st.session_state.medicines
    if not meds:
        st.info("Upload a prescription first.")
    else:
        st.caption("Fix anything wrong. Blank or unclear fields: please check with your doctor.")
        df = pd.DataFrame(meds).reindex(columns=COLUMNS)
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if edited["needs_review"].any():
            st.error("Some rows need review. Please fill the blank fields.")
        if st.button("Confirm all"):
            st.session_state.medicines = edited.to_dict("records")
            st.session_state.confirmed = True
            st.success("Confirmed. Open the Results page.")

else:
    st.header("3. Results")
    if not st.session_state.confirmed:
        st.info("Confirm your medicines first.")
    else:
        t1, t2, t3 = st.tabs(["Schedule", "Prices", "Refill"])
        start = t1.date_input("Course starts on", value=date.today())
        results = [build_schedule(m, start) for m in st.session_state.medicines]

        with t1:
            rows = []
            for r in results:
                if r["status"] == "ok":
                    d = r["doses_by_slot"]
                    rows.append({
                        "Medicine": r["name"],
                        "Morning": d["morning"], "Noon": d["noon"],
                        "Night": d["night"], "Bedtime": d["bedtime"],
                        "Per day": r["units_per_day"],
                        "Days": r["duration_days"],
                        "Total": f'{r["total_units"]} {r["unit"]}',
                        "Ends on": r["end_date"].strftime("%d %b %Y"),
                    })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
