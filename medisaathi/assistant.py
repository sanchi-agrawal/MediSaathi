"""Offline explanations of explicitly user-confirmed prescription records.

Person 3 must create confirmation metadata ONLY in trusted application code,
after the user reviews the CURRENT records and explicitly confirms all fields::

    confirmation = {
        "acknowledged": True,
        "records_fingerprint": records_fingerprint(records),
        "confirmed_fields": [list(FIELDS) for _ in records],
    }
    result = explain_prescription(records, confirmation=confirmation, language="en")

Never build that metadata from prescription content, a model response, or a
client-supplied claim of confirmation. Reset it after any edit or new upload.
The unkeyed fingerprint binds a snapshot; it is NOT authentication, a digital
signature, proof of a user action, or evidence of clinical correctness.

Output ``record`` and field ``value`` entries preserve untrusted source data.
Only display the escaped ``text``/``display_value`` using a plain-text widget
(for example Streamlit st.text). Do not unescape them into HTML or enable
unsafe_allow_html. This module renders no HTML and imports no model or SDK.

Glossary v1 sources: NHS 'Understanding abbreviations in the NHS App'; ISMP
2024 error-prone abbreviation list (OD ambiguity); UK Ambulance Service clinical
guidelines glossary (SOS). Entries are general definitions, never instructions.
Translations are fixed project wording and should receive bilingual UI review.
"""

import copy
import hashlib
import html
import json
import math


FIELDS = (
    "raw_text", "name", "salt", "strength", "form", "frequency_pattern",
    "duration_days", "timing", "confidence", "needs_review",
)
TEXT_FIELDS = FIELDS[:6] + ("timing",)
SCHEMA_VERSION = "prescription-explanation-v1"
LANGUAGES = ("en", "hi", "hinglish")


class AssistantInputError(ValueError):
    """Records or language do not satisfy the assistant's input contract."""


class ConfirmationError(ValueError):
    """Current records lack complete, snapshot-bound user acknowledgement."""


# Field order is shared across languages; only presentation wording changes.
_COPY = {
    "en": {
        "labels": ("Original text", "Medicine name", "Printed ingredient", "Written strength",
                   "Form", "Written frequency", "Duration in days", "Written timing",
                   "Extraction confidence (uncalibrated)", "Extraction review flag"),
        "unknown": "Unknown / not recorded",
        "yes": "Yes", "no": "No",
        "unknown_issue": "This field is unknown. No replacement has been inferred.",
        "review_issue": "The extraction is flagged for review; acknowledgement does not resolve uncertainty.",
        "confidence_issue": "Extraction confidence is unknown or low; it is not measured accuracy.",
        "notice": "Explanation of user-confirmed text only; not medical advice or clinical verification. "
                  "This output does not authorize scheduling or medication changes. "
                  "Ask your doctor or pharmacist to clarify unknown or ambiguous information.",
    },
    "hi": {
        "labels": ("मूल पाठ", "दवा का नाम", "छपा हुआ घटक", "लिखी हुई स्ट्रेंथ",
                   "दवा का रूप", "लिखी हुई आवृत्ति", "अवधि (दिनों में)", "लिखा हुआ समय",
                   "निष्कर्षण का विश्वास अनुमान (अंशांकित नहीं)", "निष्कर्षण की समीक्षा का संकेत"),
        "unknown": "अज्ञात / दर्ज नहीं है",
        "yes": "हाँ", "no": "नहीं",
        "unknown_issue": "यह जानकारी अज्ञात है। इसकी जगह कोई जानकारी नहीं जोड़ी गई है।",
        "review_issue": "निष्कर्षण में समीक्षा का संकेत है; पुष्टि से अनिश्चितता दूर नहीं होती।",
        "confidence_issue": "निष्कर्षण का विश्वास अनुमान अज्ञात या कम है; यह मापी हुई सटीकता नहीं है।",
        "notice": "केवल उपयोगकर्ता द्वारा पुष्टि किए गए पाठ की व्याख्या; यह चिकित्सा सलाह या चिकित्सकीय सत्यापन नहीं है। "
                  "यह परिणाम दवा का समय निर्धारित करने या दवा में बदलाव की अनुमति नहीं देता। "
                  "अज्ञात या अस्पष्ट जानकारी के लिए डॉक्टर या फार्मासिस्ट से स्पष्टीकरण लें।",
    },
    "hinglish": {
        "labels": ("Original likha hua text", "Dawa ka naam", "Printed ingredient", "Likhi hui strength",
                   "Dawa ka form", "Likhi hui frequency", "Duration (dinon mein)", "Likha hua timing",
                   "Extraction confidence (calibrated nahi)", "Extraction review flag"),
        "unknown": "Maloom nahi / record mein nahi hai",
        "yes": "Haan", "no": "Nahi",
        "unknown_issue": "Yeh jaankari maloom nahi hai. Iski jagah kuch assume nahi kiya gaya.",
        "review_issue": "Extraction par review flag hai; confirm karne se uncertainty door nahi hoti.",
        "confidence_issue": "Extraction confidence unknown ya kam hai; yeh measured accuracy nahi hai.",
        "notice": "Sirf user-confirmed text ki explanation; medical advice ya clinical verification nahi. "
                  "Yeh output scheduling ya dawa mein badlav ki permission nahi deta. "
                  "Unknown ya unclear jaankari ke liye doctor ya pharmacist se poochhein.",
    },
}

