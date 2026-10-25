import pandas as pd
import streamlit as st

import ai_flow as flow
from confirm_utils import READ_ONLY_FIELDS, UNIT_OPTIONS

st.set_page_config(page_title="MediSaathi", page_icon="💊", layout="wide")
st.markdown("<style>html, body, [class*='css'] {font-size: 18px;}</style>",
            unsafe_allow_html=True)
st.title("💊 MediSaathi")
st.warning("Reminder and information tool, not medical advice. "
           "Prices shown are SAMPLE DATA collected by hand.")

state = st.session_state
flow.ensure_session(state)          # exactly one AIIntegration per session

LANGUAGE_LABELS = {"en": "English", "hi": "हिन्दी", "hinglish": "Hinglish"}

records, doses, errors, view = [], [], [], None

tab_upload, tab_confirm, tab_results = st.tabs(["1. Upload", "2. Confirm", "3. Results"])

# ---------- 1. Upload ----------
with tab_upload:
    file = st.file_uploader("Photo of prescription", type=["jpg", "jpeg", "png"])
    flow.sync_upload(state, file.getvalue() if file else None)   # new/removed file -> fresh analysis
    if st.button("Use sample prescription (demo)", key="ai_sample"):
        flow.load_sample(state)
    if state["ai_image_bytes"]:
        st.image(state["ai_image_bytes"], width=400)
    if state["ai_status"] == "ready":
        if st.button("Analyze prescription", key="ai_analyze"):   # the only extraction trigger
            flow.analyze(state)
    if state["ai_status"] == "failed":
        if st.button("Retry extraction", key="ai_retry"):
            flow.retry(state)
    if state["ai_error"]:
        st.error(state["ai_error"]["message"])
    if state["ai_status"] == "extracted":
        st.success("Done. Open the Confirm tab.")

# ---------- 2. Confirm ----------
with tab_confirm:
    if state["ai_status"] != "extracted":
        st.info("Upload a prescription and click Analyze first.")
    else:
        st.caption("Check every row against the prescription. Fix anything wrong. "
                   "Blank or unclear fields: please check with your doctor. "
                   "'needs_review' is the reader's own flag; it is not your confirmation. "
                   "dose_quantity and dose_unit are your own notes, kept separate from the "
                   "prescription record.")
        with st.expander("Prescription image", expanded=True):
            st.image(state["ai_image_bytes"], width=400)
        with st.expander("What the AI originally read (read-only)"):
            st.dataframe(pd.DataFrame(flow.original_records(state), columns=list(flow.FIELDS)),
                         hide_index=True)

        df = pd.DataFrame(flow.baseline_rows(state), columns=list(flow.EDITOR_COLUMNS)).astype({
            "duration_days": "Int64", "confidence": "float64",
            "dose_quantity": "float64", "needs_review": "bool"})
        edited = st.data_editor(
            df, num_rows="dynamic", width="stretch", disabled=READ_ONLY_FIELDS,
            key=f"editor_{state['ai_generation']}",
            column_config={
                "form": st.column_config.SelectboxColumn(options=list(flow.FORM_OPTIONS)),
                "duration_days": st.column_config.NumberColumn(min_value=1, step=1),
                "confidence": st.column_config.NumberColumn(min_value=0.0, max_value=1.0),
                "dose_quantity": st.column_config.NumberColumn(
                    "dose_quantity", min_value=0.0, help="How much per dose, as written on the prescription"),
                "dose_unit": st.column_config.SelectboxColumn(
                    "dose_unit", options=UNIT_OPTIONS, help="Unit for that quantity"),
                "needs_review": st.column_config.CheckboxColumn(
                    default=True, help="The reader's flag. Ticking or unticking it does not confirm anything."),
            })
        records, doses, errors = flow.frame_to_state(edited.to_dict("records"), UNIT_OPTIONS)
        view = flow.current_view(records, doses, errors)

        if flow.sync_review(state, records, doses, errors):
            st.warning("You changed something after confirming. Please confirm again.")
        if errors:
            st.error("Fix these before confirming: " + " ".join(errors))

        needs_tick = bool(not errors and flow.needs_acknowledgement(records))
        ticked = True
        if needs_tick:
            ticked = st.checkbox(
                "I checked the blank or unclear values (and rows still marked needs_review) "
                "against my prescription. Blank values stay unknown.",
                key=f"ai_ack_{state['ai_generation']}_{view[:12]}")
        if st.button("Confirm all", key="ai_confirm", disabled=bool(errors) or (needs_tick and not ticked)):
            try:
                flow.confirm(state, records, doses, errors, unknowns_acknowledged=ticked)
            except flow.FlowError as problem:
                st.error(problem.message)
        if flow.is_confirmed(state, view):
            st.success("Confirmed. Open the Results tab.")

# ---------- 3. Results ----------
with tab_results:
    if not flow.is_confirmed(state, view):
        st.info("Confirm your medicines first.")
    else:
        t_explain, t1, t2, t3 = st.tabs(["Explanation", "Schedule", "Prices", "Refill"])
        with t_explain:
            language = st.radio("Language", list(LANGUAGE_LABELS), key="ai_language", horizontal=True,
                                format_func=LANGUAGE_LABELS.get)
            try:
                result = flow.get_explanation(state, view, language)
            except flow.FlowError as problem:
                st.error(problem.message)
            else:
                st.text(result["notice"])        # plain-text widgets only: values are untrusted
                if result["status"] == "empty":
                    st.info("No medicines were read. The confirmed list is empty.")
                for item in result["medicines"]:
                    lines = [f"Medicine {item['record_index'] + 1}"]
                    lines += [field["text"] for field in item["fields"]]
                    if item["glossary"]:
                        lines.append(item["glossary"]["text"])
                    st.text("\n".join(lines))
                if result["issues"]:
                    st.text("\n".join(f"Medicine {i['record_index'] + 1}: {i['text']}"
                                      for i in result["issues"]))
        for tab in (t1, t2, t3):
            tab.info("Not active in this version. Schedule, prices and refill alerts come in a later step.")