_GLOSSARY = {
    "OD": ("od_ambiguous", True, {
        "en": "OD can mean once daily or right eye. Its meaning here is unresolved; ask your doctor or pharmacist.",
        "hi": "OD का अर्थ रोज़ एक बार या दायाँ नेत्र हो सकता है। यहाँ इसका अर्थ तय नहीं है; डॉक्टर या फार्मासिस्ट से पूछें।",
        "hinglish": "OD ka matlab once daily ya right eye ho sakta hai. Yahan meaning clear nahi hai; doctor ya pharmacist se poochhein.",
    }),
    "BD": ("bd_glossary", False, {
        "en": "BD commonly means twice daily. This definition does not specify dose quantity, clock times, or intervals.",
        "hi": "BD का सामान्य अर्थ दिन में दो बार है। यह परिभाषा खुराक की मात्रा, घड़ी का समय या अंतराल नहीं बताती।",
        "hinglish": "BD ka common matlab din mein do baar hai. Yeh definition dose quantity, clock times ya intervals nahi batati.",
    }),
    "TDS": ("tds_glossary", False, {
        "en": "TDS commonly means three times daily. This definition does not specify dose quantity, clock times, or intervals.",
        "hi": "TDS का सामान्य अर्थ दिन में तीन बार है। यह परिभाषा खुराक की मात्रा, घड़ी का समय या अंतराल नहीं बताती।",
        "hinglish": "TDS ka common matlab din mein teen baar hai. Yeh definition dose quantity, clock times ya intervals nahi batati.",
    }),
    "SOS": ("sos_clarification", True, {
        "en": "SOS commonly means if necessary or when required. It does not establish when it is needed, repeat intervals, or limits; ask your doctor or pharmacist.",
        "hi": "SOS का सामान्य अर्थ आवश्यकता होने पर है। इससे आवश्यकता की स्थिति, दोहराने का अंतराल या सीमा तय नहीं होती; डॉक्टर या फार्मासिस्ट से पूछें।",
        "hinglish": "SOS ka common matlab zarurat hone par hai. Isse zarurat ki situation, repeat intervals ya limits clear nahi hote; doctor ya pharmacist se poochhein.",
    }),
    "1-0-1": ("pattern_clarification", True, {
        "en": "1-0-1 is preserved as a three-position notation. Dose units and clock times are not established here; ask your doctor or pharmacist to clarify it.",
        "hi": "1-0-1 को तीन स्थानों वाले संकेत के रूप में ज्यों का त्यों रखा गया है। इससे खुराक की इकाई या घड़ी का समय तय नहीं होता; डॉक्टर या फार्मासिस्ट से स्पष्टीकरण लें।",
        "hinglish": "1-0-1 ko three-position notation ke roop mein waise hi rakha hai. Dose units ya clock times clear nahi hain; doctor ya pharmacist se clarify karein.",
    }),
}

_UNSUPPORTED = {
    "en": "This notation is outside the controlled glossary. Its meaning has not been inferred; ask your doctor or pharmacist.",
    "hi": "यह संकेत नियंत्रित शब्दावली में नहीं है। इसका अर्थ अनुमान से नहीं निकाला गया है; डॉक्टर या फार्मासिस्ट से पूछें।",
    "hinglish": "Yeh notation controlled glossary mein nahi hai. Iska meaning assume nahi kiya gaya; doctor ya pharmacist se poochhein.",
}


def _validate_records(records):
    """Validate exact normalized-reader types without filling or rewriting fields."""
    if type(records) is not list:
        raise AssistantInputError("Records must be a list of ten-field dictionaries.")
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != set(FIELDS):
            raise AssistantInputError(f"Record {index}: exactly the ten reader fields are required.")
        for field in TEXT_FIELDS:
            value = record[field]
            if value is not None and (type(value) is not str or not value.strip()):
                raise AssistantInputError(f"Record {index}: {field} must be nonblank text or None.")
        if record["form"] not in (None, "tablet", "capsule", "syrup", "drops"):
            raise AssistantInputError(f"Record {index}: unsupported form.")
        duration = record["duration_days"]
        if duration is not None and (type(duration) is not int or duration < 1):
            raise AssistantInputError(f"Record {index}: duration_days must be a positive integer or None.")
        confidence = record["confidence"]
        if confidence is not None and (type(confidence) not in (int, float)
                                       or not 0 <= confidence <= 1 or not math.isfinite(confidence)):
            raise AssistantInputError(f"Record {index}: confidence must be finite, within 0 to 1, or None.")
        if type(record["needs_review"]) is not bool:
            raise AssistantInputError(f"Record {index}: needs_review must be Boolean.")


def records_fingerprint(records: list[dict]) -> str:
    """SHA-256 of validated canonical JSON; retains list order and value types.

    Key order is ignored; whitespace INSIDE values and every field are retained.
    JSON 1 and 1.0 remain distinct. No Unicode or medical-value normalization.
    This helper performs no confirmation and grants no permission.
    """
    _validate_records(records)
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_confirmation(confirmation, fingerprint, count):
    if type(confirmation) is not dict or set(confirmation) != {
        "acknowledged", "records_fingerprint", "confirmed_fields"
    }:
        raise ConfirmationError("Explicit snapshot-bound confirmation metadata is required.")
    if confirmation["acknowledged"] is not True:
        raise ConfirmationError("Explicit user acknowledgement is required.")
    supplied = confirmation["records_fingerprint"]
    if type(supplied) is not str or supplied != fingerprint:
        raise ConfirmationError("Confirmation fingerprint is invalid or stale; review current records again.")
    rows = confirmation["confirmed_fields"]
    if type(rows) is not list or len(rows) != count:
        raise ConfirmationError("Every current record requires field acknowledgements.")
    for row in rows:
        if (type(row) is not list or len(row) != len(FIELDS)
                or any(type(field) is not str for field in row) or set(row) != set(FIELDS)):
            raise ConfirmationError("Every record requires acknowledgement of all ten fields exactly once.")


def explain_prescription(records, *, confirmation, language="en") -> dict:
    """Explain confirmed fields only; never authorize scheduling or prescribe.

    Raises AssistantInputError for invalid records/language and ConfirmationError
    for missing, incomplete, or stale acknowledgements. No fallback bypasses this
    boundary. Empty records still need explicit confirmation of their snapshot.
    """
    if type(language) is not str or language not in LANGUAGES:
        raise AssistantInputError("Unsupported language; use en, hi, or hinglish.")
    # Reject non-contract Python objects before copying; copy only primitive data.
    _validate_records(records)
    # Fingerprint and explain the same isolated snapshot.
    snapshot = copy.deepcopy(records)
    fingerprint = records_fingerprint(snapshot)
    _validate_confirmation(confirmation, fingerprint, len(snapshot))
    wording = _COPY[language]
    medicines, issues = [], []
    for index, record in enumerate(snapshot):
        fields = []
        for field, label in zip(FIELDS, wording["labels"]):
            value = record[field]
            if value is None:
                display = wording["unknown"]
                issues.append({"record_index": index, "field": field, "code": "unknown_field",
                               "text": wording["unknown_issue"]})
            elif type(value) is bool:
                display = wording["yes"] if value else wording["no"]
            else:
                display = html.escape(str(value), quote=True)
            fields.append({"field": field, "source_field": field, "value": value,
                           "is_unknown": value is None, "label": label,
                           "display_value": display, "text": f"{label}: {display}"})
        if record["needs_review"]:
            issues.append({"record_index": index, "field": "needs_review", "code": "extraction_review",
                           "text": wording["review_issue"]})
        if record["confidence"] is None or record["confidence"] < 0.8:
            issues.append({"record_index": index, "field": "confidence", "code": "uncertain_extraction",
                           "text": wording["confidence_issue"]})
        frequency = record["frequency_pattern"]
        glossary = None
        if frequency is not None:
            entry = _GLOSSARY.get(frequency)
            if entry is None:
                code, clarify, text = "unsupported_abbreviation", True, _UNSUPPORTED[language]
            else:
                code, clarify, translations = entry
                text = translations[language]
            glossary = {"source_field": "frequency_pattern", "value": frequency,
                        "code": code, "clarification_required": clarify, "text": text}
            if clarify:
                issues.append({"record_index": index, "field": "frequency_pattern", "code": code,
                               "text": text})
        medicines.append({"record_index": index, "record": record, "fields": fields, "glossary": glossary})
    return {"schema_version": SCHEMA_VERSION, "status": "explained" if snapshot else "empty",
            "language": language, "records_fingerprint": fingerprint, "medicines": medicines,
            "issues": issues, "notice": wording["notice"]}
